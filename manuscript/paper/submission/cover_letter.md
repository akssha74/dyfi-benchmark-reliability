# Cover letter (DRAFT — NOT SUBMITTED)

**Status:** Draft only. This letter has not been sent, uploaded, or submitted to any
journal or editor. It is a factual pre-submission document.

**To:** The Editors, *Journal of Seismology* (Springer Nature)

**Re:** Submission of a data/software resource paper with original benchmark analyses

---

Dear Editors,

We submit for your consideration our manuscript, *"A versioned, leakage-audited
USGS Did You Feel It? benchmark for machine-learning evaluation of severe felt
intensity."* We request handling as a **Research Article** documenting a public
seismological data/software benchmark resource.

Machine-learning studies of macroseismic felt intensity commonly use bespoke
datasets and random record-level splits. Their results are therefore difficult to
reproduce and may be vulnerable to leakage between related earthquake events.
This manuscript addresses that evaluation problem by releasing a versioned,
single-source USGS DYFI benchmark for predicting a later severe felt-intensity
label from earthquake source metadata.

The benchmark comprises a reusable evaluation protocol and accompanying
software. It provides a six-category leakage audit,
outcome-independent train/development/temporal-holdout roles based on seismic
sequence grouping, a documented endpoint with sensitivity analysis, fixed
baselines, calibration-aware scoring, Brier-score sequence-cluster bootstrap uncertainty,
and a protected single-use evaluation.

On the frozen M ≥ 5 snapshot (7,520 source records; 2,362 eligible events;
430-event temporal holdout), the difference between random and sequence-grouped
splitting is small and slightly reversed (Brier-score difference −0.006;
AUROC difference −0.012). We report this descriptive point estimate as a
split contrast, not as evidence of equivalence, a true zero effect, leakage, or
a performance gain.
Every learned baseline improves on the no-skill reference, but the direct
comparison between the two lowest-Brier models is unresolved; we name no winning
model and make no operational, real-time, cross-system, or causal claim.
The manuscript also discloses that the protocol-defined geographic transport branch
and aggregation-grid sensitivity were not executed, that alternate thresholds
rescore fixed predictions without refitting, and that the split contrast
retained a point estimate rather than the protocol-required uncertainty
interval. Non-Brier metrics likewise retain point estimates only. The protocol
record was frozen internally but has no independent pre-analysis timestamp.

The manuscript fits the *Journal of Seismology* because it treats USGS DYFI as
an observational macroseismology and citizen-science resource, and releases a
documented dataset, software tools, and a reusable evaluation contract. This
directly aligns with the journal's stated interest in machine learning,
seismological datasets, software tools, and public resources that support
transparent, reproducible earthquake science. Every numerical result is
generated from frozen analysis outputs and checked automatically; all 102
manuscript checks pass, and two clean reconstruction runs reproduce the recorded
results and holdout predictions exactly.

The versioned data, code, frozen results, and reproduction instructions are
available in the public release at
<https://github.com/akssha74/dyfi-benchmark-reliability>. A fresh public clone
reproduced the 15-page manuscript, passed all 114 manuscript checks, and passed
all 110 benchmark tests in a newly created pinned environment. The authors
received no specific funding.

The same tagged release contains a non-peer-reviewed manuscript PDF and source;
we disclose this as a preprint under Springer Nature's preprint policy. If
published, we will update the public record with the article DOI and journal URL.

The authors declare no competing interests. The study uses aggregate,
public-domain event-level metadata, involves no human participants, and
redistributes no respondent-level personally identifying information. All
generative-AI assistance is disclosed in the manuscript and was reviewed by the
authors.

We confirm the manuscript is original, is not under consideration elsewhere, and
has not been published previously. We have no suggested or opposed reviewers to
declare at this time.

Thank you for your consideration.

Sincerely,

Akshay Sharma (corresponding author) and Lalji Prasad
Department of Computer Science and Engineering, SAGE University, Indore, India
akssha74@gmail.com
