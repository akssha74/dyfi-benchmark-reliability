# Editor decision memo

## Recommendation

**Send to external review**, subject to the authors' venue-model decision
(JEAS is sponsored open access, not hybrid).

## Thirty-second paraphrase

This Research Article releases and demonstrates a retrospective engineering
benchmark that prevents invalid severe felt-intensity classifier comparisons
caused by disallowed inputs, dependent-event splitting, unresolved score
differences, and unreproducible data/software state.

## Contribution identity

Primary: benchmark and engineering model-comparison test harness.
Secondary: reproducible dataset/software resource.

## Goal and usefulness

The paper asks whether candidate performance and superiority claims remain
supportable under predefined input, grouping, temporal, uncertainty, and
reproducibility rules. Applied-ML engineers, benchmark maintainers, and
reviewers use the release for transparent retrospective comparison. It supports
admission and improvement decisions and prevents out-of-contract comparisons
and false winner declarations.

## Substantive result

Four learned baselines improve over no-skill under paired Brier uncertainty, the
source-only logistic model clearly improves on magnitude alone, and it has the
same rounded Brier score as XGBoost. Their paired comparison remains unresolved,
making the simpler model a strong transparent reference rather than a declared winner.
One event-year candidate lies outside the source-only contract, and the
random-versus-sequence contrast remains descriptive.

## Venue fit

The contribution matches JEAS scope in artificial and machine intelligence,
computational methods, modelling/simulation, seismic evaluation, and
engineering research methods. Four substantively relevant JEAS papers establish
benchmark, applied-ML comparison, and seismic-engineering precedent.

## Principal boundaries

The labels are public, so prospective confirmation requires fresh hidden data
or an independent evaluation service. The work is not a real-time warning,
operational triage, causal, or geographic-transfer study.

## Strongest potential desk objection

The benchmark uses established statistical tools and is not a new seismological
model. Its contribution is the tested engineering comparison process and the
decision it supports: future severe-intensity methods must pass the same input
and split checks and show a paired improvement over the transparent logistic
reference before added complexity is treated as useful.
