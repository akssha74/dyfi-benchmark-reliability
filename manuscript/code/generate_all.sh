#!/usr/bin/env bash
# Regenerate the reader-facing tables and figures from the committed, verified
# asset-input record. This release command is token-free: it neither refits
# models nor opens the protected role.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PY_A="${PY_ANALYTICS:-python3}"
PY_F="${PY_FIGURES:-python3}"

test -f manuscript/derived/asset_inputs.json

echo "[1/2] tables"
"$PY_A" manuscript/code/build_tables.py >/dev/null

echo "[2/2] figures"
"$PY_F" manuscript/code/build_figures.py >/dev/null

echo "OK: reader-facing manuscript assets regenerated"
