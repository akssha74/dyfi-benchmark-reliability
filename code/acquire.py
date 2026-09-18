"""Pinned USGS DYFI acquisition + provenance for the single-source
severe-felt-intensity benchmark.

This module PINS the FDSN/ComCat query envelope (M>=5, producttype=dyfi,
2015-01-01 .. 2025-01-01), builds the exact query and count URLs, and records the
provenance a hash-locked snapshot requires: access instant, request URL, raw-byte
SHA-256, catalogue-version drift receipt, retry/rate-limit policy, the
exact-full-response (atomic snapshot) requirement, duplicate/revision
reconciliation, and quarantine ids.

Two disjoint capabilities, by design:

  * a ``--count-only`` PREFLIGHT that hits the FDSN ``/count`` endpoint. It
    returns an INTEGER only -- no event geometry, no cdi, no felt -- so it may be
    run without ever seeing a label. This stage does NOT execute it live; it
    records the already-observed live counts as provenance.

  * an OUTCOME-BEARING fetch of the ``/query`` GeoJSON (which carries cdi/felt).
    It is DISABLED here and fails closed unless an explicit activation token is
    supplied. Nothing in this stage passes one, so no real event-level GeoJSON is
    fetched, no outcome is read, and no protected cohort is opened.

Recorded provenance evidence (NOT an error): a live count preflight returned
7,575 events in the initial packet and 7,576 on an immediate recheck. That +1 is
ordinary catalogue-version drift (a revision entered the window between the two
counts); it is exactly why the outcome-bearing snapshot must be pinned to a
single access instant and hash-locked, and why the runner refuses to mix a count
taken at one instant with a payload fetched at another.
"""
from __future__ import annotations

import dataclasses
import datetime
import sys
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlencode

import common
import prehash_rules

FDSN_BASE = "https://earthquake.usgs.gov/fdsnws/event/1"
CATALOG = "USGS_ComCat_FDSNWS_event_v1"


class AcquisitionDisabledError(RuntimeError):
    """Raised when an outcome-bearing fetch is attempted without activation."""


class SnapshotIntegrityError(RuntimeError):
    """Raised when a fetched snapshot fails the exact-full-response contract."""


# ---------------------------------------------------------------------------
# Recorded live-count provenance (drift evidence, NOT an error).
# ---------------------------------------------------------------------------
OBSERVED_LIVE_COUNTS: Tuple[Dict[str, object], ...] = (
    {"label": "initial_packet", "count": 7575,
     "note": "first live /count preflight against the pinned envelope"},
    {"label": "immediate_recheck", "count": 7576,
     "note": "second live /count within the same session; +1 catalogue drift"},
)


@dataclasses.dataclass(frozen=True)
class RetryPolicy:
    """Deterministic, bounded retry/rate-limit contract for any live request."""

    max_attempts: int = 5
    backoff_base_s: float = 2.0
    backoff_cap_s: float = 60.0
    per_request_timeout_s: float = 120.0
    min_interval_between_requests_s: float = 1.0
    retry_on_status: Tuple[int, ...] = (429, 500, 502, 503, 504)

    def backoff_for_attempt(self, attempt: int) -> float:
        """Exponential backoff (capped); deterministic, no jitter for auditability."""
        if attempt < 1:
            raise ValueError("attempt is 1-based")
        return min(self.backoff_cap_s, self.backoff_base_s ** attempt)


DEFAULT_RETRY_POLICY = RetryPolicy()

# FDSN returns at most this many events per request; a full envelope larger than
# this MUST be paged deterministically and the pages recombined, with the total
# checked against the count preflight (exact-full-response requirement).
FDSN_MAX_EVENTS_PER_REQUEST = 20000


