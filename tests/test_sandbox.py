from __future__ import annotations

import tempfile
import unittest

from verified_sandbox.engine import RemediationEngine
from verified_sandbox.planner import _validate


class SandboxWorkflowTests(unittest.TestCase):
    def test_full_alert_approval_execution_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = RemediationEngine(directory)
            try:
                run = engine.create_alert()
                self.assertEqual(run["status"], "alerted")
                run = engine.plan(run["run_id"])
                self.assertIn(run["plan"]["capability"], {"restart_sandbox_worker", "terminate_sandbox_worker"})
                run = engine.approve(run["run_id"])
                run = engine.execute(run["run_id"])
                self.assertEqual(run["status"], "verified")
                self.assertTrue(run["result"]["verification"]["healthy"])
                events = [line for line in engine.audit_path.read_text(encoding="utf-8").splitlines() if line]
                self.assertGreaterEqual(len(events), 4)
            finally:
                engine.close()

    def test_execution_requires_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = RemediationEngine(directory)
            try:
                run = engine.create_alert()
                run = engine.plan(run["run_id"])
                with self.assertRaises(ValueError):
                    engine.execute(run["run_id"])
            finally:
                engine.close()

    def test_unknown_capability_is_rejected(self):
        with self.assertRaises(ValueError):
            _validate({"capability": "restart_a_real_server", "target": "synthetic.local.worker"}, {"target": "synthetic.local.worker"})

    def test_shadow_mode_never_changes_the_target(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = RemediationEngine(directory)
            try:
                run = engine.create_alert({"scenario": "stale_heartbeat", "mode": "shadow"})
                run = engine.plan(run["run_id"])
                before = run["inspection"]["pid"]
                run = engine.execute(run["run_id"])
                self.assertEqual(run["status"], "shadowed")
                self.assertEqual(run["verification"]["pid"], before)
                self.assertEqual(run["result"]["status"], "SHADOW_ONLY")
            finally:
                engine.close()

    def test_healthy_signal_selects_observe_only(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = RemediationEngine(directory)
            try:
                run = engine.create_alert({"scenario": "healthy_signal"})
                run = engine.plan(run["run_id"])
                self.assertEqual(run["plan"]["capability"], "observe_only")
                run = engine.approve(run["run_id"])
                run = engine.execute(run["run_id"])
                self.assertEqual(run["status"], "verified")
            finally:
                engine.close()

    def test_audit_replay_has_hash_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = RemediationEngine(directory)
            try:
                run = engine.create_alert()
                replay = engine.replay(run["run_id"])
                self.assertTrue(replay[0]["hash"])
                self.assertEqual(replay[0]["previous_hash"], "0" * 64)
            finally:
                engine.close()


if __name__ == "__main__":
    unittest.main()
