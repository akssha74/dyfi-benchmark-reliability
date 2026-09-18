"""Phase E: the registered one-shot protected benchmark run (frozen step 9).

Loads the pinned raw GeoJSON snapshot, builds the run lock (mode='protected',
temporal axis, real source-snapshot SHA-256), and executes external_runner's
guarded one-shot EXACTLY ONCE with a single globally-consumed run token. Opens the
protected temporal holdout once, carries frozen best_params (no protected refit /
recalibration / threshold selection), enforces the B3 axis prohibition, and emits
the full no-selective-omission result record. Fails closed on any hash / count /
code / environment / role / leakage / missing-class / subset / one-shot violation.
"""
from __future__ import annotations

import json
import os
import sys
import time

CODE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "code")
ROOT = os.path.dirname(CODE)
sys.path.insert(0, CODE)

import common  # noqa: E402
import environment  # noqa: E402
import external_runner as R  # noqa: E402

RAW = os.path.join(ROOT, "activation", "raw", "dyfi_M5_dyfi_2015_2025_20260901T063330Z.geojson")
SHA = "88722d8aa6d025cfcc3562f29593cc87d84c6a073bf211e8c21d89adddd4d7e9"
OUT_DIR = os.path.join(ROOT, "results", "protected_run_temporal")


def main() -> int:
    environment.verify_environment(strict=True)
    acq = common.load_json(os.path.join(ROOT, "activation", "acquisition_record.json"))
    if acq["source_payload_sha256"] != SHA:
        raise SystemExit("acquisition sha mismatch; fail closed")

    geojson = common.load_json(RAW)
    # Confirm the loaded payload still hashes to the pinned snapshot digest.
    import hashlib
    raw_bytes = open(RAW, "rb").read()
    if hashlib.sha256(raw_bytes).hexdigest() != SHA:
        raise SystemExit("raw payload sha drift; fail closed")

    t0 = time.time()
    lock = R.build_lock(geojson, mode="protected", axis="temporal",
                        source_snapshot_sha256=SHA)
    payload = R.execute_one_shot(geojson, lock, output_dir=OUT_DIR, axis="temporal",
                                 source_snapshot_sha256=SHA)
    runtime_s = time.time() - t0

    core = payload["result_core"]
    ver = payload["verification"]
    summary = {
        "runtime_seconds": round(runtime_s, 2),
        "run_token": payload["run_token"],
        "result_hash": payload["result_hash"],
        "data": core["data"],
        "n_construction": core["n_construction"],
        "n_holdout": core["n_holdout"],
        "fit_count": core["fit_count"],
        "expected_fit_count": core["expected_fit_count"],
        "holdout_opens": core["holdout_opens"],
        "excluded_forbidden_axis": list(core["excluded_forbidden_axis"]),
        "serialization_deterministic": core["serialization_deterministic"],
        "verification": ver,
        "leakage_inflation_headline": core["report"]["leakage_inflation_headline"],
        "difficulty": core["report"]["difficulty_characterization"],
    }
    common.write_json(os.path.join(ROOT, "activation", "run_oneshot_summary.json"), summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
