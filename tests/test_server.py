import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.server import create_server


class ServerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        (self.repo / "gtd.md").write_text(
            "# GTD\n\n## Next Actions\n\n- next: HTTP dispatch\n",
            encoding="utf-8",
        )
        self.server = create_server(self.repo, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        self.base_url = "http://127.0.0.1:{}".format(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tempdir.cleanup()

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_health_and_gtd_dispatch_are_available_over_http(self):
        status, health = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "ok")

        status, result = self.request("POST", "/gtd/dispatch", {})
        self.assertEqual(status, 200)
        self.assertEqual(result["moved"], 1)
        self.assertIn("gtd_path", result)

    def test_metrics_and_plan_are_available_over_http(self):
        status, metrics = self.request("GET", "/metrics?from=2026-01-01&to=2026-01-01")
        self.assertEqual(status, 200)
        self.assertEqual(metrics["task_count"], 0)

        status, plan = self.request("POST", "/sync/plan", {})
        self.assertEqual(status, 200)
        self.assertEqual(plan["actions"], 0)
        self.assertTrue(Path(plan["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
