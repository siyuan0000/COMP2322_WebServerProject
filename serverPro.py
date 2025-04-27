# A simple multi-threaded HTTP server that serves files from the current directory.
# It supports GET and HEAD requests, persistent connections (HTTP/1.1 keep-alive),
# and handles Last-Modified/If-Modified-Since for cache validation.
# The server logs each request and response status to a log file.
import socket
import threading
import os
import datetime
import email.utils
import mimetypes
from urllib.parse import unquote

HOST = '0.0.0.0'      # Listen on all interfaces (use 'localhost' for local only)
PORT = 8080           # Port number for the server
LOG_FILE = 'server.log'

# Initialize the mimetypes module to map file extensions to MIME types
mimetypes.init()

# Create a lock for thread-safe logging
log_lock = threading.Lock()

def log_activity(client_addr, request_line, status_code, status_text):
    """Log the client request and response status code to a file with a timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} - {client_addr} - \"{request_line}\" - {status_code} {status_text}\n"
    # Write the log entry to the log file
    with log_lock:
        with open(LOG_FILE, "a") as log_file:
            log_file.write(log_entry)

def parse_request(request_data):
    """
    Parse the raw HTTP request data and return the method, path, version, headers, and request line.
    Raises ValueError for any malformed components (to be translated into HTTP errors).
    """
    # Decode the request bytes to a string (ISO-8859-1 allows binary 0-255 without errors)
    try:
        request_text = request_data.decode('iso-8859-1')
    except UnicodeDecodeError:
        # If decoding fails, the request is not valid text
        raise ValueError("Bad Request")
    # Split the request into lines
    lines = request_text.split("\r\n")
    if len(lines) < 1 or lines[0] == '':
        raise ValueError("Bad Request")
    # Extract the request line (first line of the request)
    request_line = lines[0]
    parts = request_line.split()
    if len(parts) != 3:
        # Request line must have exactly 3 parts: method, path, and HTTP version
        raise ValueError("Bad Request")
    method, path, version = parts
    method = method.upper()
    # Validate HTTP version
    if version not in ("HTTP/1.0", "HTTP/1.1"):
        raise ValueError("HTTP Version Not Supported")
    # Validate and support only GET and HEAD methods
    if method not in ("GET", "HEAD"):
        raise ValueError("Not Implemented")
    # Path should start with "/" and not be empty
    if not path.startswith('/'):
        raise ValueError("Bad Request")
    # Remove query parameters from the path (anything after '?'), if present
    if '?' in path:
        path = path.split('?', 1)[0]
    # Decode URL-encoded characters in the path (e.g., %20 to space)
    path = unquote(path)
    # Security: prevent accessing files above the current directory
    if os.path.abspath(os.getcwd() + path).startswith(os.getcwd()) is False:
        raise ValueError("Bad Request")
    # Parse the remaining lines into headers until an empty line is encountered
    headers = {}
    for line in lines[1:]:
        if line == '':
            break  # End of headers section
        if ':' not in line:
            # Skip malformed header lines (could also raise an error)
            continue
        key, value = line.split(':', 1)
        headers[key.strip()] = value.strip()
    return method, path, version, headers, request_line

def build_response(method, path, request_headers):
    """
    Given the request method, path, and headers, build an appropriate HTTP response.
    Returns a tuple: (status_code, reason_phrase, response_headers_dict, response_body_bytes).
    """
    # Default headers for all responses
    response_headers = {
        "Date": email.utils.formatdate(usegmt=True),
        "Server": "SimplePythonServer/1.0"
    }
    # If requesting root "/", serve index.html if it exists
    if path == "/":
        path = "/index.html"
    # Determine the file's absolute path on the server
    full_path = os.path.abspath(os.getcwd() + path)
    # Security check: ensure the requested file is under current directory
    if not full_path.startswith(os.getcwd()):
        # The requested path is not allowed
        body = b"<html><body><h1>400 Bad Request</h1></body></html>"
        response_headers["Content-Length"] = str(len(body))
        response_headers["Content-Type"] = "text/html"
        return 400, "Bad Request", response_headers, body
    # Check if the file exists on the server
    if not os.path.exists(full_path):
        body = b"<html><body><h1>404 Not Found</h1></body></html>"
        response_headers["Content-Length"] = str(len(body))
        response_headers["Content-Type"] = "text/html"
        return 404, "Not Found", response_headers, body
    # If the path is a directory (and not a file), return 404 (no directory listing)
    if os.path.isdir(full_path):
        body = b"<html><body><h1>404 Not Found</h1></body></html>"
        response_headers["Content-Length"] = str(len(body))
        response_headers["Content-Type"] = "text/html"
        return 404, "Not Found", response_headers, body
    # Determine the file's MIME type based on its extension
    content_type, encoding = mimetypes.guess_type(full_path)
    if content_type is None:
        # Unknown file type, refuse to serve it
        body = b"<html><body><h1>415 Unsupported Media Type</h1></body></html>"
        response_headers["Content-Length"] = str(len(body))
        response_headers["Content-Type"] = "text/html"
        return 415, "Unsupported Media Type", response_headers, body
    response_headers["Content-Type"] = content_type
    # Get file size and last modification time for headers
    try:
        file_size = os.path.getsize(full_path)
        last_mod_ts = os.path.getmtime(full_path)
    except Exception:
        # If there's an error accessing the file (e.g., permission issue)
        body = b"<html><body><h1>500 Internal Server Error</h1></body></html>"
        response_headers["Content-Length"] = str(len(body))
        response_headers["Content-Type"] = "text/html"
        return 500, "Internal Server Error", response_headers, body
    # Format the Last-Modified time in HTTP-date format
    last_mod_str = datetime.datetime.utcfromtimestamp(last_mod_ts).strftime("%a, %d %b %Y %H:%M:%S GMT")
    response_headers["Last-Modified"] = last_mod_str
    # Handle conditional GET: If-Modified-Since header
    ims_value = request_headers.get("If-Modified-Since")
    if ims_value:
        try:
            ims_dt = email.utils.parsedate_to_datetime(ims_value)
        except Exception:
            ims_dt = None
        if ims_dt:
            # Compare file's last modified time to the If-Modified-Since time
            if last_mod_ts <= ims_dt.timestamp():
                # File not modified since the time provided by client
                response_headers.pop("Content-Type", None)  # Not sending content for 304
                response_headers["Content-Length"] = "0"
                return 304, "Not Modified", response_headers, b""
    # Read the file content if this is a GET request (skip if HEAD)
    body = b""
    if method == "GET":
        try:
            with open(full_path, "rb") as f:
                body = f.read()
        except Exception:
            # If reading file fails, return 500 Internal Server Error
            body = b"<html><body><h1>500 Internal Server Error</h1></body></html>"
            response_headers["Content-Length"] = str(len(body))
            response_headers["Content-Type"] = "text/html"
            return 500, "Internal Server Error", response_headers, body
    # Set the Content-Length header (for GET it's the file size, for HEAD it's also file size as body is empty)
    content_length = file_size if method == "HEAD" else len(body)
    response_headers["Content-Length"] = str(content_length)
    # Return 200 OK with the file content (or empty body if HEAD)
    return 200, "OK", response_headers, body

def handle_client(conn, addr):
    """
    Handle an accepted client connection: read requests, send responses, and manage persistence.
    Runs in a separate thread for each client.
    """
    client_ip = f"{addr[0]}:{addr[1]}"
    # Buffer to accumulate received data (to handle partial packets)
    buffer = b""
    # Keep connection open for multiple requests if client uses keep-alive
    keep_alive = True
    while keep_alive:
        try:
            # Read data until a full request (headers and blank line) is received
            while b"\r\n\r\n" not in buffer:
                data = conn.recv(1024)
                if not data:
                    # No more data (client closed connection)
                    keep_alive = False
                    break
                buffer += data
            if not keep_alive:
                break
            # Split the buffer into a single request and any leftover bytes after the request
            header_end = buffer.find(b"\r\n\r\n")
            request_bytes = buffer[:header_end]
            # Remove this request from buffer, leaving any extra bytes (for pipelined requests)
            buffer = buffer[header_end + 4:]
            # Parse the HTTP request
            try:
                method, path, version, headers, request_line = parse_request(request_bytes)
            except ValueError as e:
                # Handle any parsing errors by sending an appropriate error response
                err_message = str(e)
                if err_message == "HTTP Version Not Supported":
                    status_code, status_text = 505, "HTTP Version Not Supported"
                elif err_message == "Not Implemented":
                    status_code, status_text = 501, "Not Implemented"
                else:
                    status_code, status_text = 400, "Bad Request"
                # Prepare a simple HTML body for the error response
                error_body = f"<html><body><h1>{status_code} {status_text}</h1></body></html>".encode('utf-8')
                error_headers = (
                    f"HTTP/1.1 {status_code} {status_text}\r\n"
                    f"Content-Length: {len(error_body)}\r\n"
                    f"Content-Type: text/html\r\n"
                    f"Connection: close\r\n"
                    f"Date: {email.utils.formatdate(usegmt=True)}\r\n\r\n"
                )
                # Send the error response and close the connection
                conn.sendall(error_headers.encode('iso-8859-1') + error_body)
                # Log the invalid request
                log_activity(client_ip, request_line if 'request_line' in locals() else "<invalid request>", status_code, status_text)
                keep_alive = False
                break
            # Build the HTTP response for the valid request
            status_code, status_text, resp_headers, body = build_response(method, path, headers)
            # Determine the Connection header and whether to keep the connection alive
            conn_close = False
            if version == "HTTP/1.1":
                # HTTP/1.1 persists by default unless "Connection: close" is sent
                if headers.get("Connection", "").lower() == "close":
                    conn_close = True
                    resp_headers["Connection"] = "close"
                else:
                    resp_headers["Connection"] = "keep-alive"
            elif version == "HTTP/1.0":
                # HTTP/1.0 closes by default unless "Connection: keep-alive" is sent
                if headers.get("Connection", "").lower() == "keep-alive":
                    resp_headers["Connection"] = "keep-alive"
                else:
                    conn_close = True
                    resp_headers["Connection"] = "close"
            # Create the response status line and headers section
            status_line = f"{version} {status_code} {status_text}\r\n"
            headers_blob = "".join(f"{name}: {value}\r\n" for name, value in resp_headers.items())
            response_head = (status_line + headers_blob + "\r\n").encode('iso-8859-1')
            # Send the response headers and body (if method is GET and not 304)
            if method == "HEAD" or status_code == 304:
                # For HEAD requests or 304 Not Modified, do not send the body content
                conn.sendall(response_head)
            else:
                conn.sendall(response_head + body)
            # Log the successful request and response code
            log_activity(client_ip, f"{method} {path} {version}", status_code, status_text)
            # Decide if the connection should be closed
            if conn_close or status_code in (400, 500, 501, 505):
                keep_alive = False
        except Exception as e:
            # On any unexpected server error, send a 500 Internal Server Error and break
            error_body = b"<html><body><h1>500 Internal Server Error</h1></body></html>"
            error_headers = (
                "HTTP/1.1 500 Internal Server Error\r\n"
                f"Content-Length: {len(error_body)}\r\n"
                "Content-Type: text/html\r\n"
                "Connection: close\r\n"
                f"Date: {email.utils.formatdate(usegmt=True)}\r\n\r\n"
            ).encode('iso-8859-1')
            try:
                conn.sendall(error_headers + error_body)
            except Exception:
                pass
            # Log the internal error
            log_activity(client_ip, f"{method if 'method' in locals() else ''} {path if 'path' in locals() else ''} {version if 'version' in locals() else ''}", 500, "Internal Server Error")
            break
    conn.close()

def start_server():
    """Initialize the socket server and listen for incoming connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        # Allow socket address reuse to avoid 'Address already in use' on restart
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((HOST, PORT))
        server_sock.listen(5)
        print(f"Server listening on port {PORT}...")
        while True:
            # Accept a new client connection
            client_conn, client_addr = server_sock.accept()
            # Handle the client connection in a new thread
            thread = threading.Thread(target=handle_client, args=(client_conn, client_addr))
            thread.daemon = True
            thread.start()
