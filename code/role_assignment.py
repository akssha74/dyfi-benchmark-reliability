"""Pre-hashed, outcome-independent role assignment for the DYFI benchmark.

Two registered, independently-computed role manifests:

1. TEMPORAL (primary external holdout): events on/after a fixed cutoff year form
   the protected external-temporal-holdout evaluation corpus; earlier events form
   the train + development pool. Within the pre-cutoff pool, development is a
   deterministic pre-hashed slice of sequence clusters; the rest is train.

2. GEOGRAPHIC (secondary transport check): coarse region cells are held out as a
   leave-region-out transport corpus by a DOCUMENTED PROSPECTIVE RULE, not by a
   hand-picked list of region codes. A region cell is a holdout cell iff a stable
   hash of its region_code (salted, outcome-independent) falls below
   GEOGRAPHIC_HOLDOUT_FRACTION. This removes the previously hard-coded region
   constants (which encoded undocumented tectonic assumptions) in favour of a
   reproducible rule that depends only on the geographic key. Reported as an
   internal transport check (still single-source USGS).

Membership is a deterministic function of stable grouping/time/region keys ONLY,
fixed before any per-event outcome is inspected. It never reads the label.
Deterministic grouped k-fold indices (grouped by sequence) are also emitted for
within-pool baseline tuning.

Note on proxies: the temporal holdout is defined by origin_year and the
geographic holdout by region_code (lat/lon). Those fields therefore encode
holdout-role membership and must NOT be used as model predictors under the
matching transport evaluation (enforced by
leakage_audit.audit_features_against_axis; see common.EXPANDED_METADATA_SCHEMA).
"""
from __future__ import annotations

import sys
from typing import Dict, List, Sequence

from common import hash_to_unit_interval, stable_hash

# Registered role parameters (frozen before any outcome view).
TEMPORAL_CUTOFF_YEAR = 2023           # events with origin_year >= 2023 -> external holdout
DEVELOPMENT_FRACTION = 0.20           # fraction of pre-cutoff sequences used for development
ROLE_SALT = "dyfi-usgs-severe-felt-intensity-v1"
N_CV_FOLDS = 5

# Prospective leave-region-out rule: a region cell is a geographic holdout cell
# iff a salted, outcome-independent stable hash of its region_code falls below
# this fraction. No region codes are hand-picked; the holdout set is a
# reproducible function of the geographic key only.
GEOGRAPHIC_HOLDOUT_FRACTION = 0.20


def is_geographic_holdout_region(
    region: str,
    holdout_fraction: float = GEOGRAPHIC_HOLDOUT_FRACTION,
) -> bool:
    """Documented prospective, outcome-independent holdout-region predicate."""
    return hash_to_unit_interval(stable_hash(ROLE_SALT, "geo_region", region)) < holdout_fraction


def _sequence_representative_region(rows: Sequence[Dict[str, object]]) -> Dict[str, str]:
    """Map sequence_id -> region_code of its earliest (origin_time, event_id) event.

    Roles are assigned per SEQUENCE (the independence unit), so each sequence
    gets a single deterministic geographic key and cannot straddle geographic
    roles even when its member events fall in adjacent region cells.
    """
    best: Dict[str, tuple] = {}
    rep: Dict[str, str] = {}
    for r in rows:
        s = str(r["sequence_id"])
        key = (str(r.get("origin_time", "")), str(r.get("event_id", "")))
        if s not in best or key < best[s]:
            best[s] = key
            rep[s] = str(r["region_code"])
    return rep


def _sequence_year_span(rows: Sequence[Dict[str, object]]) -> Dict[str, tuple]:
    """Map sequence_id -> (min_year, max_year) over its member events."""
    span: Dict[str, tuple] = {}
    for r in rows:
        s = str(r["sequence_id"])
        y = int(float(r["origin_year"]))
        lo, hi = span.get(s, (y, y))
        span[s] = (min(lo, y), max(hi, y))
    return span


