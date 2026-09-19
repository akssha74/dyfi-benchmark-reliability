"""Build the Journal of Seismology upload bundle deterministically."""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
PAPER = HERE.parent
UPLOAD = HERE / "journal_of_seismology_upload"
SOURCE_ZIP = UPLOAD / "manuscript_source.zip"
FIXED_TIME = (2010, 1, 1, 0, 0, 0)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    if UPLOAD.exists():
        shutil.rmtree(UPLOAD)
    UPLOAD.mkdir(parents=True)

    files: list[tuple[pathlib.Path, pathlib.Path]] = [
        (PAPER / "references.bib", pathlib.Path("references.bib")),
        (PAPER / "sn-jnl.cls", pathlib.Path("sn-jnl.cls")),
        (PAPER / "sn-basic.bst", pathlib.Path("sn-basic.bst")),
    ]
    files += [
        (p, pathlib.Path("tables") / p.name)
        for p in sorted((PAPER / "tables").glob("*.tex"))
    ]
    figure_map = {
        "fig_cohort_flow.pdf": "Fig1.pdf",
        "fig_threshold_slice.pdf": "Fig2.pdf",
        "fig_leakage_split.pdf": "Fig3.pdf",
        "fig_baseline_scores.pdf": "Fig4.pdf",
    }
    files += [
        (PAPER / "figures" / source, pathlib.Path("figures") / target)
        for source, target in figure_map.items()
    ]

    with zipfile.ZipFile(SOURCE_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        main_text = (PAPER / "main.tex").read_text(encoding="utf-8")
        for source, target in figure_map.items():
            main_text = main_text.replace(source, target)
        main_info = zipfile.ZipInfo("main.tex", FIXED_TIME)
        main_info.compress_type = zipfile.ZIP_DEFLATED
        main_info.external_attr = 0o100644 << 16
        zf.writestr(main_info, main_text.encode("utf-8"))
        for source, archive_path in files:
            info = zipfile.ZipInfo(archive_path.as_posix(), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, source.read_bytes())

    shutil.copy2(PAPER / "main.pdf", UPLOAD / "main.pdf")
    shutil.copy2(HERE / "cover_letter.pdf", UPLOAD / "cover_letter.pdf")
    shutil.copy2(HERE / "article_highlights.txt", UPLOAD / "article_highlights.txt")

    readme = (
        "Journal of Seismology upload files\n"
        "==================================\n\n"
        "1. manuscript_source.zip — LaTeX source, class/style, generated tables, "
        "and vector figures\n"
        "2. main.pdf — compiled manuscript for review\n"
        "3. cover_letter.pdf — upload separately as the cover letter\n"
        "4. article_highlights.txt — three journal-required highlights\n\n"
        "Article type: Research Article documenting a public data/software "
        "benchmark resource.\n"
        "The source ZIP compiles with the Springer Nature sn-jnl [iicol] template.\n\n"
        f"main.pdf SHA-256: {sha256(PAPER / 'main.pdf')}\n"
        f"source ZIP SHA-256: {sha256(SOURCE_ZIP)}\n"
    )
    (UPLOAD / "README_UPLOAD.txt").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    build()
