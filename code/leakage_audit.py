"""Deterministic multi-family leakage audit for the single-source USGS DYFI
benchmark resource.

Three audit surfaces:

1. Field-level audit (families F1-F4): given the set of column names a model would
   consume and a target FeatureSchema, reject any name that is a forbidden field
   or a proxy for one, matched robustly against name variants (exact / affixed /
   case / punctuation / near-synonym). Accept ONLY the exact schema.

2. Axis (role) leakage audit: given the candidate fields and the evaluation axis
   ("temporal" or "geographic"), reject any field that is a proxy for that axis
   (origin_year under a temporal holdout; latitude/longitude/region_code under a
   geographic holdout). This catches the case where an expanded-schema proxy
   silently encodes holdout-role membership.

3. Split-level audit (families F5-F6): given a role manifest, reject any seismic
   sequence whose events straddle >1 role (F5 sequence/geographic cross-role
   leakage) and any temporal-cutoff violation (F6 future events informing past
   roles).

The audit is the load-bearing, power-free resource utility: it must reject 100%
of seeded forbidden fixtures and accept the exact clean schema.
"""
from __future__ import annotations

import sys
from typing import Dict, List, Sequence, Tuple

from common import (
    EXPANDED_METADATA_SCHEMA,
    SOURCE_ONLY_SCHEMA,
    FeatureSchema,
    normalize_field_name,
)

# Forbidden root tokens per leakage family. A candidate field name leaks if its
# normalized form equals, contains, or is contained by any of these roots (with
# a minimum-length guard to avoid trivial substring false positives).
FORBIDDEN_FAMILIES: Dict[str, List[str]] = {
    # F1: direct label or its report-derived constituents.
    "F1_direct_label_or_constituent": [
        "cdi", "maxcdi", "mmi", "maxmmi", "severelabel", "severe", "label",
        "dyfiintensity", "intensity", "feltintensity", "cdigeo", "cdizip",
        "dyfigeo", "perlocationintensity", "y", "target",
    ],
    # F2: post-outcome ascertainment / revision proxies.
    "F2_post_outcome_ascertainment_or_revision": [
        "numresponses", "numresp", "nresp", "felt", "responses", "responsecount",
        "reportcount", "updated", "asoffinal", "revisedflag", "postreport",
    ],
    # F3: identifier / source proxies (memorisation channels).
    "F3_identifier_or_source_proxy": [
        "eventid", "id", "ids", "net", "network", "source", "sourcecode", "code",
        "contributor", "author", "authorid", "sequenceid", "eventkey", "detail",
    ],
    # F4: downstream product proxies (different information set, out of scope).
    "F4_downstream_product_proxy": [
        "shakemap", "shakemapmmi", "pager", "pga", "pgv", "instrumentalmmi",
        "groundmotion", "sa03", "sa10", "sa30",
    ],
}

# Axis-proxy roots. These fields are only leakage RELATIVE to a chosen holdout
# axis (they are legitimate covariates in the expanded schema when no matching
# transport holdout is being evaluated), so they are handled by the axis audit
# rather than the unconditional forbidden families above.
AXIS_PROXY_ROOTS: Dict[str, List[str]] = {
    "temporal": ["originyear", "year", "origintime", "epoch", "timestamp", "date"],
    "geographic": ["latitude", "longitude", "regioncode", "region", "geocell", "gridcell"],
}

_MIN_ROOT_LEN = 2


def _field_leaks(field: str, allowed_norm: Sequence[str]) -> Tuple[bool, str, str]:
    """Return (leaks, family, root) for a single candidate field name.

    A field in ``allowed_norm`` (the active schema's normalized allowlist) is
    never flagged by the unconditional families; axis-relative proxy leakage is
    tested separately by :func:`audit_features_against_axis`.
    """
    norm = normalize_field_name(field)
    if norm in allowed_norm:
        return (False, "", "")
    for family, roots in FORBIDDEN_FAMILIES.items():
        for root in roots:
            if len(root) < _MIN_ROOT_LEN:
                continue
            # exact, affix (root is a prefix/suffix/substring of the field), or the
            # field is a substring of a longer forbidden root spelling.
            if norm == root or root in norm or (len(norm) >= _MIN_ROOT_LEN and norm in root):
                return (True, family, root)
    return (False, "", "")


def audit_feature_names(
    feature_names: Sequence[str],
    schema: FeatureSchema = SOURCE_ONLY_SCHEMA,
) -> Dict[str, object]:
    """Field-level audit (F1-F4) against a chosen FeatureSchema.

    Returns a report dict. A model input set PASSES iff every field is in the
    exact schema (same members, same canonical order) and nothing else. Under
    ``SOURCE_ONLY_SCHEMA`` the temporal/geographic proxy fields are not in the
    allowlist and are rejected; under ``EXPANDED_METADATA_SCHEMA`` they are
    permitted here but flagged for the axis audit.
    """
    allowed_norm = {normalize_field_name(f) for f in schema.features}
    rejected: List[Dict[str, str]] = []
    accepted: List[str] = []
    for f in feature_names:
        leaks, family, root = _field_leaks(f, allowed_norm)
        if leaks:
            rejected.append({"field": f, "family": family, "matched_root": root})
        elif normalize_field_name(f) in allowed_norm:
            accepted.append(f)
        else:
            # Unknown field that is not explicitly allowed: reject conservatively.
            rejected.append({"field": f, "family": "F0_unknown_non_allowlisted", "matched_root": ""})
    exact_clean = tuple(feature_names) == tuple(schema.features)
    return {
        "schema": schema.name,
        "passed": len(rejected) == 0 and exact_clean,
        "exact_clean_schema": exact_clean,
        "n_fields": len(feature_names),
        "n_rejected": len(rejected),
        "rejected": rejected,
        "accepted": accepted,
        "declared_proxy_features": list(schema.proxy_features),
    }


