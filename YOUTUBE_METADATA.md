# YouTube upload package

## Title

AI Fixes a Stuck App — Verified Windows Remediation with GPT-5.6

## Description

AutoSolve AI turns a natural-language incident into a reviewed, executable remediation—and refuses to call it solved until independent evidence proves the outcome.

In this demo, I report that Snipping Tool on my local Windows machine is stuck open and will not close. AutoSolve checks whether a prior verified resolution exists. When no reusable match is found, it inspects the target and asks GPT-5.6 to generate a constrained plan from the available capability registry.

The plan is validated and gated by explicit human approval. After approval, AutoSolve closes the exact local SnippingTool.exe process, confirms the PID is gone, changes the target state to WINDOW GONE, and records before/after evidence plus a hash-chained audit trail.

This is a clean-room Developer Tools hackathon sandbox. The repository uses synthetic incidents and a disposable worker; no production credentials, customer data, or production systems are required.

Codex was used to build the incident intake, history lookup, dynamic routing, policy gate, execution boundary, verification, audit replay, connector simulators, UI, and test/release checks. GPT-5.6 is integrated as the runtime planner that produces and validates structured remediation plans.

Repository: https://github.com/dvodev/AutoSolveAI-Verified-Remediation-Sandbox
Build session: 019f70ae-deef-7e51-a596-81c08bb2650c

## Chapters

00:00 The stuck-app problem
00:10 Natural-language alert and prior-resolution lookup
00:27 Dynamic GPT-5.6 remediation plan
00:44 Human approval gate
00:55 Execute the approved remediation
01:05 WINDOW GONE and verified evidence

## Tags

AI remediation, incident response, developer tools, GPT-5.6, Codex, DevOps, SRE, Windows automation, verified remediation, autonomous operations, AI agents, observability, runbook automation, cybersecurity

## Pinned comment

The key idea: an AI plan is not considered a solution until policy allows it to execute and independent evidence proves the target state afterward. The sandbox, setup instructions, tests, and audit workflow are in the repository.
