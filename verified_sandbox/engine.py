"""Workflow state machine and append-only audit events for the demo."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .planner import generate_plan
from .sandbox import IncidentSandbox


class RemediationEngine:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.audit_path = self.data_dir / "audit.jsonl"
        self.sandbox = IncidentSandbox(self.data_dir / "sandbox")
        self.lock = threading.RLock()
        self.runs: dict[str, dict[str, Any]] = {}
        self.sandbox.reset()

    def _audit(self, run_id: str, event: str, **details: Any) -> None:
        record = {"timestamp": time.time(), "run_id": run_id, "event": event, **details}
        with self.audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")

    def create_alert(self, alert: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            current = self.sandbox.start(hung=True)
            run_id = str(uuid.uuid4())
            alert = alert or {
                "source": "synthetic_datadog",
                "alert_id": f"demo-{run_id[:8]}",
                "title": "worker heartbeat stale",
                "severity": "high",
                "service": "checkout-worker",
                "message": "checkout-worker heartbeat exceeded the allowed threshold",
            }
            run = {"run_id": run_id, "status": "alerted", "alert": alert, "inspection": current, "audit": []}
            self.runs[run_id] = run
            self._audit(run_id, "alert_received", alert=alert)
            return run

    def plan(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            run = self.runs[run_id]
            run["inspection"] = self.sandbox.inspect()
            run["plan"] = generate_plan(run["alert"], run["inspection"])
            run["status"] = "planned"
            self._audit(run_id, "plan_generated", plan=run["plan"])
            return run

    def approve(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            run = self.runs[run_id]
            if run.get("status") != "planned":
                raise ValueError("only planned runs can be approved")
            run["status"] = "approved"
            run["approved_at"] = time.time()
            self._audit(run_id, "human_approved", actor="demo-operator")
            return run

    def execute(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            run = self.runs[run_id]
            if run.get("status") != "approved":
                raise ValueError("approval is required before execution")
            plan = run.get("plan") or {}
            run["status"] = "executing"
            self._audit(run_id, "execution_started", capability=plan.get("capability"))
            if plan.get("capability") == "restart_sandbox_worker":
                self.sandbox.start(hung=False)
            elif plan.get("capability") == "terminate_sandbox_worker":
                self.sandbox.stop()
            else:
                raise ValueError("validated plan capability is not executable")
            verification = self.sandbox.inspect()
            passed = bool(verification.get("healthy"))
            run["verification"] = verification
            run["status"] = "verified" if passed else "failed"
            run["result"] = {"status": "VERIFIED" if passed else "FAILED", "verification": verification}
            self._audit(run_id, "verification_completed", passed=passed, verification=verification)
            return run

    def state(self) -> dict[str, Any]:
        with self.lock:
            return {"runs": list(self.runs.values()), "sandbox": self.sandbox.inspect()}

    def close(self) -> None:
        self.sandbox.close()
