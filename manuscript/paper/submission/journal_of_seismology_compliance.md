# Journal of Seismology — line-item compliance matrix

Reviewed against the live pages on 2026-09-19:

1. `https://link.springer.com/journal/10950/submission-guidelines`
2. `https://link.springer.com/pre-submission?journalId=10950`
3. `https://link.springer.com/journal/10950/aims-and-scope`
4. `https://link.springer.com/journal/10950/editorial-board`
5. `https://link.springer.com/brands/springer/journal-policies`
6. `https://link.springer.com/journal/10950/ethics-and-disclosures`
7. `https://www.springernature.com/gp/partners/rights-permissions-third-party-distribution`

Navigation, marketing, translation, and post-publication contact information are
not manuscript requirements and are not repeated below.

Status key: **PASS**, **N/A**, **EXTERNAL** (author/portal action), **OPTIONAL**.

## 1. Submission guidelines

### Article type, originality, and files

| Requirement | Status | Evidence/action |
|---|---|---|
| Select a listed article type | PASS | Deliberate Research Article choice: the formal list includes Research Article, while the scope separately welcomes public datasets/software resources |
| Work not previously published or simultaneously submitted | EXTERNAL | Affirmed in cover letter; both authors must reconfirm immediately before submission |
| All authors and responsible institution approve submission | EXTERNAL | Final coauthor/institutional sign-off required |
| Cover letter | PASS | `cover_letter.pdf`, `.tex`, and `.md` |
| Online submission through Snapp | EXTERNAL | Upload not yet performed |
| Complete editable source at submission/revision | PASS | Deterministic `manuscript_source.zip` contains TeX, BibTeX, class/style, tables, and figures |
| Author contributions and competing interests entered in interface | EXTERNAL | Statements are in manuscript; repeat them in Snapp because interface entries are authoritative |
| Permission for reused third-party text/figures/tables | N/A | All figures/tables/text are original; source data are public-domain USGS products and attributed |

### Title page and front matter

| Requirement | Status | Evidence/action |
|---|---|---|
| Concise, informative title | PASS | Non-superlative seismology/ML benchmark title |
| Author names and order | PASS | Two named authors; order fixed |
| Affiliations with department, institution, city/state/country | PASS | Complete in title block |
| Active corresponding-author email | PASS | Akshay Sharma identified with active email |
| ORCID if available | EXTERNAL | Add/confirm both ORCIDs in Snapp |
| LLM not listed as author | PASS | Only human authors listed |
| LLM use documented in Methods where applicable | PASS | “Reproducible artwork and generative AI assistance” paragraph |
| Human accountability for AI-assisted text/code | PASS | Explicit author verification and responsibility |
| Abstract 150–250 words | PASS | Validator count: 195 words |
| No undefined abbreviations/references in abstract | PASS | DYFI and AUROC defined; no citations |
| 4–6 keywords | PASS | Six keywords |
| Three non-technical highlights, each ≤120 characters | PASS | 87/72/67 characters; included below abstract and as upload text |
| Statements and Declarations heading | PASS | Exact heading present |

### Text and references

| Requirement | Status | Evidence/action |
|---|---|---|
| Springer Nature LaTeX template, `[iicol]` | PASS | `sn-jnl`, `sn-basic`, `iicol` |
| Submit source, style files, figures, and compiled PDF | PASS | Upload bundle and `main.pdf` |
| Decimal headings, maximum three visible levels | PASS | Sections, subsections, paragraph headings only |
| Define abbreviations at first use | PASS | Validator/front-matter review plus manuscript audit |
| Footnotes numbered; no endnotes | N/A | No manuscript footnotes/endnotes |
| Acknowledgements as separate title-page/front-matter section | PASS | Located immediately after Article Highlights and before Introduction |
| Author–year citations | PASS | `sn-basic` without `Numbered` option |
| Reference list alphabetized | PASS | Rendered author–year bibliography |
| Only cited published/accepted works in bibliography | PASS | Bidirectional validator; no orphan entries |
| DOI as full links where available | PASS | DOI-bearing entries render as DOI URLs; canonical JMLR exception has no DOI |
| Standard journal abbreviations, or full title if unsure | PASS | Full journal titles used consistently |
| Seismic-network/data DOI citation where applicable | PASS | USGS DYFI and ANSS ComCat cited by DOI |

### Tables

| Requirement | Status | Evidence/action |
|---|---|---|
| Arabic numbering, sequential citation | PASS | Seven generated tables |
| Explanatory captions | PASS | Every table has generated caption/note |
| Source in caption for reused material | N/A | No reused table material |
| Lowercase/asterisk table footnotes beneath table | PASS | Generated notes and superscript markers follow template |

### Figures and artwork

