from __future__ import annotations

import unittest

from verified_sandbox.metrics import MetricsRegistry
from verified_sandbox.security import PlanSigner, authorize_payload, inspect_text, validate_url


class SecurityMetricsTests(unittest.TestCase):
    def test_command_gate_blocks_unsafe_shell(self):
        decision = authorize_payload({"script": "rm -rf /"})
        self.assertFalse(decision.allowed)
        self.assertTrue(any(item.rule == "unsafe_command_shape" for item in decision.findings))

    def test_gate_blocks_literal_secret_and_non_sandbox(self):
        self.assertFalse(authorize_payload({"token": "abc"}).allowed)
        self.assertFalse(authorize_payload({}, target_environment="production").allowed)

    def test_url_gate_is_allowlist_aware(self):
        self.assertTrue(validate_url("https://example.test", allowed_hosts={"example.test"}).allowed)
        self.assertFalse(validate_url("file:///etc/passwd").allowed)

    def test_plan_signer_detects_tampering(self):
        signer = PlanSigner(b"test-key"); plan = {"capability": "observe_only", "target": "synthetic.local.worker"}; signature = signer.sign(plan)
        self.assertTrue(signer.verify(plan, signature))
        self.assertFalse(signer.verify({**plan, "target": "other"}, signature))

    def test_metrics_snapshot_and_prometheus(self):
        metrics = MetricsRegistry(); metrics.counter("runs_total", "runs").inc(labels={"status": "verified"}); metrics.gauge("health", "health").set(1)
        self.assertIn("runs_total", metrics.prometheus())
        self.assertEqual(metrics.snapshot()["counters"][0]["values"][0]["value"], 1)


if __name__ == "__main__":
    unittest.main()
