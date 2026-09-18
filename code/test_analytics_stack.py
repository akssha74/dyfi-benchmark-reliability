"""Focused synthetic unit tests for the DYFI benchmark ANALYTICS stack
(metrics + baselines). Companion to test_benchmark_modules.py (the six core
utilities). Uses ONLY synthetic in-memory fixtures; never reads real USGS data,
never opens a protected role.

Run:  python -m unittest test_analytics_stack -v
"""
from __future__ import annotations

import io
import math
import unittest

import numpy as np

import baselines
import metrics
import synthetic_fixtures as fx


class TestProperScores(unittest.TestCase):
    def test_brier_known_value(self):
        mv = metrics.brier_score([1, 0], [0.75, 0.25])
        self.assertEqual(mv.status, metrics.OK)
        self.assertAlmostEqual(mv.value, ((0.75 - 1) ** 2 + (0.25 - 0) ** 2) / 2)

    def test_brier_empty_infeasible(self):
        self.assertEqual(metrics.brier_score([], []).status, metrics.INFEASIBLE_EMPTY)

    def test_log_loss_finite_at_extremes(self):
        mv = metrics.log_loss([1, 0], [1.0, 0.0])
        self.assertEqual(mv.status, metrics.OK)
        self.assertTrue(math.isfinite(mv.value))

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            metrics.brier_score([0, 2], [0.1, 0.2])  # non-binary label
        with self.assertRaises(ValueError):
            metrics.brier_score([0, 1], [0.1, 1.7])  # prob out of range


class TestAUROC(unittest.TestCase):
    def test_perfect_ranking(self):
        y = [0, 0, 1, 1]
        p = [0.1, 0.2, 0.8, 0.9]
        self.assertAlmostEqual(metrics.auroc(y, p).value, 1.0)

    def test_tied_scores_average_rank(self):
        y, p = fx.tied_yp()
        mv = metrics.auroc(y, p)
        self.assertEqual(mv.status, metrics.OK)
        self.assertAlmostEqual(mv.value, 0.5)  # all tied -> 0.5, order-independent

    def test_order_independence(self):
        y = np.array([1, 0, 1, 0, 1], dtype=float)
        p = np.array([0.6, 0.6, 0.4, 0.9, 0.4], dtype=float)
        a = metrics.auroc(y, p).value
        perm = [3, 0, 4, 1, 2]
        b = metrics.auroc(y[perm], p[perm]).value
        self.assertAlmostEqual(a, b)

    def test_one_class_infeasible(self):
        y, p = fx.one_class_yp()
        self.assertEqual(metrics.auroc(y, p).status, metrics.INFEASIBLE_ONE_CLASS)


class TestCalibration(unittest.TestCase):
    def test_ok_on_normal(self):
        y, p = fx.normal_yp()
        cal = metrics.calibration_intercept_slope(y, p)
        self.assertEqual(cal["status"], metrics.OK)
        self.assertTrue(math.isfinite(cal["slope"]))
        self.assertTrue(cal["converged"])

    def test_constant_prediction_infeasible(self):
        y, p = fx.constant_prediction_yp()
        cal = metrics.calibration_intercept_slope(y, p)
        self.assertEqual(cal["status"], metrics.INFEASIBLE_CONSTANT_PREDICTION)

    def test_one_class_infeasible(self):
        y, p = fx.one_class_yp()
        cal = metrics.calibration_intercept_slope(y, p)
        self.assertEqual(cal["status"], metrics.INFEASIBLE_ONE_CLASS)

    def test_well_calibrated_slope_near_one(self):
        # p == true probability -> recovered slope should be ~1, intercept ~0.
        rng = np.random.default_rng(3)
        p = rng.uniform(0.05, 0.95, size=4000)
        y = (rng.uniform(size=4000) < p).astype(float)
        cal = metrics.calibration_intercept_slope(y, p)
        self.assertEqual(cal["status"], metrics.OK)
        self.assertAlmostEqual(cal["slope"], 1.0, delta=0.2)
        self.assertAlmostEqual(cal["intercept"], 0.0, delta=0.2)


class TestThresholdMetrics(unittest.TestCase):
    def test_confusion(self):
        y = [1, 1, 0, 0]
        p = [0.9, 0.4, 0.6, 0.1]
        r = metrics.classification_at_threshold(y, p, 0.5)
        self.assertEqual((r["tp"], r["fp"], r["tn"], r["fn"]), (1, 1, 1, 1))
        self.assertAlmostEqual(r["precision"], 0.5)
        self.assertAlmostEqual(r["recall"], 0.5)
        self.assertAlmostEqual(r["f1"], 0.5)


