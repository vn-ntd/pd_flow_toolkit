"""
SDC Linter Rules Engine.
Defines rule definitions, categories, severity levels, and checking logic.
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Set, Optional
from .sdc_parser import SDCCommand


@dataclass
class RuleViolation:
    rule_id: str
    severity: str          # "ERROR", "WARNING", "INFO"
    line_number: int
    message: str
    suggestion: str
    command_snippet: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "line_number": str(self.line_number),
            "message": self.message,
            "suggestion": self.suggestion,
            "command_snippet": self.command_snippet,
        }


def _extract_referenced_clocks(val: Optional[str]) -> List[str]:
    if not val:
        return []
    m = re.search(r"get_clocks\s+([^\],]+)", val)
    target = m.group(1) if m else val
    target = target.strip("{}[]\"' ")
    return [c.strip() for c in target.split() if c.strip() and not c.startswith("[") and not c.startswith("-")]


class SDCRulesChecker:
    """Evaluates SDC commands against ASIC/PD industry standard lint rules."""

    def __init__(self, commands: List[SDCCommand]):
        self.commands = commands
        self.violations: List[RuleViolation] = []
        self.clocks: Dict[str, SDCCommand] = {}
        self.generated_clocks: Dict[str, SDCCommand] = {}
        self.clock_uncertainties: Set[str] = set()
        self.clock_transitions: Set[str] = set()
        self.input_delay_cmds: List[SDCCommand] = []
        self.output_delay_cmds: List[SDCCommand] = []
        self.false_path_cmds: List[SDCCommand] = []
        self.multicycle_cmds: List[SDCCommand] = []
        self.clock_group_cmds: List[SDCCommand] = []

    def run_all_checks(self) -> List[RuleViolation]:
        self.violations = []
        self._index_commands()

        # Run individual rule checks
        self._check_clk_001_clock_period()
        self._check_clk_002_waveform()
        self._check_clk_003_generated_clocks()
        self._check_clk_004_duplicate_clocks()
        self._check_clk_005_uncertainty()
        self._check_clk_006_clock_transition()
        self._check_io_001_002_missing_io_delays()
        self._check_io_003_extreme_delays()
        self._check_exc_001_wildcard_false_paths()
        self._check_exc_002_conflicting_exceptions()
        self._check_exc_003_multicycle_syntax()
        self._check_cdc_001_missing_clock_groups()
        self._check_syn_001_deprecated_commands()

        return self.violations

    def _index_commands(self):
        for cmd in self.commands:
            name = cmd.command_name
            if name == "create_clock":
                clk_name = cmd.get_value("name")
                if not clk_name and cmd.positional_args:
                    clk_name = cmd.positional_args[-1]
                if clk_name:
                    if clk_name in self.clocks:
                        self.violations.append(
                            RuleViolation(
                                rule_id="CLK-004",
                                severity="ERROR",
                                line_number=cmd.line_number,
                                message=f"Duplicate primary clock name '{clk_name}' defined.",
                                suggestion=f"Ensure each clock has a unique identifier or remove redundant definition.",
                                command_snippet=cmd.raw_text,
                            )
                        )
                    self.clocks[clk_name] = cmd

            elif name == "create_generated_clock":
                gen_name = cmd.get_value("name")
                if not gen_name and cmd.positional_args:
                    gen_name = cmd.positional_args[-1]
                if gen_name:
                    self.generated_clocks[gen_name] = cmd

            elif name == "set_clock_uncertainty":
                targets = []
                if "clock" in cmd.options:
                    targets.extend(_extract_referenced_clocks(str(cmd.options["clock"])))
                for arg in cmd.positional_args:
                    targets.extend(_extract_referenced_clocks(arg))
                if targets:
                    for t in targets:
                        self.clock_uncertainties.add(t)
                else:
                    self.clock_uncertainties.add("__GLOBAL__")

            elif name in ("set_clock_transition", "set_clock_latency"):
                targets = []
                if "clock" in cmd.options:
                    targets.extend(_extract_referenced_clocks(str(cmd.options["clock"])))
                for arg in cmd.positional_args:
                    targets.extend(_extract_referenced_clocks(arg))
                if targets:
                    for t in targets:
                        self.clock_transitions.add(t)
                else:
                    self.clock_transitions.add("__GLOBAL__")

            elif name == "set_input_delay":
                self.input_delay_cmds.append(cmd)

            elif name == "set_output_delay":
                self.output_delay_cmds.append(cmd)

            elif name == "set_false_path":
                self.false_path_cmds.append(cmd)

            elif name == "set_multicycle_path":
                self.multicycle_cmds.append(cmd)

            elif name == "set_clock_groups":
                self.clock_group_cmds.append(cmd)

    def _check_clk_001_clock_period(self):
        for clk_name, cmd in self.clocks.items():
            period_str = cmd.get_value("period")
            if not period_str:
                self.violations.append(
                    RuleViolation(
                        rule_id="CLK-001",
                        severity="ERROR",
                        line_number=cmd.line_number,
                        message=f"Clock '{clk_name}' missing required '-period' option.",
                        suggestion="Specify '-period <value_in_ns>' for all primary clocks.",
                        command_snippet=cmd.raw_text,
                    )
                )
                continue

            try:
                period_val = float(period_str)
                if period_val <= 0.0:
                    self.violations.append(
                        RuleViolation(
                            rule_id="CLK-001",
                            severity="ERROR",
                            line_number=cmd.line_number,
                            message=f"Clock '{clk_name}' has invalid non-positive period: {period_val} ns.",
                            suggestion="Clock period must be strictly greater than 0.0 ns.",
                            command_snippet=cmd.raw_text,
                        )
                    )
            except ValueError:
                self.violations.append(
                    RuleViolation(
                        rule_id="CLK-001",
                        severity="ERROR",
                        line_number=cmd.line_number,
                        message=f"Clock '{clk_name}' has non-numeric period: '{period_str}'.",
                        suggestion="Ensure period value is a valid numeric float.",
                        command_snippet=cmd.raw_text,
                    )
                )

    def _check_clk_002_waveform(self):
        for clk_name, cmd in self.clocks.items():
            waveform_str = cmd.get_value("waveform")
            if not waveform_str:
                continue

            period_str = cmd.get_value("period")
            period_val = float(period_str) if (period_str and self._is_float(period_str)) else 0.0

            # Waveform format: "{0 5.0}" or "0 5.0"
            clean_wf = waveform_str.strip("{}").split()
            if len(clean_wf) != 2:
                self.violations.append(
                    RuleViolation(
                        rule_id="CLK-002",
                        severity="ERROR",
                        line_number=cmd.line_number,
                        message=f"Clock '{clk_name}' invalid waveform '{waveform_str}'. Must specify rising and falling edges.",
                        suggestion="Provide exactly 2 edge values: '-waveform {rise_time fall_time}'.",
                        command_snippet=cmd.raw_text,
                    )
                )
                continue

            try:
                rise, fall = float(clean_wf[0]), float(clean_wf[1])
                if rise >= fall:
                    self.violations.append(
                        RuleViolation(
                            rule_id="CLK-002",
                            severity="ERROR",
                            line_number=cmd.line_number,
                            message=f"Clock '{clk_name}' rising edge ({rise}) is >= falling edge ({fall}).",
                            suggestion="Ensure rising edge precedes falling edge within the clock period.",
                            command_snippet=cmd.raw_text,
                        )
                    )
                if period_val > 0.0 and (fall > period_val or rise >= period_val):
                    self.violations.append(
                        RuleViolation(
                            rule_id="CLK-002",
                            severity="WARNING",
                            line_number=cmd.line_number,
                            message=f"Clock '{clk_name}' edge exceeds period ({period_val} ns): rise={rise}, fall={fall}.",
                            suggestion="Keep waveform edges within the fundamental period [0, period].",
                            command_snippet=cmd.raw_text,
                        )
                    )
            except ValueError:
                pass

    def _check_clk_003_generated_clocks(self):
        for gen_name, cmd in self.generated_clocks.items():
            source = cmd.get_value("source")
            if not source:
                self.violations.append(
                    RuleViolation(
                        rule_id="CLK-003",
                        severity="ERROR",
                        line_number=cmd.line_number,
                        message=f"Generated clock '{gen_name}' missing required '-source' pin/port.",
                        suggestion="Specify the driver pin using '-source [get_pins master_pin]'.",
                        command_snippet=cmd.raw_text,
                    )
                )

            master_clk = cmd.get_value("master_clock")
            if master_clk and master_clk not in self.clocks and master_clk not in self.generated_clocks:
                self.violations.append(
                    RuleViolation(
                        rule_id="CLK-003",
                        severity="ERROR",
                        line_number=cmd.line_number,
                        message=f"Generated clock '{gen_name}' references non-existent master_clock '{master_clk}'.",
                        suggestion=f"Define master clock '{master_clk}' before referencing it in generated clocks.",
                        command_snippet=cmd.raw_text,
                    )
                )

            # Check division / multiplication / edges
            has_div = "divide_by" in cmd.options
            has_mult = "multiply_by" in cmd.options
            has_edges = "edges" in cmd.options
            if not (has_div or has_mult or has_edges):
                self.violations.append(
                    RuleViolation(
                        rule_id="CLK-003",
                        severity="WARNING",
                        line_number=cmd.line_number,
                        message=f"Generated clock '{gen_name}' has no transformation specified (-divide_by, -multiply_by, or -edges).",
                        suggestion="Specify frequency scaling relationship relative to source clock.",
                        command_snippet=cmd.raw_text,
                    )
                )

    def _check_clk_004_duplicate_clocks(self):
        # Handled during _index_commands
        pass

    def _check_clk_005_uncertainty(self):
        if not self.clocks:
            return
        if "__GLOBAL__" in self.clock_uncertainties:
            return  # Global uncertainty covers all

        for clk_name, cmd in self.clocks.items():
            if clk_name not in self.clock_uncertainties:
                self.violations.append(
                    RuleViolation(
                        rule_id="CLK-005",
                        severity="WARNING",
                        line_number=cmd.line_number,
                        message=f"Clock '{clk_name}' has no 'set_clock_uncertainty' defined.",
                        suggestion=f"Add 'set_clock_uncertainty -setup <val> [get_clocks {clk_name}]' to account for jitter and skew.",
                        command_snippet=cmd.raw_text,
                    )
                )

    def _check_clk_006_clock_transition(self):
        if not self.clocks:
            return
        if "__GLOBAL__" in self.clock_transitions:
            return

        for clk_name, cmd in self.clocks.items():
            if clk_name not in self.clock_transitions:
                self.violations.append(
                    RuleViolation(
                        rule_id="CLK-006",
                        severity="INFO",
                        line_number=cmd.line_number,
                        message=f"Clock '{clk_name}' has no 'set_clock_transition' specified for pre-CTS ideal network.",
                        suggestion=f"Define realistic input clock slew with 'set_clock_transition <val> [get_clocks {clk_name}]'.",
                        command_snippet=cmd.raw_text,
                    )
                )

    def _check_io_001_002_missing_io_delays(self):
        if self.clocks and not self.input_delay_cmds:
            self.violations.append(
                RuleViolation(
                    rule_id="IO-001",
                    severity="WARNING",
                    line_number=1,
                    message="Design contains clocks but zero 'set_input_delay' constraints found.",
                    suggestion="Ensure external inputs are constrained using 'set_input_delay -clock ... [get_ports ...]'.",
                    command_snippet="<File level check>",
                )
            )

        if self.clocks and not self.output_delay_cmds:
            self.violations.append(
                RuleViolation(
                    rule_id="IO-002",
                    severity="WARNING",
                    line_number=1,
                    message="Design contains clocks but zero 'set_output_delay' constraints found.",
                    suggestion="Ensure external outputs are constrained using 'set_output_delay -clock ... [get_ports ...]'.",
                    command_snippet="<File level check>",
                )
            )

    def _check_io_003_extreme_delays(self):
        all_delays = [("input", c) for c in self.input_delay_cmds] + [("output", c) for c in self.output_delay_cmds]
        for kind, cmd in all_delays:
            # Check delay value from options (-max / -min) or positional args
            delay_val = None
            for key in ("max", "min"):
                val = cmd.get_value(key)
                if val and self._is_float(str(val)):
                    delay_val = float(val)
                    break
            if delay_val is None:
                for arg in cmd.positional_args:
                    if self._is_float(arg):
                        delay_val = float(arg)
                        break

            if delay_val is not None:
                # Compare against referenced clock period
                clk_name = cmd.get_value("clock")
                if clk_name:
                    refs = _extract_referenced_clocks(str(clk_name))
                    if refs:
                        clk_name = refs[0]
                if clk_name and clk_name in self.clocks:
                    p_str = self.clocks[clk_name].get_value("period")
                    if p_str and self._is_float(p_str):
                        period = abs(float(p_str))
                        if period > 0 and (delay_val > (0.85 * period)):
                            self.violations.append(
                                RuleViolation(
                                    rule_id="IO-003",
                                    severity="WARNING",
                                    line_number=cmd.line_number,
                                    message=f"Extreme {kind} delay: {delay_val} ns is > 85% of clock '{clk_name}' period ({period} ns).",
                                    suggestion="Check if I/O delay leaves sufficient timing budget for internal logic paths.",
                                    command_snippet=cmd.raw_text,
                                )
                            )
                if delay_val < 0.0:
                    self.violations.append(
                        RuleViolation(
                            rule_id="IO-003",
                            severity="WARNING",
                            line_number=cmd.line_number,
                            message=f"Negative {kind} delay ({delay_val} ns) detected.",
                            suggestion="Verify if negative margin is intentional for interface hold budgeting.",
                            command_snippet=cmd.raw_text,
                        )
                    )

    def _check_exc_001_wildcard_false_paths(self):
        for cmd in self.false_path_cmds:
            from_target = cmd.get_value("from")
            to_target = cmd.get_value("to")

            # Check for dangerous wildcards like * or [get_clocks *] without -through or specific objects
            if from_target in ("*", "[all_inputs]", "[all_clocks]") and to_target in ("*", "[all_outputs]", "[all_clocks]"):
                self.violations.append(
                    RuleViolation(
                        rule_id="EXC-001",
                        severity="ERROR",
                        line_number=cmd.line_number,
                        message=f"Broad wildcard 'set_false_path' from '{from_target}' to '{to_target}' will disable critical timing paths!",
                        suggestion="Never use universal wildcards across entire designs. Narrow false paths to specific CDC or reset synchronizers.",
                        command_snippet=cmd.raw_text,
                    )
                )
            elif from_target == "*" or to_target == "*":
                self.violations.append(
                    RuleViolation(
                        rule_id="EXC-001",
                        severity="WARNING",
                        line_number=cmd.line_number,
                        message=f"Unbounded wildcard '*' used in 'set_false_path' (from={from_target}, to={to_target}).",
                        suggestion="Be specific with pin or register name patterns to prevent accidental path masking.",
                        command_snippet=cmd.raw_text,
                    )
                )

    def _check_exc_002_conflicting_exceptions(self):
        fp_targets = set()
        for cmd in self.false_path_cmds:
            key = (cmd.get_value("from"), cmd.get_value("to"))
            if key[0] and key[1]:
                fp_targets.add(key)

        for cmd in self.multicycle_cmds:
            key = (cmd.get_value("from"), cmd.get_value("to"))
            if key in fp_targets:
                self.violations.append(
                    RuleViolation(
                        rule_id="EXC-002",
                        severity="ERROR",
                        line_number=cmd.line_number,
                        message=f"Conflicting timing exceptions: path from '{key[0]}' to '{key[1]}' declared as both false path and multicycle path.",
                        suggestion="A path cannot be both multicycle and false. Remove the redundant or conflicting constraint.",
                        command_snippet=cmd.raw_text,
                    )
                )

    def _check_exc_003_multicycle_syntax(self):
        for cmd in self.multicycle_cmds:
            # Multiplier must be integer >= 1
            mult = None
            for arg in cmd.positional_args:
                if arg.isdigit():
                    mult = int(arg)
                    break
            if mult is None:
                self.violations.append(
                    RuleViolation(
                        rule_id="EXC-003",
                        severity="ERROR",
                        line_number=cmd.line_number,
                        message="Missing integer cycle multiplier in 'set_multicycle_path'.",
                        suggestion="Syntax: set_multicycle_path <multiplier> -setup|-hold ...",
                        command_snippet=cmd.raw_text,
                    )
                )
            else:
                is_hold = "hold" in cmd.options or "-hold" in cmd.raw_text
                if mult <= 1 and not is_hold:
                    self.violations.append(
                        RuleViolation(
                            rule_id="EXC-003",
                            severity="WARNING",
                            line_number=cmd.line_number,
                            message=f"Multicycle setup multiplier is {mult} (default single cycle).",
                            suggestion="Multicycle setup path is usually set to 2 or more cycles.",
                            command_snippet=cmd.raw_text,
                        )
                    )

    def _check_cdc_001_missing_clock_groups(self):
        # If there are >= 2 primary clocks and 0 set_clock_groups
        if len(self.clocks) >= 2 and not self.clock_group_cmds:
            clk_names = ", ".join(self.clocks.keys())
            self.violations.append(
                RuleViolation(
                    rule_id="CDC-001",
                    severity="WARNING",
                    line_number=1,
                    message=f"Multiple primary clocks defined ({clk_names}) without 'set_clock_groups'.",
                    suggestion="If clocks are asynchronous, declare 'set_clock_groups -asynchronous -group [get_clocks ...] -group [get_clocks ...]'.",
                    command_snippet="<Design level check>",
                )
            )

    def _check_syn_001_deprecated_commands(self):
        deprecated = {"set_dont_use", "set_wire_load_model", "set_operating_conditions"}
        for cmd in self.commands:
            if cmd.command_name in deprecated:
                self.violations.append(
                    RuleViolation(
                        rule_id="SYN-001",
                        severity="INFO",
                        line_number=cmd.line_number,
                        message=f"Deprecated or flow-specific command '{cmd.command_name}' found.",
                        suggestion="Consider moving physical/cell constraints to separate flow scripts or modern Liberty constraints.",
                        command_snippet=cmd.raw_text,
                    )
                )

    @staticmethod
    def _is_float(val: str) -> bool:
        try:
            float(val)
            return True
        except ValueError:
            return False
