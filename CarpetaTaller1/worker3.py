import socket
import json
import math

# ==========================================
# CONFIGURACIÓN DEL WORKER
# ==========================================

WORKER_NAME = "op3"   # Este es el worker 1
HOST = "0.0.0.0"
PORT = 5001

EPS = 1e-12

# ==========================================
# FUNCIONES AUXILIARES JSON + SOCKET
# ==========================================

def send_json(conn, data):
    msg = json.dumps(data) + "\n"
    conn.sendall(msg.encode("utf-8"))


def recv_json(conn):
    buffer = b""
    while b"\n" not in buffer:
        chunk = conn.recv(4096)
        if not chunk:
            return None
        buffer += chunk

    line = buffer.split(b"\n", 1)[0]
    return json.loads(line.decode("utf-8"))

# ==========================================
# LÓGICA DE OPERACIONES
# ==========================================

def handle_operation(payload):

    op = payload.get("op")

    # ---- RAÍZ DEL DISCRIMINANTE ----
    if op == "sqrt_discriminant":
        a = payload.get("a")
        b = payload.get("b")
        c = payload.get("c")

        if a is None or b is None or c is None:
            return {"ok": False, "error": "Faltan parámetros"}

        if abs(a) < EPS:
            return {"ok": False, "error": "a no puede ser 0"}

        disc = b*b - 4*a*c

        if disc < 0:
            return {"ok": False, "error": "No hay raíces reales"}

        return {"ok": True, "sqrt_d": math.sqrt(disc), "disc": disc}

    # ---- NUMERADOR (+ y -) ----
    if op == "numerator":
        b = payload.get("b")
        sqrt_d = payload.get("sqrt_d")

        if b is None or sqrt_d is None:
            return {"ok": False, "error": "Faltan parámetros"}

        return {
            "ok": True,
            "num_plus": (-b) + sqrt_d,
            "num_minus": (-b) - sqrt_d
        }

    # ---- DIVISIÓN FINAL ----
    if op == "division":
        a = payload.get("a")
        num_plus = payload.get("num_plus")
        num_minus = payload.get("num_minus")

        if a is None or num_plus is None or num_minus is None:
            return {"ok": False, "error": "Faltan parámetros"}

        den = 2*a

        if abs(den) < EPS:
            return {"ok": False, "error": "División por cero"}

        return {
            "ok": True,
            "x1": num_plus/den,
            "x2": num_minus/den
        }

    # ---- MODO FULL (cuando quedan 2 caídos) ----
    if op == "full_quadratic":

        a = payload.get("a")
        b = payload.get("b")
        c = payload.get("c")

        if a is None or b is None or c is None:
            return {"ok": False, "error": "Faltan parámetros"}

        if abs(a) < EPS:
            return {"ok": False, "error": "a no puede ser 0"}

        disc = b*b - 4*a*c

        if disc < 0:
            return {"ok": False, "error": "No hay raíces reales"}

        sqrt_d = math.sqrt(disc)
        num_plus = (-b) + sqrt_d
        num_minus = (-b) - sqrt_d
        den = 2*a

        return {
            "ok": True,
            "x1": num_plus/den,
            "x2": num_minus/den
        }

    return {"ok": False, "error": "Operación no soportada"}


# ==========================================
# MANEJO DE CONEXIÓN
# ==========================================

def handle_client(conn, addr):

    payload = recv_json(conn)

    if not payload:
        return

    print(f"[{WORKER_NAME}] Recibido: {payload.get('op')}")

    result = handle_operation(payload)

    send_json(conn, result)


# ==========================================
# MAIN
# ==========================================

def main():

    print(f"[START] {WORKER_NAME} escuchando en {HOST}:{PORT}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:

        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(5)

        while True:
            conn, addr = server.accept()
            handle_client(conn, addr)
            conn.close()


if __name__ == "__main__":
    main()