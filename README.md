# AutoSolve AI — Verified Remediation Sandbox

**A standalone Codex challenge demonstration for the Developer Tools track.** It receives a synthetic monitoring alert, checks for a prior verified resolution, inspects a disposable worker, asks GPT-5.6 to produce a structured remediation plan, enforces human approval, executes only an allowlisted sandbox capability, and proves the result with an independent heartbeat check.

This repository is intentionally clean-room and self-contained. It does not import, vendor, copy, or connect to the production AutoSolveAI repository. It contains no customer data, production credentials, cloud integrations, or host-service control.

## Run it

Requires Python 3.10+.

### Clean setup

From a fresh clone:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

No API key is required for the deterministic, safe offline fallback. To use live GPT-5.6 planning, set `OPENAI_API_KEY` in the current shell only; never commit a `.env` file or key.

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
python -m verified_sandbox.cli connectors
python -m verified_sandbox.cli run --scenario stale_heartbeat
```

The HTTP server listens on `127.0.0.1:8787` by default. Set `SANDBOX_PORT` to choose another local port. The workflow is approval-gated by default; Shadow mode collects evidence and plans without mutating the disposable worker.

Optional configuration:

```powershell
$env:OPENAI_API_KEY = "..."
$env:OPENAI_MODEL = "gpt-5.6"
$env:SANDBOX_PORT = "8787"
```

## How Codex and GPT-5.6 are used

Codex was used to build and iterate on the standalone incident intake, prior-resolution lookup, explainable capability routing, typed plan validation, approval state machine, execution boundary, independent verification, audit replay, connector simulators, UI, and test/release checks. The dated implementation history is documented in [BUILD_LOG.md](BUILD_LOG.md).

GPT-5.6 is the runtime planner when `OPENAI_API_KEY` is configured. It receives the normalized alert, inspected target evidence, routing recommendation, and capability manifest; it must return a structured JSON plan. The sandbox validates the capability, target, steps, risk, and verification requirements before any action can execute. If the model is unavailable, the system uses a deterministic constrained fallback and never executes an unvalidated model response.

Primary Codex `/feedback` Session ID: `019f70ae-deef-7e51-a596-81c08bb2650c`.

## Testing and judge verification

Run the complete automated suite and release boundary check:

```powershell
python -m unittest discover -s tests -q
python -m verified_sandbox.cli release-check
```

The tests cover API lifecycle transitions, duplicate intake, routing, planner schema validation, approval/shadow policy, execution and verification, rollback/replay, connector health, security/redaction, and the scenario matrix. For a manual judge run, open the UI, enter any free-form incident, confirm the prior-resolution result, generate the plan, approve it, execute, and verify the evidence/audit chain.

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
- provider-shaped Datadog, Prometheus, ServiceNow, and AWS/EC2 simulators with connector health
- incident deduplication/correlation, explainable capability routing, policy risk controls, idempotent retries, circuit breakers, plan envelopes, learning summaries, independent check evaluation, and dependency-ordered runbook synthesis
- explainable synthetic target resolution and a complete CLI/API workflow surface for judges

## Submission boundaries

This is the hackathon edition, not the production AutoSolveAI platform. The target is always `synthetic.local.worker`; the only executable actions are against that disposable process. No secrets are committed. No production repository history is included.

See [SUBMISSION.md](SUBMISSION.md), [DEVPOST_SUBMISSION.md](DEVPOST_SUBMISSION.md), [YOUTUBE_METADATA.md](YOUTUBE_METADATA.md), [DEMO_SCRIPT.md](DEMO_SCRIPT.md), and [BUILD_LOG.md](BUILD_LOG.md). The upload thumbnail is [artifacts/youtube_thumbnail.png](artifacts/youtube_thumbnail.png).
