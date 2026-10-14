import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("agent_api", Path(__file__).parents[1] / "app/agent_api.py")
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.server = api.http.server.ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def post(self, data, origin=None, custom=True):
        headers = {"Content-Type": "application/json", "Origin": origin or self.origin}
        if custom:
            headers["X-Cloud-Browser"] = "1"
        request = urllib.request.Request(self.origin + "/api/start", data=json.dumps(data).encode(), headers=headers)
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

    def test_valid_request_missing_key(self):
        with patch.dict(api.os.environ, {}, clear=True):
            self.assertEqual(self.post({"task": "test"}), 400)

    def test_invalid_task_rejected(self):
        with patch.object(api.JOBS, "start") as start:
            self.assertEqual(self.post({"task": ""}), 400)
            self.assertEqual(self.post({"task": "x" * 2001}), 400)
            start.assert_not_called()

    def test_stop_kills_worker_without_browser(self):
        jobs = api.Jobs()
        jobs.process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
        jobs.state = "running"
        jobs.terminate("stopped", "stopped")
        self.assertIsNotNone(jobs.process.poll())
        self.assertEqual(jobs.state, "stopped")

    def test_duplicate_job_rejected(self):
        jobs = api.Jobs()
        jobs.process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
        try:
            with self.assertRaises(ValueError):
                jobs.start("second")
        finally:
            jobs.terminate("stopped", "stopped")