def audit_features_against_axis(
    feature_names: Sequence[str],
    axis: str,
) -> Dict[str, object]:
    """Axis (role) leakage audit.

    Given the evaluation ``axis`` ("temporal" or "geographic"), reject any
    candidate field that is a proxy for that axis. This is the field-vs-role
    leakage check: a temporal holdout must not receive origin_year, and a
    geographic (leave-region-out) holdout must not receive lat/lon/region_code,
    because those fields directly encode holdout-role membership.
    """
    if axis not in AXIS_PROXY_ROOTS:
        raise ValueError(f"unknown evaluation axis {axis!r}")
    roots = AXIS_PROXY_ROOTS[axis]
    leaking: List[Dict[str, str]] = []
    for f in feature_names:
        norm = normalize_field_name(f)
        for root in roots:
            if norm == root or root in norm or (len(norm) >= _MIN_ROOT_LEN and norm in root):
                leaking.append({"field": f, "axis": axis, "matched_root": root})
                break
    return {
        "axis": axis,
        "passed": len(leaking) == 0,
        "n_axis_proxy_leaks": len(leaking),
        "axis_proxy_leaks": leaking,
    }


def audit_role_manifest(rows: Sequence[Dict[str, str]], temporal_cutoff_year: int) -> Dict[str, object]:
    """Split-level audit (F5-F6) over an assigned event table.

    Each row must carry: sequence_id, role, origin_year. Roles containing the
    substring 'holdout' are treated as evaluation roles; others as development.
    F5: a sequence_id may not appear in more than one role.
    F6 (temporal manifests only): temporal-holdout events must be on/after the
        cutoff; development/train events must be strictly before it. The F6
        development-side constraint is only meaningful for a TEMPORAL manifest,
        so it is applied only when the manifest actually contains a temporal
        holdout role; a purely geographic manifest is exempt. The disclosed
        'temporal_straddle_excluded' role is exempt from both F6 checks.
    """
    has_temporal_holdout = any(
        ("temporal" in r["role"] and "holdout" in r["role"]) for r in rows
    )
    seq_to_roles: Dict[str, set] = {}
    f6_violations: List[Dict[str, str]] = []
    for r in rows:
        seq = r["sequence_id"]
        role = r["role"]
        seq_to_roles.setdefault(seq, set()).add(role)
        year = int(float(r["origin_year"]))
        is_temporal_holdout = ("temporal" in role and "holdout" in role)
        is_dev = role in ("train", "development")
        if is_temporal_holdout and year < temporal_cutoff_year:
            f6_violations.append({"sequence_id": seq, "role": role, "origin_year": str(year)})
        if has_temporal_holdout and is_dev and year >= temporal_cutoff_year:
            f6_violations.append({"sequence_id": seq, "role": role, "origin_year": str(year)})
    f5_violations = [
        {"sequence_id": s, "roles": ",".join(sorted(roles))}
        for s, roles in seq_to_roles.items()
        if len(roles) > 1
    ]
    return {
        "passed": len(f5_violations) == 0 and len(f6_violations) == 0,
        "F5_sequence_cross_role_violations": f5_violations,
        "F6_temporal_leakage_violations": f6_violations,
    }


def _cli(argv: List[str]) -> int:
    import argparse

    from common import read_csv, load_json, write_json

    p = argparse.ArgumentParser(description="DYFI benchmark leakage audit")
    p.add_argument("--feature-names", nargs="*", help="candidate model input field names")
    p.add_argument(
        "--schema",
        choices=[SOURCE_ONLY_SCHEMA.name, EXPANDED_METADATA_SCHEMA.name],
        default=SOURCE_ONLY_SCHEMA.name,
        help="feature schema to audit the field names against",
    )
    p.add_argument(
        "--axis",
        choices=["temporal", "geographic"],
        help="evaluation axis for the field-vs-role (proxy) leakage audit",
    )
    p.add_argument("--assigned-table", help="CSV with sequence_id, role, origin_year")
    p.add_argument("--cutoff-year", type=int, default=2023)
    p.add_argument("--out", help="write JSON report here")
    args = p.parse_args(argv)

    schema = SOURCE_ONLY_SCHEMA if args.schema == SOURCE_ONLY_SCHEMA.name else EXPANDED_METADATA_SCHEMA
    report: Dict[str, object] = {}
    if args.feature_names is not None:
        report["field_level"] = audit_feature_names(args.feature_names, schema=schema)
        if args.axis:
            report["axis_level"] = audit_features_against_axis(args.feature_names, args.axis)
    if args.assigned_table:
        rows = read_csv(args.assigned_table)
        report["split_level"] = audit_role_manifest(rows, args.cutoff_year)
    ok = all(
        v.get("passed", False) for v in report.values() if isinstance(v, dict)
    ) and bool(report)
    report["overall_passed"] = ok
    if args.out:
        write_json(args.out, report)
    print("PASS" if ok else "FAIL", report if not args.out else args.out)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
