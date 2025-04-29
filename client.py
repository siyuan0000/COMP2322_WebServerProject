import socket
import threading
import sys
import time
import email.utils  # for RFC-1123 date

HOST = '127.0.0.1'
PORT = 8080

def send_request(method, path='/', extra_headers=None, client_id=0):
    """Send a single HTTP request and print the response (tagged by client ID)."""
    if extra_headers is None:
        extra_headers = {}

    request_line = f"{method} {path} HTTP/1.1\r\n"
    headers = {
        "Host": f"{HOST}:{PORT}",
        "Connection": "close",
        "User-Agent": f"SimpleTestClient/{client_id}"
    }
    headers.update(extra_headers)

    header_block = ''.join(f"{k}: {v}\r\n" for k, v in headers.items())
    request_bytes = (request_line + header_block + "\r\n").encode('utf-8')

    response = b""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((HOST, PORT))
            sock.sendall(request_bytes)
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
    except Exception as exc:
        print(f"[Client {client_id}] Connection error: {exc}")
        return

    print(f"\n--- Client {client_id} Response ---")
    print(response.decode('iso-8859-1', errors='replace'))
    print(f"--- End of Client {client_id} Response ---\n")


def batch_test():
    """Sequentially issue requests covering required status codes (304 included)."""
    # Generate current time in RFC-1123 format for the 304 test
    current_http_date = email.utils.formatdate(usegmt=True)

    tests = [
        ("GET", "/index.html", {}, "Normal GET Request (200)"),
        ("HEAD", "/index.html", {}, "HEAD Request (200, no body)"),
        ("GET", "/nofile.html", {}, "404 Not Found Test"),
        ("GET", "/../server.log", {}, "403 Forbidden Test"),
        ("GET", "/unsupported.xyz", {}, "415 Unsupported Media Type Test"),
        ("POST", "/index.html", {}, "400 Bad Request Test"),
        ("GET", "/index.html", {"If-Modified-Since": current_http_date}, "304 Not Modified Test"),
    ]

    for idx, (method, path, extra_headers, desc) in enumerate(tests, 1):
        print(f"\n=== {idx}. {desc} ===")
        send_request(method, path, extra_headers, client_id=idx)
        time.sleep(0.4)


def concurrent_test(num_clients=10):
    """Launch multiple clients concurrently to validate multi-threading."""
    print(f"Starting {num_clients} concurrent clients...\n")
    threads = []
    for i in range(num_clients):
        t = threading.Thread(target=send_request, args=("GET", "/index.html", None, i))
        t.start()
        threads.append(t)
        time.sleep(0.05)
    for t in threads:
        t.join()
    print(f"\n[Concurrent Test] All {num_clients} clients completed.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "batch":
            batch_test()
        elif cmd == "concurrent":
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            concurrent_test(n)
        else:
            method = sys.argv[1].upper()
            path = sys.argv[2] if len(sys.argv) > 2 else "/"
            send_request(method, path, client_id=0)
    else:
        print("Usage:")
        print("  python client.py [METHOD] [PATH]          # Single request")
        print("  python client.py batch                    # Sequential tests")
        print("  python client.py concurrent [N]           # N concurrent clients")