class TestClusterBootstrap(unittest.TestCase):
    def test_brier_ci_ok(self):
        rows = fx.make_event_table(seed=1)
        y = fx.labels_of(rows)
        p = np.clip(0.2 + 0.1 * (y - y.mean()), 0.01, 0.99)
        p = np.clip(np.asarray([r["magnitude"] for r in rows]) / 10.0, 0.01, 0.99)
        g = fx.groups_of(rows)
        res = metrics.cluster_bootstrap(y, p, g, metric="brier", n_boot=2000, seed=5)
        self.assertEqual(res["status"], metrics.OK)
        self.assertLessEqual(res["ci_lower"], res["point"])
        self.assertGreaterEqual(res["ci_upper"], res["point"])
        self.assertGreaterEqual(res["n_valid"], res["min_valid_required"])
        self.assertEqual(res["n_boot"], 2000)

    def test_rejects_below_floor(self):
        y, p = fx.normal_yp()
        with self.assertRaises(ValueError):
            metrics.cluster_bootstrap(y, p, ["g"] * len(y), n_boot=500)

    def test_missing_class_triggers_min_valid_rule(self):
        y, p, g = fx.missing_class_corpus()
        res = metrics.cluster_bootstrap(y, p, g, metric="auroc", n_boot=2000, seed=9)
        self.assertEqual(res["status"], metrics.INFEASIBLE_INSUFFICIENT_VALID_REPLICATES)
        self.assertLess(res["n_valid"], res["min_valid_required"])

    def test_deterministic(self):
        y, p = fx.normal_yp()
        g = [f"C{i % 20}" for i in range(len(y))]
        a = metrics.cluster_bootstrap(y, p, g, seed=42)
        b = metrics.cluster_bootstrap(y, p, g, seed=42)
        self.assertEqual(a["ci_lower"], b["ci_lower"])
        self.assertEqual(a["ci_upper"], b["ci_upper"])


class TestPairedRanking(unittest.TestCase):
    def test_resolved_when_a_clearly_better(self):
        rng = np.random.default_rng(2)
        n = 400
        y = (rng.uniform(size=n) < 0.4).astype(float)
        g = [f"C{i % 40}" for i in range(n)]
        p_good = np.clip(0.1 + 0.7 * y + rng.normal(0, 0.1, n), 0.01, 0.99)
        p_bad = np.full(n, y.mean())
        res = metrics.paired_cluster_bootstrap_difference(
            y, p_good, p_bad, g, metric="brier", n_boot=2000, seed=1
        )
        self.assertEqual(res["status"], metrics.OK)
        self.assertGreater(res["prob_a_better"], 0.9)
        self.assertTrue(res["resolved"])
        self.assertAlmostEqual(
            res["prob_a_better"] + res["prob_b_better"] + res["prob_tie"], 1.0
        )

    def test_tie_band_counts_ties(self):
        rng = np.random.default_rng(4)
        n = 200
        y = (rng.uniform(size=n) < 0.5).astype(float)
        g = [f"C{i % 20}" for i in range(n)]
        p = np.clip(0.3 + 0.4 * y + rng.normal(0, 0.1, n), 0.01, 0.99)
        res = metrics.paired_cluster_bootstrap_difference(
            y, p, p.copy(), g, metric="brier", n_boot=2000, seed=1,
            resolution_floor=0.10,
        )
        self.assertEqual(res["status"], metrics.OK)
        self.assertAlmostEqual(res["prob_tie"], 1.0)  # identical predictors -> all ties
        self.assertFalse(res["resolved"])


class TestSlicesAndThresholds(unittest.TestCase):
    def test_temporal_slice(self):
        rows = fx.make_event_table(seed=3)
        y = fx.labels_of(rows)
        p = np.clip(np.asarray([r["magnitude"] for r in rows]) / 10.0, 0.01, 0.99)
        years = [r["origin_year"] for r in rows]
        sl = metrics.slice_metrics(y, p, years, metrics=("brier", "auroc"))
        self.assertTrue(len(sl) >= 2)
        for _k, v in sl.items():
            self.assertIn("brier", v)

    def test_threshold_sensitivity_hooks(self):
        rows = fx.make_event_table(seed=3)
        cdi = [r["max_cdi"] for r in rows]
        p = np.clip(np.asarray([r["magnitude"] for r in rows]) / 10.0, 0.01, 0.99)
        ts = metrics.threshold_sensitivity(cdi, p, thresholds=(5.5, 6.0, 6.5))
        self.assertEqual(set(ts.keys()), {"5.5", "6.0", "6.5"})
        # Higher threshold -> fewer positives -> lower prevalence.
        self.assertGreaterEqual(ts["5.5"]["prevalence"], ts["6.5"]["prevalence"])

    def test_relabel(self):
        lab = metrics.relabel_at_threshold([5.9, 6.0, 6.5], 6.0)
        self.assertEqual(list(lab), [0.0, 1.0, 1.0])


