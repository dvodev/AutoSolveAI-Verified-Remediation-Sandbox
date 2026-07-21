"""Data-driven capability registry for the intentionally tiny sandbox."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_capabilities() -> dict[str, dict[str, Any]]:
    path = Path(__file__).with_name("capabilities.json")
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, list):
        raise ValueError("capability manifest must be a list")
    result = {}
    for item in values:
        if not isinstance(item, dict) or not item.get("name"):
            raise ValueError("capability manifest contains an invalid entry")
        result[str(item["name"])] = item
    return result
