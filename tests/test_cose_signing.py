"""Tests for actproof-events 2.7.0 local COSE source-atom signing prototype."""
from pathlib import Path

from actproof_events.cose_signing import (
    COSE_SOURCE_ATOM_SIGNING_SCHEMA,
    COSE_SOURCE_ATOM_VERIFICATION_SCHEMA,
    COSE_STATUS_SIGNED_LOCAL,
    SCITT_REGISTRATION_STATUS,
    cbor_decode,
    cbor_encode,
    generate_ed25519_keypair,
    sign_source_atom_statement,
    verify_cose_source_atom_statement,
    write_cose_artifact,
)
from actproof_events.scitt_profile import build_source_atom_statement

ACT = "op:eu.dora.ict_incident_notification_initial.v1"
ATOM = "src.eu.dora.32022R2554.art19.reporting_obligation"


def _write_keys(tmp_path: Path) -> tuple[Path, Path]:
    private_pem, public_pem = generate_ed25519_keypair()
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)
    return private_path, public_path


def test_cbor_roundtrip_for_cose_subset():
    value = ["Signature1", {1: -8, 16: "actproof/source-atom/v1"}, b"", b"payload"]
    assert cbor_decode(cbor_encode(value)) == value


def test_sign_and_verify_source_atom_statement(tmp_path):
    private_path, public_path = _write_keys(tmp_path)
    statement = build_source_atom_statement(ACT, ATOM)
    result = sign_source_atom_statement(statement, private_key_path=private_path, kid="test-kid")
    assert result["schema"] == COSE_SOURCE_ATOM_SIGNING_SCHEMA
    assert result["cose_status"] == COSE_STATUS_SIGNED_LOCAL
    assert result["scitt_registration_status"] == SCITT_REGISTRATION_STATUS
    cose_path = tmp_path / "source-atom.cose"
    write_cose_artifact(result, cose_path)
    verdict = verify_cose_source_atom_statement(cose_path, public_key_path=public_path, statement=statement)
    assert verdict["schema"] == COSE_SOURCE_ATOM_VERIFICATION_SCHEMA
    assert verdict["ok"] is True
    assert verdict["signature_valid"] is True
    assert verdict["payload_matches_statement_hash"] is True
    assert verdict["receipt_present"] is False


def test_verify_rejects_statement_tamper_after_signing(tmp_path):
    private_path, public_path = _write_keys(tmp_path)
    statement = build_source_atom_statement(ACT, ATOM)
    result = sign_source_atom_statement(statement, private_key_path=private_path, kid="test-kid")
    cose_path = tmp_path / "source-atom.cose"
    write_cose_artifact(result, cose_path)
    tampered = dict(statement)
    tampered["statement_hash"] = "sha256:" + "0" * 64
    verdict = verify_cose_source_atom_statement(cose_path, public_key_path=public_path, statement=tampered)
    assert verdict["ok"] is False
    assert verdict["reason"] in {"statement_hash_mismatch", "invalid_statement"}


def test_verify_rejects_wrong_key(tmp_path):
    private_path, _public_path = _write_keys(tmp_path)
    wrong_dir = tmp_path / "wrong"
    wrong_dir.mkdir()
    _wrong_private, wrong_public = _write_keys(wrong_dir)
    statement = build_source_atom_statement(ACT, ATOM)
    result = sign_source_atom_statement(statement, private_key_path=private_path, kid="test-kid")
    cose_path = tmp_path / "source-atom.cose"
    write_cose_artifact(result, cose_path)
    verdict = verify_cose_source_atom_statement(cose_path, public_key_path=wrong_public, statement=statement)
    assert verdict["ok"] is False
    assert verdict["reason"] == "invalid_signature"
    assert verdict["signature_valid"] is False
