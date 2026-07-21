"""Dependency-free metrics for judge-visible operational signals."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping


def _labels(labels: Mapping[str, Any] | None) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in (labels or {}).items()))


@dataclass
class Counter:
    name: str
    help: str
    values: dict[tuple[tuple[str, str], ...], float] = field(default_factory=dict)

    def inc(self, amount: float = 1, labels: Mapping[str, Any] | None = None) -> float:
        key = _labels(labels); self.values[key] = self.values.get(key, 0) + amount; return self.values[key]

    def snapshot(self) -> dict[str, Any]:
        return {"name": self.name, "help": self.help, "values": [{"labels": dict(key), "value": value} for key, value in self.values.items()]}


@dataclass
class Gauge:
    name: str
    help: str
    values: dict[tuple[tuple[str, str], ...], float] = field(default_factory=dict)

    def set(self, value: float, labels: Mapping[str, Any] | None = None) -> None:
        self.values[_labels(labels)] = value

    def snapshot(self) -> dict[str, Any]:
        return {"name": self.name, "help": self.help, "values": [{"labels": dict(key), "value": value} for key, value in self.values.items()]}


class MetricsRegistry:
    def __init__(self) -> None:
        self.counters: dict[str, Counter] = {}
        self.gauges: dict[str, Gauge] = {}
        self.started_at = time.time()
        self.lock = threading.RLock()

    def counter(self, name: str, help: str) -> Counter:
        with self.lock:
            return self.counters.setdefault(name, Counter(name, help))

    def gauge(self, name: str, help: str) -> Gauge:
        with self.lock:
            return self.gauges.setdefault(name, Gauge(name, help))

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {"uptime_seconds": round(time.time() - self.started_at, 3), "counters": [item.snapshot() for item in self.counters.values()], "gauges": [item.snapshot() for item in self.gauges.values()]}

    def prometheus(self) -> str:
        lines: list[str] = []
        with self.lock:
            for metric in [*self.counters.values(), *self.gauges.values()]:
                lines.extend([f"# HELP {metric.name} {metric.help}", f"# TYPE {metric.name} {'counter' if isinstance(metric, Counter) else 'gauge'}"])
                for labels, value in metric.values.items():
                    label_text = "{" + ",".join(f'{key}="{value}"' for key, value in labels) + "}" if labels else ""
                    lines.append(f"{metric.name}{label_text} {value}")
        return "\n".join(lines) + ("\n" if lines else "")

    def record_workflow(self, status: str, capability: str | None = None) -> None:
        self.counter("sandbox_runs_total", "Total remediation runs").inc(labels={"status": status, "capability": capability or "unknown"})
        self.gauge("sandbox_last_run_timestamp", "Unix time of the most recent run").set(time.time())
