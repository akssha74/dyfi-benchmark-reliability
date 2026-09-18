"""Deterministic reconstruction pipeline for the DYFI-USGS benchmark, with typed
stage boundaries and immutable per-stage manifests.

The pipeline is the fixed, ordered composition of the six repaired core modules:

    ingest_eligibility.parse_geojson
        -> endpoint.add_labels
        -> decluster.assign_sequences        (order-stable)
        -> role_assignment.assign_*_roles     (pre-hashed, outcome-independent)
        -> leakage_audit.audit_role_manifest  (F5/F6 split-level gate)

Each stage emits a frozen :class:`StageManifest` carrying the stage name, its
parameters, input/output row counts, and content digests of the input and output
tables. The manifests are immutable (frozen dataclasses) and chained into a single
:class:`ReconstructionResult` whose ``pipeline_digest`` fixes the whole
reconstruction. A leakage-audit failure at the final stage fails the pipeline
closed rather than returning a partially-audited table.

This module performs NO acquisition and reads whatever GeoJSON dict it is handed;
in this stage that dict is always SYNTHETIC. It does not fetch, does not open a
protected cohort, and the endpoint/label step is only run because the caller
already holds the (synthetic) outcome field.
"""
from __future__ import annotations

import dataclasses
from typing import Dict, List, Optional, Sequence, Tuple

import common
import decluster
import endpoint
import ingest_eligibility
import leakage_audit
import role_assignment


def _digest_rows(rows: Sequence[Dict[str, object]]) -> str:
    """Order-independent content digest of a row table (sorted canonical JSON)."""
    canon = sorted(common.canonical_json(r) for r in rows)
    return common.sha256_text(common.canonical_json(canon))


@dataclasses.dataclass(frozen=True)
class StageManifest:
    """Immutable record of one reconstruction stage boundary."""

    stage: str
    params: str            # canonical-json of the stage parameters
    n_in: int
    n_out: int
    input_digest: str
    output_digest: str
    extra: str = "{}"      # canonical-json of any stage-specific stats

    def as_dict(self) -> Dict[str, object]:
        return {
            "stage": self.stage,
            "params": self.params,
            "n_in": self.n_in,
            "n_out": self.n_out,
            "input_digest": self.input_digest,
            "output_digest": self.output_digest,
            "extra": self.extra,
        }

    def digest(self) -> str:
        return common.sha256_text(common.canonical_json(self.as_dict()))


@dataclasses.dataclass(frozen=True)
class ReconstructionResult:
    """Immutable result of the full pipeline: manifests + final audited table."""

    mode: str
    manifests: Tuple[StageManifest, ...]
    n_eligible: int
    n_sequences: int
    role_counts: str            # canonical-json of role -> count
    leakage_passed: bool
    pipeline_digest: str
    rows: Tuple[Dict[str, object], ...] = dataclasses.field(
        default_factory=tuple, repr=False
    )

    def manifest_record(self) -> Dict[str, object]:
        return {
            "record_type": "reconstruction_manifest",
            "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
            "mode": self.mode,
            "n_eligible": self.n_eligible,
            "n_sequences": self.n_sequences,
            "role_counts": self.role_counts,
            "leakage_passed": self.leakage_passed,
            "stages": [m.as_dict() for m in self.manifests],
            "stage_digests": [m.digest() for m in self.manifests],
            "pipeline_digest": self.pipeline_digest,
        }


class ReconstructionError(RuntimeError):
    """Raised when a stage boundary or the final leakage audit fails closed."""


