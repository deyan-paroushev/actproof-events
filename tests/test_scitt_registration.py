"""Tests for actproof-events 2.8.0 local SCITT-style registration / receipt pilot.

Covers the locked 2.8.0 delta: self-contained standalone verification, a
recorded registration_time kept out of the hashed Merkle leaf, the per-entry
previous_receipt_hash chain, policy_digest, and the optional log cross-check.
"""
from pathlib import Path

import pytest

from actproof_events.cose_signing import (
    generate_ed25519_keypair,
    sign_source_atom_statement,
    write_cose_artifact,
)
from actproof_events.scitt_profile import build_source_atom_statement
from actproof_events.scitt_registration import (
    GENESIS_PREVIOUS_RECEIPT_HASH,
    LOCAL_LOG_SCHEMA,
    LOCAL_RECEIPT_SCHEMA,
    LOCAL_RECEIPT_VERIFICATION_SCHEMA,
    REGISTRATION_STATUS_LOCAL,
    RECEIPT_STATUS_LOCAL,
    _leaf_hash,
    compute_receipt_hash,
    init_local_log,
    load_local_log,
    register_signed_statement,
    verify_local_receipt,
    verify_local_receipt_against_log,
)

ACT = "op:eu.dora.ict_incident_notification_initial.v1"
ATOM = "src.eu.dora.32022R2554.art19.reporting_obligation"
ATOM2 = "src.eu.dora.32022R2554.art19.competent_authority_channel"
ATOM3 = "src.eu.dora.32022R2554.art19.p4.initial_intermediate_final"


def _keys(tmp_path: Path, name: str = "key") -> tuple[Path, Path]:
    priv, pub = generate_ed25519_keypair()
    priv_path = tmp_path / f"{name}.private.pem"
    pub_path = tmp_path / f"{name}.public.pem"
    priv_path.write_bytes(priv)
    pub_path.write_bytes(pub)
    return priv_path, pub_path


def _sign(tmp_path: Path, statement: dict, priv: Path, name: str = "stmt") -> Path:
    result = sign_source_atom_statement(statement, private_key_path=priv, kid="test-kid")
    cose_path = tmp_path / f"{name}.cose"
    write_cose_artifact(result, cose_path)
    return cose_path


def _register_one(tmp_path: Path, atom: str = ATOM, name: str = "a"):
    priv, pub = _keys(tmp_path, name)
    statement = build_source_atom_statement(ACT, atom)
    cose_path = _sign(tmp_path, statement, priv, name)
    log_path = tmp_path / "local-log.json"
    if not log_path.exists():
        init_local_log(log_path)
    receipt = register_signed_statement(log_path, cose_path=cose_path, statement=statement)
    return receipt, statement, cose_path, pub, log_path


# --- log + registration shape ---------------------------------------------

def test_init_local_log_is_empty_and_consistent(tmp_path):
    log_path = tmp_path / "local-log.json"
    log = init_local_log(log_path)
    assert log["schema"] == LOCAL_LOG_SCHEMA
    assert log["entry_count"] == 0
    assert log["entries"] == []
    assert log["log_root"].startswith("sha256:")
    assert load_local_log(log_path)["log_root"] == log["log_root"]


def test_init_local_log_refuses_overwrite(tmp_path):
    log_path = tmp_path / "local-log.json"
    init_local_log(log_path)
    with pytest.raises(FileExistsError):
        init_local_log(log_path)


def test_register_produces_receipt_with_commitments_and_aligned_fields(tmp_path):
    receipt, statement, _cose, _pub, _log = _register_one(tmp_path)
    assert receipt["schema"] == LOCAL_RECEIPT_SCHEMA
    assert receipt["registration_status"] == REGISTRATION_STATUS_LOCAL
    assert receipt["receipt_status"] == RECEIPT_STATUS_LOCAL
    assert receipt["statement_hash"] == statement["statement_hash"]
    # Profile View Export bridge.
    assert receipt["profile_commitments"]["profile_semantic_hash"] == statement["commitments"]["profile_semantic_hash"]
    assert receipt["source_atom_commitments"]["atom_identity_sha256"] == statement["commitments"]["atom_identity_sha256"]
    # Mechanism-vocabulary alignment (ACTA/ASQAV).
    assert receipt["canonicalization"] == "JCS/RFC8785"
    assert receipt["statement_ref"] == statement["statement_hash"]
    assert receipt["policy_digest"].startswith("sha256:")
    assert receipt["previous_receipt_hash"] == GENESIS_PREVIOUS_RECEIPT_HASH
    # Recorded registration time present.
    assert receipt["registration_time"].endswith("Z")
    assert receipt["receipt_hash"] == compute_receipt_hash(receipt)


def test_scitt_binding_present_in_statement(tmp_path):
    statement = build_source_atom_statement(ACT, ATOM)
    binding = statement["scitt_binding"]
    assert binding["issuer_model"] == "actproof_as_scitt_issuer"
    assert binding["signed_statement_media_type"] == "application/scitt-statement+cose"
    assert binding["receipt_media_type"] == "application/scitt-receipt+cose"
    assert "iana_registration_pending_rfc_publication" in binding["media_type_status"]


def test_registration_time_excluded_from_leaf(tmp_path):
    """The leaf is reproducible from cose+statement hashes alone, independent
    of the registration timestamp."""
    receipt, _statement, _cose, _pub, _log = _register_one(tmp_path)
    leaf = receipt["log"]["leaf_hash"]
    recomputed = _leaf_hash(receipt["cose_sha256"], receipt["statement_hash"])
    assert leaf == recomputed  # timestamp plays no part in the leaf


