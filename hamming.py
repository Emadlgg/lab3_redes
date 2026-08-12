"""
hamming.py
Codificación y decodificación Hamming (7,4) con corrección de 1 bit (SEC).

Orden de bits acordado con las otras 2 parejas (doc "Definición de protocolo"):
bits de paridad en las posiciones 1, 2 y 4 (estilo estándar):

    posicion:  1  2  3  4  5  6  7
    bit:       p1 p2 d1 p3 d2 d3 d4
"""


def _parity(*bits):
    r = 0
    for b in bits:
        r ^= b
    return r


def encode_nibble(d):
    """d: 4 bits de datos (0/1) -> lista de 7 bits codificados."""
    d1, d2, d3, d4 = d
    p1 = _parity(d1, d2, d4)
    p2 = _parity(d1, d3, d4)
    p3 = _parity(d2, d3, d4)
    return [p1, p2, d1, p3, d2, d3, d4]


def decode_nibble(r):
    """r: 7 bits recibidos -> (4 bits de datos corregidos, hubo_error: bool)."""
    r = list(r)
    p1, p2, d1, p3, d2, d3, d4 = r
    c1 = _parity(p1, d1, d2, d4)
    c2 = _parity(p2, d1, d3, d4)
    c3 = _parity(p3, d2, d3, d4)
    syndrome = c1 + (c2 << 1) + (c3 << 2)
    hubo_error = syndrome != 0
    if hubo_error:
        pos = syndrome - 1  # posición 1-indexada del bit erróneo -> 0-indexada
        r[pos] ^= 1
        p1, p2, d1, p3, d2, d3, d4 = r
    return [d1, d2, d3, d4], hubo_error


def bits_to_str(bits):
    return "".join(str(b) for b in bits)


def str_to_bits(s):
    return [int(c) for c in s]


def text_to_bits(text):
    data = text.encode("utf-8")
    bits = []
    for byte in data:
        bits.extend(int(b) for b in format(byte, "08b"))
    return bits


def bits_to_text(bits):
    b = bytearray()
    for i in range(0, len(bits), 8):
        byte_bits = bits[i:i + 8]
        if len(byte_bits) < 8:
            break
        b.append(int("".join(str(x) for x in byte_bits), 2))
    return b.decode("utf-8")


def encode_message(text):
    """Texto (JSON) -> cadena de bits Hamming(7,4). UTF-8 siempre produce
    bytes (múltiplos de 8 bits) => múltiplos de 4, no se requiere padding."""
    data_bits = text_to_bits(text)
    encoded = []
    for i in range(0, len(data_bits), 4):
        encoded.extend(encode_nibble(data_bits[i:i + 4]))
    return bits_to_str(encoded)


def decode_message(bitstring):
    """Cadena de bits Hamming(7,4) -> (texto original, total_errores_corregidos)."""
    bits = str_to_bits(bitstring)
    data_bits = []
    errores = 0
    for i in range(0, len(bits), 7):
        codeword = bits[i:i + 7]
        if len(codeword) < 7:
            break
        nibble, hubo_error = decode_nibble(codeword)
        if hubo_error:
            errores += 1
        data_bits.extend(nibble)
    return bits_to_text(data_bits), errores