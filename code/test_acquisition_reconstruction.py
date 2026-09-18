"""Synthetic integration tests for the DYFI acquisition + reconstruction stage.

Uses ONLY synthetic in-memory fixtures. Never fetches real USGS data, never opens
a protected cohort, never reads a real outcome. Run:

    python -m unittest test_acquisition_reconstruction -v
"""
from __future__ import annotations

import dataclasses
import unittest

import acquire
import integration_fixtures as ifx
import prehash_rules
import reconstruct


class TestPreHashRules(unittest.TestCase):
    def test_lock_deterministic_and_inactive(self):
        a = prehash_rules.compute_lock()
        b = prehash_rules.compute_lock()
        self.assertEqual(a.combined_digest, b.combined_digest)
        self.assertFalse(a.activated)
        self.assertEqual(len(a.combined_digest), 64)

    def test_role_and_quarantine_never_read_label(self):
        self.assertFalse(prehash_rules.role_rules_record()["reads_label"])
        self.assertFalse(prehash_rules.quarantine_rules_record()["reads_label"])

    def test_quarantine_reasons(self):
        clean = {"event_id": "ok", "eventtype": "earthquake", "magnitude": 5.5,
                 "origin_year": 2020, "latitude": 34.0, "longitude": -118.0, "depth_km": 8.0}
        self.assertEqual(prehash_rules.quarantine_reason(clean), "")
        blast = {**clean, "eventtype": "quarry blast"}
        self.assertEqual(prehash_rules.quarantine_reason(blast), "Q1_non_earthquake_event_type")
        small = {**clean, "magnitude": 4.0}
        self.assertEqual(prehash_rules.quarantine_reason(small), "Q2_outside_pinned_envelope")
        old = {**clean, "origin_year": 2010}
        self.assertEqual(prehash_rules.quarantine_reason(old), "Q2_outside_pinned_envelope")
        badgeo = {**clean, "latitude": 200.0}
        self.assertEqual(prehash_rules.quarantine_reason(badgeo), "Q3_corrupt_or_missing_geometry")

    def test_lock_record_digests_present(self):
        rec = prehash_rules.lock_record()
        for key in ("role_rules_digest", "quarantine_rules_digest",
                    "envelope_digest", "combined_digest"):
            self.assertIn(key, rec["digests"])


class TestAcquireEnvelope(unittest.TestCase):
    def test_envelope_pins(self):
        env = prehash_rules.ACQUISITION_ENVELOPE
        self.assertEqual(env["minmagnitude"], 5.0)
        self.assertEqual(env["producttype"], "dyfi")
        self.assertEqual(env["starttime"], "2015-01-01T00:00:00Z")
        self.assertEqual(env["endtime"], "2025-01-01T00:00:00Z")

    def test_urls_contain_pinned_params(self):
        curl = acquire.build_count_url()
        qurl = acquire.build_query_url()
        for frag in ("minmagnitude=5.0", "producttype=dyfi",
                     "starttime=2015-01-01", "endtime=2025-01-01"):
            self.assertIn(frag, curl)
            self.assertIn(frag, qurl)
        self.assertIn("format=text", curl)      # count endpoint returns integer only
        self.assertIn("format=geojson", qurl)


class TestCountOnlyPreflight(unittest.TestCase):
    def test_outcome_free_and_offline(self):
        rep = acquire.count_only_preflight(execute=False)
        self.assertTrue(rep["outcome_free"])
        self.assertTrue(rep["may_run_without_labels"])
        self.assertFalse(rep["executed_live"])

    def test_records_live_count_drift_as_provenance(self):
        rep = acquire.count_only_preflight(execute=False)
        counts = {c["count"] for c in rep["recorded_live_counts"]}
        self.assertEqual(counts, {7575, 7576})
        drift = rep["drift_receipt"]
        self.assertEqual(drift["count_drift"], 1)
        self.assertFalse(drift["drift_is_error"])
        self.assertTrue(drift["requires_pinned_snapshot"])

    def test_live_requires_explicit_network_flag(self):
        with self.assertRaises(acquire.AcquisitionDisabledError):
            acquire.count_only_preflight(execute=True, allow_network=False)


