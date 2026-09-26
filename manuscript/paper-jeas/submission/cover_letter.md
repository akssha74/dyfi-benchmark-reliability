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
risks are controlled. It contributes a released retrospective qualification
workflow for applied machine-learning engineers, benchmark maintainers, and
reviewers: declared candidates first pass schema, proxy, role, and temporal audits, then
are scored on a fixed temporal holdout and compared with paired
sequence-cluster uncertainty.

The frozen USGS Did You Feel It? snapshot contains 7,520 source records, 2,362
eligible events, and a 430-event temporal holdout. The worked qualification
excludes one candidate outside the declared source-only schema, supports all four
admissible learned baselines over the no-skill reference, and shows that adding
depth improves on a magnitude-only logistic model. The source-only logistic
model and XGBoost both round to Brier 0.181, and their paired comparison remains
unresolved. The simpler logistic model therefore provides a strong, transparent
reference for future methods without being declared superior.
These results give engineers two concrete decisions: which candidates are valid
to compare and whether added complexity has shown a measurable improvement.
They also set a clear bar that future severe-intensity models can be tested
against.

The article fits the journal's explicit scope in artificial and machine
intelligence, computer science, computational and stochastic methods, modelling
and simulation, seismic evaluation, and engineering research methods. The
journal has published comparative benchmark analysis and engineering
machine-learning model-selection studies; this manuscript extends that
contribution identity to the reliability of the comparison contract itself.

Data, code, frozen results, and reproduction instructions are available at
<https://github.com/akssha74/dyfi-benchmark-reliability>. The scientific results
come from the scientific core frozen in release v1.0.27; JEAS release v1.2.4
packages that unchanged core with an engineering-use workflow and
decision tables derived from the same assets. A clean clone passes the released
validators and benchmark test suite and reconstructs the reported results.

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
