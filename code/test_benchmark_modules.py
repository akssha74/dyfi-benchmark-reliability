"""Focused synthetic unit tests for the six DYFI benchmark utility modules.

These tests use ONLY synthetic in-memory fixtures. They never read real USGS
data, never fit a model, and never touch a protected evaluation. Run with:

    python -m unittest test_benchmark_modules -v
    # or simply:  python test_benchmark_modules.py
"""
from __future__ import annotations

import dataclasses
import datetime
import unittest

import common
import decluster
import endpoint
import ingest_eligibility
import leakage_audit
import role_assignment


def _epoch_ms(year, month=1, day=1, hour=0):
    dt = datetime.datetime(year, month, day, hour, tzinfo=datetime.timezone.utc)
    return int(dt.timestamp() * 1000)


class TestCommon(unittest.TestCase):
    def test_schema_membership_and_proxies(self):
        self.assertEqual(common.SOURCE_ONLY_SCHEMA.features, ("magnitude", "depth_km"))
        self.assertEqual(common.SOURCE_ONLY_SCHEMA.proxy_features, ())
        self.assertEqual(
            common.EXPANDED_METADATA_SCHEMA.features,
            ("magnitude", "depth_km", "latitude", "longitude", "origin_year"),
        )
        self.assertEqual(
            common.EXPANDED_METADATA_SCHEMA.proxy_axis,
            {"latitude": "geographic", "longitude": "geographic", "origin_year": "temporal"},
        )
        # Default allowed surface is the strict source-only schema.
        self.assertEqual(common.ALLOWED_FEATURES, ("magnitude", "depth_km"))

    def test_schema_is_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            common.SOURCE_ONLY_SCHEMA.name = "mutated"  # type: ignore[misc]

    def test_region_code_deterministic(self):
        a = common.region_code(34.05, -118.25)
        b = common.region_code(34.05, -118.25)
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("G"))

    def test_strict_int_rejects_fractional(self):
        self.assertEqual(common.strict_int("3", "x"), 3)
        self.assertEqual(common.strict_int(3.0, "x"), 3)
        with self.assertRaises(ValueError):
            common.strict_int("3.5", "x")
        with self.assertRaises(ValueError):
            common.strict_int("", "x")

    def test_strict_float_missing(self):
        with self.assertRaises(ValueError):
            common.strict_float("", "x")
        self.assertEqual(common.strict_float("2.5", "x"), 2.5)

    def test_hash_unit_interval(self):
        u = common.hash_to_unit_interval("abc")
        self.assertTrue(0.0 <= u < 1.0)
        self.assertEqual(u, common.hash_to_unit_interval("abc"))


class TestLeakageFieldAudit(unittest.TestCase):
    def test_source_only_exact_passes(self):
        rep = leakage_audit.audit_feature_names(["magnitude", "depth_km"])
        self.assertTrue(rep["passed"])
        self.assertTrue(rep["exact_clean_schema"])

    def test_forbidden_label_and_ascertainment_rejected(self):
        for bad in ("max_cdi", "severe_label", "num_responses", "felt", "event_id", "shakemap_mmi"):
            rep = leakage_audit.audit_feature_names(["magnitude", "depth_km", bad])
            self.assertFalse(rep["passed"], bad)
            self.assertGreaterEqual(rep["n_rejected"], 1, bad)

    def test_proxies_rejected_under_source_only(self):
        rep = leakage_audit.audit_feature_names(
            ["magnitude", "depth_km", "origin_year", "latitude", "longitude"]
        )
        self.assertFalse(rep["passed"])

    def test_proxies_allowed_under_expanded_schema(self):
        rep = leakage_audit.audit_feature_names(
            ["magnitude", "depth_km", "latitude", "longitude", "origin_year"],
            schema=common.EXPANDED_METADATA_SCHEMA,
        )
        self.assertTrue(rep["passed"])
        self.assertEqual(
            rep["declared_proxy_features"], ["latitude", "longitude", "origin_year"]
        )


