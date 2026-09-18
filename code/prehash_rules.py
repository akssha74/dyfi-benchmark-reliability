"""Pre-hashed, outcome-INDEPENDENT role and quarantine rules for the DYFI-USGS
single-source severe-felt-intensity benchmark (acquisition/reconstruction stage).

This module PINS and HASHES -- but does NOT activate -- the two rule families
that must be fixed *before* any per-event outcome is inspected:

  1. ROLE rules: the temporal-cutoff / geographic-holdout / development-fraction /
     grouped-CV parameters that ``role_assignment`` uses. These read only
     provenance/time/region grouping keys, never the label, so pinning and
     hashing them now cannot leak an outcome.

  2. QUARANTINE rules: a closed, documented set of outcome-independent predicates
     that remove an event from the resource for a catalogue-integrity reason
     (test/quarry blast, non-earthquake, duplicate authoritative origin, out of
     the pinned space-time-magnitude envelope, corrupt geometry). Each rule is a
     function of source metadata ONLY. An explicit (currently empty) frozen list
     of hand-quarantined event ids is also carried; adding one is a logged,
     reason-bearing act, never a silent drop.

The point of pre-hashing is a fail-closed lock: the one-shot runner records these
digests, and any later drift in a role parameter or quarantine rule changes the
digest and aborts the protected run. Nothing here fetches data, opens a protected
cohort, reads a real outcome, or fits a model.
"""
from __future__ import annotations

import dataclasses
import sys
from typing import Dict, List, Tuple

import common
import role_assignment

# ---------------------------------------------------------------------------
# Pinned acquisition envelope (outcome-independent selection window).
# These are the FDSN query bounds; they are provenance/selection keys, not
# labels, so they belong to the pre-hash lock.
# ---------------------------------------------------------------------------
ACQUISITION_ENVELOPE: Dict[str, object] = {
    "producttype": "dyfi",
    "minmagnitude": 5.0,
    "starttime": "2015-01-01T00:00:00Z",
    "endtime": "2025-01-01T00:00:00Z",
    "orderby": "time-asc",
    "eventtype": "earthquake",
    "note": (
        "M>=5 DYFI-bearing events over the pinned decade; the magnitude floor, "
        "product type, and time bounds are outcome-independent selection keys."
    ),
}


# ---------------------------------------------------------------------------
# Quarantine rules: outcome-independent catalogue-integrity predicates.
# Each entry is (rule_id, description). The runtime predicate lives in
# ``quarantine_reason`` below and reads ONLY source metadata.
# ---------------------------------------------------------------------------
QUARANTINE_RULES: Tuple[Tuple[str, str], ...] = (
    (
        "Q1_non_earthquake_event_type",
        "eventtype is not 'earthquake' (quarry blast, explosion, ice quake, "
        "sonic boom, etc.); these are not the tectonic population and are "
        "removed independently of any felt outcome.",
    ),
    (
        "Q2_outside_pinned_envelope",
        "origin_time outside [2015-01-01, 2025-01-01) or magnitude < 5.0; the "
        "event falls outside the pinned acquisition envelope and must not enter "
        "the resource even if it appears in a wider re-query.",
    ),
    (
        "Q3_corrupt_or_missing_geometry",
        "longitude/latitude/depth missing, non-finite, or out of physical range "
        "(|lat|>90, |lon|>180, depth<-10 km); a geometry that cannot be placed "
        "on the grid is quarantined rather than coerced.",
    ),
    (
        "Q4_duplicate_authoritative_origin",
        "a second feature shares this event's authoritative (network,eventid) "
        "origin; the non-authoritative revision is quarantined so a revision "
        "cannot enter twice (handled with the revision-reconciliation receipt).",
    ),
    (
        "Q5_explicit_listed_quarantine_id",
        "the event id is on the frozen, reason-bearing manual quarantine list "
        "below; each addition is logged, never silent.",
    ),
)

