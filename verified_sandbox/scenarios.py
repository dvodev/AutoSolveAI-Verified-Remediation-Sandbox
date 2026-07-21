"""Synthetic incidents judges can select without touching a real host."""

from __future__ import annotations

from typing import Any


SCENARIOS: dict[str, dict[str, Any]] = {
    "stale_heartbeat": {
        "label": "Stale heartbeat",
        "description": "A checkout worker is alive but no longer reporting healthy heartbeats.",
        "worker_mode": "hung",
        "alert_title": "checkout-worker heartbeat stale",
    },
    "missing_process": {
        "label": "Missing process",
        "description": "A required worker disappeared and must be restored in the sandbox.",
        "worker_mode": "missing",
        "alert_title": "checkout-worker process missing",
    },
    "healthy_signal": {
        "label": "Healthy signal",
        "description": "A noisy alert arrives while the target is already healthy; prove it without changing anything.",
        "worker_mode": "healthy",
        "alert_title": "checkout-worker health signal received",
    },
}


def get_scenario(name: str | None) -> tuple[str, dict[str, Any]]:
    key = str(name or "stale_heartbeat").strip().lower()
    if key not in SCENARIOS:
        raise ValueError(f"unknown synthetic scenario: {key}")
    return key, dict(SCENARIOS[key])
