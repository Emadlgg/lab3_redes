"""
atm_server.py — Servidor bancario ATM (role: "server"). No participa del
Link State.

Igual que server.py, escucha en su propio listen_ip:listen_port a la
espera de que su router gateway le entregue mensajes ya decodificados
(JSON plano, sin Hamming, como corresponde al último tramo router-gateway
<-> endpoint). A diferencia de server.py, sí responde: procesa la
operación (LOGIN, BALANCE, WITHDRAW, DEPOSIT, LOGOUT) y envía la
respuesta de vuelta a través de la red de routers usando el mismo
mecanismo que usa un cliente para enviar (send_line_to a su gateway),
solo que en sentido inverso.

Las cuentas se cargan desde el propio config ("accounts": [...]).

Uso:
    python atm_server.py config_bank1.json
"""

import sys
import json
import socket
import threading
import uuid

from common import recv_line, send_line_to


class ATMServer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.node_id = cfg["node_id"]
        self.listen_ip = cfg["listen_ip"]
        self.listen_port = cfg["listen_port"]
        self.gateway = cfg["neighbors"][0]  # {"node_id": "C", "ip":..., "port":...}

        self.accounts = {
            a["card"]: {"pin": a["pin"], "balance": float(a["balance"])}
            for a in cfg.get("accounts", [])
        }
        self.sessions = {}  # token -> card

        self.lock = threading.Lock()

    def _reply(self, to, payload):
        msg = {
            "type": "MESSAGE",
            "from": self.node_id,
            "to": to,
            "hops": 0,
            "payload": json.dumps(payload),
        }
        try:
            send_line_to(self.gateway["ip"], self.gateway["port"], json.dumps(msg))
        except Exception as e:
            print(f"[{self.node_id}] Error respondiendo a {to}: {e}")

    def _handle_conn(self, conn):
        try:
            line = recv_line(conn)
            if line is None:
                return
            envelope = json.loads(line)
            frm = envelope.get("from")
            req = json.loads(envelope.get("payload", "{}"))
        except Exception as e:
            print(f"[{self.node_id}] Mensaje entrante inválido: {e}")
            return
        finally:
            conn.close()

        resp = self._process(req)
        resp["request_id"] = req.get("request_id")
        self._reply(frm, resp)

    def _process(self, req):
        op = req.get("op")

        if op == "LOGIN":
            return self._login(req.get("card"), req.get("pin"))

        # Todo lo demás requiere sesión válida (token de un LOGIN previo)
        card = self._authorize(req.get("token"))
        if card is None:
            return {"status": "ERROR", "message": "Sesión inválida o expirada"}

        if op == "BALANCE":
            with self.lock:
                bal = self.accounts[card]["balance"]
            return {"status": "OK", "balance": bal}

        if op == "WITHDRAW":
            return self._withdraw(card, req.get("amount"))

        if op == "DEPOSIT":
            return self._deposit(card, req.get("amount"))

        if op == "LOGOUT":
            with self.lock:
                self.sessions = {
                    t: c for t, c in self.sessions.items() if c != card
                }
            return {"status": "OK"}

        return {"status": "ERROR", "message": f"Operación desconocida: {op}"}

    def _authorize(self, token):
        if not token:
            return None
        with self.lock:
            return self.sessions.get(token)

    def _login(self, card, pin):
        account = self.accounts.get(card)
        if account is None or account["pin"] != pin:
            print(f"[{self.node_id}] Login fallido para tarjeta {card}")
            return {"status": "FAIL", "message": "Tarjeta o PIN incorrecto"}

        token = uuid.uuid4().hex
        with self.lock:
            self.sessions[token] = card

        print(f"[{self.node_id}] Login OK: {card}")
        return {"status": "OK", "token": token, "balance": account["balance"]}

    def _withdraw(self, card, amount):
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return {"status": "FAIL", "message": "Monto inválido"}
        if amount <= 0:
            return {"status": "FAIL", "message": "Monto debe ser positivo"}

        with self.lock:
            account = self.accounts[card]
            if amount > account["balance"]:
                return {
                    "status": "FAIL",
                    "message": "Fondos insuficientes",
                    "balance": account["balance"],
                }
            account["balance"] -= amount
            bal = account["balance"]

        print(f"[{self.node_id}] Retiro de Q{amount:.2f} en {card}. "
              f"Nuevo saldo: Q{bal:.2f}")
        return {"status": "OK", "balance": bal}

    def _deposit(self, card, amount):
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return {"status": "FAIL", "message": "Monto inválido"}
        if amount <= 0:
            return {"status": "FAIL", "message": "Monto debe ser positivo"}

        with self.lock:
            account = self.accounts[card]
            account["balance"] += amount
            bal = account["balance"]

        print(f"[{self.node_id}] Depósito de Q{amount:.2f} en {card}. "
              f"Nuevo saldo: Q{bal:.2f}")
        return {"status": "OK", "balance": bal}

    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.listen_ip, self.listen_port))
        srv.listen(20)

        print(f"[{self.node_id}] Banco escuchando en "
              f"{self.listen_ip}:{self.listen_port}. "
              f"Cuentas cargadas: {len(self.accounts)}")
        try:
            while True:
                conn, _ = srv.accept()
                threading.Thread(
                    target=self._handle_conn, args=(conn,), daemon=True
                ).start()
        except KeyboardInterrupt:
            print(f"\n[{self.node_id}] Cerrando banco.")


def main():
    if len(sys.argv) != 2:
        print("Uso: python atm_server.py <config_bank.json>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        cfg = json.load(f)

    ATMServer(cfg).start()


if __name__ == "__main__":
    main()
