"""AI planner with strict schema validation and a deterministic offline mode."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .registry import load_capabilities
from .model_selection import resolve_model
from .capability_router import CapabilityRouter


def _fallback(alert: dict[str, Any], inspection: dict[str, Any]) -> dict[str, Any]:
    route = CapabilityRouter().decide(alert, inspection, load_capabilities())
    capability = route.selected
    if capability == "observe_only": reasoning = "The target is already healthy; verify it without changing state."
    elif capability == "terminate_sandbox_worker": reasoning = "The alert indicates an unresponsive process; terminate the disposable worker and prove it is no longer alive."
    else: reasoning = "The target is unhealthy; restart the disposable worker and prove a fresh healthy heartbeat."
    return {
        "capability": capability,
        "target": inspection.get("target", "synthetic.local.worker"),
        "reasoning": reasoning,
        "steps": ["inspect_worker", capability],
        "verification": {"healthy": capability != "terminate_sandbox_worker", "alive": capability != "terminate_sandbox_worker", "heartbeat_age_seconds_less_than": 3},
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
    if capability not in load_capabilities():
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
    model = resolve_model(api_key, os.getenv("OPENAI_MODEL", "gpt-5.6"))
    route = CapabilityRouter().decide(alert, inspection, load_capabilities())
    system = (
        "You are a constrained incident-remediation planner. Return JSON only with keys "
        "capability,target,reasoning,steps,verification,risk. You may select only the "
        "capabilities listed in the supplied manifest. The target is synthetic and "
        "local; never invent commands, credentials, hosts, or capabilities. Verification "
        "must require a healthy worker heartbeat younger than three seconds. Use the supplied routing recommendation as a strong safety prior: "
        "when the alert explicitly says an application is unresponsive, stuck, or will not close, select the recommended termination capability; "
        "do not substitute a restart merely because the synthetic worker is unhealthy."
    )
    user = json.dumps({"alert": alert, "inspection": inspection, "routing_recommendation": route.as_dict(), "capabilities": load_capabilities()}, sort_keys=True)
    request_body = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    # GPT-5-family models currently reject non-default temperature values.
    # Keep deterministic sampling for compatible legacy models, while making
    # the model selection fully data/configuration driven.
    if not model.lower().startswith("gpt-5"):
        request_body["temperature"] = 0
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))) as response:
            plan = _extract_json(json.loads(response.read().decode("utf-8")))
        validated = _validate(plan, inspection)
        validated["model"] = model
        return validated
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
        # A missing/unavailable model never gets to execute an unvalidated plan.
        return _validate(_fallback(alert, inspection), inspection)
