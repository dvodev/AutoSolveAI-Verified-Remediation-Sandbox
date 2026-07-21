"""Reliability primitives around the intentionally small worker adapter."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 2
    backoff_seconds: float = .05
    retryable_statuses: tuple[str, ...] = ("timeout", "unavailable", "transient_failure")


@dataclass(frozen=True)
class ExecutionEnvelope:
    execution_id: str
    run_id: str
    capability: str
    target: str
    idempotency_key: str
    attempt: int
    started_at: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeResult:
    ok: bool
    status: str
    attempts: int
    value: Any = None
    error: str | None = None
    elapsed_seconds: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "status": self.status, "attempts": self.attempts, "value": self.value, "error": self.error, "elapsed_seconds": round(self.elapsed_seconds, 6)}


class IdempotencyStore:
    def __init__(self) -> None: self._values: dict[str, RuntimeResult] = {}; self._lock = threading.RLock()
    def get(self, key: str) -> RuntimeResult | None:
        with self._lock: return self._values.get(key)
    def put(self, key: str, result: RuntimeResult) -> None:
        with self._lock: self._values[key] = result
    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock: return {key: value.as_dict() for key, value in self._values.items()}


class CircuitBreaker:
    def __init__(self, *, failure_threshold: int = 3, reset_seconds: float = 30.0) -> None:
        self.failure_threshold = failure_threshold; self.reset_seconds = reset_seconds; self.failures = 0; self.opened_at: float | None = None; self._lock = threading.RLock()
    def allow(self) -> bool:
        with self._lock:
            if self.opened_at is None: return True
            if time.time() - self.opened_at >= self.reset_seconds: self.opened_at = None; self.failures = 0; return True
            return False
    def record(self, success: bool) -> None:
        with self._lock:
            if success: self.failures = 0; self.opened_at = None
            else:
                self.failures += 1
                if self.failures >= self.failure_threshold: self.opened_at = time.time()
    def state(self) -> dict[str, Any]: return {"open": self.opened_at is not None and not self.allow(), "failures": self.failures, "opened_at": self.opened_at}


class ExecutionRuntime:
    def __init__(self, *, retry: RetryPolicy | None = None, store: IdempotencyStore | None = None) -> None:
        self.retry = retry or RetryPolicy(); self.store = store or IdempotencyStore(); self.breakers: dict[str, CircuitBreaker] = {}; self._lock = threading.RLock()

    def breaker(self, capability: str) -> CircuitBreaker:
        with self._lock: return self.breakers.setdefault(capability, CircuitBreaker())

    def run(self, *, idempotency_key: str, capability: str, operation: Callable[[], Any]) -> RuntimeResult:
        previous = self.store.get(idempotency_key)
        if previous is not None: return RuntimeResult(previous.ok, "idempotent_replay", previous.attempts, previous.value, previous.error, previous.elapsed_seconds)
        breaker = self.breaker(capability)
        if not breaker.allow(): return RuntimeResult(False, "circuit_open", 0, error=f"circuit open for {capability}")
        started = time.monotonic(); last_error: str | None = None
        for attempt in range(1, max(1, self.retry.attempts) + 1):
            try:
                value = operation(); result = RuntimeResult(True, "completed", attempt, value, elapsed_seconds=time.monotonic() - started); breaker.record(True); self.store.put(idempotency_key, result); return result
            except Exception as exc:
                last_error = str(exc); breaker.record(False)
                if attempt < max(1, self.retry.attempts): time.sleep(self.retry.backoff_seconds * attempt)
        result = RuntimeResult(False, "failed", max(1, self.retry.attempts), error=last_error, elapsed_seconds=time.monotonic() - started); self.store.put(idempotency_key, result); return result

    def health(self) -> dict[str, Any]: return {"idempotency_records": len(self.store.snapshot()), "breakers": {name: breaker.state() for name, breaker in self.breakers.items()}}
