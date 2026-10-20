"""
Unit tests for OpenROAD and Innovus report parsers.
"""

import unittest
from pathlib import Path
import tempfile
from pd_toolkit.parsers import parse_reports, detect_tool, OpenROADParser, InnovusParser
from pd_toolkit.parsers.base_parser import AreaPowerSummary, TimingSummary, DRCSummary


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

    def test_innovus_area_and_power_extraction(self):
        """Verifies full extraction of Core Area, Std Cell Count, Macro Count, and Power breakdown."""
        inn_path = self.examples_dir / "innovus_run"
        metrics = parse_reports(str(inn_path), tool="innovus", design_name="gpu_shader_tile")

        self.assertAlmostEqual(metrics.area_power.core_area_um2, 285400.0, places=1)
        self.assertAlmostEqual(metrics.area_power.die_area_um2, 342150.0, places=1)
        self.assertEqual(metrics.area_power.std_cell_count, 45210)
        self.assertEqual(metrics.area_power.macro_count, 6)
        self.assertAlmostEqual(metrics.area_power.total_power_mw, 58.75, places=2)
        self.assertAlmostEqual(metrics.area_power.internal_power_mw, 31.20, places=2)
        self.assertAlmostEqual(metrics.area_power.switching_power_mw, 22.45, places=2)
        self.assertAlmostEqual(metrics.area_power.leakage_power_mw, 5.10, places=2)

    def test_openroad_power_breakdown_and_units(self):
        """Verifies OpenROAD extraction of internal, switching, and total power in mW."""
        or_path = self.examples_dir / "openroad_run"
        metrics = parse_reports(str(or_path), tool="openroad", design_name="riscv_core")

        self.assertAlmostEqual(metrics.area_power.total_power_mw, 34.82, places=2)
        self.assertAlmostEqual(metrics.area_power.internal_power_mw, 18.25, places=2)
        self.assertAlmostEqual(metrics.area_power.switching_power_mw, 14.12, places=2)
        self.assertAlmostEqual(metrics.area_power.leakage_power_mw, 2.45, places=2)
        self.assertEqual(metrics.area_power.std_cell_count, 18450)
        self.assertEqual(metrics.area_power.macro_count, 2)

    def test_power_unit_normalization_multi_units(self):
        """Verifies power unit conversions: W, uW, nW -> mW."""
        parser = OpenROADParser(".")
        ap = AreaPowerSummary()

        # Test Watts (0.035 W -> 35.0 mW)
        sample_w = "Total Power: 0.035 W\nInternal Power: 0.020 W\nSwitching Power: 0.012 W\nLeakage Power: 0.003 W"
        parser._parse_area_power(sample_w, ap)
        self.assertAlmostEqual(ap.total_power_mw, 35.0, places=2)
        self.assertAlmostEqual(ap.internal_power_mw, 20.0, places=2)
        self.assertAlmostEqual(ap.switching_power_mw, 12.0, places=2)
        self.assertAlmostEqual(ap.leakage_power_mw, 3.0, places=2)

        # Test MicroWatts (45000 uW -> 45.0 mW)
        ap2 = AreaPowerSummary()
        sample_uw = "Total Power: 45000 uW\nInternal Power: 25000 uW\nSwitching Power: 18000 uW\nLeakage Power: 2000 uW"
        parser._parse_area_power(sample_uw, ap2)
        self.assertAlmostEqual(ap2.total_power_mw, 45.0, places=2)
        self.assertAlmostEqual(ap2.internal_power_mw, 25.0, places=2)
        self.assertAlmostEqual(ap2.switching_power_mw, 18.0, places=2)
        self.assertAlmostEqual(ap2.leakage_power_mw, 2.0, places=2)

    def test_innovus_power_unit_normalization(self):
        """Verifies Innovus power unit normalization for non-mW units."""
        parser = InnovusParser(".")
        ap = AreaPowerSummary()
        sample = "Total Power: 0.082 W\nInternal Power: 50000 uW\nSwitching Power: 25000 uW\nTotal Leakage Power: 7000 uW"
        parser._parse_area_power(sample, ap)
        self.assertAlmostEqual(ap.total_power_mw, 82.0, places=2)
        self.assertAlmostEqual(ap.internal_power_mw, 50.0, places=2)
        self.assertAlmostEqual(ap.switching_power_mw, 25.0, places=2)
        self.assertAlmostEqual(ap.leakage_power_mw, 7.0, places=2)

    def test_parser_empty_and_corrupt_files(self):
        """Verifies that parsers handle empty or malformed files gracefully without exceptions."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. Completely empty directory
            metrics = parse_reports(tmp_dir, tool="openroad")
            self.assertEqual(metrics.timing.setup_wns, 0.0)
            self.assertEqual(metrics.drc.total_violations, 0)

            # 2. Corrupt / binary / random string file
            bad_file = Path(tmp_dir) / "corrupt_report.rpt"
            bad_file.write_text("@@@ RANDOM JUNK !!! $$$ 1234 invalid @@##\n", encoding="utf-8")
            metrics_bad = parse_reports(str(bad_file), tool="innovus")
            self.assertEqual(metrics_bad.drc.total_violations, 0)
            self.assertEqual(metrics_bad.timing.setup_wns, 0.0)

    def test_detect_tool_heuristics(self):
        """Verifies automatic detection of OpenROAD vs Innovus."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            inn_rpt = Path(tmp_dir) / "timeDesign_setup.summary"
            inn_rpt.write_text("# Cadence Design Systems Innovus timeDesign\n", encoding="utf-8")
            self.assertEqual(detect_tool(tmp_dir), "innovus")

        with tempfile.TemporaryDirectory() as tmp_dir:
            or_rpt = Path(tmp_dir) / "timing.rpt"
            or_rpt.write_text("# OpenSTA OpenROAD flow timing report\n", encoding="utf-8")
            self.assertEqual(detect_tool(tmp_dir), "openroad")

    def test_drc_breakdown_by_layer_and_type(self):
        """Verifies DRC breakdown extraction by metal layer and type."""
        parser = OpenROADParser(".")
        drc = DRCSummary()
        content = """
        Total violations: 3
        violation type: Short, layer: Metal2
        violation type: MinSpacing, layer: Metal1
        violation type: MinSpacing, layer: Metal2
        """
        parser._parse_drc(content, drc)
        self.assertEqual(drc.total_violations, 3)
        self.assertEqual(drc.violations_by_type["Short"], 1)
        self.assertEqual(drc.violations_by_type["MinSpacing"], 2)
        self.assertEqual(drc.violations_by_layer["Metal1"], 1)
        self.assertEqual(drc.violations_by_layer["Metal2"], 2)

    def test_timing_drv_parsing(self):
        """Verifies max slew and capacitance violations parsing."""
        parser = OpenROADParser(".")
        t = TimingSummary()
        content = """
        [INFO] Max slew violations: 5
        [INFO] Max capacitance violations: 3
        """
        parser._parse_timing(content, t)
        self.assertEqual(t.max_slew_violations, 5)
        self.assertEqual(t.max_cap_violations, 3)


if __name__ == "__main__":
    unittest.main()
