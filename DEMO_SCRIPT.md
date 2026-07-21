# Recorded contest demo script

The submitted recording is [`artifacts/autosolve_verified_remediation_demo.webm`](artifacts/autosolve_verified_remediation_demo.webm), approximately 75 seconds at 1440×900.

**Opening — Context.** The command center shows registered capabilities, simulator connectors, and the clean-room boundary.

**Free-form incident.** Enter: “Snipping Tool on my local Windows machine will not close and is stuck open. Check whether this has been resolved before. If there is no matching verified resolution, inspect the target and generate a dynamic safe solution; after approval, close it and verify it is gone.” This is not a pre-saved scenario.

**Dynamic reasoning.** Show intake, target inspection, the router recommendation, and GPT-5.6’s structured plan. The selected capability must come from the registry.

**Policy gate.** Approve the plan explicitly. Explain that shadow mode is available and no mutation happens before approval.

**Execution and proof.** Execute the allowlisted termination. The visible target transitions `NOT RESPONDING` → `CLOSING…` → `CLOSED / VERIFIED`; then show stopped process evidence and the audit timeline.

**Boundary.** State that the demo is clean-room and synthetic: it never touches the real Snipping Tool, production systems, or secrets.

For the operator-authorized local proof, use [`artifacts/autosolve_real_snipping_tool_demo.webm`](artifacts/autosolve_real_snipping_tool_demo.webm). That recording shows the exact Windows `SnippingTool.exe` PID being closed after the AI plan and approval, followed by a process-absent verification. Do not present that local-target proof as the default sandbox boundary.

The full capture for judging is [`artifacts/autosolve_real_desktop_demo.mp4`](artifacts/autosolve_real_desktop_demo.mp4). It shows a readable native Windows Snipping Tool capture and live PID panel before approval, the prior-resolution lookup, the GPT-5.6 plan and human gate, the real PID termination, the panel changing to `WINDOW GONE`, and the final `VERIFIED` evidence view.

Use [`artifacts/autosolve_natural_language_snipping_tool_demo_final.mp4`](artifacts/autosolve_natural_language_snipping_tool_demo_final.mp4) when selecting the latest uniquely named file in File Explorer.
