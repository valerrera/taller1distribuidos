import socket
import json
import time

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================

# El coordinador escucha aquí
COORDINATOR_HOST = "0.0.0.0"
COORDINATOR_PORT = 5000

# Timeout para esperar respuesta de un worker
TIMEOUT = 3.0

# Para evitar problemas con floats
EPS = 1e-12

# IPs de los workers (cada uno en su VM)
OP_SERVERS = {
    "op1": ("10.43.99.136", 5001),
    "op2": ("10.43.99.139", 5001),
    "op3": ("10.43.97.155", 5001),
}

# Plan de roles (quién intenta primero y quién sustituye)
ROLE_PLAN = {
    "sqrt_discriminant": ["op1", "op2", "op3"],
    "numerator": ["op2", "op3", "op1"],
    "division": ["op3", "op1", "op2"],
}

ALL_OPS = ["op1", "op2", "op3"]

# =====================================================
# FUNCIONES AUXILIARES SOCKET + JSON
# =====================================================

# Enviamos JSON terminando en \n para saber cuándo termina el mensaje
def send_json(conn, data):
    msg = json.dumps(data) + "\n"
    conn.sendall(msg.encode("utf-8"))


# Leemos hasta encontrar el salto de línea
def recv_json(conn):
    buffer = b""
    while b"\n" not in buffer:
        chunk = conn.recv(4096)
        if not chunk:
            return None
        buffer += chunk

    line = buffer.split(b"\n", 1)[0]
    return json.loads(line.decode("utf-8"))


# =====================================================
# LLAMAR A UN WORKER
# =====================================================

def call_worker(op_name, payload):

    host, port = OP_SERVERS[op_name]

    # Abrimos conexión TCP hacia el worker
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

        s.settimeout(TIMEOUT)
        s.connect((host, port))

        send_json(s, payload)

        response = recv_json(s)

        if response is None:
            raise RuntimeError("Worker cerró conexión sin responder")

        return response


# =====================================================
# LÓGICA PARA FALLBACK
# =====================================================

# Si solo queda un worker vivo, ese hace todo (full_quadratic)
def try_full_quadratic(a, b, c, request_id, dead_ops):

    alive = [op for op in ALL_OPS if op not in dead_ops]

    # Solo aplica si queda uno vivo
    if len(alive) != 1:
        return None

    op_name = alive[0]

    try:
        print(f"[INFO] Solo queda {op_name}, usando full_quadratic")

        resp = call_worker(op_name, {
            "request_id": request_id,
            "op": "full_quadratic",
            "a": a,
            "b": b,
            "c": c
        })

        return resp

    except Exception:
        dead_ops.add(op_name)
        return {"ok": False, "error": "Perdona la demora, intenta más tarde"}


# Ejecuta una etapa intentando principal y luego sustitutos
def run_stage(stage_key, payload, request_id, dead_ops):

    # Primero verificamos si ya solo queda uno vivo
    fq = try_full_quadratic(
        payload.get("a"),
        payload.get("b"),
        payload.get("c"),
        request_id,
        dead_ops
    )

    if fq is not None:
        return fq, "full_quadratic"

    # Intentamos principal y sustitutos
    for op_name in ROLE_PLAN[stage_key]:

        if op_name in dead_ops:
            continue

        try:
            print(f"[TRY] {stage_key} -> {op_name}")

            resp = call_worker(op_name, dict(payload, request_id=request_id))

            # Si el worker responde ok, listo
            if resp.get("ok"):
                return resp, op_name

            # Si el error es matemático (no de red), devolvemos de una
            return resp, op_name

        except Exception as e:

            print(f"[FAIL] {op_name} no respondió ({e})")
            dead_ops.add(op_name)

    # Si nadie respondió
    return {"ok": False, "error": "Perdona la demora, intenta más tarde"}, None


# =====================================================
# PIPELINE PRINCIPAL
# =====================================================

def process(a, b, c, request_id):

    dead_ops = set()

    # Validaciones centrales (para no mandar basura a workers)
    if abs(a) < EPS:
        return {"ok": False, "error": "Valor inválido: a no puede ser 0"}

    disc = b*b - 4*a*c

    if disc < 0:
        return {"ok": False, "error": "No hay raíces reales"}

    # ---- ETAPA 1: sqrt_discriminant ----
    r1, who1 = run_stage(
        "sqrt_discriminant",
        {"op": "sqrt_discriminant", "a": a, "b": b, "c": c},
        request_id,
        dead_ops
    )

    if not r1.get("ok"):
        return r1

    if who1 == "full_quadratic":
        return {"ok": True, "mode": "single_node", "x1": r1["x1"], "x2": r1["x2"]}

    sqrt_d = r1["sqrt_d"]

    # ---- ETAPA 2: numerator ----
    r2, who2 = run_stage(
        "numerator",
        {"op": "numerator", "b": b, "sqrt_d": sqrt_d},
        request_id,
        dead_ops
    )

    if not r2.get("ok"):
        return r2

    if who2 == "full_quadratic":
        return {"ok": True, "mode": "single_node", "x1": r2["x1"], "x2": r2["x2"]}

    # ---- ETAPA 3: division ----
    r3, who3 = run_stage(
        "division",
        {
            "op": "division",
            "a": a,
            "num_plus": r2["num_plus"],
            "num_minus": r2["num_minus"]
        },
        request_id,
        dead_ops
    )

    if not r3.get("ok"):
        return r3

    if who3 == "full_quadratic":
        return {"ok": True, "mode": "single_node", "x1": r3["x1"], "x2": r3["x2"]}

    # Resultado normal pipeline
    return {
        "ok": True,
        "mode": "pipeline",
        "x1": r3["x1"],
        "x2": r3["x2"],
        "trace": {
            "sqrt": who1,
            "numerator": who2,
            "division": who3
        },
        "dead_ops": list(dead_ops)
    }


# =====================================================
# MANEJO CLIENTE
# =====================================================

def handle_client(conn, addr):

    payload = recv_json(conn)

    if not payload:
        return

    request_id = payload.get("request_id", f"req-{int(time.time())}")

    try:
        a = float(payload.get("a"))
        b = float(payload.get("b"))
        c = float(payload.get("c"))
    except Exception:
        send_json(conn, {"ok": False, "error": "a,b,c deben ser numéricos"})
        return

    result = process(a, b, c, request_id)

    send_json(conn, result)


# =====================================================
# MAIN LOOP
# =====================================================

def main():

    print(f"[START] Coordinador en {COORDINATOR_HOST}:{COORDINATOR_PORT}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:

        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        server.bind((COORDINATOR_HOST, COORDINATOR_PORT))
        server.listen(5)

        while True:

            conn, addr = server.accept()

            # Solo un cliente a la vez (simplificado)
            handle_client(conn, addr)
            conn.close()


if __name__ == "__main__":
    main()