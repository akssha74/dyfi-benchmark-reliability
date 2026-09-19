#!/usr/bin/env python3
"""Deterministically emit the manuscript claim / artifact / build ledgers.

All three ledgers are derived only from IMMUTABLE inputs already validated
elsewhere (manuscript/derived/asset_inputs.json, manuscript/asset_manifest.json)
and from byte hashes of the paper sources. No model is refit and nothing is
fetched. Re-running reproduces byte-identical ledgers (sorted keys, fixed text).

  * claim_ledger.jsonl   -- every load-bearing number in the paper mapped to its
                            source pointer inside asset_inputs.json plus where it
                            surfaces (abstract / prose / table / figure).
  * artifact_ledger.jsonl-- every file the build consumes or emits with its sha256
                            and provenance (canonical asset vs generated copy).
  * build_ledger.json    -- toolchain, ordered build steps, and output digests.
"""
from __future__ import annotations
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
MAN = HERE.parent
DERIVED = MAN / "derived" / "asset_inputs.json"
MANIFEST = MAN / "asset_manifest.json"


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def r3(x: float) -> str:
    return f"{x:.3f}"


def build_claim_ledger(ai: dict) -> list[dict]:
    rows: list[dict] = []

    def add(cid, text, value, pointer, appears):
        rows.append({
            "record_type": "claim_ledger_entry",
            "claim_id": cid,
            "claim": text,
            "value": value,
            "source_artifact": "manuscript/derived/asset_inputs.json",
            "json_pointer": pointer,
            "appears_in": appears,
        })

    cf = ai["cohort_flow"]
    roles = cf["roles"]
    add("C0", "frozen USGS DYFI source-record count",
        cf["fdsn_features_pinned_snapshot"],
        "/cohort_flow/fdsn_features_pinned_snapshot",
        ["abstract", "prose", "tab:cohort", "fig:flow"])
    add("C1", "eligible one-row-per-event corpus size", cf["n_eligible_events"],
        "/cohort_flow/n_eligible_events", ["abstract", "prose", "tab:cohort", "fig:flow"])
    add("C1b", "severe events among all eligible (= 449 train + 102 dev + 151 holdout + 1 straddle)",
        cf["n_eligible_severe"], "/cohort_flow/n_eligible_severe", ["prose", "tab:cohort"])
    add("C1c", "eligible severe prevalence (703/2362)", r3(cf["eligible_prevalence"]),
        "/cohort_flow/eligible_prevalence", ["prose", "tab:cohort"])
    add("C1d", "severe events among the 2360 analysis-role-assigned events (excludes 1 severe straddle)",
        cf["n_role_assigned_severe"], "/cohort_flow/n_role_assigned_severe", ["prose", "tab:cohort"])
    add("C2", "training role event count", roles["train"]["n"],
        "/cohort_flow/roles/train/n", ["prose", "tab:cohort", "fig:flow"])
    add("C3", "development role event count", roles["development"]["n"],
        "/cohort_flow/roles/development/n", ["prose", "tab:cohort", "fig:flow"])
    add("C4", "external temporal holdout event count", roles["external_temporal_holdout"]["n"],
        "/cohort_flow/roles/external_temporal_holdout/n",
        ["abstract", "prose", "tab:cohort", "fig:flow"])
    add("C5", "events excluded because their sequence straddles the temporal cutoff",
        cf["temporal_straddle_excluded"],
        "/cohort_flow/temporal_straddle_excluded", ["prose", "tab:cohort", "fig:flow"])
    add("C5b", "severe events among temporal-straddle exclusions",
        cf["temporal_straddle"]["positive"],
        "/cohort_flow/temporal_straddle/positive", ["prose", "tab:cohort"])
    add("C6", "construction pool (train+development) size", cf["construction_total"]["n"],
        "/cohort_flow/construction_total/n", ["prose", "tab:cohort", "fig:flow"])
    add("C6b", "construction severe-event count", cf["construction_total"]["positive"],
        "/cohort_flow/construction_total/positive", ["tab:cohort"])
    add("C6c", "construction severe-event rate", r3(cf["construction_total"]["prevalence"]),
        "/cohort_flow/construction_total/prevalence", ["prose", "tab:cohort"])
    add("C7", "holdout positive count (severe events)",
        roles["external_temporal_holdout"]["positive"],
        "/cohort_flow/roles/external_temporal_holdout/positive", ["prose", "tab:cohort"])
    add("C8", "holdout severe prevalence (151/430)",
        r3(roles["external_temporal_holdout"]["prevalence"]),
        "/cohort_flow/roles/external_temporal_holdout/prevalence",
        ["prose", "tab:cohort", "tab:threshold", "fig:flow"])
    add("C9", "eligible seismic-sequence count", cf["sequences"]["all_eligible"],
        "/cohort_flow/sequences/all_eligible", ["prose", "tab:cohort", "fig:flow"])
    add("C10", "construction seismic-sequence count", cf["sequences"]["construction"],
        "/cohort_flow/sequences/construction", ["prose", "tab:cohort", "fig:flow"])
    add("C11", "temporal-holdout seismic-sequence count", cf["sequences"]["holdout"],
        "/cohort_flow/sequences/holdout", ["prose", "tab:cohort", "fig:flow"])
    add("C12", "temporal-straddle seismic-sequence count", cf["sequences"]["straddle"],
        "/cohort_flow/sequences/straddle", ["tab:cohort"])
    for role_key, label in (("train", "training"), ("development", "development")):
        role = roles[role_key]
        add(f"C_{role_key}_positive", f"{label} severe-event count", role["positive"],
            f"/cohort_flow/roles/{role_key}/positive", ["tab:cohort"])
        add(f"C_{role_key}_prevalence", f"{label} severe-event rate",
            r3(role["prevalence"]), f"/cohort_flow/roles/{role_key}/prevalence",
            ["tab:cohort", "fig:flow"])

    ep = ai["endpoint"]
    for thr in ("5.5", "6.0", "6.5"):
        ts = ep["threshold_sensitivity"][thr]
        for field in ("prevalence", "brier", "auroc"):
            add(f"E_{thr}_{field}", f"threshold {thr} {field} (source-only probe)",
                r3(ts[field]), f"/endpoint/threshold_sensitivity/{thr}/{field}",
                ["prose", "tab:threshold", "fig:threshold"])
    add("E_near_threshold", "construction events within 0.5 CDI units of cutoff",
        r3(ep["near_threshold_fraction_construction"]),
        "/endpoint/near_threshold_fraction_construction", ["prose", "tab:threshold"])
    add("E_no_skill", "construction no-skill Brier score",
        r3(ep["no_skill_brier_floor_construction"]),
        "/endpoint/no_skill_brier_floor_construction", ["prose", "tab:threshold"])

    lh = ai["leakage_inflation_headline"]
    add("L1", "Brier split contrast (sequence minus random), reported descriptively",
        r3(lh["brier_inflation_seq_minus_random"]),
        "/leakage_inflation_headline/brier_inflation_seq_minus_random",
        ["abstract", "prose", "tab:leakage", "fig:leakage"])
    add("L2", "AUROC split contrast (random minus sequence), reported descriptively",
        r3(lh["auroc_inflation_random_minus_seq"]),
        "/leakage_inflation_headline/auroc_inflation_random_minus_seq",
        ["abstract", "prose", "tab:leakage", "fig:leakage"])
    for scheme in ("random_event", "event_grouped", "sequence_grouped"):
        ps = lh["per_scheme"][scheme]
        add(f"L_{scheme}_brier", f"{scheme} mean Brier", r3(ps["brier"]),
            f"/leakage_inflation_headline/per_scheme/{scheme}/brier",
            ["tab:leakage", "fig:leakage"])
        add(f"L_{scheme}_auroc", f"{scheme} mean AUROC", r3(ps["auroc"]),
            f"/leakage_inflation_headline/per_scheme/{scheme}/auroc",
            ["tab:leakage", "fig:leakage"])
        add(f"L_{scheme}_logloss", f"{scheme} mean log-loss", r3(ps["log_loss"]),
            f"/leakage_inflation_headline/per_scheme/{scheme}/log_loss",
            ["tab:leakage"])

    pb = ai["per_baseline"]
    for bid in ("B0_no_skill", "B1_magnitude_only_logit", "B2_source_only_logit",
                "B4_random_forest", "B5_xgboost"):
        b = pb[bid]
        add(f"{bid}_brier", f"{bid} holdout Brier", r3(b["brier"]),
            f"/per_baseline/{bid}/brier", ["prose", "tab:baselines", "fig:baselines"])
        lo, hi = b["brier_ci"]
        add(f"{bid}_brier_ci", f"{bid} holdout Brier 95% cluster-bootstrap CI",
            [r3(lo), r3(hi)], f"/per_baseline/{bid}/brier_ci",
            ["tab:baselines", "fig:baselines"])
        add(f"{bid}_auroc", f"{bid} holdout AUROC", r3(b["auroc"]),
            f"/per_baseline/{bid}/auroc", ["tab:baselines"])
        add(f"{bid}_logloss", f"{bid} holdout log-loss", r3(b["log_loss"]),
            f"/per_baseline/{bid}/log_loss", ["tab:baselines"])
        add(f"{bid}_accuracy", f"{bid} holdout accuracy at the fixed threshold",
            f"{b['confusion_at_threshold']['accuracy']:.2f}",
            f"/per_baseline/{bid}/confusion_at_threshold/accuracy", ["tab:baselines"])
        if b["calibration_status"] == "OK":
            add(f"{bid}_calibration", f"{bid} calibration intercept and slope",
                [f"{b['calibration_intercept']:.2f}", f"{b['calibration_slope']:.2f}"],
                f"/per_baseline/{bid}", ["tab:baselines"])
        else:
            add(f"{bid}_calibration", f"{bid} calibration unavailable for constant predictions",
                b["calibration_status"], f"/per_baseline/{bid}/calibration_status",
                ["tab:baselines"])

    pm = ai["pairwise_ranking_stability"]["pairwise_matrix"]
    for pk, cell in pm.items():
        add(f"P_{pk}", f"pairwise Brier comparison ({pk})",
            {
                "point_diff_a_minus_b": f"{cell['point_diff_a_minus_b']:.4f}",
                "ci": [f"{cell['ci'][0]:.4f}", f"{cell['ci'][1]:.4f}"],
                "prob_a_better": r3(cell["prob_a_better"]),
                "resolved": cell["resolved"],
            },
            f"/pairwise_ranking_stability/pairwise_matrix/{pk}",
            ["tab:pairwise"])
    add("P_unresolved", "two learned-baseline pairs unresolved (B2 vs B4; B2 vs B5)",
        ["B2_source_only_logit_vs_B4_random_forest",
         "B2_source_only_logit_vs_B5_xgboost"],
        "/pairwise_ranking_stability/pairwise_matrix", ["abstract", "prose", "tab:pairwise"])

    sl = ai["slices"]
    for yr in ("2023", "2024"):
        add(f"S_temporal_{yr}_brier", f"temporal slice {yr} Brier", r3(sl["temporal"][yr]["brier"]),
            f"/slices/temporal/{yr}/brier", ["prose", "tab:slices", "fig:threshold"])
        add(f"S_temporal_{yr}_auroc", f"temporal slice {yr} AUROC", r3(sl["temporal"][yr]["auroc"]),
            f"/slices/temporal/{yr}/auroc", ["prose", "tab:slices", "fig:threshold"])
        add(f"S_temporal_{yr}_n", f"temporal slice {yr} n", sl["temporal"][yr]["n"],
            f"/slices/temporal/{yr}/n", ["prose", "tab:slices", "fig:threshold"])
    gs = sl["geographic_summary"]
    add("S_geo_cells", "occupied 10-degree geographic cells within temporal holdout", gs["n_cells"],
        "/slices/geographic_summary/n_cells", ["prose", "tab:slices"])
    add("S_geo_sum_n", "temporal-holdout events included in geographic subgroup summary", gs["sum_n"],
        "/slices/geographic_summary/sum_n", ["tab:slices"])
    add("S_geo_median", "median cell-level Brier score in geographic subgroup summary",
        r3(gs["brier_median"]), "/slices/geographic_summary/brier_median",
        ["prose", "tab:slices"])
    add("S_geo_range", "range of cell-level Brier scores in geographic subgroup summary",
        [r3(gs["brier_min"]), r3(gs["brier_max"])],
        "/slices/geographic_summary", ["prose", "tab:slices"])

    rm = ai["reproducibility_manifest"]
    add("R_fit_count", "fit count consumed", rm["fit_count"],
        "/reproducibility_manifest/fit_count", ["prose"])
    add("R_fit_cap", "preregistered fit cap", rm["fit_cap"],
        "/reproducibility_manifest/fit_cap", ["prose"])
    add("R_run_token", "one-shot run tokens consumed", rm["run_token_consumed_count"],
        "/reproducibility_manifest/run_token_consumed_count", ["prose"])
    add("F1_stale", "self-referential expected-stale manifest entries (F1)",
        rm["n_self_referential_stale"],
        "/reproducibility_manifest/n_self_referential_stale", ["prose"])

    em = ai["pairwise_ranking_stability"]["equivalence_margin_status"]
    add("W4_margin", "preregistered numeric equivalence margin (none; W4 deviation)",
        em["preregistered_numeric_equivalence_margin"],
        "/pairwise_ranking_stability/equivalence_margin_status/preregistered_numeric_equivalence_margin",
        ["prose"])
    add("W4_floor", "genuinely registered resolution floor", em["genuinely_registered_resolution_floor"],
        "/pairwise_ranking_stability/equivalence_margin_status/genuinely_registered_resolution_floor",
        ["prose"])
    add("NW", "no winning-model claim asserted", ai["no_winning_model_claim"],
        "/no_winning_model_claim", ["abstract", "prose"])
    return rows