class TestOutcomeBearingDisabled(unittest.TestCase):
    def test_fetch_disabled_without_token(self):
        with self.assertRaises(acquire.AcquisitionDisabledError):
            acquire.fetch_outcome_bearing_geojson()

    def test_fetch_disabled_even_with_token_no_network(self):
        with self.assertRaises(acquire.AcquisitionDisabledError):
            acquire.fetch_outcome_bearing_geojson(activation_token="x", allow_network=False)

    def test_manifest_pending_has_no_payload_hash(self):
        m = acquire.source_locator_manifest()
        self.assertEqual(m["status"], "PENDING_ACTIVATION")
        self.assertIsNone(m["source_payload_sha256"])
        self.assertFalse(m["outcome_fetched"])
        self.assertTrue(m["exact_full_response_required"])


class TestRetryPolicy(unittest.TestCase):
    def test_backoff_monotonic_capped(self):
        pol = acquire.RetryPolicy(backoff_base_s=2.0, backoff_cap_s=10.0)
        b1, b2, b3 = (pol.backoff_for_attempt(i) for i in (1, 2, 3))
        self.assertLessEqual(b1, b2)
        self.assertLessEqual(pol.backoff_for_attempt(10), pol.backoff_cap_s)
        with self.assertRaises(ValueError):
            pol.backoff_for_attempt(0)


class TestExactFullResponse(unittest.TestCase):
    def test_ok_when_matched(self):
        rec = acquire.verify_exact_full_response(100, 100)
        self.assertTrue(rec["exact_full_response"])

    def test_raises_on_shortfall(self):
        with self.assertRaises(acquire.SnapshotIntegrityError):
            acquire.verify_exact_full_response(90, 100)


class TestRevisionAndQuarantine(unittest.TestCase):
    def setUp(self):
        self.gj = ifx.make_source_geojson(seed=3, n_eligible=40)

    def test_revision_reconciliation_dedups_authoritative(self):
        res = acquire.reconcile_revisions(self.gj["features"])
        # The duplicate authoritative revision must collapse to one kept feature.
        self.assertGreaterEqual(res["n_superseded"], 1)
        self.assertEqual(res["n_kept"] + res["n_superseded"], res["n_input"])
        self.assertTrue(all(r["quarantine_rule"] == "Q4_duplicate_authoritative_origin"
                            for r in res["revision_receipts"]))

    def test_quarantine_ids_flag_deliberate_cases(self):
        q = acquire.quarantine_ids_for_features(self.gj["features"])
        flagged = {rid for rule in q["quarantined_by_rule"].values() for rid in rule}
        self.assertIn("q_blast", flagged)      # Q1
        self.assertIn("q_small", flagged)      # Q2
        self.assertIn("q_badgeo", flagged)     # Q3
        self.assertGreater(q["n_clean"], 0)


class TestReconstruction(unittest.TestCase):
    def setUp(self):
        self.gj = ifx.make_source_geojson(seed=11, n_eligible=120)

    def test_typed_pipeline_stages_and_pass(self):
        res = reconstruct.reconstruct(self.gj, mode="temporal")
        self.assertTrue(res.leakage_passed)
        stage_names = [m.stage for m in res.manifests]
        self.assertEqual(stage_names, [
            "ingest_eligibility", "endpoint_add_labels",
            "decluster_assign_sequences", "role_assignment_temporal",
            "leakage_audit_role_manifest",
        ])
        self.assertGreater(res.n_eligible, 0)
        self.assertEqual(len(res.pipeline_digest), 64)

    def test_manifest_is_immutable(self):
        res = reconstruct.reconstruct(self.gj, mode="temporal")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            res.manifests[0].stage = "mutated"  # type: ignore[misc]

    def test_pipeline_digest_deterministic(self):
        a = reconstruct.reconstruct(self.gj, mode="temporal")
        b = reconstruct.reconstruct(self.gj, mode="temporal")
        self.assertEqual(a.pipeline_digest, b.pipeline_digest)

    def test_order_stability(self):
        self.assertTrue(reconstruct.verify_order_stability(self.gj, mode="temporal"))

    def test_geographic_mode(self):
        res = reconstruct.reconstruct(self.gj, mode="geographic")
        self.assertTrue(res.leakage_passed)

    def test_empty_eligible_fails_closed(self):
        empty = {"type": "FeatureCollection", "features": []}
        with self.assertRaises(reconstruct.ReconstructionError):
            reconstruct.reconstruct(empty, mode="temporal")

    def test_unknown_mode_fails_closed(self):
        with self.assertRaises(reconstruct.ReconstructionError):
            reconstruct.reconstruct(self.gj, mode="nonsense")


if __name__ == "__main__":
    unittest.main(verbosity=2)
