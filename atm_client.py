"""
atm_client.py — Cliente ATM (role: "client"). No participa del Link State.

Igual que client.py, solo conoce a su router gateway (único elemento de
"neighbors" en su config) y le envía las operaciones en JSON plano — el
Hamming(7,4) solo se aplica en los saltos router-router.

A diferencia de client.py, el ATM sí necesita respuesta (login, saldo,
retiro, depósito), así que además levanta un listener en su propio
listen_ip:listen_port para recibir la contestación del banco, que llega
por el mismo mecanismo que un MESSAGE normal (el router se la entrega
como local_endpoint).

Uso:
    python atm_client.py config_atm1.json
"""

import sys
import json
import socket
import threading
import time
import uuid

from common import send_line_to, recv_line


class ATMClient:
    def __init__(self, cfg):
        self.cfg = cfg
        self.node_id = cfg["node_id"]
        self.listen_ip = cfg["listen_ip"]
        self.listen_port = cfg["listen_port"]
        self.gateway = cfg["neighbors"][0]  # {"node_id": "A", "ip":..., "port":...}
        self.banco = cfg["banco"]           # node_id del servidor bancario, ej. "bank1"

        self.token = None
        self.card = None

        self._pending = {}    # request_id -> threading.Event
        self._responses = {}  # request_id -> payload dict
        self._lock = threading.Lock()

    # ---------- Red ----------

    def _listen_loop(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.listen_ip, self.listen_port))
        srv.listen(20)
        while True:
            conn, _ = srv.accept()
            threading.Thread(target=self._handle_conn, args=(conn,), daemon=True).start()

    def _handle_conn(self, conn):
        try:
            line = recv_line(conn)
            if line is None:
                return
            envelope = json.loads(line)
            payload = json.loads(envelope.get("payload", "{}"))
            req_id = payload.get("request_id")
            with self._lock:
                if req_id in self._pending:
                    self._responses[req_id] = payload
                    self._pending[req_id].set()
                else:
                    print(f"\n[{self.node_id}] Mensaje inesperado de "
                          f"{envelope.get('from')}: {payload}")
        except Exception as e:
            print(f"[{self.node_id}] Error procesando respuesta: {e}")
        finally:
            conn.close()

    def _request(self, op, extra=None, timeout=5.0):
        req_id = uuid.uuid4().hex
        payload = {"op": op, "request_id": req_id}
        if self.token:
            payload["token"] = self.token
        if extra:
            payload.update(extra)

        msg = {
            "type": "MESSAGE",
            "from": self.node_id,
            "to": self.banco,
            "hops": 0,
            "payload": json.dumps(payload),
        }

        ev = threading.Event()
        with self._lock:
            self._pending[req_id] = ev

        try:
            send_line_to(self.gateway["ip"], self.gateway["port"], json.dumps(msg))
        except Exception as e:
            print(f"[{self.node_id}] Error enviando al gateway: {e}")
            with self._lock:
                self._pending.pop(req_id, None)
            return None

        got = ev.wait(timeout)
        with self._lock:
            self._pending.pop(req_id, None)
            resp = self._responses.pop(req_id, None)

        if not got or resp is None:
            print(f"[{self.node_id}] Sin respuesta de {self.banco} "
                  f"(timeout). ¿Hay ruta hacia el banco?")
            return None
        return resp

    # ---------- Operaciones ----------

    def login(self):
        card = input("Tarjeta: ").strip()
        pin = input("PIN: ").strip()
        resp = self._request("LOGIN", {"card": card, "pin": pin})
        if resp is None:
            return
        if resp.get("status") == "OK":
            self.token = resp["token"]
            self.card = card
            print(f"[{self.node_id}] Login exitoso. Saldo: Q{resp['balance']:.2f}")
        else:
            print(f"[{self.node_id}] Login fallido: {resp.get('message')}")

    def balance(self):
        if not self._require_session():
            return
        resp = self._request("BALANCE")
        if resp is None:
            return
        if resp.get("status") == "OK":
            print(f"[{self.node_id}] Saldo actual: Q{resp['balance']:.2f}")
        else:
            print(f"[{self.node_id}] Error: {resp.get('message')}")

    def withdraw(self):
        if not self._require_session():
            return
        try:
            amount = float(input("Monto a retirar: "))
        except ValueError:
            print("Monto inválido.")
            return
        resp = self._request("WITHDRAW", {"amount": amount})
        if resp is None:
            return
        if resp.get("status") == "OK":
            print(f"[{self.node_id}] Retiro exitoso. Nuevo saldo: Q{resp['balance']:.2f}")
        else:
            print(f"[{self.node_id}] Retiro rechazado: {resp.get('message')}")

    def deposit(self):
        if not self._require_session():
            return
        try:
            amount = float(input("Monto a depositar: "))
        except ValueError:
            print("Monto inválido.")
            return
        resp = self._request("DEPOSIT", {"amount": amount})
        if resp is None:
            return
        if resp.get("status") == "OK":
            print(f"[{self.node_id}] Depósito exitoso. Nuevo saldo: Q{resp['balance']:.2f}")
        else:
            print(f"[{self.node_id}] Depósito rechazado: {resp.get('message')}")

    def logout(self):
        if self.token:
            self._request("LOGOUT")
        self.token = None
        self.card = None
        print(f"[{self.node_id}] Sesión cerrada.")

    def _require_session(self):
        if not self.token:
            print(f"[{self.node_id}] Primero debes iniciar sesión (opción 1).")
            return False
        return True

    # ---------- Loop principal ----------

    def start(self):
        threading.Thread(target=self._listen_loop, daemon=True).start()
        time.sleep(0.3)  # da tiempo a que el listener levante antes de aceptar input

        print(f"[{self.node_id}] Cajero ATM listo. "
              f"Gateway: {self.gateway['node_id']} "
              f"({self.gateway['ip']}:{self.gateway['port']}). "
              f"Banco destino: {self.banco}")

        menu = (
            "\n1) Iniciar sesión\n"
            "2) Consultar saldo\n"
            "3) Retirar\n"
            "4) Depositar\n"
            "5) Cerrar sesión\n"
            "0) Salir\n"
        )
        try:
            while True:
                print(menu)
                opt = input("> ").strip()
                if opt == "1":
                    self.login()
                elif opt == "2":
                    self.balance()
                elif opt == "3":
                    self.withdraw()
                elif opt == "4":
                    self.deposit()
                elif opt == "5":
                    self.logout()
                elif opt == "0":
                    break
                else:
                    print("Opción inválida.")
        except KeyboardInterrupt:
            pass
        finally:
            print(f"\n[{self.node_id}] Cerrando cajero.")


def main():
    if len(sys.argv) != 2:
        print("Uso: python atm_client.py <config_atm.json>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        cfg = json.load(f)

    ATMClient(cfg).start()


if __name__ == "__main__":
    main()
