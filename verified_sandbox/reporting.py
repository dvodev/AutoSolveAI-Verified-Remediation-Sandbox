"""Judge-facing reports: concise summary, detailed markdown, and JSON export."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .contracts import redact
from .evidence import evidence_summary


@dataclass(frozen=True)
class ReportSection:
    title: str
    body: str
    status: str = "info"


@dataclass
class RunReport:
    title: str
    run_id: str
    status: str
    generated_at: str
    sections: list[ReportSection]
    metrics: dict[str, Any]
    raw: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"title": self.title, "run_id": self.run_id, "status": self.status, "generated_at": self.generated_at, "sections": [section.__dict__ for section in self.sections], "metrics": self.metrics, "raw": redact(self.raw)}


def _status_icon(status: str) -> str:
    return {"verified": "✅", "failed": "❌", "shadowed": "🟡", "approved": "🟢"}.get(str(status).lower(), "🔵")


def build_report(run: Mapping[str, Any], *, audit_chain: Mapping[str, Any] | None = None, adapter_health: Mapping[str, Any] | None = None) -> RunReport:
    status = str(run.get("status") or "unknown")
    plan = run.get("plan") if isinstance(run.get("plan"), Mapping) else {}
    policy = run.get("policy") if isinstance(run.get("policy"), Mapping) else {}
    verification = run.get("verification_report") if isinstance(run.get("verification_report"), Mapping) else {}
    before = run.get("inspection") if isinstance(run.get("inspection"), Mapping) else {}
    after = run.get("verification") if isinstance(run.get("verification"), Mapping) else {}
    sections = [
        ReportSection("Outcome", f"{_status_icon(status)} **{status.upper()}** for `{run.get('run_id')}`", "ok" if status in {"verified", "shadowed"} else status),
        ReportSection("Alert", f"**{run.get('alert', {}).get('title', 'Alert')}** — {run.get('alert', {}).get('message', '')}"),
        ReportSection("Target evidence", f"Target `{before.get('target')}` on {before.get('os', {}).get('system', 'unknown')} with PID `{before.get('pid')}`. Healthy before: `{before.get('healthy')}`; after: `{after.get('healthy')}`."),
        ReportSection("AI plan", f"Capability `{plan.get('capability')}` from `{plan.get('source')}`. Reasoning: {plan.get('reasoning', '')}"),
        ReportSection("Policy", f"Decision `{policy.get('decision')}`. Approval required: `{policy.get('requires_approval')}`."),
        ReportSection("Verification", f"Passed: `{verification.get('passed')}`. Checks: {len(verification.get('checks') or [])}."),
        ReportSection("Audit integrity", f"Hash chain valid: `{(audit_chain or {}).get('valid')}`; events: `{(audit_chain or {}).get('events')}`."),
        ReportSection("Adapters", f"{len(adapter_health or {})} adapter endpoints available."),
    ]
    evidence = run.get("evidence") if isinstance(run.get("evidence"), list) else []
    metrics = {"evidence": evidence_summary([]), "evidence_count": len(evidence), "verification_checks": len(verification.get("checks") or [])}
    return RunReport("Verified Remediation Run", str(run.get("run_id") or ""), status, datetime.now(timezone.utc).isoformat(), sections, metrics, dict(run))


def render_markdown(report: RunReport) -> str:
    lines = [f"# {report.title}", "", f"**Run:** `{report.run_id}`  ", f"**Status:** {_status_icon(report.status)} `{report.status}`  ", f"**Generated:** `{report.generated_at}`", ""]
    for section in report.sections:
        lines.extend([f"## {section.title}", "", section.body, ""])
    lines.extend(["## Machine-readable metrics", "", "```json", json.dumps(report.metrics, indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines)


def render_html(report: RunReport) -> str:
    rows = "".join(f"<section><h2>{section.title}</h2><p>{section.body}</p></section>" for section in report.sections)
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{report.title}</title><style>body{{font:16px system-ui;max-width:850px;margin:40px auto;background:#0b1020;color:#edf2ff}}section{{background:#151d35;padding:16px;margin:12px 0;border-radius:10px}}h2{{color:#6ee7b7}}</style></head><body><h1>{report.title}</h1>{rows}</body></html>"


def score_report(report: RunReport) -> dict[str, Any]:
    checks = {
        "structured_plan": any(section.title == "AI plan" for section in report.sections),
        "approval_policy": any(section.title == "Policy" for section in report.sections),
        "independent_verification": any(section.title == "Verification" for section in report.sections),
        "audit_integrity": any(section.title == "Audit integrity" for section in report.sections),
        "target_evidence": any(section.title == "Target evidence" for section in report.sections),
    }
    passed = sum(checks.values()); total = len(checks)
    return {"score": passed / total if total else 0, "passed": passed, "total": total, "checks": checks}


def batch_summary(reports: Iterable[RunReport]) -> dict[str, Any]:
    values = list(reports); statuses = {}
    for report in values:
        statuses[report.status] = statuses.get(report.status, 0) + 1
    return {"runs": len(values), "statuses": statuses, "verified": sum(report.status == "verified" for report in values), "scores": [score_report(report) for report in values]}