def build_artifact_ledger() -> list[dict]:
    manifest = json.loads(MANIFEST.read_text()).get("artifacts", {})
    rows: list[dict] = []

    def add(rel, role, provenance, canonical_match=None):
        p = HERE / rel
        entry = {
            "record_type": "artifact_ledger_entry",
            "path": f"manuscript/paper/{rel}",
            "role": role,
            "sha256": sha256(p) if p.exists() else None,
            "exists": p.exists(),
            "provenance": provenance,
        }
        if canonical_match is not None:
            entry["canonical_asset"] = canonical_match
            cp = MAN / canonical_match
            entry["canonical_sha256"] = sha256(cp) if cp.exists() else None
            entry["byte_identical_to_canonical"] = (
                cp.exists() and p.exists() and sha256(cp) == sha256(p))
        rows.append(entry)

    add("main.tex", "manuscript source", "hand-authored from validated assets")
    add("references.bib", "bibliography", "verified per citation_ledger.jsonl")
    add("sn-jnl.cls", "venue class file", "Springer Nature sn-jnl template")
    add("sn-basic.bst", "venue bibliography style", "Springer Nature sn-basic")
    for fig in sorted((HERE / "figures").glob("*.pdf")):
        add(f"figures/{fig.name}", "figure",
            "byte-copy of validated vector manuscript figure",
            canonical_match=f"figures/{fig.name}")
    for t in sorted((HERE / "tables").glob("*.tex")):
        add(f"tables/{t.name}", "venue-formatted table input",
            "layout-only transform of canonical table via format_tables.py",
            canonical_match=f"tables/{t.name}")
    for aux in ("citation_ledger.jsonl", "claim_ledger.jsonl", "artifact_ledger.jsonl",
                "format_tables.py", "validate_manuscript.py", "generate_ledgers.py",
                "build.sh", "validation_report.json"):
        if (HERE / aux).exists():
            add(aux, "build/ledger tool or record", "generated in manuscript/paper")
    # note the canonical manifest linkage
    for row in rows:
        cm = row.get("canonical_asset")
        if cm and f"manuscript/{cm}" in manifest:
            row["recorded_manifest_sha256"] = manifest[f"manuscript/{cm}"]
    return rows


