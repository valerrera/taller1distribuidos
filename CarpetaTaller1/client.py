import socket
import json
import time

COORDINATOR_IP = "10.43.97.251"   # IP del coordinador 
COORDINATOR_PORT = 5000


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


def main():
    print("=== Cliente cálculo cuadrático distribuido ===")

    a = input("Ingrese a: ").strip()
    b = input("Ingrese b: ").strip()
    c = input("Ingrese c: ").strip()

    payload = {
        "request_id": f"cli-{int(time.time())}",
        "a": a,
        "b": b,
        "c": c
    }

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((COORDINATOR_IP, COORDINATOR_PORT))
            send_json(s, payload)

            response = recv_json(s)

        print("\n=== Respuesta del coordinador ===")
        print(json.dumps(response, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error conectando al coordinador: {e}")


if __name__ == "__main__":
    main()
