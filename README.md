# Laboratorio 3 — Protocolos de Enrutamiento (CC3067 Redes)

Implementación del protocolo **Link State** para el Laboratorio 3 de Redes.

El proyecto implementa:

* HELLO / HELLO_ACK para verificar vecinos.
* LSA y flooding.
* Construcción del grafo de la red.
* Algoritmo de Dijkstra.
* Generación automática de tablas de enrutamiento.
* Envío de mensajes cliente → servidor.
* Sistema ATM → banco sobre la misma red.
* Hamming(7,4) entre routers.
* Detección de caída y recuperación de enlaces.
* Ejecución concurrente mediante threads.

Los mensajes intercambiados entre routers respetan el formato definido en el protocolo. Los LSA contienen únicamente información sobre los enlaces entre routers.

## Estructura del proyecto

```text
lab3/
├── hamming.py
├── common.py
├── node.py
├── client.py
├── server.py
├── atm_client.py
├── atm_server.py
├── README.md
├── configs/
│   ├── config_A.json
│   ├── config_B.json
│   ├── config_C.json
│   ├── config_cliente1.json
│   ├── config_servidor1.json
│   ├── config_atm1.json
│   └── config_bank1.json
└── <node_id>_tabla_enrutamiento.csv
```

Cada router genera automáticamente su archivo de tabla de enrutamiento:

```text
<node_id>_tabla_enrutamiento.csv
```

Por ejemplo:

```text
A_tabla_enrutamiento.csv
B_tabla_enrutamiento.csv
C_tabla_enrutamiento.csv
```

## Requisitos

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
* Responde con HELLO_ACK.
* Detecta enlaces caídos.
* Genera LSA.
* Propaga LSA mediante flooding.
* Mantiene una base de datos Link State (LSDB).
* Ejecuta Dijkstra.
* Genera la tabla de enrutamiento.

**Plano de datos:**

* Recibe mensajes.
* Decodifica Hamming cuando el mensaje viene de otro router.
* Identifica el destino final.
* Determina el router gateway del destino.
* Consulta la tabla de enrutamiento.
* Reenvía el mensaje al siguiente salto.
* Entrega el mensaje directamente si el destino es un endpoint local.

El router utiliza un único socket de escucha. El contenido recibido se diferencia de la siguiente forma:

* Si es JSON válido, puede ser `HELLO`, `HELLO_ACK`, `LSA` o `MESSAGE`.
* Si no es JSON válido, se interpreta como una cadena de bits codificada mediante Hamming(7,4) proveniente de otro router.

### `client.py` — Cliente

El cliente no participa en Link State.

Conoce únicamente su router gateway y el `node_id` del servidor al que desea enviar mensajes.

Ejemplo de un mensaje:

```json
{
  "type": "MESSAGE",
  "from": "cliente1",
  "to": "servidor1",
  "hops": 0,
  "payload": "Hola Servidor"
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

utiliza JSON plano, sin Hamming.

### `atm_client.py` — Cliente ATM

Representa un cajero automático conectado a la red.

El ATM no participa directamente en Link State. Conoce únicamente:

* Su router gateway.
* El identificador del banco destino.

El ATM permite realizar las siguientes operaciones:

1. Iniciar sesión.
2. Consultar saldo.
3. Retirar dinero.
4. Depositar dinero.
5. Cerrar sesión.

Cada solicitud utiliza un `request_id` para relacionar una petición con su respuesta.

Después de un inicio de sesión exitoso, el banco proporciona un token de sesión que se utiliza en las operaciones posteriores.

A diferencia del cliente simple, el ATM también mantiene un socket de escucha para recibir las respuestas enviadas por el banco.

### `atm_server.py` — Servidor bancario

Representa el servidor bancario conectado a la red.

No participa en Link State y utiliza su router gateway para enviar las respuestas hacia el ATM.

Implementa las operaciones:

* `LOGIN`
* `BALANCE`
* `WITHDRAW`
* `DEPOSIT`
* `LOGOUT`

Las cuentas utilizadas para las pruebas se cargan desde `config_bank1.json`.

Las modificaciones de saldo se mantienen en memoria mientras el proceso del banco se encuentra en ejecución.

### `common.py`

Contiene funciones auxiliares para la comunicación mediante sockets TCP.

Los mensajes utilizan UTF-8 y terminan con:

```text
\n
```

para indicar el final de cada mensaje.

También contiene funciones para:

* Enviar líneas.
* Recibir líneas.
* Enviar JSON.
* Abrir conexiones cortas hacia una IP y puerto.

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

No se utiliza directamente en:

```text
cliente/ATM → gateway
gateway → servidor/banco
```

## Configuración de routers

Cada router tiene un archivo JSON con su identidad y sus vecinos directos.

Ejemplo para B:

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
    "servidor1": "C",
    "bank1": "C",
    "atm1": "A"
  }
}
```

