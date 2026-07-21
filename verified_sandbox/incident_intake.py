"""Provider-neutral incident intake and correlation for the sandbox edition.

This is the safe, synthetic counterpart of the production intake boundary:
every provider is normalized into one envelope before planning, deduplicated
by a stable fingerprint, and retained as an inspectable lifecycle record.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

from .contracts import canonical_json, redact
from .models import Alert


SEVERITY_ORDER = {"debug": 0, "info": 1, "notice": 2, "warning": 3, "warn": 3, "error": 4, "critical": 5, "high": 5, "fatal": 6}


def normalize_severity(value: Any) -> str:
    value = str(value or "warning").strip().lower()
    return "warning" if value == "warn" else value if value in SEVERITY_ORDER else "warning"


def _labels(value: Any) -> dict[str, str]:
    if isinstance(value, Mapping):
        return {str(k): str(v) for k, v in value.items()}
    result: dict[str, str] = {}
    for item in value or ():
        text = str(item)
        if ":" in text:
            key, val = text.split(":", 1); result[key.strip()] = val.strip()
    return result


@dataclass(frozen=True)
class IncidentEnvelope:
    incident_id: str
    fingerprint: str
    source: str
    title: str
    message: str
    severity: str
    service: str
    target_hint: str | None
    labels: dict[str, str]
    received_at: float
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return redact({"incident_id": self.incident_id, "fingerprint": self.fingerprint, "source": self.source, "title": self.title, "message": self.message, "severity": self.severity, "service": self.service, "target_hint": self.target_hint, "labels": self.labels, "received_at": self.received_at, "raw": self.raw})


@dataclass(frozen=True)
class IntakeResult:
    accepted: bool
    duplicate: bool
    correlated_incident_id: str | None
    envelope: IncidentEnvelope
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"accepted": self.accepted, "duplicate": self.duplicate, "correlated_incident_id": self.correlated_incident_id, "envelope": self.envelope.as_dict(), "reason": self.reason}


class IncidentNormalizer:
    """Normalize common webhook shapes without provider SDK dependencies."""

    def normalize(self, payload: Mapping[str, Any], source: str = "synthetic") -> IncidentEnvelope:
        source = str(source or payload.get("source") or "synthetic").lower()
        body = payload.get("event") if isinstance(payload.get("event"), Mapping) else payload
        labels = _labels(body.get("labels") or body.get("tags") or body.get("details"))
        title = body.get("title") or body.get("monitor_name") or body.get("summary") or body.get("alertname") or body.get("short_description") or "Unclassified incident"
        message = body.get("message") or body.get("text") or body.get("description") or body.get("annotations", {}).get("description") or "Incident received"
        service = body.get("service") or labels.get("service") or labels.get("job") or body.get("cmdb_ci") or "unknown-service"
        target = body.get("target") or body.get("target_id") or labels.get("target") or labels.get("instance") or body.get("resource_id")
        severity = normalize_severity(body.get("severity") or body.get("priority") or labels.get("severity"))
        stable = {"source": source, "title": str(title), "service": str(service), "target": target, "labels": labels}
        digest = hashlib.sha256(canonical_json(stable).encode()).hexdigest()[:20]
        incident_id = str(body.get("incident_id") or body.get("alert_id") or body.get("id") or body.get("fingerprint") or f"INC-{digest[:10].upper()}")
        return IncidentEnvelope(incident_id, digest, source, str(title), str(message), severity, str(service), str(target) if target else None, labels, time.time(), dict(payload))

    def to_alert(self, envelope: IncidentEnvelope) -> Alert:
        return Alert.from_payload({"alert_id": envelope.incident_id, "source": envelope.source, "title": envelope.title, "message": envelope.message, "severity": envelope.severity, "service": envelope.service, "labels": envelope.labels, "raw": envelope.raw})


class IncidentIntake:
    """Thread-safe dedupe and correlation store with bounded history."""

    def __init__(self, *, dedupe_seconds: float = 300.0, max_records: int = 1000) -> None:
        self.dedupe_seconds = float(dedupe_seconds); self.max_records = int(max_records)
        self._records: dict[str, IncidentEnvelope] = {}; self._by_fingerprint: dict[str, str] = {}; self._lock = threading.RLock()

    def ingest(self, payload: Mapping[str, Any], source: str = "synthetic") -> IntakeResult:
        envelope = IncidentNormalizer().normalize(payload, source)
        with self._lock:
            previous_id = self._by_fingerprint.get(envelope.fingerprint)
            previous = self._records.get(previous_id) if previous_id else None
            if previous and envelope.received_at - previous.received_at <= self.dedupe_seconds:
                return IntakeResult(False, True, previous.incident_id, envelope, "duplicate fingerprint within dedupe window")
            correlated = self._correlate(envelope)
            self._records[envelope.incident_id] = envelope; self._by_fingerprint[envelope.fingerprint] = envelope.incident_id
            while len(self._records) > self.max_records:
                oldest = min(self._records.values(), key=lambda item: item.received_at); self._records.pop(oldest.incident_id, None); self._by_fingerprint.pop(oldest.fingerprint, None)
            return IntakeResult(True, False, correlated, envelope, "accepted")

    def _correlate(self, envelope: IncidentEnvelope) -> str | None:
        candidates = [item for item in self._records.values() if item.service == envelope.service and item.incident_id != envelope.incident_id]
        if not candidates: return None
        candidate = max(candidates, key=lambda item: item.received_at)
        return candidate.incident_id if envelope.received_at - candidate.received_at <= self.dedupe_seconds else None

    def get(self, incident_id: str) -> IncidentEnvelope | None:
        with self._lock: return self._records.get(str(incident_id))

    def list(self, *, service: str | None = None, severity_at_least: str | None = None) -> list[IncidentEnvelope]:
        with self._lock:
            minimum = SEVERITY_ORDER.get(normalize_severity(severity_at_least), 0) if severity_at_least else 0
            return sorted([item for item in self._records.values() if (not service or item.service == service) and SEVERITY_ORDER.get(item.severity, 0) >= minimum], key=lambda item: item.received_at, reverse=True)

    def snapshot(self) -> dict[str, Any]:
        values = self.list(); return {"count": len(values), "incidents": [item.as_dict() for item in values], "dedupe_seconds": self.dedupe_seconds}
