"""
PD Run Comparator and Regression Differential Engine.
Compares two Physical Design runs (Baseline vs Current) to identify timing,
DRC, congestion, and area improvements or regressions.
"""

from dataclasses import dataclass
from typing import Dict, Any
from ..parsers.base_parser import PDRunMetrics


@dataclass
class MetricDelta:
    baseline: float
    current: float
    delta: float
    improved: bool
    unit: str = ""

    def formatted_delta(self) -> str:
        sign = "+" if self.delta > 0 else ""
        return f"{sign}{self.delta:.3f} {self.unit}".strip()


@dataclass
class RunComparison:
    design_name: str
    baseline_tool: str
    current_tool: str
    setup_wns: MetricDelta
    setup_tns: MetricDelta
    setup_fep: MetricDelta
    hold_wns: MetricDelta
    total_drc: MetricDelta
    max_congestion: MetricDelta
    utilization: MetricDelta

    def to_dict(self) -> Dict[str, Any]:
        return {
            "design_name": self.design_name,
            "setup_wns": self.setup_wns.formatted_delta(),
            "setup_tns": self.setup_tns.formatted_delta(),
            "total_drc": self.total_drc.formatted_delta(),
            "max_congestion": self.max_congestion.formatted_delta(),
            "utilization": self.utilization.formatted_delta(),
        }


class RunComparator:
    """Computes deltas between two PD runs."""

    @staticmethod
    def compare(baseline: PDRunMetrics, current: PDRunMetrics) -> RunComparison:
        # For Slack (WNS/Hold WNS): higher is better (positive delta = improvement)
        wns_delta = current.timing.setup_wns - baseline.timing.setup_wns
        tns_delta = current.timing.setup_tns - baseline.timing.setup_tns
        hold_delta = current.timing.hold_wns - baseline.timing.hold_wns

        # For Violations (FEP, DRC, Congestion): lower is better (negative delta = improvement)
        fep_delta = current.timing.setup_fep - baseline.timing.setup_fep
        drc_delta = current.drc.total_violations - baseline.drc.total_violations
        cong_delta = current.congestion.max_pct - baseline.congestion.max_pct
        util_delta = current.area_power.utilization_pct - baseline.area_power.utilization_pct

        return RunComparison(
            design_name=current.design_name,
            baseline_tool=baseline.tool_name,
            current_tool=current.tool_name,
            setup_wns=MetricDelta(baseline.timing.setup_wns, current.timing.setup_wns, wns_delta, wns_delta >= 0, "ns"),
            setup_tns=MetricDelta(baseline.timing.setup_tns, current.timing.setup_tns, tns_delta, tns_delta >= 0, "ns"),
            setup_fep=MetricDelta(baseline.timing.setup_fep, current.timing.setup_fep, fep_delta, fep_delta <= 0),
            hold_wns=MetricDelta(baseline.timing.hold_wns, current.timing.hold_wns, hold_delta, hold_delta >= 0, "ns"),
            total_drc=MetricDelta(baseline.drc.total_violations, current.drc.total_violations, drc_delta, drc_delta <= 0),
            max_congestion=MetricDelta(baseline.congestion.max_pct, current.congestion.max_pct, cong_delta, cong_delta <= 0, "%"),
            utilization=MetricDelta(baseline.area_power.utilization_pct, current.area_power.utilization_pct, util_delta, True, "%"),
        )
