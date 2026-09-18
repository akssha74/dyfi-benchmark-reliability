"""Honest, named reference baselines for the DYFI-USGS single-source
severe-felt-intensity benchmark (construction step 7).

Every baseline is a real, named procedure -- NOT a hand-rolled substitute for a
named method. The suite is fixed and non-selective; the resource claims no winner
among them. Each baseline:

  * declares the exact ``common.FeatureSchema`` it consumes;
  * is leakage-audited (field-level AND axis-level) BEFORE every fit;
  * keeps ALL preprocessing inside the group-CV pipeline (no leakage of scaler
    statistics across folds);
  * is tuned ONLY by the registered deterministic grouped cross-validation on the
    CONSTRUCTION corpus, with a registered grid and a bounded, ledgered fit count;
  * uses fixed seeds so two clean reruns reproduce predictions exactly.

Baselines implemented here:
  B0_no_skill              -- constant train-prevalence predictor (no-skill floor).
  B1_magnitude_only_logit  -- logistic regression on magnitude alone.
  B2_source_only_logit     -- L2-regularised logistic on the SOURCE_ONLY schema
                              (magnitude, depth_km).
  B3_expanded_metadata_logit -- logistic on EXPANDED_METADATA (adds lat/lon/year)
                              PUBLISHED ONLY as an explicitly proxy-bearing
                              sensitivity; it is forbidden on the temporal and
                              geographic transport axes it would leak.
  B4_random_forest         -- scikit-learn RandomForestClassifier (SOURCE_ONLY).
  B5_xgboost               -- XGBoost classifier (SOURCE_ONLY), REGISTERED ONLY
                              IF the pinned, Apache-2.0 licensed, locally
                              executable package imports and passes a smoke fit.

The domain intensity-prediction-equation (IPE) baseline is deliberately NOT
implemented here; a machine-auditable exclusion is recorded in ipe_exclusion.json
because the verified published equation cannot be applied to this benchmark's
schema/population without inventing inputs (see that file).
"""
from __future__ import annotations

import dataclasses
import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import common
import leakage_audit
import role_assignment

RANDOM_SEED = 20260901

# Bounded, registered total fit budget across the whole suite (enforced, not
# declarative). Every .fit() -- each CV fold fit and each final refit -- is
# counted by the FitLedger and must not exceed this cap.
TOTAL_FIT_CAP = 120


# ---------------------------------------------------------------------------
# No-skill constant predictor (a real named baseline, sklearn-compatible)
# ---------------------------------------------------------------------------
class PrevalenceClassifier(BaseEstimator, ClassifierMixin):
    """Predicts the TRAIN-set prevalence of the positive class for every row.

    This is the honest no-skill reference (a proper-scored constant predictor),
    not a degenerate stand-in for a learned model. It is sklearn-compatible so it
    flows through the identical fit/predict/serialize path as the other
    baselines.
    """

    def fit(self, X, y):
        y = np.asarray(y, dtype=np.float64).ravel()
        self.classes_ = np.array([0, 1])
        self.prevalence_ = float(np.mean(y)) if y.size else 0.0
        self.n_features_in_ = np.asarray(X).shape[1] if np.asarray(X).ndim == 2 else 1
        return self

    def predict_proba(self, X):
        n = np.asarray(X).shape[0]
        p1 = np.full(n, self.prevalence_, dtype=np.float64)
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


# ---------------------------------------------------------------------------
# XGBoost availability (registered only if it truly installs + runs)
# ---------------------------------------------------------------------------
def xgboost_status() -> Dict[str, object]:
    """Determine whether the pinned XGBoost is importable and passes a smoke fit."""
    try:
        import xgboost as xgb  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised only if uninstalled
        return {"available": False, "reason": f"import failed: {exc!r}",
                "version": None, "licence": "Apache-2.0"}
    try:
        rng = np.random.RandomState(0)
        X = rng.rand(40, 2)
        y = (X[:, 0] > 0.5).astype(int)
        m = xgb.XGBClassifier(
            n_estimators=10, max_depth=2, random_state=RANDOM_SEED,
            tree_method="hist", n_jobs=1, verbosity=0,
        )
        m.fit(X, y)
        _ = m.predict_proba(X)
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": f"smoke fit failed: {exc!r}",
                "version": getattr(xgb, "__version__", None), "licence": "Apache-2.0"}
    return {"available": True, "reason": "import + smoke fit ok",
            "version": xgb.__version__, "licence": "Apache-2.0"}


