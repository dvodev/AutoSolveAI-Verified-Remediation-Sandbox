"""Judge-friendly command line interface for scripted demonstrations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import RemediationEngine
from .orchestrator import RemediationOrchestrator


def dump(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="verified-remediation", description="Synthetic verified incident remediation workbench")
    root.add_argument("--data-dir", default="data", help="durable audit/run directory")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("workflow", help="show workflow steps and adapter health")
    alert = commands.add_parser("alert", help="create a synthetic alert")
    alert.add_argument("--scenario", default="stale_heartbeat")
    alert.add_argument("--mode", choices=("approval", "shadow"), default="approval")
    plan = commands.add_parser("plan", help="generate a plan for a run")
    plan.add_argument("run_id")
    approve = commands.add_parser("approve", help="approve a run")
    approve.add_argument("run_id")
    execute = commands.add_parser("execute", help="execute an approved or shadow run")
    execute.add_argument("run_id")
    rollback = commands.add_parser("rollback", help="rollback a run to a healthy sandbox state")
    rollback.add_argument("run_id")
    replay = commands.add_parser("replay", help="export the run and audit evidence")
    replay.add_argument("run_id")
    commands.add_parser("demo", help="run stale-heartbeat workflow to verification")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    engine = RemediationEngine(Path(args.data_dir)); orchestrator = RemediationOrchestrator(engine)
    try:
        if args.command == "workflow":
            dump(orchestrator.workflow()); return 0
        if args.command == "alert":
            dump(orchestrator.ingest({"scenario": args.scenario, "mode": args.mode})); return 0
        if args.command == "plan":
            dump(orchestrator.plan(args.run_id)); return 0
        if args.command == "approve":
            dump(orchestrator.authorize(args.run_id)); return 0
        if args.command == "execute":
            result = orchestrator.execute(args.run_id); dump(result); return 0 if result.get("status") in {"verified", "shadowed"} else 1
        if args.command == "rollback":
            result = orchestrator.rollback(args.run_id); dump(result); return 0 if result.get("rollback", {}).get("status") == "VERIFIED" else 1
        if args.command == "replay":
            dump(orchestrator.export_run(args.run_id)); return 0
        if args.command == "demo":
            dump(orchestrator.run_to_completion({"scenario": "stale_heartbeat"})); return 0
        return 2
    except (KeyError, ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    finally:
        orchestrator.close()


if __name__ == "__main__":
    raise SystemExit(main())