# Frozen, reason-bearing manual quarantine list. Adding an id is a logged act
# that changes the pre-hash digest. The two ids below are the events whose
# aggregate report counts were inspected during antecedent source verification
# (outcome_boundaries.json:quarantined_inspected_events); they are excluded from
# every train/development/holdout role so no previously-inspected event can enter
# the resource. This is the C5/Q5 activation change (binding condition Q5 of
# review/lock-review-opus48/independent_lock_review.json): a logged, non-silent,
# digest-changing addition made BEFORE any role is materialized. The reasons are
# outcome-INDEPENDENT (they concern prior inspection/exposure, not any label).
MANUAL_QUARANTINE_IDS: Tuple[Dict[str, str], ...] = (
    {
        "event_id": "ci40925991",
        "reason": "Its aggregate report count was exposed during antecedent source "
                  "verification (and as the DYFI sample event); exclude from every role.",
        "added_at": "2026-09-01",
        "authorization": "independent_lock_review.json binding condition Q5",
    },
    {
        "event_id": "us6000pgsd",
        "reason": "A prior broad source-code search surfaced one of its rows; exclude "
                  "if later found eligible.",
        "added_at": "2026-09-01",
        "authorization": "independent_lock_review.json binding condition Q5",
    },
)

# Physical geometry bounds for Q3.
_LAT_ABS_MAX = 90.0
_LON_ABS_MAX = 180.0
_DEPTH_MIN_KM = -10.0
_DEPTH_MAX_KM = 1000.0

# Pinned envelope numeric bounds for Q2 (kept in lockstep with ACQUISITION_ENVELOPE).
_ENVELOPE_MIN_MAG = 5.0
_ENVELOPE_START_YEAR = 2015
_ENVELOPE_END_YEAR_EXCL = 2025


def manual_quarantine_id_list() -> List[str]:
    """The frozen manual (Q5) quarantine event ids, sorted for determinism.

    These ids must be dropped from the reconstruction (parse_geojson quarantine
    set) so no previously-inspected event enters any role. Reading this list is
    outcome-independent (it is a fixed set of ids, never a label)."""
    return sorted(str(d["event_id"]) for d in MANUAL_QUARANTINE_IDS)


def quarantine_reason(event: Dict[str, object]) -> str:
    """Return the FIRST matching quarantine rule id for an event, or '' if clean.

    Reads ONLY outcome-independent source metadata: eventtype, magnitude,
    origin_year, latitude, longitude, depth_km, event_id. Never reads cdi/felt or
    any label field, so it is safe to fix before outcome inspection.
    """
    listed = {d["event_id"] for d in MANUAL_QUARANTINE_IDS}
    eid = str(event.get("event_id", ""))
    if eid in listed:
        return "Q5_explicit_listed_quarantine_id"

    etype = str(event.get("eventtype", "earthquake")).strip().lower()
    if etype and etype != "earthquake":
        return "Q1_non_earthquake_event_type"

    try:
        mag = float(event["magnitude"])
    except (KeyError, TypeError, ValueError):
        return "Q3_corrupt_or_missing_geometry"
    try:
        year = int(float(event["origin_year"]))
    except (KeyError, TypeError, ValueError):
        return "Q2_outside_pinned_envelope"
    if mag < _ENVELOPE_MIN_MAG or year < _ENVELOPE_START_YEAR or year >= _ENVELOPE_END_YEAR_EXCL:
        return "Q2_outside_pinned_envelope"

    try:
        lat = float(event["latitude"])
        lon = float(event["longitude"])
        depth = float(event["depth_km"])
    except (KeyError, TypeError, ValueError):
        return "Q3_corrupt_or_missing_geometry"
    finite = all(v == v and abs(v) != float("inf") for v in (lat, lon, depth))
    if not finite:
        return "Q3_corrupt_or_missing_geometry"
    if abs(lat) > _LAT_ABS_MAX or abs(lon) > _LON_ABS_MAX:
        return "Q3_corrupt_or_missing_geometry"
    if depth < _DEPTH_MIN_KM or depth > _DEPTH_MAX_KM:
        return "Q3_corrupt_or_missing_geometry"
    return ""


