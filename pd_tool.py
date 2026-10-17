#!/usr/bin/env python3
"""
Entry-point launcher for the Physical Design Automation Toolkit.
Usage:
    python pd_tool.py parse --path <reports_dir> --dashboard dashboard.html
    python pd_tool.py lint-sdc --sdc <constraints.sdc>
    python pd_tool.py compare --baseline <run_a> --current <run_b>
    python pd_tool.py demo
"""

import sys
from pathlib import Path

# Ensure package directory is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from pd_toolkit.cli import main

if __name__ == "__main__":
    main()