Cada router conoce inicialmente únicamente a sus vecinos directos.

`endpoint_routes` contiene información local utilizada para determinar qué router funciona como gateway de un endpoint final.

Esta información:

* No se transmite por sockets.
* No forma parte de los LSA.
* No modifica el protocolo compartido con otras implementaciones.

## Endpoints locales

Los endpoints conectados directamente a un router se especifican mediante `local_endpoints`.

En la topología local:

```text
cliente1 ─┐                 ┌─ servidor1
          │                 │
          A ──(2)── B ──(3)── C
          │                 │
atm1 ─────┘                 └─ bank1
```

A tiene conectados localmente:

```text
cliente1
atm1
```

C tiene conectados localmente:

```text
servidor1
bank1
```

Los endpoints no participan en Dijkstra ni son anunciados mediante LSA.

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

Los campos principales son:

* `origin`: router que creó originalmente el LSA.
* `seq`: número de secuencia.
* `links`: vecinos activos y costos anunciados.
* `from`: router que envió inmediatamente el LSA.

Los clientes, servidores, ATM y banco no se incluyen en los LSA.

### MESSAGE

```json
{
  "type": "MESSAGE",
  "from": "cliente1",
  "to": "servidor1",
  "hops": 0,
  "payload": "Hola Servidor"
}
```

`from` y `to` representan los endpoints finales.

`hops` aumenta en uno cada vez que el mensaje es procesado por un router.

`payload` contiene la información de aplicación.

Las solicitudes ATM utilizan el mismo tipo `MESSAGE`, pero el `payload` contiene un JSON serializado con la operación bancaria.

## HELLO y detección de enlaces

Los valores utilizados son:

```python
HELLO_INTERVAL = 4
HELLO_TIMEOUT = 12
MONITOR_INTERVAL = 3
```

Cada router envía HELLO periódicamente a sus vecinos.

Si un router deja de recibir HELLO_ACK de un vecino durante aproximadamente 12 segundos, el enlace se marca como caído.

Ejemplo:

```text
[A] Enlace con B marcado como CAIDO (sin HELLO_ACK en 12s).
```

El router genera entonces un nuevo LSA sin ese enlace y vuelve a calcular las rutas.

Cuando el vecino vuelve a responder:

```text
[A] Enlace con B recuperado.
```

se genera un nuevo LSA y las rutas vuelven a calcularse.

## LSA y flooding

Cada router genera un LSA que describe sus enlaces activos.

Para:

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

Un router solamente procesa un LSA si su número de secuencia es mayor al último conocido para ese `origin`.

## Dijkstra

Con los LSA recibidos, cada router construye una representación del grafo y ejecuta Dijkstra desde sí mismo.

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

El campo `siguiente_salto` representa el vecino directo al que debe enviarse el mensaje.

Las tablas de enrutamiento contienen rutas hacia routers. Los endpoints no participan directamente en Dijkstra.

## Flujo cliente → servidor

Para la topología local:

```text
cliente1
   |
   | JSON
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
   | JSON
   v
servidor1
```

El contador `hops` esperado es:

```text
cliente1 crea MESSAGE    hops=0
A procesa                hops=1
B procesa                hops=2
C procesa                hops=3
servidor recibe          hops=3
```

## Flujo ATM → banco

Las solicitudes del ATM siguen:

```text
atm1
 |
 | JSON
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
 | JSON
 v
bank1
```

Las respuestas utilizan el camino inverso:

```text
bank1
 |
 v
 C
 |
 v
 B
 |
 v
 A
 |
 v
atm1
```

El routing se realiza de la misma manera que para cualquier otro `MESSAGE`.

## Prueba local

Todos los procesos pueden ejecutarse en una sola computadora utilizando:

```text
127.0.0.1
```

Puertos utilizados:

```text
A          6001
B          6002
C          6003
cliente1   9001
servidor1  9002
atm1       9003
bank1      9004
```

