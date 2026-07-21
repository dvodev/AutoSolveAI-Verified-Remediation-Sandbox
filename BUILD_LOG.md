# Build-week provenance log

This file is deliberately explicit about provenance. The production AutoSolveAI application is an older, separate repository and is not included here. This repository records only the standalone sandbox implementation built for the challenge session.

| Date | New component | Evidence |
|---|---|---|
| 2026-07-21 | Synthetic worker and incident simulator | `verified_sandbox/sandbox.py`, `worker.py` |
| 2026-07-21 | Constrained model planner and schema gate | `verified_sandbox/planner.py` |
| 2026-07-21 | Approval, execution, verification, and audit state machine | `verified_sandbox/engine.py` |
| 2026-07-21 | Standalone demo UI/API and tests | `verified_sandbox/server.py`, `tests/` |
| 2026-07-21 | Typed contracts, evidence model, adapter registry, and durable store | `verified_sandbox/models.py`, `contracts.py`, `evidence.py`, `adapters.py`, `storage.py` |
| 2026-07-21 | Event orchestration, security gates, metrics, fault matrix, replay bundles, and reports | `verified_sandbox/orchestrator.py`, `security.py`, `metrics.py`, `simulation.py`, `replay.py`, `reporting.py` |
| 2026-07-21 | Release-boundary scanner and audit-chain restart continuity | `verified_sandbox/release_check.py`, `tests/test_release_check.py`, `tests/test_orchestrator.py` |
| 2026-07-21 | Judge-facing incident command UI with dynamic scenario/capability rendering and evidence timeline | `verified_sandbox/ui.py`, `tests/test_server_ui.py` |
| 2026-07-21 | Expanded provider-shaped connectors, incident correlation, capability routing, policy controls, idempotent runtime, plan envelopes, learning ledger, verification engine, and dynamic runbooks | `verified_sandbox/incident_intake.py`, `capability_router.py`, `policy_engine.py`, `execution_runtime.py`, `plan_envelope.py`, `learning.py`, `verification_engine.py`, `runbook.py`, `tests/test_expanded_system.py` |
| 2026-07-21 | Synthetic target resolution and expanded CLI connector/run surfaces | `verified_sandbox/target_resolution.py`, `verified_sandbox/cli.py`, `tests/test_cli.py` |

Codex build session: `019f70ae-deef-7e51-a596-81c08bb2650c`.

The current standalone implementation is nearly 3,000 Python lines with 65 automated tests. The line count reflects typed domain contracts, provider-shaped adapters, incident intake/correlation, target resolution, capability routing, policy controls, idempotent execution, plan envelopes, learning summaries, verification, runbook synthesis, orchestration, evidence processing, simulation, replay, reporting, CLI, API, release checks, the command UI, and tests—not copied production code.

Before submitting, record the exact public repository URL and video URL in `SUBMISSION.md`. Do not claim that legacy production code was built during the challenge.

Verification baseline: 65 automated tests pass; the four-scenario matrix passes 4/4, including a mocked configured-model planner path, expanded connector/API checks, UI contract checks, target resolution, and dependency-ordered runbook execution.
