"""Entitlement-aware OpenAI model selection without hardcoded account assumptions."""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from typing import Any


PREFERRED_MODELS = ("gpt-5.6", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5", "gpt-5-mini", "gpt-4o-mini")
_CACHE: dict[str, tuple[str, ...]] = {}
_LOCK = threading.RLock()


def _catalog(api_key: str) -> tuple[str, ...]:
    cache_key = api_key[:12]
    with _LOCK:
        if cache_key in _CACHE: return _CACHE[cache_key]
    request = urllib.request.Request("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(request, timeout=float(os.getenv("OPENAI_MODEL_DISCOVERY_TIMEOUT_SECONDS", "5"))) as response:
            payload = json.loads(response.read().decode("utf-8")); values = tuple(str(item.get("id")) for item in payload.get("data", []) if isinstance(item, dict) and item.get("id"))
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError, OSError):
        values = ()
    with _LOCK: _CACHE[cache_key] = values
    return values


def resolve_model(api_key: str, requested: str | None = None) -> str:
    requested = str(requested or os.getenv("OPENAI_MODEL", "gpt-5.6")).strip() or "gpt-5.6"
    if os.getenv("OPENAI_MODEL_DISCOVERY", "1").strip().lower() in {"0", "false", "off"}: return requested
    # Explicit non-frontier model choices are respected; discovery is needed
    # for the GPT-5.6 default because access varies by account/project.
    if not requested.startswith("gpt-5.6"): return requested
    available = set(_catalog(api_key))
    if requested in available: return requested
    for candidate in PREFERRED_MODELS:
        if candidate in available: return candidate
    return requested


def clear_model_cache() -> None:
    with _LOCK: _CACHE.clear()
