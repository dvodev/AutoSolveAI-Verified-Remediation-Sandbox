from __future__ import annotations

import tempfile
import unittest

from verified_sandbox.engine import RemediationEngine
from verified_sandbox.orchestrator import EventBus, RemediationOrchestrator, WorkflowDefinition


class OrchestratorTests(unittest.TestCase):
    def test_workflow_definition_describes_controls(self):
        names = [step["name"] for step in WorkflowDefinition().describe()]
        self.assertEqual(names[:4], ["ingest", "inspect", "plan", "policy"])
        self.assertIn("verify", names)

    def test_event_bus_supports_specific_and_wildcard_subscribers(self):
        bus = EventBus(); names = []
        bus.subscribe("specific", lambda event: names.append("specific:" + event.name))
        bus.subscribe("*", lambda event: names.append("all:" + event.name))
        bus.publish("specific", "r1")
        self.assertEqual(names, ["specific:specific", "all:specific"])
        self.assertEqual(len(bus.export("r1")), 1)

    def test_orchestrator_runs_shadow_without_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = RemediationOrchestrator(RemediationEngine(directory))
            try:
                result = orchestrator.dry_run({"scenario": "stale_heartbeat"})
                self.assertEqual(result["status"], "shadowed")
                self.assertTrue(orchestrator.export_run(result["run_id"])["audit_chain"]["valid"])
            finally:
                orchestrator.close()

    def test_orchestrator_runs_approval_workflow_and_emits_events(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = RemediationOrchestrator(RemediationEngine(directory))
            try:
                result = orchestrator.run_to_completion({"scenario": "stale_heartbeat"}, actor="test-user")
                self.assertEqual(result["status"], "verified")
                names = [item["name"] for item in orchestrator.bus.export(result["run_id"])]
                self.assertEqual(names, ["alert.received", "plan.generated", "approval.recorded", "execution.completed"])
            finally:
                orchestrator.close()

    def test_orchestrator_normalizes_datadog_source(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = RemediationOrchestrator(RemediationEngine(directory))
            try:
                run = orchestrator.ingest({"id": "d1", "title": "stale", "text": "bad", "tags": ["service:checkout"], "scenario": "stale_heartbeat"}, source="datadog")
                self.assertEqual(run["alert"]["source"], "datadog")
            finally:
                orchestrator.close()

    def test_audit_chain_continues_after_engine_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            first = RemediationOrchestrator(RemediationEngine(directory))
            try:
                first.run_to_completion({"scenario": "healthy_signal"})
            finally:
                first.close()
            second = RemediationOrchestrator(RemediationEngine(directory))
            try:
                second.run_to_completion({"scenario": "healthy_signal"})
                self.assertTrue(second.engine.events.verify_chain()["valid"])
            finally:
                second.close()


if __name__ == "__main__":
    unittest.main()