def _iso_now(clock: Optional[datetime.datetime] = None) -> str:
    dt = clock or datetime.datetime.now(datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _envelope_query_params(envelope: Optional[Dict[str, object]] = None) -> List[Tuple[str, str]]:
    env = dict(envelope or prehash_rules.ACQUISITION_ENVELOPE)
    # Stable, sorted parameter order so the URL (and its hash) is deterministic.
    params: List[Tuple[str, str]] = [
        ("starttime", str(env["starttime"])),
        ("endtime", str(env["endtime"])),
        ("minmagnitude", str(env["minmagnitude"])),
        ("producttype", str(env["producttype"])),
        ("eventtype", str(env.get("eventtype", "earthquake"))),
        ("orderby", str(env.get("orderby", "time-asc"))),
    ]
    return params


def build_count_url(envelope: Optional[Dict[str, object]] = None) -> str:
    """FDSN /count URL. Returns an integer only -- no labels -- so it is the
    outcome-free preflight surface."""
    params = _envelope_query_params(envelope) + [("format", "text")]
    return f"{FDSN_BASE}/count?{urlencode(params)}"


def build_query_url(envelope: Optional[Dict[str, object]] = None,
                    fmt: str = "geojson") -> str:
    """FDSN /query URL. This response carries cdi/felt (the OUTCOME); building the
    URL is harmless, but EXECUTING it is gated behind activation (see fetch)."""
    params = _envelope_query_params(envelope) + [("format", fmt)]
    return f"{FDSN_BASE}/query?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Catalogue-version drift receipt
# ---------------------------------------------------------------------------
def drift_receipt(
    counts: Sequence[Dict[str, object]] = OBSERVED_LIVE_COUNTS,
) -> Dict[str, object]:
    """Summarise catalogue-version drift across >=2 count observations.

    A non-zero spread is recorded as ordinary catalogue evolution (provenance),
    NOT a failure: it documents why a single pinned access instant + raw-byte
    hash is mandatory before any outcome-bearing parse.
    """
    values = [int(c["count"]) for c in counts]
    lo, hi = min(values), max(values)
    return {
        "observations": [dict(c) for c in counts],
        "n_observations": len(values),
        "count_min": lo,
        "count_max": hi,
        "count_drift": hi - lo,
        "drift_is_error": False,
        "interpretation": (
            "Catalogue-version drift: the DYFI/ComCat window count changed by "
            f"{hi - lo} between observations (e.g. 7575 -> 7576). This is expected "
            "catalogue evolution (a revision entering the window), which is why "
            "the outcome-bearing snapshot must be pinned to one access instant and "
            "hash-locked; a count from one instant must never be paired with a "
            "payload fetched at another."
        ),
        "requires_pinned_snapshot": True,
    }


# ---------------------------------------------------------------------------
# Count-only preflight (may run without labels)
# ---------------------------------------------------------------------------
def count_only_preflight(
    envelope: Optional[Dict[str, object]] = None,
    execute: bool = False,
    allow_network: bool = False,
) -> Dict[str, object]:
    """Outcome-free preflight against the FDSN /count endpoint.

    With ``execute=False`` (the default and the only path used in this stage) it
    returns the pinned envelope, the count URL, the retry policy, and the recorded
    live-count provenance + drift receipt WITHOUT any network access. A live
    execution path exists (``execute and allow_network``) but is intentionally not
    invoked here; even when invoked it only ever reads an integer count, never a
    label.
    """
    env = dict(envelope or prehash_rules.ACQUISITION_ENVELOPE)
    url = build_count_url(env)
    report: Dict[str, object] = {
        "mode": "count_only_preflight",
        "outcome_free": True,
        "may_run_without_labels": True,
        "catalog": CATALOG,
        "envelope": env,
        "count_url": url,
        "retry_policy": dataclasses.asdict(DEFAULT_RETRY_POLICY),
        "recorded_live_counts": [dict(c) for c in OBSERVED_LIVE_COUNTS],
        "drift_receipt": drift_receipt(),
        "executed_live": False,
    }
    if execute:
        if not allow_network:
            raise AcquisitionDisabledError(
                "live count preflight requires allow_network=True; refusing to "
                "touch the network implicitly"
            )
        live = _live_count(url, DEFAULT_RETRY_POLICY)  # pragma: no cover
        report["executed_live"] = True
        report["live_count"] = live
        report["access_instant"] = _iso_now()
    return report


def _live_count(url: str, policy: RetryPolicy) -> int:  # pragma: no cover
    """Execute a single /count request with bounded retries. Never called in this
    stage; provided so activation can reuse the audited policy."""
    import time
    import urllib.request

    last_exc: Optional[Exception] = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=policy.per_request_timeout_s) as resp:
                if resp.status in policy.retry_on_status:
                    raise SnapshotIntegrityError(f"retryable status {resp.status}")
                return int(resp.read().decode("utf-8").strip())
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= policy.max_attempts:
                break
            time.sleep(policy.backoff_for_attempt(attempt))
    raise SnapshotIntegrityError(f"count preflight failed after retries: {last_exc!r}")


