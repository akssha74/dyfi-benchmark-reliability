"""Synthetic integration tests for the hash-locked one-shot runner + report.

Exercises the full forward path on SYNTHETIC data (twice, for determinism) and
injects the deliberate failure modes the runner must fail closed on:
hash / version / subset / retry(one-shot) / leakage / missing-class.

Never fetches real USGS data, never opens a protected cohort, never reads a real
outcome. Run:

    python -m unittest test_runner_report -v
"""
from __future__ import annotations

import dataclasses
import json
import os
import tempfile
import unittest
from unittest import mock

import numpy as np

import baselines
import common
import environment
import external_runner as runner
import integration_fixtures as ifx
import leakage_audit
import metrics
import report as report_mod
import synthetic_fixtures as fx


def _small_source(seed: int = 20260901):
    return ifx.make_source_geojson(seed=seed, n_eligible=420)


class TestRunnerHappyPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gj = _small_source()
        cls.lock = runner.build_lock(cls.gj, mode="synthetic", axis="temporal")
        cls.result = runner.run_analysis(cls.gj, cls.lock, axis="temporal")

    def test_bounded_91_fit_suite(self):
        core = self.result["result_core"]
        self.assertEqual(core["expected_fit_count"], 91)
        self.assertEqual(core["fit_count"], 91)

    def test_holdout_opened_exactly_once(self):
        self.assertEqual(self.result["result_core"]["holdout_opens"], 1)
        self.assertTrue(self.result["verification"]["holdout_opened_once"])

    def test_b3_axis_prohibition_enforced(self):
        core = self.result["result_core"]
        self.assertIn("B3_expanded_metadata_logit", core["excluded_forbidden_axis"])
        self.assertTrue(self.result["verification"]["b3_axis_prohibition_enforced"])

    def test_no_real_protected_role_opened(self):
        self.assertFalse(self.result["result_core"]["real_protected_role_opened"])

    def test_deterministic_serialization_flags(self):
        ser = self.result["result_core"]["serialization_deterministic"]
        self.assertTrue(all(ser.values()))

    def test_determinism_two_runs_equal(self):
        r2 = runner.run_analysis(self.gj, self.lock, axis="temporal")
        h1 = common.sha256_text(common.canonical_json(self.result["result_core"]))
        h2 = common.sha256_text(common.canonical_json(r2["result_core"]))
        self.assertEqual(h1, h2)

    def test_report_has_leakage_headline_and_no_winner(self):
        rep = self.result["result_core"]["report"]
        self.assertTrue(rep["evaluation"]["no_winning_model_claim"])
        self.assertIn("leakage_inflation_headline", rep)
        self.assertIn("per_scheme", rep["leakage_inflation_headline"])


