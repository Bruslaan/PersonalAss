"""Authenticated by Nginx; loopback only. One cancellable job at a time."""
import http.server
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid

STATE = Path("/tmp/cloud-browser/jobs")
MAX_SECONDS = 240


def cdp_ready():
    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=2) as response:
            return bool(json.load(response).get("webSocketDebuggerUrl"))
    except (OSError, ValueError):
        return False


class Jobs:
    def __init__(self):
        self.lock = threading.RLock()
        self.process = None
        self.job_id = None
        self.started = 0
        self.state = "idle"
        self.message = "Bereit für einen Rechercheauftrag."

    def terminate(self, state, message):
        with self.lock:
            if self.process and self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait()
                except ProcessLookupError:
                    pass
                self.state, self.message = state, message

    def status(self):
        with self.lock:
            if self.process and self.state == "running":
                if time.monotonic() - self.started > MAX_SECONDS:
                    self.terminate("stopped", "Zeitlimit von 4 Minuten erreicht.")
                elif self.process.poll() is not None:
                    self.state = "done" if self.process.returncode == 0 else "error"
                    self.message = "Auftrag beendet." if self.state == "done" else "Auftrag fehlgeschlagen."
            details = {}
            if self.job_id and self.state != "stopped":
                try:
                    details = json.loads((STATE / (self.job_id + ".json")).read_text())
                except (OSError, ValueError):
                    pass
            return {"state": self.state, "message": details.get("message", self.message),
                    "step": details.get("step", 0), "result": details.get("result", ""),
                    "key_configured": bool(os.environ.get("OPENAI_API_KEY")),
                    "model": os.environ.get("OPENAI_MODEL", "gpt-5.6-terra"),
                    "browser_connected": cdp_ready()}

    def start(self, task):
        with self.lock:
            if self.process and self.process.poll() is None:
                raise ValueError("Ein Auftrag läuft bereits. Zuerst stoppen.")
            if not os.environ.get("OPENAI_API_KEY"):
                raise ValueError("OPENAI_API_KEY fehlt in den Railway-Servicevariablen.")
            if not cdp_ready():
                raise ValueError("Der sichtbare Browser ist noch nicht bereit.")
            self.job_id = uuid.uuid4().hex
            STATE.mkdir(parents=True, exist_ok=True)
            for old in STATE.glob("*.json"):
                old.unlink()
            self.process = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("agent_worker.py")), self.job_id],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                text=True, start_new_session=True)
            self.process.stdin.write(task)
            self.process.stdin.close()
            self.started = time.monotonic()
            self.state, self.message = "running", "Browser Use recherchiert …"
            threading.Thread(target=self.watch, args=(self.process,), daemon=True).start()

    def watch(self, process):
        try:
            process.wait(timeout=MAX_SECONDS)
        except subprocess.TimeoutExpired:
            with self.lock:
                if self.process is process:
                    self.terminate("stopped", "Zeitlimit von 4 Minuten erreicht.")


JOBS = Jobs()


class Handler(http.server.BaseHTTPRequestHandler):
    def reply(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            self.reply(200, JOBS.status())
        else:
            self.reply(404, {"error": "Unbekannter Endpunkt."})

    def do_POST(self):
        origin = urllib.parse.urlsplit(self.headers.get("Origin", ""))
        if (origin.scheme not in ("http", "https") or origin.netloc != self.headers.get("Host")
                or self.headers.get("X-Cloud-Browser") != "1"):
            self.reply(403, {"error": "Ungültige Anfrage-Origin."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8192:
                raise ValueError("Ungültige Auftragsgröße.")
            self.connection.settimeout(5)
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("JSON-Objekt erforderlich.")
            if self.path == "/api/start":
                task = data.get("task", "")
                if not isinstance(task, str) or not 1 <= len(task.strip()) <= 2000:
                    raise ValueError("Bitte einen Auftrag mit höchstens 2000 Zeichen eingeben.")
                JOBS.start(task.strip())
            elif self.path == "/api/stop":
                JOBS.terminate("stopped", "Auftrag gestoppt. Der Browser bleibt geöffnet.")
            else:
                self.reply(404, {"error": "Unbekannter Endpunkt."})
                return
            self.reply(200, JOBS.status())
        except (ValueError, OSError, socket.timeout) as error:
            self.reply(400, {"error": str(error)})

    def log_message(self, *args):
        pass


def main():
    os.umask(0o077)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 8092), Handler)
    def shutdown(*_):
        JOBS.terminate("stopped", "Service wird neu gestartet.")
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
