"""Resource reporting for the DYFI-USGS single-source severe-felt-intensity
benchmark: the leakage-inflation headline plus the honest evaluation surface.

The HEADLINE output is the leakage-inflation gap: the SAME fixed probe baseline is
cross-validated under three fold definitions --

  * random-event split   : folds assigned per event at random (sequence-mates leak
                            across folds);
  * event-grouped split  : folds keyed by event id (no single event split; on a
                            one-row-per-event table this coincides with the random
                            split and is reported as the intermediate control);
  * sequence-grouped split: folds keyed by seismic sequence (whole aftershock
                            sequences held out -- the leakage-hardened, honest
                            estimate).

-- and the apparent-skill inflation from the honest sequence-grouped estimate to
the leaky random split is reported as the resource's central quantity. No model is
declared a winner anywhere in this module.

Everything operates on already-reconstructed rows (SYNTHETIC in this stage). No
acquisition, no protected-cohort opening, no real outcome.
"""
from __future__ import annotations

from typing import Dict, Sequence

import numpy as np

import baselines
import metrics
import role_assignment

# The fixed difficulty probe: a single, untuned source-only logistic (C=1.0). It
# is deliberately NOT selected to win; it characterises benchmark difficulty and
# isolates the split effect from any tuning.
PROBE_BASELINE_ID = "B2_source_only_logit"
PROBE_PARAMS = {"C": 1.0}
NO_SKILL_BASELINE_ID = "B0_no_skill"
DEFAULT_N_FOLDS = role_assignment.N_CV_FOLDS
DEFAULT_SEED = 20260901

# The leakage probe is a FLEXIBLE, fully-grown source-only random forest. A smooth
# logistic cannot memorise a feature neighbourhood, so it under-reports split
# leakage; a fully-grown forest can, making it the honest instrument for measuring
# the random-vs-grouped inflation. Its parameters are fixed (no selection).
LEAKAGE_PROBE_BASELINE_ID = "B4_random_forest"
LEAKAGE_PROBE_PARAMS = {"n_estimators": 300, "max_depth": None}


def _round(x, nd: int = 12):
    return None if x is None else round(float(x), nd)


def _probe_spec():
    return next(s for s in baselines.registry() if s.id == PROBE_BASELINE_ID)


def _leakage_probe_spec():
    return next(s for s in baselines.registry() if s.id == LEAKAGE_PROBE_BASELINE_ID)


def _random_folds(n: int, n_folds: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, n_folds, size=n).astype(int)


def _key_folds(keys: Sequence[object], n_folds: int) -> np.ndarray:
    rows = [{"sequence_id": str(k)} for k in keys]
    fold_of = role_assignment.grouped_cv_folds(rows, n_folds=n_folds)
    return np.asarray([fold_of[str(k)] for k in keys], dtype=int)


def _oof_predictions(
    X: np.ndarray, y: np.ndarray, fold: np.ndarray, build, params: Dict[str, object]
) -> np.ndarray:
    """Deterministic out-of-fold probabilities under a given fold vector.

    A one-class train fold falls back to that fold's train prevalence (a proper
    constant), so a degenerate split never raises; this keeps the three schemes
    comparable on identical data.
    """
    p_oof = np.full(y.shape[0], np.nan, dtype=np.float64)
    for k in sorted(set(fold.tolist())):
        tr = fold != k
        te = fold == k
        if te.sum() == 0 or tr.sum() == 0:
            continue
        if np.unique(y[tr]).size < 2:
            p_oof[te] = float(np.mean(y[tr]))
            continue
        model = build(dict(params))
        model.fit(X[tr], y[tr])
        p_oof[te] = model.predict_proba(X[te])[:, 1]
    # any remaining NaN (isolated fold) -> global prevalence fallback
    if np.any(np.isnan(p_oof)):
        p_oof[np.isnan(p_oof)] = float(np.mean(y))
    return p_oof


