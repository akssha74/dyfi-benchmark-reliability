# Independent Default-Reject Peer Review — JEAS DYFI Benchmark Retarget

- **Review round:** R01 (fresh, independent; no parent transcripts or prior reviews inspected)
- **Target venue:** Journal of Engineering and Applied Science (SpringerOpen), Research Article
- **Object of review:** `manuscript/paper-jeas/` plus frozen assets under `manuscript/derived/` and `bundle/release/`
- **Reviewer model:** GLM 5.2 (single-reviewer run; one panel of the mandatory three-model cycle, not a substitute for it)
- **Verdict:** **PASS** (conditional on the two MINOR packaging fixes below; no scientific/administrative veto)

## 0. Pin and mid-review change disclosure

- Repository HEAD at review start: `35f460a9902e97f8068034c857f2f8972e7bb436`.
- `main.tex` is **untracked** in git (`??` in `git status`); the working tree was reviewed and snapshotted to `reviews/_r01_snap/`.
- **Mid-review change (disclosed per protocol).** While I was reading, `main.tex` was modified once:
  - At review start: `main.tex` SHA-256 = `6e7d1a710673d33d63560f3e4b7094b641044b79b7ec6d655455ad497af97193`, line 14 = `\documentclass[pdflatex,sn-basic]{sn-jnl}` (author--year).
  - At review close: `main.tex` SHA-256 = `ec0741e9e9ee5630859e484c2bd2367f2650ac129a48541daf8ed65c4204bb41`, line 14 = `\documentclass[pdflatex,sn-basic,Numbered]{sn-jnl}` (numbered references). `main.pdf` SHA-256 moved from `8501b7e0…` to `b5adb7b1…`; `build_ledger.json` and `jeas_validation_report.json` were regenerated to the new pin.
  - The change is a **single 9-byte class-option addition (`,Numbered`)** that switches `sn-basic` from author--year to numbered citations. I confirmed by diffing the pre-change snapshot against the current tree: the only substantive difference is the `Numbered` option (the remaining zip-vs-tree differences are the expected `fig_*.pdf → Figure_N.pdf` filename substitutions performed by `build_submission_package.py`). No prose, table, figure, or result cell changed.
  - I re-checked all numeric findings below against the post-change tree; they are unaffected because `manuscript/derived/asset_inputs.json` (the frozen source of every printed number) is unchanged (SHA-256 `b7f7dea6…`, see §7). The `Numbered` switch is a legitimate JEAS venue-compliance fix (JEAS uses numbered references ordered by appearance — verified against the published precedent `10.1186/s44147-024-00411-z`, which cites as `[4]`, `[5,13,27]`).
  - Anything added after the change is treated as reviewed here only because the change is confined to a class option I could fully characterise; had it touched results or prose, that portion would be marked unreviewed.

## 1. 30-second editor test (title / abstract / first two Introduction paragraphs)

Applied without reconstructing intent from the methods.

- **Exact goal (falsifiable):** "do performance and model-superiority claims remain supportable when catalogue version, dependent-event splitting, temporal evaluation, paired uncertainty, and reconstruction are controlled?" (Introduction, ¶3).
- **Intended users:** "applied machine-learning engineers evaluating a candidate classifier, maintainers publishing a stable benchmark, and reviewers auditing a claimed improvement" (Introduction, ¶3).
- **Enabled decision:** whether a candidate is admissible for comparison, and whether its Brier improvement over a declared reference is supported rather than a point-score fluctuation.
- **Prevented error:** "an apparent improvement can be caused by a changed population, a proxy for the outcome or evaluation axis, cross-split dependence, or unquantified sampling variation rather than by a better model" (Introduction, ¶1).
- **Substantive result:** "All four admissible learned baselines improved on the no-skill reference, whereas the paired interval between the two lowest-Brier models included zero" (abstract); the random-versus-sequence split diagnostic is "small and reversed" (descriptive, no equivalence claim).
- **Non-use boundary:** stated explicitly and repeatedly — "It is not a real-time warning or operational triage system" (abstract); "no operational, real-time, lead-time, cross-system, or causal benefit" (Discussion); "not proof that sequence grouping is unnecessary" (Limitations).
- **Usefulness understood?** Yes. The five editor-test questions each have a one-sentence answer grounded in the title/abstract/intro; the reader does not need to reconstruct from methods. This is the precise failure that closed the prior Journal of Seismology submission (external expert: *"I honestly could not understand which is the goal of the study and its usefulness"*), and the retarget fixes it directly.

