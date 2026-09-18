# Reproduction and verification

## 1. Verify the paper and frozen outputs

From the repository root:

```bash
python3 manuscript/paper/validate_manuscript.py
```

This standard-library verifier checks cohort arithmetic, result-table values,
split differences, baseline uncertainty intervals, pairwise comparisons,
citations, figure/table presence, and canonical asset fingerprints. Expected:

```text
validate_manuscript: 88 checks, 0 failed -> PASS
```

## 2. Verify the frozen source snapshot

```bash
shasum -a 256 activation/raw/dyfi_M5_dyfi_2015_2025_20260901T063330Z.geojson
```

Expected SHA-256:

```text
88722d8aa6d025cfcc3562f29593cc87d84c6a073bf211e8c21d89adddd4d7e9
```

The snapshot contains 7,520 USGS DYFI records. The derived event-level table,
role manifest, and frozen result surface are under `bundle/release/`.

## 3. Run the benchmark tests

Python 3.11 is recommended. Exact package versions are pinned in
`code/requirements.lock.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r code/requirements.lock.txt
(cd code && python -m unittest discover -p 'test_*.py')
```

The tests cover field-level leakage rejection, sequence grouping, role
assignment, metrics, baseline behavior, deterministic reporting, acquisition
guards, and reconstruction.

## 4. Regenerate and validate manuscript tables and figures

Use separate environments because the frozen analytics and figure stacks pin
different NumPy versions:

```bash
python3 -m venv .venv-fig
.venv-fig/bin/pip install -r manuscript/requirements-assets.lock.txt
PY_ANALYTICS="$PWD/.venv/bin/python" \
PY_FIGURES="$PWD/.venv-fig/bin/python" \
bash manuscript/code/generate_all.sh
PY_FIGURES="$PWD/.venv-fig/bin/python" \
.venv/bin/python manuscript/code/validate_assets.py
```

This release command rebuilds the reader-facing tables and figures from the
committed, verified `manuscript/derived/asset_inputs.json`. It does not reopen
the protected role or refit a model.

## 5. Rebuild the manuscript

With Tectonic and `pdfinfo` installed:

```bash
bash manuscript/paper/build.sh
```

The expected output is a 13-page PDF with no undefined references and no
overfull boxes.

## Environment

- Python 3.11.15
- NumPy 1.26.4
- SciPy 1.13.1
- scikit-learn 1.5.2
- XGBoost 2.1.4
- Matplotlib 3.11.1 (separate figure environment)

The published result files and protected holdout are immutable. Verification
uses the released frozen outputs; it does not reopen the protected evaluation.
