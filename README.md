# Simple Multi-threaded HTTP Server

## Overview

This project implements a modular, multi-threaded HTTP server in Python.  
It supports:
- GET and HEAD methods
- Persistent and non-persistent connections
- Last-Modified and If-Modified-Since handling
- Six HTTP status codes: 200 OK, 304 Not Modified, 400 Bad Request, 403 Forbidden, 404 Not Found, 415 Unsupported Media Type
- Thread-safe request logging to `server.log`

A simple client script is provided for manual and concurrent testing.

## Project Structure

```
COMP2322_WebServerProject-main/
├── client.py          # Client script for manual and batch tests
├── README.md          # Project documentation
├── server.log         # Generated log file
├── server_simple.py   # Basic server version
├── serverPro.py       # Full-featured server
├── serverFinal.py  # Full-featured multi-threaded server
├── www/               # Web root directory
│   ├── index.html                 # Home page with navigation links
│   ├── ink_vis_r123_bt123.html     # Chart 1 page linked from index.html
│   └── Leaderboard.PNG             # Image embedded in index.html
```

## Running the Server

Start the server by running:

```bash
python serverFinal.py
```

The server listens on `http://localhost:8080/` and automatically creates the `www/` directory if it does not exist.

## Webpage Behavior

- Access `http://localhost:8080/index.html` to view the homepage.
- Clicking **"Chart 1"** on the homepage navigates to `ink_vis_r123_bt123.html`
- 
## Using the Client

### Single Request

Send a single request manually:

```bash
python client.py [METHOD] [PATH]
```

Example:

```bash
python client.py GET /index.html
```

### Batch Testing

Run predefined tests for all key features:

```bash
python client.py batch
```

Tests include:
- 200 OK (normal file retrieval)
- 304 Not Modified (conditional GET)
- 400 Bad Request (unsupported method)
- 403 Forbidden (directory traversal attempt)
- 404 Not Found (missing file)
- 415 Unsupported Media Type (unknown file extension)

### Concurrent Testing

To simulate multiple clients and verify server multi-threading:

```bash
python client.py concurrent [number_of_clients]
```

Example:

```bash
python client.py concurrent 10
```

This launches 10 simultaneous clients sending GET requests to `/index.html`.

## Log File

Each request is recorded in `server.log`, including:
- Timestamp
- Client address
- Request line
- Response status code

Example log entry:

```
2025-04-27 14:10:02 - 127.0.0.1:50123 - "GET /index.html HTTP/1.1" - 200 OK
```

Logs are written in a thread-safe manner to ensure consistency under concurrent access.

## Notes

- Only files inside the `www/` directory are served.
- Directory listing is forbidden; only direct file requests are supported.
- Error responses include simple HTML error pages.
- The server automatically handles persistent connections according to HTTP/1.1 standards.
