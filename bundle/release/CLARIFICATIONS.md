# Version 1 clarification record

This record clarifies four non-numeric metadata and reporting points in the
immutable version 1 results. It does not change any cohort, prediction, metric,
confidence interval, or model comparison.

## Event-grouped fold wording

The `event_grouped_note` in `results.json` says that event grouping “coincides”
with random splitting on a one-row-per-event table. The precise interpretation
is that both impose the same grouping constraint because each event has one row.
Their fold allocations are different, so their reported scores can differ.

## Protected-role status flag

`result_core.real_protected_role_opened=false` is a stale compatibility field
inherited from the synthetic reporting interface. The authoritative execution
fields are `data=PROTECTED`, `mode=protected`, `holdout_opens=1`,
`report.protected_role_opened=true`, and the consumed-token record. Together
they establish that the temporal holdout was opened exactly once. The stale
field does not affect any prediction or metric.

## Geographic result

`geographic_slice` groups the 430 temporal-holdout predictions by occupied
10-degree cell. It is a descriptive geographic subgroup summary, not an
executed leave-region-out or external geographic evaluation. Version 1 makes no
geographic-generalization claim.

## Split-contrast uncertainty

The preregistration required uncertainty for the random-versus-sequence split
contrast but did not define the paired interval estimator. The executed report
retained point estimates only. Version 1 discloses this as an unfulfilled
preregistered element and does not add a post-hoc interval, equivalence claim,
or inference that the true difference is zero.
