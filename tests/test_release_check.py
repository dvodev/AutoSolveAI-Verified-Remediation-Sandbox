from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verified_sandbox.release_check import release_check, scan_secrets


class ReleaseCheckTests(unittest.TestCase):
    def test_current_submission_boundary_is_clean(self):
        result = release_check(Path(__file__).parents[1])
        self.assertFalse(result["missing_files"])
        self.assertFalse(result["secret_findings"])
        self.assertFalse(result["sensitive_filenames"])

    def test_high_confidence_secret_is_detected_without_returning_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.txt"
            fake_key = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
            path.write_text(f"OPENAI_API_KEY={fake_key}\n", encoding="utf-8")
            findings = scan_secrets(directory)
            self.assertEqual(findings[0]["pattern"], "openai_key")
            self.assertNotIn("sk-", str(findings))


if __name__ == "__main__":
    unittest.main()