XGBOOST_STATUS = xgboost_status()
XGBOOST_AVAILABLE = bool(XGBOOST_STATUS["available"])


# ---------------------------------------------------------------------------
# Baseline specification
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class BaselineSpec:
    """A registered baseline: schema, forbidden axes, grid, and a builder."""

    id: str
    name: str
    honest_reference: str
    schema: common.FeatureSchema
    build: Callable[[Dict[str, object]], Pipeline]
    param_grid: Tuple[Dict[str, object], ...]
    # Evaluation axes this baseline must NEVER be scored on because its schema
    # carries a proxy for that axis (leakage). Empty for leakage-safe baselines.
    forbidden_axes: Tuple[str, ...] = ()

    def grid_size(self) -> int:
        return len(self.param_grid)


def _logit_pipeline(params: Dict[str, object]) -> Pipeline:
    # StandardScaler is INSIDE the pipeline so it is refit within every CV fold.
    return Pipeline(
        steps=[
            ("scale", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    C=float(params.get("C", 1.0)),
                    penalty="l2",
                    solver="lbfgs",
                    max_iter=1000,
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def _rf_pipeline(params: Dict[str, object]) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=int(params.get("n_estimators", 300)),
                    max_depth=params.get("max_depth", None),
                    random_state=RANDOM_SEED,
                    n_jobs=1,  # single-threaded for bitwise determinism
                ),
            )
        ]
    )


def _no_skill_pipeline(params: Dict[str, object]) -> Pipeline:
    return Pipeline(steps=[("clf", PrevalenceClassifier())])


def _xgb_pipeline(params: Dict[str, object]) -> Pipeline:
    import xgboost as xgb  # type: ignore

    return Pipeline(
        steps=[
            (
                "clf",
                xgb.XGBClassifier(
                    n_estimators=int(params.get("n_estimators", 300)),
                    max_depth=int(params.get("max_depth", 3)),
                    learning_rate=float(params.get("learning_rate", 0.1)),
                    subsample=1.0,
                    colsample_bytree=1.0,
                    random_state=RANDOM_SEED,
                    tree_method="hist",
                    n_jobs=1,
                    verbosity=0,
                    eval_metric="logloss",
                ),
            )
        ]
    )


_C_GRID = ({"C": 0.1}, {"C": 1.0}, {"C": 10.0})
_RF_GRID = (
    {"n_estimators": 100, "max_depth": 3},
    {"n_estimators": 100, "max_depth": None},
    {"n_estimators": 300, "max_depth": 3},
    {"n_estimators": 300, "max_depth": None},
)
_XGB_GRID = (
    {"n_estimators": 100, "max_depth": 2, "learning_rate": 0.1},
    {"n_estimators": 100, "max_depth": 4, "learning_rate": 0.1},
    {"n_estimators": 300, "max_depth": 2, "learning_rate": 0.1},
    {"n_estimators": 300, "max_depth": 4, "learning_rate": 0.1},
)


# A magnitude-only schema derived honestly from the source-only schema.
MAGNITUDE_ONLY_SCHEMA = common.FeatureSchema(
    name="magnitude_only",
    features=("magnitude",),
    proxy_features=(),
    proxy_axis={},
    description="Single source covariate (magnitude); the simplest learned baseline.",
)