# ---------------------------------------------------------------------------
# Outcome-bearing fetch (DISABLED until activation)
# ---------------------------------------------------------------------------
def fetch_outcome_bearing_geojson(
    envelope: Optional[Dict[str, object]] = None,
    activation_token: Optional[str] = None,
    allow_network: bool = False,
) -> Dict[str, object]:
    """Fetch the /query GeoJSON that carries cdi/felt. DISABLED here.

    Fails closed unless BOTH a non-empty activation token AND allow_network are
    supplied. This stage never supplies an activation token, so this function
    always raises: no real event-level GeoJSON with CDI/felt fields is fetched.
    """
    if not activation_token or not allow_network:
        raise AcquisitionDisabledError(
            "outcome-bearing DYFI fetch is disabled: it requires an explicit "
            "activation token and allow_network=True, plus an authorised contract "
            "lock. None are present in this stage, so the protected outcome is "
            "never read here."
        )
    # Activation path (wired only under an explicit token + network + authorised
    # lock, per independent_lock_review.json authorized_actions). Executes ONE
    # dated pull of the pinned outcome-bearing query URL with the audited retry
    # policy, records the access instant, the raw bytes, and their SHA-256, and
    # returns them for hash-locking. The envelope (<=~7.5k events) is well under
    # FDSN_MAX_EVENTS_PER_REQUEST, so a single request returns the full response;
    # a larger envelope would page deterministically and recombine.
    import json as _json
    import time as _time
    import urllib.request as _urllib

    env = dict(envelope or prehash_rules.ACQUISITION_ENVELOPE)
    policy = DEFAULT_RETRY_POLICY
    url = build_query_url(env, fmt="geojson")
    access_instant = _iso_now()
    last_exc: Optional[Exception] = None
    raw: Optional[bytes] = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            with _urllib.urlopen(url, timeout=policy.per_request_timeout_s) as resp:
                status = getattr(resp, "status", 200)
                if status in policy.retry_on_status:
                    raise SnapshotIntegrityError(f"retryable status {status}")
                raw = resp.read()
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= policy.max_attempts:
                raise SnapshotIntegrityError(
                    f"outcome-bearing fetch failed after retries: {last_exc!r}"
                )
            _time.sleep(policy.backoff_for_attempt(attempt))
    if raw is None:  # pragma: no cover - defensive
        raise SnapshotIntegrityError("no payload retrieved")
    parsed = _json.loads(raw.decode("utf-8"))
    features = parsed.get("features", [])
    return {
        "access_instant": access_instant,
        "query_url": url,
        "raw_bytes": raw,
        "payload_bytes": len(raw),
        "source_payload_sha256": common.sha256_bytes(raw),
        "n_features": len(features),
        "geojson": parsed,
        "catalog": CATALOG,
        "activation_token_fingerprint": common.sha256_text(activation_token)[:16],
    }


