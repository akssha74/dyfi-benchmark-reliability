"""Full-forward SYNTHETIC smoke test for the DYFI benchmark analytics stack
(construction step 10, execution-validity only).

It exercises the entire construction-side forward path in the pinned environment:

    verify env -> synthetic corpus -> leakage audit -> grouped-CV tune+fit
      -> predict -> joblib serialize -> reload -> metrics -> cluster bootstrap

on SYNTHETIC data ONLY. It NEVER reads real USGS data, fits on real outcomes, or
opens the protected held-out role. The pipeline is run TWICE and the two
canonical result hashes must match, proving deterministic reproducibility. It
also (re)writes env_lock.json and smoke_report.json and prints the output hashes.

Run:  python smoke_test.py
Exit code 0 iff the environment verifies, both runs succeed, and their hashes are
bit-identical.
"""
from __future__ import annotations

import io
import os
import sys
from typing import Dict, List

import joblib
import numpy as np

import baselines
import common
import environment
import metrics
import synthetic_fixtures as fx

DEV_THRESHOLD = 0.5          # protocol-fixed; no threshold-selection procedure
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20260901
HERE = os.path.dirname(os.path.abspath(__file__))


def _round(x, nd=12):
    return None if x is None else round(float(x), nd)


def run_pipeline(train_seed: int = 1, eval_seed: int = 2) -> Dict[str, object]:
    """One full deterministic forward pass; returns the hashable result core."""
    train_rows = fx.make_event_table(n_events=240, n_sequences=60, seed=train_seed)
    eval_rows = fx.make_event_table(n_events=180, n_sequences=45, seed=eval_seed)
    train_groups = fx.groups_of(train_rows)
    eval_groups = fx.groups_of(eval_rows)
    eval_cdi = [r["max_cdi"] for r in eval_rows]
    eval_years = [r["origin_year"] for r in eval_rows]
    eval_regions = [r["region_code"] for r in eval_rows]
    y_eval = fx.labels_of(eval_rows)

    ledger = baselines.FitLedger()
    per_baseline: Dict[str, object] = {}
    predictions: Dict[str, List[float]] = {}

    for spec in baselines.registry():
        fitted = baselines.tune_and_fit(spec, train_rows, train_groups, ledger)

        # serialize -> reload, then predict from the RELOADED model (round-trip).
        buf = io.BytesIO()
        joblib.dump(fitted["model"], buf)
        buf.seek(0)
        reloaded = joblib.load(buf)
        X_eval = baselines.extract_features(eval_rows, spec.schema)
        p_from_reload = np.asarray(reloaded.predict_proba(X_eval)[:, 1], dtype=np.float64)
        p_direct = baselines.predict_proba(fitted, eval_rows)
        serialize_stable = bool(np.array_equal(p_from_reload, p_direct))
        p = p_from_reload

        summ = metrics.summary(
            y_eval, p, groups=eval_groups, threshold=DEV_THRESHOLD,
            n_boot=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED,
        )
        # Round the floaty metric surface for a stable cross-run hash.
        per_baseline[spec.id] = {
            "name": spec.name,
            "schema": spec.schema.name,
            "features": list(spec.schema.features),
            "best_params": fitted["best_params"],
            "serialize_roundtrip_identical": serialize_stable,
            "n_eval": int(y_eval.size),
            "brier": _round(summ["brier"]["value"]),
            "log_loss": _round(summ["log_loss"]["value"]),
            "auroc": (_round(summ["auroc"]["value"]) if summ["auroc"]["status"] == metrics.OK else summ["auroc"]["status"]),
            "calibration_status": summ["calibration"]["status"],
            "calibration_slope": _round(summ["calibration"].get("slope")),
            "calibration_intercept": _round(summ["calibration"].get("intercept")),
            "brier_ci": [
                _round(summ["brier_cluster_bootstrap"].get("ci_lower")),
                _round(summ["brier_cluster_bootstrap"].get("ci_upper")),
            ],
            "bootstrap_status": summ["brier_cluster_bootstrap"]["status"],
            "bootstrap_n_valid": summ["brier_cluster_bootstrap"].get("n_valid"),
        }
        predictions[spec.id] = [_round(v) for v in p.tolist()]

    # Paired ranking of the two strongest learned baselines vs the no-skill floor,
    # plus temporal/geographic slices and threshold sensitivity on the no-skill
    # reference (any predictor is fine for a smoke of the code paths).
    ref = "B0_no_skill"
    ranking: Dict[str, object] = {}
    for cand in [s.id for s in baselines.registry() if s.id != ref]:
        pa = np.asarray(predictions[cand], dtype=np.float64)
        pb = np.asarray(predictions[ref], dtype=np.float64)
        res = metrics.paired_cluster_bootstrap_difference(
            y_eval, pa, pb, eval_groups, metric="brier",
            n_boot=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED, resolution_floor=0.0,
        )
        ranking[f"{cand}_vs_{ref}"] = {
            "status": res["status"],
            "point_diff_a_minus_b": _round(res.get("point_diff_a_minus_b")),
            "ci": [_round(res.get("ci_lower")), _round(res.get("ci_upper"))],
            "prob_a_better": _round(res.get("prob_a_better")),
            "prob_tie": _round(res.get("prob_tie")),
            "resolved": res.get("resolved"),
        }

    example = [s.id for s in baselines.registry() if s.id != ref][0]
    p_example = np.asarray(predictions[example], dtype=np.float64)
    temporal_slice = metrics.slice_metrics(y_eval, p_example, eval_years, metrics=("brier",))
    geographic_slice = metrics.slice_metrics(y_eval, p_example, eval_regions, metrics=("brier",))
    thresh_sens = metrics.threshold_sensitivity(eval_cdi, p_example, thresholds=(5.5, 6.0, 6.5))

    def _round_slice(d):
        out = {}
        for k, v in d.items():
            b = v.get("brier", {})
            out[k] = {"n": v["n"], "brier_status": b.get("status"),
                      "brier": _round(b.get("value"))}
        return out

    def _round_ts(d):
        out = {}
        for k, v in d.items():
            b = v.get("brier", {})
            out[k] = {"prevalence": _round(v.get("prevalence")),
                      "brier": _round(b.get("value"))}
        return out

    core: Dict[str, object] = {
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "data": "SYNTHETIC_ONLY",
        "protected_role_opened": False,
        "dev_threshold": DEV_THRESHOLD,
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "fit_ledger_count": ledger.count,
        "fit_cap": baselines.TOTAL_FIT_CAP,
        "fit_ledger_digest": ledger.digest(),
        "baselines": per_baseline,
        "ranking_vs_no_skill": ranking,
        "temporal_slice_example_baseline": example,
        "temporal_slice": _round_slice(temporal_slice),
        "geographic_slice": _round_slice(geographic_slice),
        "threshold_sensitivity": _round_ts(thresh_sens),
        "predictions_digest": common.sha256_text(common.canonical_json(predictions)),
    }
    return core


def main() -> int:
    env_report = environment.verify_environment(strict=True)

    # Persist the machine-readable environment lock.
    common.write_json(os.path.join(HERE, "env_lock.json"), environment.lock_record())

    core1 = run_pipeline()
    core2 = run_pipeline()
    h1 = common.sha256_text(common.canonical_json(core1))
    h2 = common.sha256_text(common.canonical_json(core2))
    deterministic = h1 == h2

    report = {
        "environment": env_report,
        "deterministic_equal": deterministic,
        "run1_hash": h1,
        "run2_hash": h2,
        "result_core": core1,
        "xgboost_status": baselines.XGBOOST_STATUS,
    }
    out_path = os.path.join(HERE, "smoke_report.json")
    common.write_json(out_path, report)

    print("environment_passed:", env_report["passed"])
    print("xgboost_available:", baselines.XGBOOST_AVAILABLE)
    print("fit_ledger_count:", core1["fit_ledger_count"], "<= cap", core1["fit_cap"])
    print("run1_hash:", h1)
    print("run2_hash:", h2)
    print("deterministic_equal:", deterministic)
    print("smoke_report:", out_path)
    if not (env_report["passed"] and deterministic):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
