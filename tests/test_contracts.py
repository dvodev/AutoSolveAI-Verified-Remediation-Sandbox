from __future__ import annotations

import unittest

from verified_sandbox.contracts import ContractError, canonical_json, fingerprint, redact
from verified_sandbox.models import CapabilitySpec, RemediationPlan, TargetRef, VerificationRule
from verified_sandbox.registry import load_capabilities


class ContractTests(unittest.TestCase):
    def test_canonical_json_is_order_independent(self):
        self.assertEqual(canonical_json({"b": 2, "a": 1}), canonical_json({"a": 1, "b": 2}))
        self.assertEqual(fingerprint({"a": 1}), fingerprint({"a": 1}))

    def test_redaction_covers_nested_secrets_and_bearer_tokens(self):
        value = {"password": "hidden", "nested": {"access_token": "abc"}, "message": "Bearer abc.def"}
        safe = redact(value)
        self.assertNotIn("hidden", str(safe))
        self.assertNotIn("abc.def", str(safe))
        self.assertEqual(safe["nested"]["access_token"], "[REDACTED]")

    def test_target_contract_rejects_non_sandbox_target(self):
        from verified_sandbox.contracts import validate_target
        with self.assertRaises(ContractError):
            validate_target(TargetRef("prod-host", environment="production", provider="ssh"))

    def test_registered_plan_contract_accepts_data_driven_capability(self):
        from verified_sandbox.contracts import validate_plan
        spec = load_capabilities()["restart_sandbox_worker"]
        capability = CapabilitySpec.from_dict(spec)
        plan = RemediationPlan(
            "p1", "r1", capability.name, TargetRef("synthetic.local.worker"), "repair", ["restart"],
            [VerificationRule("healthy", "healthy", True)], capability.risk, "test", confidence=.9,
        )
        validate_plan(plan, {capability.name: capability})

    def test_plan_contract_rejects_unregistered_capability(self):
        from verified_sandbox.contracts import validate_plan
        plan = RemediationPlan("p1", "r1", "unknown", TargetRef("synthetic.local.worker"), "bad", ["x"], [VerificationRule("x", "x")], "sandbox_only", "test", confidence=.9)
        with self.assertRaises(ContractError):
            validate_plan(plan, {})


if __name__ == "__main__":
    unittest.main()
