"""
Unit tests for PD Flow Toolkit CLI commands and option parsing.
"""

import unittest
from pathlib import Path
import tempfile
import os
import json
from pd_toolkit.cli import build_parser, cmd_parse, cmd_lint_sdc, cmd_compare, cmd_demo, print_banner


class TestCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples_dir = Path(__file__).parent.parent / "examples"
        cls.parser = build_parser()

    def test_banner_execution(self):
        """Verifies print_banner runs without throwing any encoding or formatting errors."""
        try:
            print_banner()
        except Exception as e:
            self.fail(f"print_banner raised an unexpected exception: {e}")

    def test_cli_demo_command(self):
        """Verifies turnkey demo command executes with exit code 0."""
        args = self.parser.parse_args(["demo"])
        ret = cmd_demo(args)
        self.assertEqual(ret, 0)

    def test_cli_parse_openroad(self):
        """Verifies parsing openroad run through CLI."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_out = Path(tmp_dir) / "metrics.json"
            dash_out = Path(tmp_dir) / "dash.html"

            args = self.parser.parse_args([
                "parse",
                "--path", str(self.examples_dir / "openroad_run"),
                "--tool", "openroad",
                "--design", "riscv_core",
                "--output-json", str(json_out),
                "--dashboard", str(dash_out),
            ])
            # OpenROAD run has DRC violations so status is FAIL -> exit code 1
            ret = cmd_parse(args)
            self.assertEqual(ret, 1)

            # Check JSON output
            self.assertTrue(json_out.exists())
            data = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(data["design_name"], "riscv_core")
            self.assertEqual(data["tool_name"], "OpenROAD")
            self.assertEqual(data["drc"]["total_violations"], 7)

            # Check Dashboard output
            self.assertTrue(dash_out.exists())
            html = dash_out.read_text(encoding="utf-8")
            self.assertIn("riscv_core", html)

    def test_cli_parse_innovus(self):
        """Verifies parsing innovus run through CLI."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_out = Path(tmp_dir) / "inn_metrics.json"
            dash_out = Path(tmp_dir) / "inn_dash.html"

            args = self.parser.parse_args([
                "parse",
                "--path", str(self.examples_dir / "innovus_run"),
                "--tool", "innovus",
                "--design", "gpu_shader_tile",
                "--output-json", str(json_out),
                "--dashboard", str(dash_out),
            ])
            ret = cmd_parse(args)
            self.assertEqual(ret, 1)  # 4 DRC violations -> FAIL -> 1

            self.assertTrue(json_out.exists())
            data = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(data["design_name"], "gpu_shader_tile")
            self.assertEqual(data["area_power"]["std_cell_count"], 45210)
            self.assertEqual(data["area_power"]["macro_count"], 6)

    def test_cli_lint_sdc_clean(self):
        """Verifies clean SDC constraints return exit code 0."""
        clean_file = self.examples_dir / "sdc" / "clean_soc.sdc"
        args = self.parser.parse_args(["lint-sdc", "--sdc", str(clean_file)])
        ret = cmd_lint_sdc(args)
        self.assertEqual(ret, 0)

    def test_cli_lint_sdc_dirty_and_json(self):
        """Verifies buggy SDC returns exit code 1 and exports JSON report."""
        dirty_file = self.examples_dir / "sdc" / "dirty_soc.sdc"
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_out = Path(tmp_dir) / "lint_report.json"
            args = self.parser.parse_args([
                "lint-sdc",
                "--sdc", str(dirty_file),
                "--output-json", str(json_out),
            ])
            ret = cmd_lint_sdc(args)
            self.assertEqual(ret, 1)

            self.assertTrue(json_out.exists())
            data = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertFalse(data["passed"])
            self.assertGreater(data["error_count"], 0)
            self.assertGreater(data["warning_count"], 0)

    def test_cli_lint_sdc_missing_file(self):
        """Verifies error handling for non-existent SDC file."""
        args = self.parser.parse_args(["lint-sdc", "--sdc", "non_existent_file.sdc"])
        ret = cmd_lint_sdc(args)
        self.assertEqual(ret, 1)

    def test_cli_lint_sdc_fail_on_warning(self):
        """Verifies --fail-on-warning flag returns 1 when warnings exist."""
        # Create an SDC with no errors but 1 warning (e.g. unconstrained IO)
        sdc = """
        create_clock -name clk -period 5.0 [get_ports clk]
        set_clock_uncertainty 0.1
        """
        with tempfile.NamedTemporaryFile("w", suffix=".sdc", delete=False, encoding="utf-8") as tf:
            tf.write(sdc)
            temp_path = tf.name
        try:
            # Without fail-on-warning: error_count == 0 -> returns 0
            args_normal = self.parser.parse_args(["lint-sdc", "--sdc", temp_path])
            self.assertEqual(cmd_lint_sdc(args_normal), 0)

            # With fail-on-warning: warning_count > 0 -> returns 1
            args_strict = self.parser.parse_args(["lint-sdc", "--sdc", temp_path, "--fail-on-warning"])
            self.assertEqual(cmd_lint_sdc(args_strict), 1)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_cli_compare(self):
        """Verifies compare command executes with exit code 0."""
        base_path = self.examples_dir / "openroad_run"
        curr_path = self.examples_dir / "innovus_run"

        args = self.parser.parse_args([
            "compare",
            "--baseline", str(base_path),
            "--current", str(curr_path),
        ])
        ret = cmd_compare(args)
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
