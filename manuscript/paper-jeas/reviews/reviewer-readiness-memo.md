# Reviewer readiness memo

## Recommendation

**Ready for review; no scientific or evidence veto.**

## Scientific validity

Frozen cohort, threshold, split, baseline, pairwise, subgroup, and
reconstruction values pass the original 116-check manuscript validator, the
38-check JEAS validator, and 110 benchmark tests. No outcome-bearing analysis
was added during retargeting.

## Claims versus evidence

- The threshold analysis is explicitly a descriptive fixed-prediction probe,
  not endpoint-robustness evidence.
- B3 is a conservative source-only scope exclusion, not demonstrated label
  leakage.
- Dependence control is conditional on the declared 100-km/30-day heuristic.
- The public-label benchmark supports retrospective comparison; prospective
  confirmation requires fresh hidden data/service.
- The split contrast remains descriptive without an interval.
- The source-only logistic model is presented as a practical transparent
  reference, not as statistically superior to XGBoost.
- The design may be adapted to other event datasets, but transfer of the present
  DYFI model is not claimed.

## Navigation

The objective/users/decisions appear in the abstract and Introduction. Data and
provenance, benchmark design, uncertainty, results, worked qualification,
limitations, declarations, and public artifacts are separately labelled and
cross-referenced. Every headline result maps through the claim ledger to frozen
inputs.

## Reproducibility

The public release carries source data, event table, role manifest, results,
code/tests, ledgers, machine-readable corrections, manuscript source, and
submission package. The source ZIP builds byte-identically and validates
standalone.

## Remaining human actions

Confirm the target publishing-model constraint, co-author approval, portal
metadata, current APC sponsorship, and portal-generated proof before submission.
