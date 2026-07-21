"""Validation and canonicalization rules at the model/execution boundary."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from .models import CapabilitySpec, RemediationPlan, TargetRef


class ContractError(ValueError):
    """A plan or event failed a boundary contract."""


SECRET_KEY_RE = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key|authorization)")
TARGET_ID_RE = re.compile(r"^[A-Za-z0-9_.:/-]{3,160}$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def redact(value: Any, *, replacement: str = "[REDACTED]") -> Any:
    if isinstance(value, Mapping):
        return {str(key): replacement if SECRET_KEY_RE.search(str(key)) else redact(item, replacement=replacement) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, replacement=replacement) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item, replacement=replacement) for item in value)
    if isinstance(value, str):
        value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._-]+", r"\1[REDACTED]", value)
        value = re.sub(r"(?i)(password|token|secret)\s*[=:]\s*[^\s,;]+", r"\1=[REDACTED]", value)
    return value


def validate_target(target: TargetRef) -> None:
    if not TARGET_ID_RE.fullmatch(target.target_id):
        raise ContractError("target id is not a safe identifier")
    if target.environment != "sandbox" or target.provider != "local-simulator":
        raise ContractError("this submission can execute only against the synthetic local target")
    if target.target_type != "synthetic.worker":
        raise ContractError("unsupported target type")


def validate_capability(spec: CapabilitySpec, registry: Mapping[str, CapabilitySpec]) -> None:
    if spec.name not in registry:
        raise ContractError(f"capability is not registered: {spec.name}")
    if not spec.description or not spec.verification:
        raise ContractError(f"capability is incomplete: {spec.name}")


def validate_plan(plan: RemediationPlan, registry: Mapping[str, CapabilitySpec]) -> None:
    validate_target(plan.target)
    spec = registry.get(plan.capability)
    if spec is None:
        raise ContractError(f"plan capability is not registered: {plan.capability}")
    validate_capability(spec, registry)
    if plan.risk != spec.risk:
        raise ContractError("plan risk does not match capability manifest")
    if not plan.steps:
        raise ContractError("plan must contain at least one step")
    if not plan.verification:
        raise ContractError("plan must contain an independent verification rule")
    if not 0 <= float(plan.confidence) <= 1:
        raise ContractError("confidence must be between zero and one")
    if plan.capability == "observe_only" and spec.mutates:
        raise ContractError("observe_only cannot be marked mutating")


def validate_event(event: Mapping[str, Any]) -> None:
    required = {"timestamp", "run_id", "event", "hash", "previous_hash"}
    missing = sorted(required.difference(event))
    if missing:
        raise ContractError(f"audit event missing keys: {', '.join(missing)}")
    if len(str(event["hash"])) != 64 or len(str(event["previous_hash"])) != 64:
        raise ContractError("audit hash fields must be sha256 values")
