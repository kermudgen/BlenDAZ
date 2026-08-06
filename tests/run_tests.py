# SPDX-License-Identifier: GPL-3.0-or-later
"""
Test runner that executes pytest INSIDE Blender's Python process.

Usage:
    blender --background --python tests/run_tests.py
    blender --background --python tests/run_tests.py -- tests/test_fabrik_regression.py -v
    blender scene.blend --background --python tests/run_tests.py -- tests/test_golden_poses.py -v

Everything after '--' is passed to pytest.
"""

import sys
import os

# Ensure we're running from the addon root
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(addon_dir)
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

# Extract pytest args: everything after '--' in sys.argv
pytest_args = []
if '--' in sys.argv:
    idx = sys.argv.index('--')
    pytest_args = sys.argv[idx + 1:]

# Default: run all tests in tests/ with verbose output
if not pytest_args:
    pytest_args = ['tests/', '-v', '--tb=short']

# Always use importlib import mode — the root __init__.py is a Blender
# extension entry point, not a Python package. Without this, pytest tries
# to import it as 'blendaz' package and fails.
if '--import-mode' not in ' '.join(pytest_args):
    pytest_args.extend(['--import-mode=importlib'])

print(f"\n{'='*60}")
print(f"BlenDAZ Test Runner")
print(f"Working dir: {os.getcwd()}")
print(f"pytest args: {pytest_args}")
print(f"{'='*60}\n")

import pytest
exit_code = pytest.main(pytest_args)
sys.exit(exit_code)
