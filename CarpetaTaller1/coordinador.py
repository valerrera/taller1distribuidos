import socket
import json
import time
import traceback

# =========================
# CONFIGURACIÓN DEL SISTEMA
# =========================

COORDINATOR_HOST = "0.0.0.0"
COORDINATOR_PORT = 5000

# Timeout para esperar respuesta de un servidor de operación
OP_TIMEOUT_SECONDS = 3.0

# Servidores de operación (IPs reales del equipo)
OP_SERVERS = {
    "op1": ("10.43.99.136", 5001),
    "op2": ("10.43.99.139", 5001),
    "op3": ("10.43.97.155", 5001),
}

# Orden de sustitución por operación (según su diseño)
ROLE_PLAN = {
    "sqrt_discriminant": ["op1", "op2", "op3"],
    "numerator": ["op2", "op3", "op1"],
    "division": ["op3", "op1", "op2"],
}

# Para escenario de 2 fallos (solo uno vivo)
ALL_OPS = ["op1", "op2", "op3"]


# =========================
# UTILIDADES JSON SOCKET
# =========================

def recv_json(conn):
    buffer = b""
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        buffer += chunk
        if b"\n" in buffer:
            break

    if not buffer:
        return None

    line = buffer.split(b"\n", 1)[0]
    return json.loads(line.decode("utf-8"))


def send_json(conn, data):
    msg = json.dumps(data) + "\n"
    conn.sendall(msg.encode("utf-8"))


# =========================
# CLIENTE HACIA OPERACIONES
# =========================

def call_operation_server(op_name, payload, timeout_seconds=OP_TIMEOUT_SECONDS):
    """
    Llama a un servidor de operación específico (op1/op2/op3).
    Retorna dict respuesta o lanza excepción si falla.
    """
    host, port = OP_SERVERS[op_name]

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout_seconds)
        s.connect((host, port))
        send_json(s, payload)

        response = recv_json(s)
        if response is None:
            raise RuntimeError(f"{op_name} cerró conexión sin responder")

        return response


def call_with_failover(operation_key, base_payload, request_id, dead_ops):
    """
    Ejecuta una operación lógica (sqrt_discriminant / numerator / division)
    usando el plan principal+sustitutos y evitando nodos marcados como caídos.
    """
    candidates = ROLE_PLAN[operation_key]

    last_error = None
    for op_name in candidates:
        if op_name in dead_ops:
            continue

        payload = dict(base_payload)
        payload["request_id"] = request_id

        try:
            print(f"[TRY] {operation_key} -> {op_name}")
            response = call_operation_server(op_name, payload)

            if not response.get("ok", False):
                # Error lógico/matemático reportado por el servidor
                return response, op_name, False

            print(f"[OK] {operation_key} resuelto por {op_name}")
            return response, op_name, True

        except Exception as e:
            print(f"[FAIL] {operation_key} con {op_name}: {e}")
            dead_ops.add(op_name)
            last_error = str(e)

    return {"ok": False, "error": f"No hay nodos disponibles para {operation_key}. Último error: {last_error}"}, None, False


def call_full_quadratic_on_single_alive(a, b, c, request_id, dead_ops):
    """
    Si hay 2 nodos caídos y solo queda 1 vivo, ese único nodo hace todo.
    """
    alive_ops = [op for op in ALL_OPS if op not in dead_ops]

    if len(alive_ops) != 1:
        return {"ok": False, "error": "No aplica full_quadratic: no hay exactamente 1 nodo vivo"}, None, False

    op_name = alive_ops[0]
    payload = {
        "request_id": request_id,
        "op": "full_quadratic",
        "a": a,
        "b": b,
        "c": c
    }

    try:
        print(f"[TRY] full_quadratic -> {op_name}")
        response = call_operation_server(op_name, payload)

        if not response.get("ok", False):
            return response, op_name, False

        print(f"[OK] full_quadratic resuelto por {op_name}")
        return response, op_name, True

    except Exception as e:
        print(f"[FAIL] full_quadratic con {op_name}: {e}")
        dead_ops.add(op_name)
        return {"ok": False, "error": f"Falló nodo único {op_name}: {str(e)}"}, op_name, False


# =========================
# LÓGICA DEL COORDINADOR
# =========================

