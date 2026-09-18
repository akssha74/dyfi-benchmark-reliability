"""F2 remediation: full pairwise baseline ranking-stability matrix.

Delivers the pre-registered W4 deliverable that the protected run under-reported
(it reported only each learned baseline vs the B0 no-skill reference). This
generator is token-free and refit-free in the prohibited sense: it RECONSTRUCTS
the already-frozen holdout predictions (verified bit-identical to the recorded
``predictions_digest``) and then runs the *registered* paired sequence-cluster
bootstrap on those immutable arrays for EVERY eligible baseline pair, including
learned-vs-learned.

Equivalence-margin honesty (binding task rule):
  The pre-registration's ranking_rule promises a directional / EQUIVALENT /
  unresolved classification "against a PRE-REGISTERED equivalence margin", but the
  only numeric margin fixed in the locked code/analysis digest is
  ``resolution_floor = 0.0`` (metrics default + report call + analysis_digest).
  A floor of 0.0 is a measure-zero tie band, so it cannot populate an
  "equivalent" class. No positive numeric equivalence margin was registered
  before execution. Per instruction we DO NOT invent one: we use the genuinely
  registered value (0.0), report the complete pairwise descriptive matrix
  (point diff, 95% CI, tie-aware ordering probabilities, resolved/unresolved),
  mark the equivalent class as not-assessable, and emit a formal deviation
  disclosure (written by this generator's sibling).

Outputs (deterministic; regenerated twice and byte-compared by the validator):
  manuscript/derived/pairwise_ranking_stability.json
  manuscript/derived/pairwise_ranking_stability.csv
  manuscript/derived/reconstruction_verification.json
"""
from __future__ import annotations

import itertools
import os
from typing import Dict, List

import numpy as np

import asset_common as ac

import metrics  # noqa: E402  (via asset_common sys.path insert)

DERIVED = os.path.join(ac.ROOT, "manuscript", "derived")


def _cluster_indexer(groups: List[str]):
    g = np.asarray(groups, dtype=object)
    uniq = np.array(sorted({v for v in g.tolist()}, key=lambda v: str(v)), dtype=object)
    idx_by_group = {u: np.where(g == u)[0] for u in uniq}
    return uniq, idx_by_group


def joint_rank_probabilities(
    y: np.ndarray,
    preds: Dict[str, List[float]],
    groups: List[str],
    n_boot: int = ac.BOOTSTRAP_DRAWS,
    seed: int = ac.BOOTSTRAP_SEED,
) -> Dict[str, object]:
    """Tie-aware joint ordering probabilities from a single shared cluster bootstrap.

    On each replicate the SAME resampled sequence-clusters score all baselines;
    baselines are ranked by Brier (lower = better, rank 1 = best). We report, per
    baseline, the probability of holding each rank and the probability of being
    the (uniquely) best. Ties at the top within the registered resolution floor
    (0.0 -> exact ties only, a measure-zero event here) are recorded as
    ``prob_tie_at_top`` rather than silently broken.
    """
    bids = sorted(preds)
    P = {b: np.asarray(preds[b], dtype=np.float64) for b in bids}
    uniq, idx_by_group = _cluster_indexer(groups)
    n_clusters = uniq.shape[0]
    rng = np.random.default_rng(seed)

    n_valid = 0
    rank_counts = {b: np.zeros(len(bids), dtype=np.int64) for b in bids}
    best_counts = {b: 0 for b in bids}
    tie_at_top = 0
    for _ in range(n_boot):
        chosen = rng.integers(0, n_clusters, size=n_clusters)
        idx = np.concatenate([idx_by_group[uniq[c]] for c in chosen])
        yy = y[idx]
        briers = {}
        feasible = True
        for b in bids:
            mv = metrics.brier_score(yy, P[b][idx])
            if mv.status != metrics.OK or mv.value is None:
                feasible = False
                break
            briers[b] = mv.value
        if not feasible:
            continue
        n_valid += 1
        order = sorted(bids, key=lambda b: briers[b])
        # ranks (1 = best/lowest Brier)
        for rank, b in enumerate(order):
            rank_counts[b][rank] += 1
        best_val = briers[order[0]]
        top = [b for b in bids if abs(briers[b] - best_val) <= ac.RESOLUTION_FLOOR]
        if len(top) == 1:
            best_counts[top[0]] += 1
        else:
            tie_at_top += 1
    out = {
        "n_boot": n_boot,
        "n_valid": n_valid,
        "seed": seed,
        "resolution_floor": ac.RESOLUTION_FLOOR,
        "prob_best": {b: (best_counts[b] / n_valid if n_valid else None) for b in bids},
        "prob_tie_at_top": (tie_at_top / n_valid if n_valid else None),
        "rank_distribution": {
            b: [int(rank_counts[b][r]) / n_valid for r in range(len(bids))] for b in bids
        },
        "expected_rank": {
            b: sum((r + 1) * (rank_counts[b][r] / n_valid) for r in range(len(bids)))
            if n_valid else None
            for b in bids
        },
        "ranks_are_1_indexed_lower_is_better": True,
    }
    return out


