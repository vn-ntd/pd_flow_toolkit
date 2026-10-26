# PD Flow Toolkit Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix critical EDA report parsing bugs, expand test coverage to >90%, complete the PPA regression comparator triad, add Tcl variable support to SDC linter, and upgrade dashboard interactivity and CI/CD markdown export.

**Architecture:** Maintain zero-external-dependency standard library Python architecture. Enhance parsers (`openroad_parser.py`, `innovus_parser.py`), comparator (`diff_engine.py`), SDC parser (`sdc_parser.py`), dashboard generator (`generator.py`), and CLI interface (`cli.py`).

**Tech Stack:** Python 3.10+, Standard Library (`re`, `pathlib`, `csv`, `argparse`, `json`, `dataclasses`), `pytest`, `pytest-cov`, `ruff`.

**Spec:** Audit findings from Senior EDA / Physical Design review across correctness, PPA completeness, test coverage, and CI/CD user experience.

## Global Constraints

- Must run on standard Python 3.10+ without new required third-party dependencies.
- All existing and new tests must pass (`pytest`).
- Code must pass `ruff check .` with line length limit 120.
- Git working directory must remain clean after running `demo` and `pytest`.

## Review Focus

- Power values from `metrics.csv` with small fractional microwatt numbers (< 1.0 µW).
- TritonRoute reports where `layer:` is on the next line after `violation type:`.
- Multi-stage Innovus logs where multiple `Setup mode` tables exist (must pick final signoff table).
- SDC files using Tcl variables (`set PERIOD 5.0; create_clock -period $PERIOD`).
- Zero slack `0.000 ns` correctly preserved as exact critical slack without being overwritten.

---

### Task 1: Fix OpenROAD Parser Correctness Bugs

**Files:**
- Modify: `pd_toolkit/parsers/openroad_parser.py`
- Modify: `pd_toolkit/parsers/base_parser.py`
- Test: `tests/test_parsers.py`

**Interfaces:**
- `OpenROADParser._parse_metrics_csv(filepath, metrics)`
- `OpenROADParser._parse_drc(content, drc, filename)`
- `OpenROADParser._parse_timing(content, timing)`

- [ ] **Step 1: Write failing tests for OpenROAD parser bugs in `tests/test_parsers.py`**
  - Test power normalization with `power_typical_internal_uW = 0.45` in CSV.
  - Test multiline TritonRoute DRC syntax with `layer: Metal2` on next line.
  - Test zero slack `0.000 ns` preserved without being overwritten by later positive slack.
- [ ] **Step 2: Run pytest to verify tests fail**
  - Run: `pytest tests/test_parsers.py -k "test_openroad_csv_micro_power or test_triton_multiline_drc" -v`
- [ ] **Step 3: Implement fixes in `openroad_parser.py` & `base_parser.py`**
  - In `base_parser.py`: add explicit tracking flag `_setup_wns_set` and `_hold_wns_set` or optional float to handle 0.0 correctly.
  - In `openroad_parser.py`: use `self._normalize_power_mw(val, "uW")` for CSV power fields.
  - In `openroad_parser.py`: enhance DRC parser to capture layer on subsequent lines and avoid skipping unified log files.
- [ ] **Step 4: Run pytest to verify tests pass**
  - Run: `pytest tests/test_parsers.py -v`
- [ ] **Step 5: Commit changes**
  - `git commit -m "fix(parser): correct OpenROAD CSV power normalization, multiline DRC, and slack tracking"`

---

### Task 2: Fix Innovus Parser Stage Selection and Congestion Bugs

**Files:**
- Modify: `pd_toolkit/parsers/innovus_parser.py`
- Test: `tests/test_parsers.py`

**Interfaces:**
- `InnovusParser._parse_timedesign_tables(content, timing)`
- `InnovusParser._parse_congestion(content, cong)`

- [ ] **Step 1: Write failing tests for Innovus multi-stage logs and congestion in `tests/test_parsers.py`**
  - Test log containing pre-CTS Setup mode table (-0.450 WNS) and post-Route Setup mode table (-0.050 WNS) picking the post-route one.
  - Test congestion parsing with explicit H/V overflow lines without artificial 50/50 division.
- [ ] **Step 2: Run pytest to verify tests fail**
  - Run: `pytest tests/test_parsers.py -k "test_innovus_multistage_timing" -v`
- [ ] **Step 3: Implement fixes in `innovus_parser.py`**
  - Use `content.rfind("Setup mode")` and `content.rfind("Hold mode")` to grab the final signoff tables.
  - Parse `Horizontal Overflow` and `Vertical Overflow` directly; fallback to setting `overflow_h = val, overflow_v = 0` if only total 2D is given.
- [ ] **Step 4: Run pytest to verify tests pass**
  - Run: `pytest tests/test_parsers.py -v`
- [ ] **Step 5: Commit changes**
  - `git commit -m "fix(parser): pick final signoff table in Innovus multi-stage logs and improve congestion parsing"`

---

### Task 3: Expand OpenROAD Parser Test Coverage to >= 90%

**Files:**
- Modify: `tests/test_parsers.py`

- [ ] **Step 1: Add comprehensive unit tests covering untested branches**
  - Add CSV reader test with valid and `-1` missing rows.
  - Add Magic DRC test with `[INFO]: COUNT: 0` and `Total DRC errors: N`.
  - Add TritonRoute DRC test with empty violations and layer breakdowns.
  - Add FastRoute congestion overflow test cases.
- [ ] **Step 2: Run pytest with coverage report**
  - Run: `pytest --cov=pd_toolkit.parsers.openroad_parser --cov-report=term-missing`
  - Verify `openroad_parser.py` coverage >= 90%.
