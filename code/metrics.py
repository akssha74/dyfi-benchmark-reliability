"""Deterministic evaluation metrics + cluster-bootstrap uncertainty for the
DYFI-USGS single-source severe-felt-intensity benchmark.

Everything here operates on already-computed probabilities and binary labels on
SYNTHETIC or construction data; nothing in this module opens a protected role,
fits a model, or reads real USGS outcomes. It is the metric/uncertainty half of
the analytics stack (construction step 8).

Design contract:
  * Brier score is the PRIMARY metric; log-loss and AUROC accompany it.
  * Every metric that is undefined on degenerate input returns an explicit
    INFEASIBLE status (never a silent NaN or a fabricated number). The two
    load-bearing degeneracies are a CONSTANT prediction vector and a ONE-CLASS
    label vector; both are surfaced by name.
  * AUROC uses average-rank (Mann-Whitney) tie handling, so tied scores give a
    single deterministic value independent of input order.
  * Uncertainty is a GROUP/SEQUENCE-CLUSTER bootstrap (resamples clusters, not
    rows) with >= 2000 draws and a minimum-valid-replicate rule.
  * Ranking between two baselines is a paired cluster bootstrap with an explicit
    tie probability against a stated resolution floor.
  * Deterministic: fixed seeds, no global RNG, float64 throughout; two clean
    reruns reproduce every number exactly.
"""
from __future__ import annotations

import dataclasses
import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import rankdata

# ---------------------------------------------------------------------------
# Status sentinels
# ---------------------------------------------------------------------------
OK = "OK"
INFEASIBLE_ONE_CLASS = "INFEASIBLE_ONE_CLASS"
INFEASIBLE_CONSTANT_PREDICTION = "INFEASIBLE_CONSTANT_PREDICTION"
INFEASIBLE_EMPTY = "INFEASIBLE_EMPTY"
INFEASIBLE_INSUFFICIENT_VALID_REPLICATES = "INFEASIBLE_INSUFFICIENT_VALID_REPLICATES"

_PROB_EPS = 1e-15
_LOGIT_CLIP = 1e-12


@dataclasses.dataclass(frozen=True)
class MetricValue:
    """A single scalar metric outcome carrying an explicit feasibility status."""

    status: str
    value: Optional[float] = None
    reason: str = ""

    def as_dict(self) -> Dict[str, object]:
        return {"status": self.status, "value": self.value, "reason": self.reason}


# ---------------------------------------------------------------------------
# Input hygiene
# ---------------------------------------------------------------------------
def _as_arrays(y, p) -> Tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y, dtype=np.float64).ravel()
    p = np.asarray(p, dtype=np.float64).ravel()
    if y.shape != p.shape:
        raise ValueError(f"y and p length mismatch: {y.shape} vs {p.shape}")
    if y.size and not np.all((y == 0.0) | (y == 1.0)):
        raise ValueError("y must be binary {0,1}")
    if p.size and (np.any(p < 0.0) or np.any(p > 1.0) or not np.all(np.isfinite(p))):
        raise ValueError("p must be finite probabilities in [0,1]")
    return y, p


def _one_class(y: np.ndarray) -> bool:
    return np.unique(y).size < 2


def _constant(p: np.ndarray) -> bool:
    return np.unique(p).size < 2


# ---------------------------------------------------------------------------
# Proper scores
# ---------------------------------------------------------------------------
def brier_score(y, p) -> MetricValue:
    """Mean squared error of probabilities against the binary label (PRIMARY)."""
    y, p = _as_arrays(y, p)
    if y.size == 0:
        return MetricValue(INFEASIBLE_EMPTY, None, "no observations")
    return MetricValue(OK, float(np.mean((p - y) ** 2)))


def log_loss(y, p) -> MetricValue:
    """Binary cross-entropy with symmetric clipping (well-defined at 0/1)."""
    y, p = _as_arrays(y, p)
    if y.size == 0:
        return MetricValue(INFEASIBLE_EMPTY, None, "no observations")
    pc = np.clip(p, _PROB_EPS, 1.0 - _PROB_EPS)
    ll = -np.mean(y * np.log(pc) + (1.0 - y) * np.log(1.0 - pc))
    return MetricValue(OK, float(ll))


