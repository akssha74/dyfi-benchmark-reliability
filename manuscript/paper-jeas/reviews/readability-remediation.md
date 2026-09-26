# Readability remediation — JEAS v1.2.1

Scope: editorial framing only. Frozen data, models, predictions, scores,
intervals, and scientific boundaries are unchanged.

## F-R1 — Main finding sounded like a failure

- **Location:** Discussion, former paragraph “No winning model”
- **Severity:** major presentation issue
- **Former wording:** “the results do not establish a decisive winner” followed
  by a list of unsupported operational, real-time, cross-system, and causal
  benefits.
- **Reader consequence:** the paragraph ended on restrictions and hid the useful
  decision: a simple transparent model is already a strong comparison standard.
- **Correction:** lead with four supported improvements, the clear gain from
  adding depth, and the practical value of the source-only logistic model as a
  reference. Keep the unresolved XGBoost comparison explicit and retain non-use
  limits in the Limitations and Conclusion.

## F-R2 — The abstract overemphasised a secondary diagnostic

- **Location:** Abstract
- **Severity:** minor presentation issue
- **Former wording:** reported two technical random-versus-sequence point
  differences before explaining their descriptive status.
- **Reader consequence:** a secondary, underpowered diagnostic competed with the
  principal model-selection result.
- **Correction:** describe the point performance in plain language and retain
  the missing-interval boundary. Give the supported depth improvement and
  transparent reference result greater prominence.

## F-R3 — Reuse value was implicit

- **Location:** Discussion and Conclusion
- **Severity:** minor presentation issue
- **Former wording:** called the resource reusable without stating the conditions
  for reuse.
- **Reader consequence:** an editor could interpret “reusable” as an unsupported
  transfer claim or as vague future-work language.
- **Correction:** state that the comparison design can be adapted to other
  versioned, dependent event datasets only after application-specific inputs,
  grouping, holdout, reference, and uncertainty rules are defined. Explicitly
  deny transfer of the present DYFI model.

## F-R4 — Cover letter sold the caveat instead of the result

- **Location:** Cover letter and article highlights
- **Severity:** minor presentation issue
- **Former wording:** foregrounded the unresolved leading pair and false-winner
  prevention.
- **Reader consequence:** the practical result and future performance bar were
  not obvious in a quick editorial scan.
- **Correction:** lead with supported improvement over no-skill, the depth gain,
  and the transparent logistic reference; retain the unresolved XGBoost
  comparison without calling either model best.

## Boundary check

The revision does not claim equivalence, operational readiness, causality,
geographic transfer, cross-system transfer, real-time or lead-time value, or a
winning model. The random-versus-sequence comparison remains descriptive because
no uncertainty interval was retained.