class TestLeakageAxisAudit(unittest.TestCase):
    def test_temporal_axis_flags_origin_year(self):
        bad = leakage_audit.audit_features_against_axis(["magnitude", "origin_year"], "temporal")
        self.assertFalse(bad["passed"])
        ok = leakage_audit.audit_features_against_axis(["magnitude", "depth_km"], "temporal")
        self.assertTrue(ok["passed"])

    def test_geographic_axis_flags_location(self):
        for bad_field in ("latitude", "longitude", "region_code"):
            bad = leakage_audit.audit_features_against_axis(["magnitude", bad_field], "geographic")
            self.assertFalse(bad["passed"], bad_field)
        ok = leakage_audit.audit_features_against_axis(["magnitude", "depth_km"], "geographic")
        self.assertTrue(ok["passed"])

    def test_unknown_axis_raises(self):
        with self.assertRaises(ValueError):
            leakage_audit.audit_features_against_axis(["magnitude"], "nonsense")


class TestLeakageRoleManifest(unittest.TestCase):
    def test_clean_temporal_manifest_passes(self):
        rows = [
            {"sequence_id": "S1", "role": "external_temporal_holdout", "origin_year": "2024"},
            {"sequence_id": "S2", "role": "train", "origin_year": "2019"},
            {"sequence_id": "S3", "role": "development", "origin_year": "2018"},
        ]
        rep = leakage_audit.audit_role_manifest(rows, temporal_cutoff_year=2023)
        self.assertTrue(rep["passed"])

    def test_f5_cross_role_detected(self):
        rows = [
            {"sequence_id": "S1", "role": "external_temporal_holdout", "origin_year": "2024"},
            {"sequence_id": "S1", "role": "train", "origin_year": "2019"},
        ]
        rep = leakage_audit.audit_role_manifest(rows, temporal_cutoff_year=2023)
        self.assertFalse(rep["passed"])
        self.assertEqual(len(rep["F5_sequence_cross_role_violations"]), 1)

    def test_f6_temporal_violation_detected(self):
        rows = [
            {"sequence_id": "S1", "role": "external_temporal_holdout", "origin_year": "2019"},
        ]
        rep = leakage_audit.audit_role_manifest(rows, temporal_cutoff_year=2023)
        self.assertFalse(rep["passed"])
        self.assertEqual(len(rep["F6_temporal_leakage_violations"]), 1)

    def test_geographic_manifest_exempt_from_f6_dev_year(self):
        # A geographic manifest legitimately has recent events in the dev pool.
        rows = [
            {"sequence_id": "S1", "role": "geo_holdout", "origin_year": "2024"},
            {"sequence_id": "S2", "role": "train", "origin_year": "2024"},
        ]
        rep = leakage_audit.audit_role_manifest(rows, temporal_cutoff_year=2023)
        self.assertTrue(rep["passed"])


class TestIngestEligibility(unittest.TestCase):
    def _geojson(self):
        return {
            "features": [
                {
                    "id": "ev_ok",
                    "properties": {"cdi": 6.5, "felt": 20, "mag": 5.0, "magType": "mw", "time": _epoch_ms(2020)},
                    "geometry": {"coordinates": [-118.0, 34.0, 8.0]},
                },
                {
                    "id": "ev_low_reports",
                    "properties": {"cdi": 6.0, "felt": 5, "mag": 4.0, "magType": "mw", "time": _epoch_ms(2020)},
                    "geometry": {"coordinates": [-118.0, 34.0, 8.0]},
                },
                {
                    "id": "ev_no_cdi",
                    "properties": {"cdi": None, "felt": 50, "mag": 4.0, "magType": "mw", "time": _epoch_ms(2020)},
                    "geometry": {"coordinates": [-118.0, 34.0, 8.0]},
                },
                {
                    "id": "ev_quarantined",
                    "properties": {"cdi": 7.0, "felt": 99, "mag": 6.0, "magType": "mw", "time": _epoch_ms(2020)},
                    "geometry": {"coordinates": [-118.0, 34.0, 8.0]},
                },
            ]
        }

    def test_eligibility_counts_and_honesty(self):
        res = ingest_eligibility.parse_geojson(self._geojson(), quarantine=["ev_quarantined"])
        stats = res["stats"]
        self.assertEqual(stats["n_eligible"], 1)
        self.assertEqual(stats["n_below_min_reports"], 1)
        self.assertEqual(stats["n_no_cdi"], 1)
        self.assertEqual(stats["n_quarantined"], 1)
        # Honesty flags: ascertainment is NOT outcome-independent.
        self.assertFalse(stats["outcome_independent"])
        self.assertEqual(stats["eligibility_rule"], "post_report_ascertainment")
        row = res["rows"][0]
        self.assertEqual(row["event_id"], "ev_ok")
        self.assertEqual(row["origin_year"], 2020)
        self.assertEqual(row["num_responses"], 20)
        self.assertIn("region_code", row)

    def test_fractional_time_rejected(self):
        gj = {
            "features": [
                {
                    "id": "ev_frac",
                    "properties": {"cdi": 6.5, "felt": 20, "mag": 5.0, "time": 1e9 + 0.5},
                    "geometry": {"coordinates": [-118.0, 34.0, 8.0]},
                }
            ]
        }
        res = ingest_eligibility.parse_geojson(gj)
        self.assertEqual(res["stats"]["n_eligible"], 0)


