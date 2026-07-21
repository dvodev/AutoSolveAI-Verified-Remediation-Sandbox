from __future__ import annotations

import unittest

from verified_sandbox.evidence import compare_verification, diff, evidence_summary, flatten, parse_json_output, verify_snapshot
from verified_sandbox.models import Evidence


class EvidenceTests(unittest.TestCase):
    def test_flatten_and_diff_capture_nested_health_transition(self):
        before = {"process": {"pid": 1, "healthy": False}}
        after = {"process": {"pid": 2, "healthy": True}}
        self.assertEqual(flatten(before)["process.pid"], 1)
        changed = {item.key for item in diff(before, after) if item.changed}
        self.assertEqual(changed, {"process.healthy", "process.pid"})

    def test_json_output_parser_handles_json_and_plain_text(self):
        self.assertEqual(parse_json_output('{"ok":true}')["ok"], True)
        self.assertEqual(parse_json_output("plain output"), "plain output")

    def test_snapshot_verification_requires_identity_and_fresh_heartbeat(self):
        healthy = {"target": "synthetic.local.worker", "alive": True, "healthy": True, "status": "healthy", "heartbeat_age_seconds": 0.2}
        stale = {**healthy, "heartbeat_age_seconds": 8}
        self.assertTrue(verify_snapshot(healthy)["passed"])
        self.assertFalse(verify_snapshot(stale)["passed"])

    def test_compare_verification_exposes_pid_transition(self):
        result = compare_verification({"pid": 1, "healthy": False}, {"pid": 2, "healthy": True})
        self.assertTrue(result["pid_changed"])
        self.assertEqual(result["health_transition"], [False, True])

    def test_evidence_summary_groups_sources(self):
        values = [Evidence.create("inventory", "os", "Windows", "agent"), Evidence.create("log", "x", "y", "agent")]
        summary = evidence_summary(values)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["by_kind"]["inventory"], 1)


if __name__ == "__main__":
    unittest.main()
