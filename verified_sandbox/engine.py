"""Workflow state machine and append-only audit events for the demo."""

from __future__ import annotations

import json
import hashlib
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .planner import generate_plan
from .policy import evaluate
from .registry import load_capabilities
from .scenarios import get_scenario
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
        self.capabilities = load_capabilities()
        self.previous_audit_hash = "0" * 64

    def _audit(self, run_id: str, event: str, **details: Any) -> None:
        record = {"timestamp": time.time(), "run_id": run_id, "event": event, "previous_hash": self.previous_audit_hash, **details}
        record["hash"] = hashlib.sha256(json.dumps(record, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        self.previous_audit_hash = record["hash"]
        with self.audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")

    def create_alert(self, alert: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            alert = dict(alert or {})
            scenario_name, scenario = get_scenario(alert.pop("scenario", None))
            mode = str(alert.pop("mode", "approval") or "approval").lower()
            worker_mode = scenario["worker_mode"]
            current = self.sandbox.start(hung=worker_mode == "hung") if worker_mode != "missing" else (self.sandbox.stop() or self.sandbox.inspect())
            run_id = str(uuid.uuid4())
            alert = {
                "source": "synthetic_datadog",
                "alert_id": f"demo-{run_id[:8]}",
                "title": scenario["alert_title"],
                "severity": "high",
                "service": "checkout-worker",
                "message": scenario["description"],
                **alert,
            }
            run = {"run_id": run_id, "status": "alerted", "mode": mode, "scenario": scenario_name, "alert": alert, "inspection": current, "audit": []}
            self.runs[run_id] = run
            self._audit(run_id, "alert_received", scenario=scenario_name, mode=mode, alert=alert, inspection=current)
            return run

    def plan(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            run = self.runs[run_id]
            run["inspection"] = self.sandbox.inspect()
            run["plan"] = generate_plan(run["alert"], run["inspection"])
            run["policy"] = evaluate(run["plan"], run.get("mode", "approval"))
            if not run["policy"].get("allowed"):
                raise ValueError(run["policy"]["reason"])
            run["status"] = "planned"
            self._audit(run_id, "plan_generated", plan=run["plan"], policy=run["policy"], capabilities=list(self.capabilities))
            return run

    def approve(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            run = self.runs[run_id]
            if run.get("mode") == "shadow":
                run["status"] = "shadow_ready"
                self._audit(run_id, "shadow_mode_selected", actor="demo-operator")
                return run
            if run.get("status") != "planned":
                raise ValueError("only planned runs can be approved")
            run["status"] = "approved"
            run["approved_at"] = time.time()
            self._audit(run_id, "human_approved", actor="demo-operator")
            return run

    def execute(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            run = self.runs[run_id]
            if run.get("mode") == "shadow":
                run["status"] = "shadowed"
                run["verification"] = self.sandbox.inspect()
                run["result"] = {"status": "SHADOW_ONLY", "verification": run["verification"]}
                self._audit(run_id, "shadow_execution_skipped", verification=run["verification"])
                return run
            if run.get("status") != "approved":
                raise ValueError("approval is required before execution")
            plan = run.get("plan") or {}
            run["status"] = "executing"
            self._audit(run_id, "execution_started", capability=plan.get("capability"))
            if plan.get("capability") == "observe_only":
                pass
            elif plan.get("capability") == "restart_sandbox_worker":
                self.sandbox.start(hung=False)
            elif plan.get("capability") == "terminate_sandbox_worker":
                self.sandbox.stop()
            else:
                raise ValueError("validated plan capability is not executable")
            verification = self.sandbox.inspect()
            passed = (not verification.get("alive")) if plan.get("capability") == "terminate_sandbox_worker" else bool(verification.get("healthy"))
            run["verification"] = verification
            run["status"] = "verified" if passed else "failed"
            run["result"] = {"status": "VERIFIED" if passed else "FAILED", "verification": verification}
            self._audit(run_id, "verification_completed", passed=passed, verification=verification)
            return run

    def rollback(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            run = self.runs[run_id]
            self.sandbox.start(hung=False)
            verification = self.sandbox.inspect()
            run["rollback"] = {"status": "VERIFIED" if verification.get("healthy") else "FAILED", "verification": verification}
            self._audit(run_id, "rollback_completed", rollback=run["rollback"])
            return run

    def replay(self, run_id: str) -> list[dict[str, Any]]:
        if not self.audit_path.exists():
            return []
        return [json.loads(line) for line in self.audit_path.read_text(encoding="utf-8").splitlines() if line and json.loads(line).get("run_id") == run_id]

    def state(self) -> dict[str, Any]:
        with self.lock:
            return {"runs": list(self.runs.values()), "sandbox": self.sandbox.inspect(), "capabilities": self.capabilities}

    def close(self) -> None:
        self.sandbox.close()
