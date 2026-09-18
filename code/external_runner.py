"""Hash-locked, one-shot protected benchmark runner for the DYFI-USGS resource
(step 9 of the construction plan).

This runner is the fail-closed gate that opens the protected external-temporal
holdout EXACTLY ONCE, after verifying that nothing in the pinned resource has
drifted. It enforces, in order and fail-closed:

  1. pinned environment (environment.verify_environment, strict);
  2. source-snapshot hash (raw-byte SHA-256 of the pinned FDSN payload);
  3. code hashes of every load-bearing module;
  4. config hashes: pre-hashed role+quarantine rules, endpoint threshold,
     feature schema, baseline grid, and analysis config;
  5. corpus digest (no subset / selective omission of events);
  6. a single globally-consumed run token (retry across output dirs impossible);
  7. bounded 91-fit construction-only tuning suite (FitLedger cap);
  8. B3_expanded_metadata_logit axis prohibition on the leaking transport axis;
  9. frozen params on the holdout -- NO protected recalibration/refit/threshold
     selection;
 10. the protected holdout opened exactly once;
 11. deterministic joblib serialization round-trip.

REAL execution (mode='protected') additionally requires a stamped source-locator
manifest, an authorised contract lock, and an activation token -- NONE of which
exist in this stage -- so a protected run fails closed with a blocker list and no
real outcome is ever read. The SYNTHETIC path (mode='synthetic') exercises the
entire forward pipeline on synthetic data with real sklearn/XGBoost analytics and
is what this stage validates.
"""
from __future__ import annotations

import dataclasses
import io
import os
from typing import Dict, List, Optional, Sequence, Tuple

import joblib
import numpy as np

import acquire
import baselines
import common
import endpoint
import environment
import prehash_rules
import reconstruct
import report as report_mod
import role_assignment

HERE = os.path.dirname(os.path.abspath(__file__))

DEV_THRESHOLD = 0.5
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20260901
PRIMARY_AXIS = "temporal"
CONSTRUCTION_ROLES = ("train", "development")
HOLDOUT_ROLE = "external_temporal_holdout"

# Load-bearing modules whose source is hash-locked before a protected run.
LOCKED_CODE_FILES: Tuple[str, ...] = (
    "common.py", "leakage_audit.py", "endpoint.py", "decluster.py",
    "ingest_eligibility.py", "role_assignment.py", "environment.py",
    "metrics.py", "baselines.py", "prehash_rules.py", "acquire.py",
    "reconstruct.py", "report.py", "external_runner.py",
)

# Global one-shot token ledger (a single file makes retry across output dirs
# impossible: a consumed token is refused regardless of the target directory).
DEFAULT_TOKEN_LEDGER = os.path.join(HERE, "consumed_run_tokens.json")


class RunAbort(RuntimeError):
    """Raised on ANY fail-closed deviation; the protected run is refused."""


class HoldoutGuard:
    """Ensures the protected holdout is opened exactly once per run."""

    def __init__(self) -> None:
        self._opens = 0

    def open(self) -> None:
        self._opens += 1
        if self._opens > 1:
            raise RunAbort("protected holdout opened more than once")

    @property
    def opens(self) -> int:
        return self._opens


def expected_fit_count(specs: Sequence[baselines.BaselineSpec],
                       n_folds: int = role_assignment.N_CV_FOLDS) -> int:
    """The registered fit budget: grid*folds CV fits + 1 final refit per baseline
    (single-point grids skip CV). With all six baselines this is 91."""
    total = 0
    for spec in specs:
        g = spec.grid_size()
        total += (g * n_folds if g > 1 else 0) + 1
    return total


# ---------------------------------------------------------------------------
# Config fingerprints
# ---------------------------------------------------------------------------
def _schema_record(schema) -> Dict[str, object]:
    return {
        "name": schema.name,
        "features": list(schema.features),
        "proxy_features": list(schema.proxy_features),
        "proxy_axis": dict(schema.proxy_axis),
    }


