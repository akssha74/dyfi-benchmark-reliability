#!/usr/bin/env python3
"""Apply deterministic JEAS review-layout wrappers to wide generated tables."""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLES = HERE / "tables"
WIDE = {
    "cohort_roles.tex",
    "baseline_performance.tex",
}
CAPTIONS = {
    "cohort_roles.tex": "Cohort accounting and outcome-independent role assignment",
    "endpoint_threshold_sensitivity.tex": "Endpoint-threshold probe using fixed source-only probabilities",
    "baseline_performance.tex": "Temporal-holdout performance of fixed baseline models",
    "leakage_gap.tex": "Split-assignment performance of the fixed diagnostic",
    "pairwise_matrix.tex": "Paired Brier-score comparisons among admissible baselines",
    "exclusions_deviations.tex": "Protocol exclusions, deviations, and interpretation boundaries",
    "slices.tex": "Temporal and geographic summaries within the temporal holdout",
}


def wrap(path: Path) -> None:
    text = path.read_text()
    caption = CAPTIONS.get(path.name)
    if caption:
        text = re.sub(
            r"\\caption\{.*?\}\s*\\label",
            rf"\\caption{{{caption}}}\n\\label",
            text,
            count=1,
            flags=re.S,
        )
    if path.name == "baseline_performance.tex":
        text = text.replace(
            r"Table~\ref{tab:exclusions}",
            r"Supplementary Table~S2",
        )
    if path.name not in WIDE:
        path.write_text(text)
        return
    if r"\resizebox{\textwidth}{!}{%" in text:
        path.write_text(text)
        return
    start = text.index(r"\begin{tabular}")
    end_token = r"\end{tabular}"
    end = text.index(end_token, start) + len(end_token)
    text = (
        text[:start]
        + r"\resizebox{\textwidth}{!}{%"
        + "\n"
        + text[start:end]
        + "\n}%\n"
        + text[end:]
    )
    path.write_text(text)


def main() -> None:
    for name in sorted(set(CAPTIONS) | WIDE):
        wrap(TABLES / name)
        print(f"formatted {name}")


if __name__ == "__main__":
    main()
