from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verified_sandbox.cli import main


class CliTests(unittest.TestCase):
    def test_workflow_command_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(main(["--data-dir", directory, "workflow"]), 0)

    def test_demo_command_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(main(["--data-dir", directory, "demo"]), 0)

    def test_matrix_command_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(main(["--data-dir", directory, "matrix"]), 0)

    def test_invalid_command_arguments_return_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertNotEqual(main(["--data-dir", directory, "execute", "missing"]), 0)


if __name__ == "__main__":
    unittest.main()