| Requirement | Status | Evidence/action |
|---|---|---|
| Electronic figure files supplied | PASS | Vector PDF used; PDF/PNG/SVG assets retained |
| Graphics software identified | PASS | Methods names Matplotlib 3.11.1 |
| Figure files named `Fig1`, `Fig2`, etc. | PASS | Submission-ZIP builder renames vector files and rewrites TeX include paths deterministically |
| EPS preferred for vector art | PASS | PDF vector is the native pdflatex-compatible submission format; fonts embedded |
| Embedded vector fonts | PASS | Build/asset audit |
| Line width ≥0.3 pt | PASS | Generator uses ≥0.7-pt source lines before scaling |
| 300-dpi halftone / 600-dpi combination requirements | PASS/N/A | No photographic halftones; 300-dpi PNG companions and vector originals supplied |
| RGB color | PASS | Matplotlib RGB output |
| Distinguishable in grayscale | PASS | Markers/hatching supplement color |
| Final lettering approximately 8–12 pt, consistent | PASS | Measured final lettering ≥8 pt; size variance constrained |
| No titles/captions inside artwork | PASS | Only lowercase panel labels remain; descriptions moved to captions |
| Arabic figure numbers and lowercase panel letters | PASS | Four figures; `(a)/(b)` labels where applicable |
| Concise captions in manuscript, no terminal punctuation | PASS | All four captions corrected |
| Figures cited sequentially and embedded in text | PASS | Main TeX and validator |
| Full-width figures ≤174 mm / column figures ≤84 mm | PASS | `figure*` assets fit the template text width (<174 mm) |
| Descriptive captions and contrast ≥4.5:1 | PASS | Captions describe all elements; dark text/lines on light backgrounds |
| Figure alt-text in submission/production interface | EXTERNAL | Captions satisfy manuscript accessibility; paste equivalent concise alt-text into Snapp/production fields if requested |
| No generative-AI artwork | PASS | Methods and acknowledgements state none |
| Permissions for reused artwork | N/A | All artwork generated by authors’ code |

### Supplementary information

| Requirement | Status | Evidence/action |
|---|---|---|
| SI files use standard formats, captions, numbering, accessibility | N/A | No SI is submitted; public repository is cited through Data/Code Availability |
| Large SI grouped as ZIP/GZ if used | N/A | Manuscript source ZIP is a submission source bundle, not published SI |

### Ethics, authorship, interests, and data

| Requirement | Status | Evidence/action |
|---|---|---|
| Original, honest reporting; no fabrication/manipulation/salami slicing | PASS | Frozen outputs, claim ledger, independent checks; authors reconfirm at submission |
| Permissions for software/questionnaires/scales | PASS | MIT/CC0/public-domain inputs; no individual questionnaires redistributed |
| Relevant, non-manipulative citations | PASS | Citation ledger; diverse sources; editor’s work cited only for direct scientific relevance |
| Correct author group/order and accountability | EXTERNAL | Both authors must explicitly approve final submission |
| Corresponding author manages communication/integrity | PASS/EXTERNAL | Akshay Sharma identified; reconfirm duties in Snapp |
| Funding disclosed | PASS | No specific funding |
| Financial and non-financial interests disclosed | PASS | Explicit “none” statement |
| Ethics approval heading even if N/A | PASS | Public aggregate event-level products; rationale supplied |
| Consent to participate heading even if N/A | PASS | Separate N/A statement |
| Consent for publication heading even if N/A | PASS | Separate N/A statement |
| Human/animal/biological-material requirements | N/A | No participants, identifiable records, animals, cells, tissue, or biological materials |
| Sex/gender analysis (SAGER) | N/A | No human/animal participant-level variables |
| Palaeontological/geological specimens and permits | N/A | No collected specimens or samples |
| Dual-use concern identified | N/A | Benchmark has no material public-health/security dual-use risk |
| Data and custom code support claims | PASS | Public frozen data/results/code and reconstruction |
| Data Availability Statement | PASS | CC0 derived benchmark, tagged URL, source DOIs, privacy boundary |
| Public repository strongly encouraged | PASS | Tagged GitHub release; optional Zenodo DOI remains author choice |
| Data citation with persistent identifier where available | PASS | USGS source datasets have DOIs; derived release has stable tag/URL |

### Reviewers, post-acceptance, and publishing route

| Requirement | Status | Evidence/action |
|---|---|---|
| Reviewer suggestions independent and verifiable | OPTIONAL | If supplied, use diverse institutions/countries and institutional email or ORCID/Scopus ID |
| No recent collaborators/same institution as suggestions | EXTERNAL | Check before entering any names |
| Proof corrections limited to production errors | EXTERNAL | Follow after acceptance |
| Choose publishing model and sign agreement after acceptance | EXTERNAL | Select traditional subscription route if avoiding APC |
| Open Choice optional | OPTIONAL | Not required |

## 2. Pre-submission checklist page

| Checklist topic | Status | Evidence/action |
|---|---|---|
| What editors look for / choosing a journal | PASS | Scope matrix and five directly relevant in-journal citations |
| Publication and funding | PASS/EXTERNAL | Hybrid route understood; no funding; subscription choice after acceptance |
| Submission guidelines | PASS | This matrix plus venue validator |
| Language editing | PASS | Author-reviewed language; AI assistance transparently disclosed |
| Structure and layout | PASS | Official template, required front matter/declarations |
| Figures and tables | PASS | Artwork/table checks above |
| Editorial policies | PASS | Policy sections below |
| Technical check → editor review → peer review → decision | ACKNOWLEDGED | External workflow |

