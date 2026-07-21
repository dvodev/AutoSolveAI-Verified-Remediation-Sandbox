"""Composable independent verification checks and evidence scoring."""

from __future__ import annotations

import operator
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping


OPERATORS: dict[str, Callable[[Any, Any], bool]] = {"eq": operator.eq, "ne": operator.ne, "lt": operator.lt, "lte": operator.le, "gt": operator.gt, "gte": operator.ge, "contains": lambda left, right: right in left, "truthy": lambda left, right: bool(left) is bool(right)}


@dataclass(frozen=True)
class CheckSpec:
    name: str
    path: str
    operator: str
    expected: Any
    required: bool = True
    description: str = ""

    def as_dict(self) -> dict[str, Any]: return {"name": self.name, "path": self.path, "operator": self.operator, "expected": self.expected, "required": self.required, "description": self.description}


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    required: bool
    actual: Any
    expected: Any
    operator: str
    elapsed_seconds: float
    error: str | None = None

    def as_dict(self) -> dict[str, Any]: return self.__dict__.copy()


def get_path(value: Any, path: str, default: Any = None) -> Any:
    current = value
    for part in str(path).split("."):
        if isinstance(current, Mapping): current = current.get(part, default)
        else: return default
    return current


class VerificationEngine:
    def __init__(self, checks: list[CheckSpec] | None = None) -> None: self.checks = list(checks or [])
    def add(self, check: CheckSpec) -> "VerificationEngine": self.checks.append(check); return self
    def evaluate(self, snapshot: Mapping[str, Any], checks: list[CheckSpec] | None = None) -> dict[str, Any]:
        values = list(checks or self.checks); results: list[CheckResult] = []
        for check in values:
            started = time.monotonic(); actual = get_path(snapshot, check.path); error = None; passed = False
            try:
                fn = OPERATORS[check.operator]; passed = bool(fn(actual, check.expected))
            except (KeyError, TypeError, ValueError) as exc: error = str(exc)
            results.append(CheckResult(check.name, passed, check.required, actual, check.expected, check.operator, time.monotonic() - started, error))
        required = [item for item in results if item.required]; passed = all(item.passed for item in required)
        return {"passed": passed, "checks": [item.as_dict() for item in results], "required": len(required), "passed_required": sum(item.passed for item in required), "score": sum(item.passed for item in results) / len(results) if results else 1.0}

    @classmethod
    def healthy_worker(cls, *, max_heartbeat_age: float = 3.0) -> "VerificationEngine":
        return cls([CheckSpec("worker alive", "alive", "eq", True), CheckSpec("worker healthy", "healthy", "eq", True), CheckSpec("fresh heartbeat", "heartbeat_age_seconds", "lt", max_heartbeat_age)])
