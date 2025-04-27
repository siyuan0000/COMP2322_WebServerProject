import socket
import threading

# --- Configuration ---
HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 8080        # Port to listen on (non-privileged ports are > 1023)
BUFFER_SIZE = 1024 # Size of the buffer for receiving data

# --- Client Handler Function ---
def handle_client(conn, addr):
    """Handles a single client connection."""
    print(f"[NEW CONNECTION] {addr} connected.")

    try:
        # Receive the request data from the client
        request_data = conn.recv(BUFFER_SIZE)
        if not request_data:
            print(f"[CONNECTION CLOSED] Connection from {addr} closed prematurely.")
            return # Exit if no data received

        # Decode and print the raw HTTP request
        # For Phase 1, we just display the request
        print(f"--- Received Request from {addr} ---")
        print(request_data.decode('utf-8'))
        print("------------------------------------")

        # --- Placeholder for Phase 2: Response Generation ---
        # In the next phase, you would parse the request_data here,
        # determine the requested file, build an HTTP response,
        # and send it back using conn.sendall()
        # For now, we just acknowledge receipt on the server side.

    except socket.error as e:
        print(f"[SOCKET ERROR] Error handling client {addr}: {e}")
    except Exception as e:
        print(f"[ERROR] Unexpected error handling client {addr}: {e}")
    finally:
        # Clean up the connection
        print(f"[CLOSING CONNECTION] Closing connection to {addr}")
        conn.close()

# --- Main Server Function ---
def start_server():
    """Starts the multi-threaded web server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Allow reusing the address (helpful for quick restarts)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        # Bind the socket to the host and port
        server_socket.bind((HOST, PORT))
    except socket.error as e:
        print(f"[BIND ERROR] Failed to bind to {HOST}:{PORT} - {e}")
        print("Check if another service is running on this port.")
        return # Exit if binding fails
    except OverflowError:
         print(f"[BIND ERROR] Port number {PORT} is likely out of the valid range (0-65535).")
         return

    # Start listening for incoming connections
    # The number (e.g., 5) is the backlog - max number of queued connections
    server_socket.listen(5)
    print(f"[LISTENING] Server is listening on {HOST}:{PORT}")

    # --- Main Server Loop ---
    while True:
        try:
            # Accept a new connection
            # conn is a new socket object usable to send/receive data on the connection
            # addr is the address bound to the socket on the other end of the connection
            conn, addr = server_socket.accept()

            # Create a new thread to handle the client connection
            # Pass the connection socket and address to the handler function
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.daemon = True # Allows main program to exit even if threads are running
            client_thread.start()

            # Print active thread count (optional, for monitoring)
            # print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

        except KeyboardInterrupt:
            print("\n[SERVER SHUTDOWN] Shutting down server...")
            break
        except socket.error as e:
            print(f"[ACCEPT ERROR] Error accepting connection: {e}")
            # Consider whether to continue or break based on the error

    # Close the server socket when the loop breaks (e.g., on KeyboardInterrupt)
    server_socket.close()
    print("[SERVER STOPPED]")

# --- Start the Server ---
if __name__ == "__main__":
    start_server()