"""Evidence collection, normalization, comparison, and verification helpers."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .contracts import redact
from .models import Evidence, EvidenceKind


@dataclass(frozen=True)
class EvidenceDiff:
    key: str
    before: Any
    after: Any
    changed: bool


def flatten(value: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, Mapping):
            result.update(flatten(item, path))
        else:
            result[path] = item
    return result


def diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[EvidenceDiff]:
    left, right = flatten(before), flatten(after)
    return [EvidenceDiff(key, left.get(key), right.get(key), left.get(key) != right.get(key)) for key in sorted(set(left) | set(right))]


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_json_output(stdout: str) -> Any:
    text = str(stdout or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def collect_target_snapshot(snapshot: Mapping[str, Any], source: str = "sandbox-inspection") -> list[Evidence]:
    cleaned = redact(dict(snapshot))
    return [
        Evidence.create(EvidenceKind.INVENTORY, "target", cleaned.get("target"), source, snapshot=cleaned),
        Evidence.create(EvidenceKind.INVENTORY, "process", {key: cleaned.get(key) for key in ("pid", "alive", "status", "healthy")}, source),
        Evidence.create(EvidenceKind.INVENTORY, "heartbeat", {key: cleaned.get(key) for key in ("heartbeat", "heartbeat_age_seconds")}, source),
        Evidence.create(EvidenceKind.INVENTORY, "os", cleaned.get("os", {}), source),
        Evidence.create(EvidenceKind.LOG, "worker-log", normalize_text(cleaned.get("logs")), source),
    ]


def evidence_summary(items: Iterable[Evidence]) -> dict[str, Any]:
    values = list(items)
    by_kind: dict[str, int] = {}
    for item in values:
        by_kind[item.kind] = by_kind.get(item.kind, 0) + 1
    return {"count": len(values), "by_kind": by_kind, "sources": sorted({item.source for item in values}), "latest": max((item.observed_at for item in values), default=None)}


def verify_snapshot(snapshot: Mapping[str, Any], *, require_healthy: bool = True, max_age: float = 3.0) -> dict[str, Any]:
    age = snapshot.get("heartbeat_age_seconds")
    checks = [
        {"name": "target_identity", "passed": snapshot.get("target") == "synthetic.local.worker", "observed": snapshot.get("target")},
        {"name": "process_alive", "passed": bool(snapshot.get("alive")), "observed": snapshot.get("alive")},
        {"name": "heartbeat_fresh", "passed": isinstance(age, (int, float)) and float(age) < max_age, "observed": age},
    ]
    if require_healthy:
        checks.append({"name": "healthy_state", "passed": bool(snapshot.get("healthy")), "observed": snapshot.get("status")})
    return {"passed": all(item["passed"] for item in checks), "checks": checks, "verified_at": time.time()}


def compare_verification(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    changes = [item.__dict__ for item in diff(before, after) if item.changed]
    return {"changed_fields": changes, "pid_changed": before.get("pid") != after.get("pid"), "health_transition": [before.get("healthy"), after.get("healthy")], "from": dict(before), "to": dict(after)}