# ---------------------------------------------------------------------------
# Exact-full-response (atomic snapshot) contract
# ---------------------------------------------------------------------------
def verify_exact_full_response(
    n_features_in_payload: int,
    preflight_count: int,
    tolerate_drift: int = 0,
) -> Dict[str, object]:
    """Assert the fetched payload contains EVERY event the count promised.

    A partial/paged response that does not recombine to the preflight count is a
    hard failure (fail-closed), except for an explicitly tolerated catalogue-drift
    slack. Returns a receipt; raises SnapshotIntegrityError on a real shortfall.
    """
    delta = n_features_in_payload - preflight_count
    ok = abs(delta) <= max(0, tolerate_drift)
    receipt = {
        "payload_features": n_features_in_payload,
        "preflight_count": preflight_count,
        "delta": delta,
        "tolerated_drift": tolerate_drift,
        "exact_full_response": ok,
        "max_events_per_request": FDSN_MAX_EVENTS_PER_REQUEST,
        "paging_required": preflight_count > FDSN_MAX_EVENTS_PER_REQUEST,
    }
    if not ok:
        raise SnapshotIntegrityError(
            f"exact-full-response violated: payload has {n_features_in_payload} "
            f"features but preflight promised {preflight_count} (delta {delta}, "
            f"tolerated {tolerate_drift})"
        )
    return receipt


# ---------------------------------------------------------------------------
# Duplicate / revision reconciliation + quarantine
# ---------------------------------------------------------------------------
def _authoritative_key(feature: Dict[str, object]) -> str:
    props = feature.get("properties", {}) or {}
    net = str(props.get("net", "") or props.get("sourcecode", "")).strip().lower()
    ident = str(props.get("code", feature.get("id", ""))).strip().lower()
    return f"{net}:{ident}" if net else str(feature.get("id", ""))


def reconcile_revisions(features: Sequence[Dict[str, object]]) -> Dict[str, object]:
    """Deduplicate revisions of the same authoritative origin.

    Groups by authoritative (net, code) key; keeps the revision with the greatest
    ``updated`` timestamp (falling back to ``time`` then id order); quarantines the
    superseded revisions under Q4. Deterministic and outcome-independent (reads
    only provenance fields, never cdi/felt). Returns kept features + receipts.
    """
    groups: Dict[str, List[Dict[str, object]]] = {}
    order: List[str] = []
    for f in features:
        k = _authoritative_key(f)
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(f)

    kept: List[Dict[str, object]] = []
    superseded_ids: List[str] = []
    revision_receipts: List[Dict[str, object]] = []
    for k in order:
        members = groups[k]
        if len(members) == 1:
            kept.append(members[0])
            continue

        def _rev_key(f: Dict[str, object]):
            props = f.get("properties", {}) or {}
            updated = props.get("updated", None)
            time_ = props.get("time", None)
            upd = int(updated) if isinstance(updated, (int, float)) else -1
            tim = int(time_) if isinstance(time_, (int, float)) else -1
            return (upd, tim, str(f.get("id", "")))

        members_sorted = sorted(members, key=_rev_key, reverse=True)
        winner = members_sorted[0]
        losers = members_sorted[1:]
        kept.append(winner)
        for lo in losers:
            superseded_ids.append(str(lo.get("id", "")))
        revision_receipts.append(
            {
                "authoritative_key": k,
                "kept_id": str(winner.get("id", "")),
                "superseded_ids": [str(lo.get("id", "")) for lo in losers],
                "quarantine_rule": "Q4_duplicate_authoritative_origin",
            }
        )
    return {
        "kept_features": kept,
        "superseded_quarantine_ids": superseded_ids,
        "revision_receipts": revision_receipts,
        "n_input": len(features),
        "n_kept": len(kept),
        "n_superseded": len(superseded_ids),
    }


def quarantine_ids_for_features(features: Sequence[Dict[str, object]]) -> Dict[str, object]:
    """Apply the pre-hashed, outcome-independent quarantine rules to raw features.

    Reads only source metadata via ``prehash_rules.quarantine_reason``; returns the
    quarantined ids grouped by rule and the clean id list. Never reads a label.
    """
    by_rule: Dict[str, List[str]] = {}
    clean: List[str] = []
    for f in features:
        props = f.get("properties", {}) or {}
        geom = f.get("geometry", {}) or {}
        coords = geom.get("coordinates", [None, None, None]) or [None, None, None]
        t = props.get("time", None)
        year = None
        if isinstance(t, (int, float)):
            year = datetime.datetime.fromtimestamp(
                t / 1000.0, tz=datetime.timezone.utc
            ).year
        event = {
            "event_id": f.get("id", ""),
            "eventtype": props.get("type", "earthquake"),
            "magnitude": props.get("mag", None),
            "origin_year": year,
            "longitude": coords[0] if len(coords) > 0 else None,
            "latitude": coords[1] if len(coords) > 1 else None,
            "depth_km": coords[2] if len(coords) > 2 else None,
        }
        reason = prehash_rules.quarantine_reason(event)
        if reason:
            by_rule.setdefault(reason, []).append(str(f.get("id", "")))
        else:
            clean.append(str(f.get("id", "")))
    return {
        "quarantined_by_rule": by_rule,
        "n_quarantined": sum(len(v) for v in by_rule.values()),
        "clean_ids": clean,
        "n_clean": len(clean),
    }