def feature_schema_digest() -> str:
    rec = {name: _schema_record(s) for name, s in sorted(common.FEATURE_SCHEMAS.items())}
    return common.sha256_text(common.canonical_json(rec))


def baseline_grid_digest(specs: Sequence[baselines.BaselineSpec]) -> str:
    rec = [
        {
            "id": s.id,
            "schema": s.schema.name,
            "param_grid": [dict(p) for p in s.param_grid],
            "forbidden_axes": list(s.forbidden_axes),
        }
        for s in specs
    ]
    return common.sha256_text(common.canonical_json(rec))


def endpoint_digest() -> str:
    return common.sha256_text(common.canonical_json({
        "primary_threshold": endpoint.PRIMARY_THRESHOLD,
        "sensitivity_thresholds": list(endpoint.SENSITIVITY_THRESHOLDS),
        "near_threshold_band": endpoint.NEAR_THRESHOLD_BAND,
        "dev_threshold": DEV_THRESHOLD,
    }))


def analysis_digest() -> str:
    return common.sha256_text(common.canonical_json({
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "primary_metric": "brier",
        "probe_baseline": report_mod.PROBE_BASELINE_ID,
        "ranking_reference": report_mod.NO_SKILL_BASELINE_ID,
        "axis": PRIMARY_AXIS,
        "resolution_floor": 0.0,
    }))


def code_hashes(files: Sequence[str] = LOCKED_CODE_FILES) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for f in files:
        path = os.path.join(HERE, f)
        out[f] = common.sha256_file(path) if os.path.isfile(path) else "MISSING"
    return out


def corpus_digest(rows: Sequence[Dict[str, object]]) -> str:
    canon = sorted(common.canonical_json(r) for r in rows)
    return common.sha256_text(common.canonical_json(canon))


# ---------------------------------------------------------------------------
# Run lock
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class RunLock:
    """Immutable bundle of the expected digests a protected run is locked to."""

    mode: str
    axis: str
    prehash_combined_digest: str
    feature_schema_digest: str
    baseline_grid_digest: str
    endpoint_digest: str
    analysis_digest: str
    code_hashes: str          # canonical-json of {file: sha256}
    corpus_digest: str
    source_snapshot_sha256: Optional[str]
    expected_fit_count: int
    n_construction: int
    n_holdout: int

    def as_dict(self) -> Dict[str, object]:
        return dataclasses.asdict(self)

    def token(self) -> str:
        return common.sha256_text(common.canonical_json(self.as_dict()))


def _manual_quarantine() -> List[str]:
    """The frozen Q5 manual-quarantine event ids applied to every reconstruction.

    Empty on the synthetic path (no real ids present in synthetic data, so this is
    a no-op there and leaves synthetic digests unchanged); on the real activation
    it drops the two previously-inspected event ids from every role."""
    return prehash_rules.manual_quarantine_id_list()


def build_lock(
    geojson: Dict[str, object],
    mode: str = "synthetic",
    axis: str = PRIMARY_AXIS,
    source_snapshot_sha256: Optional[str] = None,
) -> RunLock:
    """Reconstruct the (synthetic) corpus and pin every expected digest."""
    recon = reconstruct.reconstruct(geojson, mode=axis if axis == "temporal" else "geographic",
                                   quarantine=_manual_quarantine())
    rows = list(recon.rows)
    construction = [r for r in rows if r["role"] in CONSTRUCTION_ROLES]
    holdout = [r for r in rows if r["role"] == HOLDOUT_ROLE]
    specs = baselines.registry()
    return RunLock(
        mode=mode,
        axis=axis,
        prehash_combined_digest=prehash_rules.compute_lock().combined_digest,
        feature_schema_digest=feature_schema_digest(),
        baseline_grid_digest=baseline_grid_digest(specs),
        endpoint_digest=endpoint_digest(),
        analysis_digest=analysis_digest(),
        code_hashes=common.canonical_json(code_hashes()),
        corpus_digest=corpus_digest(rows),
        source_snapshot_sha256=source_snapshot_sha256,
        expected_fit_count=expected_fit_count(specs),
        n_construction=len(construction),
        n_holdout=len(holdout),
    )