def test_register_rejects_cose_for_other_statement(tmp_path):
    priv, _pub = _keys(tmp_path)
    statement_a = build_source_atom_statement(ACT, ATOM)
    statement_b = build_source_atom_statement(ACT, ATOM2)
    cose_b = _sign(tmp_path, statement_b, priv, "b")
    log_path = tmp_path / "local-log.json"
    init_local_log(log_path)
    with pytest.raises(ValueError):
        register_signed_statement(log_path, cose_path=cose_b, statement=statement_a)


# --- end-to-end verification (standalone; no log needed) -------------------

def test_verify_local_receipt_passes_without_log(tmp_path):
    receipt, statement, cose_path, pub, _log = _register_one(tmp_path)
    verdict = verify_local_receipt(receipt, cose_path=cose_path, statement=statement, public_key_path=pub)
    assert verdict["schema"] == LOCAL_RECEIPT_VERIFICATION_SCHEMA
    assert verdict["ok"] is True
    assert verdict["reason"] == "local_receipt_verified"
    assert all(verdict["checks"].values())
    # registration_time surfaced in the verdict
    assert verdict["registration_time"] == receipt["registration_time"]


def test_verify_detects_receipt_tamper(tmp_path):
    receipt, statement, cose_path, pub, _log = _register_one(tmp_path)
    receipt["profile_commitments"]["profile_semantic_hash"] = "sha256:" + "0" * 64
    verdict = verify_local_receipt(receipt, cose_path=cose_path, statement=statement, public_key_path=pub)
    assert verdict["ok"] is False
    assert verdict["reason"] == "receipt_hash_mismatch"


def test_verify_detects_commitment_mismatch_with_consistent_hash(tmp_path):
    receipt, statement, cose_path, pub, _log = _register_one(tmp_path)
    receipt["source_atom_commitments"]["atom_identity_sha256"] = "sha256:" + "0" * 64
    receipt["receipt_hash"] = compute_receipt_hash(receipt)
    verdict = verify_local_receipt(receipt, cose_path=cose_path, statement=statement, public_key_path=pub)
    assert verdict["ok"] is False
    assert verdict["reason"] == "receipt_source_atom_commitments_mismatch"


def test_verify_detects_policy_digest_tamper(tmp_path):
    receipt, statement, cose_path, pub, _log = _register_one(tmp_path)
    receipt["policy_digest"] = "sha256:" + "0" * 64
    receipt["receipt_hash"] = compute_receipt_hash(receipt)
    verdict = verify_local_receipt(receipt, cose_path=cose_path, statement=statement, public_key_path=pub)
    assert verdict["ok"] is False
    assert verdict["reason"] == "policy_digest_mismatch"


def test_verify_detects_wrong_key(tmp_path):
    receipt, statement, cose_path, _pub, _log = _register_one(tmp_path)
    wrong_dir = tmp_path / "wrong"
    wrong_dir.mkdir()
    _wrong_priv, wrong_pub = _keys(wrong_dir, "wrong")
    verdict = verify_local_receipt(receipt, cose_path=cose_path, statement=statement, public_key_path=wrong_pub)
    assert verdict["ok"] is False
    assert verdict["reason"] == "cose_verification_failed"


def test_verify_detects_inclusion_path_tamper(tmp_path):
    receipt, statement, cose_path, pub, _log = _register_one(tmp_path)
    receipt["log"]["log_root"] = "sha256:" + "1" * 64
    receipt["receipt_hash"] = compute_receipt_hash(receipt)
    verdict = verify_local_receipt(receipt, cose_path=cose_path, statement=statement, public_key_path=pub)
    assert verdict["ok"] is False
    assert verdict["reason"] == "inclusion_proof_root_mismatch"


# --- multi-entry log: inclusion proofs + hash chain ------------------------

def test_multi_entry_inclusion_proofs_and_chain(tmp_path):
    priv, pub = _keys(tmp_path)
    log_path = tmp_path / "local-log.json"
    init_local_log(log_path)
    atoms = [ATOM, ATOM2, ATOM3]
    receipts, statements, cose_paths = [], [], []
    for i, atom in enumerate(atoms):
        stmt = build_source_atom_statement(ACT, atom)
        cose_path = _sign(tmp_path, stmt, priv, f"s{i}")
        receipt = register_signed_statement(log_path, cose_path=cose_path, statement=stmt)
        receipts.append(receipt)
        statements.append(stmt)
        cose_paths.append(cose_path)

    # Each receipt verifies standalone against its own committed root.
    for i, receipt in enumerate(receipts):
        verdict = verify_local_receipt(
            receipt, cose_path=cose_paths[i], statement=statements[i], public_key_path=pub
        )
        assert verdict["ok"] is True, (i, verdict.get("reason"))

    # Hash chain: entry 0 is genesis, each subsequent links to prior receipt_hash.
    assert receipts[0]["previous_receipt_hash"] == GENESIS_PREVIOUS_RECEIPT_HASH
    assert receipts[1]["previous_receipt_hash"] == receipts[0]["receipt_hash"]
    assert receipts[2]["previous_receipt_hash"] == receipts[1]["receipt_hash"]


def test_optional_log_cross_check(tmp_path):
    receipt, _statement, _cose, _pub, log_path = _register_one(tmp_path)
    cross = verify_local_receipt_against_log(receipt, log_path=log_path)
    assert cross["leaf_present_at_index"] is True
    assert cross["chain_consistent"] is True
    assert cross["log_root_matches"] is True
    assert cross["ok"] is True
