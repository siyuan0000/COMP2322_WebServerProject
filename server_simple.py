import socket
import threading
from datetime import datetime

# --- Phase 1: Simple HTTP Server ---
# --- Configuration ---
HOST = '127.0.0.1'  # Localhost
PORT = 8080  # Non-privileged port
BUFFER_SIZE = 4096  # Increased buffer size for larger requests


# --- Client Handler Function ---
def handle_client(conn, addr):
    """Handles a client connection and logs the request."""
    client_ip = addr[0]
    print(f"[NEW CONNECTION] {addr} connected.")

    try:
        # Receive full HTTP request (may require multiple reads)
        request_data = b''
        while True:
            chunk = conn.recv(BUFFER_SIZE)
            if not chunk:
                break
            request_data += chunk
            if b'\r\n\r\n' in request_data:  # Check for end of headers
                break

        if not request_data:
            print(f"[ERROR] No data received from {addr}")
            return

        # Decode request and parse headers
        decoded_request = request_data.decode('utf-8', errors='ignore')
        headers = decoded_request.split('\r\n')
        first_line = headers[0].split() if headers else []

        # Extract request method and path
        method = first_line[0] if len(first_line) > 0 else 'UNKNOWN'
        path = first_line[1] if len(first_line) > 1 else '/'

        # Log request details (Phase 1 requirement)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = (
            f"[{timestamp}] Client: {client_ip} | "
            f"Requested File: {path} | Method: {method}"
        )
        print(log_entry)

        # Display raw request (for debugging)
        print(f"\n--- Raw Request from {addr} ---")
        print(decoded_request.strip())
        print("------------------------------------")

    except socket.error as e:
        print(f"[SOCKET ERROR] {addr}: {e}")
    except Exception as e:
        print(f"[UNEXPECTED ERROR] {addr}: {e}")
    finally:
        # Phase 1: Close connection without sending response
        conn.close()
        print(f"[CLOSED] Connection to {addr} closed\n")


# --- Main Server Function ---
def start_server():
    """Starts the multi-threaded server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        print(f"[LISTENING] Server running on {HOST}:{PORT}\n")
    except Exception as e:
        print(f"[ERROR] Failed to start server: {e}")
        return

    try:
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
            print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Server stopped by user")
    finally:
        server_socket.close()


# --- Entry Point ---
if __name__ == "__main__":
    start_server()