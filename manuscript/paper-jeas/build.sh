#!/usr/bin/env bash
# Deterministic, self-contained build of the JEAS manuscript.
#
# Steps (all scripted, no hand-editing):
#   1. Generate JEAS engineering-use assets from frozen inputs.
#   2. Regenerate the venue-formatted table inputs from the canonical, validated
#      generated tables under manuscript/tables/ (layout-only transform).
#   3. Fit wide generated tables to the single-column review layout.
#   4. Copy the deterministic figures (byte-identical to the validated assets).
#   5. Compile main.tex -> main.pdf with tectonic (auto reruns bibtex + passes).
#   6. Compile supplement.tex -> supplement.pdf.
#
# Requires: python3, tectonic. No network write, no DOI mint, no submission.
set -euo pipefail
cd "$(dirname "$0")"
export SOURCE_DATE_EPOCH=1262304000

echo "[1/6] generating JEAS engineering-use assets ..."
mkdir -p frozen_inputs
if [[ -f ../derived/asset_inputs.json ]]; then
  cp -f ../derived/asset_inputs.json frozen_inputs/asset_inputs.json
fi
if [[ -f ../paper/build_ledger.json ]]; then
  cp -f ../paper/build_ledger.json frozen_inputs/original_build_ledger.json
fi
if [[ -f ../../bundle/release/CORRECTIONS_OVERLAY.json ]]; then
  cp -f ../../bundle/release/CORRECTIONS_OVERLAY.json frozen_inputs/corrections_overlay.json
fi
UTILITY_PYTHON="${DYFI_FIGURE_PYTHON:-}"
if [[ -z "$UTILITY_PYTHON" && -x ../.venv-fig/bin/python ]]; then
  UTILITY_PYTHON="../.venv-fig/bin/python"
fi
if [[ -z "$UTILITY_PYTHON" ]]; then
  UTILITY_PYTHON="python3"
fi
"$UTILITY_PYTHON" build_utility_assets.py

echo "[2/6] formatting tables from canonical assets ..."
python3 format_tables.py

echo "[3/6] fitting wide tables to review layout ..."
python3 format_jeas_tables.py

echo "[4/6] syncing figures ..."
mkdir -p figures
cp -f ../figures/*.png figures/
cp -f ../figures/*.pdf figures/

echo "[5/6] compiling main manuscript with tectonic ..."
tectonic --keep-logs main.tex >/dev/null 2>&1

echo "[6/6] compiling supplementary information ..."
tectonic --keep-logs supplement.tex >/dev/null 2>&1

pages=$(pdfinfo main.pdf 2>/dev/null | awk '/Pages:/ {print $2}')
supp_pages=$(pdfinfo supplement.pdf 2>/dev/null | awk '/Pages:/ {print $2}')
echo "OK: main.pdf built (${pages:-?} pages); supplement.pdf (${supp_pages:-?} pages)."
