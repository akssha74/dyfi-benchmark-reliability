"""Stage validator for the DYFI acquisition / reconstruction / one-shot-runner
construction stage.

Companion to (and independent of) ``validate_stage.py`` (the analytics-stack
gate). It:

  1. verifies the pinned environment and FAILS on any version mismatch;
  2. asserts every load-bearing file and synthetic integration fixture is present
     (fixture-removal detector);
  3. executes EVERY load-bearing unit test (all four suites) with zero failures;
  4. runs the full SYNTHETIC one-shot runner pipeline twice and the reconstruction
     twice, requiring bit-identical result/pipeline hashes (determinism);
  5. confirms the outcome-bearing fetch is DISABLED and the protected run is
     blocked (fail-closed), while the count-only preflight is outcome-free;
  6. emits the stage artifacts (pre-hash lock, count preflight, pending source
     manifest, reconstruction manifest, runner result) and hashes every
     load-bearing source + output file into a manifest.

Exit code 0 iff all checks pass. Writes acquisition_stage_validation.json.

Run:  python validate_acquisition_stage.py
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from typing import Dict, List

import acquire
import common
import environment
import external_runner as runner
import integration_fixtures as ifx
import prehash_rules
import reconstruct

HERE = os.path.dirname(os.path.abspath(__file__))

# Load-bearing files for THIS stage (new modules + the fixed interfaces they
# depend on + the interface contract). Removing any FAILS validation.
REQUIRED_FILES: List[str] = [
    # new acquisition/reconstruction/runner/report stage
    "prehash_rules.py", "acquire.py", "reconstruct.py", "external_runner.py",
    "report.py", "integration_fixtures.py",
    "test_acquisition_reconstruction.py", "test_runner_report.py",
    "runner_interface_contract.json",
    # fixed interfaces consumed by this stage (must remain present)
    "common.py", "leakage_audit.py", "endpoint.py", "decluster.py",
    "ingest_eligibility.py", "role_assignment.py", "environment.py",
    "metrics.py", "baselines.py",
]

REQUIRED_INTEGRATION_FIXTURES: List[str] = [
    "make_source_geojson", "make_leakage_demo_table",
]

TEST_MODULES: List[str] = [
    "test_benchmark_modules", "test_analytics_stack",
    "test_acquisition_reconstruction", "test_runner_report",
]

# Output artifacts written and hashed by this stage.
STAGE_ARTIFACTS = [
    "role_quarantine_prehash.json",
    "source_count_preflight.json",
    "source_locator_manifest.json",
    "reconstruction_manifest.json",
    "runner_result.json",
]


def check_files() -> Dict[str, object]:
    missing = [f for f in REQUIRED_FILES if not os.path.isfile(os.path.join(HERE, f))]
    return {"passed": len(missing) == 0, "missing": missing, "n_required": len(REQUIRED_FILES)}


def check_fixtures() -> Dict[str, object]:
    try:
        import integration_fixtures as fx
    except Exception as exc:  # pragma: no cover
        return {"passed": False, "reason": f"import failed: {exc!r}",
                "missing": REQUIRED_INTEGRATION_FIXTURES}
    missing = [n for n in REQUIRED_INTEGRATION_FIXTURES if not hasattr(fx, n)]
    return {"passed": len(missing) == 0, "missing": missing,
            "n_required": len(REQUIRED_INTEGRATION_FIXTURES)}


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


def run_runner_twice() -> Dict[str, object]:
    r1 = runner.run_synthetic_smoke()
    r2 = runner.run_synthetic_smoke()
    h1 = common.sha256_text(common.canonical_json(r1["result_core"]))
    h2 = common.sha256_text(common.canonical_json(r2["result_core"]))
    core = r1["result_core"]
    return {
        "passed": h1 == h2
        and core["fit_count"] == core["expected_fit_count"] == 91
        and core["holdout_opens"] == 1
        and "B3_expanded_metadata_logit" in core["excluded_forbidden_axis"]
        and core["real_protected_role_opened"] is False,
        "run1_hash": h1,
        "run2_hash": h2,
        "fit_count": core["fit_count"],
        "expected_fit_count": core["expected_fit_count"],
        "holdout_opens": core["holdout_opens"],
        "excluded_forbidden_axis": list(core["excluded_forbidden_axis"]),
    }


def run_reconstruct_twice() -> Dict[str, object]:
    gj = ifx.make_source_geojson(seed=20260901, n_eligible=300)
    a = reconstruct.reconstruct(gj, mode="temporal")
    b = reconstruct.reconstruct(gj, mode="temporal")
    order_stable = reconstruct.verify_order_stability(gj, mode="temporal")
    return {
        "passed": a.pipeline_digest == b.pipeline_digest and a.leakage_passed and order_stable,
        "pipeline_digest": a.pipeline_digest,
        "order_stable": order_stable,
        "leakage_passed": a.leakage_passed,
    }


def check_acquisition_guards() -> Dict[str, object]:
    pre = acquire.count_only_preflight(execute=False)
    fetch_disabled = False
    try:
        acquire.fetch_outcome_bearing_geojson()
    except acquire.AcquisitionDisabledError:
        fetch_disabled = True
    protected = runner.protected_activation_status()
    return {
        "passed": pre["outcome_free"] and not pre["executed_live"]
        and fetch_disabled and not protected["protected_run_ready"],
        "count_preflight_outcome_free": pre["outcome_free"],
        "outcome_bearing_fetch_disabled": fetch_disabled,
        "count_drift": pre["drift_receipt"]["count_drift"],
        "protected_run_ready": protected["protected_run_ready"],
        "protected_blockers": protected["blockers"],
    }


def emit_artifacts() -> Dict[str, str]:
    """Write the stage artifacts and return the digest of the runner result core."""
    common.write_json(os.path.join(HERE, "role_quarantine_prehash.json"),
                      prehash_rules.lock_record())
    common.write_json(os.path.join(HERE, "source_count_preflight.json"),
                      acquire.count_only_preflight(execute=False))
    common.write_json(os.path.join(HERE, "source_locator_manifest.json"),
                      acquire.source_locator_manifest())

    gj = ifx.make_source_geojson(seed=20260901, n_eligible=300)
    recon = reconstruct.reconstruct(gj, mode="temporal")
    common.write_json(os.path.join(HERE, "reconstruction_manifest.json"),
                      recon.manifest_record())

    result = runner.run_synthetic_smoke()
    core_hash = common.sha256_text(common.canonical_json(result["result_core"]))
    common.write_json(os.path.join(HERE, "runner_result.json"),
                      {"result_hash": core_hash, **result})
    return {"runner_result_core_hash": core_hash,
            "reconstruction_pipeline_digest": recon.pipeline_digest}


def hash_manifest() -> Dict[str, str]:
    manifest: Dict[str, str] = {}
    for f in REQUIRED_FILES + STAGE_ARTIFACTS:
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
    checks["acquisition_guards"] = check_acquisition_guards()
    checks["unit_tests"] = run_tests()
    checks["runner_determinism"] = run_runner_twice()
    checks["reconstruct_determinism"] = run_reconstruct_twice()

    digests = emit_artifacts()
    overall = all(bool(v.get("passed")) for v in checks.values())

    report = {
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "stage": "acquisition_reconstruction_oneshot_runner_construction",
        "overall_passed": overall,
        "checks": checks,
        "artifact_digests": digests,
        "prehash_combined_digest": prehash_rules.compute_lock().combined_digest,
        "output_hash_manifest": hash_manifest(),
    }
    common.write_json(os.path.join(HERE, "acquisition_stage_validation.json"), report)

    print("=== acquisition/reconstruction stage validation ===")
    for name, res in checks.items():
        print(f"  {name:24s}: {'PASS' if res.get('passed') else 'FAIL'}")
    print("  unit tests run          :", checks["unit_tests"]["tests_run"])
    print("  runner result hash      :", digests["runner_result_core_hash"])
    print("  reconstruction digest   :", digests["reconstruction_pipeline_digest"])
    print("OVERALL:", "PASS" if overall else "FAIL")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
