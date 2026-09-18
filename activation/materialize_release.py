"""Phase F: materialize the released derived artifacts into bundle/release/.

Deterministic, construction-side, token-free. Emits the released event-level
table (ALL roles -- no selective omission), the post-assignment role manifest with
per-role event-id hashes, a copy of the machine-readable one-shot results and fit
ledger, and the stamped source-locator manifest. Every emitted file is content-
hashed so FILE_TABLE / the artifact manifest can pin it.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import sys
from collections import Counter, OrderedDict

CODE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "code")
ROOT = os.path.dirname(CODE)
sys.path.insert(0, CODE)

import common  # noqa: E402
import external_runner as R  # noqa: E402
import reconstruct  # noqa: E402

RAW = os.path.join(ROOT, "activation", "raw",
                   "dyfi_M5_dyfi_2015_2025_20260901T063330Z.geojson")
SHA = "88722d8aa6d025cfcc3562f29593cc87d84c6a073bf211e8c21d89adddd4d7e9"
REL = os.path.join(ROOT, "bundle", "release")
OUT = os.path.join(ROOT, "results", "protected_run_temporal")

COLUMNS = [
    "event_id", "origin_time", "origin_year", "magnitude", "magnitude_type",
    "depth_km", "latitude", "longitude", "region_code",   # outcome-blind features
    "num_responses",                                       # eligibility-only (not a feature)
    "max_cdi", "severe_label",                             # OUTCOME (label)
    "sequence_id", "role",                                 # grouping + split role
]


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    geojson = common.load_json(RAW)
    recon = reconstruct.reconstruct(geojson, mode="temporal",
                                    quarantine=R._manual_quarantine())
    rows = sorted(recon.rows, key=lambda r: (str(r["origin_time"]), str(r["event_id"])))
    emitted = {}

    # --- released event-level table (ALL roles; no selective omission) ---
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLUMNS)
    for r in rows:
        w.writerow([r.get(c, "") for c in COLUMNS])
    csv_text = buf.getvalue()
    csv_path = os.path.join(REL, "event_level_table.csv")
    with open(csv_path, "w") as fh:
        fh.write(csv_text)
    emitted["event_level_table.csv"] = _sha_bytes(csv_text.encode())

    # --- role manifest: per-role event-id hash + counts -------------------
    by_role = OrderedDict()
    for role in sorted({r["role"] for r in rows}):
        ids = sorted(str(r["event_id"]) for r in rows if r["role"] == role)
        seqs = sorted({str(r["sequence_id"]) for r in rows if r["role"] == role})
        by_role[role] = {
            "n_events": len(ids),
            "n_sequences": len(seqs),
            "event_id_sha256": common.sha256_text(common.canonical_json(ids)),
            "sequence_id_sha256": common.sha256_text(common.canonical_json(seqs)),
        }
    role_manifest = {
        "record_type": "post_assignment_role_manifest",
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "axis": "temporal",
        "source_snapshot_sha256": SHA,
        "reconstruction_pipeline_digest": recon.pipeline_digest,
        "prehash_combined_digest": R.prehash_rules.compute_lock().combined_digest,
        "n_eligible_events": len(rows),
        "n_sequences_total": len({str(r["sequence_id"]) for r in rows}),
        "prevalence_severe_all_eligible": round(
            sum(int(r["severe_label"]) for r in rows) / len(rows), 12),
        "roles": by_role,
        "cross_role_sequence_disjoint": True,
        "note": ("Roles assigned by the pre-hashed, label-independent temporal "
                 "rule (cutoff year 2023, ROLE_SALT). temporal_straddle_excluded "
                 "holds sequences that cross the cutoff and enter NO scored role -- "
                 "a documented exclusion, not selective omission. event_level_table "
                 "carries every eligible row across all roles."),
    }
    common.write_json(os.path.join(REL, "role_manifest.json"), role_manifest)
    with open(os.path.join(REL, "role_manifest.json"), "rb") as fh:
        emitted["role_manifest.json"] = _sha_bytes(fh.read())

    # --- machine-readable results + fit ledger ----------------------------
    for src_name, dst_name in (("run_result.json", "results.json"),
                               ("fit_ledger.json", "fit_ledger.json")):
        src = os.path.join(OUT, src_name)
        dst = os.path.join(REL, dst_name)
        shutil.copyfile(src, dst)
        with open(dst, "rb") as fh:
            emitted[dst_name] = _sha_bytes(fh.read())

    # --- activated source-locator manifest --------------------------------
    # code/source_locator_manifest.json is the preserved pre-activation
    # template. Materialization stamps it from the immutable acquisition record
    # so rerunning this script cannot regress the public bundle to PENDING.
    slm = common.load_json(os.path.join(CODE, "source_locator_manifest.json"))
    acquisition = common.load_json(
        os.path.join(ROOT, "activation", "acquisition_record.json")
    )
    slm.update({
        "access_instant": acquisition["access_instant"],
        "count_access_instant": acquisition["count_access_instant"],
        "costamped_count": acquisition["costamped_count"],
        "count_delta": acquisition["count_delta"],
        "count_url_outcome_free": acquisition["count_url"],
        "outcome_fetched": True,
        "payload_bytes": acquisition["payload_bytes"],
        "query_url_outcome_bearing": acquisition["query_url"],
        "source_payload_sha256": acquisition["source_payload_sha256"],
        "status": "ACTIVATED_FROZEN",
    })
    slm_dst = os.path.join(REL, "source_locator_manifest.json")
    common.write_json(slm_dst, slm)
    with open(slm_dst, "rb") as fh:
        emitted["source_locator_manifest.json"] = _sha_bytes(fh.read())

    counts = Counter(r["role"] for r in rows)
    out = {
        "materialized_files": emitted,
        "role_counts": dict(counts),
        "n_eligible": len(rows),
        "csv_columns": COLUMNS,
        "source_locator_status": slm["status"],
        "source_locator_source": "activation/acquisition_record.json",
    }
    common.write_json(os.path.join(ROOT, "activation", "materialize_release_summary.json"),
                      out)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
