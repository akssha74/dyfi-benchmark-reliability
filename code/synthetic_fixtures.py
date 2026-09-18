"""Deterministic SYNTHETIC fixtures for the analytics-stack tests and smoke run.

Nothing here reads real USGS data. Every generator is a pure function of an
integer seed, so fixtures are reproducible and the reproducibility test can build
the same corpus twice. The fixtures deliberately exercise each load-bearing
metric/baseline path:

  normal         -- two-class corpus with genuine magnitude signal, many sequences
  constant       -- a constant prediction vector against a varying label
  tied           -- many tied probabilities (AUROC average-rank tie handling)
  one_class      -- a single-class label vector
  missing_class  -- a corpus so positive-sparse that some bootstrap resamples miss
                    a class (drives the minimum-valid-replicate rule)
  leakage        -- rows carrying forbidden columns + an axis-leaking schema use
  sequence_group -- events clustered into sequences for the cluster bootstrap
  reproducibility -- identical corpus from a fixed seed for double-run equality
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

import common

MAGNITUDE_TYPES = ("mw", "mb", "ml", "md")


def _iso(year: int, month: int, day: int) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}T00:00:00Z"


def make_event_table(
    n_events: int = 240,
    n_sequences: int = 60,
    seed: int = 20260901,
) -> List[Dict[str, object]]:
    """Build a synthetic eligible+labelled+sequenced event table.

    ``max_cdi`` is generated from magnitude and depth with noise so a learned
    baseline has real (but imperfect) signal; ``severe_label = 1[max_cdi >= 6]``.
    Events are packed into ``n_sequences`` clusters (the cluster-bootstrap unit),
    span multiple years (temporal slice) and region cells (geographic slice).
    """
    rng = np.random.default_rng(seed)
    rows: List[Dict[str, object]] = []
    for i in range(n_events):
        seq_idx = i % n_sequences
        magnitude = float(np.clip(rng.normal(5.0, 0.9), 2.5, 8.5))
        depth = float(np.clip(rng.gamma(2.0, 6.0), 0.5, 250.0))
        # Latent severity increases with magnitude, decreases with depth.
        latent = 1.6 * (magnitude - 5.0) - 0.02 * depth + rng.normal(0.0, 0.8)
        max_cdi = float(np.clip(5.9 + latent, 1.0, 9.5))
        year = 2015 + int(rng.integers(0, 11))  # 2015..2025
        month = int(rng.integers(1, 13))
        day = int(rng.integers(1, 28))
        lat = float(rng.uniform(-60.0, 60.0))
        lon = float(rng.uniform(-170.0, 170.0))
        rows.append(
            {
                "event_id": f"SYN{i:05d}",
                "magnitude": magnitude,
                "magnitude_type": MAGNITUDE_TYPES[int(rng.integers(0, len(MAGNITUDE_TYPES)))],
                "depth_km": depth,
                "latitude": lat,
                "longitude": lon,
                "origin_time": _iso(year, month, day),
                "origin_year": year,
                "region_code": common.region_code(lat, lon),
                "num_responses": int(rng.integers(10, 400)),
                "max_cdi": round(max_cdi, 2),
                "severe_label": 1 if max_cdi >= 6.0 else 0,
                "sequence_id": f"SEQ_{seq_idx:03d}",
            }
        )
    rows.sort(key=lambda r: (r["origin_time"], r["event_id"]))
    return rows


def groups_of(rows: List[Dict[str, object]]) -> List[str]:
    return [str(r["sequence_id"]) for r in rows]


def labels_of(rows: List[Dict[str, object]]) -> np.ndarray:
    return np.asarray([int(r["severe_label"]) for r in rows], dtype=np.float64)


# ---------------------------------------------------------------------------
# Small (y, p) fixtures for pure metric paths
# ---------------------------------------------------------------------------
def normal_yp(seed: int = 7, n: int = 200) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    y = (rng.uniform(size=n) < 0.4).astype(np.float64)
    p = np.clip(0.15 + 0.6 * y + rng.normal(0.0, 0.18, size=n), 0.001, 0.999)
    return y, p


def constant_prediction_yp(n: int = 100) -> Tuple[np.ndarray, np.ndarray]:
    y = np.array([0.0, 1.0] * (n // 2), dtype=np.float64)
    p = np.full(n, 0.33, dtype=np.float64)
    return y, p


def tied_yp() -> Tuple[np.ndarray, np.ndarray]:
    # Half positives, half negatives, ALL with the identical probability 0.5:
    # a correct AUROC with average-rank ties is exactly 0.5.
    y = np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=np.float64)
    p = np.full(8, 0.5, dtype=np.float64)
    return y, p


def one_class_yp(n: int = 50) -> Tuple[np.ndarray, np.ndarray]:
    y = np.ones(n, dtype=np.float64)
    p = np.linspace(0.1, 0.9, n)
    return y, p


def missing_class_corpus(seed: int = 11) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """A positive-sparse clustered corpus: only one cluster carries positives, so
    many cluster resamples contain no positive and the AUROC bootstrap must fall
    back to its minimum-valid-replicate rule."""
    y = np.zeros(30, dtype=np.float64)
    y[:2] = 1.0  # only 2 positives, both in cluster 'C0'
    p = np.linspace(0.05, 0.95, 30)
    groups = ["C0", "C0"] + [f"C{i}" for i in range(1, 29)]
    return y, p, groups


def leakage_fixture() -> Dict[str, object]:
    """Rows carrying forbidden columns and field-name variants for the audit."""
    return {
        "forbidden_feature_names": [
            "magnitude", "depth_km", "max_cdi", "num_responses", "felt",
            "event_id", "shakemap_mmi", "severe_label", "CDI", "Num_Responses",
        ],
        "temporal_axis_leaks": ["magnitude", "origin_year"],
        "geographic_axis_leaks": ["magnitude", "latitude", "longitude", "region_code"],
        "clean_source_only": ["magnitude", "depth_km"],
    }


FIXTURE_NAMES = (
    "normal",
    "constant",
    "tied",
    "one_class",
    "missing_class",
    "leakage",
    "sequence_group",
    "reproducibility",
)
