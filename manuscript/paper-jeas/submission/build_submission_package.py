"""Build the Journal of Engineering and Applied Science upload bundle."""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
PAPER = HERE.parent
UPLOAD = HERE / "journal_of_engineering_and_applied_science_upload"
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
        (PAPER / "build_utility_assets.py", pathlib.Path("build_utility_assets.py")),
        (PAPER / "format_jeas_tables.py", pathlib.Path("format_jeas_tables.py")),
        (PAPER / "generate_ledgers.py", pathlib.Path("generate_ledgers.py")),
        (PAPER / "validate_jeas.py", pathlib.Path("validate_jeas.py")),
        (PAPER / "goal_usefulness.json", pathlib.Path("goal_usefulness.json")),
        (PAPER / "accepted_precedents.json", pathlib.Path("accepted_precedents.json")),
        (PAPER / "citation_ledger.jsonl", pathlib.Path("citation_ledger.jsonl")),
        (PAPER / "claim_ledger.jsonl", pathlib.Path("claim_ledger.jsonl")),
        (PAPER / "build_ledger.json", pathlib.Path("build_ledger.json")),
        (PAPER / "jeas_validation_report.json", pathlib.Path("jeas_validation_report.json")),
        (PAPER / "frozen_inputs" / "asset_inputs.json", pathlib.Path("frozen_inputs") / "asset_inputs.json"),
        (PAPER / "frozen_inputs" / "original_build_ledger.json", pathlib.Path("frozen_inputs") / "original_build_ledger.json"),
    ]
    files += [
        (p, pathlib.Path("tables") / p.name)
        for p in sorted((PAPER / "tables").glob("*.tex"))
    ]
    figure_map = {
        "fig_candidate_workflow.pdf": "Figure_1.pdf",
        "fig_cohort_flow.pdf": "Figure_2.pdf",
        "fig_threshold_slice.pdf": "Figure_3.pdf",
        "fig_leakage_split.pdf": "Figure_4.pdf",
        "fig_baseline_scores.pdf": "Figure_5.pdf",
    }
    files += [
        (PAPER / "figures" / source, pathlib.Path("figures") / source)
        for source in figure_map
    ]
    files.append((
        PAPER / "figures" / "fig_candidate_workflow.png",
        pathlib.Path("figures") / "fig_candidate_workflow.png",
    ))

    with zipfile.ZipFile(SOURCE_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        main_text = (PAPER / "main.tex").read_text(encoding="utf-8")
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
    shutil.copy2(HERE / "figure_alt_text.txt", UPLOAD / "PORTAL_ALT_TEXT.txt")
    for source, target in figure_map.items():
        shutil.copy2(PAPER / "figures" / source, UPLOAD / target)

    readme = (
        "Journal of Engineering and Applied Science upload files\n"
        "=======================================================\n\n"
        "Upload manuscript_source.zip as the editable manuscript source.\n"
        "Upload Figure_1.pdf through Figure_5.pdf as separate figure files if "
        "the portal requests artwork separately.\n"
        "Upload cover_letter.pdf in the cover-letter slot.\n"
        "PORTAL_ALT_TEXT.txt is copy/paste text for accessibility fields; upload "
        "it only if the portal explicitly requests an alt-text file.\n"
        "main.pdf is the author-verified reference proof; upload it only if the "
        "portal explicitly requests a PDF in addition to editable source.\n\n"
        "Article type: Research Article on engineering model-evaluation reliability.\n"
        "The source ZIP uses the Springer Nature sn-jnl template, double spacing, "
        "continuous line numbering, editable tables, and vector figures.\n\n"
        f"main.pdf SHA-256: {sha256(PAPER / 'main.pdf')}\n"
        f"cover_letter.pdf SHA-256: {sha256(HERE / 'cover_letter.pdf')}\n"
        f"source ZIP SHA-256: {sha256(SOURCE_ZIP)}\n"
    )
    (UPLOAD / "README_UPLOAD.txt").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    build()