class TestBaselineRegistry(unittest.TestCase):
    def test_expected_ids_present(self):
        ids = [s.id for s in baselines.registry()]
        for want in ("B0_no_skill", "B1_magnitude_only_logit", "B2_source_only_logit",
                     "B3_expanded_metadata_logit", "B4_random_forest"):
            self.assertIn(want, ids)

    def test_xgboost_registered_iff_available(self):
        ids = [s.id for s in baselines.registry()]
        self.assertEqual("B5_xgboost" in ids, baselines.XGBOOST_AVAILABLE)

    def test_expanded_schema_forbidden_on_leaking_axes(self):
        spec = next(s for s in baselines.registry() if s.id == "B3_expanded_metadata_logit")
        for axis in ("temporal", "geographic"):
            with self.assertRaises(baselines.LeakageError):
                baselines.assert_fit_allowed(spec, axis=axis)

    def test_source_only_passes_both_axes(self):
        spec = next(s for s in baselines.registry() if s.id == "B2_source_only_logit")
        for axis in ("temporal", "geographic"):
            rep = baselines.assert_fit_allowed(spec, axis=axis)
            self.assertTrue(rep["passed"])


class TestFeatureExtraction(unittest.TestCase):
    def test_column_order_matches_schema(self):
        rows = fx.make_event_table(n_events=5, n_sequences=2, seed=1)
        import common
        X = baselines.extract_features(rows, common.SOURCE_ONLY_SCHEMA)
        self.assertEqual(X.shape, (5, 2))
        self.assertTrue(np.allclose(X[:, 0], [r["magnitude"] for r in rows]))
        self.assertTrue(np.allclose(X[:, 1], [r["depth_km"] for r in rows]))

    def test_forbidden_column_ignored(self):
        # A row can carry max_cdi/severe_label but extract must never read them.
        import common
        rows = fx.make_event_table(n_events=4, n_sequences=2, seed=1)
        X = baselines.extract_features(rows, common.SOURCE_ONLY_SCHEMA)
        self.assertEqual(X.shape[1], 2)


class TestFitAndPredict(unittest.TestCase):
    def setUp(self):
        self.rows = fx.make_event_table(seed=1)
        self.groups = fx.groups_of(self.rows)

    def test_all_baselines_fit_predict(self):
        ledger = baselines.FitLedger()
        for spec in baselines.registry():
            fitted = baselines.tune_and_fit(spec, self.rows, self.groups, ledger)
            p = baselines.predict_proba(fitted, self.rows)
            self.assertEqual(p.shape[0], len(self.rows))
            self.assertTrue(np.all((p >= 0) & (p <= 1)))
        self.assertLessEqual(ledger.count, baselines.TOTAL_FIT_CAP)
        self.assertGreater(ledger.count, 0)

    def test_no_skill_predicts_prevalence(self):
        spec = next(s for s in baselines.registry() if s.id == "B0_no_skill")
        fitted = baselines.tune_and_fit(spec, self.rows, self.groups, baselines.FitLedger())
        p = baselines.predict_proba(fitted, self.rows)
        self.assertTrue(np.allclose(p, fx.labels_of(self.rows).mean()))

    def test_fit_cap_enforced(self):
        tiny = baselines.FitLedger(cap=2)
        spec = next(s for s in baselines.registry() if s.id == "B4_random_forest")
        with self.assertRaises(RuntimeError):
            baselines.tune_and_fit(spec, self.rows, self.groups, tiny)

    def test_determinism_two_fits_equal(self):
        spec = next(s for s in baselines.registry() if s.id == "B4_random_forest")
        f1 = baselines.tune_and_fit(spec, self.rows, self.groups, baselines.FitLedger())
        f2 = baselines.tune_and_fit(spec, self.rows, self.groups, baselines.FitLedger())
        p1 = baselines.predict_proba(f1, self.rows)
        p2 = baselines.predict_proba(f2, self.rows)
        self.assertTrue(np.array_equal(p1, p2))

    def test_serialize_load_roundtrip(self):
        import joblib
        spec = next(s for s in baselines.registry() if s.id == "B2_source_only_logit")
        fitted = baselines.tune_and_fit(spec, self.rows, self.groups, baselines.FitLedger())
        p_before = baselines.predict_proba(fitted, self.rows)
        buf = io.BytesIO()
        joblib.dump(fitted["model"], buf)
        buf.seek(0)
        model2 = joblib.load(buf)
        p_after = np.asarray(model2.predict_proba(
            baselines.extract_features(self.rows, spec.schema))[:, 1])
        self.assertTrue(np.array_equal(p_before, p_after))


class TestReproducibility(unittest.TestCase):
    def test_event_table_reproducible(self):
        a = fx.make_event_table(seed=123)
        b = fx.make_event_table(seed=123)
        self.assertEqual(a, b)

    def test_event_table_seed_sensitive(self):
        a = fx.make_event_table(seed=1)
        b = fx.make_event_table(seed=2)
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
