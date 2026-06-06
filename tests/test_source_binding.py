import json

from jsonschema.validators import Draft202012Validator

from actproof_events.source_binding import (
    compute_field_source_coverage,
    explain_field_source,
    get_field_derivations_schema,
    get_source_atoms_schema,
    list_field_derivations,
    list_source_atoms,
    validate_field_source_bindings,
)
from actproof_events.exports import build_profile_view

ACT_ID = "op:eu.dora.ict_incident_notification_initial.v1"
REQUIRED = {
    "entity_legal_identifier",
    "entity_legal_name",
    "financial_entity_type",
    "submission_type",
    "incident_reference_code",
    "detection_datetime_utc",
    "classification_datetime_utc",
    "classification_criteria_triggered",
    "affected_member_states",
    "incident_discovery_method",
    "business_continuity_plan_activated",
    "initial_impact_description",
    "primary_contact_name",
    "primary_contact_email",
    "competent_authority",
}


def test_source_atoms_and_derivations_validate_against_schemas():
    atoms_doc = {
        "schema": "actproof.source_atoms.v1",
        "profile_id": ACT_ID,
        "source_atoms": list_source_atoms(ACT_ID),
    }
    derivations_doc = {
        "schema": "actproof.field_derivations.v1",
        "profile_id": ACT_ID,
        "field_derivations": list_field_derivations(ACT_ID),
    }
    assert not list(Draft202012Validator(get_source_atoms_schema()).iter_errors(atoms_doc))
    assert not list(Draft202012Validator(get_field_derivations_schema()).iter_errors(derivations_doc))


def test_dora_required_fields_are_all_field_bound():
    derivations = {d["field_id"] for d in list_field_derivations(ACT_ID)}
    assert REQUIRED <= derivations
    assert validate_field_source_bindings(ACT_ID) == []


def test_field_source_coverage_reaches_1_8_0_gate():
    coverage = compute_field_source_coverage(ACT_ID)
    assert coverage["required_field_source_basis"]["field_level"] == 15
    assert coverage["required_field_source_basis"]["fallback_used"] == 0
    assert coverage["required_field_source_basis"]["coverage_ratio"] == 100.0
    # Final 1.8.0 design: all 27 fields carry derivations, but the market-facing
    # field_source_basis counts only release-gated template-field bindings.
    assert coverage["field_source_basis"]["field_level"] == 15
    assert coverage["field_source_basis"]["contextual_field_level"] == 12
    assert coverage["field_source_basis"]["coverage_ratio"] == 55.6
    assert coverage["field_source_basis"]["coverage_basis"] == "release_gated_template_field_bindings"


def test_explain_field_source_returns_reviewable_derivation():
    explanation = explain_field_source(ACT_ID, "classification_criteria_triggered")
    assert explanation["source_basis_scope"] == "field"
    assert explanation["fallback_used"] is False
    assert explanation["field_derivation"]["derivation_type"] == "interpretive_classification_mapping"
    assert len(explanation["source_atoms"]) >= 3
    assert any(atom["celex"] == "32024R1772" for atom in explanation["source_basis"])


def test_profile_view_exports_required_field_level_coverage():
    view = build_profile_view(ACT_ID, generated_at="2026-01-01T00:00:00Z")
    assert view["coverage"]["required_field_source_basis"]["coverage_ratio"] == 100.0
    required_rows = [f for f in view["fields"] if f["required"]]
    assert len(required_rows) == 15
    assert all(f["source_basis_scope"] == "field" for f in required_rows)
    assert all(f["fallback_used"] is False for f in required_rows)
    # Merged design: optional fields are bound at field scope (experimental_optional),
    # so they no longer use act-level fallback. The release claim still gates on required.
    optional_rows = [f for f in view["fields"] if not f["required"]]
    assert all(f["fallback_used"] is False for f in optional_rows)