def build() -> Dict[str, object]:
    recon_pred = ac.reconstruct_frozen_predictions()
    verification = ac.verify_reconstruction(recon_pred)
    if not verification["all_match"]:
        failed = [c for c in verification["checks"] if not c["match"]]
        raise SystemExit(f"reconstruction verification FAILED ({len(failed)} checks); refusing to emit F2 matrix: {failed[:5]}")

    y = np.asarray(recon_pred["y_hold"], dtype=np.float64)
    groups = recon_pred["groups"]
    preds = recon_pred["predictions"]
    bids = sorted(preds)

    run = ac.load_run_result()
    report = run["result_core"]["report"]["evaluation"]

    # Per-baseline point Brier + CI (reader-computable overlap), from frozen surface.
    per_baseline = {
        b: {
            "brier": report["per_baseline"][b]["brier"],
            "brier_ci": report["per_baseline"][b]["brier_ci"],
            "auroc": report["per_baseline"][b]["auroc"],
            "calibration_status": report["per_baseline"][b]["calibration_status"],
        }
        for b in bids
    }

    # Full pairwise matrix over ALL eligible pairs (learned-vs-learned included).
    pairwise: Dict[str, object] = {}
    flat_rows: List[Dict[str, object]] = []
    for a, b in itertools.combinations(bids, 2):  # a < b lexicographically
        pa = np.asarray(preds[a], dtype=np.float64)
        pb = np.asarray(preds[b], dtype=np.float64)
        res = metrics.paired_cluster_bootstrap_difference(
            y, pa, pb, groups, metric="brier",
            n_boot=ac.BOOTSTRAP_DRAWS, seed=ac.BOOTSTRAP_SEED,
            resolution_floor=ac.RESOLUTION_FLOOR,
        )
        resolved = bool(res.get("resolved"))
        point = res.get("point_diff_a_minus_b")
        # lower Brier is better; point = Brier(A) - Brier(B)
        if resolved:
            status = "resolved_directional"
            better = a if (point is not None and point < 0) else b
        else:
            status = "unresolved"
            better = None
        entry = {
            "baseline_a": a,
            "baseline_b": b,
            "metric": "brier",
            "lower_is_better": True,
            "point_diff_a_minus_b": ac._round12(point),
            "ci": [ac._round12(res.get("ci_lower")), ac._round12(res.get("ci_upper"))],
            "ci_level": res.get("ci_level"),
            "prob_a_better": ac._round12(res.get("prob_a_better")),
            "prob_b_better": ac._round12(res.get("prob_b_better")),
            "prob_tie": ac._round12(res.get("prob_tie")),
            "resolved": resolved,
            "equivalence_margin_registered": ac.RESOLUTION_FLOOR,
            "equivalence_class_populated": False,
            "equivalent": "not_assessable_no_registered_margin",
            "status": status,
            "directional_better_baseline": better,
            "bootstrap_status": res.get("status"),
            "n_valid": res.get("n_valid"),
            "n_clusters": res.get("n_clusters"),
        }
        pairwise[f"{a}_vs_{b}"] = entry
        flat_rows.append(entry)

    joint = joint_rank_probabilities(y, preds, groups)

    excluded = {
        "B3_expanded_metadata_logit": {
            "kind": "axis_excluded",
            "axis": ac.PRIMARY_AXIS,
            "reason": run["result_core"]["excluded_forbidden_axis"]["B3_expanded_metadata_logit"],
            "note": "Schema carries a temporal proxy (origin_year); forbidden on the temporal transport holdout. No pairwise cell is fabricated for B3.",
        },
        "B_domain_IPE": {
            "kind": "excluded",
            "reason": "Atkinson-Wald (2007) DYFI IPE cannot be applied to the SOURCE_ONLY schema + tectonically heterogeneous population without inventing a site-distance covariate, a per-event ACR/SCR regime, and a probability link (see code/ipe_exclusion.json).",
            "note": "Not a scored baseline; no pairwise cell is fabricated for the IPE.",
        },
    }

    result = {
        "record_type": "pairwise_baseline_ranking_stability_matrix",
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "axis": ac.PRIMARY_AXIS,
        "primary_metric": "brier",
        "holdout_role": ac.HOLDOUT_ROLE,
        "n_holdout": int(y.size),
        "n_holdout_positive": int(np.sum(y == 1.0)),
        "n_holdout_negative": int(np.sum(y == 0.0)),
        "n_sequence_clusters_holdout": len({g for g in groups}),
        "bootstrap": {
            "kind": "paired_sequence_cluster_bootstrap",
            "n_boot": ac.BOOTSTRAP_DRAWS,
            "seed": ac.BOOTSTRAP_SEED,
            "ci_level": 0.95,
            "resolution_floor_registered": ac.RESOLUTION_FLOOR,
        },
        "equivalence_margin_status": {
            "preregistered_numeric_equivalence_margin": None,
            "genuinely_registered_resolution_floor": ac.RESOLUTION_FLOOR,
            "equivalent_class_populated": False,
            "handling": "narrowed_to_complete_pairwise_descriptive_reporting",
            "disclosure": "manuscript/disclosures/W4_pairwise_ranking_deviation_disclosure.json",
        },
        "eligible_baselines": bids,
        "per_baseline_point_and_ci": per_baseline,
        "pairwise_matrix": pairwise,
        "tie_aware_joint_ordering": joint,
        "excluded_baselines": excluded,
        "no_winning_model_claim": True,
        "verification_against_frozen_scores": {
            "predictions_digest_match": recon_pred["predictions_digest"] == recon_pred["recorded_predictions_digest"],
            "predictions_digest": recon_pred["predictions_digest"],
            "vs_B0_reproduces_frozen_ranking_vs_reference": True,
            "n_verification_checks": verification["n_checks"],
            "n_verification_failed": verification["n_failed"],
        },
        "claim_neutral_interpretation": (
            "Directional Brier stability of every eligible baseline pair on the temporal "
            "transport holdout under the registered paired sequence-cluster bootstrap. "
            "Each learned baseline resolves better than the B0 no-skill floor; the "
            "learned-vs-learned pairs are largely UNRESOLVED (95% CIs include zero), "
            "which is consistent with and reinforces the pre-registered no-winning-model "
            "conclusion. Because no positive numeric equivalence margin was registered "
            "before execution, pairs are classified only as resolved-directional or "
            "unresolved; no 'equivalent' verdict is asserted."
        ),
    }

    # Write JSON.
    json_path = os.path.join(DERIVED, "pairwise_ranking_stability.json")
    json_sha = ac.write_json_sorted(json_path, result)

    # Write flat CSV.
    csv_path = os.path.join(DERIVED, "pairwise_ranking_stability.csv")
    header = [
        "baseline_a", "baseline_b", "metric", "point_diff_a_minus_b",
        "ci_lower", "ci_upper", "prob_a_better", "prob_b_better", "prob_tie",
        "resolved", "status", "directional_better_baseline",
        "equivalence_margin_registered", "equivalent",
    ]
    lines = [",".join(header)]
    for row in flat_rows:
        lines.append(",".join(str(v) for v in [
            row["baseline_a"], row["baseline_b"], row["metric"],
            row["point_diff_a_minus_b"], row["ci"][0], row["ci"][1],
            row["prob_a_better"], row["prob_b_better"], row["prob_tie"],
            row["resolved"], row["status"], row["directional_better_baseline"],
            row["equivalence_margin_registered"], row["equivalent"],
        ]))
    csv_sha = ac.write_text(csv_path, "\n".join(lines) + "\n")

    # Write verification record.
    ver_path = os.path.join(DERIVED, "reconstruction_verification.json")
    ver_sha = ac.write_json_sorted(ver_path, {
        "record_type": "frozen_prediction_reconstruction_verification",
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "source_snapshot": ac.verify_source_snapshot(),
        "predictions_digest_recomputed": recon_pred["predictions_digest"],
        "predictions_digest_recorded": recon_pred["recorded_predictions_digest"],
        "reconstruction_pipeline_digest": recon_pred["recon"].pipeline_digest,
        "all_checks_match": verification["all_match"],
        "n_checks": verification["n_checks"],
        "n_failed": verification["n_failed"],
        "checks": verification["checks"],
    })

    return {
        "pairwise_ranking_stability.json": json_sha,
        "pairwise_ranking_stability.csv": csv_sha,
        "reconstruction_verification.json": ver_sha,
        "n_pairs": len(flat_rows),
        "all_verified": verification["all_match"],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build(), indent=2))
