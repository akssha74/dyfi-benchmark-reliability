"""Consolidate every frozen number the manuscript tables/figures need into one
deterministic, verified ``asset_inputs.json``.

Runs in the pinned analytics venv. It (1) re-verifies that the reconstructed
holdout predictions reproduce the recorded protected scores bit-for-bit, then
(2) copies load-bearing values straight out of the immutable released artifacts
(run_result.json report surface, event_level_table.csv, the F2 pairwise matrix,
governance manifests) with light, fully-recomputed cohort-flow arithmetic. No new
scientific quantity is invented; the figures venv consumes only this file.
"""
from __future__ import annotations

import os
from collections import Counter
from typing import Dict, List

import numpy as np

import asset_common as ac

DERIVED = os.path.join(ac.ROOT, "manuscript", "derived")
OUT = os.path.join(DERIVED, "asset_inputs.json")


def _median(vals: List[float]):
    return float(np.median(np.asarray(vals, dtype=np.float64))) if vals else None


def build() -> Dict[str, object]:
    run = ac.load_run_result()
    core = run["result_core"]
    report = core["report"]
    ev = report["evaluation"]

    # --- verify reconstruction (fail closed) -----------------------------
    recon_pred = ac.reconstruct_frozen_predictions()
    verification = ac.verify_reconstruction(recon_pred)
    if not verification["all_match"]:
        raise SystemExit("asset_inputs refuses to build: reconstruction verification failed")

    # --- cohort flow (recomputed from immutable artifacts) ---------------
    geojson = ac.common.load_json(ac.RAW)
    n_fdsn_features = len(geojson.get("features", []))
    rows = ac.common.read_csv(ac.EVENT_TABLE)
    role_counts = Counter(r["role"] for r in rows)
    n_eligible = len(rows)
    n_train = role_counts.get("train", 0)
    n_dev = role_counts.get("development", 0)
    n_hold = role_counts.get("external_temporal_holdout", 0)
    n_straddle = n_eligible - (n_train + n_dev + n_hold)
    quarantine_ids = ac.R._manual_quarantine()
    present_q = [r["event_id"] for r in rows if r["event_id"] in set(quarantine_ids)]

    def _prev(sub):
        pos = sum(int(r["severe_label"]) for r in sub)
        return {"n": len(sub), "positive": pos, "negative": len(sub) - pos,
                "prevalence": (pos / len(sub) if sub else None)}

    constr_rows = [r for r in rows if r["role"] in ("train", "development")]
    hold_rows = [r for r in rows if r["role"] == "external_temporal_holdout"]
    train_rows = [r for r in rows if r["role"] == "train"]
    dev_rows = [r for r in rows if r["role"] == "development"]
    role_assigned_rows = [r for r in rows
                          if r["role"] in ("train", "development", "external_temporal_holdout")]
    straddle_rows = [r for r in rows
                     if r["role"] not in ("train", "development", "external_temporal_holdout")]
    # Severe among ALL eligible events (denominator = n_eligible), distinct from
    # the sum over analysis roles which excludes the temporal-straddle events. The
    # off-by-one (F1) is that one temporal-straddle-excluded event is severe.
    n_eligible_severe = sum(int(r["severe_label"]) for r in rows)

    n_seq_all = len({r["sequence_id"] for r in rows})
    n_seq_constr = len({r["sequence_id"] for r in constr_rows})
    n_seq_hold = len({r["sequence_id"] for r in hold_rows})

    # --- geographic slice summary (full list also carried) ---------------
    gslice = ev["geographic_slice"]
    g_briers = [v["brier"] for v in gslice.values() if v.get("brier") is not None]
    g_ns = [v["n"] for v in gslice.values()]

    # --- pairwise matrix (F2) --------------------------------------------
    pairwise = ac.common.load_json(os.path.join(DERIVED, "pairwise_ranking_stability.json"))

    # --- reproducibility manifest facts ----------------------------------
    consumed = ac.common.load_json(os.path.join(ac.CODE, "consumed_run_tokens.json"))
    f1 = ac.common.load_json(os.path.join(
        ac.ROOT, "manuscript", "disclosures", "F1_phase_f_self_reference_disclosure.json"))
    env_lock = ac.common.load_json(os.path.join(ac.CODE, "env_lock.json"))

    out = {
        "record_type": "manuscript_asset_inputs",
        "resource_id": core["resource_id"],
        "provenance": {
            "run_result": "results/protected_run_temporal/run_result.json",
            "result_hash": run["result_hash"],
            "source_snapshot_sha256": ac.SOURCE_SHA,
            "predictions_digest": recon_pred["predictions_digest"],
            "reconstruction_verified": verification["all_match"],
            "n_verification_checks": verification["n_checks"],
        },

        "cohort_flow": {
            "fdsn_features_pinned_snapshot": n_fdsn_features,
            "eligibility_rule": "num_responses >= 10 (eligibility only; forbidden as a feature)",
            "n_eligible_events": n_eligible,
            "n_eligible_severe": n_eligible_severe,
            "eligible_prevalence": (n_eligible_severe / n_eligible if n_eligible else None),
            "n_role_assigned": len(role_assigned_rows),
            "n_role_assigned_severe": sum(int(r["severe_label"]) for r in role_assigned_rows),
            "temporal_straddle": _prev(straddle_rows),
            "quarantine_inspected_ids": list(quarantine_ids),
            "quarantine_inspected_present_in_table": present_q,
            "temporal_straddle_excluded": n_straddle,
            "roles": {
                "train": _prev(train_rows),
                "development": _prev(dev_rows),
                "external_temporal_holdout": _prev(hold_rows),
            },
            "construction_total": _prev(constr_rows),
            "sequences": {
                "all_eligible": n_seq_all,
                "construction": n_seq_constr,
                "holdout": n_seq_hold,
            },
        },

        "endpoint": {
            "definition": "severe_label = 1[event-max maxCDI >= 6.0]",
            "primary_threshold": 6.0,
            "near_threshold_band": 0.5,
            "no_skill_brier_floor_construction": report["difficulty_characterization"]["no_skill_brier_floor"],
            "near_threshold_fraction_construction": report["difficulty_characterization"]["near_threshold_fraction"],
            "construction_prevalence": report["difficulty_characterization"]["prevalence_severe"],
            "holdout_prevalence": _prev(hold_rows)["prevalence"],
            "threshold_sensitivity": ev["threshold_sensitivity"],
            "threshold_sensitivity_probe": ev["slice_probe_baseline"],
        },

        "per_baseline": ev["per_baseline"],
        "ranking_reference": ev["ranking_reference"],
        "ranking_vs_reference": ev["ranking_vs_reference"],

        "leakage_inflation_headline": report["leakage_inflation_headline"],

        "pairwise_ranking_stability": {
            "n_pairs": len(pairwise["pairwise_matrix"]),
            "eligible_baselines": pairwise["eligible_baselines"],
            "pairwise_matrix": pairwise["pairwise_matrix"],
            "tie_aware_joint_ordering": pairwise["tie_aware_joint_ordering"],
            "equivalence_margin_status": pairwise["equivalence_margin_status"],
            "excluded_baselines": pairwise["excluded_baselines"],
        },

        "slices": {
            "temporal": ev["temporal_slice"],
            "geographic_summary": {
                "n_cells": len(gslice),
                "sum_n": sum(g_ns),
                "min_cell_n": min(g_ns) if g_ns else None,
                "max_cell_n": max(g_ns) if g_ns else None,
                "brier_min": min(g_briers) if g_briers else None,
                "brier_max": max(g_briers) if g_briers else None,
                "brier_median": _median(g_briers),
            },
            "geographic_full": gslice,
            "slice_probe_baseline": ev["slice_probe_baseline"],
        },

        "exclusions_and_deviations": {
            "B3_axis_excluded": core["excluded_forbidden_axis"].get("B3_expanded_metadata_logit"),
            "IPE_excluded": pairwise["excluded_baselines"]["B_domain_IPE"]["reason"],
            "quarantined_inspected_ids": list(quarantine_ids),
            "W4_equivalence_margin_deviation": {
                "preregistered_numeric_equivalence_margin": None,
                "genuinely_registered_resolution_floor": ac.RESOLUTION_FLOOR,
                "handling": "narrowed to complete pairwise descriptive reporting; equivalent class not asserted",
                "disclosure": "manuscript/disclosures/W4_pairwise_ranking_deviation_disclosure.json",
            },
            "F1_self_reference": {
                "n_expected_stale_self_referential": 3,
                "n_load_bearing_matched": f1["independent_rehash_result"]["n_matched"],
                "disclosure": "manuscript/disclosures/F1_phase_f_self_reference_disclosure.json",
            },
            "F3_leakage_null_framing": "Leakage-inflation gap is near-null / slightly reversed on this M>=5 one-row-per-event corpus; reported as an honest measured null, not as leakage evidence or a win.",
        },

        "reproducibility_manifest": {
            "source_snapshot_sha256": ac.SOURCE_SHA,
            "source_snapshot_bytes": ac.verify_source_snapshot()["bytes"],
            "fdsn_features": n_fdsn_features,
            "result_hash": run["result_hash"],
            "run_token_consumed_count": len(consumed.get("consumed_tokens", [])),
            "predictions_digest": core["predictions_digest"],
            "fit_ledger_digest": core["fit_ledger_digest"],
            "fit_count": core["fit_count"],
            "fit_cap": 120,
            "reconstruction_pipeline_digest": core["reconstruction_pipeline_digest"],
            "environment": {p["package"]: p["version"] for p in env_lock["packages"]},
            "python": env_lock["interpreter"]["python_version"],
            "licences": {"data": "CC0-1.0", "code": "MIT", "source": "USGS public domain"},
            "n_load_bearing_files_matched": f1["independent_rehash_result"]["n_matched"],
            "n_self_referential_stale": f1["load_bearing_integrity"]["n_load_bearing_files"] and 3,
        },

        "no_winning_model_claim": True,
    }

    sha = ac.write_json_sorted(OUT, out)
    return {"asset_inputs.json": sha}


if __name__ == "__main__":
    import json
    print(json.dumps(build(), indent=2))
