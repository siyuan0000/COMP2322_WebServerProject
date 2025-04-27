import socket
import threading
import os
from urllib.parse import unquote, urlparse
import mimetypes
from email.utils import parsedate_to_datetime, formatdate
import datetime

# --- Configuration ---
HOST = '127.0.0.1'
PORT = 8080
BUFFER_SIZE = 1024
ROOT_DIR = os.path.join(os.getcwd(), 'www')
ALLOWED_MIME_TYPES = {
    'text/html', 'text/plain', 'text/css',
    'image/png', 'image/jpeg', 'image/gif',
    'application/javascript'
}

# 初始化MIME类型库
mimetypes.init()

# --- 错误响应生成函数 ---
def send_error(conn, status_code, reason_phrase, headers):
    """发送带Connection头的错误响应"""
    content = f"<html><body><h1>{status_code} {reason_phrase}</h1></body></html>".encode()
    connection = 'keep-alive' if headers.get('keep_alive') else 'close'
    response = (
        f"HTTP/1.1 {status_code} {reason_phrase}\r\n"
        f"Content-Type: text/html\r\n"
        f"Content-Length: {len(content)}\r\n"
        f"Connection: {connection}\r\n\r\n"
    )
    conn.sendall(response.encode() + content)

def send_404(conn, headers):
    send_error(conn, 404, "Not Found", headers)

def send_403(conn, headers):
    send_error(conn, 403, "Forbidden", headers)

def send_415(conn, headers):
    send_error(conn, 415, "Unsupported Media Type", headers)

def send_500(conn, headers):
    send_error(conn, 500, "Internal Server Error", headers)

# --- 处理文件请求 ---
def handle_file_request(conn, method, full_path, headers):
    try:
        # 文件类型检查
        mime_type, _ = mimetypes.guess_type(full_path)
        if mime_type not in ALLOWED_MIME_TYPES:
            send_415(conn, headers)
            return

        # 获取文件状态信息
        file_stat = os.stat(full_path)

        # 检查If-Modified-Since
        if 'if-modified-since' in headers:
            client_time = parsedate_to_datetime(headers['if-modified-since'])
            server_time = datetime.datetime.fromtimestamp(file_stat.st_mtime, datetime.timezone.utc)
            if server_time <= client_time:
                response = (
                    "HTTP/1.1 304 Not Modified\r\n"
                    f"Connection: {'keep-alive' if headers.get('keep_alive') else 'close'}\r\n\r\n"
                )
                conn.sendall(response.encode())
                return

        # 读取文件内容
        with open(full_path, 'rb') as f:
            content = f.read()

        # 确定Content-Type
        content_type = mime_type if mime_type else 'application/octet-stream'

        # 生成响应头
        last_modified = formatdate(file_stat.st_mtime, usegmt=True)
        response_headers = [
            f"HTTP/1.1 200 OK",
            f"Content-Type: {content_type}",
            f"Content-Length: {len(content)}",
            f"Last-Modified: {last_modified}",
            f"Connection: {'keep-alive' if headers.get('keep_alive') else 'close'}\r\n\r\n"
        ]
        response_header_str = "\r\n".join(response_headers)

        # 发送响应
        conn.sendall(response_header_str.encode())
        if method == 'GET':
            conn.sendall(content)

    except PermissionError:
        send_403(conn, headers)
    except Exception as e:
        print(f"[ERROR] File handling error: {e}")
        send_500(conn, headers)

# --- Client Handler Function ---
def handle_client(conn, addr):
    print(f"[NEW CONNECTION] {addr} connected.")
    keep_alive = True  # HTTP/1.1默认保持连接

    while keep_alive:
        try:
            # 接收请求数据
            request_data = conn.recv(BUFFER_SIZE)
            if not request_data:
                break

            # 解析请求行
            request_text = request_data.decode('utf-8')
            request_lines = request_text.split('\r\n')
            if len(request_lines) == 0:
                break

            # 解析请求行
            request_line = request_lines[0].split()
            if len(request_line) != 3:
                send_error(conn, 400, "Bad Request", {})
                break

            method, path, http_version = request_line

            # 只处理GET和HEAD方法
            if method not in ['GET', 'HEAD']:
                send_error(conn, 501, "Not Implemented", {})
                break

            # 解析请求路径
            parsed_path = urlparse(path).path
            decoded_path = unquote(parsed_path)
            full_path = os.path.abspath(os.path.join(ROOT_DIR, decoded_path.lstrip('/')))

            # 安全路径检查
            if not full_path.startswith(ROOT_DIR):
                send_403(conn, {})
                break

            # 处理目录请求（自动查找index.html）
            if os.path.isdir(full_path):
                full_path = os.path.join(full_path, 'index.html')
                if not os.path.exists(full_path):
                    send_403(conn, {})
                    break

            # 检查文件是否存在
            if not os.path.exists(full_path):
                send_404(conn, {})
                break

            # 解析请求头
            headers = {}
            for line in request_lines[1:]:
                if not line:
                    break
                key, _, value = line.partition(':')
                headers[key.strip().lower()] = value.strip()

            # 设置keep_alive
            connection_header = headers.get('connection', '').lower()
            headers['keep_alive'] = False
            if http_version == 'HTTP/1.1':
                headers['keep_alive'] = connection_header != 'close'
            else:
                headers['keep_alive'] = connection_header == 'keep-alive'
            keep_alive = headers['keep_alive']

            # 处理文件请求
            handle_file_request(conn, method, full_path, headers)

        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            send_500(conn, {})
            break

    print(f"[CLOSING CONNECTION] Closing connection to {addr}")
    conn.close()

# --- Main Server Function ---
def start_server():
    """Starts the multi-threaded web server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((HOST, PORT))
    except (socket.error, OverflowError) as e:
        print(f"[BIND ERROR] {e}")
        return

    server_socket.listen(5)
    print(f"[LISTENING] Server is listening on {HOST}:{PORT}")

    try:
        while True:
            conn, addr = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("\n[SERVER SHUTDOWN] Shutting down server...")
    finally:
        server_socket.close()
        print("[SERVER STOPPED]")

if __name__ == "__main__":
    # 创建www目录（如果不存在）
    if not os.path.exists(ROOT_DIR):
        os.makedirs(ROOT_DIR)
        print(f"[INFO] Created root directory at {ROOT_DIR}")
    start_server()