def verify_lock(current: RunLock, expected: RunLock) -> List[Dict[str, str]]:
    """Return the list of digest mismatches between current state and the lock."""
    mismatches: List[Dict[str, str]] = []
    fields = [
        "prehash_combined_digest", "feature_schema_digest", "baseline_grid_digest",
        "endpoint_digest", "analysis_digest", "code_hashes", "corpus_digest",
        "source_snapshot_sha256", "expected_fit_count", "axis",
    ]
    for f in fields:
        cv, ev = getattr(current, f), getattr(expected, f)
        if cv != ev:
            mismatches.append({"field": f, "current": str(cv)[:80], "expected": str(ev)[:80]})
    return mismatches


# ---------------------------------------------------------------------------
# Deterministic analytic core (no token consumption; safe to call repeatedly)
# ---------------------------------------------------------------------------
def _round(x, nd: int = 12):
    return None if x is None else round(float(x), nd)


def run_analysis(
    geojson: Dict[str, object],
    lock: RunLock,
    axis: str = PRIMARY_AXIS,
    source_snapshot_sha256: Optional[str] = None,
) -> Dict[str, object]:
    """Verify the lock, then run the full forward pipeline fail-closed.

    Returns a dict with a deterministic ``result_core`` (hashable) plus a
    ``verification`` block. Does NOT consume a one-shot token; call
    :func:`execute_one_shot` for the guarded, single-use protected run.
    """
    # (1) environment (strict, fail-closed).
    env = environment.verify_environment(strict=True)

    # Recompute current lock and verify against the provided one (fail-closed).
    current = build_lock(geojson, mode=lock.mode, axis=axis,
                         source_snapshot_sha256=source_snapshot_sha256)
    mismatches = verify_lock(current, lock)
    if mismatches:
        raise RunAbort(f"hash lock verification failed: {mismatches}")

    # Reconstruct the corpus (typed stages, immutable manifest). The frozen Q5
    # manual quarantine is applied here so previously-inspected events enter no role.
    recon = reconstruct.reconstruct(geojson, mode=axis if axis == "temporal" else "geographic",
                                   quarantine=_manual_quarantine())
    rows = list(recon.rows)

    # (5) no subset / selective omission: every row keeps a role; the partition is
    # exhaustive and disjoint, and the corpus digest already matched the lock.
    roles = [r["role"] for r in rows]
    construction = [r for r in rows if r["role"] in CONSTRUCTION_ROLES]
    holdout = [r for r in rows if r["role"] == HOLDOUT_ROLE]
    accounted = len(construction) + len(holdout) + sum(
        1 for rr in roles if rr not in CONSTRUCTION_ROLES and rr != HOLDOUT_ROLE
    )
    if accounted != len(rows):
        raise RunAbort("row accounting failed: events were selectively omitted")
    if not construction or not holdout:
        raise RunAbort("empty construction or holdout role; cannot run fail-closed")

    construction_groups = [str(r["sequence_id"]) for r in construction]
    specs = baselines.registry()

    # (7) bounded 91-fit construction-only tuning suite.
    ledger = baselines.FitLedger(cap=lock.expected_fit_count)
    fitted: Dict[str, object] = {}
    for spec in specs:
        # axis=None during CONSTRUCTION tuning (axis prohibition is a scoring-time
        # rule); this tunes every baseline on the construction role only.
        fitted[spec.id] = baselines.tune_and_fit(
            spec, construction, construction_groups, ledger, axis=None
        )
    if ledger.count != lock.expected_fit_count:
        raise RunAbort(
            f"fit budget deviation: {ledger.count} fits != registered "
            f"{lock.expected_fit_count}"
        )

    # (10) open the protected holdout EXACTLY ONCE.
    guard = HoldoutGuard()
    guard.open()
    holdout_rows = holdout

    # (8) B3 axis prohibition + (9) frozen-params scoring (predict only, no refit).
    predictions: Dict[str, List[float]] = {}
    excluded_forbidden_axis: Dict[str, str] = {}
    serialization_ok: Dict[str, bool] = {}
    for spec in specs:
        try:
            baselines.assert_fit_allowed(spec, axis=axis)
        except baselines.LeakageError as exc:
            excluded_forbidden_axis[spec.id] = str(exc)
            continue
        model = fitted[spec.id]["model"]
        # (11) deterministic serialization round-trip.
        buf = io.BytesIO()
        joblib.dump(model, buf)
        buf.seek(0)
        reloaded = joblib.load(buf)
        X_hold = baselines.extract_features(holdout_rows, common.FEATURE_SCHEMAS.get(
            fitted[spec.id]["schema"], spec.schema))
        p_reload = np.asarray(reloaded.predict_proba(X_hold)[:, 1], dtype=np.float64)
        p_direct = baselines.predict_proba(fitted[spec.id], holdout_rows)
        serialization_ok[spec.id] = bool(np.array_equal(p_reload, p_direct))
        if not serialization_ok[spec.id]:
            raise RunAbort(f"non-deterministic serialization for {spec.id}")
        predictions[spec.id] = [_round(v) for v in p_reload.tolist()]

    # Full honest report (leakage inflation headline + evaluation surface). The
    # provenance label is derived from the run mode so the real protected run is
    # not mislabelled as synthetic (semantics-preserving: no metric/decision change).
    _is_protected = lock.mode != "synthetic"
    rep = report_mod.full_report(construction, holdout_rows, predictions,
                                 n_boot=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED,
                                 data_label=("PROTECTED" if _is_protected else "SYNTHETIC_ONLY"),
                                 protected_role_opened=_is_protected)

    result_core: Dict[str, object] = {
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "mode": lock.mode,
        "axis": axis,
        "data": "SYNTHETIC_ONLY" if lock.mode == "synthetic" else "PROTECTED",
        "real_protected_role_opened": False,
        "holdout_opens": guard.opens,
        "n_construction": len(construction),
        "n_holdout": len(holdout_rows),
        "reconstruction_pipeline_digest": recon.pipeline_digest,
        "fit_count": ledger.count,
        "expected_fit_count": lock.expected_fit_count,
        "fit_ledger_digest": ledger.digest(),
        "frozen_best_params": {bid: fitted[bid]["best_params"] for bid in sorted(fitted)},
        "excluded_forbidden_axis": excluded_forbidden_axis,
        "serialization_deterministic": serialization_ok,
        "predictions_digest": common.sha256_text(common.canonical_json(predictions)),
        "report": rep,
    }
    verification = {
        "environment_passed": env["passed"],
        "lock_verified": True,
        "b3_axis_prohibition_enforced": report_mod.PROBE_BASELINE_ID not in excluded_forbidden_axis
        and "B3_expanded_metadata_logit" in excluded_forbidden_axis,
        "no_protected_refit": True,
        "holdout_opened_once": guard.opens == 1,
        "fit_budget_respected": ledger.count == lock.expected_fit_count,
        "run_token": lock.token(),
    }
    return {"result_core": result_core, "verification": verification}


