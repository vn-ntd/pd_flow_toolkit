"""
Unit tests for SDC Linter and Rules Checker.
"""

import unittest
from pathlib import Path
from pd_toolkit.sdc_linter import SDCLinter


class TestSDCLinter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples_dir = Path(__file__).parent.parent / "examples" / "sdc"

    def test_clean_sdc(self):
        clean_file = self.examples_dir / "clean_soc.sdc"
        linter = SDCLinter(str(clean_file))
        report = linter.lint()

        self.assertTrue(report.passed, f"Clean SDC should pass without errors, got {report.error_count} errors")
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.warning_count, 0)

    def test_dirty_sdc_catches_all_expected_bugs(self):
        dirty_file = self.examples_dir / "dirty_soc.sdc"
        linter = SDCLinter(str(dirty_file))
        report = linter.lint()

        self.assertFalse(report.passed)
        self.assertGreater(report.error_count, 0)
        self.assertGreater(report.warning_count, 0)

        rule_ids = {v.rule_id for v in report.violations}
        # Check specific rule IDs triggered
        self.assertIn("CLK-001", rule_ids)  # Negative period
        self.assertIn("CLK-002", rule_ids)  # Inverted waveform
        self.assertIn("CLK-003", rule_ids)  # Nonexistent master clock & missing source
        self.assertIn("EXC-001", rule_ids)  # Wildcard false path * -> *
        self.assertIn("EXC-002", rule_ids)  # Conflicting false path & multicycle path
        self.assertIn("IO-003", rule_ids)   # Extreme input delay > 85%
        self.assertIn("SYN-001", rule_ids)  # Deprecated set_dont_use


if __name__ == "__main__":
    unittest.main()
