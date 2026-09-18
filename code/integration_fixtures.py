"""Deterministic SYNTHETIC fixtures for the acquisition/reconstruction/runner
integration stage.

Kept separate from ``synthetic_fixtures`` so the completed analytics-stack files
stay byte-stable. Every generator is a pure function of an integer seed. Nothing
here reads real USGS data, fetches anything, opens a protected cohort, or reads a
real outcome.

Fixtures:
  make_source_geojson       -- a pinned-envelope-shaped FeatureCollection with
                               eligible events PLUS deliberate quarantine cases
                               (non-earthquake, out-of-envelope, corrupt geometry,
                               duplicate authoritative revision).
  make_leakage_demo_table   -- an eligible+labelled+sequenced table whose SEQUENCES
                               carry a shared random effect, so a naive random-event
                               split leaks within-sequence signal and inflates
                               apparent skill relative to a sequence-grouped split.
"""
from __future__ import annotations

import datetime
from typing import Dict, List

import numpy as np

import common

MAGNITUDE_TYPES = ("mw", "mb", "ml", "md")


def _epoch_ms(year: int, month: int = 1, day: int = 1, hour: int = 0) -> int:
    dt = datetime.datetime(year, month, day, hour, tzinfo=datetime.timezone.utc)
    return int(dt.timestamp() * 1000)


def make_source_geojson(seed: int = 20260901, n_eligible: int = 120) -> Dict[str, object]:
    """A synthetic FDSN-shaped GeoJSON FeatureCollection.

    Produces ``n_eligible`` clean DYFI events (cdi + felt>=10) inside the pinned
    envelope, plus a fixed set of deliberate quarantine/eligibility cases so the
    acquisition and ingest paths are exercised end to end.
    """
    rng = np.random.default_rng(seed)
    features: List[Dict[str, object]] = []
    for i in range(n_eligible):
        mag = float(np.clip(rng.normal(5.6, 0.5), 5.0, 8.5))
        depth = float(np.clip(rng.gamma(2.0, 6.0), 0.5, 250.0))
        latent = 1.6 * (mag - 5.5) - 0.02 * depth + rng.normal(0.0, 0.8)
        cdi = float(np.clip(5.6 + latent, 1.0, 9.5))
        year = 2015 + int(rng.integers(0, 10))  # 2015..2024 (inside [2015,2025))
        month = int(rng.integers(1, 13))
        day = int(rng.integers(1, 28))
        lat = float(rng.uniform(-60.0, 60.0))
        lon = float(rng.uniform(-170.0, 170.0))
        felt = int(rng.integers(10, 500))
        features.append({
            "id": f"syn{i:05d}",
            "properties": {
                "mag": round(mag, 2), "magType": MAGNITUDE_TYPES[int(rng.integers(0, 4))],
                "cdi": round(cdi, 1), "felt": felt, "type": "earthquake",
                "net": "us", "code": f"syn{i:05d}",
                "time": _epoch_ms(year, month, day), "updated": _epoch_ms(year, month, day, 1),
            },
            "geometry": {"type": "Point", "coordinates": [round(lon, 3), round(lat, 3), round(depth, 1)]},
        })

    # Deliberate cases (stable ids) that must be handled, not silently kept:
    deliberate = [
        # non-earthquake -> Q1
        {"id": "q_blast", "properties": {"mag": 5.2, "magType": "ml", "cdi": 6.1, "felt": 40,
         "type": "quarry blast", "net": "us", "code": "q_blast", "time": _epoch_ms(2019)},
         "geometry": {"type": "Point", "coordinates": [-120.0, 38.0, 5.0]}},
        # below magnitude floor -> Q2 (also below envelope)
        {"id": "q_small", "properties": {"mag": 4.2, "magType": "ml", "cdi": 6.0, "felt": 30,
         "type": "earthquake", "net": "us", "code": "q_small", "time": _epoch_ms(2019)},
         "geometry": {"type": "Point", "coordinates": [-118.0, 34.0, 8.0]}},
        # corrupt geometry (lat out of range) -> Q3
        {"id": "q_badgeo", "properties": {"mag": 5.5, "magType": "mw", "cdi": 6.3, "felt": 60,
         "type": "earthquake", "net": "us", "code": "q_badgeo", "time": _epoch_ms(2020)},
         "geometry": {"type": "Point", "coordinates": [-118.0, 199.0, 8.0]}},
        # below-min felt reports -> eligibility drop (not quarantine)
        {"id": "e_lowfelt", "properties": {"mag": 5.4, "magType": "mw", "cdi": 6.2, "felt": 4,
         "type": "earthquake", "net": "us", "code": "e_lowfelt", "time": _epoch_ms(2020)},
         "geometry": {"type": "Point", "coordinates": [-118.0, 34.0, 8.0]}},
        # missing cdi -> eligibility drop
        {"id": "e_nocdi", "properties": {"mag": 5.4, "magType": "mw", "cdi": None, "felt": 90,
         "type": "earthquake", "net": "us", "code": "e_nocdi", "time": _epoch_ms(2020)},
         "geometry": {"type": "Point", "coordinates": [-118.0, 34.0, 8.0]}},
    ]
    features.extend(deliberate)

    # Duplicate authoritative revision of a clean event -> Q4 on the older one.
    dup_of = features[0]
    dup = {
        "id": "syn00000_v2",
        "properties": {**dict(dup_of["properties"]),
                       "code": "syn00000",  # same authoritative code -> revision
                       "updated": _epoch_ms(2024, 12, 31, 23)},  # newer revision
        "geometry": {"type": "Point", "coordinates": list(dup_of["geometry"]["coordinates"])},
    }
    features.append(dup)

    return {"type": "FeatureCollection",
            "metadata": {"count": len(features), "synthetic": True},
            "features": features}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + float(np.exp(-x)))