def leakage_inflation_analysis(
    rows: Sequence[Dict[str, object]],
    n_folds: int = DEFAULT_N_FOLDS,
    seed: int = DEFAULT_SEED,
) -> Dict[str, object]:
    """Compare fixed-probe OOF skill under random / event / sequence grouping.

    Returns per-scheme Brier + AUROC on pooled OOF predictions and the inflation
    gaps (honest sequence-grouped -> leaky random). Positive Brier inflation and
    positive AUROC inflation both indicate optimistic leakage under the naive
    split.
    """
    spec = _leakage_probe_spec()
    X = baselines.extract_features(rows, spec.schema)
    y = baselines.extract_labels(rows)
    event_ids = [str(r["event_id"]) for r in rows]
    seq_ids = [str(r["sequence_id"]) for r in rows]

    schemes = {
        "random_event": _random_folds(len(rows), n_folds, seed),
        "event_grouped": _key_folds(event_ids, n_folds),
        "sequence_grouped": _key_folds(seq_ids, n_folds),
    }
    per_scheme: Dict[str, object] = {}
    for name, fold in schemes.items():
        p = _oof_predictions(X, y, fold, spec.build, LEAKAGE_PROBE_PARAMS)
        brier = metrics.brier_score(y, p)
        auc = metrics.auroc(y, p)
        ll = metrics.log_loss(y, p)
        per_scheme[name] = {
            "brier": _round(brier.value) if brier.status == metrics.OK else brier.status,
            "auroc": _round(auc.value) if auc.status == metrics.OK else auc.status,
            "log_loss": _round(ll.value) if ll.status == metrics.OK else ll.status,
            "n_folds_populated": int(len(set(fold.tolist()))),
        }

    def _val(scheme, m):
        v = per_scheme[scheme][m]
        return v if isinstance(v, float) else None

    br_seq, br_rand = _val("sequence_grouped", "brier"), _val("random_event", "brier")
    au_seq, au_rand = _val("sequence_grouped", "auroc"), _val("random_event", "auroc")
    return {
        "probe_baseline": LEAKAGE_PROBE_BASELINE_ID,
        "probe_params": LEAKAGE_PROBE_PARAMS,
        "n_folds": n_folds,
        "seed": seed,
        "per_scheme": per_scheme,
        "honest_estimate_scheme": "sequence_grouped",
        "brier_inflation_seq_minus_random": (
            _round(br_seq - br_rand) if (br_seq is not None and br_rand is not None) else None
        ),
        "auroc_inflation_random_minus_seq": (
            _round(au_rand - au_seq) if (au_rand is not None and au_seq is not None) else None
        ),
        "interpretation": (
            "Random-event splitting lets within-sequence signal leak across folds; "
            "the sequence-grouped split is the honest, leakage-hardened estimate. "
            "A positive Brier gap (sequence minus random) and positive AUROC gap "
            "(random minus sequence) quantify the optimistic inflation of the naive "
            "split. This is the resource's headline; no model is claimed to win."
        ),
        "event_grouped_note": (
            "On a one-row-per-event table event-grouped coincides with the random "
            "split; it is reported as the intermediate control between random and "
            "sequence grouping."
        ),
    }


