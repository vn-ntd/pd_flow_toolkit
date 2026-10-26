r"""
SDC (Synopsys Design Constraints) Tokenizer and Command Parser.
Handles line continuations (\), comments (#), nested brackets, and option parsing.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class SDCCommand:
    raw_text: str
    command_name: str
    line_number: int
    options: Dict[str, Any] = field(default_factory=dict)
    positional_args: List[str] = field(default_factory=list)

    def get_flag(self, flag: str) -> bool:
        val = self.options.get(flag)
        if isinstance(val, list):
            return any(v is True for v in val)
        return val is True

    def get_value(self, option: str, default: Any = None) -> Any:
        return self.options.get(option, default)

    def get_list(self, option: str) -> List[Any]:
        val = self.options.get(option, [])
        if isinstance(val, list):
            return val
        elif val is not None and val != []:
            return [val]
        return []


class SDCParser:
    """Parses SDC files into a structured list of SDCCommand objects."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.commands: List[SDCCommand] = []
        self.syntax_errors: List[str] = []
        self.variables: Dict[str, str] = {}

    def parse(self) -> List[SDCCommand]:
        self.commands = []
        self.syntax_errors = []
        self.variables = {}

        with open(self.filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        current_cmd = ""
        start_line = 1
        in_continuation = False

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Handle comments: strip out comments unless inside quotes
            # Ignore lines that start with #
            if not in_continuation and (not stripped or stripped.startswith("#")):
                continue

            # Strip inline comment if not within quotes
            line_no_comment = self._strip_inline_comment(line)
            stripped_line = line_no_comment.strip()

            if not stripped_line:
                continue

            if not in_continuation:
                start_line = idx

            if stripped_line.endswith("\\"):
                # Line continuation
                current_cmd += stripped_line[:-1].strip() + " "
                in_continuation = True
            else:
                current_cmd += stripped_line
                in_continuation = False
                # Parse completed command with variable substitution
                expanded_cmd = self._substitute_variables(current_cmd)
                cmd_obj = self._parse_single_command(expanded_cmd, start_line)
                if cmd_obj:
                    if cmd_obj.command_name == "set" and len(cmd_obj.positional_args) >= 2:
                        var_name = cmd_obj.positional_args[0].strip("{}")
                        var_val = cmd_obj.positional_args[1].strip("\"'{}")
                        self.variables[var_name] = var_val
                    self.commands.append(cmd_obj)
                current_cmd = ""

        if in_continuation:
            self.syntax_errors.append(f"Line {start_line}: Trailing backslash (\\) at end of file.")

        return self.commands

    def _substitute_variables(self, text: str) -> str:
        if not self.variables:
            return text

        def _repl(match):
            var_name = match.group(1) or match.group(2)
            return self.variables.get(var_name, match.group(0))

        return re.sub(r"\$(?:\{([A-Za-z0-9_]+)\}|([A-Za-z0-9_]+))", _repl, text)

    def _strip_inline_comment(self, text: str) -> str:
        in_quote = False
        quote_char = None
        result = []
        for ch in text:
            if ch in ('"', "'"):
                if not in_quote:
                    in_quote = True
                    quote_char = ch
                elif quote_char == ch:
                    in_quote = False
            elif ch == '#' and not in_quote:
                break
            result.append(ch)
        return "".join(result)

    def _parse_single_command(self, cmd_str: str, line_no: int) -> Optional[SDCCommand]:
        tokens = self._tokenize(cmd_str)
        if not tokens:
            return None

        cmd_name = tokens[0]
        options: Dict[str, Any] = {}
        positional: List[str] = []

        i = 1
        while i < len(tokens):
            tok = tokens[i]
            if tok.startswith("-") and len(tok) > 1 and not (tok[1:].replace(".", "", 1).isdigit()):
                opt_name = tok[1:]
                # Check if next token is a value or another option
                if i + 1 < len(tokens) and not (tokens[i + 1].startswith("-") and len(tokens[i + 1]) > 1 and not tokens[i + 1][1:].replace(".", "", 1).isdigit()):
                    val = tokens[i + 1]
                    i += 2
                else:
                    val = True
                    i += 1

                if opt_name in options:
                    if isinstance(options[opt_name], list):
                        options[opt_name].append(val)
                    else:
                        options[opt_name] = [options[opt_name], val]
                else:
                    options[opt_name] = val
            else:
                positional.append(tok)
                i += 1

        return SDCCommand(
            raw_text=cmd_str,
            command_name=cmd_name,
            line_number=line_no,
            options=options,
            positional_args=positional,
        )

    def _tokenize(self, text: str) -> List[str]:
        """Tokenizes SDC command preserving bracketed groups [get_ports ...] and quotes."""
        tokens = []
        current = []
        in_quote = False
        quote_char = ""
        bracket_level = 0
        brace_level = 0

        i = 0
        n = len(text)
        while i < n:
            c = text[i]

            if c in ('"', "'") and bracket_level == 0 and brace_level == 0:
                if not in_quote:
                    in_quote = True
                    quote_char = c
                elif quote_char == c:
                    in_quote = False
                    tokens.append("".join(current))
                    current = []
                else:
                    current.append(c)
            elif c == '[' and not in_quote:
                bracket_level += 1
                current.append(c)
            elif c == ']' and not in_quote:
                bracket_level = max(0, bracket_level - 1)
                current.append(c)
            elif c == '{' and not in_quote:
                brace_level += 1
                current.append(c)
            elif c == '}' and not in_quote:
                brace_level = max(0, brace_level - 1)
                current.append(c)
            elif c.isspace() and not in_quote and bracket_level == 0 and brace_level == 0:
                if current:
                    tokens.append("".join(current))
                    current = []
            else:
                current.append(c)
            i += 1

        if current:
            tokens.append("".join(current))

        return [t.strip("\"'") for t in tokens if t.strip()]