def make_leakage_demo_table(
    n_sequences: int = 90,
    events_per_sequence: int = 5,
    seed: int = 20260901,
) -> List[Dict[str, object]]:
    """Eligible+labelled+sequenced table engineered to expose split-scheme leakage.

    Each seismic sequence is a mainshock-aftershock cluster: its member events
    share a tight BASE (magnitude, depth, location), so sequence membership
    coincides with a neighbourhood in source-feature space. The severe outcome is
    driven by a per-sequence propensity ``p_seq`` (a shared random effect, only
    weakly recoverable from base magnitude), and member labels are drawn i.i.d.
    from that shared propensity -- so within-sequence outcomes are correlated.

    Consequence: under a RANDOM-event split a flexible learner can memorise each
    sequence's feature neighbourhood (its train-side siblings) and recover
    ``p_seq``, inflating apparent skill; under a SEQUENCE-grouped split the whole
    neighbourhood is held out and that shortcut vanishes. This is the concrete
    leakage the resource is built to quantify.
    """
    rng = np.random.default_rng(seed)
    rows: List[Dict[str, object]] = []
    ev = 0
    for s in range(n_sequences):
        base_mag = float(np.clip(rng.normal(5.6, 0.6), 5.0, 8.5))
        base_depth = float(np.clip(rng.gamma(2.0, 6.0), 0.5, 250.0))
        base_lat = float(rng.uniform(-55.0, 55.0))
        base_lon = float(rng.uniform(-165.0, 165.0))
        base_year = 2015 + int(rng.integers(0, 10))
        base_day = int(rng.integers(1, 20))
        seq_effect = float(rng.normal(0.0, 1.6))  # shared, mostly unexplained
        p_seq = _sigmoid(0.7 * (base_mag - 5.6) + seq_effect)
        for _j in range(events_per_sequence):
            mag = float(np.clip(base_mag + rng.normal(0.0, 0.05), 5.0, 8.5))
            depth = float(np.clip(base_depth + rng.normal(0.0, 1.0), 0.5, 250.0))
            lat = float(np.clip(base_lat + rng.normal(0.0, 0.08), -89.0, 89.0))
            lon = float(np.clip(base_lon + rng.normal(0.0, 0.08), -179.0, 179.0))
            month = int(rng.integers(1, 13))
            day = min(27, base_day + int(rng.integers(0, 5)))
            severe = 1 if rng.uniform() < p_seq else 0
            # A cdi consistent with the drawn label (severe -> >=6), for the
            # endpoint-threshold sensitivity hooks.
            if severe:
                cdi = float(np.clip(6.0 + rng.gamma(1.5, 0.8), 6.0, 9.5))
            else:
                cdi = float(np.clip(6.0 - rng.gamma(1.5, 0.8), 1.0, 5.999))
            rows.append({
                "event_id": f"LKD{ev:05d}",
                "magnitude": round(mag, 3),
                "magnitude_type": MAGNITUDE_TYPES[int(rng.integers(0, 4))],
                "depth_km": round(depth, 2),
                "latitude": round(lat, 4),
                "longitude": round(lon, 4),
                "origin_time": f"{base_year:04d}-{month:02d}-{day:02d}T00:00:00Z",
                "origin_year": base_year,
                "region_code": common.region_code(lat, lon),
                "num_responses": int(rng.integers(10, 400)),
                "max_cdi": round(cdi, 2),
                "severe_label": int(severe),
                "sequence_id": f"SEQL_{s:03d}",
            })
            ev += 1
    rows.sort(key=lambda r: (r["origin_time"], r["event_id"]))
    return rows


FIXTURE_NAMES = ("make_source_geojson", "make_leakage_demo_table")
