"""
OpenROAD EDA Report Parser.
Extracts Timing (WNS, TNS, FEP), DRC violations, Congestion, and Area/Power
from OpenROAD / OpenSTA flow outputs.
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


class OpenROADParser(BaseReportParser):
    """Parses OpenROAD / OpenSTA log and report files."""

    def __init__(self, directory_or_file: str, design_name: Optional[str] = None):
        super().__init__(directory_or_file)
        self.design_name = design_name or "openroad_design"

    def parse(self) -> PDRunMetrics:
        metrics = PDRunMetrics(
            design_name=self.design_name,
            tool_name="OpenROAD",
            stage="Signoff",
        )

        files_to_parse = self._gather_files()
        metrics.raw_files = [str(f) for f in files_to_parse]

        for filepath in files_to_parse:
            try:
                if filepath.name.lower() == "metrics.csv":
                    self._parse_metrics_csv(filepath, metrics)
                    continue
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    self._parse_timing(content, metrics.timing)
                    self._parse_drc(content, metrics.drc, filepath.name)
                    self._parse_congestion(content, metrics.congestion)
                    self._parse_area_power(content, metrics.area_power)
            except Exception:
                # Silently log or continue reading other files
                continue

        # Adjust peak congestion
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
            for ext in ("*.rpt", "*.log", "*.drc", "*.summary", "*.txt", "*.csv"):
                candidates.extend(p.glob(f"**/{ext}"))
            return sorted(set(candidates))
        return []

    def _parse_timing(self, content: str, timing: TimingSummary):
        # Skip if file is purely a DRC report
        if "detailed route drc" in content.lower() or "tritonroute drc" in content.lower():
            return

        # 1. Setup Slack / WNS
        wns_matches = re.findall(
            r"(?:worst\s+slack|worst\s+setup\s+slack|wns|setup\s+slack)\s*[:=]?\s*([+-]?\d+(?:\.\d+)?)",
            content,
            re.IGNORECASE,
        )
        if wns_matches:
            val = float(wns_matches[-1])
            timing.record_setup_wns(val)

        # Path slack (VIOLATED) -0.15
        violated_slacks = re.findall(
            r"slack\s+\(VIOLATED\)\s*[:=]?\s*([+-]?\d+(?:\.\d+)?)", content, re.IGNORECASE
        )
        if violated_slacks:
            val = min(float(x) for x in violated_slacks)
            timing.record_setup_wns(val)

        # 2. Setup TNS
        tns_matches = re.findall(
            r"(?:total\s+negative\s+slack|total\s+setup\s+negative\s+slack|tns)\s*[:=]?\s*([+-]?\d+(?:\.\d+)?)",
            content,
            re.IGNORECASE,
        )
        if tns_matches:
            val = float(tns_matches[-1])
            timing.setup_tns = min(timing.setup_tns, val) if timing.setup_tns != 0.0 else val

        # 3. Failing Endpoints (FEP) - only match explicit timing failing endpoints
        fep_matches = re.findall(
            r"(?:failing\s+endpoints|fep|slack\s+violations|timing\s+violations)\s*[:=]?\s*(\d+)",
            content,
            re.IGNORECASE,
        )
        if fep_matches:
            timing.setup_fep = max(timing.setup_fep, int(fep_matches[-1]))

        # Count occurrences of 'slack (VIOLATED)' if fep not explicitly reported
        if timing.setup_fep == 0 and violated_slacks:
            timing.setup_fep = len(violated_slacks)

        # 4. Hold Slack (min path checks)
        hold_matches = re.findall(
            r"(?:hold\s+slack|worst\s+hold\s+slack|hold_wns|min_slack)\s*[:=]?\s*([+-]?\d+(?:\.\d+)?)",
            content,
            re.IGNORECASE,
        )
        if hold_matches:
            timing.record_hold_wns(float(hold_matches[-1]))

        hold_tns_matches = re.findall(
            r"(?:hold\s+tns|hold_total_slack)\s*[:=]?\s*([+-]?\d+(?:\.\d+)?)",
            content,
            re.IGNORECASE,
        )
        if hold_tns_matches:
            timing.hold_tns = float(hold_tns_matches[-1])

        # 5. Slew / Cap / Skew
        slew_matches = re.findall(r"max\s+slew\s+violations?\s*[:=]?\s*(\d+)", content, re.IGNORECASE)
        if slew_matches:
            timing.max_slew_violations = max(timing.max_slew_violations, int(slew_matches[-1]))

        cap_matches = re.findall(r"max\s+capacitance\s+violations?\s*[:=]?\s*(\d+)", content, re.IGNORECASE)
        if cap_matches:
            timing.max_cap_violations = max(timing.max_cap_violations, int(cap_matches[-1]))

        skew_matches = re.findall(r"(?:max\s+skew|clock\s+skew)\s*[:=]?\s*([+-]?\d+(?:\.\d+)?)", content, re.IGNORECASE)
        if skew_matches:
            timing.max_clock_skew = max(timing.max_clock_skew, float(skew_matches[-1]))

    def _parse_drc(self, content: str, drc: DRCSummary, filename: str = ""):
        # Ignore purely STA logs and timing reports for DRC parsing to avoid false positives,
        # unless explicit DRC sections or tool markers are detected
        has_explicit_drc = any(
            m in content for m in ("DRT-", "TritonRoute", "detailed route drc", "violation type:", "Magic", "COUNT:")
        )
        has_sta_markers = any(
            marker in content for marker in ("Startpoint:", "Endpoint:", "Path Group:", "report_checks")
        )
        if has_sta_markers and not has_explicit_drc:
            return

        # Magic DRC OpenLane format: "[INFO]: COUNT: 0"
        magic_count = re.search(r"\[INFO\]:\s*COUNT:\s*(\d+)", content, re.IGNORECASE)
        if magic_count:
            count = int(magic_count.group(1))
            drc.total_violations = count
            if count == 0:
                drc.violations_details.clear()
                drc.violations_by_type.clear()
                drc.violations_by_layer.clear()
            return

        # OpenROAD TritonRoute: "[INFO DRT-0199] Total violations: 24"
        tr_total = re.search(r"(?:\[INFO DRT-\d+\]\s*)?Total\s+violations\s*:\s*(\d+)", content, re.IGNORECASE)
        if tr_total:
            drc.total_violations = max(drc.total_violations, int(tr_total.group(1)))

        # TritonRoute violation blocks (handles single-line or multiline with indented layer):
        #   violation type: Short, layer: Metal2
        # or:
        #   violation type: Short
        #     srcs: net1 net2
        #     layer: Metal3
        v_blocks = re.findall(
            r"violation\s+type\s*:\s*([A-Za-z0-9_]+)([\s\S]*?)(?=(?:violation\s+type\s*:|$))",
            content,
            re.IGNORECASE,
        )
        for vtype, block in v_blocks:
            vtype = vtype.strip()
            # If the block goes past the DRC section into timing or other commands, stop at double newline
            block_content = block.split("\n\n")[0]
            layer_match = re.search(r"layer\s*:\s*([A-Za-z0-9_]+)", block_content, re.IGNORECASE)
            layer = layer_match.group(1).strip() if layer_match else "Unknown"
            drc.violations_by_type[vtype] = drc.violations_by_type.get(vtype, 0) + 1
            drc.violations_by_layer[layer] = drc.violations_by_layer.get(layer, 0) + 1
            drc.violations_details.append({"type": vtype, "layer": layer})

        # Magic DRC format: "Total DRC errors: 12"
        magic_total = re.search(r"Total\s+DRC\s+errors\s*[:=]?\s*(\d+)", content, re.IGNORECASE)
        if magic_total:
            drc.total_violations = max(drc.total_violations, int(magic_total.group(1)))

        # If details exist but total_violations is 0, update total
        if drc.total_violations == 0 and drc.violations_details:
            drc.total_violations = len(drc.violations_details)

    def _parse_metrics_csv(self, filepath: Path, metrics: PDRunMetrics):
        import csv
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Timing
                    if "spef_wns" in row and row["spef_wns"] not in ("", "-1"):
                        metrics.timing.record_setup_wns(float(row["spef_wns"]))
                    elif "wns" in row and row["wns"] not in ("", "-1"):
                        metrics.timing.record_setup_wns(float(row["wns"]))

                    if "spef_tns" in row and row["spef_tns"] not in ("", "-1"):
                        metrics.timing.setup_tns = float(row["spef_tns"])
                    elif "tns" in row and row["tns"] not in ("", "-1"):
                        metrics.timing.setup_tns = float(row["tns"])

                    # DRC
                    drc_errs = 0
                    if "tritonRoute_violations" in row and row["tritonRoute_violations"] not in ("", "-1"):
                        drc_errs += int(float(row["tritonRoute_violations"]))
                    if "Magic_violations" in row and row["Magic_violations"] not in ("", "-1"):
                        drc_errs += int(float(row["Magic_violations"]))
                    metrics.drc.total_violations = drc_errs
                    if drc_errs == 0:
                        metrics.drc.violations_details.clear()
                        metrics.drc.violations_by_type.clear()
                        metrics.drc.violations_by_layer.clear()

                    # Area & Power
                    if "DIEAREA_mm^2" in row and row["DIEAREA_mm^2"] not in ("", "-1"):
                        metrics.area_power.die_area_um2 = float(row["DIEAREA_mm^2"]) * 1e6
                    if "CoreArea_um^2" in row and row["CoreArea_um^2"] not in ("", "-1"):
                        metrics.area_power.core_area_um2 = float(row["CoreArea_um^2"])
                    if "OpenDP_Util" in row and row["OpenDP_Util"] not in ("", "-1"):
                        metrics.area_power.utilization_pct = float(row["OpenDP_Util"])
                    if "TotalCells" in row and row["TotalCells"] not in ("", "-1"):
                        metrics.area_power.std_cell_count = int(float(row["TotalCells"]))

                    # Power (uW -> mW)
                    if "power_typical_internal_uW" in row and row["power_typical_internal_uW"] not in ("", "-1"):
                        val = float(row["power_typical_internal_uW"])
                        metrics.area_power.internal_power_mw = self._normalize_power_mw(val, "uW")
                    if "power_typical_switching_uW" in row and row["power_typical_switching_uW"] not in ("", "-1"):
                        val = float(row["power_typical_switching_uW"])
                        metrics.area_power.switching_power_mw = self._normalize_power_mw(val, "uW")
                    if "power_typical_leakage_uW" in row and row["power_typical_leakage_uW"] not in ("", "-1"):
                        val = float(row["power_typical_leakage_uW"])
                        metrics.area_power.leakage_power_mw = self._normalize_power_mw(val, "uW")
                    metrics.area_power.total_power_mw = (
                        metrics.area_power.internal_power_mw +
                        metrics.area_power.switching_power_mw +
                        metrics.area_power.leakage_power_mw
                    )
        except Exception:
            pass

    def _parse_congestion(self, content: str, cong: CongestionSummary):
        # OpenROAD FastRoute / Global Route:
        # "[INFO GRT-0097]   Horizontal max congestion: 88.50%"
        # "[INFO GRT-0098]   Vertical max congestion: 92.10%"
        h_cong = re.search(r"Horizontal\s+max\s+congestion\s*:\s*([0-9.]+)\s*%", content, re.IGNORECASE)
        if h_cong:
            cong.h_max_pct = max(cong.h_max_pct, float(h_cong.group(1)))

        v_cong = re.search(r"Vertical\s+max\s+congestion\s*:\s*([0-9.]+)\s*%", content, re.IGNORECASE)
        if v_cong:
            cong.v_max_pct = max(cong.v_max_pct, float(v_cong.group(1)))

        # Overflow: "[INFO GRT-0099]   Horizontal overflow: 2"
        h_ovf = re.search(r"Horizontal\s+overflow\s*:\s*(\d+)", content, re.IGNORECASE)
        if h_ovf:
            cong.overflow_h = max(cong.overflow_h, int(h_ovf.group(1)))

        v_ovf = re.search(r"Vertical\s+overflow\s*:\s*(\d+)", content, re.IGNORECASE)
        if v_ovf:
            cong.overflow_v = max(cong.overflow_v, int(v_ovf.group(1)))

        # General "max congestion: 95.2%"
        max_c = re.search(r"(?:overall|peak|max)\s+congestion\s*[:=]?\s*([0-9.]+)\s*%", content, re.IGNORECASE)
        if max_c:
            cong.max_pct = max(cong.max_pct, float(max_c.group(1)))

        # Hotspots
        hotspots = re.search(r"(?:hotspots?|congested\s+gcells)\s*[:=]?\s*(\d+)", content, re.IGNORECASE)
        if hotspots:
            cong.hotspot_count = max(cong.hotspot_count, int(hotspots.group(1)))

    def _parse_area_power(self, content: str, ap: AreaPowerSummary):
        # OpenROAD: "Design area 154200 u^2 58% utilization."
        area_match = re.search(
            r"Design\s+area\s+([0-9.]+)\s*(?:u\^2|um2|um\^2)?\s+([0-9.]+)\s*%\s*utilization",
            content,
            re.IGNORECASE,
        )
        if area_match:
            ap.core_area_um2 = float(area_match.group(1))
            ap.die_area_um2 = max(ap.die_area_um2, ap.core_area_um2)
            ap.utilization_pct = float(area_match.group(2))

        # Std cell count
        cell_cnt = re.search(r"(?:std\s*cell\s*count|number\s+of\s+instances)\s*[:=]?\s*(\d+)", content, re.IGNORECASE)
        if cell_cnt:
            ap.std_cell_count = max(ap.std_cell_count, int(cell_cnt.group(1)))

        # Macro count
        macro_cnt = re.search(r"(?:macro\s*count|number\s+of\s+macros)\s*[:=]?\s*(\d+)", content, re.IGNORECASE)
        if macro_cnt:
            ap.macro_count = max(ap.macro_count, int(macro_cnt.group(1)))

        # Power parsing with unit normalization
        tot_power = re.search(r"Total\s+Power\s*[:=]?\s*([0-9.e+-]+)\s*(nW|uW|µW|mW|W)?", content, re.IGNORECASE)
        if tot_power:
            val = float(tot_power.group(1))
            unit = tot_power.group(2) or "mW"
            ap.total_power_mw = self._normalize_power_mw(val, unit)

        int_power = re.search(r"Internal\s+Power\s*[:=]?\s*([0-9.e+-]+)\s*(nW|uW|µW|mW|W)?", content, re.IGNORECASE)
        if int_power:
            val = float(int_power.group(1))
            unit = int_power.group(2) or "mW"
            ap.internal_power_mw = self._normalize_power_mw(val, unit)

        sw_power = re.search(r"Switching\s+Power\s*[:=]?\s*([0-9.e+-]+)\s*(nW|uW|µW|mW|W)?", content, re.IGNORECASE)
        if sw_power:
            val = float(sw_power.group(1))
            unit = sw_power.group(2) or "mW"
            ap.switching_power_mw = self._normalize_power_mw(val, unit)

        leakage = re.search(r"Leakage\s+Power\s*[:=]?\s*([0-9.e+-]+)\s*(nW|uW|µW|mW|W)?", content, re.IGNORECASE)
        if leakage:
            val = float(leakage.group(1))
            unit = leakage.group(2) or "mW"
            ap.leakage_power_mw = self._normalize_power_mw(val, unit)