def difficulty_characterization(
    rows: Sequence[Dict[str, object]],
    n_folds: int = DEFAULT_N_FOLDS,
    seed: int = DEFAULT_SEED,
) -> Dict[str, object]:
    """Fixed-baseline difficulty of the benchmark under the honest split.

    Reports prevalence, the no-skill Brier floor, the fixed probe's honest
    (sequence-grouped) OOF Brier/AUROC, and near-threshold class balance. Uses
    fixed baselines only; performs no selection.
    """
    spec = _probe_spec()
    X = baselines.extract_features(rows, spec.schema)
    y = baselines.extract_labels(rows)
    seq_ids = [str(r["sequence_id"]) for r in rows]
    fold = _key_folds(seq_ids, n_folds)
    p = _oof_predictions(X, y, fold, spec.build, PROBE_PARAMS)

    prevalence = float(np.mean(y)) if y.size else None
    no_skill_brier = (
        metrics.brier_score(y, np.full_like(y, prevalence)).value
        if prevalence is not None else None
    )
    cdis = [float(r["max_cdi"]) for r in rows if "max_cdi" in r]
    near = sum(1 for c in cdis if abs(c - 6.0) < 0.5)
    probe_brier = metrics.brier_score(y, p)
    probe_auc = metrics.auroc(y, p)
    return {
        "n_events": int(y.size),
        "n_sequences": len({s for s in seq_ids}),
        "prevalence_severe": _round(prevalence),
        "n_positive": int(np.sum(y == 1.0)),
        "n_negative": int(np.sum(y == 0.0)),
        "no_skill_brier_floor": _round(no_skill_brier),
        "fixed_probe_honest_brier": _round(probe_brier.value) if probe_brier.status == metrics.OK else probe_brier.status,
        "fixed_probe_honest_auroc": _round(probe_auc.value) if probe_auc.status == metrics.OK else probe_auc.status,
        "near_threshold_fraction": _round(near / len(cdis)) if cdis else None,
        "probe_baseline": PROBE_BASELINE_ID,
        "split": "sequence_grouped",
    }


def assemble_evaluation_report(
    y_eval,
    predictions_by_baseline: Dict[str, Sequence[float]],
    groups: Sequence[object],
    years: Sequence[object],
    regions: Sequence[object],
    cdi_values: Sequence[float],
    ranking_reference: str = NO_SKILL_BASELINE_ID,
    threshold: float = 0.5,
    n_boot: int = 2000,
    seed: int = DEFAULT_SEED,
) -> Dict[str, object]:
    """Assemble the honest per-baseline evaluation surface (no winner claim).

    Calibration + proper scores, sequence-cluster bootstrap CIs, paired ranking vs
    a stated reference with explicit tie/resolution/INFEASIBLE states, endpoint
    threshold sensitivity, and temporal/geographic slices. Every degenerate case
    is surfaced by its metric status, never fabricated.
    """
    y = np.asarray(y_eval, dtype=np.float64)
    per_baseline: Dict[str, object] = {}
    for bid in sorted(predictions_by_baseline):
        p = np.asarray(predictions_by_baseline[bid], dtype=np.float64)
        summ = metrics.summary(y, p, groups=groups, threshold=threshold,
                               n_boot=n_boot, seed=seed)
        boot = summ["brier_cluster_bootstrap"]
        per_baseline[bid] = {
            "brier": _round(summ["brier"]["value"]),
            "brier_status": summ["brier"]["status"],
            "log_loss": _round(summ["log_loss"]["value"]),
            "auroc": _round(summ["auroc"]["value"]) if summ["auroc"]["status"] == metrics.OK else summ["auroc"]["status"],
            "calibration_status": summ["calibration"]["status"],
            "calibration_slope": _round(summ["calibration"].get("slope")),
            "calibration_intercept": _round(summ["calibration"].get("intercept")),
            "brier_ci": [_round(boot.get("ci_lower")), _round(boot.get("ci_upper"))],
            "bootstrap_status": boot["status"],
            "bootstrap_n_valid": boot.get("n_valid"),
            "confusion_at_threshold": {
                k: summ["classification_at_threshold"].get(k)
                for k in ("tp", "fp", "tn", "fn", "precision", "recall", "f1", "accuracy")
            },
        }

    ranking: Dict[str, object] = {}
    if ranking_reference in predictions_by_baseline:
        pb = np.asarray(predictions_by_baseline[ranking_reference], dtype=np.float64)
        for cand in sorted(predictions_by_baseline):
            if cand == ranking_reference:
                continue
            pa = np.asarray(predictions_by_baseline[cand], dtype=np.float64)
            res = metrics.paired_cluster_bootstrap_difference(
                y, pa, pb, groups, metric="brier", n_boot=n_boot, seed=seed,
                resolution_floor=0.0,
            )
            ranking[f"{cand}_vs_{ranking_reference}"] = {
                "status": res["status"],
                "point_diff_a_minus_b": _round(res.get("point_diff_a_minus_b")),
                "ci": [_round(res.get("ci_lower")), _round(res.get("ci_upper"))],
                "prob_a_better": _round(res.get("prob_a_better")),
                "prob_b_better": _round(res.get("prob_b_better")),
                "prob_tie": _round(res.get("prob_tie")),
                "resolved": res.get("resolved"),
            }

    # Temporal / geographic slices + endpoint-threshold sensitivity on the probe.
    probe_id = PROBE_BASELINE_ID if PROBE_BASELINE_ID in predictions_by_baseline else sorted(predictions_by_baseline)[0]
    p_probe = np.asarray(predictions_by_baseline[probe_id], dtype=np.float64)
    tslice = metrics.slice_metrics(y, p_probe, years, metrics=("brier", "auroc"))
    gslice = metrics.slice_metrics(y, p_probe, regions, metrics=("brier",))
    tsens = metrics.threshold_sensitivity(cdi_values, p_probe, thresholds=(5.5, 6.0, 6.5))

    def _round_slice(d, with_auroc=False):
        out = {}
        for k, v in d.items():
            entry = {"n": v["n"],
                     "brier": _round(v.get("brier", {}).get("value")),
                     "brier_status": v.get("brier", {}).get("status")}
            if with_auroc and "auroc" in v:
                entry["auroc"] = (_round(v["auroc"].get("value"))
                                  if v["auroc"].get("status") == metrics.OK else v["auroc"].get("status"))
            out[str(k)] = entry
        return out

    def _round_tsens(d):
        return {k: {"prevalence": _round(v.get("prevalence")),
                    "brier": _round(v.get("brier", {}).get("value")),
                    "auroc": (_round(v.get("auroc", {}).get("value"))
                              if v.get("auroc", {}).get("status") == metrics.OK else v.get("auroc", {}).get("status"))}
                for k, v in d.items()}

    return {
        "no_winning_model_claim": True,
        "claim_statement": (
            "This resource characterises benchmark difficulty and the leakage "
            "inflation of naive splitting. It ranks baselines with paired "
            "uncertainty and explicit tie/INFEASIBLE states but declares NO "
            "winning model; the source-only baselines are honest comparators."
        ),
        "ranking_reference": ranking_reference,
        "threshold": threshold,
        "per_baseline": per_baseline,
        "ranking_vs_reference": ranking,
        "temporal_slice": _round_slice(tslice, with_auroc=True),
        "geographic_slice": _round_slice(gslice),
        "threshold_sensitivity": _round_tsens(tsens),
        "slice_probe_baseline": probe_id,
    }