def auroc(y, p) -> MetricValue:
    """Area under the ROC curve via the Mann-Whitney U statistic.

    Ties in ``p`` are handled by average ranks, so the value is deterministic and
    order-independent. Returns INFEASIBLE_ONE_CLASS when only one label is
    present (AUROC is undefined without both a positive and a negative).
    """
    y, p = _as_arrays(y, p)
    if y.size == 0:
        return MetricValue(INFEASIBLE_EMPTY, None, "no observations")
    if _one_class(y):
        return MetricValue(INFEASIBLE_ONE_CLASS, None, "AUROC needs both classes")
    ranks = rankdata(p, method="average")
    n_pos = float(np.sum(y == 1.0))
    n_neg = float(np.sum(y == 0.0))
    sum_pos_ranks = float(np.sum(ranks[y == 1.0]))
    auc = (sum_pos_ranks - n_pos * (n_pos + 1.0) / 2.0) / (n_pos * n_neg)
    return MetricValue(OK, float(auc))


# ---------------------------------------------------------------------------
# Calibration (intercept / slope)
# ---------------------------------------------------------------------------
def _logit(p: np.ndarray) -> np.ndarray:
    pc = np.clip(p, _LOGIT_CLIP, 1.0 - _LOGIT_CLIP)
    return np.log(pc / (1.0 - pc))


def calibration_intercept_slope(
    y,
    p,
    max_iter: int = 100,
    tol: float = 1e-10,
) -> Dict[str, object]:
    """Calibration intercept (a) and slope (b) from logistic recalibration.

    Fits ``y ~ sigmoid(a + b * logit(p))`` by Newton-Raphson IRLS. Perfect
    calibration is (a, b) = (0, 1). Explicit INFEASIBLE states:
      * ONE_CLASS  -> the label has a single class (no calibration target);
      * CONSTANT_PREDICTION -> ``p`` has no spread, so the slope is unidentified.
    """
    y, p = _as_arrays(y, p)
    if y.size == 0:
        return {"status": INFEASIBLE_EMPTY, "intercept": None, "slope": None,
                "reason": "no observations", "n_iter": 0, "converged": False}
    if _one_class(y):
        return {"status": INFEASIBLE_ONE_CLASS, "intercept": None, "slope": None,
                "reason": "single-class label; calibration slope unidentified",
                "n_iter": 0, "converged": False}
    if _constant(p):
        return {"status": INFEASIBLE_CONSTANT_PREDICTION, "intercept": None,
                "slope": None,
                "reason": "constant prediction; logit design column has no rank",
                "n_iter": 0, "converged": False}

    z = _logit(p)
    X = np.column_stack([np.ones_like(z), z])  # [intercept, slope]
    beta = np.zeros(2, dtype=np.float64)
    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        eta = X @ beta
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(mu * (1.0 - mu), 1e-12, None)
        grad = X.T @ (y - mu)
        XtW = X.T * w
        hess = XtW @ X
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            return {"status": INFEASIBLE_CONSTANT_PREDICTION, "intercept": None,
                    "slope": None, "reason": "singular Hessian (degenerate design)",
                    "n_iter": it, "converged": False}
        beta = beta + step
        if not np.all(np.isfinite(beta)):
            return {"status": INFEASIBLE_CONSTANT_PREDICTION, "intercept": None,
                    "slope": None, "reason": "non-finite IRLS step (separation)",
                    "n_iter": it, "converged": False}
        if float(np.max(np.abs(step))) < tol:
            converged = True
            break
    return {
        "status": OK,
        "intercept": float(beta[0]),
        "slope": float(beta[1]),
        "reason": "",
        "n_iter": it,
        "converged": converged,
    }


# ---------------------------------------------------------------------------
# Thresholded confusion metrics
# ---------------------------------------------------------------------------
def classification_at_threshold(y, p, threshold: float) -> Dict[str, object]:
    """Confusion matrix + precision/recall/F1/accuracy at a FIXED threshold.

    The threshold is a development-fixed decision cut (>= threshold -> positive),
    supplied by the caller from the frozen development configuration; it is never
    tuned on the data being scored here.
    """
    y, p = _as_arrays(y, p)
    if y.size == 0:
        return {"status": INFEASIBLE_EMPTY, "reason": "no observations"}
    pred = (p >= threshold).astype(np.float64)
    tp = int(np.sum((pred == 1) & (y == 1)))
    fp = int(np.sum((pred == 1) & (y == 0)))
    tn = int(np.sum((pred == 0) & (y == 0)))
    fn = int(np.sum((pred == 0) & (y == 1)))
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = None
    accuracy = (tp + tn) / y.size
    return {
        "status": OK,
        "threshold": float(threshold),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "accuracy": float(accuracy),
    }


