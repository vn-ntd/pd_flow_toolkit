"""
EDA Report Parsers Module.
Auto-detects and parses OpenROAD or Cadence Innovus physical design reports.
"""

from pathlib import Path
from typing import Optional
from .base_parser import PDRunMetrics, BaseReportParser
from .openroad_parser import OpenROADParser
from .innovus_parser import InnovusParser


def detect_tool(target_path: str) -> str:
    """Heuristically inspects report files to detect OpenROAD vs Innovus."""
    p = Path(target_path)
    files = [p] if p.is_file() else list(p.glob("**/*"))[:30]

    for f in files:
        if not f.is_file():
            continue
        fname = f.name.lower()
        if "timedesign" in fname or "verifygeom" in fname or "innovus" in fname or "tarpt" in fname:
            return "innovus"
        if "openroad" in fname or "opensta" in fname or "triton" in fname or "drc.rpt" in fname:
            return "openroad"
        try:
            sample = f.read_text(encoding="utf-8", errors="ignore")[:2000]
            if "Cadence Design Systems" in sample or "timeDesign" in sample or "Innovus" in sample:
                return "innovus"
            if "OpenROAD" in sample or "OpenSTA" in sample or "TritonRoute" in sample:
                return "openroad"
        except Exception:
            pass

    return "openroad"  # Default fallback


def parse_reports(
    target_path: str,
    tool: Optional[str] = None,
    design_name: Optional[str] = None,
) -> PDRunMetrics:
    """Entry point to parse reports with auto-detection."""
    if not tool or tool.lower() == "auto":
        detected = detect_tool(target_path)
    else:
        detected = tool.lower()

    if "innovus" in detected:
        parser = InnovusParser(target_path, design_name=design_name)
    else:
        parser = OpenROADParser(target_path, design_name=design_name)

    return parser.parse()


__all__ = ["PDRunMetrics", "BaseReportParser", "OpenROADParser", "InnovusParser", "parse_reports", "detect_tool"]