def build_build_ledger() -> dict:
    pdf = HERE / "main.pdf"
    return {
        "record_type": "manuscript_build_ledger",
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "engine": "Tectonic 0.17.0 (auto BibTeX + reruns)",
        "engine_reference_binary_sha256": "568dea0a81f4ceed859e33734bbbea85d54a25f14b12665a48c98b536a887986",
        "pdf_determinism_scope": (
            "Byte-identical under Tectonic 0.17.0 with the same cached resource "
            "bundle and SOURCE_DATE_EPOCH. Other Tectonic versions may serialize "
            "different PDF bytes while preserving identical text and pixels."
        ),
        "entrypoint": "manuscript/paper/build.sh",
        "ordered_steps": [
            "python3 format_tables.py  (layout-only venue table copies)",
            "cp ../figures/*.pdf figures/  (byte-identical vector figures)",
            "tectonic --keep-logs main.tex  (compile -> main.pdf)",
        ],
        "inputs_are_immutable": True,
        "network_writes": False,
        "public_repository": "https://github.com/akssha74/dyfi-benchmark-reliability",
        "public_release_tag": "v1.0.14",
        "doi": None,
        "submitted": False,
        "main_tex_sha256": sha256(HERE / "main.tex"),
        "references_bib_sha256": sha256(HERE / "references.bib"),
        "main_pdf_sha256": sha256(pdf) if pdf.exists() else None,
        "main_pdf_bytes": pdf.stat().st_size if pdf.exists() else None,
    }


def main() -> int:
    ai = json.loads(DERIVED.read_text())

    claim_rows = build_claim_ledger(ai)
    with (HERE / "claim_ledger.jsonl").open("w") as f:
        for r in claim_rows:
            f.write(json.dumps(r) + "\n")

    art_rows = build_artifact_ledger()
    with (HERE / "artifact_ledger.jsonl").open("w") as f:
        for r in art_rows:
            f.write(json.dumps(r) + "\n")

    (HERE / "build_ledger.json").write_text(
        json.dumps(build_build_ledger(), indent=2) + "\n")

    print(f"claim_ledger.jsonl: {len(claim_rows)} claims")
    print(f"artifact_ledger.jsonl: {len(art_rows)} artifacts")
    print("build_ledger.json: written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
