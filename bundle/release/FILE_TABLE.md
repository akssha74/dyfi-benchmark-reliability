# Release file table (v1)

Data-Note "Table 1" equivalent: file formats and identifiers for the release.
**Post-execution (2026-09-01):** the single authorised one-shot protected run has
executed, so the derived artifacts previously marked `present=no` are now
materialized and content-hashed below.

| File | Format | Present | SHA-256 (materialized) | Purpose |
|---|---|---|---|---|
| `README.md` | Markdown | yes | — | Overview, one-command reproduction, scope |
| `CITATION.cff` | CFF 1.2.0 | yes | Public release `v1.0.5` | Citation metadata |
| `LICENSE-DATA.txt` | text | yes | CC0-1.0 | Data licence |
| `LICENSE-CODE.txt` | text | yes | MIT | Code licence |
| `DATA_DICTIONARY.md` | Markdown | yes | — | Column schema, types, flags |
| `DATASHEET.md` | Markdown | yes | — | Datasheet-for-datasets |
| `FILE_TABLE.md` | Markdown | yes | — | This table |
| `CLARIFICATIONS.md` | Markdown | yes | — | Post-execution interpretation and metadata clarifications |
| `REPRODUCTION.md` | Markdown | yes | — | Environment + reproduction steps |
| `source_locator_manifest.json` | JSON | **yes** | `PUBLIC_RELEASE_MANIFEST.json` | Activated FDSNWS locators, access instant, and payload hash |
| `event_level_table.csv` | CSV | **yes** | `9657b92767b29910…` | Released derived event-level rows (2,362; all roles) |
| `role_manifest.json` | JSON | **yes** | `5741c5cb6af77300…` | Post-assignment role event-id/sequence hashes |
| `results.json` | JSON | **yes** | `b3ec45d587d6125d…` | Machine-readable one-shot benchmark results |
| `fit_ledger.json` | JSON | **yes** | `f993b509e6204e1f…` | Immutable 91-fit ledger (digest `74ea4679…`) |
| `code/` (tested modules + tests + validators) | Python | yes (in `code/`) | `PUBLIC_RELEASE_MANIFEST.json` | Version-pinned instrumentation |

## Source snapshot

- Raw GeoJSON: `activation/raw/dyfi_M5_dyfi_2015_2025_20260901T063330Z.geojson`
  SHA-256 `88722d8aa6d025cfcc3562f29593cc87d84c6a073bf211e8c21d89adddd4d7e9`
  (5,752,776 bytes; 7,520 records; access instant 2026-09-01T06:33:30Z).
- Machine-readable results also at `results/protected_run_temporal/run_result.json`
  (`result_hash 817219e8…`). Full per-artifact hashes:
  `PUBLIC_RELEASE_MANIFEST.json`.

## Source data identifiers

- USGS DYFI / ComCat: DOI `10.5066/F7J101C8` (public domain).
- Source URLs, access times, and the frozen payload hash are recorded in
  `source_locator_manifest.json`.
