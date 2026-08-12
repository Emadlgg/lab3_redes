"""
server.py — Nodo servidor (role: "server"). No participa del Link State.
Escucha en su propio listen_ip:listen_port a la espera de que su router
gateway le entregue mensajes ya decodificados (JSON plano, sin Hamming,
como corresponde al último tramo router-gateway <-> endpoint).

Uso:
    python server.py config_servidor1.json
"""

import sys
import json
import socket
import threading

from common import recv_line


def handle_conn(conn, my_id):
    try:
        line = recv_line(conn)
        if line is None:
            return
        msg = json.loads(line)
        print(f"[{my_id}] Mensaje de {msg.get('from')} "
              f"(hops={msg.get('hops')}): {msg.get('payload')}")
    except Exception as e:
        print(f"[{my_id}] Error procesando mensaje entrante: {e}")
    finally:
        conn.close()


def main():
    if len(sys.argv) != 2:
        print("Uso: python server.py <config_servidor.json>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        cfg = json.load(f)

    my_id = cfg["node_id"]
    listen_ip = cfg["listen_ip"]
    listen_port = cfg["listen_port"]

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((listen_ip, listen_port))
    srv.listen(20)

    print(f"[{my_id}] Escuchando en {listen_ip}:{listen_port}. Esperando mensajes...")
    try:
        while True:
            conn, _ = srv.accept()
            threading.Thread(target=handle_conn, args=(conn, my_id), daemon=True).start()
    except KeyboardInterrupt:
        print(f"\n[{my_id}] Cerrando servidor.")


if __name__ == "__main__":
    main()