# Demo recording

`autosolve_verified_remediation_demo.webm` is a 1440×900 browser recording of the complete synthetic workflow (approximately 75 seconds):

1. Free-form alert: “Snipping Tool won't close”.
2. Dynamic router selects the registered termination capability.
3. GPT-5.6 generates and validates the constrained plan.
4. Human approval is required before mutation.
5. The disposable worker is terminated and independently verified.
6. Before/after evidence and the hash-chained audit trail are shown.

The recording also includes a clearly labeled **Snipping Tool — Sandbox target** window that visibly transitions from `NOT RESPONDING` to `CLOSING…` to `CLOSED / VERIFIED` when the AI-selected remediation executes.

The recording uses synthetic data only. It does not control the real Snipping Tool or any production host.

`autosolve_real_snipping_tool_demo.webm` is the separately gated local-target proof. It records the AI plan and approval, then closes the exact live `SnippingTool.exe` PID and verifies that Windows no longer reports that process. This local-target recording is not the default contest sandbox path and should only be run with explicit operator authorization.

`autosolve_real_desktop_demo.mp4` is the judge-facing full workflow. It uses a clear page recording with an actual native Windows Snipping Tool capture and PID panel, shows the natural-language alert, prior-resolution lookup, GPT-5.6 plan provenance, approval gate, execution, and final verified evidence. The exact live PID is terminated only after approval; the native target panel changes to `WINDOW GONE` and the final screen shows the verified audit result. The recording is operator-authorized and uses the local OpenAI key only in memory; no key is stored in the repository.