class TestRunnerFailClosed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gj = _small_source(seed=5)
        cls.lock = runner.build_lock(cls.gj, mode="synthetic", axis="temporal")

    def test_hash_failure(self):
        # Corrupt a single locked code hash; the runner must fail closed.
        bad_codes = common.canonical_json({**json.loads(self.lock.code_hashes),
                                           "common.py": "deadbeef"})
        bad_lock = dataclasses.replace(self.lock, code_hashes=bad_codes)
        with self.assertRaises(runner.RunAbort):
            runner.run_analysis(self.gj, bad_lock, axis="temporal")

    def test_version_failure(self):
        patched = {**environment.EXPECTED_VERSIONS, "numpy": "0.0.0-bogus"}
        with mock.patch.dict(environment.EXPECTED_VERSIONS, patched, clear=True):
            with self.assertRaises(RuntimeError):
                environment.verify_environment(strict=True)
            with self.assertRaises(RuntimeError):
                runner.run_analysis(self.gj, self.lock, axis="temporal")

    def test_subset_omission_failure(self):
        truncated = dict(self.gj)
        truncated["features"] = list(self.gj["features"])[: len(self.gj["features"]) // 2]
        with self.assertRaises(runner.RunAbort):
            runner.run_analysis(truncated, self.lock, axis="temporal")

    def test_snapshot_hash_mismatch_failure(self):
        # Lock demands a specific source snapshot; current run has none -> abort.
        locked = dataclasses.replace(self.lock, source_snapshot_sha256="a" * 64)
        with self.assertRaises(runner.RunAbort):
            runner.run_analysis(self.gj, locked, axis="temporal")

    def test_retry_one_shot_token_consumed(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = os.path.join(td, "tokens.json")
            out1 = os.path.join(td, "run1")
            out2 = os.path.join(td, "run2")  # a DIFFERENT output dir
            runner.execute_one_shot(self.gj, self.lock, out1,
                                    token_ledger_path=ledger)
            # A second attempt (even to a fresh directory) is refused.
            with self.assertRaises(runner.RunAbort):
                runner.execute_one_shot(self.gj, self.lock, out2,
                                        token_ledger_path=ledger)


class TestLeakageFailClosed(unittest.TestCase):
    def test_b3_forbidden_axis_raises_at_fit(self):
        spec = next(s for s in baselines.registry() if s.id == "B3_expanded_metadata_logit")
        rows = fx.make_event_table(seed=1)
        groups = fx.groups_of(rows)
        for axis in ("temporal", "geographic"):
            with self.assertRaises(baselines.LeakageError):
                baselines.tune_and_fit(spec, rows, groups, baselines.FitLedger(), axis=axis)

    def test_cross_role_manifest_detected(self):
        manifest = [
            {"sequence_id": "S1", "role": "external_temporal_holdout", "origin_year": "2024"},
            {"sequence_id": "S1", "role": "train", "origin_year": "2019"},
        ]
        rep = leakage_audit.audit_role_manifest(manifest, temporal_cutoff_year=2023)
        self.assertFalse(rep["passed"])
        self.assertEqual(len(rep["F5_sequence_cross_role_violations"]), 1)

    def test_forbidden_features_rejected(self):
        rep = leakage_audit.audit_feature_names(["magnitude", "depth_km", "max_cdi"])
        self.assertFalse(rep["passed"])


class TestMissingClassFailClosed(unittest.TestCase):
    def test_cluster_bootstrap_infeasible(self):
        y, p, g = fx.missing_class_corpus()
        res = metrics.cluster_bootstrap(y, p, g, metric="auroc", n_boot=2000, seed=9)
        self.assertEqual(res["status"], metrics.INFEASIBLE_INSUFFICIENT_VALID_REPLICATES)

    def test_report_surfaces_infeasible_auroc(self):
        # A one-class holdout: AUROC must be INFEASIBLE, never fabricated.
        y = np.ones(20, dtype=float)
        preds = {"B0_no_skill": [0.3] * 20, "B2_source_only_logit": list(np.linspace(0.1, 0.9, 20))}
        groups = [f"C{i % 4}" for i in range(20)]
        rep = report_mod.assemble_evaluation_report(
            y, preds, groups, years=[2020] * 20, regions=["G+000+000"] * 20,
            cdi_values=[6.5] * 20,
        )
        self.assertEqual(rep["per_baseline"]["B2_source_only_logit"]["auroc"],
                         metrics.INFEASIBLE_ONE_CLASS)


class TestReportContent(unittest.TestCase):
    def test_leakage_inflation_positive_on_demo(self):
        rows = ifx.make_leakage_demo_table(seed=7)
        r = report_mod.leakage_inflation_analysis(rows, seed=7)
        self.assertEqual(r["probe_baseline"], "B4_random_forest")
        # Random split is optimistic: higher AUROC, lower Brier than sequence split.
        self.assertGreater(r["auroc_inflation_random_minus_seq"], 0.0)
        self.assertGreater(r["brier_inflation_seq_minus_random"], 0.0)

    def test_difficulty_characterization_bounds(self):
        rows = ifx.make_leakage_demo_table(seed=7)
        d = report_mod.difficulty_characterization(rows, seed=7)
        self.assertTrue(0.0 < d["prevalence_severe"] < 1.0)
        self.assertEqual(d["n_positive"] + d["n_negative"], d["n_events"])

    def test_ranking_reports_tie_and_resolution_states(self):
        rng = np.random.default_rng(2)
        n = 200
        y = (rng.uniform(size=n) < 0.4).astype(float)
        groups = [f"C{i % 20}" for i in range(n)]
        good = np.clip(0.1 + 0.7 * y + rng.normal(0, 0.1, n), 0.01, 0.99)
        preds = {"B0_no_skill": [float(y.mean())] * n,
                 "B2_source_only_logit": good.tolist()}
        rep = report_mod.assemble_evaluation_report(
            y, preds, groups, years=[2020] * n, regions=["G+000+000"] * n,
            cdi_values=[6.5 if v else 5.0 for v in y],
        )
        pair = rep["ranking_vs_reference"]["B2_source_only_logit_vs_B0_no_skill"]
        self.assertIn("prob_tie", pair)
        self.assertIn("resolved", pair)


if __name__ == "__main__":
    unittest.main(verbosity=2)
