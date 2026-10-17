"""
SDC Linter Package.
Validates Synopsys Design Constraints for clock integrity, unconstrained I/O,
wildcard false paths, CDC clock grouping, and syntax before synthesis & P&R.
"""

from .sdc_parser import SDCParser, SDCCommand
from .rules import RuleViolation, SDCRulesChecker
from .linter import SDCLinter, SDCLintReport

__all__ = ["SDCParser", "SDCCommand", "RuleViolation", "SDCRulesChecker", "SDCLinter", "SDCLintReport"]
