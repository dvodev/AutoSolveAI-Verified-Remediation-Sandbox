from __future__ import annotations

import tempfile
import unittest

from verified_sandbox.engine import RemediationEngine
from verified_sandbox.reporting import build_report, batch_summary, render_html, render_markdown, score_report


class ReportingTests(unittest.TestCase):
    def test_report_contains_judge_visible_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = RemediationEngine(directory)
            try:
                run = engine.create_alert(); run = engine.plan(run["run_id"]); run = engine.approve(run["run_id"]); run = engine.execute(run["run_id"])
                report = build_report(run, audit_chain=engine.events.verify_chain(), adapter_health={"sandbox": {"status": "ready"}})
                titles = {section.title for section in report.sections}
                self.assertTrue({"AI plan", "Policy", "Verification", "Audit integrity"}.issubset(titles))
                self.assertEqual(score_report(report)["score"], 1)
                self.assertIn("VERIFIED", render_markdown(report))
                self.assertIn("<html", render_html(report).lower())
            finally:
                engine.close()

    def test_batch_summary_counts_statuses(self):
        from verified_sandbox.reporting import ReportSection, RunReport
        report = RunReport("x", "r", "verified", "now", [ReportSection("AI plan", "x"), ReportSection("Policy", "x"), ReportSection("Verification", "x"), ReportSection("Audit integrity", "x"), ReportSection("Target evidence", "x")], {}, {})
        summary = batch_summary([report, report])
        self.assertEqual(summary["verified"], 2)


if __name__ == "__main__":
    unittest.main()