def registry() -> List[BaselineSpec]:
    """The fixed, ordered baseline suite (XGBoost included only if available)."""
    specs: List[BaselineSpec] = [
        BaselineSpec(
            id="B0_no_skill",
            name="No-skill train-prevalence constant",
            honest_reference="constant predictor at the training positive rate (proper-scored no-skill floor)",
            schema=common.SOURCE_ONLY_SCHEMA,
            build=_no_skill_pipeline,
            param_grid=({},),
        ),
        BaselineSpec(
            id="B1_magnitude_only_logit",
            name="Magnitude-only logistic regression",
            honest_reference="L2 logistic regression on magnitude alone",
            schema=MAGNITUDE_ONLY_SCHEMA,
            build=_logit_pipeline,
            param_grid=_C_GRID,
        ),
        BaselineSpec(
            id="B2_source_only_logit",
            name="Source-only regularised logistic regression",
            honest_reference="L2 logistic regression on magnitude + depth",
            schema=common.SOURCE_ONLY_SCHEMA,
            build=_logit_pipeline,
            param_grid=_C_GRID,
        ),
        BaselineSpec(
            id="B3_expanded_metadata_logit",
            name="Expanded-metadata logistic (proxy-bearing sensitivity)",
            honest_reference="L2 logistic regression on source covariates PLUS disclosed temporal/geographic proxies; published ONLY as a proxy-bearing sensitivity",
            schema=common.EXPANDED_METADATA_SCHEMA,
            build=_logit_pipeline,
            param_grid=_C_GRID,
            forbidden_axes=("temporal", "geographic"),
        ),
        BaselineSpec(
            id="B4_random_forest",
            name="scikit-learn random forest",
            honest_reference="sklearn.ensemble.RandomForestClassifier on magnitude + depth",
            schema=common.SOURCE_ONLY_SCHEMA,
            build=_rf_pipeline,
            param_grid=_RF_GRID,
        ),
    ]
    if XGBOOST_AVAILABLE:
        specs.append(
            BaselineSpec(
                id="B5_xgboost",
                name="XGBoost gradient-boosted trees",
                honest_reference="xgboost.XGBClassifier (hist) on magnitude + depth",
                schema=common.SOURCE_ONLY_SCHEMA,
                build=_xgb_pipeline,
                param_grid=_XGB_GRID,
            )
        )
    return specs


# ---------------------------------------------------------------------------
# Feature extraction + leakage guard
# ---------------------------------------------------------------------------
def extract_features(rows: Sequence[Dict[str, object]], schema: common.FeatureSchema) -> np.ndarray:
    """Build the model matrix in the schema's exact column order.

    Only the schema's declared features are read; any other column in ``rows`` is
    ignored, so a forbidden column present in the table cannot leak into X.
    """
    cols = []
    for f in schema.features:
        cols.append([common.strict_float(r[f], f) for r in rows])
    return np.asarray(cols, dtype=np.float64).T


def extract_labels(rows: Sequence[Dict[str, object]]) -> np.ndarray:
    return np.asarray([common.strict_int(r["severe_label"], "severe_label") for r in rows],
                      dtype=np.float64)


def assert_fit_allowed(spec: BaselineSpec, axis: Optional[str] = None) -> Dict[str, object]:
    """Run the field-level (and, if an axis is given, axis-level) leakage audit.

    Raises LeakageError if the schema is not exactly clean under its own schema,
    or if the baseline is being scored on an axis its schema leaks. Returns the
    audit report on success.
    """
    field_rep = leakage_audit.audit_feature_names(list(spec.schema.features), schema=spec.schema)
    if not field_rep["passed"]:
        raise LeakageError(f"{spec.id}: field-level leakage audit failed: {field_rep}")
    axis_reports: Dict[str, object] = {}
    if axis is not None:
        if axis in spec.forbidden_axes:
            raise LeakageError(
                f"{spec.id}: schema '{spec.schema.name}' carries a proxy for the "
                f"'{axis}' axis and must not be fit/scored on that transport holdout"
            )
        axis_rep = leakage_audit.audit_features_against_axis(list(spec.schema.features), axis)
        axis_reports[axis] = axis_rep
        if not axis_rep["passed"]:
            raise LeakageError(f"{spec.id}: axis-level leakage on '{axis}': {axis_rep}")
    return {"field_level": field_rep, "axis_level": axis_reports, "passed": True}


class LeakageError(RuntimeError):
    """Raised when a baseline would be fit on a leaking field or axis."""


