# DYFI-USGS severe felt-intensity benchmark — version 1

This directory contains the materialized public release of the benchmark.

## Core files

- `event_level_table.csv` — 2,362 eligible event-level records across every
  analysis and exclusion role.
- `role_manifest.json` — role counts, sequence counts, and role fingerprints.
- `results.json` — frozen benchmark results.
- `fit_ledger.json` — complete record of the 91 model fits.
- `source_locator_manifest.json` — source URL, access instant, and frozen-source
  fingerprint.
- `DATA_DICTIONARY.md` and `DATASHEET.md` — field definitions, intended uses,
  scope, and limitations.
- `REPRODUCTION.md` — verification and test instructions.

The primary feature set contains magnitude and depth. Response count is used
only to establish eligibility and is forbidden as a model input. The severe
label is event-maximum community decimal intensity (CDI) of at least 6.

The observed random-versus-sequence-grouped split difference is reported as a
descriptive measured null. Learned baselines improve on the no-skill reference,
but the direct comparison between the two lowest-Brier models is unresolved.
No winning model is claimed.

## Scope

This benchmark supports retrospective, single-USGS-source evaluation. It does
not support real-time, operational, causal, or cross-system claims.

## Licences

- Derived data: CC0 1.0 (`LICENSE-DATA.txt`)
- Code: MIT (`LICENSE-CODE.txt`)
- Underlying USGS DYFI and ComCat data: public domain
