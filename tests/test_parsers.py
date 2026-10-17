"""
Unit tests for OpenROAD and Innovus report parsers.
"""

import unittest
from pathlib import Path
from pd_toolkit.parsers import parse_reports, OpenROADParser, InnovusParser


class TestParsers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples_dir = Path(__file__).parent.parent / "examples"

    def test_openroad_parser(self):
        or_path = self.examples_dir / "openroad_run"
        metrics = parse_reports(str(or_path), tool="openroad", design_name="riscv_core")

        self.assertEqual(metrics.tool_name, "OpenROAD")
        self.assertEqual(metrics.design_name, "riscv_core")
        self.assertAlmostEqual(metrics.timing.setup_wns, -0.140, places=3)
        self.assertAlmostEqual(metrics.timing.setup_tns, -4.320, places=3)
        self.assertEqual(metrics.timing.setup_fep, 18)
        self.assertAlmostEqual(metrics.timing.hold_wns, 0.035, places=3)
        self.assertEqual(metrics.drc.total_violations, 7)
        self.assertIn("Short", metrics.drc.violations_by_type)
        self.assertAlmostEqual(metrics.congestion.max_pct, 89.20, places=2)
        self.assertAlmostEqual(metrics.area_power.utilization_pct, 64.2, places=1)
        self.assertEqual(metrics.overall_status, "FAIL")

    def test_innovus_parser(self):
        inn_path = self.examples_dir / "innovus_run"
        metrics = parse_reports(str(inn_path), tool="innovus", design_name="gpu_shader_tile")

        self.assertEqual(metrics.tool_name, "Innovus")
        self.assertEqual(metrics.design_name, "gpu_shader_tile")
        self.assertAlmostEqual(metrics.timing.setup_wns, -0.085, places=3)
        self.assertAlmostEqual(metrics.timing.setup_tns, -2.140, places=3)
        self.assertEqual(metrics.timing.setup_fep, 9)
        self.assertAlmostEqual(metrics.timing.hold_wns, 0.022, places=3)
        self.assertEqual(metrics.drc.total_violations, 4)
        self.assertIn("Spacing", metrics.drc.violations_by_type)
        self.assertAlmostEqual(metrics.area_power.utilization_pct, 71.4, places=1)


if __name__ == "__main__":
    unittest.main()