# ---------------------------------------------------------------------------
# Fit ledger (bounded, hashed record of every model fit)
# ---------------------------------------------------------------------------
class FitLedger:
    """Counts and hashes every .fit() call; enforces the registered fit cap."""

    def __init__(self, cap: int = TOTAL_FIT_CAP):
        self.cap = cap
        self.entries: List[Dict[str, object]] = []

    def record(self, baseline_id: str, context: str, params: Dict[str, object]) -> None:
        if len(self.entries) + 1 > self.cap:
            raise RuntimeError(
                f"fit cap {self.cap} exceeded at fit #{len(self.entries) + 1} "
                f"({baseline_id}/{context})"
            )
        self.entries.append(
            {
                "n": len(self.entries) + 1,
                "baseline_id": baseline_id,
                "context": context,
                "params": common.canonical_json(params),
            }
        )

    @property
    def count(self) -> int:
        return len(self.entries)

    def digest(self) -> str:
        return common.sha256_text(common.canonical_json(self.entries))


# ---------------------------------------------------------------------------
# Deterministic grouped cross-validated tuning
# ---------------------------------------------------------------------------
def _folds_for_groups(groups: Sequence[object], n_folds: int) -> np.ndarray:
    """Map each row to a deterministic fold via the registered grouped-CV rule."""
    rows = [{"sequence_id": str(g)} for g in groups]
    fold_of_seq = role_assignment.grouped_cv_folds(rows, n_folds=n_folds)
    return np.asarray([fold_of_seq[str(g)] for g in groups], dtype=int)


def tune_and_fit(
    spec: BaselineSpec,
    rows: Sequence[Dict[str, object]],
    groups: Sequence[object],
    ledger: FitLedger,
    n_folds: int = role_assignment.N_CV_FOLDS,
    axis: Optional[str] = None,
) -> Dict[str, object]:
    """Tune ``spec`` by grouped CV on the construction rows and refit the winner.

    Selection metric is the CROSS-VALIDATED mean Brier score (the primary
    metric). All preprocessing lives inside the pipeline, so no fold sees another
    fold's scaler statistics. Returns the fitted pipeline plus a tuning record.
    """
    audit = assert_fit_allowed(spec, axis=axis)
    X = extract_features(rows, spec.schema)
    y = extract_labels(rows)
    fold = _folds_for_groups(groups, n_folds)

    grid = spec.param_grid
    single = len(grid) == 1
    cv_scores: List[Dict[str, object]] = []
    best_params: Dict[str, object] = dict(grid[0])
    best_score = math.inf

    if single:
        best_params = dict(grid[0])
    else:
        for params in grid:
            fold_briers: List[float] = []
            for k in sorted(set(fold.tolist())):
                tr = fold != k
                te = fold == k
                if te.sum() == 0 or tr.sum() == 0:
                    continue
                if np.unique(y[tr]).size < 2:
                    # cannot fit a discriminative model on a one-class fold
                    continue
                model = spec.build(dict(params))
                ledger.record(spec.id, f"cv_fold_{k}", dict(params))
                model.fit(X[tr], y[tr])
                p = model.predict_proba(X[te])[:, 1]
                fold_briers.append(float(np.mean((p - y[te]) ** 2)))
            mean_brier = float(np.mean(fold_briers)) if fold_briers else math.inf
            cv_scores.append({"params": dict(params), "cv_brier": mean_brier,
                              "n_folds_used": len(fold_briers)})
            if mean_brier < best_score:
                best_score = mean_brier
                best_params = dict(params)

    final_model = spec.build(dict(best_params))
    ledger.record(spec.id, "final_refit", dict(best_params))
    final_model.fit(X, y)

    return {
        "baseline_id": spec.id,
        "name": spec.name,
        "honest_reference": spec.honest_reference,
        "schema": spec.schema.name,
        "features": list(spec.schema.features),
        "forbidden_axes": list(spec.forbidden_axes),
        "leakage_audit": audit,
        "best_params": best_params,
        "cv_selection_metric": "grouped_cv_mean_brier",
        "cv_scores": cv_scores,
        "model": final_model,
    }


def predict_proba(fitted: Dict[str, object], rows: Sequence[Dict[str, object]]) -> np.ndarray:
    """Positive-class probabilities from a fitted baseline record on new rows."""
    spec_schema = common.FEATURE_SCHEMAS.get(fitted["schema"])
    if spec_schema is None and fitted["schema"] == MAGNITUDE_ONLY_SCHEMA.name:
        spec_schema = MAGNITUDE_ONLY_SCHEMA
    X = extract_features(rows, spec_schema)  # type: ignore[arg-type]
    return np.asarray(fitted["model"].predict_proba(X)[:, 1], dtype=np.float64)
