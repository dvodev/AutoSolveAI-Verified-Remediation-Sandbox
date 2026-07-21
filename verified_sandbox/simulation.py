"""Fault injection and deterministic scenario evaluation."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from .engine import RemediationEngine
from .evidence import verify_snapshot


@dataclass(frozen=True)
class Fault:
    name: str
    description: str
    expected_status: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationResult:
    name: str
    run_id: str
    status: str
    expected: str
    passed: bool
    duration_seconds: float
    assertions: list[dict[str, Any]] = field(default_factory=list)
    run: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "run_id": self.run_id, "status": self.status, "expected": self.expected, "passed": self.passed, "duration_seconds": self.duration_seconds, "assertions": self.assertions, "run": self.run}


FAULTS = {
    "stale_heartbeat": Fault("stale_heartbeat", "worker process lives but stops healthy heartbeats", "verified"),
    "missing_process": Fault("missing_process", "worker process disappears", "verified"),
    "healthy_signal": Fault("healthy_signal", "alert arrives for an already healthy target", "verified"),
    "shadow_preview": Fault("shadow_preview", "planner must not mutate the target", "shadowed"),
}


class ScenarioRunner:
    def __init__(self, engine_factory=lambda directory: RemediationEngine(directory)) -> None:
        self.engine_factory = engine_factory

    def run(self, name: str, data_dir: str) -> SimulationResult:
        if name not in FAULTS:
            raise ValueError(f"unknown fault: {name}")
        fault = FAULTS[name]; started = time.time(); engine = self.engine_factory(data_dir)
        try:
            mode = "shadow" if name == "shadow_preview" else "approval"
            scenario = "stale_heartbeat" if name == "shadow_preview" else name
            initial = engine.create_alert({"scenario": scenario, "mode": mode})
            planned = engine.plan(initial["run_id"])
            if mode == "shadow":
                finished = engine.execute(planned["run_id"])
            else:
                approved = engine.approve(planned["run_id"])
                finished = engine.execute(approved["run_id"])
            assertions = self._assertions(name, initial, planned, finished)
            status = finished["status"]
            return SimulationResult(name, finished["run_id"], status, fault.expected_status, status == fault.expected_status and all(item["passed"] for item in assertions), time.time() - started, assertions, finished)
        finally:
            engine.close()

    def _assertions(self, name: str, initial: dict[str, Any], planned: dict[str, Any], finished: dict[str, Any]) -> list[dict[str, Any]]:
        before = initial.get("inspection", {}); after = finished.get("verification", {})
        assertions = [
            {"name": "plan_present", "passed": bool(planned.get("plan"))},
            {"name": "target_bound", "passed": planned.get("plan", {}).get("target") == "synthetic.local.worker"},
        ]
        if name == "shadow_preview":
            assertions.append({"name": "shadow_did_not_change_pid", "passed": before.get("pid") == after.get("pid")})
        elif name == "healthy_signal":
            assertions.append({"name": "observe_only_selected", "passed": planned.get("plan", {}).get("capability") == "observe_only"})
        else:
            assertions.append({"name": "health_verified", "passed": bool(finished.get("verification_report", {}).get("passed"))})
        return assertions

    def matrix(self, names: Iterable[str], base_directory: str) -> dict[str, Any]:
        results = [self.run(name, f"{base_directory}/{index}-{name}") for index, name in enumerate(names)]
        return {"passed": all(item.passed for item in results), "total": len(results), "passed_count": sum(item.passed for item in results), "results": [item.as_dict() for item in results]}


class ReplaySimulator:
    def compare(self, first: SimulationResult, second: SimulationResult) -> dict[str, Any]:
        return {"same_scenario": first.name == second.name, "same_status": first.status == second.status, "first": first.as_dict(), "second": second.as_dict()}
