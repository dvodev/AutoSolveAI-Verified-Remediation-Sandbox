"""Provider-neutral adapter contracts for the sandbox edition.

The challenge build is synthetic, but it demonstrates the same seams a real
incident product needs: monitoring ingestion, target inspection, controlled
execution, ticket updates, and post-action verification. Every adapter is
side-effect scoped and returns serializable results.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .evidence import collect_target_snapshot, verify_snapshot
from .models import Alert, Evidence, TargetRef
from .sandbox import IncidentSandbox


@dataclass(frozen=True)
class AdapterResult:
    adapter: str
    operation: str
    ok: bool
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    evidence: tuple[Evidence, ...] = ()
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float = field(default_factory=time.time)

    def as_dict(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter, "operation": self.operation, "ok": self.ok,
            "status": self.status, "data": self.data,
            "evidence": [item.as_dict() for item in self.evidence], "error": self.error,
            "started_at": self.started_at, "finished_at": self.finished_at,
        }


class AdapterError(RuntimeError):
    pass


class MonitoringAdapter(abc.ABC):
    name = "monitoring"

    @abc.abstractmethod
    def normalize(self, payload: Mapping[str, Any]) -> Alert:
        raise NotImplementedError

    @abc.abstractmethod
    def health(self) -> AdapterResult:
        raise NotImplementedError


class DatadogAdapter(MonitoringAdapter):
    name = "datadog-simulator"

    def normalize(self, payload: Mapping[str, Any]) -> Alert:
        event = payload.get("event") if isinstance(payload.get("event"), Mapping) else payload
        tags = event.get("tags") or event.get("labels") or {}
        if isinstance(tags, list):
            tags = {str(item).split(":", 1)[0]: str(item).split(":", 1)[1] for item in tags if ":" in str(item)}
        return Alert.from_payload({
            "source": "datadog",
            "alert_id": event.get("id") or event.get("alert_id"),
            "title": event.get("title") or event.get("monitor_name"),
            "message": event.get("text") or event.get("message"),
            "severity": event.get("priority") or event.get("severity"),
            "service": event.get("service") or tags.get("service") or "unknown",
            "labels": tags,
            "raw": dict(payload),
        })

    def health(self) -> AdapterResult:
        return AdapterResult(self.name, "health", True, "ready", {"provider": "synthetic-datadog"})


class PrometheusAdapter(MonitoringAdapter):
    name = "prometheus-simulator"

    def normalize(self, payload: Mapping[str, Any]) -> Alert:
        labels = payload.get("labels") if isinstance(payload.get("labels"), Mapping) else {}
        annotations = payload.get("annotations") if isinstance(payload.get("annotations"), Mapping) else {}
        return Alert.from_payload({
            "source": "prometheus",
            "alert_id": payload.get("fingerprint") or payload.get("alert_id"),
            "title": annotations.get("summary") or labels.get("alertname"),
            "message": annotations.get("description") or "Prometheus alert received",
            "severity": labels.get("severity") or "warning",
            "service": labels.get("service") or labels.get("job") or "unknown",
            "labels": labels,
            "raw": dict(payload),
        })

    def health(self) -> AdapterResult:
        return AdapterResult(self.name, "health", True, "ready", {"provider": "synthetic-prometheus"})


class ServiceNowSimulatorAdapter:
    """ServiceNow-shaped ticket lifecycle without network or credentials."""

    name = "servicenow-simulator"

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def health(self) -> AdapterResult:
        return AdapterResult(self.name, "health", True, "ready", {"provider": "synthetic-servicenow", "mode": "simulator"})

    def create(self, alert: Alert) -> AdapterResult:
        number = f"INC{abs(hash(alert.alert_id)) % 10_000_000:07d}"
        record = {"number": number, "state": "new", "short_description": alert.title, "description": alert.message, "impact": alert.severity, "service": alert.service, "work_notes": []}
        self.records[number] = record
        return AdapterResult(self.name, "create_incident", True, "created", {"ticket_id": number, "record": record})

    def update(self, ticket_id: str, status: str, details: Mapping[str, Any]) -> AdapterResult:
        record = self.records.get(str(ticket_id))
        if not record:
            return AdapterResult(self.name, "update_incident", False, "not_found", error=str(ticket_id))
        note = {"timestamp": time.time(), "status": str(status), "details": dict(details)}
        record["state"] = str(status); record["work_notes"].append(note)
        return AdapterResult(self.name, "update_incident", True, "updated", {"ticket_id": ticket_id, "record": record, "note": note})


class AwsEc2SimulatorAdapter:
    """AWS/EC2-shaped inventory and action ledger; never calls AWS."""

    name = "aws-ec2-simulator"

    def __init__(self) -> None:
        self.instances = {
            "i-sandbox-checkout": {"instance_id": "i-sandbox-checkout", "state": "running", "status_checks": "impaired", "region": "us-east-1", "service": "checkout-worker", "environment": "sandbox"},
            "i-sandbox-api": {"instance_id": "i-sandbox-api", "state": "running", "status_checks": "ok", "region": "us-east-1", "service": "api", "environment": "sandbox"},
        }
        self.actions: list[dict[str, Any]] = []

    def health(self) -> AdapterResult:
        return AdapterResult(self.name, "health", True, "ready", {"provider": "aws", "mode": "simulator", "instances": len(self.instances)})

    def inventory(self, *, service: str | None = None) -> AdapterResult:
        values = [dict(item) for item in self.instances.values() if not service or item["service"] == service]
        return AdapterResult(self.name, "describe_instances", True, "complete", {"count": len(values), "instances": values})

    def restart_instance(self, instance_id: str) -> AdapterResult:
        instance = self.instances.get(str(instance_id))
        if not instance:
            return AdapterResult(self.name, "restart_instance", False, "not_found", error=str(instance_id))
        action = {"action": "restart_instance", "instance_id": instance_id, "timestamp": time.time(), "simulated": True}
        instance["state"] = "running"; instance["status_checks"] = "ok"; self.actions.append(action)
        return AdapterResult(self.name, "restart_instance", True, "simulated", {"instance": dict(instance), "action": action})


class ConnectorHealth:
    """Stable health payload for UI, CLI, and judge scripts."""

    @staticmethod
    def summarize(registry: "AdapterRegistry") -> dict[str, Any]:
        values = registry.health(); return {"healthy": all(item.get("ok", item.get("status") in {"ready", "registered"}) for item in values.values()), "count": len(values), "adapters": values}


class TargetAdapter(abc.ABC):
    name = "target"

    @abc.abstractmethod
    def inspect(self, target: TargetRef) -> AdapterResult:
        raise NotImplementedError

    @abc.abstractmethod
    def execute(self, target: TargetRef, capability: str, inputs: Mapping[str, Any] | None = None) -> AdapterResult:
        raise NotImplementedError

    @abc.abstractmethod
    def verify(self, target: TargetRef, capability: str) -> AdapterResult:
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self, target: TargetRef, capability: str) -> AdapterResult:
        raise NotImplementedError


class SandboxWorkerAdapter(TargetAdapter):
    name = "sandbox-worker"

    def __init__(self, sandbox: IncidentSandbox) -> None:
        self.sandbox = sandbox

    def inspect(self, target: TargetRef) -> AdapterResult:
        before = time.time(); snapshot = self.sandbox.inspect(); after = time.time()
        return AdapterResult(self.name, "inspect", True, "complete", snapshot, tuple(collect_target_snapshot(snapshot)), started_at=before, finished_at=after)

    def execute(self, target: TargetRef, capability: str, inputs: Mapping[str, Any] | None = None) -> AdapterResult:
        before = time.time()
        try:
            if capability == "restart_sandbox_worker":
                result = self.sandbox.start(hung=False)
            elif capability == "terminate_sandbox_worker":
                self.sandbox.stop(); result = self.sandbox.inspect()
            elif capability == "observe_only":
                result = self.sandbox.inspect()
            else:
                return AdapterResult(self.name, "execute", False, "rejected", error=f"unknown capability: {capability}")
            return AdapterResult(self.name, "execute", True, "complete", result, tuple(collect_target_snapshot(result)), started_at=before, finished_at=time.time())
        except Exception as exc:
            return AdapterResult(self.name, "execute", False, "failed", error=str(exc), started_at=before, finished_at=time.time())

    def verify(self, target: TargetRef, capability: str) -> AdapterResult:
        before = time.time(); snapshot = self.sandbox.inspect()
        require_healthy = capability != "terminate_sandbox_worker"
        report = verify_snapshot(snapshot, require_healthy=require_healthy)
        return AdapterResult(self.name, "verify", report["passed"], "verified" if report["passed"] else "failed", {"snapshot": snapshot, "report": report}, tuple(collect_target_snapshot(snapshot)), started_at=before, finished_at=time.time())

    def rollback(self, target: TargetRef, capability: str) -> AdapterResult:
        before = time.time()
        try:
            snapshot = self.sandbox.start(hung=False)
            report = verify_snapshot(snapshot)
            return AdapterResult(self.name, "rollback", report["passed"], "verified" if report["passed"] else "failed", {"snapshot": snapshot, "report": report}, tuple(collect_target_snapshot(snapshot)), started_at=before, finished_at=time.time())
        except Exception as exc:
            return AdapterResult(self.name, "rollback", False, "failed", error=str(exc), started_at=before, finished_at=time.time())


class TicketingAdapter(abc.ABC):
    name = "ticketing"

    @abc.abstractmethod
    def create(self, alert: Alert) -> AdapterResult:
        raise NotImplementedError

    @abc.abstractmethod
    def update(self, ticket_id: str, status: str, details: Mapping[str, Any]) -> AdapterResult:
        raise NotImplementedError


class MemoryTicketingAdapter(TicketingAdapter):
    name = "memory-ticketing"

    def __init__(self) -> None:
        self.tickets: dict[str, dict[str, Any]] = {}

    def create(self, alert: Alert) -> AdapterResult:
        ticket_id = f"INC-{alert.alert_id[-8:].upper()}"
        self.tickets[ticket_id] = {"id": ticket_id, "status": "open", "alert": alert.as_dict(), "updates": []}
        return AdapterResult(self.name, "create", True, "created", {"ticket_id": ticket_id, "ticket": self.tickets[ticket_id]})

    def update(self, ticket_id: str, status: str, details: Mapping[str, Any]) -> AdapterResult:
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            return AdapterResult(self.name, "update", False, "not_found", error=ticket_id)
        update = {"status": status, "details": dict(details), "timestamp": time.time()}
        ticket["status"] = status; ticket["updates"].append(update)
        return AdapterResult(self.name, "update", True, "updated", {"ticket": ticket, "update": update})


class AdapterRegistry:
    def __init__(self, adapters: Iterable[Any] | None = None) -> None:
        self.adapters: dict[str, Any] = {}
        for adapter in adapters or ():
            self.register(adapter)

    def register(self, adapter: Any) -> None:
        name = str(getattr(adapter, "name", "")).strip()
        if not name:
            raise AdapterError("adapter must expose a name")
        if name in self.adapters:
            raise AdapterError(f"adapter already registered: {name}")
        self.adapters[name] = adapter

    def get(self, name: str) -> Any:
        if name not in self.adapters:
            raise AdapterError(f"adapter unavailable: {name}")
        return self.adapters[name]

    def health(self) -> dict[str, dict[str, Any]]:
        result = {}
        for name, adapter in self.adapters.items():
            method = getattr(adapter, "health", None)
            result[name] = method().as_dict() if callable(method) else {"status": "registered"}
        return result

    def names(self) -> list[str]:
        return sorted(self.adapters)
