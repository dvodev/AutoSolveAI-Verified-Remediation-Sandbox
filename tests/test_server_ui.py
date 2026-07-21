from __future__ import annotations

import unittest

from verified_sandbox.server import HTML


class ServerUiTests(unittest.TestCase):
    def test_ui_is_a_real_workflow_shell(self):
        self.assertIn("Turn an alert into verified proof", HTML)
        self.assertIn("Generate constrained AI plan", HTML)
        self.assertIn("Evidence comparison", HTML)
        self.assertIn("Audit trail", HTML)
        self.assertIn("Try any incident", HTML)
        self.assertIn("customTitle", HTML)
        self.assertNotIn("Start the demo.", HTML)


if __name__ == "__main__":
    unittest.main()
