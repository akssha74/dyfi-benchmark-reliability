"""Q5 re-pin: recompute load-bearing hashes after the authorized manual-quarantine
addition and update the dependent manifests/contracts, emitting an OLD->NEW
transition record. Run from the study root.

This performs NO acquisition, opens no protected role, reads no outcome. It only
recomputes SHA-256 digests of files already on disk and updates the pinned digest
references that the Q5 change legitimately invalidated. The pre-lock packet
validator (governance/validate_prelock_packet.py) is intentionally NOT modified;
it is a pre-lock gate that is superseded once the contract is locked and the
digest re-pinned (documented in the post-execution validation report).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_PREHASH = "122bf4ccbaad986e37edc4fa914c3481ea90ab823cdead68f5577617455cfcd5"
OLD_RUNNER_CORE = "c32561e2ec4066e596265104825d5ab03b75099806fa24fef401e42bb754abac"


def sha256_file(rel: str) -> str:
    h = hashlib.sha256()
    with open(os.path.join(ROOT, rel), "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load(rel):
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as f:
        return json.load(f)


def dump(rel, obj):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def main() -> int:
    # New prehash digest, computed live from the (edited) prehash rules.
    sys.path.insert(0, os.path.join(ROOT, "code"))
    import prehash_rules  # noqa: E402
    new_prehash = prehash_rules.compute_lock().combined_digest

    # New synthetic runner-result core hash (from the regenerated artifact).
    rr = load("code/runner_result.json")
    new_runner_core = rr.get("result_hash")

    transitions = {"prehash_combined_digest": {"old": OLD_PREHASH, "new": new_prehash},
                   "synthetic_runner_result_core_hash": {"old": OLD_RUNNER_CORE, "new": new_runner_core}}

    # 1. frozen_artifact_manifest.json: recompute every listed artifact hash.
    fam_rel = "governance/frozen_artifact_manifest.json"
    fam = load(fam_rel)
    changed_hashes = {}
    for section in ("source_modules", "test_modules", "config_and_contracts",
                    "stage_validators", "deterministic_outputs"):
        for rel, old in list(fam["artifacts"].get(section, {}).items()):
            new = sha256_file(rel)
            if new != old:
                changed_hashes[rel] = {"old": old, "new": new}
            fam["artifacts"][section][rel] = new
    fam["key_facts_pinned_from_artifacts"]["prehash_combined_digest"] = new_prehash
    fam["key_facts_pinned_from_artifacts"]["runner_result_core_hash"] = new_runner_core
    fam["q5_repin_provenance"] = {
        "repinned_at": "2026-09-01",
        "reason": "Authorized Q5 manual-quarantine addition (ci40925991, us6000pgsd) + "
                  "semantics-preserving wiring of the manual quarantine into the runner "
                  "reconstruction and of the outcome-bearing fetch activation branch. This "
                  "is the binding-condition Q5 digest-changing re-pin; original artifacts "
                  "preserved under snapshots/pre_activation_20260901/.",
        "transitions": transitions,
        "changed_file_hashes": changed_hashes,
    }
    dump(fam_rel, fam)

    # 2. frozen_preregistration.json: update the pinned prehash digest reference.
    pre_rel = "preregistration/frozen_preregistration.json"
    pre = load(pre_rel)
    pre_old = pre.get("prehash_combined_digest")
    pre["prehash_combined_digest"] = new_prehash
    pre["prehash_combined_digest_q5_transition"] = {
        "old": pre_old, "new": new_prehash,
        "note": "Re-pinned at activation for the authorized Q5 manual-quarantine addition; "
                "scientific plan unchanged."}
    dump(pre_rel, pre)

    # 3. source_locator_activation_procedure.json: update pinned digest references.
    slap_rel = "reports/source_locator_activation_procedure.json"
    slap = load(slap_rel)
    if "outcome_free_locators_already_stamped" in slap:
        slap["outcome_free_locators_already_stamped"]["prehash_combined_digest"] = new_prehash
    # Update the human-readable step text that names the old digest.
    steps = slap.get("activation_procedure_after_review", [])
    slap["activation_procedure_after_review"] = [
        s.replace(OLD_PREHASH[:8], new_prehash[:8]).replace(OLD_PREHASH, new_prehash)
        if isinstance(s, str) else s for s in steps]
    slap["q5_repin_note"] = {
        "old_prehash": OLD_PREHASH, "new_prehash": new_prehash,
        "note": "Digest re-pinned for the authorized Q5 manual-quarantine addition."}
    dump(slap_rel, slap)

    print(json.dumps({"new_prehash": new_prehash, "new_runner_core": new_runner_core,
                      "n_changed_file_hashes": len(changed_hashes),
                      "changed": sorted(changed_hashes)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
