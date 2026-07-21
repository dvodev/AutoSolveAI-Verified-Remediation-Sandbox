"""Stable plan envelope shared by planner, policy, executor, and UI."""

from __future__ import annotations

from typing import Any, Mapping


PLAN_TYPES = frozenset({"primitive", "diagnostic", "generated", "connector", "composite", "escalation"})
STATUSES = frozenset({"READY", "BLOCKED", "REQUIRES_APPROVAL", "EXECUTED", "VERIFIED", "FAILED"})


def build_target(*, identifier: str | None = None, display_name: str | None = None, platform: str = "local", environment: str = "sandbox", resolved_from: str = "synthetic") -> dict[str, Any]:
    return {"id": identifier, "display_name": display_name or identifier, "platform": platform, "environment": environment, "resolved_from": resolved_from, "freshness_status": "fresh", "inventory_source": "sandbox-inspection"}


def build_envelope(*, plan_type: str = "primitive", status: str = "READY", capability: str | None = None, target: Mapping[str, Any] | None = None, steps: list[Mapping[str, Any]] | None = None, verification: list[Mapping[str, Any]] | None = None, evidence: list[Mapping[str, Any]] | None = None, reason: str = "", confidence: float = 0.0, source: str = "offline_fallback", requires_approval: bool = True, executable: bool = False, rollback: Mapping[str, Any] | None = None, escalation: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if plan_type not in PLAN_TYPES: raise ValueError(f"unsupported plan type: {plan_type}")
    if status not in STATUSES: raise ValueError(f"unsupported plan status: {status}")
    return {"plan_type": plan_type, "status": status, "supported": True, "executable": bool(executable), "requires_manual_approval": bool(requires_approval), "reason": reason, "target": dict(target or build_target()), "evidence": [dict(item) for item in (evidence or [])], "steps": [dict(item) for item in (steps or [])], "verification": [dict(item) for item in (verification or [])], "rollback": dict(rollback) if rollback else None, "escalation": dict(escalation) if escalation else None, "capability": capability, "confidence": max(0.0, min(1.0, float(confidence))), "source": source}


def ensure_envelope(plan: Mapping[str, Any] | None, *, inspection: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Upgrade legacy planner output without deleting existing fields."""
    value = dict(plan or {}); inspection = inspection or {}
    value.setdefault("plan_type", "primitive"); value.setdefault("status", "READY"); value.setdefault("supported", True); value.setdefault("executable", bool(value.get("capability"))); value.setdefault("requires_manual_approval", value.get("capability") != "observe_only"); value.setdefault("reason", value.get("reasoning", "")); value.setdefault("evidence", []); value.setdefault("steps", [{"name": step, "status": "planned"} for step in value.get("steps", []) if isinstance(step, str)]); value.setdefault("verification", []); value.setdefault("rollback", {"capability": "restart_sandbox_worker"} if value.get("capability") == "terminate_sandbox_worker" else None); value.setdefault("escalation", None); value.setdefault("supported", True); value.setdefault("confidence", .8 if value.get("source") == "openai" else .65)
    target = value.get("target") if isinstance(value.get("target"), Mapping) else {}
    if isinstance(value.get("verification"), Mapping): value["verification"] = [dict(value["verification"])]
    elif not isinstance(value.get("verification"), list): value["verification"] = []
    target = dict(target); target.setdefault("id", inspection.get("target", "synthetic.local.worker")); target.setdefault("display_name", target["id"]); target.setdefault("platform", inspection.get("os", {}).get("system", "local")); target.setdefault("environment", "sandbox"); target.setdefault("resolved_from", "sandbox-inspection"); target.setdefault("freshness_status", "fresh" if inspection.get("healthy") else "stale"); value["target"] = target
    value["plan_fingerprint_input"] = {"plan_type": value["plan_type"], "capability": value.get("capability"), "target": value["target"], "steps": value["steps"], "verification": value["verification"]}
    return value


def validate_envelope(plan: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("plan_type", "status", "target", "steps", "verification", "capability"):
        if key not in plan: errors.append(f"missing:{key}")
    if plan.get("plan_type") not in PLAN_TYPES: errors.append("invalid:plan_type")
    if plan.get("status") not in STATUSES: errors.append("invalid:status")
    if not isinstance(plan.get("target"), Mapping): errors.append("invalid:target")
    if not isinstance(plan.get("steps"), list) or not plan.get("steps"): errors.append("invalid:steps")
    if not isinstance(plan.get("verification"), list): errors.append("invalid:verification")
    try:
        if not 0 <= float(plan.get("confidence", 0)) <= 1: errors.append("invalid:confidence")
    except (TypeError, ValueError): errors.append("invalid:confidence")
    return errors
