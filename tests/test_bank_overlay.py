import json
from pathlib import Path

from actproof_events.bank_overlay import (
    BANK_OVERLAY_REPORT_SCHEMA_ID,
    BANK_OVERLAY_STATUS_SCHEMA_ID,
    BANK_PROFILE_OVERLAY_SCHEMA_ID,
    build_bank_overlay_report,
    build_bank_overlay_status,
    init_bank_overlay_from_schema,
    validate_bank_overlay,
)
from actproof_events.schema_mapping import compare_schema_file

ACT_ID = "op:eu.dora.ict_incident_notification_initial.v1"
EXTERNAL_SCHEMA = Path("examples/external-schema.example.json")


def test_init_bank_overlay_from_schema_is_draft_and_review_required():
    overlay = init_bank_overlay_from_schema(ACT_ID, EXTERNAL_SCHEMA, institution="Example Bank")
    assert overlay["schema"] == BANK_PROFILE_OVERLAY_SCHEMA_ID
    assert overlay["institution"]["name"] == "Example Bank"
    assert overlay["overlay_status"] == "draft"
    assert overlay["mappings"]
    assert all(m["mapping_status"] == "candidate_review_required" for m in overlay["mappings"])
    assert all(m["review_required"] is True for m in overlay["mappings"])
    assert all(m["review_decision"] == "needs_review" for m in overlay["mappings"])


def test_overlay_status_not_ready_until_review_decisions_are_recorded():
    overlay = init_bank_overlay_from_schema(ACT_ID, EXTERNAL_SCHEMA, institution="Example Bank")
    status = build_bank_overlay_status(overlay)
    assert status["schema"] == BANK_OVERLAY_STATUS_SCHEMA_ID
    assert status["profile_semantic_hash_matches"] is True
    assert status["review_required"] is True
    assert status["ready_for_internal_poc"] is False
    assert status["mapping_counts"]["needs_review"] >= 1


def test_overlay_validation_accepts_initial_draft():
    overlay = init_bank_overlay_from_schema(ACT_ID, EXTERNAL_SCHEMA, institution="Example Bank")
    # A draft overlay is valid even if it is not ready for internal POC.
    assert validate_bank_overlay(overlay) == []


def test_accepted_mapping_requires_reviewer_metadata():
    overlay = init_bank_overlay_from_schema(ACT_ID, EXTERNAL_SCHEMA, institution="Example Bank")
    overlay["mappings"][0]["review_decision"] = "accepted"
    overlay["mappings"][0]["mapping_status"] = "approved_for_internal_review_use"
    errors = validate_bank_overlay(overlay)
    assert any("reviewed_by and reviewed_at" in e for e in errors)


def test_overlay_report_is_audit_friendly():
    overlay = init_bank_overlay_from_schema(ACT_ID, EXTERNAL_SCHEMA, institution="Example Bank")
    report = build_bank_overlay_report(overlay)
    assert report["schema"] == BANK_OVERLAY_REPORT_SCHEMA_ID
    assert report["overlay_report_hash"].startswith("sha256:")
    assert report["status"]["ready_for_internal_poc"] is False
    assert report["next_actions"]


def test_overlay_can_be_initialised_from_existing_mapping_report():
    from actproof_events.bank_overlay import init_bank_overlay
    mapping = compare_schema_file(ACT_ID, EXTERNAL_SCHEMA)
    overlay = init_bank_overlay(ACT_ID, mapping, institution={"name": "Example Bank", "identifier": "BANK"})
    assert overlay["source_mapping_report"]["mapping_report_hash"].startswith("sha256:")
    assert overlay["institution"]["identifier"] == "BANK"


# --- merge: honesty guardrails (self-degradation + decision-scoped claim check) ---

def test_hash_change_degrades_status_to_needs_re_review():
    overlay = init_bank_overlay_from_schema(ACT_ID, EXTERNAL_SCHEMA, institution="Example Bank")
    overlay["profile_semantic_hash"] = "sha256:" + "f" * 64  # profile moved
    status = build_bank_overlay_status(overlay)
    assert status["overlay_status"] == "needs_re_review"
    assert status["profile_semantic_hash_matches"] is False


def test_real_legal_equivalence_claim_in_notes_is_rejected():
    overlay = init_bank_overlay_from_schema(ACT_ID, EXTERNAL_SCHEMA, institution="Example Bank")
    m = overlay["mappings"][0]
    m.update(review_decision="accepted", mapping_status="approved_for_internal_prevalidation",
             reviewed_by="ICT Risk", reviewed_at="2026-06-07",
             review_notes="accepted because this is legally equivalent to the regulation")
    errors = validate_bank_overlay(overlay)
    assert any("must not claim" in e for e in errors)


def test_disclaimer_text_does_not_trigger_false_positive():
    # the overlay's own "does not create legal equivalence" disclaimer must NOT
    # be flagged as a forbidden claim
    overlay = init_bank_overlay_from_schema(ACT_ID, EXTERNAL_SCHEMA, institution="Example Bank")
    assert validate_bank_overlay(overlay) == []


def test_derived_status_for_clean_draft_is_review_in_progress():
    overlay = init_bank_overlay_from_schema(ACT_ID, EXTERNAL_SCHEMA, institution="Example Bank")
    status = build_bank_overlay_status(overlay)
    # hash matches, valid, but undecided mappings remain
    assert status["profile_semantic_hash_matches"] is True
    assert status["overlay_status"] in {"review_in_progress", "internal_review_complete"}
    assert status["overlay_status"] != "needs_re_review"
