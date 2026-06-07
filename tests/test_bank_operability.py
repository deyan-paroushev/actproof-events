import json

from actproof_events.bank_operability import (
    build_bank_review_checklist,
    build_prevalidation_run_report,
    build_profile_lock,
)

ACT = "op:eu.dora.ict_incident_notification_initial.v1"


def test_profile_lock_contains_hashes_and_completeness():
    lock = build_profile_lock(ACT)
    assert lock["schema"] == "actproof.profile_lock.v1"
    from actproof_events import __version__
    assert lock["package"]["version"] == __version__
    assert lock["profile"]["profile_semantic_hash"].startswith("sha256:")
    assert lock["component_hashes"]["source_atoms_hash"].startswith("sha256:")
    assert lock["coverage"]["source_atom_coverage"]["total_source_atoms"] >= 1
    assert lock["completeness"]["field_id_policy"]["universal_claim"] is False
    assert lock["profile_lock_hash"].startswith("sha256:")


def test_prevalidation_run_report_hashes_input_without_embedding_payload():
    report = {"entity_legal_identifier": "549300EXAMPLE00000001"}
    out = build_prevalidation_run_report(ACT, report)
    assert out["schema"] == "actproof.prevalidation_report.v1"
    assert out["input_report_hash"].startswith("sha256:")
    assert "entity_legal_identifier" not in json.dumps(out["run_summary"])
    assert out["prevalidation_result"]["prevalidation_status"] == "blocked"
    assert out["prevalidation_report_hash"].startswith("sha256:")


def test_review_checklist_names_bank_review_sections():
    checklist = build_bank_review_checklist(ACT)
    sections = [x["section"] for x in checklist["checklist"]]
    assert "Profile scope and boundary" in sections
    assert "Internal field mapping" in sections
    assert "Change management" in sections
    assert checklist["review_checklist_hash"].startswith("sha256:")


# --- merge: verify_profile_lock round-trip + tamper detection ----------------

from actproof_events.bank_operability import verify_profile_lock


def test_verify_profile_lock_passes_against_self():
    from actproof_events.bank_operability import build_profile_lock
    lock = build_profile_lock("op:eu.dora.ict_incident_notification_initial.v1")
    result = verify_profile_lock(lock)
    assert result["ok"] is True
    assert all(result["checks"].values())


def test_verify_profile_lock_detects_tampered_hash():
    from actproof_events.bank_operability import build_profile_lock
    lock = build_profile_lock("op:eu.dora.ict_incident_notification_initial.v1")
    lock["component_hashes"]["source_atoms_hash"] = "sha256:" + "0" * 64
    result = verify_profile_lock(lock)
    assert result["ok"] is False
    assert result["checks"]["source_atoms_hash"] is False
