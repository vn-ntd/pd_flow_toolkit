"""
Unit tests for PD Run Comparator and HTML Dashboard.
"""

import unittest
from pathlib import Path
import tempfile
import os
from pd_toolkit.parsers import parse_reports, PDRunMetrics
from pd_toolkit.parsers.base_parser import AreaPowerSummary, TimingSummary, CongestionSummary
from pd_toolkit.comparator import RunComparator, MetricDelta
from pd_toolkit.dashboard import generate_html_dashboard


class TestComparatorAndDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples_dir = Path(__file__).parent.parent / "examples"
        cls.or_metrics = parse_reports(str(cls.examples_dir / "openroad_run"), tool="openroad", design_name="riscv_core")
        cls.inn_metrics = parse_reports(str(cls.examples_dir / "innovus_run"), tool="innovus", design_name="gpu_shader_tile")

    def test_run_comparator(self):
        diff = RunComparator.compare(self.or_metrics, self.inn_metrics)
        # Setup WNS: baseline=-0.140, current=-0.085 => delta = +0.055 (improved)
        self.assertAlmostEqual(diff.setup_wns.delta, 0.055, places=3)
        self.assertTrue(diff.setup_wns.improved)

        # Total DRC: baseline=7, current=4 => delta = -3 (improved)
        self.assertEqual(diff.total_drc.delta, -3)
        self.assertTrue(diff.total_drc.improved)

    def test_integer_drc_and_fep_formatting(self):
        """Ensures DRC count and failing endpoints format as clean integers, not floats."""
        diff = RunComparator.compare(self.or_metrics, self.inn_metrics)
        self.assertTrue(diff.total_drc.is_integer)
        self.assertTrue(diff.setup_fep.is_integer)
        self.assertEqual(diff.total_drc.formatted_delta(), "-3")
        self.assertNotIn(".000", diff.total_drc.formatted_delta())
        self.assertNotIn(".000", diff.setup_fep.formatted_delta())

        d = diff.to_dict()
        self.assertEqual(d["total_drc"], "-3")

    def test_utilization_regression_logic(self):
        """Tests utilization safety thresholds: delta <= +5% and current <= 85%."""
        base = PDRunMetrics(design_name="top", area_power=AreaPowerSummary(utilization_pct=60.0))

        # 1. Normal safe increase: 60% -> 63% (+3% <= 5%, 63% <= 85%) -> improved
        curr_safe = PDRunMetrics(design_name="top", area_power=AreaPowerSummary(utilization_pct=63.0))
        diff1 = RunComparator.compare(base, curr_safe)
        self.assertTrue(diff1.utilization.improved)

        # 2. Excessive area bloat: 60% -> 68% (+8% > 5%) -> not improved (regression risk)
        curr_bloat = PDRunMetrics(design_name="top", area_power=AreaPowerSummary(utilization_pct=68.0))
        diff2 = RunComparator.compare(base, curr_bloat)
        self.assertFalse(diff2.utilization.improved)

        # 3. High congestion risk: 82% -> 87% (current > 85%) -> not improved
        base_high = PDRunMetrics(design_name="top", area_power=AreaPowerSummary(utilization_pct=82.0))
        curr_high = PDRunMetrics(design_name="top", area_power=AreaPowerSummary(utilization_pct=87.0))
        diff3 = RunComparator.compare(base_high, curr_high)
        self.assertFalse(diff3.utilization.improved)

        # 4. Abnormal drop: 70% -> 55% (-15% < -10%) -> not improved (possible logic loss)
        base_drop = PDRunMetrics(design_name="top", area_power=AreaPowerSummary(utilization_pct=70.0))
        curr_drop = PDRunMetrics(design_name="top", area_power=AreaPowerSummary(utilization_pct=55.0))
        diff4 = RunComparator.compare(base_drop, curr_drop)
        self.assertFalse(diff4.utilization.improved)

        # 5. Baseline with 0% utilization: current <= 85% -> improved
        base_zero = PDRunMetrics(design_name="top", area_power=AreaPowerSummary(utilization_pct=0.0))
        curr_norm = PDRunMetrics(design_name="top", area_power=AreaPowerSummary(utilization_pct=70.0))
        diff5 = RunComparator.compare(base_zero, curr_norm)
        self.assertTrue(diff5.utilization.improved)

    def test_timing_and_congestion_deltas(self):
        """Verifies that higher slack and lower congestion are identified as improvements."""
        base = PDRunMetrics(
            timing=TimingSummary(setup_wns=-0.200, setup_tns=-5.000, hold_wns=-0.050),
            congestion=CongestionSummary(max_pct=95.0),
        )
        curr_good = PDRunMetrics(
            timing=TimingSummary(setup_wns=-0.100, setup_tns=-2.000, hold_wns=0.020),
            congestion=CongestionSummary(max_pct=82.0),
        )
        diff = RunComparator.compare(base, curr_good)
        self.assertTrue(diff.setup_wns.improved)
        self.assertTrue(diff.setup_tns.improved)
        self.assertTrue(diff.hold_wns.improved)
        self.assertTrue(diff.max_congestion.improved)

        # Regression case
        curr_bad = PDRunMetrics(
            timing=TimingSummary(setup_wns=-0.350, setup_tns=-8.000, hold_wns=-0.100),
            congestion=CongestionSummary(max_pct=98.5),
        )
        diff_reg = RunComparator.compare(base, curr_bad)
        self.assertFalse(diff_reg.setup_wns.improved)
        self.assertFalse(diff_reg.setup_tns.improved)
        self.assertFalse(diff_reg.hold_wns.improved)
        self.assertFalse(diff_reg.max_congestion.improved)

    def test_ppa_power_and_cells(self):
        """Verifies PPA completion by testing power and std cell count deltas."""
        base = PDRunMetrics(
            design_name="top",
            area_power=AreaPowerSummary(total_power_mw=50.0, std_cell_count=20000),
        )
        curr = PDRunMetrics(
            design_name="top",
            area_power=AreaPowerSummary(total_power_mw=45.5, std_cell_count=19500),
        )
        diff = RunComparator.compare(base, curr)
        self.assertAlmostEqual(diff.total_power.delta, -4.5, places=1)
        self.assertTrue(diff.total_power.improved)
        self.assertEqual(diff.std_cell_count.delta, -500)
        self.assertTrue(diff.std_cell_count.improved)
        self.assertTrue(diff.std_cell_count.is_integer)
        self.assertIn("total_power", diff.to_dict())
        self.assertIn("std_cell_count", diff.to_dict())

    def test_html_dashboard_generation(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
            temp_path = tf.name

        try:
            res = generate_html_dashboard(self.or_metrics, temp_path)
            self.assertTrue(os.path.exists(res))
            content = Path(res).read_text(encoding="utf-8")
            self.assertIn("riscv_core", content)
            self.assertIn("-0.140 ns", content)
            self.assertIn("Total DRC Violations", content)
            self.assertIn("89.2%", content)
            self.assertIn("Internal Power", content)
            self.assertIn("Switching Power", content)
            self.assertIn("drcSearchInput", content)
            self.assertIn("copySummaryBtn", content)
            self.assertIn("filterDrcTable", content)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_metric_delta_formatted_string(self):
        """Verifies formatting of positive, negative, and zero deltas with units."""
        m_pos = MetricDelta(baseline=1.0, current=2.5, delta=1.5, improved=True, unit="ns")
        self.assertEqual(m_pos.formatted_delta(), "+1.500 ns")

        m_neg = MetricDelta(baseline=5.0, current=2.0, delta=-3.0, improved=True, unit="mW")
        self.assertEqual(m_neg.formatted_delta(), "-3.000 mW")

        m_int = MetricDelta(baseline=10.0, current=4.0, delta=-6.0, improved=True, is_integer=True)
        self.assertEqual(m_int.formatted_delta(), "-6")


if __name__ == "__main__":
    unittest.main()
