"""Endpoint construction for the DYFI severe-felt-intensity benchmark.

Primary endpoint: severe_label = 1 if event maximum CDI >= 6.0 else 0.
Reported sensitivity variants: cdi >= 5.5 and cdi >= 6.5 (single-outlier
sensitivity of the event maximum), plus near-threshold event counts. An
aggregation-grid sensitivity variant is documented in the schema; it requires
the alternate cdi_geo grid payload and is reported at construction time.

Outcome-boundary disclosure: this module CONSTRUCTS the label from the outcome
field (max_cdi); running it is a label-defining, outcome-bearing operation, not
an outcome-blind step. The endpoint threshold and its sensitivity band are fixed
here (data-informed at most by previously-disclosed aggregate prevalence) and
must be frozen before any protected evaluation. This is a retrospective,
USGS-only resource; no operational/real-time claim is implied.
"""
from __future__ import annotations

import sys
from typing import Dict, List, Sequence

PRIMARY_THRESHOLD = 6.0
SENSITIVITY_THRESHOLDS = (5.5, 6.0, 6.5)
NEAR_THRESHOLD_BAND = 0.5


def add_labels(rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    out = []
    for r in rows:
        r = dict(r)
        cdi = float(r["max_cdi"])
        r["severe_label"] = 1 if cdi >= PRIMARY_THRESHOLD else 0
        out.append(r)
    return out


def endpoint_report(rows: Sequence[Dict[str, object]]) -> Dict[str, object]:
    n = len(rows)
    cdis = [float(r["max_cdi"]) for r in rows]
    report: Dict[str, object] = {"n_events": n, "thresholds": {}}
    for t in SENSITIVITY_THRESHOLDS:
        pos = sum(1 for c in cdis if c >= t)
        report["thresholds"][str(t)] = {
            "positives": pos,
            "prevalence": (pos / n) if n else None,
        }
    near = sum(1 for c in cdis if abs(c - PRIMARY_THRESHOLD) < NEAR_THRESHOLD_BAND)
    report["primary_threshold"] = PRIMARY_THRESHOLD
    report["near_threshold_events"] = near
    report["near_threshold_band"] = NEAR_THRESHOLD_BAND
    report["note"] = (
        "Event maximum CDI can flip across the severe threshold on a single "
        "outlier report; threshold-sensitivity and near-threshold counts are "
        "reported so the endpoint is not read as grid/aggregation artefact."
    )
    return report


def _cli(argv: List[str]) -> int:
    import argparse

    from common import read_csv, write_csv, write_json
    from ingest_eligibility import CANONICAL_COLUMNS

    p = argparse.ArgumentParser(description="Endpoint labels + sensitivity")
    p.add_argument("--in-csv", required=True)
    p.add_argument("--out-csv", required=True)
    p.add_argument("--out-report", required=True)
    args = p.parse_args(argv)

    rows = read_csv(args.in_csv)
    labelled = add_labels(rows)
    cols = list(CANONICAL_COLUMNS) + ["severe_label"]
    write_csv(args.out_csv, labelled, cols)
    write_json(args.out_report, endpoint_report(labelled))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
