# Laboratorio 3 — Protocolos de Enrutamiento (CC3067 Redes)

Implementación del protocolo **Link State** definido para el Laboratorio 3.

El proyecto implementa:

* HELLO / HELLO_ACK para verificar vecinos.
* LSA y flooding.
* Construcción del grafo de la red.
* Algoritmo de Dijkstra.
* Generación de tablas de enrutamiento.
* Envío de mensajes cliente → servidor.
* Hamming(7,4) entre routers.
* Detección de caída y recuperación de enlaces.
* Ejecución concurrente mediante threads.

Los mensajes intercambiados entre routers respetan el formato definido en el documento de protocolo. Los LSA contienen únicamente la información de enlaces entre routers.

## Estructura del proyecto

```text
lab3/
├── hamming.py
├── common.py
├── node.py
├── client.py
├── server.py
├── README.md
└── configs/
    ├── config_A.json
    ├── config_B.json
    ├── config_C.json
    ├── config_cliente1.json
    └── config_servidor1.json
```

Cada router genera automáticamente su archivo:

```text
<node_id>_tabla_enrutamiento.csv
```

Por ejemplo:

```text
A_tabla_enrutamiento.csv
B_tabla_enrutamiento.csv
C_tabla_enrutamiento.csv
```

Requisitos:

* Python 3.10+
* No se requieren librerías externas.

## Programas

### `node.py` — Router

Representa un router de la topología.

Cada instancia recibe un archivo de configuración diferente:

```bash
python node.py configs/config_A.json
python node.py configs/config_B.json
python node.py configs/config_C.json
```

El router implementa dos funciones principales.

**Plano de control:**

* Envía HELLO periódicamente.
* Responde HELLO_ACK.
* Detecta enlaces caídos.
* Genera LSA.
* Propaga LSA mediante flooding.
* Mantiene una base de datos Link State.
* Ejecuta Dijkstra.
* Genera la tabla de enrutamiento.

**Plano de datos:**

* Recibe mensajes.
* Decodifica Hamming cuando el mensaje viene de otro router.
* Identifica el destino final.
* Determina el router gateway del destino.
* Consulta la tabla de enrutamiento.
* Reenvía al siguiente salto.
* Entrega el mensaje al servidor si está conectado localmente.

El router utiliza un único socket de escucha. El contenido recibido se diferencia de la siguiente forma:

* Si es JSON válido, puede ser `HELLO`, `HELLO_ACK`, `LSA` o `MESSAGE`.
* Si no es JSON válido, se interpreta como una cadena de bits codificada mediante Hamming(7,4) proveniente de otro router.

### `client.py` — Cliente

El cliente no participa en Link State.

Conoce únicamente su router gateway y el `node_id` del servidor al que desea enviar mensajes.

El mensaje se construye como:

```json
{
  "type": "MESSAGE",
  "from": "cliente1",
  "to": "servidor1",
  "hops": 0,
  "payload": "Hola servidor"
}
```

El tramo:

```text
cliente → router gateway
```

utiliza JSON plano, sin Hamming.

### `server.py` — Servidor

El servidor tampoco participa en Link State.

Escucha en su IP y puerto y espera que su router gateway le entregue el mensaje final.

El último tramo:

```text
router gateway → servidor
```

también utiliza JSON plano, sin Hamming.

### `common.py`

Contiene funciones auxiliares para la comunicación mediante sockets TCP.

Los mensajes de texto utilizan:

```text
UTF-8
```

y terminan con:

```text
\n
```

para indicar el final de cada mensaje.

También contiene funciones para:

* enviar líneas;
* recibir líneas;
* enviar JSON;
* abrir una conexión corta hacia una IP y puerto.

### `hamming.py`

Implementa Hamming(7,4).

Cada bloque utiliza:

```text
posición:  1  2  3  4  5  6  7
bit:       p1 p2 d1 p3 d2 d3 d4
```

Los bits de paridad se encuentran en las posiciones 1, 2 y 4.

Hamming se utiliza únicamente en los saltos:

```text
router → router
```

No se utiliza en:

```text
cliente → gateway
gateway → servidor
```