# ---------------------------------------------------------------------------
# Source locator manifest (the pinned-snapshot provenance the runner verifies)
# ---------------------------------------------------------------------------
def source_locator_manifest(
    raw_bytes: Optional[bytes] = None,
    access_instant: Optional[str] = None,
    preflight_count: Optional[int] = None,
    envelope: Optional[Dict[str, object]] = None,
    status: str = "PENDING_ACTIVATION",
) -> Dict[str, object]:
    """Build the source-locator manifest.

    When ``raw_bytes`` is None (this stage), the manifest is a PENDING template
    that pins the query URLs, envelope, retry policy, and drift receipt but
    carries NO payload hash (nothing has been fetched). At activation, the same
    function stamps the raw-byte SHA-256, access instant, and exact-full-response
    receipt for the hash lock.
    """
    env = dict(envelope or prehash_rules.ACQUISITION_ENVELOPE)
    manifest: Dict[str, object] = {
        "record_type": "source_locator_manifest",
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "catalog": CATALOG,
        "status": status,
        "envelope": env,
        "query_url_outcome_bearing": build_query_url(env),
        "count_url_outcome_free": build_count_url(env),
        "retry_policy": dataclasses.asdict(DEFAULT_RETRY_POLICY),
        "exact_full_response_required": True,
        "duplicate_revision_policy": "keep latest authoritative revision; quarantine superseded (Q4)",
        "quarantine_rule_ids": [rid for rid, _ in prehash_rules.QUARANTINE_RULES],
        "drift_receipt": drift_receipt(),
        "prehash_combined_digest": prehash_rules.compute_lock().combined_digest,
    }
    if raw_bytes is None:
        manifest["access_instant"] = None
        manifest["source_payload_sha256"] = None
        manifest["payload_bytes"] = None
        manifest["outcome_fetched"] = False
        return manifest

    # Activation path (not used in this stage): stamp the payload hash lock.
    manifest["access_instant"] = access_instant or _iso_now()
    manifest["source_payload_sha256"] = common.sha256_bytes(raw_bytes)
    manifest["payload_bytes"] = len(raw_bytes)
    manifest["outcome_fetched"] = True
    if preflight_count is not None:
        import json as _json

        try:
            n_features = len(_json.loads(raw_bytes.decode("utf-8")).get("features", []))
        except Exception:  # noqa: BLE001
            n_features = -1
        manifest["exact_full_response_receipt"] = verify_exact_full_response(
            n_features, preflight_count
        )
    return manifest


def _cli(argv: List[str]) -> int:
    import argparse

    from common import write_json

    p = argparse.ArgumentParser(description="Pinned DYFI acquisition provenance")
    p.add_argument("--count-only", action="store_true",
                   help="outcome-free /count preflight (records provenance, no fetch)")
    p.add_argument("--manifest", action="store_true",
                   help="emit the PENDING source-locator manifest template")
    p.add_argument("--out", help="write the selected JSON here")
    args = p.parse_args(argv)

    if args.count_only:
        rec = count_only_preflight(execute=False)
    elif args.manifest:
        rec = source_locator_manifest()
    else:
        rec = {
            "count_url": build_count_url(),
            "query_url": build_query_url(),
            "drift_receipt": drift_receipt(),
            "outcome_bearing_fetch": "DISABLED (no activation token)",
        }
    if args.out:
        write_json(args.out, rec)
    print(common.canonical_json(rec)[:400])
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
