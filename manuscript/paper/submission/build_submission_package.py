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
        (PAPER / "main.tex", pathlib.Path("main.tex")),
        (PAPER / "references.bib", pathlib.Path("references.bib")),
        (PAPER / "sn-jnl.cls", pathlib.Path("sn-jnl.cls")),
        (PAPER / "sn-basic.bst", pathlib.Path("sn-basic.bst")),
    ]
    files += [
        (p, pathlib.Path("tables") / p.name)
        for p in sorted((PAPER / "tables").glob("*.tex"))
    ]
    files += [
        (p, pathlib.Path("figures") / p.name)
        for p in sorted((PAPER / "figures").glob("*.pdf"))
    ]

    with zipfile.ZipFile(SOURCE_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
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
        "Requested article type: Data or Software Paper; use Original Paper if "
        "Snapp does not expose that label.\n"
        "The source ZIP compiles with the Springer Nature sn-jnl [iicol] template.\n\n"
        f"main.pdf SHA-256: {sha256(PAPER / 'main.pdf')}\n"
        f"source ZIP SHA-256: {sha256(SOURCE_ZIP)}\n"
    )
    (UPLOAD / "README_UPLOAD.txt").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    build()
