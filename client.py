import socket
import threading
import sys
import time

HOST = '127.0.0.1'  # Server IP address
PORT = 8080         # Server port number

def send_request(method, path='/', extra_headers=None, client_id=0):
    """Send a single HTTP request and print response with client ID."""
    if extra_headers is None:
        extra_headers = {}

    request_line = f"{method} {path} HTTP/1.1\r\n"
    headers = {
        "Host": f"{HOST}:{PORT}",
        "Connection": "close",
        "User-Agent": f"SimpleTestClient/{client_id}"
    }
    headers.update(extra_headers)

    header_text = ''.join(f"{k}: {v}\r\n" for k, v in headers.items())
    request_data = (request_line + header_text + "\r\n").encode('utf-8')

    response = b""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            s.sendall(request_data)
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response += chunk
    except Exception as e:
        print(f"[Client {client_id}] Connection error: {e}")
        return

    print(f"\n--- Client {client_id} Response ---")
    print(response.decode('iso-8859-1', errors='replace'))
    print(f"--- End of Client {client_id} Response ---\n")


def batch_test():
    """Sequentially test different functionalities."""
    tests = [
        ("GET", "/index.html", "Normal GET Request"),
        ("HEAD", "/index.html", "HEAD Request (No body)"),
        ("GET", "/nofile.html", "404 Not Found Test"),
        ("GET", "/../server.log", "403 Forbidden Test"),
        ("GET", "/unsupported.xyz", "415 Unsupported Media Type Test"),
        ("POST", "/index.html", "400 Bad Request Test"),
    ]

    for idx, (method, path, description) in enumerate(tests, start=1):
        print(f"\n=== {idx}. {description} ===")
        send_request(method, path, client_id=idx)
        time.sleep(0.5)  # Small delay between tests


def concurrent_test(num_clients=10):
    """Launch multiple clients concurrently to test server's multi-threading."""
    threads = []

    print(f"Starting {num_clients} concurrent clients...\n")

    for i in range(num_clients):
        t = threading.Thread(target=send_request, args=("GET", "/index.html", None, i))
        threads.append(t)
        t.start()
        time.sleep(0.05)  # Slight stagger to better simulate real-world clients

    for t in threads:
        t.join()

    print(f"\n[Concurrent Test] All {num_clients} clients have completed.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "batch":
            batch_test()
        elif sys.argv[1] == "concurrent":
            num = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            concurrent_test(num)
        else:
            method = sys.argv[1].upper()
            path = sys.argv[2] if len(sys.argv) > 2 else "/"
            send_request(method, path, client_id=0)
    else:
        print("Usage:")
        print("  python client.py [METHOD] [PATH]          # Send a single request")
        print("  python client.py batch                    # Run batch functional tests")
        print("  python client.py concurrent [num_clients] # Run concurrent clients test")
