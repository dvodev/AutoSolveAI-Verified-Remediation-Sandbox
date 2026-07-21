"""Portable run-bundle export and replay verification."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .contracts import canonical_json, fingerprint, redact
from .evidence import diff
from .storage import JsonlStore


@dataclass
class RunBundle:
    format_version: str
    exported_at: float
    run: dict[str, Any]
    events: list[dict[str, Any]]
    chain: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"format_version": self.format_version, "exported_at": self.exported_at, "run": self.run, "events": self.events, "chain": self.chain, "metadata": self.metadata}


class BundleExporter:
    VERSION = "1.0"

    def __init__(self, audit: JsonlStore) -> None:
        self.audit = audit

    def build(self, run: Mapping[str, Any], *, metadata: Mapping[str, Any] | None = None) -> RunBundle:
        run_id = run.get("run_id")
        events = self.audit.query(run_id=run_id)
        return RunBundle(self.VERSION, time.time(), redact(dict(run)), redact_records(events), self.audit.verify_chain(), dict(metadata or {}))

    def write(self, bundle: RunBundle, destination: str | Path) -> Path:
        path = Path(destination); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(bundle.as_dict(), indent=2, sort_keys=True, default=str), encoding="utf-8"); return path


def redact_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [redact(record) for record in records]


class BundleValidator:
    required = {"format_version", "exported_at", "run", "events", "chain"}

    def validate(self, bundle: Mapping[str, Any]) -> dict[str, Any]:
        missing = sorted(self.required.difference(bundle))
        errors: list[str] = []
        if missing:
            errors.append("missing:" + ",".join(missing))
        if str(bundle.get("format_version")) != BundleExporter.VERSION:
            errors.append("unsupported_format")
        if not isinstance(bundle.get("run"), Mapping):
            errors.append("run_not_object")
        if not isinstance(bundle.get("events"), list):
            errors.append("events_not_list")
        chain = bundle.get("chain") if isinstance(bundle.get("chain"), Mapping) else {}
        if chain.get("valid") is not True:
            errors.append("invalid_audit_chain")
        return {"valid": not errors, "errors": errors, "fingerprint": fingerprint(bundle) if not errors else None}

    def load(self, path: str | Path) -> dict[str, Any]:
        value = json.loads(Path(path).read_text(encoding="utf-8")); result = self.validate(value)
        if not result["valid"]:
            raise ValueError("invalid run bundle: " + "; ".join(result["errors"]))
        return value


def summarize_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    run = bundle.get("run") if isinstance(bundle.get("run"), Mapping) else {}
    execution = run.get("execution") if isinstance(run.get("execution"), Mapping) else run.get("result") or {}
    return {"run_id": run.get("run_id"), "status": run.get("status"), "capability": (run.get("plan") or {}).get("capability"), "verification": execution.get("verification") or run.get("verification_report"), "event_count": len(bundle.get("events") or []), "chain_valid": (bundle.get("chain") or {}).get("valid")}


def compare_bundles(first: Mapping[str, Any], second: Mapping[str, Any]) -> dict[str, Any]:
    first_run = first.get("run") if isinstance(first.get("run"), Mapping) else {}
    second_run = second.get("run") if isinstance(second.get("run"), Mapping) else {}
    return {"same_capability": (first_run.get("plan") or {}).get("capability") == (second_run.get("plan") or {}).get("capability"), "status_transition": [first_run.get("status"), second_run.get("status")], "changed_run_fields": [item.__dict__ for item in diff(first_run, second_run) if item.changed], "first": summarize_bundle(first), "second": summarize_bundle(second)}
