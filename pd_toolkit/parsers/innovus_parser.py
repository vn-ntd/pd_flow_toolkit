"""
Cadence Innovus EDA Report Parser.
Extracts Timing (timeDesign WNS, TNS, Violating Paths), verifyGeometry (DRC),
Congestion, and Area/Power metrics from Cadence Innovus flow reports.
"""

import re
from pathlib import Path
from typing import List, Optional
from .base_parser import (
    BaseReportParser,
    PDRunMetrics,
    TimingSummary,
    DRCSummary,
    CongestionSummary,
    AreaPowerSummary,
)


class InnovusParser(BaseReportParser):
    """Parses Cadence Innovus reports and log summaries."""

    def __init__(self, directory_or_file: str, design_name: Optional[str] = None):
        super().__init__(directory_or_file)
        self.design_name = design_name or "innovus_design"

    def parse(self) -> PDRunMetrics:
        metrics = PDRunMetrics(
            design_name=self.design_name,
            tool_name="Innovus",
            stage="Signoff",
        )

        files_to_parse = self._gather_files()
        metrics.raw_files = [str(f) for f in files_to_parse]

        for filepath in files_to_parse:
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    self._parse_timedesign_tables(content, metrics.timing)
                    self._parse_drc_verify_geometry(content, metrics.drc)
                    self._parse_congestion(content, metrics.congestion)
                    self._parse_area_power(content, metrics.area_power)
            except Exception:
                continue

        metrics.congestion.max_pct = max(
            metrics.congestion.h_max_pct,
            metrics.congestion.v_max_pct,
            metrics.congestion.max_pct
        )

        return metrics

    def _gather_files(self) -> List[Path]:
        p = Path(self.target_path)
        if p.is_file():
            return [p]
        if p.is_dir():
            candidates = []
            for ext in ("*.rpt", "*.summary", "*.log", "*.tarpt", "*.txt"):
                candidates.extend(p.glob(f"**/{ext}"))
            return sorted(set(candidates))
        return []

    def _parse_timedesign_tables(self, content: str, timing: TimingSummary):
        # 1. Parse Innovus timeDesign Setup Table (take final signoff occurrence in log)
        if "Setup mode" in content:
            setup_part = content[content.rfind("Setup mode"):]
            wns_row = re.search(r"\|\s*WNS\s*\([^)]*\)\s*:\s*\|\s*([+-]?\d+(?:\.\d+)?|N/A)", setup_part, re.IGNORECASE)
            if wns_row and wns_row.group(1) != "N/A":
                timing.record_setup_wns(float(wns_row.group(1)))

            tns_row = re.search(r"\|\s*TNS\s*\([^)]*\)\s*:\s*\|\s*([+-]?\d+(?:\.\d+)?|N/A)", setup_part, re.IGNORECASE)
            if tns_row and tns_row.group(1) != "N/A":
                timing.setup_tns = float(tns_row.group(1))

            vio_row = re.search(r"\|\s*Violating\s+Paths\s*:\s*\|\s*(\d+)", setup_part, re.IGNORECASE)
            if vio_row:
                timing.setup_fep = int(vio_row.group(1))

        # 2. Parse Innovus timeDesign Hold Table (take final signoff occurrence in log)
        if "Hold mode" in content:
            hold_part = content[content.rfind("Hold mode"):]
            h_wns = re.search(r"\|\s*WNS\s*\([^)]*\)\s*:\s*\|\s*([+-]?\d+(?:\.\d+)?|N/A)", hold_part, re.IGNORECASE)
            if h_wns and h_wns.group(1) != "N/A":
                timing.record_hold_wns(float(h_wns.group(1)))

            h_tns = re.search(r"\|\s*TNS\s*\([^)]*\)\s*:\s*\|\s*([+-]?\d+(?:\.\d+)?|N/A)", hold_part, re.IGNORECASE)
            if h_tns and h_tns.group(1) != "N/A":
                timing.hold_tns = float(h_tns.group(1))

            h_vio = re.search(r"\|\s*Violating\s+Paths\s*:\s*\|\s*(\d+)", hold_part, re.IGNORECASE)
            if h_vio:
                timing.hold_fep = int(h_vio.group(1))

        # 3. DRVs (MaxTran / MaxCap)
        tran_vio = re.search(r"Nr\s*of\s*MaxTran\s*(?:Vio|Violations)?\s*:\s*\|\s*(\d+)", content, re.IGNORECASE)
        if tran_vio:
            timing.max_slew_violations = max(timing.max_slew_violations, int(tran_vio.group(1)))

        cap_vio = re.search(r"Nr\s*of\s*MaxCap\s*(?:Vio|Violations)?\s*:\s*\|\s*(\d+)", content, re.IGNORECASE)
        if cap_vio:
            timing.max_cap_violations = max(timing.max_cap_violations, int(cap_vio.group(1)))

        # 4. Fallback standard regex if table was not standard ASCII box
        if timing.setup_wns == 0.0 and "Setup mode" not in content and "Hold mode" not in content:
            m = re.search(r"(?:worst\s+slack|wns)\s*[:=]\s*([+-]?\d+(?:\.\d+)?)", content, re.IGNORECASE)
            if m:
                timing.record_setup_wns(float(m.group(1)))

    def _parse_drc_verify_geometry(self, content: str, drc: DRCSummary):
        # Innovus verifyGeometry / verify_drc output:
        # "Total Violations : 18"
        tot = re.search(r"Total\s+Violations\s*[:=]\s*(\d+)", content, re.IGNORECASE)
        if tot:
            drc.total_violations = max(drc.total_violations, int(tot.group(1)))

        # Breakdown summary rows:
        #   Short              :   4
        #   Spacing            :  10
        #   MinWidth           :   4
        for m in re.finditer(r"^\s*([A-Za-z0-9_]+)\s*:\s*(\d+)\s*$", content, re.MULTILINE):
            vtype, count = m.group(1), int(m.group(2))
            if vtype.lower() not in ("total", "violations", "date", "warnings", "errors"):
                drc.violations_by_type[vtype] = drc.violations_by_type.get(vtype, 0) + count

        # Check for detailed VIOLATION lines:
        # VIOLATION: Metal2 Spacing ...
        for m in re.finditer(r"VIOLATION\s*:\s*([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)", content, re.IGNORECASE):
            layer, vtype = m.group(1), m.group(2)
            drc.violations_by_layer[layer] = drc.violations_by_layer.get(layer, 0) + 1
            drc.violations_by_type[vtype] = drc.violations_by_type.get(vtype, 0) + 1
            drc.violations_details.append({"layer": layer, "type": vtype})

        # Recalculate total if breakdown found but total was 0
        if drc.total_violations == 0 and drc.violations_by_type:
            drc.total_violations = sum(drc.violations_by_type.values())

    def _parse_congestion(self, content: str, cong: CongestionSummary):
        # Innovus reportCongestion:
        # "Max H Congestion: 85.4%"
        # "Max V Congestion: 89.2%"
        h_m = re.search(r"(?:Max\s+H\s+Congestion|Horizontal\s+Congestion)\s*[:=]\s*([0-9.]+)\s*%", content, re.IGNORECASE)
        if h_m:
            cong.h_max_pct = max(cong.h_max_pct, float(h_m.group(1)))

        v_m = re.search(r"(?:Max\s+V\s+Congestion|Vertical\s+Congestion)\s*[:=]\s*([0-9.]+)\s*%", content, re.IGNORECASE)
        if v_m:
            cong.v_max_pct = max(cong.v_max_pct, float(v_m.group(1)))

        # Explicit Horizontal & Vertical Overflow
        h_ovf = re.search(r"(?:Horizontal\s+Overflow|H-Overflow)\s*[:=]\s*(\d+)", content, re.IGNORECASE)
        if h_ovf:
            cong.overflow_h = max(cong.overflow_h, int(h_ovf.group(1)))

        v_ovf = re.search(r"(?:Vertical\s+Overflow|V-Overflow)\s*[:=]\s*(\d+)", content, re.IGNORECASE)
        if v_ovf:
            cong.overflow_v = max(cong.overflow_v, int(v_ovf.group(1)))

        # Fallback 2D Overflow if H/V were not separately specified (preserve total without fabricating 50/50 split)
        if cong.overflow_h == 0 and cong.overflow_v == 0:
            ovf = re.search(r"(?:Total\s+2D\s+Overflow|2D\s+Overflow|overflow)\s*[:=]\s*(\d+)", content, re.IGNORECASE)
            if ovf:
                val = int(ovf.group(1))
                cong.overflow_h = val
                cong.overflow_v = 0

        # Hotspots
        hot = re.search(r"(?:Hotspot\s+Count|Congested\s+Bins)\s*[:=]\s*(\d+)", content, re.IGNORECASE)
        if hot:
            cong.hotspot_count = max(cong.hotspot_count, int(hot.group(1)))

    def _parse_area_power(self, content: str, ap: AreaPowerSummary):
        # Total Area / Die Area
        tot_area = re.search(r"(?:Total\s+Area|Die\s+Area)\s*[:=]\s*([0-9.]+)", content, re.IGNORECASE)
        if tot_area:
            ap.die_area_um2 = float(tot_area.group(1))

        # Core Area
        core_area = re.search(r"Core\s+Area\s*[:=]\s*([0-9.]+)", content, re.IGNORECASE)
        if core_area:
            ap.core_area_um2 = float(core_area.group(1))

        # Cell Area
        cell_area = re.search(r"Cell\s+Area\s*[:=]\s*([0-9.]+)", content, re.IGNORECASE)
        if cell_area:
            ap.cell_area_um2 = float(cell_area.group(1))

        # Density / Utilization: "Density / Utilization: 71.4%" or "Core Utilization: 68.5%"
        util = re.search(r"(?:Density\s*/\s*Utilization|Density|Core\s+Utilization|Utilization)\s*[:=]\s*([0-9.]+)\s*%", content, re.IGNORECASE)
        if util:
            ap.utilization_pct = float(util.group(1))

        # Standard Cell Count: "Standard Cell Count: 45210"
        std_cell = re.search(r"(?:Standard\s*Cell\s*Count|Std\s*Cell\s*Count|Total\s*Std\s*Cells?)\s*[:=]\s*(\d+)", content, re.IGNORECASE)
        if std_cell:
            ap.std_cell_count = max(ap.std_cell_count, int(std_cell.group(1)))

        # Macro Count: "Macro Count: 6"
        macros = re.search(r"(?:Macro\s*Count|Number\s+of\s+Macros|Total\s*Macros?)\s*[:=]\s*(\d+)", content, re.IGNORECASE)
        if macros:
            ap.macro_count = max(ap.macro_count, int(macros.group(1)))

        # Power parsing with unit normalization
        tot_pow = re.search(r"(?:Total\s+Power|Total\s+Internal\s+Power)\s*[:=]\s*([0-9.e+-]+)\s*(nW|uW|µW|mW|W)?", content, re.IGNORECASE)
        if tot_pow:
            val = float(tot_pow.group(1))
            unit = tot_pow.group(2) or "mW"
            ap.total_power_mw = self._normalize_power_mw(val, unit)

        int_pow = re.search(r"Internal\s+Power\s*[:=]\s*([0-9.e+-]+)\s*(nW|uW|µW|mW|W)?", content, re.IGNORECASE)
        if int_pow:
            val = float(int_pow.group(1))
            unit = int_pow.group(2) or "mW"
            ap.internal_power_mw = self._normalize_power_mw(val, unit)

        sw_pow = re.search(r"Switching\s+Power\s*[:=]\s*([0-9.e+-]+)\s*(nW|uW|µW|mW|W)?", content, re.IGNORECASE)
        if sw_pow:
            val = float(sw_pow.group(1))
            unit = sw_pow.group(2) or "mW"
            ap.switching_power_mw = self._normalize_power_mw(val, unit)

        leak = re.search(r"(?:Total\s+Leakage\s+Power|Leakage\s+Power)\s*[:=]\s*([0-9.e+-]+)\s*(nW|uW|µW|mW|W)?", content, re.IGNORECASE)
        if leak:
            val = float(leak.group(1))
            unit = leak.group(2) or "mW"
            ap.leakage_power_mw = self._normalize_power_mw(val, unit)