class TestEndpoint(unittest.TestCase):
    def test_labels(self):
        rows = [{"max_cdi": 6.5}, {"max_cdi": 6.0}, {"max_cdi": 5.9}]
        labelled = endpoint.add_labels(rows)
        self.assertEqual([r["severe_label"] for r in labelled], [1, 1, 0])

    def test_report_thresholds_and_near(self):
        rows = [{"max_cdi": c} for c in (5.4, 5.8, 6.0, 6.4, 7.0)]
        rep = endpoint.endpoint_report(rows)
        self.assertEqual(rep["n_events"], 5)
        self.assertEqual(rep["thresholds"]["6.0"]["positives"], 3)  # 6.0, 6.4, 7.0
        self.assertEqual(rep["thresholds"]["5.5"]["positives"], 4)  # 5.8, 6.0, 6.4, 7.0
        # near-threshold band |c - 6.0| < 0.5 -> 5.8, 6.0, 6.4
        self.assertEqual(rep["near_threshold_events"], 3)


def _ev(eid, year, lat, lon, mag, month=1, day=1):
    return {
        "event_id": eid,
        "magnitude": mag,
        "depth_km": 8.0,
        "latitude": lat,
        "longitude": lon,
        "origin_time": f"{year:04d}-{month:02d}-{day:02d}T00:00:00Z",
        "origin_year": year,
        "region_code": common.region_code(lat, lon),
    }


class TestDecluster(unittest.TestCase):
    def test_order_stability(self):
        rows = [
            _ev("a", 2020, 0.0, 0.0, 5.0, day=1),
            _ev("b", 2020, 0.4, 0.0, 4.0, day=2),
            _ev("c", 2020, 0.8, 0.0, 3.0, day=3),
            _ev("d", 2020, 40.0, 40.0, 6.0, day=1),
        ]
        out1 = decluster.assign_sequences(rows)
        out2 = decluster.assign_sequences(list(reversed(rows)))
        m1 = {r["event_id"]: r["sequence_id"] for r in out1}
        m2 = {r["event_id"]: r["sequence_id"] for r in out2}
        self.assertEqual(m1, m2)

    def test_connected_chain_not_split(self):
        # A-B ~0.8deg (~89km), B-C ~0.8deg, A-C ~1.6deg (~178km > 100km).
        rows = [
            _ev("A", 2020, 0.0, 0.0, 4.0, day=1),
            _ev("B", 2020, 0.8, 0.0, 4.0, day=2),
            _ev("C", 2020, 1.6, 0.0, 4.0, day=3),
        ]
        out = decluster.assign_sequences(rows, space_km=100.0, time_days=30.0)
        seqs = {r["event_id"]: r["sequence_id"] for r in out}
        self.assertEqual(seqs["A"], seqs["B"])
        self.assertEqual(seqs["B"], seqs["C"])  # transitive: chain stays whole

    def test_far_events_separate(self):
        rows = [
            _ev("A", 2020, 0.0, 0.0, 4.0, day=1),
            _ev("Z", 2020, 50.0, 50.0, 4.0, day=1),
        ]
        out = decluster.assign_sequences(rows)
        seqs = {r["event_id"]: r["sequence_id"] for r in out}
        self.assertNotEqual(seqs["A"], seqs["Z"])

    def test_time_window_separates(self):
        rows = [
            _ev("A", 2020, 0.0, 0.0, 4.0, month=1, day=1),
            _ev("B", 2020, 0.0, 0.0, 4.0, month=6, day=1),  # >30 days apart
        ]
        out = decluster.assign_sequences(rows, space_km=100.0, time_days=30.0)
        seqs = {r["event_id"]: r["sequence_id"] for r in out}
        self.assertNotEqual(seqs["A"], seqs["B"])


