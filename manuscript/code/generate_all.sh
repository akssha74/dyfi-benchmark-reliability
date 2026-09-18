#!/usr/bin/env bash
# Deterministic end-to-end regeneration of every manuscript asset from the frozen
# released resource. Token-free; opens no protected role; mutates no author artifact.
#
#   analytics venv (code/.venv)      : F2 matrix, F1 disclosure, asset inputs, tables, ledger
#   figures venv  (manuscript/.venv-fig): figures only (matplotlib)
#
# Usage:  bash manuscript/code/generate_all.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PY_A="$ROOT/code/.venv/bin/python"
PY_F="$ROOT/manuscript/.venv-fig/bin/python"

echo "[1/6] F2 pairwise ranking-stability matrix"
"$PY_A" manuscript/code/build_pairwise_ranking.py >/dev/null

echo "[2/6] F1 phase-F self-reference disclosure"
"$PY_A" manuscript/code/build_f1_disclosure.py >/dev/null

echo "[3/6] consolidated asset inputs (verified)"
"$PY_A" manuscript/code/build_asset_inputs.py >/dev/null

echo "[4/6] tables"
"$PY_A" manuscript/code/build_tables.py >/dev/null

echo "[5/6] figures"
"$PY_F" manuscript/code/build_figures.py >/dev/null

echo "[6/6] asset ledger + manifest"
"$PY_A" manuscript/code/build_asset_ledger.py >/dev/null

echo "OK: manuscript/asset_manifest.json"
