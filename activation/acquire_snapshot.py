"""Phase D: the single dated, hash-pinned outcome-bearing acquisition.

Under the frozen preregistration and source fingerprint, this performs one dated pull of the
pinned outcome-bearing GeoJSON query, co-stamps a /count at the same access
window, verifies the exact-full-response contract (tolerating only declared
catalogue drift between the two HTTP calls), records raw bytes + SHA-256 + counts
+ drift + licence/provenance, saves the raw payload immutably, and writes the
stamped source_locator_manifest.json. It opens NO protected role and scores NO
model; that is the separate one-shot runner step.
"""
from __future__ import annotations

import json
import os
import sys

CODE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "code")
ROOT = os.path.dirname(CODE)
sys.path.insert(0, CODE)

import acquire  # noqa: E402
import common  # noqa: E402
import environment  # noqa: E402
import prehash_rules  # noqa: E402

EXPECTED_PREHASH = "f678d2c2cea07a55e8ad37268b833c9e6f8971022cef855a528424ce1b5ee06e"
RAW_DIR = os.path.join(ROOT, "activation", "raw")
ACQ_OUT = os.path.join(ROOT, "activation", "acquisition_record.json")
# Recorded prior live counts (provenance): 7575 (initial), 7576 (recheck).
DRIFT_TOLERANCE = 25  # events; generous slack for revisions between the two HTTP calls


def main() -> int:
    # (1) environment strict; abort on mismatch.
    env = environment.verify_environment(strict=True)

    # (2) prehash digest must equal the re-pinned lock; abort on drift.
    prehash = prehash_rules.compute_lock().combined_digest
    if prehash != EXPECTED_PREHASH:
        raise SystemExit(f"prehash drift: {prehash} != {EXPECTED_PREHASH} (fail closed)")

    # (3) ONE dated outcome-bearing GeoJSON pull.
    token = f"ACTIVATION|independent_lock_review.json|prehash={prehash}"
    fetched = acquire.fetch_outcome_bearing_geojson(
        activation_token=token, allow_network=True)
    n_features = fetched["n_features"]
    access_instant = fetched["access_instant"]
    raw = fetched["raw_bytes"]
    sha = fetched["source_payload_sha256"]

    # (4) co-stamped /count at the same access window (drift is expected, must be
    #     co-recorded, never mixed into the cohort silently).
    count_rep = acquire.count_only_preflight(execute=True, allow_network=True)
    live_count = count_rep["live_count"]
    count_instant = count_rep["access_instant"]

    # (5) exact-full-response contract (tolerating only the declared drift between
    #     the query and the count HTTP calls).
    delta = n_features - live_count
    receipt = acquire.verify_exact_full_response(
        n_features, live_count, tolerate_drift=DRIFT_TOLERANCE)

    # (6) save the raw payload immutably (the frozen cohort IS these bytes).
    os.makedirs(RAW_DIR, exist_ok=True)
    safe_instant = access_instant.replace(":", "").replace("-", "")
    raw_path = os.path.join(RAW_DIR, f"dyfi_M5_dyfi_2015_2025_{safe_instant}.geojson")
    with open(raw_path, "wb") as f:
        f.write(raw)

    # (7) stamped source-locator manifest (real payload hash lock). Built without
    #     passing preflight_count (which would fail closed on any nonzero drift);
    #     the tolerated exact-full-response receipt is attached explicitly.
    manifest = acquire.source_locator_manifest(
        raw_bytes=raw, access_instant=access_instant, envelope=None,
        status="ACTIVATED_HASH_LOCKED")
    manifest["preflight_count_costamped"] = live_count
    manifest["count_access_instant"] = count_instant
    manifest["payload_features"] = n_features
    manifest["exact_full_response_receipt"] = receipt
    manifest["catalogue_drift_vs_query_count"] = {
        "payload_features": n_features, "costamped_count": live_count,
        "delta": delta, "tolerance": DRIFT_TOLERANCE,
        "drift_is_error": False,
        "interpretation": "Difference between the payload feature count and the "
                          "co-stamped /count reflects catalogue revisions entering/"
                          "leaving the window between the two HTTP calls; the frozen "
                          "cohort is the payload bytes + SHA-256, not a hard count."}
    manifest["recorded_prior_counts"] = {"initial_packet": 7575, "immediate_recheck": 7576,
                                        "note": "prior outcome-free counts; catalogue evolves over time"}
    manifest["licence_provenance"] = {
        "source": "USGS ComCat / FDSNWS Did-You-Feel-It (DYFI)",
        "source_doi": "10.5066/F7J101C8",
        "status": "US Government work / public domain",
        "derived_release_licence": "CC0-1.0 (derived event-level table + provenance hashes)",
        "attribution": "U.S. Geological Survey Earthquake Hazards Program, Did You Feel It?"}
    common.write_json(os.path.join(CODE, "source_locator_manifest.json"), manifest)

    record = {
        "record_type": "outcome_bearing_acquisition_record",
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "access_instant": access_instant,
        "count_access_instant": count_instant,
        "query_url": fetched["query_url"],
        "count_url": count_rep["count_url"],
        "prehash_combined_digest": prehash,
        "activation_token_fingerprint": fetched["activation_token_fingerprint"],
        "payload_features": n_features,
        "costamped_count": live_count,
        "count_delta": delta,
        "drift_tolerance": DRIFT_TOLERANCE,
        "exact_full_response": receipt["exact_full_response"],
        "payload_bytes": fetched["payload_bytes"],
        "source_payload_sha256": sha,
        "raw_payload_path": os.path.relpath(raw_path, ROOT),
        "environment_passed": env["passed"],
        "catalog": fetched["catalog"],
        "single_dated_pull": True,
        "no_mixed_instant": True,
        "protected_role_opened": False,
        "model_fit": False,
    }
    common.write_json(ACQ_OUT, record)
    print(json.dumps({k: record[k] for k in (
        "access_instant", "payload_features", "costamped_count", "count_delta",
        "payload_bytes", "source_payload_sha256", "exact_full_response",
        "raw_payload_path")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
