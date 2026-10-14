import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))

spec = importlib.util.spec_from_file_location("agent_api", Path(__file__).parents[1] / "app/agent_api.py")
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path_patch = patch("conversation.PATH", Path(self.directory.name) / "conversation.json")
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.server = api.http.server.ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def post(self, data, origin=None, custom=True, path="/api/start"):
        headers = {"Content-Type": "application/json", "Origin": origin or self.origin}
        if custom:
            headers["X-Cloud-Browser"] = "1"
        request = urllib.request.Request(self.origin + path, data=json.dumps(data).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    def test_csrf_rejected_before_start(self):
        with patch.object(api.JOBS, "start") as start:
            self.assertEqual(self.post({"task": "test"}, origin="https://other.invalid"), 403)
            self.assertEqual(self.post({"task": "test"}, custom=False), 403)
            start.assert_not_called()

    def test_reset_route_and_csrf(self):
        with patch.object(api.JOBS, "reset") as reset, patch.object(api.JOBS, "status", return_value={}):
            self.assertEqual(self.post({}, path="/api/reset", origin="https://other.invalid"), 403)
            reset.assert_not_called()
            self.assertEqual(self.post({}, path="/api/reset"), 200)
            reset.assert_called_once()

    def test_valid_request_missing_key(self):
        with patch.dict(api.os.environ, {}, clear=True):
            self.assertEqual(self.post({"task": "test"}), 400)

    def test_invalid_task_rejected(self):
        with patch.object(api.JOBS, "start") as start:
            self.assertEqual(self.post({"task": ""}), 400)
            self.assertEqual(self.post({"task": "x" * 2001}), 400)
            start.assert_not_called()

    def test_selected_model_reaches_job(self):
        with patch.object(api.JOBS, "start") as start, patch.object(api.JOBS, "status", return_value={}):
            self.assertEqual(self.post({"task": "test", "model": "gpt-6.1-sol"}), 200)
            start.assert_called_once_with("test", "gpt-6.1-sol")

    def test_unknown_model_rejected_without_worker(self):
        with patch.object(api.subprocess, "Popen") as worker:
            with self.assertRaisesRegex(ValueError, "Modell"):
                api.Jobs().start("test", "unknown")
            worker.assert_not_called()

    def test_selected_model_passed_to_worker_environment(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory, patch.object(api, "STATE", Path(directory)), \
                patch.dict(api.os.environ, {"OPENAI_API_KEY": "test-key"}), \
                patch.object(api, "cdp_ready", return_value=True), \
                patch.object(api.threading, "Thread"), patch.object(api.subprocess, "Popen") as worker:
            jobs = api.Jobs()
            jobs.start("test", "gpt-6.1-sol")
            payload = json.loads(worker.return_value.stdin.write.call_args.args[0])
            self.assertEqual(payload["model"], "gpt-6.1-sol")
            self.assertEqual(jobs.status()["model"], "gpt-6.1-sol")

    def test_stop_kills_worker_without_browser(self):
        jobs = api.Jobs()
        jobs.process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
        jobs.state = "running"
        process = jobs.process
        jobs.terminate("stopped", "stopped")
        self.assertIsNotNone(process.poll())
        self.assertEqual(jobs.state, "stopped")

    def test_duplicate_job_rejected(self):
        jobs = api.Jobs()
        jobs.process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
        jobs.state = "running"
        try:
            with self.assertRaises(ValueError):
                jobs.start("second")
        finally:
            jobs.terminate("stopped", "stopped")
