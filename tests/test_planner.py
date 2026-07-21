from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from verified_sandbox.planner import generate_plan


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class PlannerTests(unittest.TestCase):
    def test_configured_model_path_is_used_and_validated(self):
        payload = {"choices": [{"message": {"content": json.dumps({
            "capability": "restart_sandbox_worker",
            "target": "synthetic.local.worker",
            "reasoning": "fresh heartbeat is required",
            "steps": ["inspect_worker", "restart_sandbox_worker"],
            "verification": {"healthy": True},
            "risk": "sandbox_only",
        })}}]}
        inspection = {"target": "synthetic.local.worker", "healthy": False}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}), patch("urllib.request.urlopen", return_value=_Response(payload)) as urlopen:
            plan = generate_plan({"title": "synthetic alert"}, inspection)
        self.assertEqual(plan["source"], "openai")
        self.assertEqual(plan["capability"], "restart_sandbox_worker")
        self.assertIn("test-model", urlopen.call_args.args[0].data.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
