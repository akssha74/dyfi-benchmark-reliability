# Journal of Engineering and Applied Science compliance matrix

Target: **Research Article**, regular collection
Publisher: Springer Nature / SpringerOpen
Official guidance checked: 2026-09-26

## Scope and publishing model

| Requirement | Status | Evidence/action |
|---|---|---|
| Fundamental or applied engineering contribution | PASS | Engineering model-comparison reliability for dependent, evolving event data |
| Artificial and machine intelligence | PASS | Explicit scope category |
| Computer science, computational/stochastic methods, modelling and simulation | PASS | Explicit scope categories |
| Seismic evaluation / global engineering challenge | PASS | Earthquake felt-intensity case study; no claim of structural-response modelling |
| Engineering research methods | PASS | Explicit scope category; contribution is a reusable qualification method |
| Contribution identity demonstrated in the venue | PASS | COCO benchmark comparison, engineering ML comparisons, and seismic-engineering precedents recorded in `accepted_precedents.json` |
| Open-access publishing model | ACKNOWLEDGED | Journal is fully open access |
| APC | PASS | Current official guidance states that the APC is covered by the Specialized Presidential Council for Education and Scientific Research; re-check immediately before submission |
| Scopus / EI Compendex | PASS | Listed on official journal page |
| First-decision metric | ACKNOWLEDGED | Official median is 9 days; this includes editorial decisions and is not an acceptance-rate claim |

## Main manuscript

| Requirement | Status | Evidence/action |
|---|---|---|
| Editable manuscript source | PASS | Self-contained LaTeX source plus bibliography, tables, and figures |
| Springer Nature LaTeX template | PASS | Use current `sn-jnl` class and upload every editable source |
| pdfLaTeX / TeX Live 2021 compatibility | REQUIRED | Compile cleanly under pdfLaTeX-compatible source package in addition to the pinned reference build |
| Double-line spacing | REQUIRED | Enable in review manuscript if the official template does not already enforce it |
| Continuous line numbering | REQUIRED | Enable line numbers in the review manuscript |
| Page numbering | PASS | Compiled review manuscript |
| SI units and embedded special characters | PASS | Audit final text and equations |
| No forced page breaks | REQUIRED | Remove manual page breaks from submission source |
| Concise informative title | REQUIRED | Lead with reliable engineering model comparison; avoid venue or workflow jargon |
| Complete author names/order | REQUIRED | Match portal exactly |
| Full affiliations and postal addresses | REQUIRED | Include country and current corresponding-author contact |
| Corresponding author clearly identified | REQUIRED | Active verified email; no institutional-email claim unless required |
| Abstract and keywords | REQUIRED | Verify exact Research Article limits on the live article-type form before upload |
| Goal and usefulness readable in 30 seconds | HARD GATE | Goal/usefulness contract and independent editor test must pass |

## Data, software, figures, and tables

| Requirement | Status | Evidence/action |
|---|---|---|
| Availability of data and materials section | REQUIRED | Name repository, persistent tag/identifier, licence, and source-data DOIs |
| Public data fully referenced | REQUIRED | USGS DYFI and ANSS ComCat data citations in bibliography |
| Software metadata | REQUIRED | Project name, homepage, archived version/tag, OS, language, licence, and restrictions |
| Machine-readable supporting data | PASS | CSV/JSON assets and manifests in public release |
| Tables editable, not images | PASS | Generated LaTeX tables |
| Figures numbered/cited in order | PASS | Automated validator |
| Multi-panel figures submitted as one composite | PASS | Existing vector PDFs |
| Figure title ≤15 words and legend ≤300 words | REQUIRED | Short title plus explanatory legend in manuscript, not artwork |
| Figure titles/legends outside graphic | PASS | Only axes, keys, panel labels, flow nodes, and data labels remain in artwork |
| Figure keys incorporated into graphic | PASS | Legends/keys within vector artwork |
| Closely cropped artwork | REQUIRED | Recheck final separate figure files |
| Separate editable/vector figure files | PASS | PDF/EPS-compatible vector files; each <10 MB |
| Final-size resolution | PASS | Vector PDFs; raster companions ≥300 dpi |
| Third-party permissions | N/A | Author-generated figures; public-domain source data |
| Alt text prepared | REQUIRED | Prepare one concise description per figure for portal/production |

## Declarations and editorial policy

| Requirement | Status | Evidence/action |
|---|---|---|
| Availability of data and materials | REQUIRED | Separate declaration |
| Competing interests | REQUIRED | Authors declare none |
| Funding | REQUIRED | No specific funding |
| Authors' contributions | REQUIRED | Per-author contribution and accountability statement |
| Ethics approval and consent | N/A with rationale | Public aggregate event metadata; no participants/animals |
| Consent for publication | N/A |
| Acknowledgements | PASS | USGS DYFI and ANSS ComCat programs |
| Generative-AI disclosure | REQUIRED | Tool, tasks, exclusions, human verification, and accountability |
| Preprint disclosure | REQUIRED | Existing public manuscript/source, no DOI, licence status |
| Originality / no simultaneous submission | REQUIRED | JoS rejection is closed; registry updated before JEAS submission |
| Cover letter | REQUIRED | Fit, contribution, policies, conflicts, co-author approval, originality, preprint, data/code availability |
| Optional reviewer suggestions | OPTIONAL | Use only verified independent experts; no fabrication or close collaborators |

## Release and submission transaction

| Requirement | Status | Evidence/action |
|---|---|---|
| Preserve JoS v1.0.27 | PASS | Separate `paper-jeas/` tree |
| Frozen numerical results unchanged | HARD GATE | Hash/claim-ledger regression against v1.0.27 |
| New JEAS release | REQUIRED | New immutable tag after final reviews |
| Cold-clone reproduction | REQUIRED | Build manuscript, verify ledgers/manifests, and run tests |
| Portal fields match manuscript | REQUIRED | Submission-transaction record |
| Portal-generated PDF audited | REQUIRED | Semantic comparison plus all-page visual inspection |
| Explicit human authorization before submit | REQUIRED | Stop before final submit action |
