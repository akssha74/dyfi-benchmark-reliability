# Cover letter (DRAFT — NOT SUBMITTED)

**Status:** Draft only. This letter has not been sent, uploaded, or submitted.

**To:** The Editors, *Journal of Engineering and Applied Science*

**Re:** Research Article on reliable engineering model comparison

---

Dear Editors,

We submit the manuscript *“Reliable comparison of severe felt-intensity
classifiers with versioned and dependent event data: a USGS DYFI benchmark”*
for consideration as a **Research Article**.

Engineering model selection can be invalidated by catalogue revision,
outcome-derived inputs, dependent events crossing data splits, temporal
contamination, or unresolved point-score differences. The manuscript asks
whether performance and model-superiority claims remain supportable when these
risks are controlled. It contributes a released candidate-qualification
workflow for applied machine-learning engineers, benchmark maintainers, and
reviewers: candidates first pass schema, proxy, role, and temporal audits, then
are scored on a fixed temporal holdout and compared with paired
sequence-cluster uncertainty.

The frozen USGS Did You Feel It? snapshot contains 7,520 source records, 2,362
eligible events, and a 430-event temporal holdout. The worked qualification
rejects one temporal-proxy candidate before scoring, supports all four
admissible learned baselines over the no-skill reference, and leaves the two
lowest-Brier models unresolved. It therefore demonstrates two concrete
engineering decisions: which candidates are admissible and when an apparent
score advantage is insufficient to name a winner. The random-versus-sequence
diagnostic is small and reversed and is reported descriptively, not as evidence
of leakage, equivalence, or a win.

The article fits the journal's explicit scope in artificial and machine
intelligence, computer science, computational and stochastic methods, modelling
and simulation, seismic evaluation, and engineering research methods. The
journal has published comparative benchmark analysis and engineering
machine-learning model-selection studies; this manuscript extends that
contribution identity to the reliability of the comparison contract itself.

Data, code, frozen results, and reproduction instructions are available at
<https://github.com/akssha74/dyfi-benchmark-reliability>. The scientific results
are unchanged from immutable release v1.0.27; the JEAS manuscript adds only a
generated engineering-use workflow and decision tables derived from the same
frozen assets. A clean clone passes the released validators and benchmark test
suite and reconstructs the reported results.

The manuscript is original and is not under consideration elsewhere. Both
authors have approved this manuscript and its submission. The authors declare no competing
interests and no specific funding. The study uses aggregate public-domain event
metadata, involves no human participants, and redistributes no
respondent-level identifying information. Generative-AI assistance is disclosed
in the manuscript, and all assisted work was reviewed and verified by the
authors.

The public repository contains a non-peer-reviewed manuscript copy and source,
which we disclose as a preprint. It has no DOI; the software and derived data
retain their MIT and CC0 terms, respectively.

Thank you for your consideration.

Sincerely,

Akshay Sharma (corresponding author) and Lalji Prasad
Department of Computer Science and Engineering, SAGE University, Indore, India
akssha74@gmail.com
