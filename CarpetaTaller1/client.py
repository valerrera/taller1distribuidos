import socket
import json
import time

# ==========================================
# CONFIGURACIÓN
# ==========================================

# IP del coordinador (VM donde corre el servidor central)
COORDINATOR_IP = "10.43.97.251"
COORDINATOR_PORT = 5000


# ==========================================
# FUNCIONES AUXILIARES JSON
# ==========================================

# Enviamos JSON terminado en salto de línea
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


# ==========================================
# CLIENTE
# ==========================================

def main():

    print("=== Cliente cálculo cuadrático distribuido ===")

    # Pedimos datos al usuario
    a = input("Ingrese a: ").strip()
    b = input("Ingrese b: ").strip()
    c = input("Ingrese c: ").strip()

    # Creamos payload para enviar al coordinador
    payload = {
        "request_id": f"cli-{int(time.time())}",
        "a": a,
        "b": b,
        "c": c
    }

    try:

        # Abrimos conexión TCP con el coordinador
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

            s.connect((COORDINATOR_IP, COORDINATOR_PORT))

            # Enviamos datos
            send_json(s, payload)

            # Esperamos respuesta
            response = recv_json(s)

        if response is None:
            print("No se recibió respuesta del coordinador.")
            return

        print("\n=== Respuesta del coordinador ===")
        print(json.dumps(response, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error conectando al coordinador: {e}")


if __name__ == "__main__":
    main()