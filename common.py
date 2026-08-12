"""common.py — utilidades de envío/recepción sobre sockets (delimitado por '\\n', UTF-8)."""

import json
import socket


def send_line(sock, text):
    sock.sendall((text + "\n").encode("utf-8"))


def recv_line(sock):
    buf = b""
    while True:
        chunk = sock.recv(1)
        if not chunk:
            return buf.decode("utf-8") if buf else None
        if chunk == b"\n":
            return buf.decode("utf-8")
        buf += chunk


def send_json(sock, obj):
    send_line(sock, json.dumps(obj))


def recv_json(sock):
    line = recv_line(sock)
    if line is None:
        return None
    return json.loads(line)


def send_line_to(ip, port, text, timeout=2.0):
    """Abre una conexión corta, envía una línea, cierra. Usado para
    HELLO/HELLO_ACK/LSA/MESSAGE, que viajan cada uno en su propia conexión."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        send_line(s, text)
    finally:
        s.close()


def send_json_to(ip, port, obj, timeout=2.0):
    send_line_to(ip, port, json.dumps(obj), timeout=timeout)