"""
client.py — Nodo cliente (role: "client"). No participa del Link State.
Solo conoce a su router gateway (definido como su único elemento en
"neighbors" dentro de su propio config.json) y le envía mensajes en JSON
plano — el Hamming(7,4) solo se aplica en los saltos router-router.

Uso:
    python client.py config_cliente1.json
"""

import sys
import json
import time

from common import send_line_to


def main():
    if len(sys.argv) != 2:
        print("Uso: python client.py <config_cliente.json>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        cfg = json.load(f)

    my_id = cfg["node_id"]
    gateway = cfg["neighbors"][0]         # {"node_id": "A", "ip":..., "port":...}
    destino = cfg["to"]                    # node_id del servidor destino

    print(f"[{my_id}] Gateway: {gateway['node_id']} ({gateway['ip']}:{gateway['port']})")
    print(f"[{my_id}] Destino configurado: {destino}")
    print(f"[{my_id}] Escribe un mensaje y Enter para enviarlo (Ctrl+C para salir).")

    try:
        while True:
            texto = input("> ")
            msg = {
                "type": "MESSAGE",
                "from": my_id,
                "to": destino,
                "hops": 0,
                "payload": texto,
            }
            send_line_to(gateway["ip"], gateway["port"], json.dumps(msg))
    except KeyboardInterrupt:
        print(f"\n[{my_id}] Cerrando cliente.")


if __name__ == "__main__":
    main()