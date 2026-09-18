# Data dictionary — released event-level table (v1)

One row per earthquake **event** (parent event id) with a DYFI product. The
independence unit for leakage control is the space-time seismic **sequence**.

| Column | Type | Units | Role | Predictive? | Notes |
|---|---|---|---|---|---|
| `event_id` | string | — | identifier / provenance | **No (forbidden)** | USGS event id; grouping + provenance only. Leakage family F3. |
| `magnitude` | float | Mw-equiv | predictor | Yes | First catalogue magnitude. `SOURCE_ONLY`. |
| `depth_km` | float | km | predictor | Yes | Event depth. `SOURCE_ONLY`. |
| `latitude` | float | deg | predictor (expanded only) | Expanded / axis-restricted | In `EXPANDED_METADATA` only; geographic-axis proxy. |
| `longitude` | float | deg | predictor (expanded only) | Expanded / axis-restricted | In `EXPANDED_METADATA` only; geographic-axis proxy. |
| `origin_time` | ISO-8601 UTC | — | covariate / temporal-holdout key | Temporal covariate; **not** joinable to any post-outcome field | Derived `origin_year` is a temporal-axis proxy (B3-restricted). |
| `maxCDI` | float | CDI | **label source** | **No (label constituent)** | Event-maximum Community Decimal Intensity. Leakage family F1. |
| `severe_label` | int {0,1} | — | **target** | target | `1` iff `maxCDI >= 6`. |
| `num_responses` | int | count | eligibility only | **No (forbidden)** | Post-outcome ascertainment quantity; `>=10` eligibility filter only. Leakage family F2. |
| `sequence_id` | string | — | grouping | No | Space-time sequence cluster (100 km / 30 d). |
| `role` | enum | — | split assignment | No | `train` / `development` / `external_temporal_holdout` (+ geographic variant). |
| `product_version_id` | string | — | provenance | No | DYFI product version + update time. |
| `access_instant` | ISO-8601 UTC | — | provenance | No | Snapshot access instant (hash-pinned). |
| `source_payload_sha256` | hex | — | provenance | No | SHA-256 of the retrieved per-event payload. |

## Feature schemas (strict)

- `SOURCE_ONLY = {magnitude, depth_km}` — the **only** schema scored on the
  temporal/geographic transport holdouts.
- `EXPANDED_METADATA = {magnitude, depth_km, latitude, longitude, origin_year}` —
  published **only** as a proxy-bearing sensitivity (baseline `B3`); forbidden on
  the temporal/geographic axes.

The leakage audit accepts **only** the exact schema (same members, same order).

## Forbidden fields (rejected by the audit)

`maxCDI`, cdi grid values, `maxmmi`, per-location intensity, `severe_label` as a
feature, `num_responses`/`numResp`, any DYFI aggregate grid content, `event_id`
and high-cardinality identifiers, and any downstream product (ShakeMap/PAGER/PGA/
PGV/instrumental MMI). Families F1–F4 (field-level), F5 (sequence cross-role),
F6 (temporal).

> Real column values are written only at authorized construction; this dictionary
> pins the schema in advance.
