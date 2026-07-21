# AutoSolve AI — Verified Remediation Sandbox

**A standalone Codex challenge demonstration.** It receives a synthetic monitoring alert, inspects a disposable worker, asks GPT to produce a structured remediation plan, enforces human approval, executes only an allowlisted sandbox capability, and proves the result with an independent heartbeat check.

This repository is intentionally clean-room and self-contained. It does not import, vendor, copy, or connect to the production AutoSolveAI repository. It contains no customer data, production credentials, cloud integrations, or host-service control.

## Run it

Requires Python 3.10+.

```powershell
python -m verified_sandbox
```

Open <http://127.0.0.1:8787> and click the four buttons in order:

1. Simulate a synthetic Datadog-style alert. This starts a deliberately unhealthy disposable worker.
2. Generate a plan. With `OPENAI_API_KEY` set, the configured model is used; without it, the safe offline planner keeps the demo testable.
3. Approve the plan.
4. Execute and verify. The worker is restarted and the fresh heartbeat is shown as `VERIFIED`.

The model is constrained to the sandbox's declared capability contract. A plan naming any other capability or target is rejected before execution.

```powershell
python -m unittest discover -s tests -v
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
- explicit human approval before execution
- a real process restart inside a disposable temp directory
- independent post-action verification
- append-only JSONL audit events with a terminal `VERIFIED` or `FAILED` result
- safe offline behavior when no model credential is configured

## Submission boundaries

This is the hackathon edition, not the production AutoSolveAI platform. The target is always `synthetic.local.worker`; the only executable actions are against that disposable process. No secrets are committed. No production repository history is included.

See [SUBMISSION.md](SUBMISSION.md), [DEMO_SCRIPT.md](DEMO_SCRIPT.md), and [BUILD_LOG.md](BUILD_LOG.md).
