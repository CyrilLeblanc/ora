#!/usr/bin/env python3
"""
Ora — backward-compatibility launcher.
The application has been refactored into the `ora/` package.
Run with:  python3 -m ora
Or simply: python3 ora.py  (this file)
"""
import runpy, sys, os

# Make sure the project root is on sys.path so `import ora` finds the package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
runpy.run_module("ora", run_name="__main__", alter_sys=True)
