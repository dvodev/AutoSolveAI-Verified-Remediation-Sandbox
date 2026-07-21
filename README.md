# AutoSolve AI — Verified Remediation Sandbox

**A standalone Codex challenge demonstration.** It receives a synthetic monitoring alert, inspects a disposable worker, asks GPT to produce a structured remediation plan, enforces human approval, executes only an allowlisted sandbox capability, and proves the result with an independent heartbeat check.

This repository is intentionally clean-room and self-contained. It does not import, vendor, copy, or connect to the production AutoSolveAI repository. It contains no customer data, production credentials, cloud integrations, or host-service control.

## Run it

Requires Python 3.10+.

```powershell
python -m verified_sandbox
```

Open <http://127.0.0.1:8787> and choose a scenario:

1. **Stale heartbeat** starts a deliberately hung disposable worker.
2. **Missing process** removes the disposable worker.
3. **Healthy signal** demonstrates an observe-only no-op.

Then simulate the alert, generate a plan, approve it, and execute/verify it. Shadow mode performs planning and evidence collection without changing the target. The UI also exposes audit replay and rollback.

The model is constrained to the sandbox's declared capability contract. A plan naming any other capability or target is rejected before execution.

```powershell
python -m unittest discover -s tests -v
python -m verified_sandbox.cli workflow
python -m verified_sandbox.cli demo
python -m verified_sandbox.cli matrix
python -m verified_sandbox.cli release-check
```

Optional configuration:

```powershell
$env:OPENAI_API_KEY = "..."
$env:OPENAI_MODEL = "gpt-5.6"
$env:SANDBOX_PORT = "8787"
```

## What the demo proves

- alert ingestion and target inspection
- structured AI planning with schema and capability validation
- data-driven capability registry and scenario catalog
- explicit human approval before execution
- shadow mode for safe previews
- a real process restart inside a disposable temp directory
- independent post-action verification
- append-only hash-chained JSONL audit events with a terminal `VERIFIED` or `FAILED` result
- rollback and replay evidence
- provider-neutral adapters for Datadog/Prometheus-style alerts, targets, and ticket updates
- CLI and workflow/event-bus facades for reproducible judge scripts
- signed plan envelopes, payload security inspection, secret redaction, and sandbox-boundary enforcement
- fault-injection scenario matrix, replay bundles, markdown/HTML reports, and Prometheus-style metrics
- safe offline behavior when no model credential is configured
- local release-boundary checks for high-confidence credentials, sensitive filenames, required submission files, and a clean worktree

## Submission boundaries

This is the hackathon edition, not the production AutoSolveAI platform. The target is always `synthetic.local.worker`; the only executable actions are against that disposable process. No secrets are committed. No production repository history is included.

See [SUBMISSION.md](SUBMISSION.md), [DEMO_SCRIPT.md](DEMO_SCRIPT.md), and [BUILD_LOG.md](BUILD_LOG.md).
