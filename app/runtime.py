"""Small fail-fast desktop supervisor. No third-party Python dependencies."""
import http.server
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import threading
import time


def config(env):
    username = env.get("VIEW_USERNAME", "")
    password = env.get("VIEW_PASSWORD", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", username):
        raise ValueError("VIEW_USERNAME: 1–64 letters, digits, _ or - required")
    if not 20 <= len(password.encode()) <= 72 or any(c in password for c in "\r\n\x00"):
        raise ValueError("VIEW_PASSWORD: 20–72 UTF-8 bytes, no newline/NUL required")
    port = int(env.get("PORT", "8080"))
    if not 1024 <= port <= 65535 or port in (5900, 6080, 8091, 8092, 9222):
        raise ValueError("PORT must be an available port between 1024 and 65535")
    return username, password, port


def render_nginx(port):
    return Path(__file__).with_name("nginx.conf.template").read_text().replace("@@PORT@@", str(port))


class Desktop:
    def __init__(self):
        self.processes = {}
        self.stop = threading.Event()
        self.started = False

    def launch(self, name, args):
        # Secrets are used only to generate htpasswd, never inherited by web content.
        env = {k: v for k, v in os.environ.items()
               if k not in ("VIEW_PASSWORD", "VIEW_USERNAME")
               and not any(word in k.upper() for word in ("API_KEY", "TOKEN", "SECRET", "PASSWORD"))}
        if name == "agent-api" and os.environ.get("OPENAI_API_KEY"):
            env["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
        env["ANONYMIZED_TELEMETRY"] = "false"
        env["BROWSER_USE_LOGGING_LEVEL"] = "error"
        self.processes[name] = subprocess.Popen(args, env=env, start_new_session=True)
        print(f"Started {name}", flush=True)

    def ready(self):
        if not self.started or self.stop.is_set() or any(p.poll() is not None for p in self.processes.values()):
            return False
        try:
            for port in (5900, 6080, 8092, 9222):
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    pass
            visible = subprocess.run(
                ["xdotool", "search", "--onlyvisible", "--class", "chromium"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            return visible.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def shutdown(self):
        self.stop.set()
        # Give Chromium time to flush its profile while X is still alive.
        for name in reversed(list(self.processes)):
            process = self.processes[name]
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=8 if name == "chromium" else 2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                except ProcessLookupError:
                    pass


def health_server(desktop):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/healthz":
                self.send_error(404)
                return
            ready = desktop.ready()
            body = b"ready\n" if ready else b"starting or unhealthy\n"
            self.send_response(200 if ready else 503)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return http.server.ThreadingHTTPServer(("127.0.0.1", 8091), Handler)


def main():
    os.umask(0o077)
    username, password, port = config(os.environ)
    state = Path("/tmp/cloud-browser")
    state.mkdir(exist_ok=True)
    for folder in ("body", "proxy"):
        (state / folder).mkdir(exist_ok=True)
    subprocess.run(["htpasswd", "-i", "-B", "-c", str(state / "htpasswd"), username],
                   input=password + "\n", text=True, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    del password
    os.environ.pop("VIEW_PASSWORD", None)
    (state / "nginx.conf").write_text(render_nginx(port))
    subprocess.run(["nginx", "-t", "-c", str(state / "nginx.conf")], check=True)
    profile = Path("/data/profile")
    # Only one replica may use this profile. Hostname changes leave stale locks.
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        (profile / name).unlink(missing_ok=True)
    desktop = Desktop()
    signal.signal(signal.SIGTERM, lambda *_: desktop.stop.set())
    signal.signal(signal.SIGINT, lambda *_: desktop.stop.set())
    server = health_server(desktop)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        desktop.launch("xvfb", ["Xvfb", ":99", "-screen", "0", "1280x800x24", "-nolisten", "tcp"])
        for _ in range(100):
            if desktop.stop.is_set():
                return 0
            if desktop.processes["xvfb"].poll() is not None:
                raise RuntimeError("Xvfb exited during startup")
            if subprocess.run(["xdpyinfo"], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=2).returncode == 0:
                break
            desktop.stop.wait(0.1)
        else:
            raise RuntimeError("X display did not become ready")
        desktop.launch("openbox", ["openbox", "--sm-disable"])
        desktop.launch("vnc", ["x11vnc", "-display", ":99", "-listen", "127.0.0.1",
                               "-rfbport", "5900", "-forever", "-shared", "-nopw", "-noxdamage", "-quiet"])
        desktop.launch("websockify", ["websockify", "--heartbeat=30", "127.0.0.1:6080", "127.0.0.1:5900"])
        desktop.launch("nginx", ["nginx", "-c", str(state / "nginx.conf")])
        desktop.launch("chromium", ["chromium", "--no-sandbox", "--disable-dev-shm-usage",
                                    "--no-first-run", "--no-default-browser-check",
                                    "--password-store=basic", "--user-data-dir=/data/profile",
                                    "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=9222",
                                    "--disk-cache-size=104857600", "--window-size=1280,800",
                                    "--start-maximized", "https://example.com"])
        desktop.launch("agent-api", ["/opt/agent-venv/bin/python", "/app/agent_api.py"])
        desktop.started = True
        while not desktop.stop.wait(0.5):
            for name, process in desktop.processes.items():
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited ({process.returncode}); restart required")
        return 0
    finally:
        desktop.shutdown()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