- [ ] **Step 3: Commit changes**
  - `git commit -m "test(parsers): expand OpenROAD parser test coverage to >90%"`

---

### Task 4: Clean Up Demo Command & Git Hygiene

**Files:**
- Modify: `pd_toolkit/cli.py`
- Modify: `.gitignore`

- [ ] **Step 1: Update `.gitignore` and `cmd_demo` in `cli.py`**
  - Ensure `.gitignore` ignores `examples/*_dashboard.html` and `examples/output/`.
  - Update `cmd_demo` to generate dashboards into `examples/output/` or clean up demo artifacts.
  - Remove existing untracked `examples/openroad_dashboard.html` and `examples/innovus_dashboard.html`.
- [ ] **Step 2: Run `python pd_tool.py demo` and verify `git status` stays clean**
  - Run: `python pd_tool.py demo; git status`
- [ ] **Step 3: Commit changes**
  - `git commit -m "chore: ensure demo outputs do not dirty git working tree"`

---

### Task 5: Basic Tcl Variable Support in SDC Linter

**Files:**
- Modify: `pd_toolkit/sdc_linter/sdc_parser.py`
- Test: `tests/test_sdc_linter.py`

**Interfaces:**
- `SDCParser.variables: Dict[str, str]`
- Variable expansion during tokenization / command building for `$var_name`.

- [ ] **Step 1: Write failing test in `tests/test_sdc_linter.py`**
  - Test SDC with `set CLK_PERIOD 10.0; create_clock -name core_clk -period $CLK_PERIOD [get_ports clk]`.
  - Verify it does not trigger `CLK-001` error.
- [ ] **Step 2: Run pytest to verify test fails**
  - Run: `pytest tests/test_sdc_linter.py -k "test_sdc_tcl_variables" -v`
- [ ] **Step 3: Implement variable tracking & substitution in `sdc_parser.py`**
  - When encountering `set <var_name> <value>`, record in `self.variables`.
  - Replace tokens matching `$var_name` with their stored value.
- [ ] **Step 4: Run pytest to verify tests pass**
  - Run: `pytest tests/test_sdc_linter.py -v`
- [ ] **Step 5: Commit changes**
  - `git commit -m "feat(sdc-linter): add basic Tcl variable substitution ($var) support"`

---

### Task 6: Complete PPA Triad in RunComparator

**Files:**
- Modify: `pd_toolkit/comparator/diff_engine.py`
- Modify: `pd_toolkit/cli.py`
- Test: `tests/test_comparator.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- `RunComparison.total_power: MetricDelta`
- `RunComparison.cell_count: MetricDelta`
- `RunComparison.to_dict()` includes power and cell count deltas.

- [ ] **Step 1: Write failing test in `tests/test_comparator.py`**
  - Test delta calculation for `total_power_mw` and `std_cell_count`.
- [ ] **Step 2: Run pytest to verify test fails**
  - Run: `pytest tests/test_comparator.py -k "test_ppa_power_and_cells" -v`
- [ ] **Step 3: Implement power and instance count deltas in `diff_engine.py` & `cli.py`**
  - Add `total_power` and `std_cell_count` to `RunComparison`.
  - Lower power is improved (`delta <= 0`).
  - Print Power and Cells in `cmd_compare` table.
- [ ] **Step 4: Run pytest to verify tests pass**
  - Run: `pytest tests/test_comparator.py tests/test_cli.py -v`
- [ ] **Step 5: Commit changes**
  - `git commit -m "feat(comparator): complete PPA triad by adding Power and Cell Count deltas"`

---

### Task 7: Interactive Vanilla JS in HTML Dashboard

**Files:**
- Modify: `pd_toolkit/dashboard/generator.py`
- Test: `tests/test_comparator.py`

**Interfaces:**
- `generate_html_dashboard(metrics, output_file) -> str`
- HTML includes search input for DRC table, filter badges, and copy summary button.

- [ ] **Step 1: Write test verifying HTML contains interactive JS elements**
  - Test search input element id `drcSearchInput` and copy button `copySummaryBtn`.
- [ ] **Step 2: Implement zero-dependency vanilla JS in `generator.py`**
  - Add search input for DRC table filtering.
  - Add "Copy Signoff Summary to Clipboard" button with feedback toast.
  - Add toggle for raw input files.
- [ ] **Step 3: Run pytest to verify tests pass**
  - Run: `pytest tests/test_comparator.py -v`
- [ ] **Step 4: Commit changes**
  - `git commit -m "feat(dashboard): add interactive search, filter, and clipboard copy"`

---

### Task 8: Markdown CI/CD Summary Export (`--output-md`)

**Files:**
- Modify: `pd_toolkit/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- `cmd_parse(args)` supports `--output-md <file.md>`
- `cmd_compare(args)` supports `--output-md <file.md>` and `--output-json <file.json>`

- [ ] **Step 1: Write failing tests in `tests/test_cli.py` for `--output-md`**
  - Test `parse --output-md summary.md` outputs valid markdown table.
  - Test `compare --output-md diff.md` outputs valid markdown comparison table.
- [ ] **Step 2: Run pytest to verify tests fail**
  - Run: `pytest tests/test_cli.py -k "test_cli_markdown_export" -v`
- [ ] **Step 3: Implement `--output-md` in `cli.py`**
  - Format GitHub Actions compatible markdown summary.
  - Write to file if requested.
- [ ] **Step 4: Run full test suite & ruff checks**
  - Run: `pytest --cov=pd_toolkit --cov-report=term-missing; ruff check .`
- [ ] **Step 5: Commit changes**
  - `git commit -m "feat(cli): add Markdown summary export for CI/CD integration"`
