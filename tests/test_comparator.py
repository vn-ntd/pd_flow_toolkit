"""
Unit tests for PD Run Comparator and HTML Dashboard.
"""

import unittest
from pathlib import Path
import tempfile
import os
from pd_toolkit.parsers import parse_reports
from pd_toolkit.comparator import RunComparator
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
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
