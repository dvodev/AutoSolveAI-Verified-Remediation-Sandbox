"""Execution-boundary security helpers for the public sandbox.

These controls are intentionally stricter than the demo needs. They make the
security story visible to reviewers without pretending the repository is a
production secrets-management system.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from .contracts import ContractError, canonical_json, redact


UNSAFE_SHELL_RE = re.compile(r"(?i)(rm\s+-rf|format\s+[a-z]:|curl[^|]+\|\s*(sh|bash)|invoke-expression|powershell\s+-enc|chmod\s+777)")
SECRET_ASSIGNMENT_RE = re.compile(r"(?i)\b(?:password|token|secret|api[_-]?key)\s*[:=]")
SECRET_KEY_RE = re.compile(r"(?i)^(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|authorization)$")
ALLOWED_SCHEMES = {"http", "https"}


@dataclass(frozen=True)
class SecurityFinding:
    rule: str
    severity: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "severity": self.severity, "message": self.message, "evidence": redact(self.evidence)}


@dataclass(frozen=True)
class SecurityDecision:
    allowed: bool
    reason: str
    findings: tuple[SecurityFinding, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "reason": self.reason, "findings": [item.as_dict() for item in self.findings]}


def inspect_text(text: str, *, field_name: str = "text") -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    if UNSAFE_SHELL_RE.search(str(text or "")):
        findings.append(SecurityFinding("unsafe_command_shape", "high", "text contains a disallowed shell pattern", {field_name: text}))
    if SECRET_ASSIGNMENT_RE.search(str(text or "")):
        findings.append(SecurityFinding("literal_secret", "high", "text appears to contain a secret assignment", {field_name: text}))
    return findings


def inspect_mapping(value: Mapping[str, Any], *, path: str = "root") -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for key, item in value.items():
        current = f"{path}.{key}"
        if SECRET_KEY_RE.search(str(key)):
            findings.append(SecurityFinding("secret_field", "high", "mapping contains a secret-shaped key", {"path": current}))
        if isinstance(item, Mapping):
            findings.extend(inspect_mapping(item, path=current))
        elif isinstance(item, str):
            findings.extend(inspect_text(item, field_name=current))
    return findings


def authorize_payload(value: Mapping[str, Any], *, target_environment: str = "sandbox") -> SecurityDecision:
    findings = inspect_mapping(value)
    if target_environment != "sandbox":
        findings.append(SecurityFinding("environment_boundary", "high", "execution target is outside the sandbox", {"environment": target_environment}))
    blocked = [item for item in findings if item.severity in {"high", "critical"}]
    return SecurityDecision(not blocked, "payload accepted" if not blocked else "payload blocked by security gate", tuple(findings))


def validate_url(url: str, *, allowed_hosts: set[str] | None = None) -> SecurityDecision:
    from urllib.parse import urlparse
    parsed = urlparse(str(url or ""))
    findings: list[SecurityFinding] = []
    if parsed.scheme not in ALLOWED_SCHEMES:
        findings.append(SecurityFinding("url_scheme", "high", "only HTTP(S) URLs are allowed", {"url": url}))
    if not parsed.hostname:
        findings.append(SecurityFinding("url_host", "high", "URL must contain a host", {"url": url}))
    if allowed_hosts and parsed.hostname not in allowed_hosts:
        findings.append(SecurityFinding("url_allowlist", "high", "URL host is not allowlisted", {"host": parsed.hostname}))
    return SecurityDecision(not findings, "URL accepted" if not findings else "URL blocked", tuple(findings))


class PlanSigner:
    """HMAC signer for an in-memory demo plan envelope."""

    def __init__(self, key: bytes | None = None) -> None:
        self.key = key or os.getenv("SANDBOX_PLAN_SIGNING_KEY", "demo-only-plan-key").encode("utf-8")

    def sign(self, plan: Mapping[str, Any]) -> str:
        return hmac.new(self.key, canonical_json(plan).encode("utf-8"), hashlib.sha256).hexdigest()

    def verify(self, plan: Mapping[str, Any], signature: str) -> bool:
        return hmac.compare_digest(self.sign(plan), str(signature or ""))

    def envelope(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        return {"plan": redact(dict(plan)), "signature": self.sign(plan), "algorithm": "HMAC-SHA256"}

    def require_valid(self, plan: Mapping[str, Any], signature: str) -> None:
        if not self.verify(plan, signature):
            raise ContractError("plan signature is invalid")
