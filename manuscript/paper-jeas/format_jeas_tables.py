#!/usr/bin/env python3
"""Apply deterministic JEAS review-layout wrappers to wide generated tables."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLES = HERE / "tables"
WIDE = {
    "cohort_roles.tex",
    "baseline_performance.tex",
    "candidate_qualification.tex",
}


def wrap(path: Path) -> None:
    text = path.read_text()
    if r"\resizebox{\textwidth}{!}{%" in text:
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
    for name in sorted(WIDE):
        wrap(TABLES / name)
        print(f"wrapped {name}")


if __name__ == "__main__":
    main()
