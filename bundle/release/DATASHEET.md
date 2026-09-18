# Datasheet — DYFI-USGS single-source severe-felt-intensity benchmark (v1)

Following Gebru et al., *Datasheets for Datasets*.

## Motivation
- **Purpose.** Provide a reusable, versioned, leakage-safe evaluation contract
  for predicting a later event-maximum severe felt-intensity label (`maxCDI>=6`)
  from outcome-blind USGS event source metadata, replacing ad-hoc single-system
  random splits with a frozen sequence-grouped protocol and an executable leakage
  audit.
- **Not for.** Real-time triage, lead-time forecasting, operational allocation,
  cross-system transport, causal inference, or claiming a winning model.

> **Post-execution (2026-09-01).** The single authorised one-shot protected run
> has executed on the pinned snapshot (`sha256 88722d8a…`, 7,520 features). The
> released `event_level_table.csv` now carries **2,362 eligible instances** across
> all roles (train 1,573 / development 357 / external_temporal_holdout 430 /
> temporal_straddle_excluded 2). Severe prevalence: 0.2855 (construction), 0.3512
> (holdout). Results: `results.json` / `results/protected_run_temporal/run_result.json`.

## Composition
- **Instances.** One row per earthquake event with a DYFI product, drawn from a
  single hash-pinned USGS DYFI/ComCat snapshot; `M>=5`, 2015–2024, worldwide.
  Outcome-blind universe count: 7,520 (co-stamped 2026-09-01T06:34:20Z; packet
  preflight 7,575/7,576 — within disclosed catalogue-drift tolerance; the single
  pinned instant governs). Eligible after `num_responses>=10` + Q1–Q5: 2,362.
- **Label.** `severe_label = 1[maxCDI>=6]`; primary threshold 6.0 with sensitivity
  at 5.5/6.5.
- **Splits.** Sequence-grouped `train` / `development` / `external_temporal_holdout`
  (primary, cutoff year 2023) + geographic transport secondary; assigned by a
  pre-hashed, label-independent rule.
- **PII.** None redistributed; only event-level metadata, labels, non-predictive
  eligibility fields, roles, and provenance hashes.

## Collection & preprocessing
- **Source.** USGS DYFI + ComCat via FDSNWS (public domain, DOI 10.5066/F7J101C8).
- **Eligibility.** `num_responses >= 10` (data-informed, disclosed; eligibility
  only).
- **Grouping.** Single-link space-time connected components (100 km / 30 d).
- **Quarantine.** Q1–Q5 (non-earthquake type, outside envelope, corrupt geometry,
  duplicate authoritative origin, explicit manual list incl. two inspected ids).
- **Provenance.** Per-event product version id, access instant, payload SHA-256;
  snapshot pinned to one instant.

## Uses
- **Recommended.** Benchmarking leakage-safe evaluation, measuring naive-split
  optimism inflation, calibration/uncertainty studies, baseline-ranking-stability
  analysis under a fixed non-selective suite.
- **Cautions.** The endpoint may be magnitude-dominated; many baseline differences
  are `unresolved`. maxCDI is ascertainment-sensitive; the eligibility filter
  mitigates but does not remove it. Descriptive-retrospective only.

## Distribution & maintenance
- **Licence.** Derived data CC0 1.0; code MIT.
- **Public release.** `https://github.com/akssha74/dyfi-benchmark-reliability/releases/tag/v1.0.1`.
- **Versioning.** `v1 = <access-instant>` snapshot; any later USGS revision defines
  a new version, never a silent overwrite.
- **Reconstruction.** Fetch-and-verify source-locator manifest + payload hashes;
  two clean reruns reproduce role hashes/predictions/metrics exactly.

The derived event-level records and frozen results are materialized in this
release. Later source updates must use a new version rather than overwrite
version 1.
