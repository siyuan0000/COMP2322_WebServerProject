import socket
import os
import time
import urllib.parse
import email.utils
from datetime import datetime, timezone
import threading

log_lock = threading.Lock()
# Configuration
HOST = '0.0.0.0'        # Listen on all network interfaces
PORT = 8080             # Default port for the server
WWW_ROOT = 'www'        # Root directory for web files
LOG_FILE = 'server.log' # Path to log file

# Supported MIME types for content
MIME_TYPES = {
    ".html": "text/html",
    ".htm":  "text/html",
    ".txt":  "text/plain",
    ".css":  "text/css",
    ".js":   "application/javascript",
    ".json": "application/json",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif":  "image/gif",
    ".ico":  "image/x-icon"
}

# HTTP status codes and reason phrases
STATUS_PHRASES = {
    200: "OK",
    304: "Not Modified",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    415: "Unsupported Media Type"
}

def format_http_date(ts: float) -> str:
    """
    Convert a timestamp (seconds since epoch) to a string in HTTP-date format (RFC 1123).
    """
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")

def log_request(client_addr: str, request_line: str, status_code: int) -> None:
    """Thread-safe request logger."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reason = STATUS_PHRASES.get(status_code, "")
    entry = f"{timestamp} - {client_addr} - \"{request_line}\" - {status_code} {reason}\n"
    with log_lock:                     # NEW
        with open(LOG_FILE, "a") as f:
            f.write(entry)


def parse_request(request_data: bytes):
    """
    Parse an HTTP request message and return (method, path, version, headers, request_line).
    Raises ValueError for bad requests or PermissionError for forbidden paths.
    """
    # Decode the request bytes to text (ISO-8859-1 allows raw 0-255 values)
    try:
        request_text = request_data.decode('iso-8859-1')
    except Exception:
        raise ValueError("Cannot decode request bytes")
    # Split request into lines
    lines = request_text.split("\r\n")
    if len(lines) < 1 or lines[0] == "":
        raise ValueError("No request line")
    request_line = lines[0]
    parts = request_line.split(" ")
    if len(parts) != 3:
        raise ValueError("Malformed request line")
    method, raw_path, version = parts
    method = method.upper()
    if method not in ("GET", "HEAD"):
        raise ValueError("Unsupported method")
    if version not in ("HTTP/1.0", "HTTP/1.1"):
        raise ValueError("Unsupported HTTP version")
    # Parse headers
    headers = {}
    idx = 1
    while idx < len(lines) and lines[idx] != "":
        header_line = lines[idx]
        if ":" not in header_line:
            raise ValueError("Malformed header line")
        name, value = header_line.split(":", 1)
        headers[name.strip()] = value.strip()
        idx += 1
    if version == "HTTP/1.1" and "Host" not in headers:
        raise ValueError("Missing Host header")
    # Process the request path (exclude query string and fragment)
    path_only = raw_path.split('?', 1)[0].split('#', 1)[0]
    decoded_path = urllib.parse.unquote(path_only)  # decode URL-encoded characters
    # Security: forbid any path that attempts to traverse directories
    if ".." in decoded_path:
        raise PermissionError("Forbidden path")
    # Normalize the path to remove redundant slashes or dots
    normalized_path = os.path.normpath(decoded_path)
    # Remove leading slash to get a relative filesystem path
    if normalized_path.startswith(os.sep):
        normalized_path = normalized_path.lstrip(os.sep)
    return method, normalized_path, version, headers, request_line

def build_response(method: str, normalized_path: str, version: str, headers: dict):
    """
    Build an HTTP response for the given request components.
    Returns a tuple of (response_bytes, keep_alive, status_code).
    """
    status_code = 200
    content = b""
    response_headers = {}
    body = b""

    # Map the normalized path to a file in the WWW_ROOT directory
    base_path = os.path.realpath(WWW_ROOT)
    target_path = os.path.join(WWW_ROOT, normalized_path)
    abs_path = os.path.realpath(target_path)
    # Check if the resolved path is within the www directory
    if not abs_path.startswith(base_path):
        status_code = 403  # outside of permitted directory
    elif os.path.isdir(abs_path):
        # If a directory is requested, look for an index.html
        index_file = os.path.join(abs_path, "index.html")
        if os.path.isfile(index_file):
            abs_path = os.path.realpath(index_file)
        else:
            status_code = 403  # directory access is forbidden (no index file)
    # If OK so far, attempt to open and read the file
    file_mtime = None
    if status_code == 200:
        try:
            file_mtime = os.path.getmtime(abs_path)
            with open(abs_path, "rb") as f:
                content = f.read()
        except FileNotFoundError:
            status_code = 404
        except PermissionError:
            status_code = 403
        except Exception:
            status_code = 404
    # Determine content type if a file is successfully read
    content_type = None
    if status_code == 200:
        ext = os.path.splitext(abs_path)[1].lower()
        if ext in MIME_TYPES:
            content_type = MIME_TYPES[ext]
        else:
            status_code = 415  # unsupported file type
    # Handle conditional GET: If-Modified-Since
    if status_code == 200 and "If-Modified-Since" in headers:
        ims_str = headers["If-Modified-Since"]
        try:
            ims_dt = email.utils.parsedate_to_datetime(ims_str)
        except Exception:
            ims_dt = None
        if ims_dt:
            if ims_dt.tzinfo is None:
                ims_dt = ims_dt.replace(tzinfo=timezone.utc)
            if file_mtime is not None:
                # Compare file mod time (as UTC datetime without microseconds)
                last_mod_dt = datetime.fromtimestamp(file_mtime, tz=timezone.utc).replace(microsecond=0)
                if last_mod_dt <= ims_dt:
                    status_code = 304  # Not Modified
    # Prepare response body and headers based on the status code
    if status_code == 200:
        # 200 OK: body is file content (for GET) or empty (for HEAD)
        body = content if method == "GET" else b""
    elif status_code != 304:
        # Error responses (400, 403, 404, 415): generate a simple HTML page
        reason = STATUS_PHRASES.get(status_code, "")
        error_html = (f"<html><head><title>{status_code} {reason}</title></head>"
                      f"<body><h1>{status_code} {reason}</h1>"
                      f"<p>The requested resource is not available.</p></body></html>")
        body = error_html.encode("utf-8")
        content_type = "text/html"
    # Start building the response lines
    reason_phrase = STATUS_PHRASES.get(status_code, "")
    status_line = f"{version} {status_code} {reason_phrase}\r\n"
    # Date header (HTTP-date format)
    response_headers["Date"] = format_http_date(time.time())
    # Connection header: decide if we will close or keep the connection alive
    conn_hdr = headers.get("Connection", "").lower()
    if version == "HTTP/1.1":
        # HTTP/1.1 defaults to keep-alive unless "Connection: close"
        if conn_hdr == "close":
            response_headers["Connection"] = "close"
            keep_alive = False
        else:
            response_headers["Connection"] = "keep-alive"
            keep_alive = True
    else:  # HTTP/1.0
        # HTTP/1.0 closes by default, unless "Connection: keep-alive" is present
        if conn_hdr == "keep-alive":
            response_headers["Connection"] = "keep-alive"
            keep_alive = True
        else:
            response_headers["Connection"] = "close"
            keep_alive = False
    # Last-Modified header for OK responses
    if status_code == 200 and file_mtime is not None:
        response_headers["Last-Modified"] = format_http_date(file_mtime)
    # Content-Type header (if available and not a 304 response)
    if content_type and status_code != 304:
        response_headers["Content-Type"] = content_type
    # Content-Length header (for all responses with a body, including 0-length for HEAD or errors)
    if status_code != 304:
        if status_code == 200 and method == "HEAD":
            response_headers["Content-Length"] = str(len(content))
        else:
            response_headers["Content-Length"] = str(len(body))
    # Assemble the response headers into a byte sequence
    headers_bytes = "".join(f"{name}: {value}\r\n" for name, value in response_headers.items()).encode("utf-8")
    # Combine status line, headers, and body into final response bytes
    response_bytes = status_line.encode("utf-8") + headers_bytes + b"\r\n" + body
    return response_bytes, keep_alive, status_code

def handle_client(client_sock, client_addr):
    """
    Serve all HTTP requests from one client socket.
    Runs in a dedicated thread; supports keep-alive.
    """
    client_ip, client_port = client_addr
    addr_str = f"{client_ip}:{client_port}"

    try:
        while True:                                    # loop for persistent connection
            request_bytes = b""
            while b"\r\n\r\n" not in request_bytes:
                chunk = client_sock.recv(1024)
                if not chunk:
                    break                               # client closed
                request_bytes += chunk
            if not request_bytes:                       # nothing received
                break

            try:
                method, path, version, headers, req_line = parse_request(request_bytes)
            except PermissionError:
                status = 403
                reason = STATUS_PHRASES[status]
                body = (f"<html><body><h1>{status} {reason}</h1>"
                        f"<p>The requested resource is forbidden.</p></body></html>")
                proto = "HTTP/1.1" if b"HTTP/1.1" in request_bytes else "HTTP/1.0"
                resp = (f"{proto} {status} {reason}\r\n"
                        f"Date: {format_http_date(time.time())}\r\n"
                        f"Content-Type: text/html\r\n"
                        f"Content-Length: {len(body.encode())}\r\n"
                        f"Connection: close\r\n\r\n"
                        f"{body}")
                client_sock.sendall(resp.encode())
                first_line = request_bytes.split(b"\r\n", 1)[0].decode("iso-8859-1", "ignore")
                log_request(addr_str, first_line, status)
                break                                   # close socket after 403
            except ValueError:                          # malformed request → 400
                status = 400
                reason = STATUS_PHRASES[status]
                body = (f"<html><body><h1>{status} {reason}</h1>"
                        f"<p>Bad request.</p></body></html>")
                proto = "HTTP/1.1" if b"HTTP/1.1" in request_bytes else "HTTP/1.0"
                resp = (f"{proto} {status} {reason}\r\n"
                        f"Date: {format_http_date(time.time())}\r\n"
                        f"Content-Type: text/html\r\n"
                        f"Content-Length: {len(body.encode())}\r\n"
                        f"Connection: close\r\n\r\n"
                        f"{body}")
                client_sock.sendall(resp.encode())
                first_line = request_bytes.split(b"\r\n", 1)[0].decode("iso-8859-1", "ignore")
                log_request(addr_str, first_line, status)
                break                                   # close socket after 400

            # ▸ normal processing via build_response --------------------------
            response_bytes, keep_alive, status_code = build_response(
                method, path, version, headers
            )
            client_sock.sendall(response_bytes)
            log_request(addr_str, req_line, status_code)

            if not keep_alive:                          # client or protocol said close
                break
    finally:
        client_sock.close()

def run_server(host: str = HOST, port: int = PORT):
    """
    Start the multi-threaded HTTP server: accept connections and
    hand each one off to handle_client() in its own thread.
    """
    os.makedirs(WWW_ROOT, exist_ok=True)          # ensure web-root exists

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(5)
    print(f"Serving HTTP on {host} port {port} …")

    try:
        while True:
            client_sock, client_addr = server_sock.accept()

            t = threading.Thread(target=handle_client, args=(client_sock, client_addr))
            t.daemon = True            # optional: threads exit when main exits
            t.start()                  # immediately return to accept the next client
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Server stopped by user")
    finally:
        server_sock.close()

if __name__ == "__main__":
    run_server()
