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

from conversation import Conversation

STATE = Path("/tmp/cloud-browser/jobs")
MAX_SECONDS = 240
MODELS = {"gpt-6.1-sol": "GPT-6.1 Sol", "gpt-5.6-terra": "GPT-5.6 Terra"}
DEFAULT_MODEL = "gpt-6.1-sol"


def default_model():
    configured = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    return configured if configured in MODELS else DEFAULT_MODEL


def cdp_ready():
    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=2) as response:
            return bool(json.load(response).get("webSocketDebuggerUrl"))
    except (OSError, ValueError):
        return False


class Jobs:
    def __init__(self, conversation=None):
        self.conversation = conversation or Conversation()
        for turn in self.conversation.data["turns"]:
            if turn["state"] == "running":
                turn["state"] = "interrupted"
                self.conversation.save()
        self.lock = threading.RLock()
        self.process = None
        self.job_id = None
        self.started = 0
        self.state = "idle"
        self.message = "Bereit für einen Rechercheauftrag."
        self.model = None

    def details(self):
        if not self.job_id:
            return {}
        try:
            return json.loads((STATE / (self.job_id + ".json")).read_text())
        except (OSError, ValueError):
            return {}

    def harvest(self):
        details = self.details()
        if self.job_id and self.state == "running":
            self.conversation.update(self.job_id, **{k: v for k, v in details.items()
                                                   if k in ("state", "result", "page", "progress")})
        if self.state == "running":
            if details.get("state") in ("done", "error"):
                self.state = details["state"]
                self.message = details.get("message", "Auftrag beendet.")
            elif self.process and self.process.poll() is not None:
                self.state, self.message = "error", "Worker beendet. Der Verlauf bleibt erhalten."
                self.conversation.update(self.job_id, state="error", result=self.message)
        return details

    def terminate(self, state, message):
        with self.lock:
            self.harvest()
            if self.process and self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait()
                except ProcessLookupError:
                    pass
            if self.state == "running":
                self.state, self.message = state, message
                self.conversation.update(self.job_id, state=state, result=message)
            self.process = None

    def reset(self):
        with self.lock:
            self.terminate("stopped", "Neue Unterhaltung.")
            self.conversation.reset()
            self.job_id = None
            self.state, self.message = "idle", "Neue Unterhaltung. Der Browser bleibt geöffnet."

    def status(self):
        with self.lock:
            details = self.harvest()
            if self.state == "running" and time.monotonic() - self.started > MAX_SECONDS:
                self.terminate("stopped", "Zeitlimit von 4 Minuten erreicht.")
            return {"state": self.state,
                    "message": self.message if self.state == "stopped" else details.get("message", self.message),
                    "step": details.get("step", 0), "result": details.get("result", "") if self.state != "stopped" else "",
                    "key_configured": bool(os.environ.get("OPENAI_API_KEY")),
                    "model": self.model or default_model(),
                    "default_model": default_model(),
                    "models": [{"id": key, "label": label} for key, label in MODELS.items()],
                    "conversation_id": self.conversation.data["id"],
                    "turns": self.conversation.data["turns"],
                    "browser_connected": cdp_ready()}

    def start(self, task, model=None):
        with self.lock:
            model = default_model() if model is None else model
            if not isinstance(model, str) or model not in MODELS:
                raise ValueError("Bitte ein unterstütztes Modell auswählen.")
            self.harvest()
            if self.state == "running":
                raise ValueError("Ein Auftrag läuft bereits. Zuerst stoppen.")
            if not os.environ.get("OPENAI_API_KEY"):
                raise ValueError("OPENAI_API_KEY fehlt in den Railway-Servicevariablen.")
            if not cdp_ready():
                raise ValueError("Der sichtbare Browser ist noch nicht bereit.")
            self.job_id = uuid.uuid4().hex
            STATE.mkdir(parents=True, exist_ok=True)
            for old in STATE.glob("*.json"):
                old.unlink()
            self.conversation.start(task, model, self.job_id)
            if not self.process or self.process.poll() is not None:
                self.process = subprocess.Popen(
                    [sys.executable, str(Path(__file__).with_name("agent_worker.py"))],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    text=True, start_new_session=True, env=dict(os.environ))
            self.model = model
            payload = {"task": task, "model": model, "job_id": self.job_id,
                       "conversation_id": self.conversation.data["id"],
                       "context": self.conversation.context()}
            try:
                self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                self.process.stdin.flush()
            except (OSError, ValueError):
                self.state = "error"
                self.conversation.update(self.job_id, state="error", result="Worker-Verbindung fehlgeschlagen. Bitte erneut versuchen.")
                raise ValueError("Worker-Verbindung fehlgeschlagen. Bitte erneut versuchen.")
            self.started = time.monotonic()
            self.state, self.message = "running", "Browser Use recherchiert …"
            threading.Thread(target=self.watch, args=(self.job_id,), daemon=True).start()

    def watch(self, job_id):
        while True:
            time.sleep(0.5)
            with self.lock:
                if self.job_id != job_id or self.state != "running":
                    return
                self.harvest()
                if self.state == "running" and time.monotonic() - self.started > MAX_SECONDS:
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
                JOBS.start(task.strip(), data.get("model"))
            elif self.path == "/api/reset":
                JOBS.reset()
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
