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
cd code
python -m unittest discover -p 'test_*.py'
```

The tests cover field-level leakage rejection, sequence grouping, role
assignment, metrics, baseline behavior, deterministic reporting, acquisition
guards, and reconstruction.

## 4. Rebuild the manuscript

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

The published result files and protected holdout are immutable. Verification
uses the released frozen outputs; it does not reopen the protected evaluation.
