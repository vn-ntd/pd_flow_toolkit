"""
Base Data Models and Parser Interface for Physical Design Reports.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
import json


@dataclass
class TimingSummary:
    setup_wns: float = 0.0          # Worst Negative Slack (ns)
    setup_tns: float = 0.0          # Total Negative Slack (ns)
    setup_fep: int = 0              # Failing Endpoints count
    hold_wns: float = 0.0           # Hold WNS (ns)
    hold_tns: float = 0.0           # Hold TNS (ns)
    hold_fep: int = 0               # Hold Failing Endpoints count
    max_slew_violations: int = 0
    max_cap_violations: int = 0
    max_clock_skew: float = 0.0     # (ns)

    @property
    def setup_passed(self) -> bool:
        return self.setup_wns >= 0.0

    @property
    def hold_passed(self) -> bool:
        return self.hold_wns >= 0.0


@dataclass
class DRCSummary:
    total_violations: int = 0
    violations_by_type: Dict[str, int] = field(default_factory=dict)
    violations_by_layer: Dict[str, int] = field(default_factory=dict)
    violations_details: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.total_violations == 0


@dataclass
class CongestionSummary:
    h_max_pct: float = 0.0          # Horizontal max congestion %
    v_max_pct: float = 0.0          # Vertical max congestion %
    max_pct: float = 0.0            # Overall peak congestion %
    overflow_h: int = 0
    overflow_v: int = 0
    hotspot_count: int = 0

    @property
    def is_congested(self) -> bool:
        return self.max_pct >= 100.0 or (self.overflow_h + self.overflow_v) > 0


@dataclass
class AreaPowerSummary:
    die_area_um2: float = 0.0
    core_area_um2: float = 0.0
    cell_area_um2: float = 0.0
    utilization_pct: float = 0.0
    std_cell_count: int = 0
    macro_count: int = 0
    internal_power_mw: float = 0.0
    switching_power_mw: float = 0.0
    leakage_power_mw: float = 0.0
    total_power_mw: float = 0.0


@dataclass
class PDRunMetrics:
    design_name: str = "Unknown"
    tool_name: str = "Unknown"      # "OpenROAD" or "Innovus"
    stage: str = "Signoff"           # "Floorplan", "Placement", "CTS", "Route", "Signoff"
    run_date: str = ""
    timing: TimingSummary = field(default_factory=TimingSummary)
    drc: DRCSummary = field(default_factory=DRCSummary)
    congestion: CongestionSummary = field(default_factory=CongestionSummary)
    area_power: AreaPowerSummary = field(default_factory=AreaPowerSummary)
    raw_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @property
    def overall_status(self) -> str:
        """Determines if the PD run passes signoff quality checks."""
        if not self.timing.setup_passed or not self.timing.hold_passed or not self.drc.passed:
            return "FAIL"
        if self.congestion.is_congested or self.timing.max_slew_violations > 0 or self.timing.max_cap_violations > 0:
            return "WARN"
        return "PASS"


class BaseReportParser(ABC):
    """Abstract interface for EDA report parsers."""

    def __init__(self, directory_or_file: str):
        self.target_path = directory_or_file

    @abstractmethod
    def parse(self) -> PDRunMetrics:
        """Parses the reports and returns standardized PDRunMetrics."""
        pass
