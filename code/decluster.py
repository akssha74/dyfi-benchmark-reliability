"""Space-time declustering to build the leakage-hardened grouping unit.

Events within a fixed space-time window of one another are assigned to the SAME
seismic sequence, so mainshock/aftershock near-duplicates (which share epicentral
region and depth) cannot straddle train and evaluation roles.

Grouping rule: single-link SPACE-TIME CONNECTED COMPONENTS via union-find.
Two events are linked iff they are within both the space window (default 100 km,
great-circle) and the time window (default 30 days); a sequence is a connected
component of that undirected link graph. Properties this guarantees, and why the
previous greedy magnitude-anchored rule was replaced:

  * Order-stable / deterministic: connected components are a property of the
    edge set alone, so any input ordering yields identical sequences. The old
    greedy rule sorted by descending magnitude and let the FIRST anchor absorb
    neighbours, so membership depended on processing order and on magnitude ties.
  * Cannot split a connected sequence: if events form a linked chain A-B-C
    (A-B linked, B-C linked) but A and C are not directly within-window, the
    greedy anchor rule could leave C in a different group (it only absorbed
    events within window of the anchor, not transitively). Connected components
    take the transitive closure, so any space-time-connected chain stays whole
    and therefore cannot leak across roles.

The rule reads only source metadata (time, location) and never the label. The
sequence id is the deterministic canonical representative of the component (the
earliest (origin_time, event_id) member), independent of magnitude. The exact
window is registered before role assignment.
"""
from __future__ import annotations

import datetime
import math
import sys
from typing import Dict, List, Sequence, Tuple

DEFAULT_SPACE_KM = 100.0
DEFAULT_TIME_DAYS = 30.0
_EARTH_R_KM = 6371.0088


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * _EARTH_R_KM * math.asin(min(1.0, math.sqrt(a)))


def _epoch_s(iso: str) -> float:
    dt = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc
    )
    return dt.timestamp()


def _find(parent: List[int], x: int) -> int:
    """Union-find root with iterative path compression (deterministic)."""
    root = x
    while parent[root] != root:
        root = parent[root]
    while parent[x] != root:
        parent[x], x = root, parent[x]
    return root


def _union(parent: List[int], rank: List[int], a: int, b: int) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra == rb:
        return
    # Union by rank; ties broken toward the smaller index for full determinism.
    if rank[ra] < rank[rb]:
        ra, rb = rb, ra
    elif rank[ra] == rank[rb]:
        if ra > rb:
            ra, rb = rb, ra
        rank[ra] += 1
    parent[rb] = ra


def assign_sequences(
    rows: Sequence[Dict[str, object]],
    space_km: float = DEFAULT_SPACE_KM,
    time_days: float = DEFAULT_TIME_DAYS,
) -> List[Dict[str, object]]:
    """Assign a deterministic sequence_id to every row.

    Single-link space-time connected components via union-find. Two events are
    linked iff they are within both ``space_km`` (great-circle) and ``time_days``;
    a sequence is a connected component. The result is independent of input order
    and of magnitude, and never splits a space-time-connected chain (see module
    docstring). The sequence id is ``SEQ_<earliest (origin_time, event_id)>``.
    """
    items = [dict(r) for r in rows]
    n = len(items)
    for it in items:
        it["_epoch"] = _epoch_s(str(it["origin_time"]))
        it["_lat"] = float(it["latitude"])
        it["_lon"] = float(it["longitude"])
    parent = list(range(n))
    rank = [0] * n
    time_win_s = time_days * 86400.0
    # Undirected link graph: symmetric predicate, so enumeration order of pairs
    # does not affect the connected components.
    for i in range(n):
        ei = items[i]
        for j in range(i + 1, n):
            ej = items[j]
            if abs(ei["_epoch"] - ej["_epoch"]) > time_win_s:
                continue
            if _haversine_km(ei["_lat"], ei["_lon"], ej["_lat"], ej["_lon"]) <= space_km:
                _union(parent, rank, i, j)
    # Deterministic component representative: earliest (origin_time, event_id).
    rep_key: Dict[int, Tuple[str, str]] = {}
    rep_id: Dict[int, str] = {}
    for i, it in enumerate(items):
        root = _find(parent, i)
        key = (str(it["origin_time"]), str(it["event_id"]))
        if root not in rep_key or key < rep_key[root]:
            rep_key[root] = key
            rep_id[root] = str(it["event_id"])
    out = []
    for i, it in enumerate(items):
        for k in ("_epoch", "_lat", "_lon"):
            it.pop(k, None)
        it["sequence_id"] = f"SEQ_{rep_id[_find(parent, i)]}"
        out.append(it)
    out.sort(key=lambda r: (r["origin_time"], r["event_id"]))
    return out


def sequence_stats(
    rows: Sequence[Dict[str, object]],
    space_km: float = DEFAULT_SPACE_KM,
    time_days: float = DEFAULT_TIME_DAYS,
) -> Dict[str, object]:
    seqs: Dict[str, int] = {}
    for r in rows:
        seqs[r["sequence_id"]] = seqs.get(r["sequence_id"], 0) + 1
    sizes = sorted(seqs.values(), reverse=True)
    return {
        "n_events": len(rows),
        "n_sequences": len(seqs),
        "largest_sequence_size": sizes[0] if sizes else 0,
        "n_singleton_sequences": sum(1 for s in sizes if s == 1),
        "space_km": space_km,
        "time_days": time_days,
        "grouping_rule": "single_link_space_time_connected_components",
    }


def _cli(argv: List[str]) -> int:
    import argparse

    from common import read_csv, write_csv, write_json
    from ingest_eligibility import CANONICAL_COLUMNS

    p = argparse.ArgumentParser(description="Space-time sequence clustering")
    p.add_argument("--in-csv", required=True)
    p.add_argument("--out-csv", required=True)
    p.add_argument("--out-stats", required=True)
    p.add_argument("--space-km", type=float, default=DEFAULT_SPACE_KM)
    p.add_argument("--time-days", type=float, default=DEFAULT_TIME_DAYS)
    args = p.parse_args(argv)

    rows = read_csv(args.in_csv)
    out = assign_sequences(rows, args.space_km, args.time_days)
    cols = list(CANONICAL_COLUMNS) + ["severe_label", "sequence_id"]
    # tolerate missing severe_label (declustering can run pre-labelling)
    cols = [c for c in cols if c in out[0]] if out else cols
    write_csv(args.out_csv, out, cols)
    write_json(args.out_stats, sequence_stats(out, args.space_km, args.time_days))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
