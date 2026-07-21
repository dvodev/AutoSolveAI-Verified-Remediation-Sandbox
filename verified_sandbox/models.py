"""Typed domain objects for the incident-remediation workbench.

The demo deliberately keeps the domain model independent from the HTTP layer.
That makes every decision serializable, replayable, and testable without a
browser or a live model provider.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStatus(str, Enum):
    ALERTED = "alerted"
    PLANNING = "planning"
    PLANNED = "planned"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    EXECUTING = "executing"
    VERIFIED = "verified"
    FAILED = "failed"
    SHADOWED = "shadowed"
    ROLLED_BACK = "rolled_back"


class EvidenceKind(str, Enum):
    ALERT = "alert"
    INVENTORY = "inventory"
    LOG = "log"
    COMMAND = "command"
    VERIFICATION = "verification"
    POLICY = "policy"
    AUDIT = "audit"


@dataclass(frozen=True)
class TargetRef:
    target_id: str
    target_type: str = "synthetic.worker"
    display_name: str = "Synthetic Worker"
    environment: str = "sandbox"
    provider: str = "local-simulator"
    attributes: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Alert:
    alert_id: str
    source: str
    title: str
    message: str
    severity: str
    service: str
    received_at: str = field(default_factory=now_iso)
    labels: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "Alert":
        return cls(
            alert_id=str(payload.get("alert_id") or f"alert-{uuid4().hex[:10]}"),
            source=str(payload.get("source") or "synthetic-monitor"),
            title=str(payload.get("title") or payload.get("name") or "Unclassified alert"),
            message=str(payload.get("message") or payload.get("description") or ""),
            severity=str(payload.get("severity") or "warning").lower(),
            service=str(payload.get("service") or "unknown-service"),
            labels={str(k): str(v) for k, v in dict(payload.get("labels") or {}).items()},
            raw=dict(payload),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    kind: str
    name: str
    value: Any
    source: str
    observed_at: str = field(default_factory=now_iso)
    confidence: float = 1.0
    redacted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, kind: str | EvidenceKind, name: str, value: Any, source: str, **metadata: Any) -> "Evidence":
        return cls(uuid4().hex, str(kind), name, value, source, metadata=metadata)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationRule:
    name: str
    predicate: str
    expected: Any = True
    timeout_seconds: float = 5.0
    required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    label: str
    description: str
    risk: str
    mutates: bool
    verification: str
    supports: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CapabilitySpec":
        return cls(
            name=str(value["name"]), label=str(value.get("label") or value["name"]),
            description=str(value.get("description") or ""), risk=str(value.get("risk") or "unknown"),
            mutates=bool(value.get("mutates")), verification=str(value.get("verification") or ""),
            supports=tuple(str(x) for x in value.get("supports") or ()),
            inputs=tuple(str(x) for x in value.get("inputs") or ()),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RemediationPlan:
    plan_id: str
    run_id: str
    capability: str
    target: TargetRef
    reasoning: str
    steps: list[str]
    verification: list[VerificationRule]
    risk: str
    source: str
    model: str | None = None
    confidence: float = 0.0
    requires_approval: bool = True
    rollback_capability: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["target"] = self.target.as_dict()
        value["verification"] = [rule.as_dict() for rule in self.verification]
        return value


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    decision: str
    reason: str
    requires_approval: bool
    mode: str
    risk: str
    controls: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionResult:
    status: str
    capability: str
    target: TargetRef
    started_at: str
    finished_at: str
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    verification: list[dict[str, Any]] = field(default_factory=list)
    rollback: dict[str, Any] | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["target"] = self.target.as_dict()
        return value


@dataclass
class RunRecord:
    run_id: str
    alert: Alert
    target: TargetRef
    status: str = RunStatus.ALERTED.value
    mode: str = "approval"
    inspection: list[Evidence] = field(default_factory=list)
    plan: RemediationPlan | None = None
    policy: PolicyDecision | None = None
    execution: ExecutionResult | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    approved_by: str | None = None
    tags: dict[str, str] = field(default_factory=dict)

    def touch(self, status: str | None = None) -> None:
        if status:
            self.status = status
        self.updated_at = now_iso()

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["alert"] = self.alert.as_dict()
        value["target"] = self.target.as_dict()
        value["inspection"] = [item.as_dict() for item in self.inspection]
        value["plan"] = self.plan.as_dict() if self.plan else None
        value["policy"] = self.policy.as_dict() if self.policy else None
        value["execution"] = self.execution.as_dict() if self.execution else None
        return value