def assign_temporal_roles(
    rows: Sequence[Dict[str, object]],
    cutoff_year: int = TEMPORAL_CUTOFF_YEAR,
    development_fraction: float = DEVELOPMENT_FRACTION,
) -> List[Dict[str, object]]:
    """Assign the temporal role at the SEQUENCE level (never per raw event).

    A whole sequence is the external temporal holdout iff every one of its events
    is on/after the cutoff (min_year >= cutoff). A sequence entirely before the
    cutoff (max_year < cutoff) joins the pre-cutoff train/development pool. A
    sequence that STRADDLES the cutoff is assigned the disclosed
    ``temporal_straddle_excluded`` role and kept out of both the holdout and the
    clean pool, so no sequence can straddle roles (prevents F5) and every holdout
    event is post-cutoff / every pool event is pre-cutoff (prevents F6).
    """
    span = _sequence_year_span(rows)
    out = []
    for r in rows:
        r = dict(r)
        lo, hi = span[str(r["sequence_id"])]
        if lo >= cutoff_year:
            role = "external_temporal_holdout"
        elif hi >= cutoff_year:
            role = "temporal_straddle_excluded"
        else:
            u = hash_to_unit_interval(stable_hash(ROLE_SALT, "temporal", r["sequence_id"]))
            role = "development" if u < development_fraction else "train"
        r["role"] = role
        out.append(r)
    return out


def assign_geographic_roles(
    rows: Sequence[Dict[str, object]],
    holdout_fraction: float = GEOGRAPHIC_HOLDOUT_FRACTION,
    development_fraction: float = DEVELOPMENT_FRACTION,
) -> List[Dict[str, object]]:
    """Assign the leave-region-out role at the SEQUENCE level.

    Each sequence's single geographic key is its representative region (earliest
    member's region_code), so a sequence whose events span adjacent cells cannot
    straddle geographic roles (prevents F5). A sequence is ``geo_holdout`` iff its
    representative region satisfies the prospective holdout-region rule.
    """
    rep_region = _sequence_representative_region(rows)
    out = []
    for r in rows:
        r = dict(r)
        region = rep_region[str(r["sequence_id"])]
        if is_geographic_holdout_region(region, holdout_fraction):
            role = "geo_holdout"
        else:
            u = hash_to_unit_interval(stable_hash(ROLE_SALT, "geo", r["sequence_id"]))
            role = "development" if u < development_fraction else "train"
        r["role"] = role
        out.append(r)
    return out


def grouped_cv_folds(
    rows: Sequence[Dict[str, object]],
    n_folds: int = N_CV_FOLDS,
) -> Dict[str, int]:
    """Deterministic grouped k-fold: every event in a sequence gets one fold."""
    seqs = sorted({r["sequence_id"] for r in rows})
    fold_of_seq = {
        s: int(hash_to_unit_interval(stable_hash(ROLE_SALT, "cv", s)) * n_folds) % n_folds
        for s in seqs
    }
    return fold_of_seq


def role_stats(rows: Sequence[Dict[str, object]]) -> Dict[str, object]:
    counts: Dict[str, int] = {}
    seq_by_role: Dict[str, set] = {}
    for r in rows:
        counts[r["role"]] = counts.get(r["role"], 0) + 1
        seq_by_role.setdefault(r["role"], set()).add(r["sequence_id"])
    return {
        "event_counts_by_role": counts,
        "sequence_counts_by_role": {k: len(v) for k, v in seq_by_role.items()},
        "cutoff_year": TEMPORAL_CUTOFF_YEAR,
        "development_fraction": DEVELOPMENT_FRACTION,
        "geographic_holdout_fraction": GEOGRAPHIC_HOLDOUT_FRACTION,
        "role_salt": ROLE_SALT,
    }


def _cli(argv: List[str]) -> int:
    import argparse

    from common import read_csv, write_csv, write_json

    p = argparse.ArgumentParser(description="Pre-hashed role assignment")
    p.add_argument("--in-csv", required=True)
    p.add_argument("--mode", choices=["temporal", "geographic"], default="temporal")
    p.add_argument("--out-csv", required=True)
    p.add_argument("--out-stats", required=True)
    args = p.parse_args(argv)

    rows = read_csv(args.in_csv)
    if args.mode == "temporal":
        out = assign_temporal_roles(rows)
    else:
        out = assign_geographic_roles(rows)
    cols = list(out[0].keys()) if out else []
    write_csv(args.out_csv, out, cols)
    write_json(args.out_stats, role_stats(out))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