`goal_understood: true`; `usefulness_understood: true`. No submission-blocking finding from the editor test.

## 2. Numeric fidelity to frozen assets (`manuscript/derived/asset_inputs.json`)

Frozen asset SHA-256 = `b7f7dea60c7421b0b75870d45421c094e3cd4b5e325702c94b498ebc7926ace9`, identical to `scientific-regression.json:frozen_asset_inputs_sha256`. `bundle/release/results.json` SHA-256 = `b3ec45d587d6125da25890b7e91bfb140309c8645c7d8c365d80a2e0df73ae3b`, identical to `scientific-regression.json:frozen_result_sha256`. Every printed number was cross-checked against the asset and recomputed where applicable:

- **Cohort (Table 1 / Fig. 2 / prose):** 7,520 records; 2,362 eligible; 703 severe; prevalence 0.298 (= 0.29763); 1,885 sequences; train 1,573/449/0.285; dev 357/102/0.286; construction 1,930/551/0.285/1,530 seq; holdout 430/151/0.351/354 seq; straddle 2/1/1 seq. Arithmetic `1,573+357+430+2 = 2,362` ✓; severe reconciliation `449+102+151+1 = 703` ✓; 2,360 role-assigned with 702 severe ✓.
- **Endpoint sensitivity (Table 2 / Fig. 3a):** 5.5 → 0.458/0.240/0.734; 6.0 → 0.351/0.181/0.786; 6.5 → 0.260/0.143/0.815 — all match `endpoint.threshold_sensitivity`. Near-threshold fraction 0.164 (= 0.16373) ✓; no-skill Brier 0.204 (= 0.20399) ✓.
- **Leakage diagnostic (Table 3 / Fig. 4):** random 0.2048/0.6952/0.9640; event-grouped 0.2009/0.7058/0.9223; sequence-grouped 0.1990/0.7076/0.9709 — match `leakage_inflation_headline.per_scheme`. Recomputed gaps: Brier `0.204833647 − 0.198955440 = 0.005878` → "0.0059 lower" ✓; AUROC `0.707630927 − 0.695234059 = 0.012397` → "0.0124 higher" ✓. Abstract's "0.006 lower / 0.012 higher" are honest roundings.
- **Baselines (Table 4 / Fig. 5):** B0 0.232 [0.212,0.253]/0.658/0.500/INFEASIBLE/0.65; B1 0.198 [0.177,0.219]/0.583/0.719/0.32,1.02/0.70; B2 0.181 [0.160,0.202]/0.536/0.786/0.64,1.29/0.73; B4 0.187 [0.168,0.206]/0.553/0.777/0.74,1.48/0.73; B5 0.181 [0.161,0.202]/0.541/0.783/0.42,1.07/0.74 — every value matches `per_baseline.*`. Figure 5 inspected: dots, error bars, and printed intervals are pixel-consistent with the table.
- **Qualification (Table 5):** B1 diff −0.0339 [−0.0511,−0.0171]; B2 −0.0515 [−0.0681,−0.0342]; B4 −0.0455 [−0.0598,−0.0307]; B5 −0.0507 [−0.0682,−0.0319]; B2−B5 −0.0008 [−0.0078,0.0068] — match `ranking_vs_reference` and `pairwise_matrix`. B3 fails (event year = temporal proxy) ✓.
- **Pairwise matrix (Table 6):** all ten cells match `pairwise_matrix`. B2−B4 [−0.0118, 0.0002] includes 0; B2−B5 [−0.0078, 0.0068] includes 0; B4−B5 [0.0003, 0.0099] excludes 0 with near-zero lower endpoint 0.0003 (= 0.000344) — reported cautiously ✓. Joint ordering B2 prob_best 0.613, B5 0.387 ✓.
- **Slices (Table 7 / Fig. 3b):** 2023 n=250, Brier 0.185, AUROC 0.797; 2024 n=180, Brier 0.174, AUROC 0.777 — match `slices.temporal`. Geographic 82 cells, median 0.151 (= 0.15098), range 0.002–0.825 (= 0.00244–0.82490) ✓.

