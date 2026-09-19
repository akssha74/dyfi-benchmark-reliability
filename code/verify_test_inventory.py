"""Verify the four-suite, 110-test inventory without executing model fits."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

EXPECTED = {
    "test_acquisition_reconstruction.py": 24,
    "test_analytics_stack.py": 35,
    "test_benchmark_modules.py": 31,
    "test_runner_report.py": 20,
}


def main() -> int:
    observed: dict[str, int] = {}
    for name in EXPECTED:
        path = HERE / name
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot import {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        observed[name] = unittest.defaultTestLoader.loadTestsFromModule(
            module
        ).countTestCases()

    report = {
        "record_type": "benchmark_test_suite_inventory",
        "n_suites": len(observed),
        "n_tests": sum(observed.values()),
        "suites": observed,
        "expected": EXPECTED,
        "matches": observed == EXPECTED and sum(observed.values()) == 110,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["matches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