## Configuración de routers

Cada router tiene un archivo JSON con su identidad y sus vecinos directos.

Ejemplo:

```json
{
  "node_id": "B",
  "listen_ip": "127.0.0.1",
  "listen_port": 6002,
  "role": "router",
  "neighbors": [
    {
      "node_id": "A",
      "ip": "127.0.0.1",
      "port": 6001,
      "cost": 2
    },
    {
      "node_id": "C",
      "ip": "127.0.0.1",
      "port": 6003,
      "cost": 3
    }
  ],
  "endpoint_routes": {
    "servidor1": "C"
  }
}
```

Cada router conoce inicialmente únicamente a sus vecinos directos.

El campo local:

```json
"endpoint_routes": {
  "servidor1": "C"
}
```

indica que el router gateway conocido para `servidor1` es `C`.

Esta información es únicamente configuración interna de la implementación.

**`endpoint_routes` no se transmite por sockets, no forma parte de los LSA y no modifica el protocolo intercambiado con las otras implementaciones.**

En la topología final, el valor se cambia por el router que funcione como gateway real del servidor.

Por ejemplo, si el servidor está conectado a `F`:

```json
"endpoint_routes": {
  "servidor1": "F"
}
```

## Endpoints locales

Un router que tenga conectado directamente un cliente o servidor puede utilizar:

```json
"local_endpoints": [
  {
    "node_id": "servidor1",
    "ip": "127.0.0.1",
    "port": 9002
  }
]
```

`local_endpoints` también es información local de la implementación.

No se anuncia mediante LSA.

Sirve para que el router gateway final pueda determinar la IP y puerto donde debe entregar el mensaje.

Por ejemplo:

```text
C
|
| servidor1 es local
v
servidor1
```

## Mensajes del protocolo

### HELLO

```json
{
  "type": "HELLO",
  "from": "A"
}
```

Se envía periódicamente a los vecinos directos.

### HELLO_ACK

```json
{
  "type": "HELLO_ACK",
  "from": "B",
  "to": "A"
}
```

Confirma que el vecino continúa disponible.

### LSA

```json
{
  "type": "LSA",
  "origin": "A",
  "seq": 3,
  "links": [
    {
      "to": "B",
      "cost": 2
    }
  ],
  "from": "A"
}
```

Los LSA contienen únicamente la información definida para Link State.

No se agregan clientes o servidores al LSA.

Los campos principales son:

* `origin`: router que creó originalmente el LSA.
* `seq`: número de secuencia.
* `links`: vecinos y costos anunciados por `origin`.
* `from`: router que reenvió inmediatamente el LSA.

### MESSAGE

```json
{
  "type": "MESSAGE",
  "from": "cliente1",
  "to": "servidor1",
  "hops": 0,
  "payload": "Hola servidor"
}
```

`from` y `to` representan los endpoints finales.

`hops` aumenta en uno cada vez que el mensaje es procesado por un router.

`payload` contiene el mensaje de aplicación.

## HELLO y detección de enlaces

Los valores actuales son:

```python
HELLO_INTERVAL = 4
HELLO_TIMEOUT = 12
MONITOR_INTERVAL = 3
```

Cada router envía HELLO periódicamente a sus vecinos.

Si un router deja de recibir HELLO_ACK de un vecino durante el tiempo definido por `HELLO_TIMEOUT`, el enlace se marca como caído.

Por ejemplo:

```text
[A] Enlace con B marcado como CAIDO (sin HELLO_ACK en 12s).
```

El router genera entonces un nuevo LSA sin ese enlace.

Si el vecino vuelve a responder:

```text
[A] Enlace con B recuperado.
```

se genera un nuevo LSA y las rutas se vuelven a calcular.

## LSA y flooding

Cada router genera un LSA que describe sus enlaces activos.

Por ejemplo:

```text
A --2-- B --3-- C
```

A anuncia:

```text
A → B costo 2
```

B anuncia:

```text
B → A costo 2
B → C costo 3
```

C anuncia:

```text
C → B costo 3
```

Los LSA se distribuyen mediante flooding.