Abrir siete terminales.

### Terminal 1 — Router A

```bash
python node.py configs/config_A.json
```

### Terminal 2 — Router B

```bash
python node.py configs/config_B.json
```

### Terminal 3 — Router C

```bash
python node.py configs/config_C.json
```

Esperar unos segundos para permitir el intercambio de HELLO, HELLO_ACK y LSA y el cálculo de las tablas.

### Terminal 4 — Servidor

```bash
python server.py configs/config_servidor1.json
```

### Terminal 5 — Cliente

```bash
python client.py configs/config_cliente1.json
```

Escribir, por ejemplo:

```text
Hola
```

El recorrido esperado es:

```text
[A] MESSAGE from=cliente1 to=servidor1 hops=1 payload='Hola'
[B] MESSAGE from=cliente1 to=servidor1 hops=2 payload='Hola'
[C] MESSAGE from=cliente1 to=servidor1 hops=3 payload='Hola'
```

Finalmente el servidor debe recibir:

```text
[servidor1] Mensaje de cliente1 (hops=3): Hola
```

### Terminal 6 — Banco

```bash
python atm_server.py configs/config_bank1.json
```

### Terminal 7 — ATM

```bash
python atm_client.py configs/config_atm1.json
```

El ATM muestra el menú:

```text
1) Iniciar sesión
2) Consultar saldo
3) Retirar
4) Depositar
5) Cerrar sesión
0) Salir
```

Para la configuración de prueba se puede iniciar sesión con:

```text
Tarjeta: 4000-0001
PIN: 1234
```

Después se pueden probar las operaciones de consulta de saldo, retiro, depósito y cierre de sesión.

## Prueba de caída y recuperación de enlace

Con A, B y C funcionando, detener B utilizando:

```text
Ctrl+C
```

Después de aproximadamente 12 segundos, A y C deberían detectar la caída:

```text
[A] Enlace con B marcado como CAIDO (sin HELLO_ACK en 12s).
[C] Enlace con B marcado como CAIDO (sin HELLO_ACK en 12s).
```

Como la topología local no posee una ruta alternativa entre A y C, A deja de tener una ruta disponible hacia C.

Al volver a iniciar B:

```bash
python node.py configs/config_B.json
```

A y C deberían detectar la recuperación:

```text
[A] Enlace con B recuperado.
[C] Enlace con B recuperado.
```

Los nuevos LSA se propagan y las tablas de enrutamiento se reconstruyen.

Después de la convergencia, los mensajes cliente → servidor y ATM → banco vuelven a atravesar A → B → C normalmente.

## Prueba con Tailscale

Para las pruebas con las demás parejas se utilizan las direcciones IP asignadas por Tailscale.

La lógica del programa no cambia.

Cada router debe tener en `neighbors` únicamente sus vecinos directos de la topología.

Las IP configuradas como `127.0.0.1` durante las pruebas locales deben sustituirse por las direcciones correspondientes de Tailscale cuando el vecino se encuentre en otra computadora.

Por ejemplo:

```json
{
  "node_id": "D",
  "ip": "100.x.x.x",
  "port": 6004,
  "cost": 1
}
```

Cada router necesita conocer directamente solamente la IP y puerto de sus vecinos.

Los LSA propagados mediante flooding permiten que posteriormente los routers construyan una vista de la topología completa.

## Interoperabilidad

Las implementaciones de las diferentes parejas pueden tener estructuras internas diferentes.

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

son detalles internos de esta implementación y no se transmiten a las implementaciones de otras parejas.

## Resumen del funcionamiento

```text
                 config.json
                      |
                      v
                 Router inicia
                      |
          +-----------+-----------+
          |                       |
          v                       v
 HELLO / HELLO_ACK           recibir MESSAGE
          |                       |
          v                       v
 estado de vecinos          identificar "to"
          |                       |
          v                       v
      generar LSA           endpoint local?
          |                    /       \
          v                  sí         no
       flooding              |          |
          |                  v          v
          v              entregar   endpoint_routes
         LSDB               JSON        |
          |                             v
          v                       router gateway
       Dijkstra                       |
          |                           v
          v                    tabla de rutas
 tabla_enrutamiento.csv               |
                                      v
                               siguiente salto
                                  /        \
                                 v          v
                           otro router   endpoint
                            Hamming       JSON
```
