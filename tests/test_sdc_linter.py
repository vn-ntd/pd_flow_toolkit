"""
Unit tests for SDC Linter and Rules Checker.
"""

import unittest
from pathlib import Path
import tempfile
import os
from pd_toolkit.sdc_linter import SDCLinter
from pd_toolkit.sdc_linter.sdc_parser import SDCParser


class TestSDCLinter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples_dir = Path(__file__).parent.parent / "examples" / "sdc"

    def _lint_string(self, sdc_content: str):
        with tempfile.NamedTemporaryFile("w", suffix=".sdc", delete=False, encoding="utf-8") as tf:
            tf.write(sdc_content)
            temp_path = tf.name
        try:
            linter = SDCLinter(temp_path)
            return linter.lint()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

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

    def test_global_clock_uncertainty_no_false_positive(self):
        """Ensures 'set_clock_uncertainty 0.15' is recognized as global and does not trigger CLK-005."""
        sdc = """
        create_clock -name core_clk -period 10.0 [get_ports clk]
        create_clock -name dsp_clk -period 5.0 [get_ports dsp_clk]
        set_clock_uncertainty 0.150
        set_input_delay -clock core_clk 2.0 [get_ports in_data]
        set_output_delay -clock core_clk 2.0 [get_ports out_data]
        set_clock_groups -asynchronous -group [get_clocks core_clk] -group [get_clocks dsp_clk]
        """
        report = self._lint_string(sdc)
        rule_ids = [v.rule_id for v in report.violations]
        self.assertNotIn("CLK-005", rule_ids, "Global uncertainty should prevent CLK-005 false positive.")

    def test_clock_specific_uncertainty(self):
        """Verifies that uncertainty defined for one clock warns for another unconstrained clock."""
        sdc = """
        create_clock -name clk_a -period 5.0 [get_ports clk_a]
        create_clock -name clk_b -period 5.0 [get_ports clk_b]
        set_clock_uncertainty 0.15 [get_clocks clk_a]
        set_input_delay -clock clk_a 1.0 [get_ports in_a]
        set_output_delay -clock clk_a 1.0 [get_ports out_a]
        set_clock_groups -asynchronous -group [get_clocks clk_a] -group [get_clocks clk_b]
        """
        report = self._lint_string(sdc)
        clk_005_violations = [v for v in report.violations if v.rule_id == "CLK-005"]
        self.assertEqual(len(clk_005_violations), 1)
        self.assertIn("clk_b", clk_005_violations[0].message)

    def test_set_clock_groups_multiple_groups(self):
        """Ensures repeated -group options are preserved and parsed as a list."""
        sdc = """
        create_clock -name clk1 -period 4.0 [get_ports clk1]
        create_clock -name clk2 -period 6.0 [get_ports clk2]
        create_clock -name clk3 -period 8.0 [get_ports clk3]
        set_clock_groups -asynchronous -group [get_clocks clk1] -group [get_clocks clk2] -group [get_clocks clk3]
        set_clock_uncertainty 0.1
        set_input_delay -clock clk1 1.0 [get_ports in1]
        set_output_delay -clock clk1 1.0 [get_ports out1]
        """
        with tempfile.NamedTemporaryFile("w", suffix=".sdc", delete=False, encoding="utf-8") as tf:
            tf.write(sdc)
            temp_path = tf.name
        try:
            parser = SDCParser(temp_path)
            cmds = parser.parse()
            grp_cmd = [c for c in cmds if c.command_name == "set_clock_groups"][0]
            groups = grp_cmd.get_list("group")
            self.assertEqual(len(groups), 3)
            self.assertIn("[get_clocks clk1]", groups)
            self.assertIn("[get_clocks clk2]", groups)
            self.assertIn("[get_clocks clk3]", groups)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_set_clock_groups_insufficient_groups(self):
        """Warns when set_clock_groups is declared with fewer than 2 groups."""
        sdc = """
        create_clock -name clk1 -period 5.0 [get_ports clk1]
        create_clock -name clk2 -period 5.0 [get_ports clk2]
        set_clock_groups -asynchronous -group [get_clocks clk1]
        set_clock_uncertainty 0.1
        set_input_delay -clock clk1 1.0 [get_ports in1]
        set_output_delay -clock clk1 1.0 [get_ports out1]
        """
        report = self._lint_string(sdc)
        rule_ids = [v.rule_id for v in report.violations]
        self.assertIn("CDC-001", rule_ids)

    def test_waveform_edge_cases(self):
        """Checks invalid waveform specifications: rise >= fall, edge exceeding period, non-2 edges."""
        # 1. Rise >= Fall
        sdc1 = "create_clock -name bad_wf -period 10.0 -waveform {5.0 2.0} [get_ports clk]\n"
        report1 = self._lint_string(sdc1)
        self.assertTrue(any(v.rule_id == "CLK-002" and "rising edge" in v.message for v in report1.violations))

        # 2. Edge exceeding period
        sdc2 = "create_clock -name over_wf -period 10.0 -waveform {0.0 12.0} [get_ports clk]\n"
        report2 = self._lint_string(sdc2)
        self.assertTrue(any(v.rule_id == "CLK-002" and "exceeds period" in v.message for v in report2.violations))

        # 3. Only 1 edge
        sdc3 = "create_clock -name single_edge -period 10.0 -waveform {5.0} [get_ports clk]\n"
        report3 = self._lint_string(sdc3)
        self.assertTrue(any(v.rule_id == "CLK-002" and "Must specify rising and falling" in v.message for v in report3.violations))

    def test_unconstrained_io_delays(self):
        """Verifies IO-001 and IO-002 for missing input and output delays."""
        sdc = """
        create_clock -name clk -period 10.0 [get_ports clk]
        set_clock_uncertainty 0.1
        """
        report = self._lint_string(sdc)
        rule_ids = {v.rule_id for v in report.violations}
        self.assertIn("IO-001", rule_ids)
        self.assertIn("IO-002", rule_ids)

    def test_extreme_and_negative_delays(self):
        """Verifies IO-003 triggers on excessive delay (> 85% clock period) or negative delay."""
        sdc = """
        create_clock -name clk -period 10.0 [get_ports clk]
        set_clock_uncertainty 0.1
        set_input_delay -clock clk -max 9.20 [get_ports in_excessive]
        set_output_delay -clock clk -min -0.50 [get_ports out_neg]
        """
        report = self._lint_string(sdc)
        io_003 = [v for v in report.violations if v.rule_id == "IO-003"]
        self.assertGreaterEqual(len(io_003), 2)
        messages = [v.message for v in io_003]
        self.assertTrue(any("85%" in m for m in messages))
        self.assertTrue(any("Negative" in m for m in messages))

    def test_duplicate_clock_names(self):
        """Verifies CLK-004 triggers when the same clock name is defined multiple times."""
        sdc = """
        create_clock -name master_clk -period 10.0 [get_ports clk1]
        create_clock -name master_clk -period 12.0 [get_ports clk2]
        """
        report = self._lint_string(sdc)
        self.assertTrue(any(v.rule_id == "CLK-004" for v in report.violations))

    def test_trailing_backslash_syntax_error(self):
        """Verifies trailing backslash at end of file raises SYN-000 syntax error."""
        sdc = "create_clock -name test_clk -period 5.0 \\\n"
        report = self._lint_string(sdc)
        self.assertTrue(any(v.rule_id == "SYN-000" for v in report.violations))


if __name__ == "__main__":
    unittest.main()