Un router solo procesa un LSA si su número de secuencia es mayor al último conocido para ese `origin`.

Esto evita procesar repetidamente información vieja.

## Dijkstra

Con los LSA recibidos, cada router construye una representación del grafo.

Después ejecuta Dijkstra desde sí mismo.

Para:

```text
A --2-- B --3-- C
```

A calcula:

```text
A → B = 2
A → B → C = 5
```

Su tabla queda:

```csv
destino,siguiente_salto,ip,puerto,costo
B,B,127.0.0.1,6002,2
C,B,127.0.0.1,6002,5
```

El campo `siguiente_salto` representa el vecino directo al que debe entregarse el mensaje.

Para llegar de A a C:

```text
destino final de red = C
siguiente salto desde A = B
```

Las tablas de enrutamiento contienen rutas hacia **routers**.

Los clientes y servidores no participan en Link State y no se agregan como destinos calculados por Dijkstra.

## Routing hacia el servidor

El campo `to` del MESSAGE continúa siendo el endpoint final:

```text
to = servidor1
```

Los routers conocen mediante configuración local qué router funciona como gateway del servidor.

Ejemplo:

```text
servidor1 → C
```

Si A recibe:

```text
to = servidor1
```

realiza:

```text
servidor1
    ↓
endpoint_routes
    ↓
C
    ↓
routing_table["C"]
    ↓
siguiente salto = B
```

El MESSAGE no cambia su campo `to`.

Continúa siendo:

```text
to = servidor1
```

durante todo el recorrido.

Cuando el mensaje llega a C, C encuentra:

```text
servidor1
```

dentro de sus `local_endpoints` y lo entrega directamente.

## Flujo completo de un MESSAGE

Para la topología local:

```text
cliente1 ─ A ─ B ─ C ─ servidor1
```

el flujo es:

```text
cliente1
    |
    | JSON plano
    v
    A
    |
    | Hamming(7,4)
    v
    B
    |
    | Hamming(7,4)
    v
    C
    |
    | JSON plano
    v
servidor1
```

El contador `hops` cambia así:

```text
cliente1 crea MESSAGE    hops=0
A procesa                hops=1
B procesa                hops=2
C procesa                hops=3
servidor recibe          hops=3
```

## Prueba local

La configuración de prueba utiliza:

```text
cliente1 ── A ── B ── C ── servidor1
              2       3
```

Todos los procesos se ejecutan en:

```text
127.0.0.1
```

Los puertos son:

```text
A          6001
B          6002
C          6003
cliente1   9001
servidor1  9002
```

Abrir cinco terminales.

### Terminal 1

```bash
python node.py configs/config_A.json
```

### Terminal 2

```bash
python node.py configs/config_B.json
```

### Terminal 3

```bash
python node.py configs/config_C.json
```

Esperar unos segundos para permitir que los routers intercambien HELLO, LSA y calculen sus tablas.

### Terminal 4

```bash
python server.py configs/config_servidor1.json
```

### Terminal 5

```bash
python client.py configs/config_cliente1.json
```

Escribir:

```text
Hola Servidor
```

El recorrido esperado es:

```text
[A] MESSAGE from=cliente1 to=servidor1 hops=1 payload='Hola Servidor'

[B] MESSAGE from=cliente1 to=servidor1 hops=2 payload='Hola Servidor'

[C] MESSAGE from=cliente1 to=servidor1 hops=3 payload='Hola Servidor'
```

Y finalmente:

```text
[servidor1] Mensaje de cliente1 (hops=3): Hola Servidor
```

## Prueba de caída de enlace

Con A, B y C funcionando, detener B con:

```text
Ctrl+C
```

Después de aproximadamente 12 segundos, A y C deberían marcar el enlace como caído.

Como A ya no tiene una ruta hacia C, un mensaje nuevo debe descartarse.

Al volver a iniciar B:

```bash
python node.py configs/config_B.json
```

los enlaces deberían recuperarse, propagarse nuevos LSA y Dijkstra debería reconstruir las rutas.

## Prueba entre dos computadoras sin Tailscale

También se puede probar utilizando dos computadoras conectadas a la misma red local.

