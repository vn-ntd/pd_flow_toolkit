"""
Command Line Interface for Physical Design Automation Toolkit.
"""

import argparse
import sys
import os
from pathlib import Path

from .parsers import parse_reports
from .dashboard import generate_html_dashboard
from .sdc_linter import SDCLinter
from .comparator import RunComparator


# Reconfigure stdout/stderr for Windows UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Terminal Colors & Icons
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    banner = f"""{CYAN}{BOLD}
======================================================================
  ____  ____    _____ _                  _____           _ _    _ _
 |  _ \\|  _ \\  |  ___| | _____      __  |_   _|__   ___ | | | _(_) |_
 | |_) | | | | | |_  | |/ _ \\ \\ /\\ / /    | |/ _ \\ / _ \\| | |/ / | __|
 |  __/| |_| | |  _| | | (_) \\ V  V /     | | (_) | (_) | |   <| | |_
 |_|   |____/  |_|   |_|\\___/ \\_/\\_/      |_|\\___/ \\___/|_|_|\\_\\_|\\__|
  ASIC/SoC Physical Design Automation & Quality Signoff Suite
======================================================================{RESET}"""
    print(banner)


def cmd_parse(args):
    print(f"\n{BOLD}▶ Parsing PD Reports from: {args.path}{RESET}")
    metrics = parse_reports(args.path, tool=args.tool, design_name=args.design)

    # Print Terminal Summary Table
    status = metrics.overall_status
    status_str = f"{GREEN}[PASS]{RESET}" if status == "PASS" else (f"{YELLOW}[WARN]{RESET}" if status == "WARN" else f"{RED}[FAIL]{RESET}")

    print("\n" + "=" * 65)
    print(f" {BOLD}PD RUN SUMMARY: {metrics.design_name} ({metrics.tool_name} {metrics.stage}) - {status_str}{RESET}")
    print("=" * 65)

    def color_val(val, passed, invert=False):
        p = (not passed) if invert else passed
        c = GREEN if p else RED
        return f"{c}{val}{RESET}"

    print(f" • Setup WNS (Worst Slack)   : {color_val(f'{metrics.timing.setup_wns:+.3f} ns', metrics.timing.setup_passed)}")
    print(f" • Setup TNS (Total Slack)   : {color_val(f'{metrics.timing.setup_tns:.3f} ns', metrics.timing.setup_tns >= 0)}")
    print(f" • Setup Failing Endpoints   : {metrics.timing.setup_fep}")
    print(f" • Hold WNS                  : {color_val(f'{metrics.timing.hold_wns:+.3f} ns', metrics.timing.hold_passed)}")
    print(f" • Total DRC Violations      : {color_val(str(metrics.drc.total_violations), metrics.drc.passed)}")
    if metrics.drc.violations_by_type:
        print(f"   └─ Top DRC Types          : {metrics.drc.violations_by_type}")
    print(f" • Max Routing Congestion    : {metrics.congestion.max_pct:.1f}% (H: {metrics.congestion.h_max_pct:.1f}%, V: {metrics.congestion.v_max_pct:.1f}%)")
    print(f" • Routing Overflows         : {metrics.congestion.overflow_h + metrics.congestion.overflow_v}")
    print(f" • Core Utilization          : {metrics.area_power.utilization_pct:.1f}%")
    print("=" * 65)

    # Export JSON if requested
    if args.output_json:
        out_p = Path(args.output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(metrics.to_json(), encoding="utf-8")
        print(f"{GREEN}✓ Exported JSON metrics to: {out_p.resolve()}{RESET}")

    # Generate Dashboard HTML
    dash_path = args.dashboard or "pd_dashboard.html"
    res_path = generate_html_dashboard(metrics, dash_path)
    print(f"{GREEN}✓ Generated Interactive HTML Dashboard: {res_path}{RESET}")

    return 0 if status == "PASS" else (1 if status == "FAIL" else 0)


def cmd_lint_sdc(args):
    print(f"\n{BOLD}▶ Linting SDC File: {args.sdc}{RESET}")
    if not os.path.exists(args.sdc):
        print(f"{RED}Error: File not found: {args.sdc}{RESET}")
        return 1

    linter = SDCLinter(args.sdc)
    report = linter.lint()

    print("\n" + "=" * 80)
    print(f" {BOLD}SDC LINT REPORT: {os.path.basename(args.sdc)}{RESET}")
    print(f" Total Commands Parsed: {report.total_commands}")
    print(f" Status: {'PASS' if report.passed else 'FAIL'} | Errors: {report.error_count} | Warnings: {report.warning_count} | Info: {report.info_count}")
    print("=" * 80)

    if not report.violations:
        print(f"\n{GREEN}✓ Outstanding! No SDC violations found. Constraints are clean for synthesis & P&R.{RESET}")
    else:
        for v in report.violations:
            sev_badge = f"{RED}[ERROR]{RESET}" if v.severity == "ERROR" else (f"{YELLOW}[WARN]{RESET}" if v.severity == "WARNING" else f"{CYAN}[INFO]{RESET}")
            print(f"\n{sev_badge} {BOLD}{v.rule_id}{RESET} (Line {v.line_number}): {v.message}")
            print(f"   Command   : {v.command_snippet}")
            print(f"   Suggestion: {CYAN}{v.suggestion}{RESET}")

    print("\n" + "=" * 80)

    if args.output_json:
        out_p = Path(args.output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(report.to_json(), encoding="utf-8")
        print(f"{GREEN}✓ Saved JSON lint report to: {out_p.resolve()}{RESET}")

    if report.error_count > 0:
        return 1
    if args.fail_on_warning and report.warning_count > 0:
        return 1
    return 0


def cmd_compare(args):
    print(f"\n{BOLD}▶ Comparing PD Runs: [Baseline] vs [Current]{RESET}")
    base_metrics = parse_reports(args.baseline, tool=args.tool_base, design_name="Baseline")
    curr_metrics = parse_reports(args.current, tool=args.tool_curr, design_name="Current")

    diff = RunComparator.compare(base_metrics, curr_metrics)

    print("\n" + "=" * 70)
    print(f" {BOLD}PD REGRESSION COMPARISON REPORT{RESET}")
    print(f" Baseline ({base_metrics.tool_name}) vs Current ({curr_metrics.tool_name})")
    print("=" * 70)
    print(f"{'Metric':<25} | {'Baseline':<12} | {'Current':<12} | {'Delta':<12}")
    print("-" * 70)

    def print_row(name, delta_obj):
        d_str = delta_obj.formatted_delta()
        color = GREEN if delta_obj.improved else RED
        if delta_obj.delta == 0:
            color = RESET
        if delta_obj.is_integer:
            b_str = f"{int(round(delta_obj.baseline)):<12}"
            c_str = f"{int(round(delta_obj.current)):<12}"
        else:
            b_str = f"{delta_obj.baseline:<12.3f}"
            c_str = f"{delta_obj.current:<12.3f}"
        print(f"{name:<25} | {b_str} | {c_str} | {color}{d_str:<12}{RESET}")

    print_row("Setup WNS (ns)", diff.setup_wns)
    print_row("Setup TNS (ns)", diff.setup_tns)
    print_row("Hold WNS (ns)", diff.hold_wns)
    print_row("Total DRC", diff.total_drc)
    print_row("Peak Congestion (%)", diff.max_congestion)
    print_row("Utilization (%)", diff.utilization)
    print_row("Total Power (mW)", diff.total_power)
    print_row("Std Cell Count", diff.std_cell_count)
    print("=" * 70)
    return 0


def cmd_demo(args):
    """Executes a full turnkey demonstration on sample OpenROAD, Innovus, and SDC files."""
    script_dir = Path(__file__).parent.parent
    examples_dir = script_dir / "examples"

    print(f"\n{CYAN}{BOLD}--- RUNNING TURNKEY DEMONSTRATION OF PD TOOLKIT ---{RESET}\n")

    # 1. OpenROAD Run Demo
    openroad_path = examples_dir / "openroad_run"
    print(f"{BOLD}[1/4] Parsing OpenROAD signoff flow reports...{RESET}")
    openroad_metrics = parse_reports(str(openroad_path), tool="openroad", design_name="riscv_core")
    or_html = examples_dir / "openroad_dashboard.html"
    generate_html_dashboard(openroad_metrics, str(or_html))
    print(f"{GREEN}✓ OpenROAD run parsed successfully. Dashboard generated at: {or_html}{RESET}")

    # 2. Innovus Run Demo
    innovus_path = examples_dir / "innovus_run"
    print(f"\n{BOLD}[2/4] Parsing Cadence Innovus flow reports...{RESET}")
    innovus_metrics = parse_reports(str(innovus_path), tool="innovus", design_name="gpu_shader_tile")
    inn_html = examples_dir / "innovus_dashboard.html"
    generate_html_dashboard(innovus_metrics, str(inn_html))
    print(f"{GREEN}✓ Innovus run parsed successfully. Dashboard generated at: {inn_html}{RESET}")

    # 3. SDC Linting Demo: Clean vs Buggy
    print(f"\n{BOLD}[3/4] Running SDC Linter on gold-standard SDC...{RESET}")
    clean_sdc = examples_dir / "sdc" / "clean_soc.sdc"
    linter_clean = SDCLinter(str(clean_sdc))
    rep_clean = linter_clean.lint()
    print(f"{GREEN}✓ Clean SDC verified: {rep_clean.error_count} errors, {rep_clean.warning_count} warnings.{RESET}")

    print(f"\n{BOLD}[4/4] Running SDC Linter on pre-synthesis buggy SDC...{RESET}")
    dirty_sdc = examples_dir / "sdc" / "dirty_soc.sdc"
    linter_dirty = SDCLinter(str(dirty_sdc))
    rep_dirty = linter_dirty.lint()
    print(f"{YELLOW}! Buggy SDC detected {rep_dirty.error_count} errors and {rep_dirty.warning_count} warnings:{RESET}")
    for v in rep_dirty.violations[:4]:
        sev_color = RED if v.severity == "ERROR" else YELLOW
        print(f"  {sev_color}[{v.severity}] {v.rule_id} (L{v.line_number}): {v.message}{RESET}")
    print(f"  ... (+{len(rep_dirty.violations) - 4} more rules triggered)")

    print(f"\n{GREEN}{BOLD}Demonstration completed successfully! All tools functional.{RESET}\n")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="Physical Design Flow Automation Toolkit: Report Parser, Dashboard & SDC Linter.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # Command: parse
    p_parse = subparsers.add_parser("parse", help="Parse OpenROAD or Innovus reports and create dashboard")
    p_parse.add_argument("--path", "-p", required=True, help="Path to report file or run directory")
    p_parse.add_argument("--tool", "-t", choices=["openroad", "innovus", "auto"], default="auto", help="EDA Tool")
    p_parse.add_argument("--design", "-d", default=None, help="Design / Block name")
    p_parse.add_argument("--stage", "-s", default="Signoff", help="PD flow stage (e.g. CTS, Route, Signoff)")
    p_parse.add_argument("--output-json", "-j", help="Output JSON metrics file path")
    p_parse.add_argument("--dashboard", "-o", default="dashboard.html", help="Output HTML dashboard file path")

    # Command: lint-sdc
    p_sdc = subparsers.add_parser("lint-sdc", help="Lint SDC file for clock integrity and unconstrained paths")
    p_sdc.add_argument("--sdc", "-f", required=True, help="Path to .sdc file")
    p_sdc.add_argument("--output-json", "-j", help="Output JSON report file path")
    p_sdc.add_argument("--fail-on-warning", action="store_true", help="Return error code if warnings exist")

    # Command: compare
    p_cmp = subparsers.add_parser("compare", help="Compare two PD runs to evaluate timing/DRC/congestion regressions")
    p_cmp.add_argument("--baseline", "-b", required=True, help="Path to baseline run reports")
    p_cmp.add_argument("--current", "-c", required=True, help="Path to current run reports")
    p_cmp.add_argument("--tool-base", default="auto", help="Baseline tool format")
    p_cmp.add_argument("--tool-curr", default="auto", help="Current tool format")

    # Command: demo
    subparsers.add_parser("demo", help="Run full self-test demo with included mock datasets")

    return parser


def main():
    print_banner()
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if args.subcommand == "parse":
        sys.exit(cmd_parse(args))
    elif args.subcommand == "lint-sdc":
        sys.exit(cmd_lint_sdc(args))
    elif args.subcommand == "compare":
        sys.exit(cmd_compare(args))
    elif args.subcommand == "demo":
        sys.exit(cmd_demo(args))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
