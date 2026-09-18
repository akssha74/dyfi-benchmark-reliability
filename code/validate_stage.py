"""Stage validator for the DYFI benchmark analytics stack.

This is the load-bearing gate for the construction analytics stage. It:

  1. verifies the pinned environment and FAILS on any version mismatch;
  2. asserts every load-bearing file and synthetic fixture is present, and FAILS
     if any fixture/test was removed (fixture-removal detector);
  3. executes EVERY load-bearing unit test (both suites) and requires zero
     failures/errors;
  4. runs the full synthetic forward smoke pipeline twice and requires bit-
     identical result hashes (deterministic reproducibility);
  5. hashes every load-bearing source + output file into a manifest.

Exit code 0 iff all checks pass. Writes validation_report.json.

Run:  python validate_stage.py
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from typing import Dict, List

import common
import environment

HERE = os.path.dirname(os.path.abspath(__file__))

# Load-bearing source + interface files. Removing any of these FAILS validation.
REQUIRED_FILES: List[str] = [
    # six repaired core modules (interfaces; inspected, not redesigned)
    "common.py",
    "leakage_audit.py",
    "endpoint.py",
    "decluster.py",
    "ingest_eligibility.py",
    "role_assignment.py",
    "test_benchmark_modules.py",
    # analytics stack built this stage
    "environment.py",
    "requirements.lock.txt",
    "metrics.py",
    "baselines.py",
    "synthetic_fixtures.py",
    "test_analytics_stack.py",
    "smoke_test.py",
    "ipe_exclusion.json",
    "runner_interface_contract.json",
]

# Load-bearing synthetic fixtures. Removing any FAILS validation.
REQUIRED_FIXTURES: List[str] = [
    "make_event_table",
    "groups_of",
    "labels_of",
    "normal_yp",
    "constant_prediction_yp",
    "tied_yp",
    "one_class_yp",
    "missing_class_corpus",
    "leakage_fixture",
]

# Load-bearing test modules that must run and pass.
TEST_MODULES: List[str] = ["test_benchmark_modules", "test_analytics_stack"]


def check_files() -> Dict[str, object]:
    missing = [f for f in REQUIRED_FILES if not os.path.isfile(os.path.join(HERE, f))]
    return {"passed": len(missing) == 0, "missing": missing,
            "n_required": len(REQUIRED_FILES)}


def check_fixtures() -> Dict[str, object]:
    try:
        import synthetic_fixtures as fx
    except Exception as exc:  # pragma: no cover
        return {"passed": False, "reason": f"import failed: {exc!r}", "missing": REQUIRED_FIXTURES}
    missing = [name for name in REQUIRED_FIXTURES if not hasattr(fx, name)]
    return {"passed": len(missing) == 0, "missing": missing,
            "n_required": len(REQUIRED_FIXTURES)}


def run_tests() -> Dict[str, object]:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for mod in TEST_MODULES:
        suite.addTests(loader.loadTestsFromName(mod))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    return {
        "passed": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "modules": TEST_MODULES,
        "failure_names": [str(t) for t, _ in result.failures],
        "error_names": [str(t) for t, _ in result.errors],
    }


def run_smoke_twice() -> Dict[str, object]:
    import smoke_test
    core1 = smoke_test.run_pipeline()
    core2 = smoke_test.run_pipeline()
    h1 = common.sha256_text(common.canonical_json(core1))
    h2 = common.sha256_text(common.canonical_json(core2))
    return {
        "passed": h1 == h2,
        "run1_hash": h1,
        "run2_hash": h2,
        "fit_ledger_count": core1["fit_ledger_count"],
        "fit_cap": core1["fit_cap"],
        "fit_cap_respected": core1["fit_ledger_count"] <= core1["fit_cap"],
    }


def hash_manifest() -> Dict[str, str]:
    manifest: Dict[str, str] = {}
    for f in REQUIRED_FILES + ["env_lock.json", "smoke_report.json"]:
        path = os.path.join(HERE, f)
        if os.path.isfile(path):
            manifest[f] = common.sha256_file(path)
    return manifest


def main() -> int:
    checks: Dict[str, object] = {}

    try:
        env = environment.verify_environment(strict=True)
        checks["environment"] = {"passed": env["passed"], "detail": env}
    except RuntimeError as exc:
        checks["environment"] = {"passed": False, "detail": str(exc)}

    checks["files"] = check_files()
    checks["fixtures"] = check_fixtures()
    checks["unit_tests"] = run_tests()
    checks["smoke_determinism"] = run_smoke_twice()

    overall = all(bool(v.get("passed")) for v in checks.values())
    report = {
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "stage": "analytics_stack_construction",
        "overall_passed": overall,
        "checks": checks,
        "output_hash_manifest": hash_manifest(),
    }
    common.write_json(os.path.join(HERE, "validation_report.json"), report)

    print("=== stage validation ===")
    for name, res in checks.items():
        print(f"  {name:20s}: {'PASS' if res.get('passed') else 'FAIL'}")
    print("  unit tests run     :", checks["unit_tests"]["tests_run"])
    print("OVERALL:", "PASS" if overall else "FAIL")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
