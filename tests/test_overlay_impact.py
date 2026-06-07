import copy
import json
from pathlib import Path

from actproof_events.bank_overlay import init_bank_overlay_from_schema
from actproof_events.exports import build_profile_view
from actproof_events.overlay_impact import (
    BANK_OVERLAY_IMPACT_SCHEMA_ID,
    build_overlay_impact_report,
    diff_overlay_impact_files,
)

ACT_ID = "op:eu.dora.ict_incident_notification_initial.v1"
EXTERNAL_SCHEMA = Path("examples/external-schema.example.json")


def _overlay():
    return init_bank_overlay_from_schema(ACT_ID, EXTERNAL_SCHEMA, institution="Example Bank")


def test_no_profile_change_has_no_overlay_impact():
    old = build_profile_view(ACT_ID, generated_at="x")
    new = copy.deepcopy(old)
    overlay = _overlay()
    overlay["profile_semantic_hash"] = old["profile_semantic_hash"]
    report = build_overlay_impact_report(overlay, old, new)
    assert report["schema"] == BANK_OVERLAY_IMPACT_SCHEMA_ID
    assert report["impact_status"] == "no_profile_change"
    assert report["ready_to_carry_forward"] is True
    assert report["summary"]["blocking_items"] == 0


def test_changed_mapped_field_requires_review():
    old = build_profile_view(ACT_ID, generated_at="x")
    new = copy.deepcopy(old)
    overlay = _overlay()
    # Force a known mapped field and make it accepted so the impact is meaningful.
    overlay["mappings"][0]["selected_actproof_field_id"] = "classification_criteria_triggered"
    overlay["mappings"][0]["review_decision"] = "accepted"
    overlay["mappings"][0]["mapping_status"] = "approved_for_internal_review_use"
    overlay["mappings"][0]["reviewed_by"] = "ICT Risk"
    overlay["mappings"][0]["reviewed_at"] = "2026-06-07T00:00:00Z"
    overlay["profile_semantic_hash"] = old["profile_semantic_hash"]
    field = next(f for f in new["fields"] if f["field_id"] == "classification_criteria_triggered")
    field["source_atoms"] = list(field.get("source_atoms") or []) + ["src.example.changed"]
    new["profile_semantic_hash"] = "sha256:" + "2" * 64

    report = build_overlay_impact_report(overlay, old, new)
    assert report["impact_status"] == "review_required"
    impacted = report["impacted_mappings"]
    assert any(x["selected_actproof_field_id"] == "classification_criteria_triggered" for x in impacted)
    assert any("source_basis_changed" in x["impact_reasons"] for x in impacted)
    assert report["ready_to_carry_forward"] is False


def test_removed_accepted_mapping_is_blocking():
    old = build_profile_view(ACT_ID, generated_at="x")
    new = copy.deepcopy(old)
    overlay = _overlay()
    fid = "classification_criteria_triggered"
    overlay["mappings"][0]["selected_actproof_field_id"] = fid
    overlay["mappings"][0]["review_decision"] = "accepted"
    overlay["mappings"][0]["mapping_status"] = "approved_for_internal_review_use"
    overlay["mappings"][0]["reviewed_by"] = "ICT Risk"
    overlay["mappings"][0]["reviewed_at"] = "2026-06-07T00:00:00Z"
    overlay["profile_semantic_hash"] = old["profile_semantic_hash"]
    new["fields"] = [f for f in new["fields"] if f["field_id"] != fid]
    new["profile_semantic_hash"] = "sha256:" + "3" * 64

    report = build_overlay_impact_report(overlay, old, new)
    assert report["impact_status"] == "blocking_review_required"
    assert report["summary"]["blocking_items"] >= 1
    assert any(x["severity"] == "blocking" for x in report["impacted_mappings"])


def test_new_required_field_without_overlay_decision_is_blocking():
    old = build_profile_view(ACT_ID, generated_at="x")
    new = copy.deepcopy(old)
    overlay = _overlay()
    overlay["profile_semantic_hash"] = old["profile_semantic_hash"]
    new["fields"].append({
        "field_id": "new_required_test_field",
        "display_label": "New required test field",
        "required": True,
        "source_basis_scope": "field",
        "source_atoms": ["src.example.required"],
    })
    new["profile_semantic_hash"] = "sha256:" + "4" * 64
    report = build_overlay_impact_report(overlay, old, new)
    assert report["impact_status"] == "blocking_review_required"
    assert any(x["field_id"] == "new_required_test_field" for x in report["new_required_field_impacts"])


def test_diff_overlay_impact_files(tmp_path: Path):
    old = build_profile_view(ACT_ID, generated_at="x")
    new = copy.deepcopy(old)
    new["profile_semantic_hash"] = "sha256:" + "5" * 64
    overlay = _overlay()
    overlay["profile_semantic_hash"] = old["profile_semantic_hash"]
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    overlay_path = tmp_path / "overlay.json"
    old_path.write_text(json.dumps(old), encoding="utf-8")
    new_path.write_text(json.dumps(new), encoding="utf-8")
    overlay_path.write_text(json.dumps(overlay), encoding="utf-8")
    report = diff_overlay_impact_files(overlay_path, old_path, new_path)
    assert report["schema"] == BANK_OVERLAY_IMPACT_SCHEMA_ID
    assert report["profile_semantic_hash_changed"] is True


# --- merge: convenience-path + audit guardrails ------------------------------

import copy as _copy
from actproof_events.overlay_impact import build_overlay_impact_report as _impact


def _accepted_overlay():
    ov = init_bank_overlay_from_schema(ACT_ID, EXTERNAL_SCHEMA, institution="Example Bank")
    for m in ov["mappings"][:1]:
        if m.get("selected_actproof_field_id"):
            m.update(review_decision="accepted", mapping_status="approved_for_internal_prevalidation",
                     reviewed_by="ICT Risk", reviewed_at="2026-06-07", review_notes="internal prevalidation only")
    return ov


def test_new_view_defaults_to_current_profile_no_change():
    # convenience path: omit new view -> compares against current profile (== old)
    ov = _accepted_overlay()
    old = build_profile_view(ACT_ID)
    report = _impact(ov, old)  # new_profile_view omitted
    assert report["impact_status"] == "no_profile_change"
    assert report["profile_semantic_hash_changed"] is False


def test_changed_target_field_impacts_accepted_mapping():
    ov = _accepted_overlay()
    target = next(m["selected_actproof_field_id"] for m in ov["mappings"] if m.get("review_decision") == "accepted")
    old = build_profile_view(ACT_ID)
    new = _copy.deepcopy(old)
    for f in new["fields"]:
        if f["field_id"] == target:
            f["source_atoms"] = list(f.get("source_atoms", [])) + ["src.changed.atom"]
    new["profile_semantic_hash"] = "sha256:" + "c" * 64
    report = _impact(ov, old, new)
    assert report["summary"]["accepted_mappings_impacted"] >= 1
    # the impacted mapping preserves the bank's reviewer + date for audit
    impacted = report["impacted_mappings"]
    assert any(m.get("reviewed_by") == "ICT Risk" and m.get("reviewed_at") == "2026-06-07" for m in impacted)


def test_unchanged_profile_is_honest_no_op():
    ov = _accepted_overlay()
    old = build_profile_view(ACT_ID)
    report = _impact(ov, old, _copy.deepcopy(old))
    assert report["impact_status"] in {"no_profile_change", "no_overlay_impact"}
    assert report["ready_to_carry_forward"] is True
