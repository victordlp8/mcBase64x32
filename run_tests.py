#!/usr/bin/env python3
"""Test runner script for mcbase64x32 library.

This script provides an easy way to run all tests with different configurations.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return True if successful."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        return False


def main():
    """Main test runner function."""
    print("🧪 mcbase64x32 Test Runner")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("❌ Error: pyproject.toml not found. Please run from project root.")
        sys.exit(1)
    
    # Check if uv is available
    try:
        subprocess.run(["uv", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Error: uv not found. Please install uv first.")
        sys.exit(1)
    
    # Install dependencies
    if not run_command(["uv", "sync"], "Installing dependencies"):
        sys.exit(1)
    
    # Run different test configurations
    test_configs = [
        (["uv", "run", "pytest", "tests/", "-v"], "All tests"),
        (["uv", "run", "pytest", "tests/test_basic_functionality.py", "-v"], "Basic functionality tests"),
        (["uv", "run", "pytest", "tests/test_roundtrip.py", "-v"], "Round-trip tests"),
        (["uv", "run", "pytest", "tests/test_error_handling.py", "-v"], "Error handling tests"),
        (["uv", "run", "pytest", "tests/", "--cov=src/mcbase64x32", "--cov-report=term-missing"], "Tests with coverage"),
        (["uv", "run", "pytest", "tests/test_roundtrip.py::TestRoundTrip::test_known_failure_case", "-v"], "Known failure case test"),
    ]
    
    success_count = 0
    total_count = len(test_configs)
    
    for cmd, description in test_configs:
        if run_command(cmd, description):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"Test Summary: {success_count}/{total_count} test suites passed")
    print('='*60)
    
    if success_count == total_count:
        print("🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