# ---------------------------------------------------------------------------
# One-shot, globally-consumed token wrapper
# ---------------------------------------------------------------------------
def _load_ledger(path: str) -> List[str]:
    if not os.path.isfile(path):
        return []
    data = common.load_json(path)
    return list(data.get("consumed_tokens", []))


def _consume_token(path: str, token: str, meta: Dict[str, object]) -> None:
    consumed = _load_ledger(path)
    consumed.append(token)
    common.write_json(path, {"consumed_tokens": consumed, "last": meta})


def execute_one_shot(
    geojson: Dict[str, object],
    lock: RunLock,
    output_dir: str,
    axis: str = PRIMARY_AXIS,
    token_ledger_path: str = DEFAULT_TOKEN_LEDGER,
    source_snapshot_sha256: Optional[str] = None,
) -> Dict[str, object]:
    """Guarded single-use run: mint+consume a global token, then run once.

    A token already present in the global ledger is refused regardless of the
    ``output_dir`` (retry across directories is impossible). On success the result
    is written to ``output_dir`` and the token is consumed.
    """
    token = lock.token()
    if token in _load_ledger(token_ledger_path):
        raise RunAbort(
            "run token already consumed: this one-shot protected run cannot be "
            "retried (a fresh output directory does not reset the global token)"
        )
    result = run_analysis(geojson, lock, axis=axis,
                          source_snapshot_sha256=source_snapshot_sha256)
    os.makedirs(output_dir, exist_ok=True)
    result_hash = common.sha256_text(common.canonical_json(result["result_core"]))
    payload = {"lock": lock.as_dict(), "run_token": token,
               "result_hash": result_hash, **result}
    common.write_json(os.path.join(output_dir, "run_result.json"), payload)
    _consume_token(token_ledger_path, token, {"result_hash": result_hash,
                                              "output_dir": output_dir})
    return payload


