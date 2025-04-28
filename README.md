# Simple Multi-threaded HTTP Server

## Overview

This project implements a modular, multi-threaded HTTP server in Python.  
It supports:
- GET and HEAD methods
- Persistent and non-persistent connections
- Last-Modified and If-Modified-Since handling
- Six HTTP status codes: 200, 304, 400, 403, 404, 415
- Request logging to `server.log`

A simple client script is provided for manual and batch testing.
## Running the Server

```bash
python server.py
```
The server listens on http://localhost:8080/ and creates the www/ directory if missing.

## Using the Client
### Single Request
```bash
python client.py [METHOD] [PATH]
```
### Example:
```bash
python client.py GET /index.html
```
### Batch Testing
```bash
python client.py batch
```
Covers:
- 200 OK
- 304 Not Modified
- 400 Bad Request
- 403 Forbidden
- 404 Not Found
- 415 Unsupported Media Type


## Log File

Each request is logged in `server.log` with timestamp, client address, request line, and response status.

Example log entry:

```
2025-04-27 14:10:02 - 127.0.0.1:50123 - "GET /index.html HTTP/1.1" - 200 OK
```

## Notes

- Only files inside `www/` are served.
- Directory listing is forbidden.
- Error responses return minimal HTML pages.
- Persistent connections follow HTTP/1.1 standards.

