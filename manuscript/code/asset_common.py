"""Shared, deterministic helpers for post-review manuscript-asset generation.

This module NEVER opens a protected role, never consumes the one-shot token,
never refits or retunes a model to *select* anything, and never mutates a frozen
author/result artifact. It only:

  * loads immutable released artifacts (the pinned raw snapshot, the released
    event-level table, the frozen protected ``run_result.json``);
  * deterministically RECONSTRUCTS the frozen holdout predictions by fitting each
    registered baseline with its already-FROZEN ``best_params`` on the released
    construction rows and predicting the released holdout rows -- exactly the
    computation whose output the protected run already recorded -- and then
    verifies bit-for-bit that the reconstruction reproduces the recorded
    ``predictions_digest`` and every recorded per-baseline score before any new
    number is derived from it;
  * exposes small pure helpers (hashing, rounding) reused by the table/figure
    and pairwise-ranking generators.

Everything imports the frozen, hash-locked modules under ``code/`` so the
analytics are byte-identical to the protected run's.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Dict, List, Tuple

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CODE = os.path.join(ROOT, "code")
if CODE not in sys.path:
    sys.path.insert(0, CODE)

import baselines  # noqa: E402
import common  # noqa: E402
import external_runner as R  # noqa: E402
import metrics  # noqa: E402
import reconstruct  # noqa: E402

RAW = os.path.join(
    ROOT, "activation", "raw", "dyfi_M5_dyfi_2015_2025_20260901T063330Z.geojson"
)
SOURCE_SHA = "88722d8aa6d025cfcc3562f29593cc87d84c6a073bf211e8c21d89adddd4d7e9"
RUN_RESULT = os.path.join(ROOT, "results", "protected_run_temporal", "run_result.json")
EVENT_TABLE = os.path.join(ROOT, "bundle", "release", "event_level_table.csv")

# Registered analysis constants, mirrored from the frozen runner/report so the
# reconstruction is identical (asserted against the recorded digests below).
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20260901
DEV_THRESHOLD = 0.5
RESOLUTION_FLOOR = 0.0  # the genuinely pre-registered value (metrics default + report call)
PRIMARY_AXIS = "temporal"
CONSTRUCTION_ROLES = ("train", "development")
HOLDOUT_ROLE = "external_temporal_holdout"


def sha256_file(path: str) -> str:
    return common.sha256_file(path)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _round12(x, nd: int = 12):
    return None if x is None else round(float(x), nd)


def load_run_result() -> Dict[str, object]:
    return common.load_json(RUN_RESULT)


def verify_source_snapshot() -> Dict[str, object]:
    raw = open(RAW, "rb").read()
    got = sha256_bytes(raw)
    return {
        "path": os.path.relpath(RAW, ROOT),
        "recorded_sha256": SOURCE_SHA,
        "recomputed_sha256": got,
        "match": got == SOURCE_SHA,
        "bytes": len(raw),
    }


def reconstruct_rows() -> Tuple[List[dict], List[dict], object]:
    """Deterministically rebuild construction + holdout rows in canonical order.

    Uses the frozen reconstruction pipeline with the frozen Q5 manual quarantine,
    exactly as the protected one-shot did. Reads only the pinned raw snapshot.
    """
    geojson = common.load_json(RAW)
    recon = reconstruct.reconstruct(
        geojson, mode="temporal", quarantine=R._manual_quarantine()
    )
    rows = list(recon.rows)
    construction = [r for r in rows if r["role"] in CONSTRUCTION_ROLES]
    holdout = [r for r in rows if r["role"] == HOLDOUT_ROLE]
    return construction, holdout, recon


def reconstruct_frozen_predictions() -> Dict[str, object]:
    """Rebuild the frozen holdout predictions from released rows + frozen params.

    For each registered baseline that is NOT axis-excluded on the temporal
    transport holdout, build the model with its FROZEN ``best_params`` (no
    re-tuning), fit on the construction rows, predict the holdout rows, and round
    to 12 dp -- byte-identical to what the protected runner serialized. Returns
    the predictions dict, the axis-exclusion map, and the released holdout arrays
    (labels, sequence groups, years, region cells, max_cdi) needed downstream.
    """
    run = load_run_result()
    core = run["result_core"]
    frozen_params = core["frozen_best_params"]

    construction, holdout, recon = reconstruct_rows()
    specs = baselines.registry()

    predictions: Dict[str, List[float]] = {}
    excluded_forbidden_axis: Dict[str, str] = {}
    for spec in specs:
        try:
            baselines.assert_fit_allowed(spec, axis=PRIMARY_AXIS)
        except baselines.LeakageError as exc:
            excluded_forbidden_axis[spec.id] = str(exc)
            continue
        params = dict(frozen_params[spec.id])
        model = spec.build(params)
        X_constr = baselines.extract_features(construction, spec.schema)
        y_constr = baselines.extract_labels(construction)
        model.fit(X_constr, y_constr)
        schema = common.FEATURE_SCHEMAS.get(spec.schema.name, spec.schema)
        X_hold = baselines.extract_features(holdout, schema)
        p = np.asarray(model.predict_proba(X_hold)[:, 1], dtype=np.float64)
        predictions[spec.id] = [_round12(v) for v in p.tolist()]

    y_hold = baselines.extract_labels(holdout)
    groups = [str(r["sequence_id"]) for r in holdout]
    years = [r["origin_year"] for r in holdout]
    regions = [r["region_code"] for r in holdout]
    cdi = [float(r["max_cdi"]) for r in holdout]

    predictions_digest = common.sha256_text(common.canonical_json(predictions))

    return {
        "predictions": predictions,
        "excluded_forbidden_axis": excluded_forbidden_axis,
        "y_hold": y_hold,
        "groups": groups,
        "years": years,
        "regions": regions,
        "cdi": cdi,
        "construction": construction,
        "holdout": holdout,
        "recon": recon,
        "predictions_digest": predictions_digest,
        "recorded_predictions_digest": core["predictions_digest"],
        "frozen_best_params": frozen_params,
    }


def verify_reconstruction(recon_pred: Dict[str, object]) -> Dict[str, object]:
    """Assert the reconstruction reproduces recorded protected numbers exactly.

    Checks (a) predictions_digest, (b) reconstruction_pipeline_digest,
    (c) every recorded per-baseline Brier / AUROC / log-loss / calibration /
    confusion value, (d) every recorded ``ranking_vs_reference`` entry, all to the
    12-dp released precision. Returns a structured verification record; the caller
    fails closed if ``all_match`` is False.
    """
    run = load_run_result()
    core = run["result_core"]
    report = core["report"]["evaluation"]

    checks: List[Dict[str, object]] = []

    def _chk(name, recomputed, recorded, tol=0.0):
        if isinstance(recomputed, (int, float)) and isinstance(recorded, (int, float)):
            ok = abs(float(recomputed) - float(recorded)) <= tol
        else:
            ok = recomputed == recorded
        checks.append(
            {"check": name, "recomputed": recomputed, "recorded": recorded, "match": bool(ok)}
        )
        return ok

    # (a) predictions digest -- the decisive bit-identity check.
    _chk(
        "predictions_digest",
        recon_pred["predictions_digest"],
        recon_pred["recorded_predictions_digest"],
    )
    _chk(
        "predictions_digest_equals_bit_identity",
        1 if recon_pred["predictions_digest"] == recon_pred["recorded_predictions_digest"] else 0,
        1,
    )

    # (b) reconstruction pipeline digest.
    _chk(
        "reconstruction_pipeline_digest",
        recon_pred["recon"].pipeline_digest,
        core["reconstruction_pipeline_digest"],
    )

    # (c) recompute the per-baseline evaluation surface from reconstructed preds.
    y = np.asarray(recon_pred["y_hold"], dtype=np.float64)
    groups = recon_pred["groups"]
    preds = recon_pred["predictions"]
    for bid in sorted(preds):
        p = np.asarray(preds[bid], dtype=np.float64)
        summ = metrics.summary(
            y, p, groups=groups, threshold=DEV_THRESHOLD,
            n_boot=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED,
        )
        rec = report["per_baseline"][bid]
        _chk(f"{bid}.brier", _round12(summ["brier"]["value"]), rec["brier"])
        _chk(f"{bid}.log_loss", _round12(summ["log_loss"]["value"]), rec["log_loss"])
        auroc_val = (
            _round12(summ["auroc"]["value"]) if summ["auroc"]["status"] == metrics.OK else summ["auroc"]["status"]
        )
        _chk(f"{bid}.auroc", auroc_val, rec["auroc"])
        _chk(f"{bid}.calibration_status", summ["calibration"]["status"], rec["calibration_status"])
        _chk(f"{bid}.calibration_slope", _round12(summ["calibration"].get("slope")), rec["calibration_slope"])
        _chk(f"{bid}.calibration_intercept", _round12(summ["calibration"].get("intercept")), rec["calibration_intercept"])
        boot = summ["brier_cluster_bootstrap"]
        _chk(f"{bid}.brier_ci_lower", _round12(boot.get("ci_lower")), rec["brier_ci"][0])
        _chk(f"{bid}.brier_ci_upper", _round12(boot.get("ci_upper")), rec["brier_ci"][1])
        conf = summ["classification_at_threshold"]
        for k in ("tp", "fp", "tn", "fn"):
            _chk(f"{bid}.confusion.{k}", conf.get(k), rec["confusion_at_threshold"][k])

    # (d) recompute ranking_vs_reference exactly.
    ref = report["ranking_reference"]
    pb = np.asarray(preds[ref], dtype=np.float64)
    for cand in sorted(preds):
        if cand == ref:
            continue
        pa = np.asarray(preds[cand], dtype=np.float64)
        res = metrics.paired_cluster_bootstrap_difference(
            y, pa, pb, groups, metric="brier", n_boot=BOOTSTRAP_DRAWS,
            seed=BOOTSTRAP_SEED, resolution_floor=RESOLUTION_FLOOR,
        )
        rec = report["ranking_vs_reference"][f"{cand}_vs_{ref}"]
        _chk(f"rank[{cand}_vs_{ref}].point", _round12(res.get("point_diff_a_minus_b")), rec["point_diff_a_minus_b"])
        _chk(f"rank[{cand}_vs_{ref}].ci_lo", _round12(res.get("ci_lower")), rec["ci"][0])
        _chk(f"rank[{cand}_vs_{ref}].ci_hi", _round12(res.get("ci_upper")), rec["ci"][1])
        _chk(f"rank[{cand}_vs_{ref}].prob_a_better", _round12(res.get("prob_a_better")), rec["prob_a_better"])
        _chk(f"rank[{cand}_vs_{ref}].prob_tie", _round12(res.get("prob_tie")), rec["prob_tie"])
        _chk(f"rank[{cand}_vs_{ref}].resolved", res.get("resolved"), rec["resolved"])

    all_match = all(c["match"] for c in checks)
    return {
        "all_match": all_match,
        "n_checks": len(checks),
        "n_failed": sum(1 for c in checks if not c["match"]),
        "checks": checks,
    }


def write_json_sorted(path: str, obj) -> str:
    """Write canonical, sorted, newline-terminated JSON; return its sha256."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
    return sha256_file(path)


def write_text(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return sha256_file(path)
