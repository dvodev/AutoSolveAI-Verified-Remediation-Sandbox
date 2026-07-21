from __future__ import annotations

import tempfile
import unittest

from verified_sandbox.replay import BundleExporter, BundleValidator, compare_bundles, summarize_bundle
from verified_sandbox.simulation import ReplaySimulator, ScenarioRunner
from verified_sandbox.storage import JsonlStore


class SimulationReplayTests(unittest.TestCase):
    def test_scenario_matrix_covers_faults(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ScenarioRunner().matrix(["stale_heartbeat", "missing_process", "healthy_signal", "shadow_preview"], directory)
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["passed_count"], 4)

    def test_unknown_fault_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                ScenarioRunner().run("unknown", directory)

    def test_bundle_export_and_validator(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = ScenarioRunner(); result = runner.run("stale_heartbeat", directory + "/run")
            # The scenario runner closes the engine, so construct a minimal
            # durable event store for the portable bundle contract here.
            store = JsonlStore(directory + "/events.jsonl")
            import hashlib, json
            value = {"timestamp": 1, "run_id": result.run_id, "event": "complete", "previous_hash": "0" * 64}
            value["hash"] = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest(); store.append(value)
            bundle = BundleExporter(store).build(result.run)
            self.assertTrue(BundleValidator().validate(bundle.as_dict())["valid"])
            self.assertEqual(summarize_bundle(bundle.as_dict())["run_id"], result.run_id)

    def test_replay_comparison_reports_status(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = ScenarioRunner(); first = runner.run("stale_heartbeat", directory + "/a"); second = runner.run("healthy_signal", directory + "/b")
            comparison = ReplaySimulator().compare(first, second)
            self.assertFalse(comparison["same_scenario"])
            self.assertTrue(comparison["same_status"])


if __name__ == "__main__":
    unittest.main()
