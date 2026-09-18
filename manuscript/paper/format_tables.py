#!/usr/bin/env python3
"""Deterministic, value-preserving venue formatting of the generated tables.

Reads the canonical generated table sources from ``manuscript/tables/*.tex`` and
writes venue-formatted copies into ``manuscript/paper/tables/*.tex``. The only
transforms are LAYOUT-ONLY and never touch a result-bearing number:

  * internal baseline identifiers are replaced by reader-facing model names;
  * wide tables span both columns; and
  * spacing is tuned without changing any result-bearing value.

No Brier/AUROC/CI/count/hash value is altered. Running this script is idempotent
and reproduces the exact paper/tables/*.tex used by the build.
"""
from __future__ import annotations
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / "tables"
DST = HERE / "tables"

# Internal -> reader-facing model labels.
PAIRWISE_MAP = {
    r"B0\_no\_skill": "B0",
    r"B1\_magnitude\_only\_logit": "B1",
    r"B2\_source\_only\_logit": "B2",
    r"B4\_random\_forest": "B4",
    r"B5\_xgboost": "B5",
}
BASELINE_MAP = {
    r"B0\_no\_skill": "B0 (no-skill)",
    r"B1\_magnitude\_only\_logit": "B1 (magnitude-only logistic)",
    r"B2\_source\_only\_logit": "B2 (source-only logistic)",
    r"B4\_random\_forest": "B4 (random forest)",
    r"B5\_xgboost": "B5 (XGBoost)",
}


def _apply(text: str, mapping: dict[str, str]) -> str:
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text


def format_all() -> list[str]:
    DST.mkdir(parents=True, exist_ok=True)
    written = []
    for src in sorted(SRC.glob("*.tex")):
        text = src.read_text()
        name = src.name
        # In two-column iicol mode, tables span both columns cleanly via table*
        text = text.replace("\\begin{table}[t]", "\\begin{table*}[t]").replace("\\end{table}", "\\end{table*}")
        if name == "pairwise_matrix.tex":
            text = _apply(text, PAIRWISE_MAP)
        elif name == "baseline_performance.tex":
            text = _apply(text, BASELINE_MAP)
            text = text.replace(
                "\\label{tab:baselines}\n\\begin{tabular}{lccccc c}",
                "\\label{tab:baselines}\n\\setlength{\\tabcolsep}{4.5pt}\n"
                "\\begin{tabular}{lccccc c}",
            )
        elif name in {"exclusions_deviations.tex", "reproducibility_manifest.tex"}:
            text = text.replace(
                "\\label{tab:", "\\renewcommand{\\arraystretch}{1.08}\n\\label{tab:", 1
            )
        (DST / name).write_text(text)
        written.append(name)
    return written


if __name__ == "__main__":
    files = format_all()
    print(f"formatted {len(files)} tables into {DST}")
    for f in files:
        print(" -", f)
