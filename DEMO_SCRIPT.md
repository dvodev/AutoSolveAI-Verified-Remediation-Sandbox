# Under-three-minute video script

**0:00–0:20 — Problem.** “Monitoring says checkout-worker is unhealthy. A green API response is not proof of recovery.”

**0:20–0:45 — Alert and inspection.** Choose **Stale heartbeat** and click **Simulate alert**. Point out the synthetic target, PID, OS facts, logs, stale status, and `healthy: false`.

**0:45–1:15 — AI plan.** Click **Generate GPT plan**. Show the structured capability, target, reasoning, verification requirement, and `sandbox_only` risk. Explain that unknown capabilities are rejected.

**1:15–1:35 — Policy.** Show the capability manifest and approval decision. Click **Approve**. Show the audit event proving approval is a separate state transition. Mention that **Shadow mode** can run the same plan without changing state.

**1:35–2:15 — Execution.** Click **Execute + verify**. Show the worker PID changes and the new heartbeat.

**2:15–2:40 — Proof.** Highlight `VERIFIED`, `healthy: true`, the PID transition, and the hash-chained audit timeline. Click **Replay audit** and **Rollback**.

**2:40–3:00 — Generalization and boundary.** Select **Healthy signal** to show the observe-only no-op, then say: “The system does not mark an incident solved because a command returned zero; it checks the recovered target. This is a clean-room sandbox: synthetic alert, disposable process, no production systems or secrets.”
