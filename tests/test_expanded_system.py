from __future__ import annotations

import tempfile
import unittest

from verified_sandbox.adapters import AwsEc2SimulatorAdapter, ServiceNowSimulatorAdapter
from verified_sandbox.capability_router import CapabilityRouter
from verified_sandbox.execution_runtime import ExecutionRuntime
from verified_sandbox.incident_intake import IncidentIntake, IncidentNormalizer
from verified_sandbox.engine import RemediationEngine
from verified_sandbox.models import Alert
from verified_sandbox.orchestrator import RemediationOrchestrator
from verified_sandbox.policy_engine import PolicyEngine, PolicyInput
from verified_sandbox.learning import LearningLedger, Outcome
from verified_sandbox.plan_envelope import ensure_envelope, validate_envelope
from verified_sandbox.verification_engine import CheckSpec, VerificationEngine
from verified_sandbox.runbook import RunbookExecutor, RunbookSynthesizer
from verified_sandbox.target_resolution import TargetResolver
from verified_sandbox.registry import load_capabilities


class ExpandedSystemTests(unittest.TestCase):
    def test_normalizer_supports_datadog_prometheus_and_servicenow_shapes(self):
        normalizer = IncidentNormalizer()
        values = [
            normalizer.normalize({"id": "d1", "title": "stale", "tags": ["service:checkout"]}, "datadog"),
            normalizer.normalize({"fingerprint": "p1", "labels": {"alertname": "Down", "service": "checkout"}}, "prometheus"),
            normalizer.normalize({"number": "INC1", "short_description": "worker", "cmdb_ci": "checkout"}, "servicenow"),
        ]
        self.assertEqual([item.service for item in values], ["checkout", "checkout", "checkout"])
        self.assertEqual([item.source for item in values], ["datadog", "prometheus", "servicenow"])

    def test_intake_deduplicates_and_correlates(self):
        intake = IncidentIntake(dedupe_seconds=60)
        first = intake.ingest({"id": "a", "title": "down", "service": "checkout"}, "synthetic")
        duplicate = intake.ingest({"id": "a", "title": "down", "service": "checkout"}, "synthetic")
        related = intake.ingest({"id": "b", "title": "still down", "service": "checkout"}, "synthetic")
        self.assertTrue(first.accepted); self.assertTrue(duplicate.duplicate); self.assertEqual(related.correlated_incident_id, "a")

    def test_repeated_synthetic_button_presses_create_new_incidents(self):
        intake = IncidentIntake(dedupe_seconds=60)
        first = intake.ingest({"scenario": "stale_heartbeat", "mode": "approval"}, "synthetic")
        second = intake.ingest({"scenario": "stale_heartbeat", "mode": "approval"}, "synthetic")
        self.assertTrue(first.accepted); self.assertTrue(second.accepted); self.assertFalse(second.duplicate)

    def test_router_selects_registered_restart_for_unhealthy_worker(self):
        decision = CapabilityRouter().decide({"title": "stale heartbeat", "message": "worker hung"}, {"healthy": False}, load_capabilities())
        self.assertEqual(decision.selected, "restart_sandbox_worker")
        self.assertTrue(decision.candidates)
        self.assertTrue(all(item.capability in load_capabilities() for item in decision.candidates))

    def test_policy_denies_non_sandbox_and_supports_shadow(self):
        policy = PolicyEngine()
        denied = policy.evaluate(PolicyInput("approval", "restart", "sandbox_only", True, .9, "prod-host", "production"))
        shadow = policy.evaluate(PolicyInput("shadow", "restart", "sandbox_only", True, .9, "synthetic.local.worker"))
        self.assertFalse(denied.allowed); self.assertEqual(denied.denied_by, "target_boundary"); self.assertTrue(shadow.allowed); self.assertFalse(shadow.requires_approval)

    def test_runtime_replays_idempotent_success_and_tracks_health(self):
        runtime = ExecutionRuntime(); calls = []
        operation = lambda: calls.append("run") or {"healthy": True}
        first = runtime.run(idempotency_key="run-1", capability="restart", operation=operation)
        second = runtime.run(idempotency_key="run-1", capability="restart", operation=operation)
        self.assertTrue(first.ok); self.assertEqual(second.status, "idempotent_replay"); self.assertEqual(calls, ["run"])

    def test_simulated_servicenow_and_aws_adapters_are_operational(self):
        alert = Alert.from_payload({"alert_id": "a1", "title": "worker down", "message": "down", "service": "checkout"})
        servicenow = ServiceNowSimulatorAdapter(); created = servicenow.create(alert); ticket_id = created.data["ticket_id"]
        updated = servicenow.update(ticket_id, "resolved", {"verified": True})
        aws = AwsEc2SimulatorAdapter(); inventory = aws.inventory(service="checkout-worker"); restarted = aws.restart_instance("i-sandbox-checkout")
        self.assertTrue(created.ok and updated.ok and inventory.ok and restarted.ok)
        self.assertEqual(restarted.data["instance"]["status_checks"], "ok")

    def test_plan_envelope_upgrades_legacy_planner_shape(self):
        envelope = ensure_envelope({"capability": "restart_sandbox_worker", "target": "synthetic.local.worker", "steps": ["restart"], "verification": {"healthy": True}}, inspection={"target": "synthetic.local.worker", "healthy": False})
        self.assertEqual(validate_envelope(envelope), [])
        self.assertEqual(envelope["target"]["environment"], "sandbox")
        self.assertEqual(envelope["verification"], [{"healthy": True}])

    def test_learning_ledger_produces_success_and_duration_summary(self):
        ledger = LearningLedger()
        ledger.record(Outcome("r1", "restart", "stale", "verified", 1.0, True)); ledger.record(Outcome("r2", "restart", "stale", "failed", 3.0, False))
        summary = ledger.summarize("restart")[0]
        self.assertEqual(summary.observations, 2); self.assertEqual(summary.verification_rate, .5); self.assertGreater(summary.p95_duration_seconds, 1.0)

    def test_verification_engine_returns_machine_readable_checks(self):
        result = VerificationEngine([CheckSpec("healthy", "health.healthy", "eq", True), CheckSpec("latency", "latency", "lt", 3)]).evaluate({"health": {"healthy": True}, "latency": 1.2})
        self.assertTrue(result["passed"]); self.assertEqual(result["passed_required"], 2)

    def test_unknown_alert_synthesizes_dependency_ordered_runbook(self):
        route = CapabilityRouter().decide({"title": "unknown signal", "message": "worker heartbeat stale"}, {"healthy": False}, load_capabilities()).as_dict()
        runbook = RunbookSynthesizer().synthesize({"alert_id": "a1", "title": "Unknown", "message": "heartbeat stale"}, {"healthy": False}, route, load_capabilities())
        observed: list[str] = []
        executor = RunbookExecutor({kind: (lambda step, kind=kind: observed.append(kind) or {"ok": True}) for kind in ("inspect", "reason", "policy", "execute", "verify")})
        result = executor.execute(runbook)
        self.assertEqual(result.status, "verified"); self.assertEqual(observed[0:2], ["inspect", "reason"]); self.assertIn("execute", observed)

    def test_target_resolution_returns_explainable_synthetic_match(self):
        resolution = TargetResolver().resolve({"service": "checkout-worker", "message": "heartbeat stale"})
        self.assertEqual(resolution.status, "resolved")
        self.assertEqual(resolution.selected.target_id, "synthetic.local.worker")
        self.assertIn("service matched alert", resolution.reason)

    def test_free_form_unknown_incident_is_preserved_and_routed_dynamically(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = RemediationOrchestrator(RemediationEngine(directory))
            try:
                run = orchestrator.ingest({"title": "Snipping Tool won't close", "message": "The process is unresponsive and must be force closed.", "service": "desktop-app"})
                self.assertEqual(run["scenario"], "custom")
                self.assertEqual(run["alert"]["title"], "Snipping Tool won't close")
                self.assertEqual(run["alert"]["service"], "desktop-app")
                self.assertEqual(run["route_preview"]["selected"], "terminate_sandbox_worker")
                planned = orchestrator.plan(run["run_id"])
                self.assertEqual(planned["plan"]["capability"], "terminate_sandbox_worker")
                completed = orchestrator.authorize(planned["run_id"])
                completed = orchestrator.execute(completed["run_id"])
                self.assertEqual(completed["status"], "verified")
                self.assertFalse(completed["verification"]["alive"])
                self.assertTrue(completed["verification_engine"]["passed"])
            finally:
                orchestrator.close()

    def test_workflow_exposes_expanded_controls_and_connectors(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = RemediationOrchestrator(RemediationEngine(directory))
            try:
                workflow = orchestrator.workflow()
                self.assertIn("servicenow-simulator", workflow["adapters"])
                self.assertIn("aws-ec2-simulator", workflow["adapters"])
                self.assertIn("intake_dedupe", workflow["controls"])
                run = orchestrator.ingest({"scenario": "stale_heartbeat", "title": "stale", "message": "heartbeat stale"})
                self.assertIn("runbook", run)
                self.assertGreaterEqual(len(run["runbook"]["steps"]), 3)
            finally:
                orchestrator.close()


if __name__ == "__main__":
    unittest.main()
