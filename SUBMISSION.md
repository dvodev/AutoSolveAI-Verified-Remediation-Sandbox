# Hackathon submission brief

## Category

Developer Tools — verified incident remediation.

## One-sentence pitch

AutoSolve AI turns a monitoring alert into a reviewed, executable remediation and refuses to call it solved until the target independently proves recovery—or safely demonstrates that no change is needed.

## The judge-visible workflow

Synthetic alert → inspect worker/OS/logs → GPT structured plan → capability/policy gate → approval or shadow mode → restart/observe/terminate disposable worker → independent verification → hash-chained audit replay and rollback.

The implementation includes a provider-neutral adapter layer, typed contracts, signed plan envelopes, security/redaction gates, fault-injection matrix, replayable run bundles, metrics, CLI workflows, and judge-facing reports. These are new standalone hackathon components, not imported production modules.

## Scope and ownership boundary

This repository is a standalone implementation created for the hackathon demonstration. It is not a branch or export of the pre-existing AutoSolveAI application. It uses synthetic incidents and a disposable local process only. No company equipment, confidential incidents, internal architecture, customer records, production secrets, or production source are required to run it.

The entrant should independently confirm that their employment agreements and equipment-use policies permit submission. This repository does not make that legal determination.

## Pre-existing versus new work

The production AutoSolveAI project predates the challenge. This submission does not claim that pre-existing work was created during Build Week. The new, separately committed work here is the contained remediation sandbox: its incident simulator, constrained model schema, approval state machine, target-side verification, and audit UI. See the dated Git history and [BUILD_LOG.md](BUILD_LOG.md).

## Judge setup

```powershell
python -m unittest discover -s tests -v
python -m verified_sandbox
```

The demo works without an API key using a deterministic safe fallback. Set `OPENAI_API_KEY` and `OPENAI_MODEL` to show live model planning.

## Links to provide at submission time

- Public repository: replace with the dedicated repository URL.
- YouTube video (under three minutes): replace with the published URL.
- Codex session ID: `019f70ae-deef-7e51-a596-81c08bb2650c` (the session in which the standalone core was built).
