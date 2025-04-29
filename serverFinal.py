import socket
import threading
import logging
import os
import mimetypes
import sys

HOST = ''
PORT = 8080  # Default port, can be overridden via command-line
DOC_ROOT = "www"  # Default directory to serve files from

# Allow overriding PORT and DOC_ROOT via command-line arguments
if len(sys.argv) > 1:
    PORT = int(sys.argv[1])
if len(sys.argv) > 2:
    DOC_ROOT = sys.argv[2]

# Ensure the document root directory exists
if not os.path.isdir(DOC_ROOT):
    os.makedirs(DOC_ROOT, exist_ok=True)

# Configure logging to file and console with time stamps
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[logging.FileHandler("server.log", mode='a'),
                              logging.StreamHandler()])

# Lock for synchronizing log writes to avoid interleaving in multi-threading
log_lock = threading.Lock()


def log_request(client_addr, request_line, status_code):
    """
    Log the HTTP request and response code in a thread-safe manner.
    """
    ip, port = client_addr
    message = f'{ip}:{port} "{request_line}" {status_code}'
    with log_lock:
        logging.info(message)


def handle_client(client_socket, client_address):
    """
    Handle a single HTTP client: read request, send response, and log the transaction.
    Runs in a separate thread for each client connection.
    """
    try:
        # Receive the HTTP request data (simple implementation: no streaming of large requests)
        request_data = b""
        client_socket.settimeout(1.0)  # small timeout to prevent hanging on partial requests
        while True:
            try:
                chunk = client_socket.recv(1024)
            except socket.timeout:
                # Break loop if no more data within timeout (request might be incomplete but we'll proceed)
                break
            if not chunk:
                # Client closed connection
                break
            request_data += chunk
            if b"\r\n\r\n" in request_data:
                # End of HTTP headers reached
                break

        if not request_data:
            return  # No request received (client disconnected)

        # Decode request bytes to string (HTTP is ASCII-based)
        try:
            request_text = request_data.decode('utf-8', errors='ignore')
        except UnicodeDecodeError:
            request_text = request_data.decode('iso-8859-1', errors='ignore')

        # Parse the request line (first line of the request)
        lines = request_text.splitlines()
        if len(lines) == 0:
            return  # empty request, ignore
        request_line = lines[0]  # e.g., "GET /index.html HTTP/1.1"
        parts = request_line.split()
        if len(parts) < 3:
            # Malformed HTTP request line
            bad_response = "HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n"
            client_socket.sendall(bad_response.encode())
            log_request(client_address, request_line, 400)
            return

        method, path, http_version = parts[0], parts[1], parts[2]

        # Only support GET method (others return 501 Not Implemented)
        if method.upper() != "GET":
            body = (f"<html><body><h1>501 Not Implemented</h1>"
                    f"<p>Method {method} is not supported on this server.</p></body></html>")
            headers = [
                "HTTP/1.1 501 Not Implemented",
                "Content-Type: text/html",
                f"Content-Length: {len(body.encode())}",
                "Connection: close"
            ]
            response = "\r\n".join(headers) + "\r\n\r\n" + body
            client_socket.sendall(response.encode())
            log_request(client_address, request_line, 501)
            return

        # Handle root path and directory requests by appending index.html
        if path.endswith('/'):
            path += 'index.html'
        if path == '/':
            path = '/index.html'

        # Prevent directory traversal: construct safe file path within DOC_ROOT
        requested_file = path.lstrip('/')  # remove leading '/'
        full_path = os.path.normpath(os.path.join(DOC_ROOT, requested_file))
        # Ensure the full_path is within the DOC_ROOT directory
        docroot_abspath = os.path.abspath(DOC_ROOT)
        fullpath_abspath = os.path.abspath(full_path)
        if not fullpath_abspath.startswith(docroot_abspath):
            # Security check failed: attempt to access outside DOC_ROOT
            body = "<html><body><h1>403 Forbidden</h1></body></html>"
            headers = [
                "HTTP/1.1 403 Forbidden",
                "Content-Type: text/html",
                f"Content-Length: {len(body.encode())}",
                "Connection: close"
            ]
            response = "\r\n".join(headers) + "\r\n\r\n" + body
            client_socket.sendall(response.encode())
            log_request(client_address, request_line, 403)
            return

        # If the file does not exist or is a directory, return 404
        if not os.path.isfile(full_path):
            body = ("<html><body><h1>404 Not Found</h1>"
                    "<p>The requested resource was not found on this server.</p></body></html>")
            headers = [
                "HTTP/1.1 404 Not Found",
                "Content-Type: text/html",
                f"Content-Length: {len(body.encode())}",
                "Connection: close"
            ]
            response = "\r\n".join(headers) + "\r\n\r\n" + body
            client_socket.sendall(response.encode())
            log_request(client_address, request_line, 404)
        else:
            # File exists; prepare and send a 200 OK response with file content
            # Guess the content type based on file extension
            content_type, _ = mimetypes.guess_type(full_path)
            if content_type is None:
                content_type = "application/octet-stream"  # default binary type

            # Read file content in binary mode
            try:
                with open(full_path, 'rb') as f:
                    content = f.read()
            except OSError:
                # If file can't be read (permission or other error), return 500 Internal Server Error
                body = ("<html><body><h1>500 Internal Server Error</h1>"
                        "<p>Could not read the requested file.</p></body></html>")
                headers = [
                    "HTTP/1.1 500 Internal Server Error",
                    "Content-Type: text/html",
                    f"Content-Length: {len(body.encode())}",
                    "Connection: close"
                ]
                error_response = "\r\n".join(headers) + "\r\n\r\n" + body
                client_socket.sendall(error_response.encode())
                log_request(client_address, request_line, 500)
            else:
                # Send 200 OK with file content
                headers = [
                    "HTTP/1.1 200 OK",
                    f"Content-Type: {content_type}",
                    f"Content-Length: {len(content)}",
                    "Connection: close"
                ]
                response_header = "\r\n".join(headers) + "\r\n\r\n"
                client_socket.sendall(response_header.encode())
                client_socket.sendall(content)
                log_request(client_address, request_line, 200)
    except Exception as e:
        # Log unexpected errors for debugging
        logging.error(f"Exception handling request from {client_address}: {e}")
    finally:
        # Ensure the connection is closed after handling the request
        client_socket.close()


def main():
    """
    Set up the listening socket and handle incoming connections with new threads.
    """
    # Create and configure server socket
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(5)
    print(f"HTTP Server running on port {PORT}, serving directory '{DOC_ROOT}'")

    try:
        while True:
            # Accept a new client connection
            client_sock, client_addr = server_sock.accept()
            # Spawn a new thread to handle the client connection
            client_thread = threading.Thread(target=handle_client, args=(client_sock, client_addr))
            client_thread.daemon = True  # allow thread to exit when main program exits
            client_thread.start()
    except KeyboardInterrupt:
        print("\nShutting down the server.")
    finally:
        server_sock.close()


if __name__ == "__main__":
    main()
