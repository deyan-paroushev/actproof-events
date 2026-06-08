"""Tests for actproof-events 2.6.0 SCITT/COSE source atom statement profile."""
import json

from actproof_events import __version__
from actproof_events.scitt_profile import (
    SCITT_REGISTRATION_STATUS,
    SCITT_SOURCE_ATOM_MANIFEST_SCHEMA,
    SCITT_SOURCE_ATOM_PROFILE_ID,
    SCITT_SOURCE_ATOM_STATEMENT_SCHEMA,
    SCITT_SOURCE_ATOM_STATEMENT_TYPE,
    build_source_atom_manifest,
    build_source_atom_statement,
    compute_manifest_hash,
    compute_statement_hash,
    validate_source_atom_manifest,
    validate_source_atom_statement,
)

ACT = "op:eu.dora.ict_incident_notification_initial.v1"
ATOM = "src.eu.dora.32022R2554.art19.reporting_obligation"


def test_build_source_atom_statement_shape():
    stmt = build_source_atom_statement(ACT, ATOM)
    assert stmt["schema"] == SCITT_SOURCE_ATOM_STATEMENT_SCHEMA
    assert stmt["statement_type"] == SCITT_SOURCE_ATOM_STATEMENT_TYPE
    assert stmt["profile"] == SCITT_SOURCE_ATOM_PROFILE_ID
    assert stmt["subject"]["atom_id"] == ATOM
    assert stmt["verification"]["scitt_registration_status"] == SCITT_REGISTRATION_STATUS
    assert stmt["verification"]["cose_status"] == "profile_defined_not_signed"
    assert stmt["verification"]["payload_mode"] == "hash_commitment"
    assert stmt["package"]["version"] == __version__
    assert stmt["commitments"]["official_text_sha256"].startswith("sha256:")
    assert stmt["statement_hash"] == compute_statement_hash(stmt)


def test_statement_validates_and_detects_tamper():
    stmt = build_source_atom_statement(ACT, ATOM)
    assert validate_source_atom_statement(stmt) == []
    stmt["commitments"]["canonical_atom_json_sha256"] = "sha256:" + "0" * 64
    assert any("statement_hash mismatch" in e for e in validate_source_atom_statement(stmt))


def test_draft_statement_warns_against_public_registration():
    stmt = build_source_atom_statement(ACT, ATOM)
    assert stmt["maturity"]["review_status"] == "draft"
    assert stmt["maturity"]["registration_recommendation"] == "do_not_register_publicly_until_reviewed"
    assert any("not prove legal correctness" in x for x in stmt["non_claims"])


def test_manifest_lists_all_dora_atoms():
    manifest = build_source_atom_manifest(ACT)
    assert manifest["schema"] == SCITT_SOURCE_ATOM_MANIFEST_SCHEMA
    assert manifest["statement_type"] == SCITT_SOURCE_ATOM_STATEMENT_TYPE
    assert manifest["statement_count"] == 26
    assert manifest["manifest_hash"] == compute_manifest_hash(manifest)
    assert validate_source_atom_manifest(manifest) == []
    assert all(e["scitt_registration_status"] == "not_registered" for e in manifest["entries"])


def test_manifest_contains_three_text_hashes_and_twenty_three_pending():
    manifest = build_source_atom_manifest(ACT)
    with_text = [e for e in manifest["entries"] if e.get("official_text_sha256")]
    without_text = [e for e in manifest["entries"] if not e.get("official_text_sha256")]
    assert len(with_text) == 3
    assert len(without_text) == 23


def test_statement_is_json_serialisable():
    stmt = build_source_atom_statement(ACT, ATOM)
    encoded = json.dumps(stmt, ensure_ascii=False, sort_keys=True)
    assert "actproof/source-atom/v1" in encoded


# --- merged-in: live-atom verification (recompute from the current atom) ---
from actproof_events.scitt_profile import verify_source_atom_statement


def test_verify_passes_against_live_atom():
    stmt = build_source_atom_statement(ACT, ATOM)
    verdict = verify_source_atom_statement(stmt, ACT)
    assert verdict["ok"] is True
    assert verdict["reason"] == "match"


def test_verify_detects_drift_from_live_atom():
    stmt = build_source_atom_statement(ACT, ATOM)
    stmt["commitments"]["official_text_sha256"] = "sha256:" + "0" * 64
    verdict = verify_source_atom_statement(stmt, ACT)
    assert verdict["ok"] is False
    assert verdict["reason"] == "hash_mismatch"
    assert "official_text_sha256" in verdict["mismatches"]


def test_verify_unknown_atom_is_reported():
    stmt = build_source_atom_statement(ACT, ATOM)
    stmt["subject"]["atom_id"] = "src.does.not.exist"
    verdict = verify_source_atom_statement(stmt, ACT)
    assert verdict["ok"] is False
    assert verdict["reason"] == "atom_not_found_in_profile"


def test_verify_uses_act_id_from_statement_when_omitted():
    stmt = build_source_atom_statement(ACT, ATOM)
    verdict = verify_source_atom_statement(stmt)
    assert verdict["ok"] is True