Ejemplo:

```text
PC 1                           PC 2

cliente1                       servidor1
   |                               |
   A ───── B ───────────────────── C
```

Primero obtener la dirección IPv4 de cada computadora:

```powershell
ipconfig
```

Ejemplo:

```text
PC 1: 192.168.1.10
PC 2: 192.168.1.20
```

Para aceptar conexiones desde otras computadoras se puede configurar:

```json
"listen_ip": "0.0.0.0"
```

Las direcciones dentro de `neighbors`, en cambio, deben ser las IP reales de las computadoras.

Por ejemplo, si B está en PC1 y C en PC2:

B debe conocer:

```json
{
  "node_id": "C",
  "ip": "192.168.1.20",
  "port": 6003,
  "cost": 3
}
```

C debe conocer:

```json
{
  "node_id": "B",
  "ip": "192.168.1.10",
  "port": 6002,
  "cost": 3
}
```

Se puede comprobar la conectividad con:

```powershell
ping 192.168.1.20
```

y verificar el puerto:

```powershell
Test-NetConnection 192.168.1.20 -Port 6003
```

Se espera:

```text
TcpTestSucceeded : True
```

El firewall del sistema operativo debe permitir las conexiones entrantes de Python en la red privada.

## Prueba con Tailscale

Para la prueba con las demás parejas se utilizan las IP asignadas por Tailscale.

La lógica del programa no cambia.

En lugar de:

```text
127.0.0.1
```

o:

```text
192.168.x.x
```

los vecinos que estén en otras computadoras utilizan su IP correspondiente de Tailscale.

Ejemplo:

```json
{
  "node_id": "D",
  "ip": "100.x.x.x",
  "port": 6004,
  "cost": 1
}
```

Cada router debe tener en `neighbors` únicamente sus vecinos directos de la topología.

No necesita conocer las IP de todos los routers de la red.

Por ejemplo:

```text
A ─ B ─ C ─ D ─ E ─ F
```

si C y D pertenecen a implementaciones diferentes, únicamente necesitan tener configurado correctamente el enlace:

```text
C ↔ D
```

C conoce la IP/puerto de D y D conoce la IP/puerto de C.

Los LSA propagados mediante flooding permiten que posteriormente cada router conozca la topología completa.

## Interoperabilidad

Las implementaciones de las diferentes parejas pueden estar estructuradas de manera distinta.

Lo importante es que los mensajes intercambiados por sockets respeten el protocolo acordado.

Se debe mantener compatible:

* Formato de HELLO.
* Formato de HELLO_ACK.
* Formato de LSA.
* Formato de MESSAGE.
* Nombres y casing de los campos JSON.
* Delimitador `\n`.
* Codificación UTF-8.
* Hamming(7,4).
* Posiciones de paridad 1, 2 y 4.
* Criterio acordado para detección de enlaces caídos.

Elementos como:

```text
endpoint_routes
local_endpoints
```

son detalles internos de esta implementación y **no se transmiten a las implementaciones de las otras parejas**.

En particular, un LSA enviado a otro router mantiene el formato:

```json
{
  "type": "LSA",
  "origin": "A",
  "seq": 3,
  "links": [
    {
      "to": "B",
      "cost": 2
    }
  ],
  "from": "A"
}
```

sin agregar campos adicionales de endpoints.

## Resumen del funcionamiento

```text
config.json
    |
    v
Router inicia
    |
    +--> HELLO / HELLO_ACK
    |         |
    |         v
    |   estado de vecinos
    |
    +--> generar LSA
    |         |
    |         v
    |      flooding
    |         |
    |         v
    |       LSDB
    |         |
    |         v
    |      Dijkstra
    |         |
    |         v
    | tabla_enrutamiento.csv
    |
    +--> recibir MESSAGE
              |
              v
       decodificar Hamming
       si viene de router
              |
              v
          leer "to"
              |
              v
     determinar gateway
              |
              v
       consultar tabla
              |
              v
      siguiente salto
              |
        +-----+-----+
        |           |
        v           v
   otro router   endpoint local
     Hamming       JSON plano
```
