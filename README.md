# USGS DYFI severe felt-intensity benchmark

Version 1 of a single-source, leakage-audited benchmark for retrospective
prediction of severe felt intensity from earthquake source metadata.

The resource uses a frozen USGS *Did You Feel It?* (DYFI) snapshot for
2015--2024 earthquakes with magnitude at least 5. It contains:

- 7,520 frozen source records;
- 2,362 eligible events in 1,885 seismic sequences;
- 703 severe events, defined by event-maximum community decimal intensity
  (CDI) of at least 6;
- internally specified train (1,573), development (357), temporal-holdout (430), and
  temporal-straddle (2) roles; and
- fixed reference baselines, a six-category leakage audit, and reproducible
  evaluation outputs.

The benchmark is descriptive and retrospective. It does not support real-time,
operational, causal, or cross-system claims, and it does not identify a winning
model.

## Repository contents

| Path | Contents |
|---|---|
| `bundle/release/` | Event-level table, role manifest, frozen results, fit log, source locator, data dictionary, and licences |
| `activation/raw/` | Frozen USGS GeoJSON source snapshot |
| `code/` | Leakage audit, grouping, baselines, metrics, tests, and validators |
| `preregistration/` | Frozen internal protocol record (first publicly timestamped with the repository release) |
| `results/` | Protected-run result and construction-side fit record |
| `manuscript/` | Paper source, PDF, tables, vector figures, ledgers, and manuscript validator |

## Quick verification

The manuscript-level verifier uses only the Python standard library:

```bash
python3 manuscript/paper/validate_manuscript.py
```

Expected result:

```text
validate_manuscript: 95 checks, 0 failed -> PASS
```

To run the benchmark test suite:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r code/requirements.lock.txt
cd code
python -m unittest discover -p 'test_*.py'
```

From the repository root, `python code/verify_test_inventory.py` confirms that
the four shipped suites contain 110 tests in total.

The frozen source snapshot has SHA-256
`88722d8aa6d025cfcc3562f29593cc87d84c6a073bf211e8c21d89adddd4d7e9`.
The activated source-locator manifest records the same payload hash, access
instant, payload size, and co-stamped count. See
`bundle/release/REPRODUCTION.md` for manuscript-asset regeneration and detailed
verification instructions.

## Licences and citation

Derived benchmark data are released under CC0 1.0. Code is released under the
MIT licence. The underlying USGS data are public domain. See
`bundle/release/CITATION.cff` for citation metadata.