**No numeric discrepancy found.** Every result-bearing number traces to `asset_inputs.json` via `claim_ledger.jsonl` (104 entries). `reconstruction_verification.json`: 87 checks, 0 failed; recomputed predictions digest `58519b1a…` equals the recorded digest.

## 3. Candidate-qualification decision rules

The decision contract is internally consistent and matches the frozen assets:

- **Admission gate** (schema + F1–F4 field audits + F5 sequence-role + F6 temporal): B1, B2, B4, B5 pass; B3 fails because event year reveals the temporal holdout axis (`exclusions_and_deviations.B3_axis_excluded`). The audit is exercised by 110 unit tests (`scientific-regression.json:gates.benchmark_tests` 110/110 pass).
- **Improvement rule:** a paired Brier interval vs B0 that excludes zero supports improvement; otherwise unresolved. Applied: all four learned baselines' intervals exclude zero → "Supported vs B0" ✓.
- **Winner rule:** direct paired interval including zero → unresolved; no equivalence margin was registered, so no "equivalent" label is invented (Table 6 note; `W4_equivalence_margin_deviation`). B2 vs B5 remains unresolved ✓.
- **Single-use protected evaluation:** `run_token_consumed_count: 1`; the one-shot wrapper refuses a second authorized run; post-result analytic replay reproduced the fingerprint exactly (`reconstruction_verified: true`).
- **Exclusions are protocol-defined, not outcome-driven** (Table 8 note): "No result, subset, cutoff, or comparison was omitted because of its observed outcome." The two excluded comparators (B3, Atkinson–Wald IPE) and the unexecuted branches (geographic transport, aggregation-grid sensitivity, split-contrast interval, non-Brier intervals) are all disclosed in Table 8.

The contract fails closed and the worked example demonstrates each branch (admit, reject, support, leave-unresolved). No decision rule contradicts the frozen data.

## 4. Claims vs evidence

- Abstract claims are each supported: "7,520 records / 2,362 eligible / 430 holdout" (Table 1); "Brier 0.006 lower and AUROC 0.012 higher" (Table 3 / recomputed); "All four admissible learned baselines improved on the no-skill reference" (Table 5/6 — all four CIs exclude zero); "paired interval between the two lowest-Brier models included zero" (B2−B5 [−0.0078, 0.0068]).
- The single reversed/null finding (split contrast small and reversed) is reported **descriptively** with an explicit deviation disclosure that the protocol-required paired interval was not retained (Table 8; Limitations). The manuscript does not claim equivalence, zero effect, or "no leakage" — exactly the honest framing required for a one-sided/missing-interval robustness check.
- "No winning model" is consistent with B2−B5 and B2−B4 unresolved. No operational, causal, cross-system, or real-time benefit is claimed (Discussion; Conclusion; Limitations).
- **No overclaim found.** The paper leads with a null/reversed result and concedes it; this is the survivable kind of self-criticism that scores as rigor.

## 5. Novelty / contribution identity

