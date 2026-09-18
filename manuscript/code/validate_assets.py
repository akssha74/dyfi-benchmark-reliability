"""Validate the manuscript-asset build.

Checks, and records into manuscript/validation_report.json:
  1. Determinism: run generate_all.sh TWICE and require byte-identical sha256 for
     every registered artifact (and identical asset_manifest.json).
  2. Arithmetic: independently recompute cohort partition, confusion totals,
     accuracy, holdout prevalence, threshold prevalence, leakage gaps, and the
     vs-B0 pairwise cells from the frozen artifacts + generated CSVs; require
     agreement.
  3. Bit-identity: reconstructed predictions_digest == recorded digest.
  4. File integrity: every JSON parses; every CSV has a rectangular shape; every
     PNG has the PNG signature; every SVG has an <svg> root; every table .tex has
     matching table/tabular environments.
  5. Lint: pyflakes over all generator/validator modules (must be clean).

Run in the pinned analytics venv:  code/.venv/bin/python manuscript/code/validate_assets.py
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
from typing import Dict, List

import asset_common as ac

MAN = os.path.join(ac.ROOT, "manuscript")
DERIVED = os.path.join(MAN, "derived")
TABLES = os.path.join(MAN, "tables")
FIGS = os.path.join(MAN, "figures")
REPORT = os.path.join(MAN, "validation_report.json")

PY_A = os.path.join(ac.ROOT, "code", ".venv", "bin", "python")
PY_F = os.path.join(ac.ROOT, "manuscript", ".venv-fig", "bin", "python")
GEN = os.path.join(MAN, "code", "generate_all.sh")

MODULES = [
    "asset_common.py", "build_pairwise_ranking.py", "build_f1_disclosure.py",
    "build_asset_inputs.py", "build_tables.py", "build_asset_ledger.py",
    "validate_assets.py",
]


def _load_manifest_hashes() -> Dict[str, str]:
    m = ac.common.load_json(os.path.join(MAN, "asset_manifest.json"))
    h = dict(m["artifacts"])
    h["__asset_manifest__"] = ac.sha256_file(os.path.join(MAN, "asset_manifest.json"))
    h["__asset_ledger__"] = m["asset_ledger"]["sha256"]
    return h


def check_determinism() -> Dict[str, object]:
    subprocess.run(["bash", GEN], check=True, cwd=ac.ROOT,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    h1 = _load_manifest_hashes()
    subprocess.run(["bash", GEN], check=True, cwd=ac.ROOT,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    h2 = _load_manifest_hashes()
    diffs = [k for k in h1 if h1.get(k) != h2.get(k)]
    return {
        "n_artifacts": len(h1),
        "byte_identical_across_two_runs": len(diffs) == 0,
        "differing_artifacts": diffs,
    }


def _read_csv(rel: str):
    with open(os.path.join(ac.ROOT, rel), newline="") as f:
        return list(csv.reader(f))


def check_arithmetic() -> Dict[str, object]:
    checks: List[Dict[str, object]] = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    D = ac.common.load_json(os.path.join(DERIVED, "asset_inputs.json"))
    cf = D["cohort_flow"]
    roles = cf["roles"]
    partition = roles["train"]["n"] + roles["development"]["n"] + roles["external_temporal_holdout"]["n"] + cf["temporal_straddle_excluded"]
    add("cohort_partition_sums_to_eligible", partition == cf["n_eligible_events"],
        f"{partition} == {cf['n_eligible_events']}")
    add("construction_equals_train_plus_dev",
        cf["construction_total"]["n"] == roles["train"]["n"] + roles["development"]["n"])

    # confusion totals + accuracy from generated baseline CSV.
    rows = _read_csv("manuscript/tables/baseline_performance.csv")
    hdr = rows[0]
    ix = {c: i for i, c in enumerate(hdr)}
    for r in rows[1:]:
        bid = r[ix["baseline"]]
        tp, fp, tn, fn = (int(r[ix[k]]) for k in ("tp", "fp", "tn", "fn"))
        add(f"{bid}.confusion_sums_to_430", tp + fp + tn + fn == 430, f"{tp+fp+tn+fn}")
        add(f"{bid}.positives_151", tp + fn == 151)
        add(f"{bid}.negatives_279", tn + fp == 279)
        acc_recompute = round((tp + tn) / 430.0, 12)
        add(f"{bid}.accuracy_matches", abs(float(r[ix["accuracy"]]) - acc_recompute) <= 1e-9,
            f"{r[ix['accuracy']]} vs {acc_recompute}")

    add("holdout_prevalence_151_over_430",
        abs(roles["external_temporal_holdout"]["prevalence"] - 151.0 / 430.0) <= 1e-12)

    # threshold prevalence recompute from released holdout rows.
    ev_rows = ac.common.read_csv(ac.EVENT_TABLE)
    hold = [r for r in ev_rows if r["role"] == "external_temporal_holdout"]
    for thr in (5.5, 6.0, 6.5):
        pos = sum(1 for r in hold if float(r["max_cdi"]) >= thr)
        rec = D["endpoint"]["threshold_sensitivity"][f"{thr}"]["prevalence"]
        add(f"threshold_{thr}_prevalence", abs(pos / len(hold) - rec) <= 1e-9,
            f"{pos}/{len(hold)} vs {rec}")

    # leakage gap arithmetic.
    lk = D["leakage_inflation_headline"]
    ps = lk["per_scheme"]
    add("brier_gap_seq_minus_random",
        abs((ps["sequence_grouped"]["brier"] - ps["random_event"]["brier"]) - lk["brier_inflation_seq_minus_random"]) <= 1e-9)
    add("auroc_gap_random_minus_seq",
        abs((ps["random_event"]["auroc"] - ps["sequence_grouped"]["auroc"]) - lk["auroc_inflation_random_minus_seq"]) <= 1e-9)

    # pairwise vs-B0 equals frozen ranking_vs_reference (sign-flipped orientation).
    run = ac.load_run_result()
    rvr = run["result_core"]["report"]["evaluation"]["ranking_vs_reference"]
    pw = ac.common.load_json(os.path.join(DERIVED, "pairwise_ranking_stability.json"))["pairwise_matrix"]
    for cand_key, frozen in rvr.items():
        cand = cand_key.replace("_vs_B0_no_skill", "")
        key = f"B0_no_skill_vs_{cand}"
        cell = pw[key]
        add(f"pairwise_vs_B0[{cand}]_point_negates_frozen",
            abs(cell["point_diff_a_minus_b"] + frozen["point_diff_a_minus_b"]) <= 1e-9,
            f"{cell['point_diff_a_minus_b']} vs -({frozen['point_diff_a_minus_b']})")
        add(f"pairwise_vs_B0[{cand}]_resolved_matches", cell["resolved"] == frozen["resolved"])

    # predictions digest bit-identity.
    rp = ac.reconstruct_frozen_predictions()
    add("predictions_digest_bit_identical",
        rp["predictions_digest"] == rp["recorded_predictions_digest"],
        rp["predictions_digest"])

    return {"all_ok": all(c["ok"] for c in checks),
            "n_checks": len(checks),
            "n_failed": sum(1 for c in checks if not c["ok"]),
            "checks": checks}


def check_files() -> Dict[str, object]:
    issues: List[str] = []
    manifest = ac.common.load_json(os.path.join(MAN, "asset_manifest.json"))
    for rel in sorted(manifest["artifacts"]):
        full = os.path.join(ac.ROOT, rel)
        if not os.path.isfile(full):
            issues.append(f"missing:{rel}")
            continue
        if rel.endswith(".json"):
            try:
                json.load(open(full))
            except Exception as exc:
                issues.append(f"bad_json:{rel}:{exc}")
        elif rel.endswith(".jsonl"):
            for i, line in enumerate(open(full)):
                if line.strip():
                    try:
                        json.loads(line)
                    except Exception as exc:
                        issues.append(f"bad_jsonl:{rel}:{i}:{exc}")
        elif rel.endswith(".csv"):
            rows = _read_csv(rel)
            if rows:
                ncol = len(rows[0])
                if any(len(r) != ncol for r in rows):
                    issues.append(f"ragged_csv:{rel}")
        elif rel.endswith(".png"):
            with open(full, "rb") as f:
                if f.read(8) != b"\x89PNG\r\n\x1a\n":
                    issues.append(f"bad_png:{rel}")
        elif rel.endswith(".svg"):
            head = open(full, "r", encoding="utf-8").read(4096)
            if "<svg" not in head:
                issues.append(f"bad_svg:{rel}")
        elif rel.endswith(".tex"):
            txt = open(full, encoding="utf-8").read()
            if txt.count(r"\begin{table}") != txt.count(r"\end{table}") or \
               txt.count(r"\begin{tabular}") != txt.count(r"\end{tabular}"):
                issues.append(f"unbalanced_tex_env:{rel}")
    return {"all_ok": len(issues) == 0, "n_artifacts": len(manifest["artifacts"]),
            "issues": issues}


def check_lint() -> Dict[str, object]:
    paths_a = [os.path.join(MAN, "code", m) for m in MODULES]
    out_a = subprocess.run([PY_A, "-m", "pyflakes", *paths_a],
                           capture_output=True, text=True)
    out_f = subprocess.run([PY_F, "-m", "pyflakes", os.path.join(MAN, "code", "build_figures.py")],
                           capture_output=True, text=True)
    findings = [l for l in (out_a.stdout + out_a.stderr + out_f.stdout + out_f.stderr).splitlines() if l.strip()]
    return {"clean": len(findings) == 0, "findings": findings}


def build() -> Dict[str, object]:
    determinism = check_determinism()
    arithmetic = check_arithmetic()
    files = check_files()
    lint = check_lint()
    overall = (determinism["byte_identical_across_two_runs"] and arithmetic["all_ok"]
               and files["all_ok"] and lint["clean"])
    report = {
        "record_type": "manuscript_asset_validation_report",
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "validated_at": "2026-09-01",
        "overall_pass": overall,
        "determinism": determinism,
        "arithmetic": arithmetic,
        "file_integrity": files,
        "lint": lint,
    }
    ac.write_json_sorted(REPORT, report)
    return {
        "overall_pass": overall,
        "determinism_ok": determinism["byte_identical_across_two_runs"],
        "arithmetic_ok": arithmetic["all_ok"],
        "files_ok": files["all_ok"],
        "lint_clean": lint["clean"],
        "report": os.path.relpath(REPORT, ac.ROOT),
    }


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
