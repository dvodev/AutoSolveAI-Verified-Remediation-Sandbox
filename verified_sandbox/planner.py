"""AI planner with strict schema validation and a deterministic offline mode."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


ALLOWED_CAPABILITIES = {"restart_sandbox_worker", "terminate_sandbox_worker"}


def _fallback(alert: dict[str, Any], inspection: dict[str, Any]) -> dict[str, Any]:
    capability = "restart_sandbox_worker" if inspection.get("alive") else "terminate_sandbox_worker"
    return {
        "capability": capability,
        "target": inspection.get("target", "synthetic.local.worker"),
        "reasoning": "The synthetic worker is unhealthy; restart it and prove a fresh healthy heartbeat.",
        "steps": ["inspect_worker", capability],
        "verification": {"healthy": True, "heartbeat_age_seconds_less_than": 3},
        "risk": "sandbox_only",
        "source": "offline_fallback",
    }


def _extract_json(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices") or []
    content = (((choices[0] if choices else {}).get("message") or {}).get("content") or "")
    if isinstance(content, list):
        content = "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
    text = str(content).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("model response was not an object")
    return value


def _validate(plan: dict[str, Any], inspection: dict[str, Any]) -> dict[str, Any]:
    capability = str(plan.get("capability") or "").strip()
    if capability not in ALLOWED_CAPABILITIES:
        raise ValueError(f"capability is not allowed: {capability!r}")
    if str(plan.get("target") or "") != str(inspection.get("target") or "synthetic.local.worker"):
        raise ValueError("plan target did not match the inspected target")
    if not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise ValueError("plan has no steps")
    plan["verification"] = plan.get("verification") if isinstance(plan.get("verification"), dict) else {}
    plan["risk"] = "sandbox_only"
    plan["source"] = "openai" if plan.get("source") != "offline_fallback" else plan["source"]
    return plan


def generate_plan(alert: dict[str, Any], inspection: dict[str, Any]) -> dict[str, Any]:
    """Generate a plan from the configured model, or work offline safely."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _validate(_fallback(alert, inspection), inspection)
    model = os.getenv("OPENAI_MODEL", "gpt-5.6").strip() or "gpt-5.6"
    system = (
        "You are a constrained incident-remediation planner. Return JSON only with keys "
        "capability,target,reasoning,steps,verification,risk. You may select only "
        "restart_sandbox_worker or terminate_sandbox_worker. The target is synthetic and "
        "local; never invent commands, credentials, hosts, or capabilities. Verification "
        "must require a healthy worker heartbeat younger than three seconds."
    )
    user = json.dumps({"alert": alert, "inspection": inspection}, sort_keys=True)
    request_body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))) as response:
            plan = _extract_json(json.loads(response.read().decode("utf-8")))
        return _validate(plan, inspection)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
        # A missing/unavailable model never gets to execute an unvalidated plan.
        return _validate(_fallback(alert, inspection), inspection)
