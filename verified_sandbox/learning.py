"""Small deterministic learning ledger for replayable remediation outcomes."""

from __future__ import annotations

import math
import statistics
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class Outcome:
    run_id: str
    capability: str
    scenario: str
    status: str
    duration_seconds: float
    verified: bool
    source: str = "sandbox"
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]: return {"run_id": self.run_id, "capability": self.capability, "scenario": self.scenario, "status": self.status, "duration_seconds": self.duration_seconds, "verified": self.verified, "source": self.source, "timestamp": self.timestamp, "metadata": self.metadata}


@dataclass(frozen=True)
class CapabilityLearning:
    capability: str
    observations: int
    success_rate: float
    verification_rate: float
    average_duration_seconds: float
    p95_duration_seconds: float
    confidence_adjustment: float

    def as_dict(self) -> dict[str, Any]: return self.__dict__.copy()


class LearningLedger:
    def __init__(self, *, max_outcomes: int = 5000) -> None:
        self.max_outcomes = max_outcomes; self._outcomes: list[Outcome] = []; self._lock = threading.RLock()

    def record(self, outcome: Outcome) -> Outcome:
        with self._lock:
            self._outcomes.append(outcome)
            if len(self._outcomes) > self.max_outcomes: self._outcomes = self._outcomes[-self.max_outcomes:]
        return outcome

    def outcomes(self, capability: str | None = None, scenario: str | None = None) -> list[Outcome]:
        with self._lock: return [item for item in self._outcomes if (not capability or item.capability == capability) and (not scenario or item.scenario == scenario)]

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values: return 0.0
        ordered = sorted(values); index = (len(ordered) - 1) * percentile; lower = math.floor(index); upper = math.ceil(index)
        if lower == upper: return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)

    def summarize(self, capability: str | None = None) -> list[CapabilityLearning]:
        groups: dict[str, list[Outcome]] = {}
        for item in self.outcomes(capability=capability): groups.setdefault(item.capability, []).append(item)
        result: list[CapabilityLearning] = []
        for name, values in sorted(groups.items()):
            durations = [max(0.0, float(item.duration_seconds)) for item in values]; success = sum(item.status in {"verified", "shadowed"} for item in values) / len(values); verified = sum(item.verified for item in values) / len(values); confidence = max(-.2, min(.2, (verified - .5) * .4))
            result.append(CapabilityLearning(name, len(values), success, verified, statistics.fmean(durations), self._percentile(durations, .95), confidence))
        return result

    def recommend_confidence(self, capability: str, baseline: float) -> float:
        summary = next((item for item in self.summarize(capability) if item.capability == capability), None)
        return max(0.0, min(1.0, baseline + (summary.confidence_adjustment if summary else 0.0)))

    def snapshot(self) -> dict[str, Any]: return {"outcomes": len(self._outcomes), "capabilities": [item.as_dict() for item in self.summarize()]}
