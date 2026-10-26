"""
Unit tests for OpenROAD and Innovus report parsers.
"""

import unittest
from pathlib import Path
import tempfile
from pd_toolkit.parsers import parse_reports, detect_tool, OpenROADParser, InnovusParser
from pd_toolkit.parsers.base_parser import AreaPowerSummary, TimingSummary, DRCSummary, CongestionSummary


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

    def test_openroad_csv_micro_power(self):
        """Verifies CSV parsing correctly converts sub-microwatt values without inverted multiplication."""
        parser = OpenROADParser(".")
        metrics = parse_reports(str(self.examples_dir / "openroad_run"), tool="openroad")
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as tf:
            tf.write("spef_wns,spef_tns,power_typical_internal_uW,power_typical_switching_uW,power_typical_leakage_uW\n")
            tf.write("-0.05,-1.2,0.45,0.25,0.10\n")
            csv_path = Path(tf.name)
        try:
            parser._parse_metrics_csv(csv_path, metrics)
            # 0.45 uW should be 0.00045 mW, NOT 450.0 mW
            self.assertAlmostEqual(metrics.area_power.internal_power_mw, 0.00045, places=5)
            self.assertAlmostEqual(metrics.area_power.switching_power_mw, 0.00025, places=5)
            self.assertAlmostEqual(metrics.area_power.leakage_power_mw, 0.00010, places=5)
        finally:
            if csv_path.exists():
                csv_path.unlink()

    def test_triton_multiline_drc(self):
        """Verifies multiline TritonRoute DRC violation block extracts layer properly."""
        parser = OpenROADParser(".")
        drc = DRCSummary()
        content = """
        [INFO DRT-0199] Total violations: 2
        violation type: Short
          srcs: net1 net2
          layer: Metal3
        violation type: MinSpacing
          srcs: net3
          layer: Metal4
        """
        parser._parse_drc(content, drc)
        self.assertEqual(drc.total_violations, 2)
        self.assertEqual(drc.violations_by_type.get("Short"), 1)
        self.assertEqual(drc.violations_by_layer.get("Metal3"), 1)
        self.assertEqual(drc.violations_by_layer.get("Metal4"), 1)

    def test_timing_exact_zero_slack_not_overwritten(self):
        """Verifies that 0.000 ns slack is not treated as uninitialized sentinel and overwritten by higher slack."""
        parser = OpenROADParser(".")
        t = TimingSummary()
        # Parse exact 0.000 critical slack first
        parser._parse_timing("[INFO] Worst slack: 0.000 ns", t)
        self.assertEqual(t.setup_wns, 0.0)
        # Parse positive slack +0.250 from second report: setup_wns should remain min(0.0, 0.25) = 0.0
        parser._parse_timing("[INFO] Worst slack: 0.250 ns", t)
        self.assertEqual(t.setup_wns, 0.0)

    def test_innovus_multistage_timing(self):
        """Verifies Innovus parser grabs the final signoff table rather than the early pre-CTS table."""
        parser = InnovusParser(".")
        t = TimingSummary()
        content = """
        ================================================================
        Setup mode (Pre-CTS Placement Stage)
        ----------------------------------------------------------------
        |  WNS (ns):   | -0.450 |
        |  TNS (ns):   | -12.50 |
        |  Violating Paths: | 45 |
        ================================================================

        ... Optimization and Routing steps ...

        ================================================================
        Setup mode (Post-Route Signoff Stage)
        ----------------------------------------------------------------
        |  WNS (ns):   | -0.050 |
        |  TNS (ns):   | -0.850 |
        |  Violating Paths: | 2  |
        ================================================================
        """
        parser._parse_timedesign_tables(content, t)
        self.assertAlmostEqual(t.setup_wns, -0.050, places=3)
        self.assertAlmostEqual(t.setup_tns, -0.850, places=3)
        self.assertEqual(t.setup_fep, 2)

    def test_innovus_explicit_hv_congestion(self):
        """Verifies Innovus parser extracts explicit H and V overflows correctly without faking 50/50 split."""
        parser = InnovusParser(".")
        c = CongestionSummary()
        content = """
        Max H Congestion: 78.5%
        Max V Congestion: 82.1%
        Horizontal Overflow: 14
        Vertical Overflow: 6
        Hotspot Count: 3
        """
        parser._parse_congestion(content, c)
        self.assertEqual(c.overflow_h, 14)
        self.assertEqual(c.overflow_v, 6)
        self.assertEqual(c.hotspot_count, 3)

    def test_openroad_single_file_target(self):
        """Verifies OpenROAD parser handles a single file as target_path."""
        rpt = self.examples_dir / "openroad_run" / "timing_setup.rpt"
        parser = OpenROADParser(str(rpt), design_name="single_file_design")
        metrics = parser.parse()
        self.assertEqual(metrics.design_name, "single_file_design")
        self.assertAlmostEqual(metrics.timing.setup_wns, -0.140, places=3)

    def test_openroad_parse_with_metrics_csv_in_dir(self):
        """Verifies OpenROAD parser automatically processes metrics.csv in directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "metrics.csv"
            csv_path.write_text(
                "wns,tns,tritonRoute_violations,Magic_violations,DIEAREA_mm^2,CoreArea_um^2,OpenDP_Util,TotalCells\n"
                "-0.15,-3.2,2,1,0.5,450000.0,65.5,12000\n",
                encoding="utf-8",
            )
            parser = OpenROADParser(tmp_dir, design_name="csv_design")
            metrics = parser.parse()
            self.assertEqual(metrics.design_name, "csv_design")
            self.assertAlmostEqual(metrics.timing.setup_wns, -0.15, places=2)
            self.assertAlmostEqual(metrics.timing.setup_tns, -3.2, places=2)
            self.assertEqual(metrics.drc.total_violations, 3)
            self.assertAlmostEqual(metrics.area_power.die_area_um2, 500000.0, places=1)
            self.assertAlmostEqual(metrics.area_power.core_area_um2, 450000.0, places=1)
            self.assertAlmostEqual(metrics.area_power.utilization_pct, 65.5, places=1)
            self.assertEqual(metrics.area_power.std_cell_count, 12000)

    def test_openroad_magic_drc_count_zero_and_nonzero(self):
        """Verifies Magic format [INFO]: COUNT: 0 clears violations and Total DRC errors: N."""
        parser = OpenROADParser(".")
        drc = DRCSummary(total_violations=5, violations_by_type={"Short": 5})
        parser._parse_drc("[INFO]: COUNT: 0", drc)
        self.assertEqual(drc.total_violations, 0)
        self.assertEqual(len(drc.violations_by_type), 0)

        drc2 = DRCSummary()
        parser._parse_drc("Total DRC errors: 12", drc2)
        self.assertEqual(drc2.total_violations, 12)

    def test_openroad_violated_slack_fep_fallback(self):
        """Verifies violated slack fallback sets setup_wns and computes FEP count."""
        parser = OpenROADParser(".")
        t = TimingSummary()
        content = """
        Path 1: slack (VIOLATED) -0.320
        Path 2: slack (VIOLATED) -0.150
        """
        parser._parse_timing(content, t)
        self.assertAlmostEqual(t.setup_wns, -0.320, places=3)
        self.assertEqual(t.setup_fep, 2)

    def test_openroad_hold_tns_and_skew(self):
        """Verifies hold_tns and clock skew extraction in OpenROAD parser."""
        parser = OpenROADParser(".")
        t = TimingSummary()
        content = """
        [INFO] Hold TNS: -0.850 ns
        [INFO] Max skew: 0.120 ns
        """
        parser._parse_timing(content, t)
        self.assertAlmostEqual(t.hold_tns, -0.850, places=3)
        self.assertAlmostEqual(t.max_clock_skew, 0.120, places=3)

    def test_openroad_vertical_overflow_and_hotspots(self):
        """Verifies vertical overflow and hotspots parsing in FastRoute."""
        parser = OpenROADParser(".")
        c = CongestionSummary()
        content = """
        [INFO GRT-0097]   Horizontal max congestion: 80.00%
        [INFO GRT-0098]   Vertical max congestion: 85.00%
        [INFO GRT-0099]   Horizontal overflow: 5
        [INFO GRT-0100]   Vertical overflow: 8
        Hotspots: 11
        """
        parser._parse_congestion(content, c)
        self.assertEqual(c.overflow_h, 5)
        self.assertEqual(c.overflow_v, 8)
        self.assertEqual(c.hotspot_count, 11)

    def test_unified_log_drc_not_suppressed(self):
        """Verifies that DRC violations in a unified openroad batch log are parsed even if timing markers exist."""
        parser = OpenROADParser(".")
        drc = DRCSummary()
        content = """
        Startpoint: u_reg/D
        Endpoint: u_out/Q
        slack (MET) 0.50

        [INFO DRT-0199] Total violations: 1
        violation type: Short, layer: Metal2
        """
        parser._parse_drc(content, drc)
        self.assertEqual(drc.total_violations, 1)
        self.assertEqual(drc.violations_by_type.get("Short"), 1)
        self.assertEqual(drc.violations_by_layer.get("Metal2"), 1)


if __name__ == "__main__":
    unittest.main()
