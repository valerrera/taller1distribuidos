import socket
import json
import math
import traceback

HOST = "0.0.0.0"   # Escucha en todas las interfaces de la VM
PORT = 5001        # Todos los servidores de operación usan el mismo puerto


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


def handle_operation(payload):
    op = payload.get("op")

    if op == "sqrt_discriminant":
        a = payload["a"]
        b = payload["b"]
        c = payload["c"]

        disc = (b * b) - (4 * a * c)
        if a == 0:
            return {"ok": False, "error": "Valor inválido: a no puede ser 0"}
        if disc < 0:
            return {"ok": False, "error": "No hay raíces reales (discriminante < 0)"}

        sqrt_d = math.sqrt(disc)
        return {"ok": True, "sqrt_d": sqrt_d, "disc": disc}

    elif op == "numerator":
        b = payload["b"]
        sqrt_d = payload["sqrt_d"]

        num_plus = (-b) + sqrt_d
        num_minus = (-b) - sqrt_d

        return {
            "ok": True,
            "num_plus": num_plus,
            "num_minus": num_minus
        }

    elif op == "division":
        a = payload["a"]
        num_plus = payload["num_plus"]
        num_minus = payload["num_minus"]

        den = 2 * a
        if den == 0:
            return {"ok": False, "error": "División por cero: 2a = 0"}

        x1 = num_plus / den
        x2 = num_minus / den

        return {"ok": True, "x1": x1, "x2": x2, "den": den}

    elif op == "full_quadratic":
        a = payload["a"]
        b = payload["b"]
        c = payload["c"]

        if a == 0:
            return {"ok": False, "error": "Valor inválido: a no puede ser 0"}

        disc = (b * b) - (4 * a * c)
        if disc < 0:
            return {"ok": False, "error": "No hay raíces reales (discriminante < 0)"}

        sqrt_d = math.sqrt(disc)
        num_plus = (-b) + sqrt_d
        num_minus = (-b) - sqrt_d
        den = 2 * a

        if den == 0:
            return {"ok": False, "error": "División por cero: 2a = 0"}

        x1 = num_plus / den
        x2 = num_minus / den

        return {
            "ok": True,
            "disc": disc,
            "sqrt_d": sqrt_d,
            "num_plus": num_plus,
            "num_minus": num_minus,
            "den": den,
            "x1": x1,
            "x2": x2
        }

    else:
        return {"ok": False, "error": f"Operación no soportada: {op}"}


def handle_client(conn, addr):
    try:
        payload = recv_json(conn)
        if payload is None:
            return

        request_id = payload.get("request_id", "sin_id")
        op = payload.get("op", "sin_op")

        print(f"[INFO] Solicitud desde {addr} | request_id={request_id} | op={op}")

        result = handle_operation(payload)

        send_json(conn, result)
        print(f"[OK] Respuesta enviada | request_id={request_id} | op={op} | ok={result.get('ok')}")

    except Exception as e:
        error_msg = f"Error interno en servidor de operación: {str(e)}"
        print("[ERROR]", error_msg)
        traceback.print_exc()
        try:
            send_json(conn, {"ok": False, "error": error_msg})
        except Exception:
            pass
    finally:
        conn.close()


def main():
    print(f"[START] Servidor de operación escuchando en {HOST}:{PORT}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(5)

        while True:
            conn, addr = server.accept()
            handle_client(conn, addr)


if __name__ == "__main__":
    main()