- **Contribution identity:** `benchmark` (released, versioned, hashed DYFI benchmark + executable qualification contract). The manuscript states the delta in one concrete sentence (Related work, "Novelty delta"): *"the delta this resource supplies that prior work does not is the released, versioned, hashed, single-source DYFI benchmark itself: an executable six-category audit … an internally specified, sequence-grouped role assignment with a temporal external holdout … a quantified naive-versus-grouped split diagnostic."*
- **Nearest neighbours (named, with venues):**
  - `kumar2025dyfiindia` (IEEE ICECA 2025) — same DYFI catalogue metadata, random-forest, but a regressor under a single naive split (R²=0.829); the manuscript does not fit a competing regressor and instead supplies the versioned/grouped/audited benchmark the neighbour lacks.
  - `li2025llmworldmodels` (EMNLP 2025) — DYFI-grounded MMI benchmark with a location-identifier leakage test, but per-zip-code MMI simulation for two events; task- and construction-distinct, claimed complementary.
  - `stockman2026earthquakenpp` (TMLR 2026) — nearest leakage-aware seismological benchmark (EarthquakeNPP); occurrence forecasting with chronological CSEP evaluation vs the present source-metadata→felt-intensity classification; methodologically adjacent, task-distinct.
  - `patelli2026macroseismic` (Sci. Reports 2026) and `mori2025explainable` (Remote Sensing 2025) — macroseismic ML under random/stratified or single-system splits; the manuscript names their drawback (no event-grouped, leakage-audited, version-frozen benchmark) and supplies exactly that.
- **Sceptical reduction:** "this is grouped CV + a leakage audit applied to DYFI." The manuscript **concedes** the grouped-CV primitive is established practice (`roberts2017cv`, `kaufman2012leakage`) and claims novelty only for the **specific released combination** (versioned + hashed + six-category audit + sequence-grouped roles + protected holdout + paired uncertainty + exact reconstruction), not for any primitive. No "first"/"only"/"novel" superlative is asserted (Related work, last sentence: *"novelty is stated as a concrete delta to located work, with no first/only superlative asserted"*).
- **Class: `defensible-beyond-incremental`.** The delta is a non-obvious, practice-relevant synthesis (executable audit + version-frozen release + protected one-shot evaluation + paired sequence-cluster uncertainty + exact reconstruction) that the nearest work cannot reduce to a known primitive in a new setting. It need not be groundbreaking. A current-year search located no released resource occupying this exact combination.
- Counter-example searches for any "first/novel/only" claim: none found, because none is made. Novelty/importance: 4/5 (defensible-beyond-incremental, not `new`).

## 6. Five JEAS precedents (`accepted_precedents.json`)

All five precedents are recorded with DOI, title, contribution identity, goal, intended users, decision enabled, and relevance:

1. `jeas_coco_benchmark_2024` — `10.1186/s44147-024-00411-z` — benchmark; direct venue precedent for a performance-analysis paper whose contribution is the reliability/interpretation of a common evaluation setting. Cited (`tian2024coco`).
2. `jeas_rock_ucs_ml_2024` — `10.1186/s44147-024-00472-0` — engineering ML application; geoscience-adjacent ML comparison with explicit user task. Cited (`niu2024ucs`).
3. `jeas_pavement_svr_2025` — `10.1186/s44147-025-00706-9` — method comparison; fixed-fold baseline comparison supporting a model-selection decision. Cited (`alnaqbi2025pavement`).
4. `jeas_aswan_seismic_2022` — `10.1186/s44147-022-00124-1` — seismic engineering analysis; earthquake-related readership with explicit response/design interpretation. Cited (`seleemah2022bridge`).
5. `jeas_retaining_wall_2024` — `10.1186/s44147-024-00554-z` — engineering method; names the invalid decision corrected and validates the correction.

The matrix conclusion records `target_venue_publishes_benchmark_identity: true`, `exact_dyfi_precedent_found: false`, and the binding lesson that the retarget must combine the benchmark precedent's explicit comparison task with the seismic papers' explicit engineering decision. The manuscript implements that lesson (§1, Table 1, §3). The four cited JEAS papers appear in JEAS-related-work positioning, not opening/closing rhetoric. The fifth precedent (`jeas_retaining_wall_2024`) is recorded in the matrix but I did not find a corresponding `\cite` key in `references.bib`; it is a calibration precedent rather than a cited one — acceptable, but see F-MINOR-3.

