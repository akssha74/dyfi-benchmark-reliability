"""Shared, dependency-free deterministic utilities for the single-source USGS DYFI
severe-felt-intensity benchmark resource.

Scope: this is a RETROSPECTIVE, USGS-only benchmark-resource. Nothing here makes
an operational, real-time, pre-report, EMSC, or winning-method claim. These
modules only reconstruct the resource, run the leakage audit, construct the
endpoint, group events, and assign outcome-independent roles.

Design constraints:
- Python 3.9+, standard library ONLY. These stdlib utilities intentionally do
  NOT implement the named reference baselines (e.g. scikit-learn logistic
  regression / gradient boosting, XGBoost). Those baselines require their real
  third-party libraries and are out of scope for this file; NO pure-stdlib
  stand-in for a named baseline is provided here, because a hand-rolled
  substitute would not be the named method and would misrepresent the comparison.
- All floating-point summaries are computed with plain Python floats and rounded
  only at serialization, so two clean reruns reproduce results exactly (<= 1e-12).

Feature honesty: two schemas are exposed (see FEATURE_SCHEMAS). The SOURCE_ONLY
schema contains only source-intrinsic physical covariates (magnitude, depth).
The EXPANDED_METADATA schema additionally exposes origin_year (a TEMPORAL proxy)
and latitude/longitude (GEOGRAPHIC proxies). Those proxy fields coincide with the
axes used to define the temporal and geographic holdouts, so they are disclosed
as proxies and must be excluded whenever the matching transport holdout is
evaluated (enforced by leakage_audit.audit_features_against_axis).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
from typing import Any, Dict, Iterable, List, Sequence, Tuple

SCHEMA_VERSION = 2


@dataclasses.dataclass(frozen=True)
class FeatureSchema:
    """A strict, immutable predictor schema.

    ``features`` is the exact, ordered set of columns a model may consume under
    this schema. ``proxy_features`` is the subset that are temporal/geographic
    proxies for a holdout axis and are therefore unsafe under the matching
    transport evaluation. ``proxy_axis`` maps each proxy field to the axis it
    leaks ("temporal" or "geographic").
    """

    name: str
    features: Tuple[str, ...]
    proxy_features: Tuple[str, ...]
    proxy_axis: Dict[str, str]
    description: str


# Source-intrinsic physical covariates only. No temporal/geographic proxy.
SOURCE_ONLY_SCHEMA = FeatureSchema(
    name="source_only",
    features=("magnitude", "depth_km"),
    proxy_features=(),
    proxy_axis={},
    description=(
        "Physical source covariates that are not proxies for any holdout axis; "
        "the only schema safe under both temporal and geographic transport."
    ),
)

# Adds honestly-labelled temporal/geographic proxies.
EXPANDED_METADATA_SCHEMA = FeatureSchema(
    name="expanded_metadata",
    features=("magnitude", "depth_km", "latitude", "longitude", "origin_year"),
    proxy_features=("latitude", "longitude", "origin_year"),
    proxy_axis={
        "latitude": "geographic",
        "longitude": "geographic",
        "origin_year": "temporal",
    },
    description=(
        "Source covariates plus disclosed temporal (origin_year) and geographic "
        "(latitude, longitude) proxies. origin_year proxies the temporal-holdout "
        "cutoff and lat/lon proxy the geographic-holdout cells, so each proxy is "
        "leakage under its matching transport evaluation and must be dropped there."
    ),
)

FEATURE_SCHEMAS: Dict[str, FeatureSchema] = {
    SOURCE_ONLY_SCHEMA.name: SOURCE_ONLY_SCHEMA,
    EXPANDED_METADATA_SCHEMA.name: EXPANDED_METADATA_SCHEMA,
}

# Back-compat default surface: the strictest (source-only) schema.
ALLOWED_FEATURES: Tuple[str, ...] = SOURCE_ONLY_SCHEMA.features

# Provenance/grouping/eligibility columns present in the released table but
# FORBIDDEN as model inputs. num_responses is a POST-REPORT ascertainment
# quantity (it counts felt reports gathered after the event) and is therefore
# never a predictor; region_code is a geographic proxy for the geographic
# holdout axis.
NON_PREDICTIVE_COLUMNS: Tuple[str, ...] = (
    "event_id",
    "product_version_id",
    "access_date",
    "source_payload_sha256",
    "origin_time",
    "region_code",
    "num_responses",
    "max_cdi",
    "severe_label",
    "sequence_id",
    "role",
)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def canonical_json(obj: Any) -> str:
    """Deterministic JSON serialization (sorted keys, fixed separators)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(*parts: Any) -> str:
    """Outcome-independent stable hash of the given key parts.

    Used for pre-hashed role and fold assignment. It reads ONLY provenance /
    grouping / time / region keys, never the label.
    """
    return sha256_text("|".join(str(p) for p in parts))


def hash_to_unit_interval(key: str) -> float:
    """Map a stable hash to a deterministic float in [0, 1)."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(1 << 64)


def region_code(lat: float, lon: float, cell_deg: float = 10.0) -> str:
    """Deterministic coarse geographic cell code from epicentre lat/lon.

    A 10-degree grid cell is a stable, outcome-independent transform of the
    catalogue coordinates. It is used ONLY as the grouping unit for the
    leave-region-out transport holdout, never as a model predictor: it is a
    geographic proxy for the geographic-holdout axis (see NON_PREDICTIVE_COLUMNS
    and EXPANDED_METADATA_SCHEMA.proxy_axis).
    """
    la = math.floor(lat / cell_deg) * int(cell_deg)
    lo = math.floor(lon / cell_deg) * int(cell_deg)
    return f"G{la:+04d}{lo:+05d}"


def read_csv(path: str) -> List[Dict[str, str]]:
    import csv

    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: str, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    import csv

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames))
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def strict_float(value: Any, field: str) -> float:
    """Parse a float with an explicit, non-silent contract."""
    if value is None or value == "":
        raise ValueError(f"missing required numeric field {field!r}")
    return float(value)


def strict_int(value: Any, field: str) -> int:
    """Parse an integer, REJECTING (not silently truncating) fractional input."""
    if value is None or value == "":
        raise ValueError(f"missing required integer field {field!r}")
    f = float(value)
    if not f.is_integer():
        raise ValueError(
            f"field {field!r} expected integer but got fractional value {value!r}"
        )
    return int(f)


def normalize_field_name(name: str) -> str:
    """Normalize a column name for leakage matching: lowercase, strip separators."""
    return "".join(ch for ch in name.lower() if ch.isalnum())
