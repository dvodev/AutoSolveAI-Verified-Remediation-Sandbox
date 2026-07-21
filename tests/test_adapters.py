from __future__ import annotations

import tempfile
import unittest

from verified_sandbox.adapters import AdapterError, AdapterRegistry, DatadogAdapter, MemoryTicketingAdapter, PrometheusAdapter, SandboxWorkerAdapter
from verified_sandbox.models import Alert, TargetRef
from verified_sandbox.sandbox import IncidentSandbox


class AdapterTests(unittest.TestCase):
    def test_datadog_payload_normalizes_alert_and_tags(self):
        alert = DatadogAdapter().normalize({"id": "d1", "title": "bad", "text": "stale", "priority": "P1", "tags": ["service:checkout", "env:sandbox"]})
        self.assertEqual(alert.source, "datadog")
        self.assertEqual(alert.service, "checkout")
        self.assertEqual(alert.labels["env"], "sandbox")

    def test_prometheus_payload_normalizes_labels_and_annotations(self):
        alert = PrometheusAdapter().normalize({"fingerprint": "p1", "labels": {"alertname": "Down", "job": "worker"}, "annotations": {"summary": "worker down"}})
        self.assertEqual(alert.alert_id, "p1")
        self.assertEqual(alert.service, "worker")

    def test_sandbox_adapter_executes_and_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            sandbox = IncidentSandbox(directory); sandbox.start(hung=True)
            adapter = SandboxWorkerAdapter(sandbox); target = TargetRef("synthetic.local.worker")
            result = adapter.execute(target, "restart_sandbox_worker")
            self.assertTrue(result.ok)
            self.assertTrue(adapter.verify(target, "restart_sandbox_worker").ok)
            adapter.rollback(target, "restart_sandbox_worker"); sandbox.close()

    def test_memory_ticketing_lifecycle(self):
        adapter = MemoryTicketingAdapter(); alert = Alert.from_payload({"alert_id": "abc", "title": "x", "message": "y", "service": "z"})
        created = adapter.create(alert); ticket_id = created.data["ticket_id"]
        updated = adapter.update(ticket_id, "resolved", {"verified": True})
        self.assertTrue(created.ok and updated.ok)
        self.assertEqual(updated.data["ticket"]["status"], "resolved")

    def test_registry_rejects_duplicate_names(self):
        registry = AdapterRegistry([DatadogAdapter()])
        with self.assertRaises(AdapterError):
            registry.register(DatadogAdapter())


if __name__ == "__main__":
    unittest.main()
