import socket
import sys
import time

HOST = '127.0.0.1'  # Server IP address
PORT = 8080         # Server port number

def send_request(method, path='/', extra_headers=None):
    """Send an HTTP request and return the response text."""
    if extra_headers is None:
        extra_headers = {}

    request_line = f"{method} {path} HTTP/1.1\r\n"
    headers = {
        "Host": f"{HOST}:{PORT}",
        "Connection": "close",
        "User-Agent": "SimpleTestClient/1.0"
    }
    headers.update(extra_headers)

    header_text = ''.join(f"{k}: {v}\r\n" for k, v in headers.items())
    request_data = (request_line + header_text + "\r\n").encode('utf-8')

    response = b""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall(request_data)
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk

    return response.decode('iso-8859-1', errors='replace')


def simple_test(method, path, description, extra_headers=None):
    """Run a single test and print the result."""
    print(f"\n=== {description} ===")
    print(f"Request: {method} {path}")
    response = send_request(method, path, extra_headers)
    print(response)
    print("="*40)


def batch_test():
    """Batch send test requests to cover all functionalities."""

    tests = [
        # Normal file requests
        ("GET", "/index.html", "1. Normal GET request returns 200 OK"),
        ("HEAD", "/index.html", "2. Normal HEAD request returns 200 OK (no body)"),

        # Test If-Modified-Since header
        ("GET", "/index.html", "3. Test 304 Not Modified with If-Modified-Since", {
            "If-Modified-Since": "Wed, 01 Jan 3000 00:00:00 GMT"  # Future time to trigger 304 response
        }),

        # Test 404 Not Found
        ("GET", "/nofile.html", "4. Non-existent file request returns 404 Not Found"),

        # Test 403 Forbidden (directory traversal attempt)
        ("GET", "/../server.log", "5. Accessing parent directory triggers 403 Forbidden"),

        # Test 415 Unsupported Media Type
        ("GET", "/unsupported.xyz", "6. Unsupported file type returns 415 Unsupported Media Type"),

        # Test 400 Bad Request (invalid method)
        ("POST", "/index.html", "7. Invalid method returns 400 Bad Request"),
    ]

    for test in tests:
        if len(test) == 4:
            method, path, description, headers = test
        else:
            method, path, description = test
            headers = None
        simple_test(method, path, description, headers)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "batch":
        batch_test()
    else:
        # Support custom requests via command line
        method = sys.argv[1] if len(sys.argv) > 1 else "GET"
        path = sys.argv[2] if len(sys.argv) > 2 else "/"
        simple_test(method, path, "Single custom request")