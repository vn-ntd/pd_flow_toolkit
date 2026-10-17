#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="pd-flow-toolkit",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "pd-toolkit=pd_toolkit.cli:main",
            "pd-flow=pd_toolkit.cli:main",
        ],
    },
)
