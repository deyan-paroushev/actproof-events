import json
from pathlib import Path

from actproof_events.exports import build_profile_view
from actproof_events.profile_diff import diff_profile_views, diff_profile_view_files

ACT_ID = "op:eu.dora.ict_incident_notification_initial.v1"


def test_diff_profile_views_detects_hash_and_field_changes():
    old = build_profile_view(ACT_ID)
    new = json.loads(json.dumps(old))
    new["profile_semantic_hash"] = "sha256:" + "1" * 64
    field = next(f for f in new["fields"] if f["field_id"] == "classification_criteria_triggered")
    field["review_status"] = "maintainer_reviewed"
    if isinstance(field.get("field_derivation"), dict):
        field["field_derivation"]["review_status"] = "maintainer_reviewed"
    field["source_atoms"] = list(field.get("source_atoms") or []) + ["src.example.changed"]
    new["coverage"] = json.loads(json.dumps(new["coverage"]))
    new["coverage"]["source_atom_coverage"]["unused_source_atoms"] = 99

    report = diff_profile_views(old, new, old_label="old", new_label="new")

    assert report["schema"] == "actproof.profile_diff.v1"
    assert report["summary"]["semantic_hash_changed"] is True
    assert report["summary"]["fields_changed"] >= 1
    assert report["summary"]["source_atom_changes"] >= 1
    assert report["summary"]["coverage_changes"] >= 1
    assert report["summary"]["review_required"] is True
    assert any(x["field_id"] == "classification_criteria_triggered" for x in report["source_atom_changes"])


def test_diff_profile_views_detects_added_and_removed_fields():
    old = build_profile_view(ACT_ID)
    new = json.loads(json.dumps(old))
    removed = new["fields"].pop()
    new["fields"].append({"field_id": "new_external_test_field", "required": False})

    report = diff_profile_views(old, new)

    added_ids = {x["field_id"] for x in report["field_changes"]["added"]}
    removed_ids = {x["field_id"] for x in report["field_changes"]["removed"]}
    assert "new_external_test_field" in added_ids
    assert removed["field_id"] in removed_ids
    assert report["summary"]["review_required"] is True


def test_diff_profile_view_files(tmp_path: Path):
    old = build_profile_view(ACT_ID)
    new = json.loads(json.dumps(old))
    new["profile_artifact_hash"] = "sha256:" + "2" * 64
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(json.dumps(old), encoding="utf-8")
    new_path.write_text(json.dumps(new), encoding="utf-8")

    report = diff_profile_view_files(old_path, new_path)
    assert report["summary"]["artifact_hash_changed"] is True
    assert report["summary"]["review_required"] is False  # artifact-only change is not a semantic review trigger


# --- merge: guardrail tests (act_id refusal + descriptive-only contract) -----

import copy as _copy
from actproof_events.profile_diff import diff_profile_views as _diff
from actproof_events.exports import build_profile_view as _view

_ACT = "op:eu.dora.ict_incident_notification_initial.v1"


def _v():
    return _view(_ACT, generated_at="x")


def test_identical_views_show_no_change_and_no_review_required():
    d = _diff(_v(), _v())
    s = d["summary"]
    assert s["fields_added"] == 0 and s["fields_removed"] == 0 and s["fields_changed"] == 0
    assert s["semantic_hash_changed"] is False
    assert s["review_required"] is False


def test_diff_refuses_act_id_mismatch():
    a = _v()
    b = _copy.deepcopy(a)
    b["act_id"] = "op:eu.other.act.v1"
    d = _diff(a, b)
    assert d.get("error") == "act_id_mismatch"


def test_review_status_change_sets_review_required():
    a = _v()
    b = _copy.deepcopy(a)
    b["completeness"]["review_status"] = "maintainer_reviewed"
    d = _diff(a, b)
    assert d["summary"]["review_required"] is True


def test_diff_is_descriptive_only_not_approval():
    # the report must not assert any change is safe/approved/material
    d = _diff(_v(), _v())
    blob = str(d).lower()
    assert "approved" not in blob
    assert "compliance certification" in blob or "not_for" in str(d).lower()  # boundary present
    # change_control_boundary explicitly excludes auto-approval
    boundary = d.get("change_control_boundary", {})
    not_for = str(boundary.get("not_for", [])).lower()
    assert "automatic approval" in not_for