class TestRoleAssignment(unittest.TestCase):
    def _seq_rows(self):
        # Two whole sequences, each single event, on either side of the cutoff.
        return [
            {"event_id": "e1", "sequence_id": "SEQ_e1", "origin_year": 2024,
             "origin_time": "2024-01-01T00:00:00Z", "region_code": "G+030-120"},
            {"event_id": "e2", "sequence_id": "SEQ_e2", "origin_year": 2018,
             "origin_time": "2018-01-01T00:00:00Z", "region_code": "G+030-120"},
        ]

    def test_temporal_roles_deterministic_and_consistent(self):
        rows = self._seq_rows()
        out1 = role_assignment.assign_temporal_roles(rows)
        out2 = role_assignment.assign_temporal_roles(rows)
        self.assertEqual([r["role"] for r in out1], [r["role"] for r in out2])
        roles = {r["event_id"]: r["role"] for r in out1}
        self.assertEqual(roles["e1"], "external_temporal_holdout")
        self.assertIn(roles["e2"], ("train", "development"))

    def test_temporal_straddle_excluded(self):
        rows = [
            {"event_id": "a", "sequence_id": "SEQ_x", "origin_year": 2022,
             "origin_time": "2022-12-20T00:00:00Z", "region_code": "G+000+000"},
            {"event_id": "b", "sequence_id": "SEQ_x", "origin_year": 2023,
             "origin_time": "2023-01-05T00:00:00Z", "region_code": "G+000+000"},
        ]
        out = role_assignment.assign_temporal_roles(rows)
        self.assertTrue(all(r["role"] == "temporal_straddle_excluded" for r in out))

    def test_temporal_manifest_passes_audit(self):
        # Build many synthetic sequences and confirm the manifest has no F5/F6.
        rows = []
        for i in range(40):
            year = 2015 + (i % 12)  # 2015..2026, straddling the 2023 cutoff by year
            rows.append({
                "event_id": f"e{i}", "sequence_id": f"SEQ_{i}", "origin_year": year,
                "origin_time": f"{year:04d}-06-01T00:00:00Z",
                "region_code": common.region_code((i % 30) - 15, (i * 7 % 60) - 30),
            })
        assigned = role_assignment.assign_temporal_roles(rows)
        manifest = [
            {"sequence_id": r["sequence_id"], "role": r["role"], "origin_year": str(r["origin_year"])}
            for r in assigned
        ]
        rep = leakage_audit.audit_role_manifest(manifest, temporal_cutoff_year=2023)
        self.assertTrue(rep["passed"], rep)

    def test_geographic_roles_sequence_consistent(self):
        rows = []
        for i in range(40):
            lat = (i % 30) - 15
            lon = (i * 11 % 60) - 30
            rows.append({
                "event_id": f"e{i}", "sequence_id": f"SEQ_{i}", "origin_year": 2020,
                "origin_time": "2020-06-01T00:00:00Z",
                "region_code": common.region_code(lat, lon),
            })
        assigned = role_assignment.assign_geographic_roles(rows)
        manifest = [
            {"sequence_id": r["sequence_id"], "role": r["role"], "origin_year": str(r["origin_year"])}
            for r in assigned
        ]
        rep = leakage_audit.audit_role_manifest(manifest, temporal_cutoff_year=2023)
        self.assertTrue(rep["passed"], rep)
        # At least one region should be held out under the prospective rule.
        self.assertIn("geo_holdout", {r["role"] for r in assigned})

    def test_grouped_cv_folds_stable(self):
        rows = [{"sequence_id": f"SEQ_{i}"} for i in range(20)]
        f1 = role_assignment.grouped_cv_folds(rows)
        f2 = role_assignment.grouped_cv_folds(rows)
        self.assertEqual(f1, f2)
        self.assertTrue(all(0 <= v < role_assignment.N_CV_FOLDS for v in f1.values()))

    def test_geographic_holdout_rule_prospective(self):
        # Deterministic function of the region key only.
        r = "G+030-120"
        self.assertEqual(
            role_assignment.is_geographic_holdout_region(r),
            role_assignment.is_geographic_holdout_region(r),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
