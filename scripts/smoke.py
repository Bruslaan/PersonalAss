"""Check deployed HTTP auth and a real WebSocket -> VNC RFB greeting."""
import base64
import getpass
import hashlib
import os
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


def main():
    parsed = urllib.parse.urlsplit(sys.argv[1] if len(sys.argv) == 2 else "")
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment):
        raise SystemExit("Usage: python3 scripts/smoke.py https://YOUR-DOMAIN")
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"):
        raise SystemExit("Use HTTPS except for a local loopback test")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    user = os.environ.get("VIEW_USERNAME") or input("View username: ")
    password = os.environ.get("VIEW_PASSWORD") or getpass.getpass("View password: ")
    auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()

    def status(path, headers=None):
        try:
            with urllib.request.urlopen(urllib.request.Request(origin + path, headers=headers or {}), timeout=15) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    for path in ("/", "/vnc.html", "/app/ui.js"):
        assert status(path) == 401, f"Unauthenticated {path} not rejected"
    assert status("/vnc.html", {"Authorization": "Basic aW52YWxpZDppbnZhbGlk"}) == 401
    assert status("/healthz") == 200, "Desktop not ready"
    assert status("/", {"Authorization": auth}) == 200
    assert status("/vnc.html", {"Authorization": auth}) == 200
    assert status("/websockify", {"Origin": origin}) == 401
    assert status("/websockify", {"Origin": "https://other.invalid", "Authorization": auth}) == 403
    # CDP is disabled; these paths must never return a debugging endpoint.
    assert status("/json/version", {"Authorization": auth}) == 404
    key = base64.b64encode(os.urandom(16)).decode()
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    with socket.create_connection((parsed.hostname, port), timeout=15) as raw:
        conn = ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname) if parsed.scheme == "https" else raw
        with conn:
            request = (f"GET /websockify HTTP/1.1\r\nHost: {parsed.netloc}\r\nOrigin: {origin}\r\n"
                       f"Authorization: {auth}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                       f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                       "Sec-WebSocket-Protocol: binary\r\n\r\n")
            conn.sendall(request.encode())
            with conn.makefile("rb") as stream:
                assert b" 101 " in stream.readline(), "WebSocket upgrade failed"
                headers = {}
                while True:
                    line = stream.readline()
                    if line == b"\r\n":
                        break
                    if not line:
                        raise AssertionError("Incomplete upgrade")
                    name, value = line.decode().split(":", 1)
                    headers[name.lower()] = value.strip()
                expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                assert headers.get("sec-websocket-accept") == expected
                greeting = b""
                while len(greeting) < 12:
                    frame = stream.read(2)
                    assert len(frame) == 2, "No VNC greeting"
                    opcode, length = frame[0] & 15, frame[1] & 127
                    assert not frame[1] & 128, "Unexpected server masking"
                    if length == 126:
                        length = int.from_bytes(stream.read(2), "big")
                    elif length == 127:
                        length = int.from_bytes(stream.read(8), "big")
                    assert length <= 65536, "Unexpected frame size"
                    payload = stream.read(length)
                    assert opcode in (0, 2), "Expected binary VNC stream"
                    greeting += payload
                assert greeting.startswith(b"RFB "), "Not a VNC server"
    print("PASS: auth, origin protection, health, WebSocket upgrade and VNC greeting")


if __name__ == "__main__":
    main()
