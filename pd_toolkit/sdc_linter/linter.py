"""
SDC Linter Execution Engine and Report Formatter.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import json
from .sdc_parser import SDCParser
from .rules import SDCRulesChecker, RuleViolation


@dataclass
class SDCLintReport:
    filepath: str
    total_commands: int = 0
    violations: List[RuleViolation] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "WARNING")

    @property
    def info_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "INFO")

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filepath": self.filepath,
            "total_commands": self.total_commands,
            "passed": self.passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "violations": [v.to_dict() for v in self.violations],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class SDCLinter:
    """Main SDC Linter runner."""

    def __init__(self, sdc_file: str):
        self.sdc_file = sdc_file

    def lint(self) -> SDCLintReport:
        parser = SDCParser(self.sdc_file)
        commands = parser.parse()

        report = SDCLintReport(filepath=self.sdc_file, total_commands=len(commands))

        # Check for parser syntax errors
        for syn_err in parser.syntax_errors:
            report.violations.append(
                RuleViolation(
                    rule_id="SYN-000",
                    severity="ERROR",
                    line_number=1,
                    message=syn_err,
                    suggestion="Fix SDC syntax or trailing line continuation characters.",
                    command_snippet="<Syntax Error>",
                )
            )

        # Run semantic rule checker
        checker = SDCRulesChecker(commands)
        violations = checker.run_all_checks()
        report.violations.extend(violations)

        # Sort violations by line number
        report.violations.sort(key=lambda x: x.line_number)
        return report
