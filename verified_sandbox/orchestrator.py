"""Event-driven orchestration facade used by the CLI and integrations.

The HTTP server can remain intentionally small while this module exposes a
stable workflow API for future providers and for deterministic judge scripts.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from .adapters import AdapterRegistry, DatadogAdapter, MemoryTicketingAdapter, PrometheusAdapter, SandboxWorkerAdapter
from .contracts import ContractError, fingerprint
from .engine import RemediationEngine
from .models import RunStatus, TargetRef


@dataclass(frozen=True)
class WorkflowEvent:
    name: str
    run_id: str | None
    timestamp: float
    payload: dict[str, Any] = field(default_factory=dict)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[WorkflowEvent], None]]] = {}
        self._history: list[WorkflowEvent] = []
        self._lock = threading.RLock()

    def subscribe(self, name: str, callback: Callable[[WorkflowEvent], None]) -> None:
        with self._lock:
            self._subscribers.setdefault(name, []).append(callback)

    def publish(self, name: str, run_id: str | None = None, **payload: Any) -> WorkflowEvent:
        event = WorkflowEvent(name, run_id, time.time(), payload)
        with self._lock:
            self._history.append(event)
            callbacks = list(self._subscribers.get(name, ())) + list(self._subscribers.get("*", ()))
        for callback in callbacks:
            callback(event)
        return event

    def history(self, run_id: str | None = None) -> list[WorkflowEvent]:
        with self._lock:
            return [item for item in self._history if run_id is None or item.run_id == run_id]

    def export(self, run_id: str | None = None) -> list[dict[str, Any]]:
        return [{"name": item.name, "run_id": item.run_id, "timestamp": item.timestamp, "payload": item.payload} for item in self.history(run_id)]


@dataclass(frozen=True)
class WorkflowStep:
    name: str
    description: str
    required_statuses: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    reversible: bool = False


class WorkflowDefinition:
    def __init__(self, steps: Iterable[WorkflowStep] | None = None) -> None:
        self.steps = tuple(steps or (
            WorkflowStep("ingest", "Normalize the monitoring alert", produces=("alert",)),
            WorkflowStep("inspect", "Collect target, process, OS, and log evidence", required_statuses=("alerted",), produces=("inspection",)),
            WorkflowStep("plan", "Generate and validate a structured remediation", required_statuses=("alerted",), produces=("plan",)),
            WorkflowStep("policy", "Evaluate approval or shadow controls", required_statuses=("planned",), produces=("policy",)),
            WorkflowStep("approve", "Record explicit human approval", required_statuses=("planned",), produces=("approval",), reversible=True),
            WorkflowStep("execute", "Dispatch the allowlisted capability", required_statuses=("approved", "planned"), produces=("execution",), reversible=True),
            WorkflowStep("verify", "Independently prove the post-action state", required_statuses=("executing", "shadowed"), produces=("verification",)),
        ))

    def describe(self) -> list[dict[str, Any]]:
        return [{"name": step.name, "description": step.description, "required_statuses": step.required_statuses, "produces": step.produces, "reversible": step.reversible} for step in self.steps]


class OrchestrationError(RuntimeError):
    pass


class RemediationOrchestrator:
    def __init__(self, engine: RemediationEngine | None = None, *, bus: EventBus | None = None) -> None:
        self.engine = engine or RemediationEngine()
        self.bus = bus or EventBus()
        self.definition = WorkflowDefinition()
        self.adapters = AdapterRegistry([
            DatadogAdapter(), PrometheusAdapter(), SandboxWorkerAdapter(self.engine.sandbox), MemoryTicketingAdapter(),
        ])

    def workflow(self) -> dict[str, Any]:
        return {"steps": self.definition.describe(), "adapters": self.adapters.names(), "adapter_health": self.adapters.health()}

    def ingest(self, payload: Mapping[str, Any], source: str = "synthetic") -> dict[str, Any]:
        if source == "datadog":
            alert = self.adapters.get("datadog-simulator").normalize(payload).as_dict()
        elif source == "prometheus":
            alert = self.adapters.get("prometheus-simulator").normalize(payload).as_dict()
        else:
            alert = dict(payload)
        run = self.engine.create_alert(alert)
        self.bus.publish("alert.received", run["run_id"], source=source, alert=alert)
        return run

    def plan(self, run_id: str) -> dict[str, Any]:
        run = self.engine.plan(run_id)
        self.bus.publish("plan.generated", run_id, fingerprint=run.get("plan_fingerprint"), policy=run.get("policy"))
        return run

    def authorize(self, run_id: str, actor: str = "judge") -> dict[str, Any]:
        run = self.engine.approve(run_id)
        run["approved_by"] = actor
        self.bus.publish("approval.recorded", run_id, actor=actor)
        return run

    def execute(self, run_id: str) -> dict[str, Any]:
        run = self.engine.execute(run_id)
        self.bus.publish("execution.completed", run_id, status=run.get("status"), result=run.get("result"))
        return run

    def rollback(self, run_id: str) -> dict[str, Any]:
        run = self.engine.rollback(run_id)
        self.bus.publish("rollback.completed", run_id, rollback=run.get("rollback"))
        return run

    def run_to_completion(self, payload: Mapping[str, Any], *, source: str = "synthetic", actor: str = "judge") -> dict[str, Any]:
        run = self.ingest(payload, source=source)
        run = self.plan(run["run_id"])
        if run.get("mode") != "shadow":
            run = self.authorize(run["run_id"], actor=actor)
        return self.execute(run["run_id"])

    def dry_run(self, payload: Mapping[str, Any], *, source: str = "synthetic") -> dict[str, Any]:
        body = dict(payload); body["mode"] = "shadow"
        run = self.ingest(body, source=source)
        run = self.plan(run["run_id"])
        return self.execute(run["run_id"])

    def export_run(self, run_id: str) -> dict[str, Any]:
        run = self.engine.runs.get(run_id)
        if not run:
            raise OrchestrationError(f"run not found: {run_id}")
        return {"run": run, "events": self.bus.export(run_id), "audit": self.engine.replay(run_id), "audit_chain": self.engine.events.verify_chain()}

    def close(self) -> None:
        self.engine.close()
