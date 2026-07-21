from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from verified_sandbox.engine import RemediationEngine
from verified_sandbox.server import Handler


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = RemediationEngine(self.temp.name)
        Handler.engine = self.engine
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.engine.close()
        self.temp.cleanup()

    def call(self, path: str, method: str = "GET", body: dict | None = None):
        request = urllib.request.Request(
            self.base + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode())

    def test_scenario_and_capability_catalogs_are_public(self):
        self.assertEqual(len(self.call("/api/scenarios")), 3)
        self.assertGreaterEqual(len(self.call("/api/capabilities")), 3)

    def test_shadow_api_flow_skips_mutation(self):
        run = self.call("/api/alerts", "POST", {"scenario": "stale_heartbeat", "mode": "shadow"})
        run = self.call(f"/api/runs/{run['run_id']}/plan", "POST")
        run = self.call(f"/api/runs/{run['run_id']}/execute", "POST")
        self.assertEqual(run["status"], "shadowed")
        self.assertEqual(run["result"]["status"], "SHADOW_ONLY")

    def test_approval_flow_exposes_replay_and_chain_verification(self):
        run = self.call("/api/alerts", "POST", {"scenario": "stale_heartbeat"})
        run = self.call(f"/api/runs/{run['run_id']}/plan", "POST")
        with self.assertRaises(urllib.error.HTTPError):
            self.call(f"/api/runs/{run['run_id']}/execute", "POST")
        run = self.call(f"/api/runs/{run['run_id']}/approve", "POST")
        run = self.call(f"/api/runs/{run['run_id']}/execute", "POST")
        self.assertEqual(run["status"], "verified")
        self.assertGreaterEqual(len(self.call(f"/api/runs/{run['run_id']}/replay")), 3)
        self.assertTrue(self.call("/api/audit/verify")["valid"])


if __name__ == "__main__":
    unittest.main()
