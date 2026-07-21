# Devpost submission worksheet

Use this as the paste-ready source for the Devpost form. Replace only the fields marked `REPLACE`.

## Project

- **Title:** AutoSolve AI — Verified Remediation Sandbox
- **Track:** Developer Tools
- **Tagline:** From “Snipping Tool is stuck” to verified recovery: AutoSolve uses GPT-5.6 to create safe, approved remediations for known or unfamiliar incidents—and proves the fix actually worked.
- **Repository:** https://github.com/dvodev/AutoSolveAI-Verified-Remediation-Sandbox
- **Demo video:** https://youtu.be/8FyZQrSK7kU
- **Codex `/feedback` Session ID:** `019f70ae-deef-7e51-a596-81c08bb2650c`

## Description

AutoSolve AI is a verified incident-remediation command center for developer and operations workflows. An operator can enter an incident in ordinary language—for example, “Snipping Tool on my local Windows machine will not close and is stuck open.” The system first checks its local incident history for a prior verified resolution. If no reusable match exists, it inspects the target, operating-system facts, process state, heartbeat, logs, and registered capabilities, then asks GPT-5.6 for a structured remediation plan.

The plan is schema-validated against a capability registry and target contract. Policy requires explicit human approval (or supports shadow mode), so the model cannot directly mutate a target. After approval, the sandbox executes only an allowlisted capability against a disposable worker, independently verifies the post-action state, and records before/after evidence plus a hash-chained audit trail. A run is only marked `VERIFIED` when the evidence supports the claimed result; otherwise it fails or remains shadow-only.

The repository is a clean-room hackathon implementation using synthetic incidents and a disposable local process. It includes provider-shaped Datadog, Prometheus, ServiceNow, and AWS/EC2 simulators, dynamic routing, deduplication/correlation, runbook synthesis, replay/rollback, redaction/security checks, connector health, and automated tests. The public demo shows the natural-language incident, prior-resolution lookup, GPT-5.6 planning, approval, real local Snipping Tool PID closure, `WINDOW GONE`, and verified evidence.

## How Codex and GPT-5.6 were used

Codex was used to build and iterate on the standalone intake boundary, history lookup, capability router, typed contracts, planner validation, approval state machine, execution/verification boundary, audit replay, connector simulators, UI, fault matrix, and release checks. GPT-5.6 is integrated as the runtime planner: it receives normalized alert data, inspection evidence, routing recommendations, and the capability manifest, then returns a structured JSON plan. The application validates every field before execution and falls back safely when no API key or model is available.

## Judge setup

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m unittest discover -s tests -q
python -m verified_sandbox
```

Open `http://127.0.0.1:8787`, enter any free-form incident, confirm the prior-resolution result, generate the plan, approve it, execute it, and verify the evidence/audit chain. The demo works without an API key using the safe deterministic fallback. For live planning, set `OPENAI_API_KEY` and `OPENAI_MODEL=gpt-5.6` in the current shell only.

## Remaining submission fields

- **Team members:** `REPLACE_WITH_NAMES_AND_ROLES`
- **Repository visibility:** Public with the included MIT license, or private shared with `testing@devpost.com` and `build-week-event@openai.com`.
- **Video:** Upload `artifacts/autosolve_natural_language_snipping_tool_demo_final.mp4` to YouTube as Public; keep the final video under three minutes and include narration covering the product, Codex, and GPT-5.6.
