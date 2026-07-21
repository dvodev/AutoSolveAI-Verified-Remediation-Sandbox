"""Composable policy controls for approval, shadow, blast radius, and replay."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping


RISK_RANK = {"none": 0, "sandbox_only": 1, "low": 2, "medium": 3, "high": 4, "critical": 5}


@dataclass(frozen=True)
class PolicyInput:
    mode: str
    capability: str
    risk: str
    mutates: bool
    confidence: float
    target: str
    target_environment: str = "sandbox"
    alert_severity: str = "warning"
    heartbeat_age_seconds: float | None = None
    approved_actor: str | None = None
    emergency_stop: bool = False
    budget_remaining: int | None = None


@dataclass(frozen=True)
class PolicyResult:
    allowed: bool
    decision: str
    reason: str
    requires_approval: bool
    controls: tuple[str, ...] = ()
    expires_at: float | None = None
    denied_by: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "decision": self.decision, "reason": self.reason, "requires_approval": self.requires_approval, "controls": list(self.controls), "expires_at": self.expires_at, "denied_by": self.denied_by}


class PolicyEngine:
    def __init__(self, *, max_risk: str = "sandbox_only", approval_ttl_seconds: float = 900.0) -> None:
        self.max_risk = max_risk; self.approval_ttl_seconds = float(approval_ttl_seconds)

    def evaluate(self, item: PolicyInput) -> PolicyResult:
        mode = str(item.mode or "approval").lower(); risk = str(item.risk or "unknown").lower(); controls = ["target_contract", "capability_allowlist", "post_action_verification"]
        if mode not in {"approval", "shadow"}: return PolicyResult(False, "denied", "mode must be approval or shadow", False, tuple(controls), denied_by="mode")
        if item.target_environment != "sandbox" or item.target != "synthetic.local.worker": return PolicyResult(False, "denied", "target is outside the submission sandbox", False, tuple(controls), denied_by="target_boundary")
        if item.emergency_stop: return PolicyResult(False, "denied", "emergency stop is active", False, tuple(controls), denied_by="emergency_stop")
        if RISK_RANK.get(risk, 99) > RISK_RANK.get(self.max_risk, 1): return PolicyResult(False, "denied", f"risk {risk} exceeds policy ceiling {self.max_risk}", False, tuple(controls), denied_by="risk_ceiling")
        if item.budget_remaining is not None and item.budget_remaining <= 0: return PolicyResult(False, "denied", "execution budget is exhausted", False, tuple(controls), denied_by="budget")
        if item.confidence < .35 and item.mutates: return PolicyResult(False, "denied", "model confidence is below the mutation threshold", False, tuple(controls), denied_by="confidence")
        if mode == "shadow": return PolicyResult(True, "shadow_only", "shadow mode permits planning and evidence collection without mutation", False, tuple(controls + ["no_mutation"]))
        controls.append("human_approval") if item.mutates else None
        return PolicyResult(True, "approval_required" if item.mutates else "observe_allowed", "explicit approval is required before a state-changing capability", item.mutates, tuple(controls), time.time() + self.approval_ttl_seconds if item.mutates else None)


def evaluate(plan: Mapping[str, Any], mode: str) -> dict[str, Any]:
    """Compatibility wrapper retaining the original public policy function."""
    result = PolicyEngine().evaluate(PolicyInput(mode=str(mode), capability=str(plan.get("capability") or ""), risk=str(plan.get("risk") or "unknown"), mutates=str(plan.get("capability")) != "observe_only", confidence=float(plan.get("confidence", .8)), target=str(plan.get("target") or "synthetic.local.worker")))
    return result.as_dict()
