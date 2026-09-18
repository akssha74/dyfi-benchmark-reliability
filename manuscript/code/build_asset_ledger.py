"""Register every generated manuscript artifact in an artifact ledger + manifest.

Each table, figure, derived result, and disclosure gets a ledger entry with its
generator, generator command, hashed source artifacts, sha256, and a
claim-neutral interpretation (per skills/research-paper-scientist/artifacts.md).
Deterministic: verified_at is the fixed study date, so the manifest hash is stable
across runs.

Outputs:
  manuscript/asset_ledger.jsonl
  manuscript/asset_manifest.json
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

import asset_common as ac

MAN = os.path.join(ac.ROOT, "manuscript")
DERIVED = os.path.join(MAN, "derived")
TABLES = os.path.join(MAN, "tables")
FIGS = os.path.join(MAN, "figures")
DISC = os.path.join(MAN, "disclosures")
VERIFIED_AT = "2026-09-01"

PY_A = "code/.venv/bin/python"          # pinned analytics venv
PY_F = "manuscript/.venv-fig/bin/python"  # figures venv


def _sha(rel: str) -> str:
    return ac.sha256_file(os.path.join(ac.ROOT, rel))


def _src(rel: str) -> Dict[str, str]:
    return {"path": rel, "sha256": _sha(rel)}


# Frozen inputs common to the whole asset set.
FROZEN_INPUTS = [
    "results/protected_run_temporal/run_result.json",
    "bundle/release/event_level_table.csv",
    "activation/raw/dyfi_M5_dyfi_2015_2025_20260901T063330Z.geojson",
]


def build() -> Dict[str, object]:
    caps = ac.common.load_json(os.path.join(DERIVED, "table_captions.json"))
    pw = ac.common.load_json(os.path.join(DERIVED, "pairwise_ranking_stability.json"))

    entries: List[Dict[str, object]] = []
    aid = [0]

    def add(atype, rel_path, generator_code, generator_command, sources, justification):
        aid[0] += 1
        entries.append({
            "artifact_id": f"A{aid[0]:03d}",
            "type": atype,
            "path": rel_path,
            "sha256": _sha(rel_path),
            "generator_code": generator_code,
            "generator_command": generator_command,
            "source_artifacts": sources,
            "justification": justification,
            "verified_at": VERIFIED_AT,
        })

    frozen_src = [_src(p) for p in FROZEN_INPUTS]
    inputs_src = frozen_src + [_src("manuscript/derived/asset_inputs.json")]
    pairwise_src = frozen_src + [_src("code/metrics.py")]

    # F2 derived results.
    add("other", "manuscript/derived/pairwise_ranking_stability.json",
        "manuscript/code/build_pairwise_ranking.py",
        f"{PY_A} manuscript/code/build_pairwise_ranking.py",
        pairwise_src,
        pw["claim_neutral_interpretation"])
    add("other", "manuscript/derived/pairwise_ranking_stability.csv",
        "manuscript/code/build_pairwise_ranking.py",
        f"{PY_A} manuscript/code/build_pairwise_ranking.py",
        pairwise_src,
        "Flat CSV of the full pairwise ranking-stability matrix; same content as the JSON, reader-parseable.")
    add("other", "manuscript/derived/reconstruction_verification.json",
        "manuscript/code/build_pairwise_ranking.py",
        f"{PY_A} manuscript/code/build_pairwise_ranking.py",
        frozen_src,
        "Bit-identity proof that reconstructed holdout predictions reproduce the recorded predictions_digest and every frozen per-baseline score.")
    add("other", "manuscript/derived/asset_inputs.json",
        "manuscript/code/build_asset_inputs.py",
        f"{PY_A} manuscript/code/build_asset_inputs.py",
        frozen_src + [_src("manuscript/derived/pairwise_ranking_stability.json"),
                      _src("manuscript/disclosures/F1_phase_f_self_reference_disclosure.json")],
        "Consolidated, verified frozen numbers consumed by all tables and figures.")

    # Disclosures.
    add("other", "manuscript/disclosures/W4_pairwise_ranking_deviation_disclosure.json",
        "manuscript/disclosures/W4_pairwise_ranking_deviation_disclosure.json",
        "static disclosure authored from the frozen preregistration + F2 matrix",
        [_src("preregistration/frozen_preregistration.json"),
         _src("manuscript/derived/pairwise_ranking_stability.json")],
        "Formal W4 deviation: no positive numeric equivalence margin was pre-registered; W4 narrowed to complete pairwise descriptive reporting; no equivalent verdict asserted.")
    add("other", "manuscript/disclosures/F1_phase_f_self_reference_disclosure.json",
        "manuscript/code/build_f1_disclosure.py",
        f"{PY_A} manuscript/code/build_f1_disclosure.py",
        [_src("governance/post_execution_artifact_manifest.json")],
        "Honest disclosure of the three expected-stale self-referential phase-F manifest entries; 83/83 load-bearing artifacts match recorded digests; no hash hand-edited.")

    # Tables (tex + csv companions).
    table_specs = [
        ("cohort_roles", "cohort/role accounting"),
        ("endpoint_threshold_sensitivity", "endpoint threshold sensitivity"),
        ("baseline_performance", "baseline performance with uncertainty/calibration"),
        ("leakage_gap", "leakage-inflation across split schemes"),
        ("pairwise_matrix", "full pairwise ranking-stability matrix"),
        ("slices", "temporal and geographic subgroup summaries within the temporal holdout"),
        ("exclusions_deviations", "exclusions and disclosed deviations"),
        ("reproducibility_manifest", "data/reproducibility manifest"),
    ]
    for name, _desc in table_specs:
        cap = caps.get(name, {})
        interp = cap.get("claim_neutral_interpretation", "")
        add("table", f"manuscript/tables/{name}.tex",
            "manuscript/code/build_tables.py",
            f"{PY_A} manuscript/code/build_tables.py",
            inputs_src, interp)
        add("table", f"manuscript/tables/{name}.csv",
            "manuscript/code/build_tables.py",
            f"{PY_A} manuscript/code/build_tables.py",
            inputs_src, interp + " (full-precision CSV companion)")
    # extra companion CSV
    add("other", "manuscript/tables/slices_geographic_full.csv",
        "manuscript/code/build_tables.py",
        f"{PY_A} manuscript/code/build_tables.py",
        inputs_src, "Full cell-level Brier values for 82 geographic subgroups of the temporal holdout; not a leave-region-out evaluation.")

    # Figures (editable SVG, review PNG, and publication-ready vector PDF).
    fig_specs = [
        ("fig_cohort_flow", "Cohort construction and role assignment flow diagram."),
        ("fig_baseline_scores", "Baseline Brier with 95% CIs and calibration intercept/slope; B0 calibration infeasible."),
        ("fig_leakage_split", "Fixed-diagnostic Brier and AUROC across random/event/sequence splits; small observed differences reported descriptively."),
        ("fig_threshold_slice", "Probe Brier/AUROC/prevalence across endpoint thresholds and across the two holdout years."),
    ]
    for name, interp in fig_specs:
        for ext in ("svg", "png", "pdf"):
            add("figure", f"manuscript/figures/{name}.{ext}",
                "manuscript/code/build_figures.py",
                f"{PY_F} manuscript/code/build_figures.py",
                [_src("manuscript/derived/asset_inputs.json")],
                interp)

    # Code listings (self-referential generator_code).
    for mod in ("asset_common.py", "build_pairwise_ranking.py", "build_f1_disclosure.py",
                "build_asset_inputs.py", "build_tables.py", "build_figures.py",
                "build_asset_ledger.py", "validate_assets.py"):
        rel = f"manuscript/code/{mod}"
        if os.path.isfile(os.path.join(ac.ROOT, rel)):
            add("code-listing", rel, rel, "n/a (source listing)", [],
                "Deterministic generator/validation source; procedural artifact.")

    # Write JSONL ledger (sorted by artifact_id for stability).
    ledger_path = os.path.join(MAN, "asset_ledger.jsonl")
    lines = [json.dumps(e, sort_keys=True, separators=(",", ":")) for e in entries]
    ledger_sha = ac.write_text(ledger_path, "\n".join(lines) + "\n")

    manifest = {
        "record_type": "manuscript_asset_manifest",
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "verified_at": VERIFIED_AT,
        "n_artifacts": len(entries),
        "counts_by_type": {
            t: sum(1 for e in entries if e["type"] == t)
            for t in sorted({e["type"] for e in entries})
        },
        "frozen_inputs": frozen_src,
        "artifacts": {e["path"]: e["sha256"] for e in entries},
        "asset_ledger": {"path": "manuscript/asset_ledger.jsonl", "sha256": ledger_sha},
        "no_winning_model_claim": True,
        "note": (
            "All artifacts regenerate deterministically from the frozen released "
            "resource via the recorded generator commands. No result-bearing cell or "
            "plotted value was hand-edited. Figures use the separate build venv "
            "(manuscript/.venv-fig); tables/derived use the pinned analytics venv."
        ),
    }
    man_sha = ac.write_json_sorted(os.path.join(MAN, "asset_manifest.json"), manifest)
    return {"asset_ledger.jsonl": ledger_sha, "asset_manifest.json": man_sha,
            "n_artifacts": len(entries)}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
