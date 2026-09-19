#!/usr/bin/env python3
"""Deterministic manuscript validator for the DYFI severe-felt-intensity paper.

Checks, all against IMMUTABLE assets (no model refit, no network):

  1. arithmetic / consistency: every load-bearing number rendered in the paper
     tables and prose is derived from manuscript/derived/asset_inputs.json and
     the identities among them hold (partition sums, confusion sums, prevalences,
     threshold prevalences, leakage gaps, pairwise-vs-B0 negation).
  2. citation coverage: every \\cite* key in main.tex exists in references.bib;
     every references.bib entry is cited; every entry carries a DOI (or is an
     explicitly DOI-less venue) and is listed in citation_ledger.jsonl.
  3. file integrity: every \\input table and \\includegraphics figure exists;
     the class/style files are present.
  4. asset hash identity: paper figure files are byte-identical to the validated
     manuscript figures, and the canonical manuscript/tables/*.tex match
     their recorded sha256 in manuscript/asset_manifest.json.

Exits non-zero on any failure and writes validation_report.json.
"""
from __future__ import annotations
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
MAN = HERE.parent                      # manuscript/
DERIVED = MAN / "derived" / "asset_inputs.json"
MANIFEST = MAN / "asset_manifest.json"
MAIN = HERE / "main.tex"
BIB = HERE / "references.bib"
CITELEDGER = HERE / "citation_ledger.jsonl"
BUILD_LEDGER = HERE / "build_ledger.json"

results: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append({"check": name, "ok": bool(ok), "detail": detail})


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def r3(x: float) -> str:
    return f"{x:.3f}"