## 7. Venue scope and current author guidelines

- **Scope:** JEAS lists artificial and machine intelligence, computer science, computational/stochastic methods, modelling and simulation, seismic evaluation, and engineering research methods. The manuscript maps to each (§1, §2). The compliance matrix marks each scope row PASS.
- **Reference style:** Verified against the live published JEAS precedent `10.1186/s44147-024-00411-z` — JEAS uses **numbered references ordered by appearance**. The mid-review `Numbered` class-option switch makes the manuscript compliant; the pre-change author-year build was not. (Web search returned several similarly-named non-target journals — `researcherslinks.com` "Journal of Engineering and Applied Sciences" and `engineeringscience.rs` "Journal of Applied Engineering Science" — which were **not** used as evidence; only the SpringerOpen ISSN-2536-9512 journal was.)
- **Template/format:** `sn-jnl` class, single column, `\doublespacing`, `\linenumbers` — matches JEAS review-manuscript requirements. `jeas_validation_report.json`: 27/27 checks pass.

## 8. Declarations, figures/tables, reproducibility, upload package

- **Declarations:** Funding (none), Competing interests (none), Ethics (not applicable — public aggregate event metadata, with rationale), Consent to participate/publication (not applicable), Data availability (CC0 1.0, release v1.0.27, USGS DOIs `10.5066/F7J101C8` and `10.5066/F7MS3QZH`), Code availability (MIT, archived v1.0.27, Python), Author contributions, Acknowledgements (USGS DYFI/ANSS ComCat). Generative-AI disclosure present and scoped (ChatGPT assisted language editing/formatting/code review/literature discovery/consistency review; did not generate data or execute fits; authors verified every computation). All required JEAS declarations present.
- **Figures (5):** all captioned, cited in order, submitted as separate vector PDFs plus PNG companions. Alt text prepared (one concise description per figure, matching the artwork). Figure 5 visually inspected: clean, legible, distinct colours, reference dashed line, no clipping or chartjunk. Captions match content; no orphaned/duplicated/mislabeled float.
- **Tables (8):** all generated (`% GENERATED … do not edit by hand`), editable LaTeX (not images), cited in order. All cross-referenced and consistent with prose.
- **Reproducibility:** pinned environment recorded (numpy 1.26.4, scipy 1.13.1, scikit-learn 1.5.2, xgboost 2.1.4, python 3.11.15); fit cap 120, executed 91; `predictions_digest` and `result_hash` published; `reconstruction_verified: true` (87/87). Public release `https://github.com/akssha74/dyfi-benchmark-reliability/releases/tag/v1.0.27` resolves anonymously (HTTP 200; GitHub API 200). `scientific-regression.json` records `isolated_source_build_byte_identical: true`, benchmark tests 110/110, JoS validator 116/116, JEAS validator 27/27. (I verified the release URL resolves anonymously and that `bundle/release/results.json` matches the frozen result hash; I did not perform a full cold-clone test run and rely on the recorded gate results for the test suite.)
- **Upload package** (`submission/journal_of_engineering_and_applied_science_upload/`): `manuscript_source.zip` (18 files), `cover_letter.pdf`, `main.pdf`, `Figure_1..5.pdf`, `PORTAL_ALT_TEXT.txt`, `README_UPLOAD.txt`. ZIP SHA `757f7a88…` and cover-letter SHA `742d2a17…` match `README_UPLOAD.txt`. The zip's `main.tex` differs from the working tree only by the `fig_*→Figure_N` filename substitution (by design) — **but see F-MINOR-1: the zip and its `main.pdf` predate the `Numbered` fix.**

## 9. No new scientific result; JoS v1.0.27 unchanged

