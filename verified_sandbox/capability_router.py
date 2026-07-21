"""Explainable, data-driven capability selection.

The router never executes an action. It ranks only registered capabilities and
returns evidence for why a candidate was selected, leaving policy and the
execution boundary as separate controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class RouteCandidate:
    capability: str
    score: float
    reasons: tuple[str, ...] = ()
    blocked: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"capability": self.capability, "score": round(self.score, 4), "reasons": list(self.reasons), "blocked": self.blocked}


@dataclass(frozen=True)
class RouteDecision:
    selected: str
    candidates: tuple[RouteCandidate, ...]
    confidence: float
    explanation: str
    fallback_used: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"selected": self.selected, "candidates": [item.as_dict() for item in self.candidates], "confidence": round(self.confidence, 4), "explanation": self.explanation, "fallback_used": self.fallback_used}


class CapabilityRouter:
    KEYWORDS = {"restart": ("restart", "hung", "stale", "unhealthy", "crash", "heartbeat"), "terminate": ("terminate", "kill", "stop", "stuck", "won't close", "wont close", "not responding", "unresponsive", "force close"), "observe": ("healthy", "no-op", "normal", "signal")}

    def rank(self, alert: Mapping[str, Any], inspection: Mapping[str, Any], registry: Mapping[str, Mapping[str, Any]]) -> tuple[RouteCandidate, ...]:
        text = " ".join(str(alert.get(key, "")) for key in ("title", "message", "severity", "service")).lower(); healthy = bool(inspection.get("healthy")); termination_signal = any(word in text for word in self.KEYWORDS["terminate"]); candidates: list[RouteCandidate] = []
        for name, spec in registry.items():
            reasons: list[str] = []; score = 0.0; mutates = bool(spec.get("mutates"))
            if name == "observe_only":
                score += 0.8 if healthy else 0.1; reasons.append("target is healthy" if healthy else "safe observation fallback")
                if any(word in text for word in self.KEYWORDS["observe"]): score += 0.25; reasons.append("alert language suggests observation")
            elif "restart" in name:
                score += 0.15 if termination_signal else (0.9 if not healthy else 0.15); reasons.append("explicit termination language takes precedence" if termination_signal else ("target is unhealthy" if not healthy else "restart is unnecessary while healthy"))
                if any(word in text for word in self.KEYWORDS["restart"]): score += 0.45; reasons.append("alert matches restart signal")
            elif "terminate" in name:
                score += 0.35 if not healthy else 0.05; reasons.append("termination is available for a failed worker")
                if termination_signal: score += 0.9; reasons.append("alert matches termination signal")
            else:
                score += 0.05; reasons.append("registered capability with no specialized signal")
            candidates.append(RouteCandidate(name, score, tuple(reasons), blocked=False if name in registry else True))
        return tuple(sorted(candidates, key=lambda item: (-item.score, item.capability)))

    def decide(self, alert: Mapping[str, Any], inspection: Mapping[str, Any], registry: Mapping[str, Mapping[str, Any]]) -> RouteDecision:
        ranked = self.rank(alert, inspection, registry)
        if not ranked: raise ValueError("no capabilities are registered")
        winner = ranked[0]; second = ranked[1].score if len(ranked) > 1 else 0.0; confidence = min(1.0, max(.1, .5 + (winner.score - second) / 2))
        fallback = winner.capability == "observe_only" and not inspection.get("healthy")
        explanation = f"Selected {winner.capability} from {len(ranked)} registered capabilities; {winner.reasons[0] if winner.reasons else 'highest scored candidate'}."
        return RouteDecision(winner.capability, ranked, confidence, explanation, fallback)
