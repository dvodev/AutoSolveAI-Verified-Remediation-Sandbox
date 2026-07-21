"""Dynamic runbook synthesis and execution graph for unknown incidents.

Runbooks are generated from evidence and the capability manifest. They are
plans of observable steps, not arbitrary shell commands, which preserves the
submission's safety boundary while demonstrating how an unknown alert can be
worked without a hand-authored scenario branch.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping


@dataclass(frozen=True)
class RunbookStep:
    step_id: str
    title: str
    kind: str
    required: bool = True
    capability: str | None = None
    timeout_seconds: float = 5.0
    depends_on: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]: return {"step_id": self.step_id, "title": self.title, "kind": self.kind, "required": self.required, "capability": self.capability, "timeout_seconds": self.timeout_seconds, "depends_on": list(self.depends_on), "metadata": self.metadata}


@dataclass(frozen=True)
class Runbook:
    runbook_id: str
    title: str
    trigger: str
    steps: tuple[RunbookStep, ...]
    selected_capability: str | None
    confidence: float
    generated_reason: str
    version: int = 1

    def as_dict(self) -> dict[str, Any]: return {"runbook_id": self.runbook_id, "title": self.title, "trigger": self.trigger, "steps": [item.as_dict() for item in self.steps], "selected_capability": self.selected_capability, "confidence": self.confidence, "generated_reason": self.generated_reason, "version": self.version}


@dataclass(frozen=True)
class StepResult:
    step_id: str
    status: str
    started_at: float
    finished_at: float
    output: Any = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]: return {"step_id": self.step_id, "status": self.status, "started_at": self.started_at, "finished_at": self.finished_at, "output": self.output, "error": self.error}


@dataclass(frozen=True)
class RunbookResult:
    status: str
    runbook_id: str
    steps: tuple[StepResult, ...]
    failed_step: str | None = None

    def as_dict(self) -> dict[str, Any]: return {"status": self.status, "runbook_id": self.runbook_id, "steps": [item.as_dict() for item in self.steps], "failed_step": self.failed_step}


class RunbookSynthesizer:
    def synthesize(self, alert: Mapping[str, Any], inspection: Mapping[str, Any], route: Mapping[str, Any], capabilities: Mapping[str, Mapping[str, Any]]) -> Runbook:
        selected = str(route.get("selected") or "observe_only"); confidence = float(route.get("confidence") or .2); incident = str(alert.get("alert_id") or "incident")[-12:]; unhealthy = not bool(inspection.get("healthy")); steps: list[RunbookStep] = [RunbookStep("collect-snapshot", "Collect current target and process evidence", "inspect", True, "observe_only", metadata={"source": "sandbox-inspection"}), RunbookStep("classify-signal", "Classify alert against observed health and capability registry", "reason", True, None, depends_on=("collect-snapshot",))]
        if selected != "observe_only" and selected in capabilities and unhealthy:
            steps.append(RunbookStep("approval-gate", "Apply policy and require explicit approval for mutation", "policy", True, None, depends_on=("classify-signal",)))
            steps.append(RunbookStep("execute-capability", f"Dispatch registered capability {selected}", "execute", True, selected, depends_on=("approval-gate",)))
            steps.append(RunbookStep("verify-outcome", "Independently verify a fresh healthy state", "verify", True, "observe_only", depends_on=("execute-capability",)))
        else:
            steps.append(RunbookStep("verify-outcome", "Prove the target is already healthy without mutation", "verify", True, "observe_only", depends_on=("classify-signal",)))
        return Runbook(f"rb-{incident}", f"{alert.get('title') or 'Unknown incident'} runbook", str(alert.get("message") or "incident"), tuple(steps), selected, max(0.0, min(1.0, confidence)), str(route.get("explanation") or "Generated from observed evidence and registered capabilities."))


class RunbookExecutor:
    def __init__(self, handlers: Mapping[str, Callable[[RunbookStep], Any]] | None = None) -> None: self.handlers = dict(handlers or {})
    def register(self, kind: str, handler: Callable[[RunbookStep], Any]) -> None: self.handlers[str(kind)] = handler
    def execute(self, runbook: Runbook, *, stop_on_failure: bool = True) -> RunbookResult:
        results: list[StepResult] = []; completed: set[str] = set()
        for step in runbook.steps:
            if not set(step.depends_on).issubset(completed):
                result = StepResult(step.step_id, "blocked", time.time(), time.time(), error="dependency not completed"); results.append(result)
                if stop_on_failure and step.required: return RunbookResult("blocked", runbook.runbook_id, tuple(results), step.step_id)
                continue
            started = time.time()
            try:
                handler = self.handlers.get(step.kind)
                if handler is None: raise RuntimeError(f"no handler registered for step kind {step.kind}")
                output = handler(step); result = StepResult(step.step_id, "completed", started, time.time(), output=output); completed.add(step.step_id)
            except Exception as exc:
                result = StepResult(step.step_id, "failed", started, time.time(), error=str(exc))
                results.append(result)
                if stop_on_failure and step.required: return RunbookResult("failed", runbook.runbook_id, tuple(results), step.step_id)
            results.append(result)
        status = "verified" if all(item.status == "completed" for item in results) else "completed_with_warnings"
        return RunbookResult(status, runbook.runbook_id, tuple(results))