def full_report(
    construction_rows: Sequence[Dict[str, object]],
    eval_rows: Sequence[Dict[str, object]],
    predictions_by_baseline: Dict[str, Sequence[float]],
    n_boot: int = 2000,
    seed: int = DEFAULT_SEED,
    data_label: str = "SYNTHETIC_ONLY",
    protected_role_opened: bool = False,
) -> Dict[str, object]:
    """Bundle the leakage-inflation headline, difficulty, and evaluation surface.

    ``data_label`` / ``protected_role_opened`` describe the provenance of the rows
    being reported; they default to the synthetic-stage values so the synthetic
    path is byte-identical, and are set by the caller for the real protected run.
    """
    y_eval = baselines.extract_labels(eval_rows)
    groups = [str(r["sequence_id"]) for r in eval_rows]
    years = [r["origin_year"] for r in eval_rows]
    regions = [r["region_code"] for r in eval_rows]
    cdi = [float(r["max_cdi"]) for r in eval_rows]
    return {
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "data": data_label,
        "protected_role_opened": protected_role_opened,
        "leakage_inflation_headline": leakage_inflation_analysis(construction_rows, seed=seed),
        "difficulty_characterization": difficulty_characterization(construction_rows, seed=seed),
        "evaluation": assemble_evaluation_report(
            y_eval, predictions_by_baseline, groups, years, regions, cdi,
            n_boot=n_boot, seed=seed,
        ),
    }