# ---------------------------------------------------------------------------
# Metric registry (name -> function returning a float or raising for infeasible)
# ---------------------------------------------------------------------------
def _metric_scalar(name: str, y: np.ndarray, p: np.ndarray) -> Optional[float]:
    """Return a scalar for a named metric, or None if infeasible on this sample."""
    if name == "brier":
        mv = brier_score(y, p)
    elif name == "log_loss":
        mv = log_loss(y, p)
    elif name == "auroc":
        mv = auroc(y, p)
    else:
        raise ValueError(f"unknown bootstrap metric {name!r}")
    return mv.value if mv.status == OK else None


# Metrics for which lower is better (loss orientation).
LOWER_IS_BETTER = {"brier": True, "log_loss": True, "auroc": False}


# ---------------------------------------------------------------------------
# Group / sequence-cluster bootstrap
# ---------------------------------------------------------------------------
def cluster_bootstrap(
    y,
    p,
    groups: Sequence[object],
    metric: str = "brier",
    n_boot: int = 2000,
    seed: int = 20260901,
    ci: float = 0.95,
    min_valid_fraction: float = 0.8,
    min_valid_absolute: int = 1000,
) -> Dict[str, object]:
    """Cluster (sequence) bootstrap CI for a single metric.

    Resamples whole CLUSTERS (e.g. seismic sequences) with replacement, not rows,
    so within-cluster dependence is respected. ``n_boot`` defaults to 2000 (the
    registered floor). A replicate is VALID only if the metric is computable on
    it (e.g. AUROC requires both classes to appear in the resample). The
    minimum-valid-replicate rule requires
    ``max(min_valid_absolute, min_valid_fraction * n_boot)`` valid replicates,
    else the interval is reported INFEASIBLE rather than from a thin tail.
    """
    y, p = _as_arrays(y, p)
    groups = np.asarray(list(groups), dtype=object)
    if groups.shape[0] != y.shape[0]:
        raise ValueError("groups length must match y")
    if n_boot < 2000:
        raise ValueError("n_boot must be >= 2000 (registered floor)")
    point = _metric_scalar(metric, y, p)

    uniq = np.array(sorted({g for g in groups.tolist()}, key=lambda v: str(v)),
                    dtype=object)
    # index lists per cluster (stable order)
    idx_by_group: Dict[object, np.ndarray] = {
        g: np.where(groups == g)[0] for g in uniq
    }
    n_clusters = uniq.shape[0]
    rng = np.random.default_rng(seed)

    reps: List[float] = []
    for _ in range(n_boot):
        chosen = rng.integers(0, n_clusters, size=n_clusters)
        parts = [idx_by_group[uniq[c]] for c in chosen]
        idx = np.concatenate(parts) if parts else np.empty(0, dtype=int)
        val = _metric_scalar(metric, y[idx], p[idx])
        if val is not None and math.isfinite(val):
            reps.append(val)

    n_valid = len(reps)
    min_valid = max(int(min_valid_absolute), int(math.ceil(min_valid_fraction * n_boot)))
    if n_valid < min_valid:
        return {
            "status": INFEASIBLE_INSUFFICIENT_VALID_REPLICATES,
            "metric": metric,
            "point": point,
            "n_boot": n_boot,
            "n_valid": n_valid,
            "min_valid_required": min_valid,
            "n_clusters": n_clusters,
            "reason": "too few computable replicates (likely one-class resamples)",
        }
    arr = np.sort(np.asarray(reps, dtype=np.float64))
    lo_q = (1.0 - ci) / 2.0
    hi_q = 1.0 - lo_q
    return {
        "status": OK,
        "metric": metric,
        "point": point,
        "mean": float(np.mean(arr)),
        "ci_lower": float(np.quantile(arr, lo_q, method="linear")),
        "ci_upper": float(np.quantile(arr, hi_q, method="linear")),
        "ci_level": ci,
        "n_boot": n_boot,
        "n_valid": n_valid,
        "min_valid_required": min_valid,
        "n_clusters": n_clusters,
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Paired difference + ordering probability (ranking)
# ---------------------------------------------------------------------------
def paired_cluster_bootstrap_difference(
    y,
    p_a,
    p_b,
    groups: Sequence[object],
    metric: str = "brier",
    n_boot: int = 2000,
    seed: int = 20260901,
    ci: float = 0.95,
    resolution_floor: float = 0.0,
    min_valid_fraction: float = 0.8,
    min_valid_absolute: int = 1000,
) -> Dict[str, object]:
    """Paired cluster bootstrap of the metric DIFFERENCE between two predictors.

    The SAME resampled clusters score both predictors on each replicate (paired),
    which cancels shared sampling noise. ``diff = metric(A) - metric(B)`` per
    replicate. Ordering probabilities are reported WITH a tie band: a replicate
    is a tie when ``|diff| <= resolution_floor``. The pair is 'resolved' only if
    the difference CI excludes the tie band, matching the plan's resolution rule.
    """
    y, pa = _as_arrays(y, p_a)
    _, pb = _as_arrays(y, p_b)
    groups = np.asarray(list(groups), dtype=object)
    if not (groups.shape[0] == y.shape[0] == pa.shape[0] == pb.shape[0]):
        raise ValueError("y, p_a, p_b, groups must be the same length")
    if n_boot < 2000:
        raise ValueError("n_boot must be >= 2000 (registered floor)")

    pa_pt = _metric_scalar(metric, y, pa)
    pb_pt = _metric_scalar(metric, y, pb)
    point_diff = (pa_pt - pb_pt) if (pa_pt is not None and pb_pt is not None) else None
    lower_better = LOWER_IS_BETTER[metric]

    uniq = np.array(sorted({g for g in groups.tolist()}, key=lambda v: str(v)),
                    dtype=object)
    idx_by_group = {g: np.where(groups == g)[0] for g in uniq}
    n_clusters = uniq.shape[0]
    rng = np.random.default_rng(seed)

    diffs: List[float] = []
    a_better = 0
    b_better = 0
    ties = 0
    for _ in range(n_boot):
        chosen = rng.integers(0, n_clusters, size=n_clusters)
        parts = [idx_by_group[uniq[c]] for c in chosen]
        idx = np.concatenate(parts) if parts else np.empty(0, dtype=int)
        va = _metric_scalar(metric, y[idx], pa[idx])
        vb = _metric_scalar(metric, y[idx], pb[idx])
        if va is None or vb is None or not (math.isfinite(va) and math.isfinite(vb)):
            continue
        d = va - vb
        diffs.append(d)
        if abs(d) <= resolution_floor:
            ties += 1
        elif (d < 0) == lower_better:  # A wins if (A<B and lower better) or (A>B and higher better)
            a_better += 1
        else:
            b_better += 1

    n_valid = len(diffs)
    min_valid = max(int(min_valid_absolute), int(math.ceil(min_valid_fraction * n_boot)))
    if n_valid < min_valid:
        return {
            "status": INFEASIBLE_INSUFFICIENT_VALID_REPLICATES,
            "metric": metric,
            "point_diff_a_minus_b": point_diff,
            "n_boot": n_boot,
            "n_valid": n_valid,
            "min_valid_required": min_valid,
            "reason": "too few paired computable replicates",
        }
    arr = np.sort(np.asarray(diffs, dtype=np.float64))
    lo_q = (1.0 - ci) / 2.0
    hi_q = 1.0 - lo_q
    ci_lo = float(np.quantile(arr, lo_q, method="linear"))
    ci_hi = float(np.quantile(arr, hi_q, method="linear"))
    resolved = (ci_lo > resolution_floor) or (ci_hi < -resolution_floor)
    return {
        "status": OK,
        "metric": metric,
        "lower_is_better": lower_better,
        "point_diff_a_minus_b": point_diff,
        "ci_lower": ci_lo,
        "ci_upper": ci_hi,
        "ci_level": ci,
        "resolution_floor": resolution_floor,
        "prob_a_better": a_better / n_valid,
        "prob_b_better": b_better / n_valid,
        "prob_tie": ties / n_valid,
        "resolved": bool(resolved),
        "n_boot": n_boot,
        "n_valid": n_valid,
        "min_valid_required": min_valid,
        "n_clusters": n_clusters,
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Slices (temporal / geographic) and endpoint-threshold sensitivity hooks
# ---------------------------------------------------------------------------
def slice_metrics(
    y,
    p,
    slice_keys: Sequence[object],
    metrics: Sequence[str] = ("brier", "auroc"),
) -> Dict[str, object]:
    """Compute metrics within each value of a slice key (e.g. year, region cell).

    Used for the temporal and geographic reporting slices. Each slice reports its
    own feasibility (a one-class or empty slice yields the metric's INFEASIBLE
    state, never a fabricated value).
    """
    y, p = _as_arrays(y, p)
    keys = np.asarray(list(slice_keys), dtype=object)
    if keys.shape[0] != y.shape[0]:
        raise ValueError("slice_keys length must match y")
    out: Dict[str, object] = {}
    for k in sorted({v for v in keys.tolist()}, key=lambda v: str(v)):
        mask = keys == k
        ys, ps = y[mask], p[mask]
        entry: Dict[str, object] = {"n": int(mask.sum())}
        for m in metrics:
            if m == "brier":
                entry[m] = brier_score(ys, ps).as_dict()
            elif m == "log_loss":
                entry[m] = log_loss(ys, ps).as_dict()
            elif m == "auroc":
                entry[m] = auroc(ys, ps).as_dict()
            else:
                raise ValueError(f"unknown slice metric {m!r}")
        out[str(k)] = entry
    return out


def relabel_at_threshold(cdi_values: Sequence[float], threshold: float) -> np.ndarray:
    """Endpoint-threshold sensitivity hook: recompute the binary severe label.

    Given the raw event-maximum CDI values, produce ``1[cdi >= threshold]`` so a
    caller can re-score any metric under an alternate endpoint threshold
    (e.g. 5.5 / 6.0 / 6.5) without refitting. This does not itself open a
    protected outcome; callers pass CDI arrays they are already permitted to see.
    """
    cdi = np.asarray(cdi_values, dtype=np.float64).ravel()
    return (cdi >= float(threshold)).astype(np.float64)


def threshold_sensitivity(
    cdi_values: Sequence[float],
    p,
    thresholds: Sequence[float] = (5.5, 6.0, 6.5),
    metrics: Sequence[str] = ("brier", "auroc"),
) -> Dict[str, object]:
    """Re-score the given metrics at each endpoint threshold (sensitivity hook)."""
    p = np.asarray(p, dtype=np.float64).ravel()
    out: Dict[str, object] = {}
    for t in thresholds:
        y_t = relabel_at_threshold(cdi_values, t)
        entry: Dict[str, object] = {"prevalence": float(np.mean(y_t)) if y_t.size else None}
        for m in metrics:
            if m == "brier":
                entry[m] = brier_score(y_t, p).as_dict()
            elif m == "log_loss":
                entry[m] = log_loss(y_t, p).as_dict()
            elif m == "auroc":
                entry[m] = auroc(y_t, p).as_dict()
            else:
                raise ValueError(f"unknown sensitivity metric {m!r}")
        out[str(t)] = entry
    return out


def summary(
    y,
    p,
    groups: Optional[Sequence[object]] = None,
    threshold: float = 0.5,
    n_boot: int = 2000,
    seed: int = 20260901,
) -> Dict[str, object]:
    """A single deterministic metric bundle for one predictor on one corpus."""
    y, p = _as_arrays(y, p)
    rep: Dict[str, object] = {
        "n": int(y.size),
        "prevalence": float(np.mean(y)) if y.size else None,
        "brier": brier_score(y, p).as_dict(),
        "log_loss": log_loss(y, p).as_dict(),
        "auroc": auroc(y, p).as_dict(),
        "calibration": calibration_intercept_slope(y, p),
        "classification_at_threshold": classification_at_threshold(y, p, threshold),
    }
    if groups is not None:
        rep["brier_cluster_bootstrap"] = cluster_bootstrap(
            y, p, groups, metric="brier", n_boot=n_boot, seed=seed
        )
    return rep