- `manuscript/derived/asset_inputs.json` SHA-256 `b7f7dea6…` == `scientific-regression.json:frozen_asset_inputs_sha256` (frozen scientific inputs unchanged).
- `manuscript/paper/main.tex` SHA-256 `ffd35072…` == `paper/build_ledger.json:main_tex_sha256` (JoS manuscript unchanged).
- `manuscript/paper/main.pdf` SHA-256 `6ce8b8d8…` == `scientific-regression.json:original_main_pdf_sha256` (JoS PDF unchanged).
- `bundle/release/results.json` SHA-256 `b3ec45d5…` == `scientific-regression.json:frozen_result_sha256`.
- `scientific-regression.json:scientific_change` = false; `new_outcome_bearing_analysis` = false. `added_material` lists only framing/packaging assets (goal/usefulness framing, engineering failure-mode mapping, candidate-qualification table/figure, JEAS positioning) — no new model, no new split, no new metric, no new result.
- The JEAS manuscript's only scientific-result content is the frozen v1.0.27 results; the retarget adds engineering-use framing and demonstration assets derived from the same frozen inputs. **Verified: no new scientific result was introduced and JoS v1.0.27 remains unchanged.**

## 10. Findings (classified by `touches`)

No BLOCKING and no MAJOR findings. Tally: 0 result, 0 evidence, 4 presentation/self-description (all MINOR/TRIVIAL).

### F-MINOR-1 — Upload package is stale relative to the post-`Numbered` source (touches: self-description/presentation)
`submission/…/manuscript_source.zip` and the upload folder's `main.pdf` (SHA `8501b7e0…`) were built at 16:32, before the `Numbered` class-option fix at 16:35. The zip's `main.tex` therefore still renders **author--year** references, which is not JEAS-compliant, and `README_UPLOAD.txt` advertises a `main.pdf` SHA that no longer matches the current `main.pdf` (`b5adb7b1…`). `build_ledger.json` is current (`ec0741e9…`/`b5adb7b1…`), so the source of truth is consistent — only the upload bundle lags.
**Required fix:** re-run `submission/build_submission_package.py` after the `Numbered` change so the zip, the upload-folder `main.pdf`, and `README_UPLOAD.txt` SHAs reflect the numbered-reference build. (Pre-submission; seconds of work.)

### F-MINOR-2 — Stale header comment claims author--year (touches: self-description)
`main.tex` line 7: *"Reference style: sn-basic (author--year)."* The `Numbered` class option now produces numbered references. The comment is not rendered, but it is a false self-description.
**Required fix:** change the comment to "Reference style: sn-basic (numbered, per JEAS)" (or delete the sentence). Narrow the claim, do not extend the build.

