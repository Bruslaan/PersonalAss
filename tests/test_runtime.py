import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("runtime", Path(__file__).parents[1] / "app/runtime.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class RuntimeTests(unittest.TestCase):
    def test_reject_missing_or_unsafe_credentials(self):
        for env in ({}, {"VIEW_USERNAME": "a:b", "VIEW_PASSWORD": "x" * 30},
                    {"VIEW_USERNAME": "owner", "VIEW_PASSWORD": "short"},
                    {"VIEW_USERNAME": "owner", "VIEW_PASSWORD": "x" * 73},
                    {"VIEW_USERNAME": "owner", "VIEW_PASSWORD": "x" * 20 + "\n"}):
            with self.assertRaises(ValueError):
                runtime.config(env)

    def test_port_validation(self):
        env = {"VIEW_USERNAME": "owner", "VIEW_PASSWORD": "x" * 24}
        self.assertEqual(runtime.config(env)[2], 8080)
        for port in ("5900", "6080", "8091", "80", "65536", "8080;bad"):
            with self.assertRaises(ValueError):
                runtime.config(dict(env, PORT=port))

    def test_secrets_not_inherited_and_shutdown(self):
        desktop = runtime.Desktop()
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "ready"
            try:
                with patch.dict(runtime.os.environ, VIEW_PASSWORD="private-value", VIEW_USERNAME="owner"):
                    desktop.launch("child", [sys.executable, "-c",
                        "import os,time,pathlib,sys; assert 'VIEW_PASSWORD' not in os.environ; "
                        "assert 'VIEW_USERNAME' not in os.environ; pathlib.Path(sys.argv[1]).touch(); time.sleep(30)", str(marker)])
                deadline = time.monotonic() + 5
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(marker.exists(), "Child did not confirm secret isolation")
                self.assertFalse(desktop.ready())
            finally:
                desktop.shutdown()
            self.assertIsNotNone(desktop.processes["child"].poll())

    def test_dead_child_is_unhealthy(self):
        desktop = runtime.Desktop()
        process = subprocess.Popen([sys.executable, "-c", "pass"])
        process.wait(timeout=5)
        desktop.processes["child"] = process
        desktop.started = True
        self.assertFalse(desktop.ready())


if __name__ == "__main__":
    unittest.main()
