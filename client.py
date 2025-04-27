import socket
import sys

HOST = '127.0.0.1'  # Server IP address
PORT = 8080         # Server port number


def send_request(method, path='/', host=HOST, port=PORT, headers=None):
    """Send an HTTP request to the server and print the response."""
    if headers is None:
        headers = {}

    # Basic request line
    request_line = f"{method} {path} HTTP/1.1\r\n"

    # Default headers
    default_headers = {
        "Host": f"{host}:{port}",
        "Connection": "close",  # Close after each request to simplify client behavior
        "User-Agent": "SimpleTestClient/1.0"
    }
    all_headers = {**default_headers, **headers}

    # Compose headers
    header_lines = "".join(f"{k}: {v}\r\n" for k, v in all_headers.items())

    # Combine into full request
    request_message = (request_line + header_lines + "\r\n").encode('utf-8')

    # Connect and send
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.sendall(request_message)
        # Receive and print response
        response = b""
        while True:
            data = s.recv(4096)
            if not data:
                break
            response += data
        print(response.decode('iso-8859-1'))


if __name__ == "__main__":
    # Allow basic command-line usage: python client.py [METHOD] [PATH]
    method = 'GET'
    path = '/'
    if len(sys.argv) > 1:
        method = sys.argv[1].upper()
    if len(sys.argv) > 2:
        path = sys.argv[2]
    send_request(method, path)
