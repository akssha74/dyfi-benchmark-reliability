"""Phase F: post-execution immutable artifacts + hashes + validation inputs.

Runs AFTER the one-shot protected run (activation/run_oneshot.py) has already
produced the official decision-bearing result and consumed the single global
authorization token.

This script performs token-free, deterministic verification work:
  1. Regenerate the full fit ledger from the construction-role tuning pass and
     assert its digest equals the value recorded by the protected run
     (fit_ledger_digest). No holdout is scored here.
  2. Registered W2 reproducibility gate: replay the full analytic core twice,
     including fixed holdout scoring, and confirm both reproduce the recorded
     protected result_core hash exactly (point summaries) and the recorded
     predictions/reconstruction/role digests. These are post-result verification
     replays, not new decision-bearing runs. run_analysis does NOT consume a
     token and does NOT touch the global ledger.
  3. Emit the derived fit ledger, a run log, and a post-execution artifact/source
     SHA-256 manifest over every load-bearing file.

It writes new files only; it never mutates prior artifacts.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import sys
import time

CODE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "code")
ROOT = os.path.dirname(CODE)
sys.path.insert(0, CODE)

import baselines  # noqa: E402
import common  # noqa: E402
import external_runner as R  # noqa: E402
import reconstruct  # noqa: E402
import role_assignment  # noqa: E402

RAW = os.path.join(ROOT, "activation", "raw",
                   "dyfi_M5_dyfi_2015_2025_20260901T063330Z.geojson")
SHA = "88722d8aa6d025cfcc3562f29593cc87d84c6a073bf211e8c21d89adddd4d7e9"
OUT_DIR = os.path.join(ROOT, "results", "protected_run_temporal")
RUN_RESULT = os.path.join(OUT_DIR, "run_result.json")


def _sha_file(path: str) -> str:
    return common.sha256_file(path)


def regenerate_fit_ledger(geojson):
    """Re-run the construction-only tuning pass and dump the full FitLedger."""
    recon = reconstruct.reconstruct(geojson, mode="temporal",
                                    quarantine=R._manual_quarantine())
    rows = list(recon.rows)
    construction = [r for r in rows if r["role"] in R.CONSTRUCTION_ROLES]
    groups = [str(r["sequence_id"]) for r in construction]
    specs = baselines.registry()
    ledger = baselines.FitLedger(cap=R.expected_fit_count(specs))
    fitted = {}
    for spec in specs:
        fitted[spec.id] = baselines.tune_and_fit(spec, construction, groups,
                                                 ledger, axis=None)
    return ledger, {bid: fitted[bid]["best_params"] for bid in sorted(fitted)}


def main() -> int:
    t0 = time.time()
    raw_bytes = open(RAW, "rb").read()
    if hashlib.sha256(raw_bytes).hexdigest() != SHA:
        raise SystemExit("raw payload sha drift; fail closed")
    geojson = common.load_json(RAW)
    recorded = common.load_json(RUN_RESULT)
    core = recorded["result_core"]

    log = []

    def emit(msg):
        line = f"[{time.time() - t0:7.2f}s] {msg}"
        log.append(line)
        print(line)

    emit(f"loaded pinned snapshot {os.path.basename(RAW)} sha256={SHA[:16]}...")
    emit(f"recorded protected result_hash={recorded['result_hash'][:16]}... "
         f"run_token={recorded['run_token'][:16]}...")

    # --- (1) fit ledger regeneration -------------------------------------
    ledger, best_params = regenerate_fit_ledger(geojson)
    ledger_digest = ledger.digest()
    emit(f"regenerated fit ledger: {ledger.count} fits, digest={ledger_digest[:16]}...")
    if ledger.count != core["fit_count"]:
        raise SystemExit(f"fit count mismatch {ledger.count} != {core['fit_count']}")
    if ledger_digest != core["fit_ledger_digest"]:
        raise SystemExit("fit ledger digest mismatch; fail closed")
    if best_params != core["frozen_best_params"]:
        raise SystemExit("best-params mismatch vs recorded protected run")
    emit("fit ledger digest + best-params MATCH recorded protected run (construction-only)")

    fit_ledger_artifact = {
        "record_type": "immutable_fit_ledger",
        "resource_id": core["resource_id"],
        "axis": core["axis"],
        "source_snapshot_sha256": SHA,
        "fit_count": ledger.count,
        "expected_fit_count": core["expected_fit_count"],
        "fit_cap": R.expected_fit_count(baselines.registry()),
        "hard_cap_TOTAL_FIT_CAP": baselines.TOTAL_FIT_CAP,
        "fit_ledger_digest": ledger_digest,
        "matches_protected_run_digest": True,
        "frozen_best_params": best_params,
        "entries": ledger.entries,
        "note": ("Regenerated construction-only (train+development roles); the "
                 "protected transport holdout is NEVER scored in this pass. The "
                 "digest is byte-identical to the value the one-shot protected "
                 "run recorded, proving the fit budget and tuning are reproducible."),
    }
    common.write_json(os.path.join(OUT_DIR, "fit_ledger.json"), fit_ledger_artifact)
    emit("wrote results/protected_run_temporal/fit_ledger.json")

    # --- (2) W2 reproducibility: recompute analytic core twice -----------
    lock = R.build_lock(geojson, mode="protected", axis="temporal",
                        source_snapshot_sha256=SHA)
    rerun_hashes = []
    for i in (1, 2):
        res = R.run_analysis(geojson, lock, axis="temporal",
                             source_snapshot_sha256=SHA)
        h = common.sha256_text(common.canonical_json(res["result_core"]))
        rerun_hashes.append(h)
        emit(f"reproducibility rerun #{i}: result_core hash={h[:16]}...")
    repro_ok = (rerun_hashes[0] == rerun_hashes[1] == recorded["result_hash"])
    emit(f"W2 reproducibility (2 reruns == recorded protected hash): "
         f"{'PASS' if repro_ok else 'FAIL'}")
    if not repro_ok:
        raise SystemExit("reproducibility failure; fail closed (K2)")
    # confirm token ledger still shows exactly one consumed token
    ledger_tokens = common.load_json(os.path.join(CODE, "consumed_run_tokens.json"))
    n_tokens = len(ledger_tokens.get("consumed_tokens", []))
    emit(f"global one-shot token ledger holds {n_tokens} consumed token(s) "
         f"(reruns consumed none)")
    if n_tokens != 1:
        raise SystemExit(f"unexpected token count {n_tokens}; fail closed")

    # --- (3) post-execution artifact / source manifest -------------------
    manifest_files = []
    for rel_dir in ("code", "preregistration", "governance", "activation",
                    "results/protected_run_temporal", "bundle/release",
                    "review/lock-review-opus48", "reports", "validation"):
        d = os.path.join(ROOT, rel_dir)
        for base, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x not in (".venv", "__pycache__",
                                                     ".pytest_cache", ".git")]
            for fn in sorted(files):
                if fn.endswith((".pyc",)) or "__pycache__" in base:
                    continue
                full = os.path.join(base, fn)
                rel = os.path.relpath(full, ROOT)
                manifest_files.append(rel)
    manifest_files = sorted(set(manifest_files))
    artifact_hashes = {rel: _sha_file(os.path.join(ROOT, rel))
                       for rel in manifest_files}
    emit(f"hashed {len(artifact_hashes)} artifact/source files")

    post_manifest = {
        "record_type": "post_execution_artifact_and_source_manifest",
        "resource_id": core["resource_id"],
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_snapshot_sha256": SHA,
        "source_snapshot_path": os.path.relpath(RAW, ROOT),
        "source_snapshot_bytes": len(raw_bytes),
        "protected_result_hash": recorded["result_hash"],
        "run_token": recorded["run_token"],
        "prehash_combined_digest": lock.prehash_combined_digest,
        "code_hashes_at_lock": json.loads(recorded["lock"]["code_hashes"]),
        "n_files": len(artifact_hashes),
        "artifact_sha256": artifact_hashes,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    common.write_json(os.path.join(ROOT, "governance",
                                   "post_execution_artifact_manifest.json"),
                      post_manifest)
    emit("wrote governance/post_execution_artifact_manifest.json")

    # run log
    log_path = os.path.join(OUT_DIR, "phase_f_run_log.txt")
    with open(log_path, "w") as fh:
        fh.write("\n".join(log) + "\n")
    emit(f"wrote {os.path.relpath(log_path, ROOT)}")

    summary = {
        "fit_ledger_digest_match": True,
        "reproducibility_W2": "PASS",
        "rerun_hashes": rerun_hashes,
        "recorded_result_hash": recorded["result_hash"],
        "consumed_tokens": n_tokens,
        "artifact_manifest_files": len(artifact_hashes),
        "elapsed_seconds": round(time.time() - t0, 2),
    }
    common.write_json(os.path.join(ROOT, "activation", "phase_f_summary.json"),
                      summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
