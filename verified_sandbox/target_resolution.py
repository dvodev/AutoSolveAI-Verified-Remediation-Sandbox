"""Deterministic target-resolution seam backed by synthetic inventory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class TargetCandidate:
    target_id: str
    display_name: str
    target_type: str
    provider: str
    environment: str
    score: float
    reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]: return {"target_id": self.target_id, "display_name": self.display_name, "target_type": self.target_type, "provider": self.provider, "environment": self.environment, "score": round(self.score, 4), "reasons": list(self.reasons)}


@dataclass(frozen=True)
class Resolution:
    selected: TargetCandidate | None
    candidates: tuple[TargetCandidate, ...]
    status: str
    confidence: float
    reason: str

    def as_dict(self) -> dict[str, Any]: return {"selected": self.selected.as_dict() if self.selected else None, "candidates": [item.as_dict() for item in self.candidates], "status": self.status, "confidence": round(self.confidence, 4), "reason": self.reason}


class TargetResolver:
    def __init__(self, inventory: Iterable[Mapping[str, Any]] | None = None) -> None:
        self.inventory = [dict(item) for item in (inventory or ({"id": "synthetic.local.worker", "name": "Checkout Worker", "type": "synthetic.worker", "provider": "local-simulator", "environment": "sandbox", "service": "checkout-worker"},))]

    def resolve(self, hints: Mapping[str, Any] | None = None) -> Resolution:
        hints = hints or {}; text = " ".join(str(hints.get(key, "")) for key in ("target", "target_id", "service", "hostname", "resource_id", "title", "message")).lower(); candidates: list[TargetCandidate] = []
        for item in self.inventory:
            target_id = str(item.get("id") or item.get("instance_id") or item.get("hostname") or "unknown"); name = str(item.get("name") or item.get("display_name") or target_id); service = str(item.get("service") or "").lower(); score = .1; reasons = ["inventory candidate"]
            if target_id.lower() in text: score += .7; reasons.append("identifier matched alert")
            if service and service in text: score += .45; reasons.append("service matched alert")
            if str(item.get("environment", "sandbox")).lower() in text: score += .1; reasons.append("environment matched alert")
            candidates.append(TargetCandidate(target_id, name, str(item.get("type") or "synthetic.worker"), str(item.get("provider") or "local-simulator"), str(item.get("environment") or "sandbox"), min(1.0, score), tuple(reasons)))
        candidates.sort(key=lambda item: (-item.score, item.target_id)); selected = candidates[0] if candidates else None; ambiguous = len(candidates) > 1 and abs(candidates[0].score - candidates[1].score) < .1
        if not selected: return Resolution(None, (), "unresolved", 0.0, "no inventory candidate matched")
        if ambiguous: return Resolution(None, tuple(candidates), "ambiguous", selected.score, "multiple targets have equivalent evidence")
        return Resolution(selected, tuple(candidates), "resolved", selected.score, "; ".join(selected.reasons))
