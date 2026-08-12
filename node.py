"""
node.py — Nodo Router (Laboratorio 3, CC3067 Redes)

Implementa:
- HELLO / HELLO_ACK
- LSA + flooding
- Dijkstra
- Tabla de enrutamiento
- Forwarding de MESSAGE
- Hamming(7,4) entre routers

Los LSA contienen únicamente la información definida en el protocolo.
La relación endpoint -> gateway se conoce localmente mediante endpoint_routes.
"""

import sys
import json
import socket
import threading
import time
import heapq
import csv

from hamming import encode_message, decode_message
from common import recv_line, send_json_to, send_line_to


HELLO_INTERVAL = 4
HELLO_TIMEOUT = 12
MONITOR_INTERVAL = 3


class Node:
    def __init__(self, config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = json.load(f)

        self.node_id = self.cfg["node_id"]
        self.listen_ip = self.cfg["listen_ip"]
        self.listen_port = self.cfg["listen_port"]
        self.role = self.cfg.get("role", "router")

        # Vecinos directos del router
        self.neighbors = {
            n["node_id"]: n
            for n in self.cfg.get("neighbors", [])
        }

        # Clientes/servidores conectados directamente a este router
        self.local_endpoints = {
            e["node_id"]: e
            for e in self.cfg.get("local_endpoints", [])
        }

        # Mapeo local: endpoint final -> router gateway
        # Ejemplo: {"servidor1": "C"}
        self.endpoint_routes = self.cfg.get("endpoint_routes", {})

        self.seq = 0

        # origin -> {"seq": ..., "links": {vecino: costo}}
        self.lsdb = {}

        # destino_router -> {"next_hop", "ip", "port", "cost"}
        self.routing_table = {}

        self.alive = {nid: True for nid in self.neighbors}
        self.last_ack = {nid: time.time() for nid in self.neighbors}

        self.lock = threading.Lock()

    def start(self):
        # Servidor que recibe conexiones
        threading.Thread(
            target=self._listen_server,
            daemon=True
        ).start()

        time.sleep(0.5)

        # HELLO y monitoreo de vecinos corren en paralelo
        threading.Thread(
            target=self._hello_loop,
            daemon=True
        ).start()

        threading.Thread(
            target=self._liveness_monitor,
            daemon=True
        ).start()

        self._build_and_flood_own_lsa()

        print(
            f"[{self.node_id}] Nodo iniciado ({self.role}) en "
            f"{self.listen_ip}:{self.listen_port}"
        )

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"[{self.node_id}] Cerrando nodo.")

    def _listen_server(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.listen_ip, self.listen_port))
        srv.listen(50)

        while True:
            conn, _ = srv.accept()
            threading.Thread(
                target=self._handle_conn,
                args=(conn,),
                daemon=True
            ).start()

    def _handle_conn(self, conn):
        try:
            line = recv_line(conn)

            if line is None:
                return

            self._handle_line(line)

        except Exception as e:
            print(f"[{self.node_id}] Error manejando conexión: {e}")

        finally:
            conn.close()

    def _handle_line(self, line):
        # Los mensajes de control y MESSAGE vienen como JSON.
        # Los bits Hamming no son JSON.
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            obj = None

        if isinstance(obj, dict) and "type" in obj:
            msg_type = obj["type"]

            if msg_type == "HELLO":
                self._on_hello(obj)

            elif msg_type == "HELLO_ACK":
                self._on_hello_ack(obj)

            elif msg_type == "LSA":
                self._process_lsa(obj)

            elif msg_type == "MESSAGE":
                self._process_message(obj)

            else:
                print(
                    f"[{self.node_id}] "
                    f"Tipo de mensaje desconocido: {msg_type}"
                )
        else:
            # Si no es JSON, asumimos que viene de otro router con Hamming
            self._process_hamming_bits(line)

    def _hello_loop(self):
        while True:
            for nid, info in list(self.neighbors.items()):
                hello = {
                    "type": "HELLO",
                    "from": self.node_id
                }

                try:
                    send_json_to(
                        info["ip"],
                        info["port"],
                        hello
                    )
                except Exception:
                    pass

            time.sleep(HELLO_INTERVAL)

    def _on_hello(self, msg):
        sender = msg["from"]
        info = self.neighbors.get(sender)

        if not info:
            return

        ack = {
            "type": "HELLO_ACK",
            "from": self.node_id,
            "to": sender
        }

        try:
            send_json_to(
                info["ip"],
                info["port"],
                ack
            )
        except Exception:
            pass

    def _on_hello_ack(self, msg):
        sender = msg["from"]

        with self.lock:
            self.last_ack[sender] = time.time()
            was_dead = not self.alive.get(sender, True)
            self.alive[sender] = True

        if was_dead:
            print(
                f"[{self.node_id}] "
                f"Enlace con {sender} recuperado."
            )

            self._build_and_flood_own_lsa()

    def _liveness_monitor(self):
        while True:
            time.sleep(MONITOR_INTERVAL)
            changed = False

            with self.lock:
                now = time.time()

                for nid in self.neighbors:
                    last_ack = self.last_ack.get(nid, now)

                    if (
                        self.alive.get(nid, True)
                        and now - last_ack > HELLO_TIMEOUT
                    ):
                        self.alive[nid] = False
                        changed = True

                        print(
                            f"[{self.node_id}] "
                            f"Enlace con {nid} marcado como CAIDO "
                            f"(sin HELLO_ACK en {HELLO_TIMEOUT}s)."
                        )

            if changed:
                self._build_and_flood_own_lsa()

    def _build_and_flood_own_lsa(self):
        with self.lock:
            self.seq += 1

            links = [
                {
                    "to": nid,
                    "cost": info["cost"]
                }
                for nid, info in self.neighbors.items()
                if self.alive.get(nid, True)
            ]

            # Formato LSA acordado en el protocolo
            lsa = {
                "type": "LSA",
                "origin": self.node_id,
                "seq": self.seq,
                "links": links,
                "from": self.node_id
            }

            self.lsdb[self.node_id] = {
                "seq": self.seq,
                "links": {
                    link["to"]: link["cost"]
                    for link in links
                }
            }

        self._flood(lsa, exclude=None)
        self._recompute_routes()

    def _process_lsa(self, msg):
        origin = msg["origin"]

        # Descartar nuestro propio LSA si regresa por flooding
        if origin == self.node_id:
            return

        seq = msg["seq"]

        with self.lock:
            known = self.lsdb.get(origin)

            # Si ya tenemos esta versión o una más nueva, se descarta
            if known and known["seq"] >= seq:
                return

            self.lsdb[origin] = {
                "seq": seq,
                "links": {
                    link["to"]: link["cost"]
                    for link in msg["links"]
                }
            }

        self._flood(msg, exclude=msg.get("from"))
        self._recompute_routes()

    def _flood(self, lsa, exclude):
        for nid, info in self.neighbors.items():

            if nid == exclude:
                continue

            if not self.alive.get(nid, True):
                continue

            forwarded = dict(lsa)
            forwarded["from"] = self.node_id

            try:
                send_json_to(
                    info["ip"],
                    info["port"],
                    forwarded
                )

            except Exception as e:
                print(
                    f"[{self.node_id}] "
                    f"No se pudo floodear LSA a {nid}: {e}"
                )

    def _recompute_routes(self):
        with self.lock:
            graph = {
                origin: dict(data["links"])
                for origin, data in self.lsdb.items()
            }

        # Dijkstra desde este router
        dist = {self.node_id: 0}
        prev = {}
        pq = [(0, self.node_id)]
        visited = set()

        while pq:
            current_dist, current = heapq.heappop(pq)

            if current in visited:
                continue

            visited.add(current)

            for neighbor, cost in graph.get(current, {}).items():
                new_dist = current_dist + cost

                if new_dist < dist.get(neighbor, float("inf")):
                    dist[neighbor] = new_dist
                    prev[neighbor] = current

                    heapq.heappush(
                        pq,
                        (new_dist, neighbor)
                    )

        new_table = {}

        for destination in dist:
            if destination == self.node_id:
                continue

            # Retroceder hasta encontrar el vecino directo
            next_hop = destination

            while prev.get(next_hop) != self.node_id:
                next_hop = prev.get(next_hop)

                if next_hop is None:
                    break

            if next_hop is None:
                continue

            info = self.neighbors.get(next_hop)

            if not info:
                continue

            new_table[destination] = {
                "next_hop": next_hop,
                "ip": info["ip"],
                "port": info["port"],
                "cost": dist[destination]
            }

        with self.lock:
            self.routing_table = new_table

        self._write_routing_table_csv()

    def _write_routing_table_csv(self):
        filename = f"{self.node_id}_tabla_enrutamiento.csv"

        with open(
            filename,
            "w",
            newline="",
            encoding="utf-8"
        ) as f:
            writer = csv.writer(f)

            writer.writerow([
                "destino",
                "siguiente_salto",
                "ip",
                "puerto",
                "costo"
            ])

            for destination, info in sorted(
                self.routing_table.items()
            ):
                writer.writerow([
                    destination,
                    info["next_hop"],
                    info["ip"],
                    info["port"],
                    info["cost"]
                ])

    def _process_hamming_bits(self, bitstring):
        try:
            text, errors = decode_message(bitstring)

        except Exception as e:
            print(
                f"[{self.node_id}] "
                f"No se pudo decodificar Hamming: {e}"
            )
            return

        if errors:
            print(
                f"[{self.node_id}] "
                f"Hamming corrigio {errors} error(es) de bit"
            )

        try:
            msg = json.loads(text)

        except json.JSONDecodeError:
            print(
                f"[{self.node_id}] "
                f"Payload decodificado no es JSON valido: {text}"
            )
            return

        self._process_message(msg)

    def _process_message(self, msg):
        to = msg.get("to")
        msg["hops"] = msg.get("hops", 0) + 1

        print(
            f"[{self.node_id}] "
            f"MESSAGE from={msg.get('from')} "
            f"to={to} "
            f"hops={msg['hops']} "
            f"payload={msg.get('payload')!r}"
        )

        # Primero revisar si el destino está conectado directamente aquí
        local_endpoint = self.local_endpoints.get(to)

        if local_endpoint:
            try:
                # Último tramo: JSON plano, sin Hamming
                send_line_to(
                    local_endpoint["ip"],
                    local_endpoint["port"],
                    json.dumps(msg)
                )

            except Exception as e:
                print(
                    f"[{self.node_id}] "
                    f"Error entregando a endpoint local {to}: {e}"
                )

            return

        # Buscar qué router es gateway del destino final
        destination_router = self.endpoint_routes.get(to)

        if destination_router is None:
            print(
                f"[{self.node_id}] "
                f"No conozco el gateway de {to}, "
                f"descartando mensaje."
            )
            return

        # Buscar la ruta hacia ese router
        with self.lock:
            route = self.routing_table.get(destination_router)

        if not route:
            print(
                f"[{self.node_id}] "
                f"Sin ruta hacia {destination_router} "
                f"(gateway de {to}), descartando mensaje."
            )
            return

        # Entre routers se utiliza Hamming(7,4)
        bits = encode_message(json.dumps(msg))

        try:
            send_line_to(
                route["ip"],
                route["port"],
                bits
            )

        except Exception as e:
            print(
                f"[{self.node_id}] "
                f"Error reenviando a {route['next_hop']}: {e}"
            )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python node.py <config.json>")
        sys.exit(1)

    Node(sys.argv[1]).start()