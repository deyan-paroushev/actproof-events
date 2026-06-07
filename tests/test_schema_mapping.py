import json
from pathlib import Path

from actproof_events.schema_mapping import compare_schema, compare_schema_file

ACT_ID = "op:eu.dora.ict_incident_notification_initial.v1"


def test_compare_schema_emits_candidates_not_final_matches():
    payload = {
        "external_system": "example-bank-incident-form",
        "fields": [
            {"name": "majorIncidentCriteria", "type": "array", "description": "DORA classification criteria triggered"},
            {"name": "entityLei", "type": "string", "description": "Legal entity identifier"},
            {"name": "internalEscalationOwner", "type": "string"},
        ],
    }
    report = compare_schema(ACT_ID, payload)
    assert report["schema"] == "actproof.external_schema_mapping.v1"
    assert report["mapping_policy"]["mapping_status"] == "candidate_review_required"
    assert report["mapping_policy"]["review_required"] is True
    assert report["mapping_policy"]["not_authoritative"] is True
    assert report["mapping_policy"]["field_ids_universal"] is False
    assert report["summary"]["external_field_count"] == 3
    assert report["mappings"]
    for row in report["mappings"]:
        assert row["mapping_status"] == "candidate_review_required"
        assert row["review_required"] is True
        for cand in row["candidates"]:
            assert cand["mapping_status"] == "candidate_review_required"
            assert cand["review_required"] is True
            assert cand["candidate_strength"] in {"weak", "medium", "strong"}


def test_compare_schema_reports_missing_required_fields():
    payload = {"fields": [{"name": "entity_legal_identifier", "type": "string"}]}
    report = compare_schema(ACT_ID, payload, minimum_strength="medium")
    assert report["summary"]["actproof_required_total"] == 15
    assert report["missing_actproof_required_fields"]
    assert "classification_criteria_triggered" in report["missing_actproof_required_fields"]


def test_compare_schema_file_accepts_json_schema_properties(tmp_path: Path):
    path = tmp_path / "schema.json"
    path.write_text(json.dumps({
        "title": "Example GRC schema",
        "type": "object",
        "required": ["entity_legal_identifier"],
        "properties": {
            "entity_legal_identifier": {"type": "string", "description": "LEI"},
            "classificationCriteria": {"type": "array", "description": "classification criteria triggered"},
        },
    }), encoding="utf-8")
    report = compare_schema_file(ACT_ID, path)
    assert report["external_system"] == "Example GRC schema"
    assert report["summary"]["external_field_count"] == 2
    assert any(row["external_field"] == "entity_legal_identifier" for row in report["mappings"])


# --- merge: honesty-contract guardrail tests --------------------------------
# These lock the invariants that keep candidate mapping from overclaiming.

from actproof_events.schema_mapping import compare_schema as _cmp

_ACT = "op:eu.dora.ict_incident_notification_initial.v1"


def test_no_high_confidence_or_authoritative_language_anywhere():
    r = _cmp(_ACT, ["affectedMemberStates", "majorIncidentCriteria", "entityLEI", "xyz"])
    blob = str(r).lower()
    assert "high confidence" not in blob
    assert "high_confidence" not in blob
    # the only acceptable use of "authoritative" is a negation
    assert "not_authoritative" in blob or "authoritative" not in blob.replace("not_authoritative", "")


def test_every_candidate_strength_is_enumerated():
    r = _cmp(_ACT, ["affectedMemberStates", "majorIncidentCriteria", "entityLEI", "reportType", "xyz"])
    for m in r["mappings"]:
        for c in m.get("candidates", []):
            assert c["candidate_strength"] in {"weak", "medium", "strong"}


def test_every_candidate_is_review_required():
    r = _cmp(_ACT, ["affectedMemberStates", "entityLEI"])
    for m in r["mappings"]:
        assert m["mapping_status"] == "candidate_review_required"
        assert m["review_required"] is True
        for c in m.get("candidates", []):
            assert c["mapping_status"] == "candidate_review_required"
            assert c["review_required"] is True


def test_ambiguous_is_surfaced_not_auto_resolved():
    # an acronym-y field that plausibly hits several entity_* fields
    r = _cmp(_ACT, ["entityLEI"])
    # if flagged ambiguous, it must list >1 competing candidate and stay candidate-only
    for a in r["ambiguous_mappings"]:
        cands = a.get("candidates") or a.get("competing_candidates") or []
        assert len(cands) > 1
        assert a.get("review_required") is True


def test_strong_candidate_is_still_only_a_candidate():
    r = _cmp(_ACT, ["affectedMemberStates"])
    strong = [c for m in r["mappings"] for c in m.get("candidates", [])
              if c["candidate_strength"] == "strong"]
    assert strong  # there is at least one strong match
    for c in strong:
        assert c["mapping_status"] == "candidate_review_required"  # strong != confirmed
