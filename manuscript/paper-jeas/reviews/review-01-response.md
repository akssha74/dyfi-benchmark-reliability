# Response to JEAS default-reject review R01

All mandatory findings were administrative/presentation findings; no result or
evidence correction was required.

1. **Stale upload package — resolved.** The submission package was rebuilt after
   enabling the JEAS numbered reference style. The current source ZIP is
   generated deterministically and compiles to the canonical PDF byte-for-byte.
2. **Stale author-year header — resolved.** `main.tex` now identifies
   `sn-basic` as numbered per JEAS.
3. **Wrong validator comment — resolved.** `main.tex` now points to
   `validate_jeas.py`.
4. **Fifth precedent — resolved without citation padding.** The retaining-wall
   paper is explicitly marked calibration-only and intentionally uncited in
   `accepted_precedents.json`; four substantively relevant JEAS precedents remain
   engaged in the manuscript.
5. **Standalone validation — hardened.** Frozen input and original-build
   identity files are bundled with the source, and `validate_jeas.py` passes
   29/29 from an isolated source-only extraction.

Scientific data, predictions, scores, intervals, and conclusions remain
unchanged.
