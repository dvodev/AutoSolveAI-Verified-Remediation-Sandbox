"""Small, explicit approval policy used by the judge-facing workflow."""

from __future__ import annotations

from typing import Any


def evaluate(plan: dict[str, Any], mode: str) -> dict[str, Any]:
    normalized = str(mode or "approval").strip().lower()
    if normalized not in {"approval", "shadow"}:
        return {"allowed": False, "reason": "mode must be approval or shadow"}
    if not plan.get("capability") or not plan.get("target"):
        return {"allowed": False, "reason": "plan must name a capability and target"}
    if normalized == "shadow":
        return {"allowed": True, "requires_approval": False, "decision": "shadow_only"}
    return {
        "allowed": True,
        "requires_approval": True,
        "decision": "human_approval_required",
        "reason": "state-changing or model-generated actions require explicit approval",
    }
