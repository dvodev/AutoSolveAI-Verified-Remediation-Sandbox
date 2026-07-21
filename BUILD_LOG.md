# Build-week provenance log

This file is deliberately explicit about provenance. The production AutoSolveAI application is an older, separate repository and is not included here. This repository records only the standalone sandbox implementation built for the challenge session.

| Date | New component | Evidence |
|---|---|---|
| 2026-07-21 | Synthetic worker and incident simulator | `verified_sandbox/sandbox.py`, `worker.py` |
| 2026-07-21 | Constrained model planner and schema gate | `verified_sandbox/planner.py` |
| 2026-07-21 | Approval, execution, verification, and audit state machine | `verified_sandbox/engine.py` |
| 2026-07-21 | Standalone demo UI/API and tests | `verified_sandbox/server.py`, `tests/` |

Codex build session: `019f70ae-deef-7e51-a596-81c08bb2650c`.

Before submitting, record the exact public repository URL and video URL in `SUBMISSION.md`. Do not claim that legacy production code was built during the challenge.