def process_quadratic_request(a, b, c, request_id):
    """
    Orquesta el cálculo distribuido con failover.
    """
    dead_ops = set()

    # Validación inicial (coordinador también valida)
    if a == 0:
        return {"ok": False, "error": "Valor inválido: a no puede ser 0"}

    # ===== ETAPA 1: sqrt_discriminant =====
    resp1, op_used_1, success1 = call_with_failover(
        "sqrt_discriminant",
        {"op": "sqrt_discriminant", "a": a, "b": b, "c": c},
        request_id,
        dead_ops
    )

    if not success1:
        # Si falló por lógica (disc<0) o por falta de nodos, devolvemos
        if len(dead_ops) >= 2:
            # Intento extremo: nodo único hace todo si queda uno
            full_resp, _, full_ok = call_full_quadratic_on_single_alive(a, b, c, request_id, dead_ops)
            if full_ok:
                return {
                    "ok": True,
                    "request_id": request_id,
                    "mode": "single_node_fallback",
                    "x1": full_resp["x1"],
                    "x2": full_resp["x2"],
                    "details": full_resp
                }
            return full_resp
        return resp1

    sqrt_d = resp1["sqrt_d"]

    # Si a esta altura quedaron 2 caídos, que el único vivo haga todo
    if len(dead_ops) >= 2:
        full_resp, _, full_ok = call_full_quadratic_on_single_alive(a, b, c, request_id, dead_ops)
        if full_ok:
            return {
                "ok": True,
                "request_id": request_id,
                "mode": "single_node_fallback",
                "x1": full_resp["x1"],
                "x2": full_resp["x2"],
                "details": full_resp
            }
        return full_resp

    # ===== ETAPA 2: numerator =====
    resp2, op_used_2, success2 = call_with_failover(
        "numerator",
        {"op": "numerator", "b": b, "sqrt_d": sqrt_d},
        request_id,
        dead_ops
    )

    if not success2:
        if len(dead_ops) >= 2:
            full_resp, _, full_ok = call_full_quadratic_on_single_alive(a, b, c, request_id, dead_ops)
            if full_ok:
                return {
                    "ok": True,
                    "request_id": request_id,
                    "mode": "single_node_fallback",
                    "x1": full_resp["x1"],
                    "x2": full_resp["x2"],
                    "details": full_resp
                }
            return full_resp
        return resp2

    num_plus = resp2["num_plus"]
    num_minus = resp2["num_minus"]

    if len(dead_ops) >= 2:
        full_resp, _, full_ok = call_full_quadratic_on_single_alive(a, b, c, request_id, dead_ops)
        if full_ok:
            return {
                "ok": True,
                "request_id": request_id,
                "mode": "single_node_fallback",
                "x1": full_resp["x1"],
                "x2": full_resp["x2"],
                "details": full_resp
            }
        return full_resp

    # ===== ETAPA 3: division =====
    resp3, op_used_3, success3 = call_with_failover(
        "division",
        {"op": "division", "a": a, "num_plus": num_plus, "num_minus": num_minus},
        request_id,
        dead_ops
    )

    if not success3:
        if len(dead_ops) >= 2:
            full_resp, _, full_ok = call_full_quadratic_on_single_alive(a, b, c, request_id, dead_ops)
            if full_ok:
                return {
                    "ok": True,
                    "request_id": request_id,
                    "mode": "single_node_fallback",
                    "x1": full_resp["x1"],
                    "x2": full_resp["x2"],
                    "details": full_resp
                }
            return full_resp
        return resp3

    # Éxito normal
    return {
        "ok": True,
        "request_id": request_id,
        "mode": "pipeline",
        "x1": resp3["x1"],
        "x2": resp3["x2"],
        "trace": {
            "sqrt_discriminant": op_used_1,
            "numerator": op_used_2,
            "division": op_used_3
        },
        "dead_ops": list(dead_ops)
    }


# =========================
# ATENCIÓN A CLIENTES
# =========================

def handle_client(conn, addr):
    try:
        payload = recv_json(conn)
        if payload is None:
            return

        request_id = payload.get("request_id", f"req-{int(time.time())}")
        a = payload.get("a")
        b = payload.get("b")
        c = payload.get("c")

        print(f"\n[CLIENT] {addr} request_id={request_id} a={a}, b={b}, c={c}")

        # Validación de formato
        if a is None or b is None or c is None:
            send_json(conn, {"ok": False, "error": "Faltan parámetros a, b, c"})
            return

        try:
            a = float(a)
            b = float(b)
            c = float(c)
        except ValueError:
            send_json(conn, {"ok": False, "error": "a, b, c deben ser numéricos"})
            return

        result = process_quadratic_request(a, b, c, request_id)
        send_json(conn, result)

    except Exception as e:
        error_msg = f"Error interno en coordinador: {str(e)}"
        print("[ERROR]", error_msg)
        traceback.print_exc()
        try:
            send_json(conn, {"ok": False, "error": error_msg})
        except Exception:
            pass
    finally:
        conn.close()


def main():
    print(f"[START] Coordinador escuchando en {COORDINATOR_HOST}:{COORDINATOR_PORT}")
    print(f"[INFO] Timeout por operación: {OP_TIMEOUT_SECONDS}s")
    print(f"[INFO] Servidores de operación: {OP_SERVERS}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((COORDINATOR_HOST, COORDINATOR_PORT))
        server.listen(5)

        while True:
            conn, addr = server.accept()
            handle_client(conn, addr)


if __name__ == "__main__":
    main()