## 3. Aims and scope

| Scope line | Status | Evidence |
|---|---|---|
| Observational/theoretical earthquake occurrence | PASS | Event-level DYFI macroseismology benchmark |
| Seismological data and applied analysis | PASS | Frozen public data and protected temporal evaluation |
| Machine learning/data-driven seismology | PASS | Fixed ML baselines and evaluation contract |
| Citizen science and risk communication | PASS | DYFI crowd-sourced felt reports; no operational overclaim |
| Well-documented datasets/software/open resources | PASS | Public release, audit code, tests, manifests, reproduction |
| Research Article with original data/analysis/models | PASS | Research Article selected; original benchmark analyses |

## 4. Editorial board

| Requirement/risk | Status | Evidence/action |
|---|---|---|
| Current Editor-in-Chief identified correctly | PASS | Angela Saraò, OGS |
| No author is an editor/board member | PASS | Neither author appears on board |
| No known board conflict | EXTERNAL | Authors should reconfirm no recent collaboration/personal conflict |
| Editor citation is scientifically relevant, not gratuitous | PASS | Saraò et al. (2023) directly supports crowdsourced macroseismic-data use; bibliography remains alphabetic |

## 5. Springer journal policies

| Policy | Status | Evidence/action |
|---|---|---|
| Respectful communication | ACKNOWLEDGED | Use professional correspondence |
| Authorship criteria and explicit consent | EXTERNAL | Contributions documented; both authors must consent before upload |
| Correct affiliations/names; changes restricted | EXTERNAL | Verify final spelling/order/affiliation/ORCID in Snapp |
| Confidentiality of editor/reviewer communications | ACKNOWLEDGED | Do not publish correspondence/reports without consent |
| Competing interests/funding | PASS | Complete declarations |
| Ethical responsibilities/originality/no duplicate submission | PASS/EXTERNAL | Cover letter states originality; reconfirm no simultaneous submission |
| Citation integrity | PASS | All sources checked; no hallucinated/retracted/irrelevant citation; no excessive self-citation |
| Preprints allowed and must be disclosed | PASS | Public manuscript copy disclosed in cover letter; update record after publication |
| Fundamental errors must be corrected | ACKNOWLEDGED | Versioned release and correction workflow |
| Appeals/complaints process | ACKNOWLEDGED | External post-decision process |
| Predatory references should be scrutinized | PASS | Primary/publisher sources and DOI registry checks used |
| AI supports but does not replace judgement | PASS | Human accountability and bounded use in Methods |
| AI disclosure for evaluative/interpretive assistance | PASS | Tool, tasks, exclusions, and verification disclosed |
| Manuscript confidentiality for reviewer AI tools | N/A for authors | No confidential review material supplied in this submission package |
| Digital image integrity | PASS | Code-generated figures from frozen data; no selective manipulation; source code/assets available |
| Data availability statement mandatory | PASS | Present |
| Reporting guideline checklists | N/A | Non-biomedical benchmark-resource study; no CONSORT/PRISMA/STROBE clinical design |
| Peer review model | PASS | The journal's live Ethics & Disclosures page explicitly states single-anonymous peer review; author identities are correctly retained |
| Suggested reviewer integrity/diversity | OPTIONAL/EXTERNAL | Follow policy if names are entered |

## 6. Journal ethics and disclosures page

| Requirement | Status | Evidence/action |
|---|---|---|
| Competing-interest policy | PASS | Explicit financial/non-financial statement |
| Human/animal reporting standards | N/A | No participant-level or animal research |
| COPE compliance / plagiarism screening | ACKNOWLEDGED | Originality and citation audit complete |
| Single-anonymous peer review | PASS | Confirmed on the live Ethics & Disclosures page; non-anonymized title page and public data are appropriate |

## 7. Rights, permissions, and third-party distribution

| Requirement | Status | Evidence/action |
|---|---|---|
| Permission for Springer/third-party reused content | N/A | No third-party figures/tables/text reproduced |
| RightsLink process if reuse is later introduced | ACKNOWLEDGED | Obtain article-level licence before submission |
| CC-BY material reuse follows licence terms | N/A | No externally reproduced CC-BY artwork/text |
| High-resolution third-party image requests | N/A | All figures generated in-house |
| Commercial reprints / translations / TPD | N/A | No such request |
| Accessibility requests and licensing contacts | ACKNOWLEDGED | External post-publication process |

## Remaining external actions before submission

1. Send the presubmission inquiry (optional but recommended).
2. Obtain explicit final approval from both authors and responsible institution.
3. Confirm author names, order, affiliations, and ORCIDs in Snapp.
4. Enter contributions, funding, and competing interests in Snapp.
5. Decide whether to suggest independent reviewers and verify their identities.
6. Optionally archive the release on Zenodo and add its DOI.
7. Select the traditional subscription route after acceptance if avoiding APC.
8. Enter concise figure alt-text in Snapp/production if the interface requests it.
9. Upload `manuscript_source.zip`, `main.pdf`, `cover_letter.pdf`, and
   `article_highlights.txt`.
