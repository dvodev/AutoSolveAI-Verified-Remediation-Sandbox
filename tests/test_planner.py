from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from verified_sandbox.planner import generate_plan
from verified_sandbox.model_selection import clear_model_cache, resolve_model


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
    def tearDown(self):
        clear_model_cache()

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
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "gpt-5"}), patch("urllib.request.urlopen", return_value=_Response(payload)) as urlopen:
            plan = generate_plan({"title": "synthetic alert"}, inspection)
        self.assertEqual(plan["source"], "openai")
        self.assertEqual(plan["capability"], "restart_sandbox_worker")
        request_payload = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(request_payload["model"], "gpt-5")
        self.assertNotIn("temperature", request_payload)

    def test_model_selection_uses_available_frontier_model_without_printing_credentials(self):
        catalog = _Response({"data": [{"id": "gpt-5.6"}, {"id": "gpt-5"}]})
        with patch("urllib.request.urlopen", return_value=catalog):
            selected = resolve_model("test-key", "gpt-5.6")
        self.assertEqual(selected, "gpt-5.6")


if __name__ == "__main__":
    unittest.main()
