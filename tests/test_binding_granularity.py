"""Tests for binding_granularity, precision tiers, computed conclusions,
and the atom_identity_sha256 recompute gate (the integrity additions)."""
import json
from actproof_events.source_binding import (
    compute_field_source_coverage,
    explain_field_source,
    compute_source_atom_identity_hash,
    verify_source_atom_identity_hash,
    source_atom_index,
    field_derivation_index,
)

ACT = "op:eu.dora.ict_incident_notification_initial.v1"


def test_all_required_fields_are_template_cell_granularity():
    derivations = field_derivation_index(ACT)
    from actproof_events.services import get_profile
    required = get_profile(ACT)["required_claim_fields"]
    for fid in required:
        assert derivations[fid]["binding_granularity"] == "template_field", fid


def test_optional_fields_are_lower_granularity_than_template_field():
    cov = compute_field_source_coverage(ACT)
    opt = cov["optional_field_source_basis"]
    assert opt["template_cell_bound"] == 0
    assert opt["section_or_obligation_bound"] == opt["optional_total"]


def test_precision_tiers_sum_to_total():
    cov = compute_field_source_coverage(ACT)
    prec = cov["source_binding_precision"]
    assert prec["template_field"] == 15
    assert sum(prec.values()) == 27


def test_counts_toward_conclusions_are_computed_consistently():
    # Required template_field field: counts toward gate AND coverage.
    e = explain_field_source(ACT, "entity_legal_identifier")
    assert e["binding_granularity"] == "template_field"
    assert e["release_scope"] == "required_release_scope"
    assert e["counts_toward_required_release_gate"] is True
    assert e["counts_toward_field_level_coverage"] is True
    # Optional non-template field: counts toward NEITHER.
    o = explain_field_source(ACT, "linked_nis2_notification_reference")
    assert o["binding_granularity"] != "template_field"
    assert o["counts_toward_required_release_gate"] is False
    assert o["counts_toward_field_level_coverage"] is False


def test_conclusions_are_not_stored_in_data_only_computed():
    # The stored derivation carries the two facts but NOT the derived booleans,
    # so the data has one source of truth per fact.
    d = field_derivation_index(ACT)["entity_legal_identifier"]
    assert "binding_granularity" in d
    assert "release_scope" in d
    assert "counts_toward_required_release_gate" not in d
    assert "counts_toward_field_level_coverage" not in d


def test_atom_identity_hashes_recompute():
    atoms = source_atom_index(ACT)
    for aid, atom in atoms.items():
        assert verify_source_atom_identity_hash(atom), f"{aid} identity hash does not recompute"


def test_identity_hash_is_deterministic_and_basis_locked():
    atoms = source_atom_index(ACT)
    atom = next(iter(atoms.values()))
    h1 = compute_source_atom_identity_hash(atom)
    h2 = compute_source_atom_identity_hash(dict(atom))
    assert h1 == h2
    assert h1.startswith("sha256:")
    # changing an identity field changes the hash
    mutated = dict(atom); mutated["locator"] = {"article": "999"}
    assert compute_source_atom_identity_hash(mutated) != h1


# --- final market-aligned additions: 3-tier vocab, field_binding_status, lint ---

def test_three_tier_headline_vocabulary():
    cov = compute_field_source_coverage(ACT)
    prec = cov["source_binding_precision"]
    # exactly three headline tiers (+ act_fallback), glossary folded into section
    assert set(prec.keys()) == {"template_field", "template_section", "obligation_context", "act_fallback"}
    assert prec["template_field"] == 15
    assert prec["template_section"] == 9
    assert prec["obligation_context"] == 3


def test_field_binding_status_is_computed():
    e = explain_field_source(ACT, "entity_legal_identifier")
    # provisional because official_text_sha256 is still pending in 1.8.0
    assert e["field_binding_status"] == "provisional_locator_bound"
    # and it is NOT stored in the source data
    d = field_derivation_index(ACT)["entity_legal_identifier"]
    assert "field_binding_status" not in d


def test_glossary_nuance_preserved_as_detail():
    d = field_derivation_index(ACT)["secondary_contact_name"]
    # headline tier is template_section, but the glossary nuance is retained
    assert d["binding_granularity"] == "template_section"
    assert d.get("binding_granularity_detail") == "glossary"


def test_lint_report_flags_incomplete_and_attention():
    from actproof_events.services import lint_report
    report = {"entity_legal_identifier": "LEI", "classification_criteria_triggered": "x"}
    r = lint_report(ACT, report)
    assert r["status"] == "incomplete"
    assert r["required_present"] == 2
    assert len(r["missing_required"]) == 13
    assert "classification_criteria_triggered" in r["present_fields_needing_attention"]["high_interpretive_load"]


def test_lint_report_unknown_fields():
    from actproof_events.services import lint_report
    report = {f: "x" for f in __import__("actproof_events").services.get_profile(ACT)["required_claim_fields"]}
    report["totally_made_up_field"] = "x"
    r = lint_report(ACT, report)
    assert "totally_made_up_field" in r["unknown_fields"]
    assert r["required_present"] == 15
