# Data dictionary — released event-level table (version 1)

`event_level_table.csv` contains one row per eligible earthquake event. Its
columns are listed below exactly as released.

| Column | Type | Role | Model input? | Description |
|---|---|---|---|---|
| `event_id` | string | identifier | No | USGS event identifier; used for provenance and deterministic grouping only |
| `origin_time` | ISO-8601 UTC | temporal key | No | Frozen preferred origin time in the snapshot |
| `origin_year` | integer | temporal key | B3 only; not temporal holdout | Year derived from `origin_time` |
| `magnitude` | float | predictor | Yes | Frozen preferred catalogue magnitude; not guaranteed to be the first-alert value |
| `magnitude_type` | string | descriptive | No | Magnitude scale reported by the catalogue |
| `depth_km` | float | predictor | Yes | Frozen preferred catalogue depth in kilometres |
| `latitude` | float | location | B3 only; axis-restricted | Event latitude |
| `longitude` | float | location | B3 only; axis-restricted | Event longitude |
| `region_code` | string | subgroup key | No | 10-degree geographic-cell identifier |
| `num_responses` | integer | eligibility only | No | Post-event DYFI response count; at least 10 required |
| `max_cdi` | float | label source | No | Event-maximum community decimal intensity |
| `severe_label` | integer (0/1) | target | Target | 1 when `max_cdi` is at least 6 |
| `sequence_id` | string | grouping | No | Space--time sequence identifier (100 km, 30 days) |
| `role` | enum | split assignment | No | `train`, `development`, `external_temporal_holdout`, or `temporal_straddle_excluded` |

## Approved feature sets

- **Source-only:** `magnitude`, `depth_km`. This is the only feature set
  evaluated on the temporal holdout.
- **Expanded metadata (B3 sensitivity):** `magnitude`, `depth_km`, `latitude`,
  `longitude`, `origin_year`. It is not evaluated on the temporal holdout
  because `origin_year` reveals the evaluation axis.

The leakage audit accepts only an approved feature set in the expected order and
rejects additional fields.

## Provenance

Version 1 provides snapshot-level provenance in
`source_locator_manifest.json`: access instant, query and count URLs, payload
size, co-stamped count, and source-payload SHA-256. The event table does not
contain per-event product-version, access-time, or payload-hash columns.

## Geographic result

`region_code` is used only to summarize the 430 temporal-holdout predictions by
occupied geographic cell. This is not a leave-region-out evaluation and does not
support a geographic-generalization claim.
