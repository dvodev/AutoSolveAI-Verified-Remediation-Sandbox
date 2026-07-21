# Under-three-minute video script

**0:00–0:20 — Problem.** “Monitoring says checkout-worker is unhealthy. A green API response is not proof of recovery.”

**0:20–0:45 — Alert and inspection.** Click **Simulate alert**. Point out the synthetic target, PID, stale heartbeat, and `healthy: false`.

**0:45–1:15 — AI plan.** Click **Generate GPT plan**. Show the structured capability, target, reasoning, verification requirement, and `sandbox_only` risk. Explain that unknown capabilities are rejected.

**1:15–1:35 — Approval.** Click **Approve**. Show the audit event proving approval is a separate state transition.

**1:35–2:15 — Execution.** Click **Execute + verify**. Show the worker PID changes and the new heartbeat.

**2:15–2:45 — Proof.** Highlight `VERIFIED`, `healthy: true`, and the append-only audit timeline. “The system does not mark the incident solved because a command returned zero; it checks the recovered target.”

**2:45–3:00 — Boundary.** “This is a clean-room sandbox: synthetic alert, disposable process, no production systems or secrets.”
