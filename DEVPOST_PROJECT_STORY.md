# About the project

## Inspiration

Incident response usually breaks down in the space between an alert and a trustworthy fix. A ticket may say that an application is stuck, unhealthy, or timing out, but the wording is incomplete and the correct runbook may not exist. Existing automation can execute a guessed command too quickly, while purely advisory AI can describe a fix without actually changing the system or proving that the problem is gone.

AutoSolve AI was built around a stricter question: **can an operator give the system an incident in ordinary language, let it discover a safe remediation, and receive evidence that the target really recovered?** The goal is not to make an impressive suggestion. The goal is to create a controlled, reviewable action and refuse to label it solved when verification does not support that claim.

## What it does

AutoSolve AI is a verified incident-remediation command center for developer and operations workflows. An operator can enter a statement such as:

> Snipping Tool on my local Windows machine will not close and is stuck open.

The system then:

1. Normalizes the natural-language incident and identifies the target and symptom.
2. Searches incident history for a previously verified resolution instead of blindly repeating an action.
3. Inspects the target, process state, heartbeat, logs, operating-system facts, and available capabilities.
4. Routes the incident through provider-shaped adapters and a dynamic capability registry.
5. Asks GPT-5.6 for a structured remediation plan when a reusable resolution is not available.
6. Validates the plan against typed contracts, the target contract, policy, and the allowlisted capability manifest.
7. Requires explicit approval, with shadow mode available when execution should be simulated.
8. Executes only the approved capability against a disposable sandbox worker or the explicitly selected local demo target.
9. Independently verifies the post-action state, records before/after evidence, and writes a hash-chained audit trail.

The run is marked `VERIFIED` only when the evidence supports the claimed outcome. If the plan is unsafe, unsupported, rejected, or not independently verified, the system reports that honestly instead of manufacturing success.

## The demo

The public demo uses a real local Windows Snipping Tool window as the visible target. The incident is entered in natural language rather than as a hardcoded process command. AutoSolve checks its history, shows whether a reusable verified resolution exists, inspects the target, and generates a GPT-5.6 plan. After approval, it closes the exact target process, shows the window disappearing, confirms `WINDOW GONE`, and displays verified evidence and the audit record.

The same workflow also runs safely without an API key through a deterministic offline planner, so judges can test the repository without credentials. With an API key configured, GPT-5.6 is the runtime planner; the application still validates the returned plan before anything can execute.

## How it was built

The implementation is a standalone clean-room hackathon sandbox using Python 3.10+ and the Python standard library. It deliberately avoids production credentials and customer data. The architecture is split into explicit boundaries:

- **Intake and normalization:** converts free-form incidents and provider-shaped alerts into typed internal records.
- **History and correlation:** deduplicates related incidents and reuses only resolutions that have verified evidence.
- **Inspection and routing:** gathers target facts and chooses capabilities from a registry instead of embedding one command per incident.
- **Planner:** sends normalized evidence and the capability manifest to GPT-5.6 and requires structured JSON.
- **Validation and policy:** rejects malformed, unsupported, over-scoped, or disallowed plans before execution.
- **Approval and execution:** separates model output from human authorization and runs only allowlisted operations.
- **Verification and audit:** checks the target independently after execution and records tamper-evident before/after evidence.

The repository includes provider-shaped Datadog and Prometheus alert adapters, ServiceNow-shaped ticket lifecycle simulation, AWS/EC2-shaped inventory and action-ledger simulation, connector health, dynamic routing, deduplication/correlation, runbook synthesis, replay and rollback paths, redaction checks, fault-injection scenarios, reports, metrics, and automated tests. These integrations are intentionally simulators; they do not call production systems or require credentials.

## How Codex and GPT-5.6 were used

Codex was used throughout the build to design and implement the standalone project, iterate on the typed contracts and state machine, build the UI and local execution boundary, add connector simulators, create the fault matrix, write tests, generate the demo workflow, and run release checks.

GPT-5.6 has a separate runtime role inside the application. It receives the normalized incident, inspection evidence, routing recommendation, and capability manifest, then returns a structured remediation plan. The application validates every field, checks the requested capability and target against policy, requires approval, and independently verifies the result. GPT-5.6 is therefore useful for novel planning without becoming an unrestricted command executor.

## The hardest engineering problems

The central challenge was making the system dynamic without making it unsafe. A hardcoded `if SnippingTool then kill process` demo would be easy, but it would not demonstrate general remediation. Conversely, allowing a model to invent and run arbitrary shell commands would be unsafe and impossible to verify reliably. The solution is a typed, capability-based boundary: the model can reason over available capabilities, but only validated and policy-approved capabilities can execute. Unknown or unsupported situations remain visible as unsupported or escalated rather than being hidden.

Another challenge was proving the result. A successful API response or an AI statement is not evidence that a service recovered. AutoSolve records the observed state before and after the action, verifies the target independently, and exposes the evidence and audit chain in the UI. This makes a failed remediation useful too: the operator can see exactly what was attempted and why it was not marked solved.

## Running it

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m unittest discover -s tests -q
python -m verified_sandbox
```

Open `http://127.0.0.1:8787`, enter any free-form incident, inspect the target, generate a plan, approve it, execute it, and review the evidence and audit chain. The safe deterministic fallback works without an API key. For live GPT-5.6 planning, set `OPENAI_API_KEY` and `OPENAI_MODEL=gpt-5.6` only in the current shell.

## Safety and scope

This submission is a disposable demonstration sandbox, not a production deployment. It contains synthetic incidents and provider simulators, uses an allowlisted execution boundary, requires approval for mutating actions, redacts sensitive values, and never calls AWS, ServiceNow, Datadog, or Prometheus production endpoints. A real deployment would require organization-specific identity, secrets management, capability approvals, observability credentials, rollback policy, and additional security review.

## Why it matters

AutoSolve AI combines the flexibility of an AI agent with the discipline expected from incident-response tooling. It turns ambiguous reports into reviewable plans, supports unfamiliar incidents without pretending every problem has a known runbook, and makes verification a first-class product outcome. The result is a path from “something is broken” to “this approved action ran, this is what changed, and here is the evidence that recovery occurred.”