def reconstruct(
    geojson: Dict[str, object],
    mode: str = "temporal",
    quarantine: Optional[Sequence[str]] = None,
    space_km: float = decluster.DEFAULT_SPACE_KM,
    time_days: float = decluster.DEFAULT_TIME_DAYS,
    cutoff_year: int = role_assignment.TEMPORAL_CUTOFF_YEAR,
) -> ReconstructionResult:
    """Run the full typed reconstruction pipeline on an (already-held) GeoJSON dict.

    ``mode`` selects the role manifest: 'temporal' (primary external holdout) or
    'geographic' (leave-region-out transport check). Returns an immutable
    :class:`ReconstructionResult`; raises :class:`ReconstructionError` if the
    final split-level leakage audit does not pass.
    """
    if mode not in ("temporal", "geographic"):
        raise ReconstructionError(f"unknown reconstruction mode {mode!r}")
    manifests: List[StageManifest] = []

    # Stage 1: ingest + eligibility (post-report ascertainment gate).
    in_digest = common.sha256_text(common.canonical_json(
        sorted(str(f.get("id", "")) for f in geojson.get("features", []))
    ))
    ingest = ingest_eligibility.parse_geojson(geojson, quarantine=quarantine)
    eligible = ingest["rows"]
    manifests.append(StageManifest(
        stage="ingest_eligibility",
        params=common.canonical_json({"min_responses": ingest_eligibility.MIN_RESPONSES,
                                      "quarantine": sorted(quarantine or [])}),
        n_in=int(ingest["stats"]["n_features"]),
        n_out=len(eligible),
        input_digest=in_digest,
        output_digest=_digest_rows(eligible),
        extra=common.canonical_json(ingest["stats"]),
    ))
    if not eligible:
        raise ReconstructionError("no eligible events after the ascertainment gate")

    # Stage 2: endpoint labelling (outcome-defining; caller holds the outcome).
    labelled = endpoint.add_labels(eligible)
    manifests.append(StageManifest(
        stage="endpoint_add_labels",
        params=common.canonical_json({"primary_threshold": endpoint.PRIMARY_THRESHOLD}),
        n_in=len(eligible),
        n_out=len(labelled),
        input_digest=manifests[-1].output_digest,
        output_digest=_digest_rows(labelled),
        extra=common.canonical_json(endpoint.endpoint_report(labelled)),
    ))

    # Stage 3: order-stable declustering into seismic sequences.
    sequenced = decluster.assign_sequences(labelled, space_km=space_km, time_days=time_days)
    seq_stats = decluster.sequence_stats(sequenced, space_km=space_km, time_days=time_days)
    manifests.append(StageManifest(
        stage="decluster_assign_sequences",
        params=common.canonical_json({"space_km": space_km, "time_days": time_days}),
        n_in=len(labelled),
        n_out=len(sequenced),
        input_digest=manifests[-1].output_digest,
        output_digest=_digest_rows(sequenced),
        extra=common.canonical_json(seq_stats),
    ))

    # Stage 4: pre-hashed, outcome-independent role assignment.
    if mode == "temporal":
        roled = role_assignment.assign_temporal_roles(sequenced, cutoff_year=cutoff_year)
    else:
        roled = role_assignment.assign_geographic_roles(sequenced)
    rstats = role_assignment.role_stats(roled)
    manifests.append(StageManifest(
        stage=f"role_assignment_{mode}",
        params=common.canonical_json({
            "mode": mode,
            "cutoff_year": cutoff_year,
            "development_fraction": role_assignment.DEVELOPMENT_FRACTION,
            "geographic_holdout_fraction": role_assignment.GEOGRAPHIC_HOLDOUT_FRACTION,
            "role_salt": role_assignment.ROLE_SALT,
        }),
        n_in=len(sequenced),
        n_out=len(roled),
        input_digest=manifests[-1].output_digest,
        output_digest=_digest_rows(roled),
        extra=common.canonical_json(rstats),
    ))

    # Stage 5: split-level leakage audit (F5 cross-role, F6 temporal), fail-closed.
    audit_rows = [
        {"sequence_id": str(r["sequence_id"]), "role": str(r["role"]),
         "origin_year": str(r["origin_year"])}
        for r in roled
    ]
    split = leakage_audit.audit_role_manifest(audit_rows, temporal_cutoff_year=cutoff_year)
    manifests.append(StageManifest(
        stage="leakage_audit_role_manifest",
        params=common.canonical_json({"cutoff_year": cutoff_year}),
        n_in=len(roled),
        n_out=len(roled),
        input_digest=manifests[-1].output_digest,
        output_digest=_digest_rows(roled),
        extra=common.canonical_json(split),
    ))
    if not split["passed"]:
        raise ReconstructionError(f"split-level leakage audit failed: {split}")

    pipeline_digest = common.sha256_text(common.canonical_json(
        [m.digest() for m in manifests]
    ))
    return ReconstructionResult(
        mode=mode,
        manifests=tuple(manifests),
        n_eligible=len(eligible),
        n_sequences=int(seq_stats["n_sequences"]),
        role_counts=common.canonical_json(rstats["event_counts_by_role"]),
        leakage_passed=bool(split["passed"]),
        pipeline_digest=pipeline_digest,
        rows=tuple(roled),
    )


def verify_order_stability(
    geojson: Dict[str, object],
    mode: str = "temporal",
    quarantine: Optional[Sequence[str]] = None,
) -> bool:
    """Reconstruct twice from feature orders reversed; require identical digests.

    Proves the pipeline (in particular declustering + role assignment) is order
    stable: the reconstruction digest cannot depend on the feature enumeration
    order of the source payload.
    """
    forward = reconstruct(geojson, mode=mode, quarantine=quarantine)
    features = list(geojson.get("features", []))
    reversed_geo = dict(geojson)
    reversed_geo["features"] = list(reversed(features))
    backward = reconstruct(reversed_geo, mode=mode, quarantine=quarantine)
    return forward.pipeline_digest == backward.pipeline_digest


def _cli(argv: List[str]) -> int:
    import argparse

    from common import load_json, write_json

    p = argparse.ArgumentParser(description="Typed DYFI reconstruction pipeline")
    p.add_argument("--geojson", required=True)
    p.add_argument("--mode", choices=["temporal", "geographic"], default="temporal")
    p.add_argument("--quarantine", nargs="*", default=[])
    p.add_argument("--out-manifest", required=True)
    args = p.parse_args(argv)

    gj = load_json(args.geojson)
    res = reconstruct(gj, mode=args.mode, quarantine=args.quarantine)
    write_json(args.out_manifest, res.manifest_record())
    print("pipeline_digest:", res.pipeline_digest)
    print("leakage_passed:", res.leakage_passed)
    return 0 if res.leakage_passed else 1


if __name__ == "__main__":
    import sys

    sys.exit(_cli(sys.argv[1:]))