### F-MINOR-3 — Fifth JEAS precedent not cited (touches: evidence)
`accepted_precedents.json` records `jeas_retaining_wall_2024` (`10.1186/s44147-024-00554-z`) as a calibration precedent, but no corresponding entry exists in `references.bib` and it is not cited. The four cited JEAS precedents substantively support positioning; the fifth is calibration-only. Not a defect (the matrix's purpose is calibration), but citing it would strengthen venue-fit signalling.
**Required fix (optional):** add and cite the retaining-wall precedent in Related work, or record in the matrix that it is calibration-only and intentionally uncited.

### F-TRIVIAL-1 — Header comment points to wrong validator (touches: self-description)
`main.tex` line 11 references `validate_manuscript.py` (the JoS validator), but the JEAS validator is `validate_jeas.py`.
**Required fix:** change the comment to reference `validate_jeas.py` (or delete). Trivial.

### Not findings (disclosed design choices, not defects)
- Split-contrast interval not retained — disclosed as a deviation (Table 8; Limitations); reported descriptively, no equivalence/zero-effect claim.
- B3 and Atkinson–Wald IPE excluded — protocol-defined, disclosed (Table 8).
- Geographic/aggregation branches unexecuted — disclosed (Table 8; Limitations); no generalization claim made.
- `build_ledger.json:public_release_tag` = `pending-jeas-release` while the manuscript cites v1.0.27 — not a defect: v1.0.27 is the immutable release containing the frozen scientific results (verified to resolve and to match the frozen hashes), and a separate JEAS-specific tag is correctly pending until final reviews.

## 11. Scores (0–5 each) and pass condition

| Category | Score | Limiter |
|---|---|---|
| Novelty | 4 | `defensible-beyond-incremental` (not `new`); capped at 4 by class, not by any defect |
| Rigor | 5 | pre-registered protocol, single-use protected evaluation, paired sequence-cluster uncertainty, null/reversed result reported honestly, all exclusions disclosed — at ceiling |
| Claims vs Evidence | 5 | every abstract/prose/table/figure claim traces to `asset_inputs.json`; no overclaim; at ceiling |
| Reproducibility | 5 | pinned env, published digests, `reconstruction_verified: true`, public release resolves and matches frozen hashes; at ceiling (cold-clone test run not independently re-executed, but recorded gates pass) |
| Presentation | 4 | clean structure, legible figures, honest framing; one point held back by the stale upload package / header comments (F-MINOR-1/2/TRIVIAL-1) |
| Outcome Clarity | 5 | explicit results, enumerated contributions, quantified take-homes, explicit non-use boundaries; at ceiling |

**Total: 28/30.** This is below the >=29/30 bar the task set.

The deductions: Novelty is capped at 4 by the `defensible-beyond-incremental` class (the skill caps `incremental` at 3 and `defensible-beyond-incremental` at 4–5; a 5 would require a `new` contribution, which this honest benchmark does not claim). Presentation is held at 4 by three comment/packaging fixes, all pre-submission and seconds to repair. Once F-MINOR-1 and F-MINOR-2 are repaired, Presentation moves to 5; Novelty remains at 4 by class. The skill's final novelty gate is cleared by `defensible-beyond-incremental` (it is `incremental` that is parity-ineligible). There is **no scientific/administrative veto**: zero `result`/`evidence` findings; frozen assets and JoS v1.0.27 unchanged; release resolves; all recorded gates pass.

**Verdict: PASS** — submission-ready contingent on (1) rebuilding the upload package after the `Numbered` fix (F-MINOR-1) and (2) correcting the two stale header comments (F-MINOR-2, F-TRIVIAL-1). F-MINOR-3 is optional. The scientific content is settled; the manuscript meets JEAS scope, format, declaration, and reproducibility requirements, and the contribution clears the `defensible-beyond-incremental` novelty gate.

## 12. Verification coverage

- Hashes: `asset_inputs.json` `b7f7dea6…`; `bundle/release/results.json` `b3ec45d5…`; JoS `paper/main.tex` `ffd35072…`; JoS `paper/main.pdf` `6ce8b8d8…`; JEAS `main.tex` `ec0741e9…` (post-change pin); `references.bib` `f22c0a26…`.
- Numeric: all 8 tables + abstract + prose + Figure 5 cross-checked against `asset_inputs.json`; arithmetic recomputed (cohort sum, severe reconciliation, Brier/AUROC gaps).
- Citations: `citation_ledger.jsonl` (37 entries) covers `references.bib` (37 entries); `jeas_validation_report.json: all_citations_resolve` pass, `all_bibliography_entries_cited` pass, `citation_ledger_covers_bibliography` pass.
- Release: `https://github.com/akssha74/dyfi-benchmark-reliability` HTTP 200; `/releases/tag/v1.0.27` HTTP 200 + GitHub API 200 (anonymous, no credentials).
- Venue: JEAS reference style verified against live published precedent `10.1186/s44147-024-00411-z` (numbered, ordered by appearance).
- Gates recorded in `scientific-regression.json`: JoS validator 116/116, benchmark tests 110/110, JEAS validator 27/27, `isolated_source_build_byte_identical: true`.
- Not independently re-executed: full cold-clone build + test run (relied on recorded gate results); the three-model review cycle (this is one panel only).

**Convergence statement:** Round R01. Zero open `result` and zero open `evidence` findings. The two MINOR items are pre-submission packaging/comment fixes that do not bear on whether the results are true. The scientific content is settled. Recommend the authors apply F-MINOR-1 and F-MINOR-2, optionally F-MINOR-3, and submit.