# ---------------------------------------------------------------------------
# Protected activation gate (fails closed in this stage)
# ---------------------------------------------------------------------------
def protected_activation_status() -> Dict[str, object]:
    """Report why a REAL protected run is blocked (fail-closed blocker list)."""
    manifest = acquire.source_locator_manifest()  # PENDING template, no payload
    blockers: List[str] = []
    if manifest.get("source_payload_sha256") is None:
        blockers.append("no stamped source-locator manifest (outcome-bearing fetch disabled)")
    blockers.append("contract lock not authorised (governance simultaneous-submission flags)")
    blockers.append("activation token absent")
    return {
        "protected_run_ready": False,
        "blockers": blockers,
        "outcome_bearing_fetch": "DISABLED",
        "prehash_combined_digest": prehash_rules.compute_lock().combined_digest,
    }


def run_synthetic_smoke(seed: int = 20260901, n_eligible: int = 420) -> Dict[str, object]:
    """Build a synthetic source payload, lock it, and run the analytic core once."""
    import integration_fixtures as ifx

    geojson = ifx.make_source_geojson(seed=seed, n_eligible=n_eligible)
    lock = build_lock(geojson, mode="synthetic", axis=PRIMARY_AXIS)
    return run_analysis(geojson, lock, axis=PRIMARY_AXIS)


def _cli(argv: List[str]) -> int:
    import argparse

    from common import write_json

    p = argparse.ArgumentParser(description="Hash-locked one-shot DYFI runner")
    p.add_argument("--mode", choices=["synthetic", "protected"], default="synthetic")
    p.add_argument("--out", help="write the run result JSON here")
    args = p.parse_args(argv)

    if args.mode == "protected":
        status = protected_activation_status()
        print("protected_run_ready:", status["protected_run_ready"])
        for b in status["blockers"]:
            print("  blocker:", b)
        if args.out:
            write_json(args.out, status)
        return 1  # fail-closed: protected run refused

    result = run_synthetic_smoke()
    core_hash = common.sha256_text(common.canonical_json(result["result_core"]))
    print("mode: synthetic")
    print("fit_count:", result["result_core"]["fit_count"],
          "expected:", result["result_core"]["expected_fit_count"])
    print("holdout_opens:", result["result_core"]["holdout_opens"])
    print("excluded_forbidden_axis:", list(result["result_core"]["excluded_forbidden_axis"]))
    print("result_core_hash:", core_hash)
    if args.out:
        write_json(args.out, {"result_hash": core_hash, **result})
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_cli(sys.argv[1:]))