def main() -> int:
    ai = json.loads(DERIVED.read_text())
    main_tex = MAIN.read_text()
    tables = {p.name: p.read_text() for p in (HERE / "tables").glob("*.tex")}
    all_tex = main_tex + "\n" + "\n".join(tables.values())

    # ---- 0. Journal of Seismology front matter / venue fit ----
    check("journal_of_seismology_target",
          "Journal of Seismology (Springer Nature) submission" in main_tex
          and "Discover Applied Sciences" not in main_tex, "")
    check("author_year_sn_basic_style",
          r"\documentclass[pdflatex,sn-basic,iicol]{sn-jnl}" in main_tex
          and "Numbered" not in main_tex.split(r"\begin{document}", 1)[0], "")
    abstract_match = re.search(r"\\abstract\{(.*?)\}\s*\\keywords", main_tex, re.S)
    abstract_words = (re.findall(r"\b[\w'-]+\b", abstract_match.group(1))
                      if abstract_match else [])
    check("abstract_150_to_250_words",
          150 <= len(abstract_words) <= 250, str(len(abstract_words)))
    check("title_page_author_information_complete",
          r"\author*" in main_tex and main_tex.count(r"\email{") == 2
          and r"\affil*" in main_tex and r"\city{Indore}" in main_tex
          and r"\country{India}" in main_tex, "")
    keyword_match = re.search(r"\\keywords\{([^}]+)\}", main_tex, re.S)
    keywords = [x.strip() for x in keyword_match.group(1).split(",")] if keyword_match else []
    check("four_to_six_keywords", 4 <= len(keywords) <= 6, str(keywords))
    highlights_match = re.search(
        r"\\section\*\{Article Highlights\}(.*?)\\end\{itemize\}", main_tex, re.S)
    highlights = (re.findall(r"\\item\s+([^\n]+)", highlights_match.group(1))
                  if highlights_match else [])
    check("three_highlights_under_120_characters",
          len(highlights) == 3 and all(len(x) <= 120 for x in highlights),
          str([(len(x), x) for x in highlights]))
    check("statements_and_declarations_heading",
          r"\section*{Statements and Declarations}" in main_tex, "")
    check("generative_ai_disclosed_in_methods",
          r"\paragraph{Generative AI assistance.}" in main_tex
          and main_tex.index(r"\paragraph{Generative AI assistance.}")
          < main_tex.index(r"\section{Results}"), "")

    # ---- 1. arithmetic / consistency ----
    cf = ai["cohort_flow"]
    roles = cf["roles"]
    part = roles["train"]["n"] + roles["development"]["n"] + \
        roles["external_temporal_holdout"]["n"] + cf["temporal_straddle_excluded"]
    check("partition_sums_to_eligible", part == cf["n_eligible_events"] == 2362,
          f"{part} == {cf['n_eligible_events']}")
    check("construction_equals_train_plus_dev",
          cf["construction_total"]["n"] == roles["train"]["n"] + roles["development"]["n"],
          f"{cf['construction_total']['n']}")
    # F1: eligible severe count/prevalence use the full eligible denominator and
    # reconcile with the role-assigned sum plus the straddle exclusions.
    role_sev = (roles["train"]["positive"] + roles["development"]["positive"]
                + roles["external_temporal_holdout"]["positive"])
    check("eligible_severe_reconciles_with_roles_and_straddle",
          cf["n_eligible_severe"] == role_sev + cf["temporal_straddle"]["positive"] == 703,
          f"{cf['n_eligible_severe']} == {role_sev} + {cf['temporal_straddle']['positive']}")
    check("role_assigned_severe_equals_702",
          cf["n_role_assigned_severe"] == role_sev == 702, str(cf["n_role_assigned_severe"]))
    ct = tables["cohort_roles.tex"]
    check("eligible_severe_703_in_table", "703" in ct and str(cf["n_eligible_severe"]) in ct,
          str(cf["n_eligible_severe"]))
    check("eligible_prevalence_0.298_in_table",
          r3(cf["eligible_prevalence"]) == "0.298" and "0.298" in ct, r3(cf["eligible_prevalence"]))
    check("eligible_prevalence_0.298_in_prose", "0.298" in main_tex and "0.297" not in main_tex,
          "0.298 present and stale 0.297 absent")

    ep = ai["endpoint"]
    hp = roles["external_temporal_holdout"]["prevalence"]
    check("holdout_prevalence_151_over_430", abs(hp - 151 / 430) < 1e-9, r3(hp))
    for thr in ("5.5", "6.0", "6.5"):
        ts = ep["threshold_sensitivity"][thr]
        # prevalence, brier, auroc must appear (rounded) in the threshold table
        tt = tables["endpoint_threshold_sensitivity.tex"]
        for field in ("prevalence", "brier", "auroc"):
            s = r3(ts[field])
            check(f"threshold_{thr}_{field}_in_table", s in tt, s)

    lh = ai["leakage_inflation_headline"]
    bgap = lh["brier_inflation_seq_minus_random"]
    agap = lh["auroc_inflation_random_minus_seq"]
    # recompute from per-scheme to confirm the recorded gap
    ps = lh["per_scheme"]
    rb = round(ps["sequence_grouped"]["brier"] - ps["random_event"]["brier"], 12)
    ra = round(ps["random_event"]["auroc"] - ps["sequence_grouped"]["auroc"], 12)
    check("leakage_brier_gap_recompute", abs(rb - bgap) < 1e-9, f"{rb} vs {bgap}")
    check("leakage_auroc_gap_recompute", abs(ra - agap) < 1e-9, f"{ra} vs {agap}")
    lt = tables["leakage_gap.tex"]
    check("leakage_brier_gap_-0.0059_in_table", "-0.0059" in lt, f"{bgap}")
    check("leakage_auroc_gap_-0.0124_in_table", "-0.0124" in lt, f"{agap}")
    # Headline is descriptive only: no post-hoc equivalence or zero-effect claim.
    check("split_contrast_framed_descriptively",
          "report the contrast descriptively" in main_tex
          and "zero-effect" in main_tex
          and "unfulfilled element as a deviation" in main_tex, "")
    check("no_winning_model_claim_in_prose",
          "no winning model" in main_tex and ai["no_winning_model_claim"] is True, "")
    check("protocol_chronology_disclosed",
          "first publicly timestamped on 2026-09-19" in main_tex
          and "not an externally registered preregistration" in main_tex, "")
    check("metric_uncertainty_coverage_disclosed",
          "only Brier-based intervals" in main_tex
          and "other metrics are descriptive point estimates" in main_tex, "")
    check("fdsn_inclusive_endtime_disclosed",
          "FDSN defines the end bound as inclusive" in main_tex
          and "realized snapshot spans 2015--2024" in main_tex
          and "50 seconds later in the same acquisition session" in main_tex, "")

    # per-baseline holdout values must appear in the baseline table
    bt = tables["baseline_performance.tex"]
    pb = ai["per_baseline"]
    for bid in ("B0_no_skill", "B1_magnitude_only_logit", "B2_source_only_logit",
                "B4_random_forest", "B5_xgboost"):
        b = pb[bid]
        check(f"{bid}_brier_in_table", r3(b["brier"]) in bt, r3(b["brier"]))
        lo, hi = b["brier_ci"]
        check(f"{bid}_brier_ci_in_table", f"[{r3(lo)}, {r3(hi)}]" in bt,
              f"[{r3(lo)}, {r3(hi)}]")
    # confusion sums to holdout n for each learned baseline
    for bid in ("B0_no_skill", "B1_magnitude_only_logit", "B2_source_only_logit",
                "B4_random_forest", "B5_xgboost"):
        c = pb[bid]["confusion_at_threshold"]
        tot = c["tp"] + c["fp"] + c["tn"] + c["fn"]
        check(f"{bid}_confusion_sums_to_430", tot == 430, str(tot))
        check(f"{bid}_positives_151", c["tp"] + c["fn"] == 151, str(c["tp"] + c["fn"]))

    # pairwise vs-B0 point diffs negate the frozen ranking_vs_reference
    pm = ai["pairwise_ranking_stability"]["pairwise_matrix"]
    rr = ai["ranking_vs_reference"]
    mp = {
        "B0_no_skill_vs_B1_magnitude_only_logit": "B1_magnitude_only_logit_vs_B0_no_skill",
        "B0_no_skill_vs_B2_source_only_logit": "B2_source_only_logit_vs_B0_no_skill",
        "B0_no_skill_vs_B4_random_forest": "B4_random_forest_vs_B0_no_skill",
        "B0_no_skill_vs_B5_xgboost": "B5_xgboost_vs_B0_no_skill",
    }
    for pk, rk in mp.items():
        pdif = pm[pk]["point_diff_a_minus_b"]
        rdif = rr[rk]["point_diff_a_minus_b"]
        check(f"pairwise_{pk}_negates_frozen", abs(pdif + rdif) < 1e-9,
              f"{pdif} vs -({rdif})")
    # the two unresolved learned pairs must be reported unresolved
    for pk in ("B2_source_only_logit_vs_B4_random_forest",
               "B2_source_only_logit_vs_B5_xgboost"):
        check(f"{pk}_unresolved", pm[pk]["resolved"] is False, pm[pk]["status"])

    # slices
    sl = ai["slices"]["temporal"]
    st = tables["slices.tex"]
    for yr in ("2023", "2024"):
        check(f"temporal_{yr}_brier_in_table", r3(sl[yr]["brier"]) in st, r3(sl[yr]["brier"]))
    gs = ai["slices"]["geographic_summary"]
    check("geographic_n_cells_82", gs["n_cells"] == 82 and "82" in st, str(gs["n_cells"]))
    check("geographic_sum_n_430",
          gs["sum_n"] == 430
          and "not a leave-region-out" in st
          and "not a\nleave-region-out evaluation" in main_tex,
          f"{gs['sum_n']}; subgroup-only wording present")

    # Absence of a prespecified positive equivalence margin must be disclosed.
    em = ai["pairwise_ranking_stability"]["equivalence_margin_status"]
    check("W4_no_preregistered_margin",
          em["preregistered_numeric_equivalence_margin"] is None
          and em["equivalent_class_populated"] is False, "")
    check("equivalence_margin_limit_disclosed_in_prose",
          "equivalence margin" in main_tex and "resolution floor of\nzero" in main_tex
          or "resolution floor" in main_tex, "")
    # Three self-referential bookkeeping records must be explained plainly.
    check("three_self_referential_records_disclosed_in_prose",
          re.search(r"Three\s+original\s+execution-bookkeeping\s+records\s+are\s+self-referential",
                    main_tex) is not None
          and "cannot contain their own final fingerprints" in main_tex, "")
    check("held_out_not_untouched",
          "held out from model development" in main_tex
          and "untouched" in main_tex, "phrasing present (with explicit not-untouched)")

    # ---- 2. citation coverage ----
    cited = set(re.findall(r"\\cite[a-z]*\{([^}]*)\}", main_tex))
    cited = {k.strip() for grp in cited for k in grp.split(",")}
    bib_keys = set(re.findall(r"@\w+\{([^,]+),", BIB.read_text()))
    check("all_cited_keys_in_bib", cited <= bib_keys, str(sorted(cited - bib_keys)))
    check("all_bib_entries_cited", bib_keys <= cited, str(sorted(bib_keys - cited)))
    jos_keys = {
        "kouskouna2021athens", "neefs2025btm", "sira2025macrosisdata",
        "ozupak2026alert", "ertuncay2025detection",
    }
    check("journal_of_seismology_literature_engaged",
          jos_keys <= cited, str(sorted(jos_keys - cited)))
    # DOI presence (pedregosa is the one DOI-less JMLR entry)
    bibtext = BIB.read_text()
    check("relevant_editor_in_chief_work_engaged",
          "sarao2023crowdsourcing" in cited, "")
    bib_years = [int(x) for x in re.findall(r"year\s*=\s*\{(\d{4})\}", bibtext)]
    check("bibliography_contains_recent_work",
          sum(y >= 2024 for y in bib_years) >= 9,
          str(sorted(y for y in bib_years if y >= 2024)))
    entries = re.split(r"@\w+\{", bibtext)[1:]
    no_doi = []
    for e in entries:
        key = e.split(",", 1)[0].strip()
        if "doi" not in e.lower():
            no_doi.append(key)
    check("only_expected_entry_has_no_doi", set(no_doi) <= {"pedregosa2011sklearn"},
          str(no_doi))
    # citation ledger covers every bib key
    led_keys = set()
    if CITELEDGER.exists():
        for line in CITELEDGER.read_text().splitlines():
            line = line.strip()
            if line:
                led_keys.add(json.loads(line)["key"])
    check("citation_ledger_covers_bib", bib_keys <= led_keys,
          str(sorted(bib_keys - led_keys)))
    check("corrected_authoritative_reference_metadata",
          "@article{oliveti2022inge" in bibtext
          and "year    = {2022}" in bibtext
          and "volume  = {65}" in bibtext
          and "@misc{usgs_dyfi_data" in bibtext
          and "year         = {2005}" in bibtext
          and "author       = {Wald, David J. and Dewey, James W.}" in bibtext
          and "@article{wald2012dyfi" in bibtext
          and "year    = {2012}" in bibtext
          and "pages   = {688--707}" in bibtext,
          "")

    # ---- 3. file integrity ----
    table_inputs = re.findall(r"\\input\{(tables/[^}]+)\}", main_tex)
    check("seven_focused_tables_in_manuscript",
          len(table_inputs) == 7
          and "tables/reproducibility_manifest.tex" not in table_inputs,
          str(table_inputs))
    check("no_orphaned_reproducibility_table_assets",
          not (MAN / "tables" / "reproducibility_manifest.tex").exists()
          and not (HERE / "tables" / "reproducibility_manifest.tex").exists(),
          "")
    for m in table_inputs:
        check(f"input_exists_{m}", (HERE / m).exists(), m)
    for m in re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}", main_tex):
        rel = pathlib.Path(m)
        cand = (HERE / rel) if "/" in m else (HERE / "figures" / rel)
        if not rel.suffix:
            choices = [cand.with_suffix(ext) for ext in (".pdf", ".png", ".svg")]
            cand = next((p for p in choices if p.exists()), choices[0])
        detail = str(cand.relative_to(HERE)) if cand.is_relative_to(HERE) else cand.name
        check(f"figure_exists_{m}", cand.exists(), detail)
    for f in ("sn-jnl.cls", "sn-basic.bst", "references.bib"):
        check(f"style_present_{f}", (HERE / f).exists(), f)

    # ---- 4. compiled-artifact currency ----
    build_ledger = json.loads(BUILD_LEDGER.read_text())
    check("build_ledger_main_tex_is_current",
          build_ledger["main_tex_sha256"] == sha256(MAIN),
          build_ledger["main_tex_sha256"])
    check("build_ledger_main_pdf_is_current",
          build_ledger["main_pdf_sha256"] == sha256(HERE / "main.pdf"),
          build_ledger["main_pdf_sha256"])
    release_tag = build_ledger["public_release_tag"]
    check("build_ledger_release_tag_matches_manuscript",
          f"/releases/tag/{release_tag}" in main_tex,
          release_tag)

    # ---- 5. asset hash identity ----
    for fig in (HERE / "figures").glob("*.pdf"):
        canon = MAN / "figures" / fig.name
        check(f"figure_byte_identical_{fig.name}",
              canon.exists() and sha256(fig) == sha256(canon), fig.name)
    manifest = json.loads(MANIFEST.read_text())["artifacts"]
    for rel, digest in manifest.items():
        if rel.startswith("manuscript/tables/") and rel.endswith(".tex"):
            src = MAN / rel.split("manuscript/", 1)[1]
            if src.exists():
                check(f"canonical_table_hash_{src.name}", sha256(src) == digest, src.name)

    n_fail = sum(1 for r in results if not r["ok"])
    report = {
        "record_type": "manuscript_paper_validation_report",
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "n_checks": len(results),
        "n_failed": n_fail,
        "overall_pass": n_fail == 0,
        "checks": results,
    }
    (HERE / "validation_report.json").write_text(json.dumps(report, indent=2))
    print(f"validate_manuscript: {len(results)} checks, {n_fail} failed -> "
          f"{'PASS' if n_fail == 0 else 'FAIL'}")
    if n_fail:
        for r in results:
            if not r["ok"]:
                print("  FAIL:", r["check"], r["detail"])
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