@dataclasses.dataclass(frozen=True)
class PreHashLock:
    """Immutable digest bundle of the outcome-independent role + quarantine rules."""

    role_rules_digest: str
    quarantine_rules_digest: str
    envelope_digest: str
    combined_digest: str
    activated: bool


def role_rules_record() -> Dict[str, object]:
    """The pinned, outcome-independent role parameters (from role_assignment)."""
    return {
        "temporal_cutoff_year": role_assignment.TEMPORAL_CUTOFF_YEAR,
        "development_fraction": role_assignment.DEVELOPMENT_FRACTION,
        "geographic_holdout_fraction": role_assignment.GEOGRAPHIC_HOLDOUT_FRACTION,
        "role_salt": role_assignment.ROLE_SALT,
        "n_cv_folds": role_assignment.N_CV_FOLDS,
        "decluster_space_km": 100.0,
        "decluster_time_days": 30.0,
        "assignment_unit": "sequence",
        "reads_label": False,
    }


def quarantine_rules_record() -> Dict[str, object]:
    """The pinned, outcome-independent quarantine rule set."""
    return {
        "rules": [{"rule_id": rid, "description": desc} for rid, desc in QUARANTINE_RULES],
        "manual_quarantine_ids": [dict(d) for d in MANUAL_QUARANTINE_IDS],
        "geometry_bounds": {
            "lat_abs_max": _LAT_ABS_MAX,
            "lon_abs_max": _LON_ABS_MAX,
            "depth_min_km": _DEPTH_MIN_KM,
            "depth_max_km": _DEPTH_MAX_KM,
        },
        "envelope_bounds": {
            "min_magnitude": _ENVELOPE_MIN_MAG,
            "start_year": _ENVELOPE_START_YEAR,
            "end_year_exclusive": _ENVELOPE_END_YEAR_EXCL,
        },
        "reads_label": False,
    }


def compute_lock() -> PreHashLock:
    """Deterministically hash the role + quarantine + envelope rules.

    ``activated`` is always False here: pre-hashing pins the rules for the
    fail-closed lock but performs NO real acquisition or outcome execution.
    """
    role_digest = common.sha256_text(common.canonical_json(role_rules_record()))
    quar_digest = common.sha256_text(common.canonical_json(quarantine_rules_record()))
    env_digest = common.sha256_text(common.canonical_json(ACQUISITION_ENVELOPE))
    combined = common.sha256_text(
        common.canonical_json(
            {
                "role_rules_digest": role_digest,
                "quarantine_rules_digest": quar_digest,
                "envelope_digest": env_digest,
            }
        )
    )
    return PreHashLock(
        role_rules_digest=role_digest,
        quarantine_rules_digest=quar_digest,
        envelope_digest=env_digest,
        combined_digest=combined,
        activated=False,
    )


def lock_record() -> Dict[str, object]:
    """Full machine-readable pre-hash record for ``role_quarantine_prehash.json``."""
    lock = compute_lock()
    return {
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "record_type": "outcome_independent_role_and_quarantine_prehash",
        "activated": lock.activated,
        "activation_note": (
            "Rules are PINNED and HASHED only. Real acquisition/outcome execution "
            "is disabled until contract lock + activation token are supplied; the "
            "runner records combined_digest and fails closed on any drift."
        ),
        "role_rules": role_rules_record(),
        "quarantine_rules": quarantine_rules_record(),
        "acquisition_envelope": dict(ACQUISITION_ENVELOPE),
        "digests": {
            "role_rules_digest": lock.role_rules_digest,
            "quarantine_rules_digest": lock.quarantine_rules_digest,
            "envelope_digest": lock.envelope_digest,
            "combined_digest": lock.combined_digest,
        },
    }


def _cli(argv: List[str]) -> int:
    import argparse

    from common import write_json

    p = argparse.ArgumentParser(description="Pre-hash role + quarantine rules")
    p.add_argument("--out", help="write role_quarantine_prehash.json here")
    args = p.parse_args(argv)
    rec = lock_record()
    if args.out:
        write_json(args.out, rec)
    print("combined_digest:", rec["digests"]["combined_digest"])
    print("activated:", rec["activated"])
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
