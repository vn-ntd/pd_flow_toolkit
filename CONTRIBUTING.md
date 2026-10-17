# Contributing to PD Flow Automation Toolkit

Thank you for your interest in improving the **PD Flow Automation Toolkit**!

## How to Contribute

1. **Fork the Repository** on GitHub.
2. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/new-eda-parser
   ```
3. **Write Unit Tests**:
   - Place new tests in `tests/test_<feature>.py`.
   - Verify all tests pass:
     ```bash
     python -m unittest discover -s tests -p "test_*.py" -v
     ```
4. **Follow Coding Standards**:
   - Maintain type annotations and docstrings.
   - Avoid introducing heavy third-party dependencies to preserve compatibility with restricted air-gapped EDA servers.
5. **Commit and Open a Pull Request**:
   - Use descriptive commit messages following the Conventional Commits specification (e.g. `feat: add Synopsys IC Compiler II parser`).
