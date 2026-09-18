#!/usr/bin/env bash
# Deterministic, self-contained build of the Discover Applied Sciences manuscript.
#
# Steps (all scripted, no hand-editing):
#   1. Regenerate the venue-formatted table inputs from the canonical, validated
#      generated tables under manuscript/tables/ (layout-only transform).
#   2. Copy the deterministic figures (byte-identical to the validated assets).
#   3. Compile main.tex -> main.pdf with tectonic (auto reruns bibtex + passes).
#
# Requires: python3, tectonic. No network write, no DOI mint, no submission.
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/3] formatting tables from canonical assets ..."
python3 format_tables.py

echo "[2/3] syncing figures ..."
mkdir -p figures
cp -f ../figures/*.png figures/
cp -f ../figures/*.pdf figures/

echo "[3/3] compiling with tectonic ..."
tectonic --keep-logs main.tex >/dev/null 2>&1

pages=$(pdfinfo main.pdf 2>/dev/null | awk '/Pages:/ {print $2}')
echo "OK: main.pdf built (${pages:-?} pages)."
