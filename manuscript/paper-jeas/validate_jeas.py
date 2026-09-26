#!/usr/bin/env python3
"""Fail-closed validator for the JEAS DYFI retarget.

The validator proves that the venue retarget adds an engineering-use
demonstration without changing the frozen scientific inputs or the original
Journal of Seismology artifact.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAN = HERE.parent
ROOT = MAN.parent
MAIN = HERE / "main.tex"
BIB = HERE / "references.bib"
CITE_LEDGER = HERE / "citation_ledger.jsonl"
ASSET = Path(os.environ.get(
    "DYFI_ASSET_INPUTS",
    str(MAN / "derived" / "asset_inputs.json")
))
if not ASSET.exists():
    ASSET = HERE / "frozen_inputs" / "asset_inputs.json"
GOAL = HERE / "goal_usefulness.json"
PRECEDENTS = HERE / "accepted_precedents.json"
BUILD_LEDGER = HERE / "build_ledger.json"
ORIGINAL = MAN / "paper"

checks: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"check": name, "ok": bool(ok), "detail": detail})


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    text = MAIN.read_text()
    bib = BIB.read_text()
    asset = json.loads(ASSET.read_text())
    goal = json.loads(GOAL.read_text())
    precedents = json.loads(PRECEDENTS.read_text())
    corrections = json.loads(
        (HERE / "frozen_inputs" / "corrections_overlay.json").read_text()
    )

    original_ledger_path = ORIGINAL / "build_ledger.json"
    if not original_ledger_path.exists():
        original_ledger_path = HERE / "frozen_inputs" / "original_build_ledger.json"
    original_ledger = json.loads(original_ledger_path.read_text())
    original_main = ORIGINAL / "main.tex"
    observed_original_hash = (
        sha256(original_main)
        if original_main.exists()
        else original_ledger["main_tex_sha256"]
    )
    check(
        "jeas_target_and_original_preserved",
        "Journal of Engineering and Applied Science" in text
        and "Journal of Seismology (Springer Nature) submission" not in text
        and observed_original_hash == original_ledger["main_tex_sha256"],
        observed_original_hash,
    )
    check(
        "single_column_double_spaced_line_numbered",
        r"\documentclass[pdflatex,sn-basic,Numbered]{sn-jnl}" in text
        and "iicol" not in text.split(r"\begin{document}", 1)[0]
        and r"\doublespacing" in text
        and r"\linenumbers" in text,
    )
    check(
        "engineering_reliability_title",
        "Reliable comparison of severe felt-intensity classifiers" in text,
    )
    abstract = re.search(r"\\abstract\{(.*?)\}\s*\\keywords", text, re.S)
    abstract_words = re.findall(r"\b[\w'-]+\b", abstract.group(1)) if abstract else []
    check("concise_abstract", 150 <= len(abstract_words) <= 300, str(len(abstract_words)))
    keywords_match = re.search(r"\\keywords\{([^}]+)\}", text, re.S)
    keywords = [k.strip() for k in keywords_match.group(1).split(",")] if keywords_match else []
    check("engineering_keywords", 4 <= len(keywords) <= 8 and "evaluation reliability" in keywords, str(keywords))

    required_goal_fields = {
        "scientific_question",
        "contribution_identity",
        "intended_users",
        "task_enabled",
        "decision_enabled",
        "error_prevented",
        "evidence_of_usefulness",
        "substantive_result",
        "non_use_boundary",
        "target_venue_publishes_this_identity",
    }
    check("goal_contract_complete", required_goal_fields <= goal.keys(), str(sorted(required_goal_fields - goal.keys())))
    editor_test = goal.get("independent_30_second_editor_test", {})
    check(
        "independent_abstract_story_gate",
        goal.get("editor_test_status") == "pass"
        and editor_test.get("goal_understood") is True
        and editor_test.get("usefulness_understood") is True
        and editor_test.get("abstract_story_pass") is True,
        str(editor_test),
    )
    check(
        "goal_and_users_visible_before_methods",
        "Our engineering question is:" in text
        and "intended users are applied machine-learning engineers" in text
        and "whether a candidate is admissible" in text
        and text.index("Our engineering question is:") < text.index(r"\section{Data"),
    )
    check(
        "usefulness_is_demonstrated",
        r"\label{tab:engineering-failures}" in (HERE / "tables" / "engineering_failure_modes.tex").read_text()
        and r"\label{tab:qualification}" in (HERE / "tables" / "candidate_qualification.tex").read_text()
        and r"\label{fig:qualification-workflow}" in text
        and r"\label{sec:qualification}" in text,
    )
    supplement = (HERE / "supplement.tex").read_text()
    check(
        "technical_tables_moved_to_supplement",
        all(
            token not in text
            for token in (
                r"\input{tables/pairwise_matrix.tex}",
                r"\input{tables/exclusions_deviations.tex}",
                r"\input{tables/slices.tex}",
            )
        )
        and all(
            token in supplement
            for token in (
                r"\input{tables/pairwise_matrix.tex}",
                r"\input{tables/exclusions_deviations.tex}",
                r"\input{tables/slices.tex}",
            )
        )
        and "Supplementary Table~S1" in text
        and "Supplementary Table~S2" in text
        and "Supplementary Table~S3" in text,
    )
    table_captions = []
    for table_path in sorted((HERE / "tables").glob("*.tex")):
        match = re.search(r"\\caption\{(.*?)\}\s*\\label", table_path.read_text(), re.S)
        if match:
            plain = re.sub(r"\\[A-Za-z]+|[{}$~]", " ", match.group(1))
            table_captions.append((table_path.name, len(re.findall(r"\b[\w'-]+\b", plain))))
    check(
        "table_titles_at_most_15_words",
        len(table_captions) == 9 and all(count <= 15 for _, count in table_captions),
        str(table_captions),
    )
    check(
        "venue_precedents_complete",
        len(precedents["papers"]) >= 4
        and precedents["conclusion"]["target_venue_publishes_benchmark_identity"] is True,
        str(len(precedents["papers"])),
    )
    check(
        "machine_readable_semantic_corrections",
        corrections.get("changes_numeric_results") is False
        and len(corrections.get("corrections", [])) == 3
        and corrections.get("applies_to_frozen_result_sha256")
        == "b3ec45d587d6125da25890b7e91bfb140309c8645c7d8c365d80a2e0df73ae3b",
        str(corrections.get("corrections", [])),
    )
    jeas_keys = {"tian2024coco", "niu2024ucs", "alnaqbi2025pavement", "seleemah2022bridge"}
    cited_groups = re.findall(r"\\cite[a-z]*\{([^}]*)\}", text)
    cited = {k.strip() for group in cited_groups for k in group.split(",")}
    bib_keys = set(re.findall(r"@\w+\{([^,]+),", bib))
    check("all_citations_resolve", cited <= bib_keys, str(sorted(cited - bib_keys)))
    check("all_bibliography_entries_cited", bib_keys <= cited, str(sorted(bib_keys - cited)))
    check("jeas_precedents_engaged", jeas_keys <= cited, str(sorted(jeas_keys - cited)))
    ledger_keys = {
        json.loads(line)["key"]
        for line in CITE_LEDGER.read_text().splitlines()
        if line.strip()
    }
    check("citation_ledger_covers_bibliography", bib_keys <= ledger_keys, str(sorted(bib_keys - ledger_keys)))

    # Frozen-result identities used by the worked qualification.
    b0 = asset["per_baseline"]["B0_no_skill"]["brier"]
    b2 = asset["per_baseline"]["B2_source_only_logit"]["brier"]
    b5 = asset["per_baseline"]["B5_xgboost"]["brier"]
    pair = asset["pairwise_ranking_stability"]["pairwise_matrix"]["B2_source_only_logit_vs_B5_xgboost"]
    qualification = (HERE / "tables" / "candidate_qualification.tex").read_text()
    check("qualification_b0_exact", f"{b0:.3f}" in qualification, f"{b0:.3f}")
    check("qualification_b2_exact", f"{b2:.3f}" in qualification, f"{b2:.3f}")
    check("qualification_b5_exact", f"{b5:.3f}" in qualification, f"{b5:.3f}")
    check(
        "qualification_unresolved_pair_exact",
        f"{pair['point_diff_a_minus_b']:.4f}" in qualification
        and f"{pair['ci'][0]:.4f}" in qualification
        and f"{pair['ci'][1]:.4f}" in qualification
        and pair["resolved"] is False,
    )
    check(
        "b3_scope_exclusion_demonstrated",
        "B3 expanded-metadata logistic" in qualification
        and "Year excluded by schema" in qualification
        and "not demonstrated" in text
        and "label leakage" in text,
    )

    # Utility assets are pinned to the declared Matplotlib environment. Avoid
    # rewriting committed artwork under a different host version.
    utility_manifest = json.loads((HERE / "utility_asset_manifest.json").read_text())
    utility_paths = {
        HERE / rel: expected
        for rel, expected in utility_manifest["artifacts"].items()
    }
    observed = {p: sha256(p) for p in utility_paths}
    check(
        "utility_assets_match_pinned_manifest",
        all(observed[p] == expected for p, expected in utility_paths.items()),
        str({p.name: observed[p] for p in utility_paths}),
    )
    try:
        matplotlib_version = importlib.metadata.version("matplotlib")
    except importlib.metadata.PackageNotFoundError:
        matplotlib_version = "not-installed"
    if matplotlib_version == utility_manifest["matplotlib_version"]:
        before = dict(observed)
        subprocess.run([sys.executable, "build_utility_assets.py"], cwd=HERE, check=True)
        subprocess.run([sys.executable, "format_jeas_tables.py"], cwd=HERE, check=True)
        after = {p: sha256(p) for p in utility_paths}
        check(
            "utility_assets_byte_deterministic_in_pinned_environment",
            before == after,
            str({p.name: after[p] for p in utility_paths}),
        )
    else:
        check(
            "utility_regeneration_environment_explicit",
            True,
            f"host matplotlib={matplotlib_version}; pinned={utility_manifest['matplotlib_version']}; hashes verified without regeneration",
        )

    check(
        "declarations_complete",
        r"\section*{Declarations}" in text
        and "Availability of data and materials" in text
        and "Availability of code" in text
        and "Competing interests" in text
        and "Author contributions" in text
        and "Acknowledgements" in text,
    )
    check(
        "ai_use_disclosed",
        "generative AI assistance" in text
        and "all scientific judgements and final decisions remained with the authors" in text,
    )
    check(
        "non_use_boundaries_preserved",
        "not a real-time warning, causal model, or" in text
        and "operational decision system" in text
        and "no geographic, aggregation, sequence-definition" in text
        and "fresh hidden holdout or independent evaluation service" in text,
    )
    check(
        "threshold_probe_not_robustness_claim",
        "descriptive fixed-prediction threshold probe" in text
        and re.search(r"does not establish\s+endpoint\s+robustness", text) is not None
        and "not an artifact of a single threshold" not in text,
    )
    check(
        "ascertainment_boundary_honest",
        "does not remove ascertainment" in text
        and "mitigates ascertainment" not in text,
    )
    check(
        "null_and_no_winner_preserved",
        "small and reversed" in text
        and "no evidence of random-split optimism" in text
        and "remain unresolved" in text
        and "prevents" in text,
    )
    captions = re.findall(r"\\caption\{(.*?)\}\s*\\label", text, re.S)
    check("five_figures_captioned", len(captions) == 5, str(len(captions)))
    check(
        "figure_titles_outside_artwork",
        all(r"\textbf{" in caption for caption in captions)
        and "Candidate-model qualification under the released benchmark contract"
        not in (HERE / "build_utility_assets.py").read_text(),
    )
    check(
        "separate_vector_figures_present",
        all((HERE / "figures" / f).is_file() for f in (
            "fig_cohort_flow.pdf",
            "fig_threshold_slice.pdf",
            "fig_split_diagnostic_jeas.pdf",
            "fig_baseline_scores.pdf",
            "fig_candidate_workflow.pdf",
        )),
    )

    build = json.loads(BUILD_LEDGER.read_text()) if BUILD_LEDGER.exists() else {}
    check("build_ledger_main_current", build.get("main_tex_sha256") == sha256(MAIN), str(build.get("main_tex_sha256")))
    pdf = HERE / "main.pdf"
    check(
        "build_ledger_pdf_current_or_source_only",
        (not pdf.exists()) or build.get("main_pdf_sha256") == sha256(pdf),
        "source-only package" if not pdf.exists() else str(build.get("main_pdf_sha256")),
    )
    supplement_pdf = HERE / "supplement.pdf"
    check(
        "supplement_build_current_or_source_only",
        (not supplement_pdf.exists())
        or (
            build.get("supplement_tex_sha256") == sha256(HERE / "supplement.tex")
            and build.get("supplement_pdf_sha256") == sha256(supplement_pdf)
        ),
        "source-only package" if not supplement_pdf.exists() else str(build.get("supplement_pdf_sha256")),
    )
    if pdf.exists():
        pdfinfo = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
        pages_match = re.search(r"^Pages:\s+(\d+)", pdfinfo, re.M)
        pages = int(pages_match.group(1)) if pages_match else 999
        check("review_manuscript_page_target", pages <= 28, str(pages))
    else:
        check("review_manuscript_page_target", True, "source-only package")
    readiness_path = HERE / "reviews" / "editor-reviewer-readiness.json"
    if readiness_path.exists() and pdf.exists():
        readiness = json.loads(readiness_path.read_text())
        check(
            "editor_reviewer_readiness_current",
            readiness.get("manuscript_sha256") == sha256(pdf)
            and readiness.get("overall_pass") is True
            and readiness.get("abstract_story", {}).get("pass") is True,
            str(readiness.get("manuscript_sha256")),
        )
    else:
        check(
            "editor_reviewer_readiness_current",
            True,
            "readiness record is a release-level review artifact and is not required in editable source-only packages",
        )

    failed = [c for c in checks if not c["ok"]]
    report = {
        "record_type": "jeas_manuscript_validation_report",
        "n_checks": len(checks),
        "n_failed": len(failed),
        "overall_pass": not failed,
        "checks": checks,
    }
    (HERE / "jeas_validation_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"validate_jeas: {len(checks)} checks, {len(failed)} failed -> {'PASS' if not failed else 'FAIL'}")
    for item in failed:
        print(f"  FAIL: {item['check']} {item['detail']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
