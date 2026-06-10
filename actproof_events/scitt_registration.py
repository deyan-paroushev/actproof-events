# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Local SCITT-style registration and receipt verification pilot (2.8.0).

This is the 2.8.0 layer on top of the 2.7.0 local COSE_Sign1 signing prototype.
It models, locally and in-process, the SCITT registration shape:

    signed statement (COSE_Sign1)
        -> append to a local append-only log
        -> compute an inclusion proof against a Merkle-style log root
        -> issue a local receipt

and the corresponding verification:

    local receipt + COSE_Sign1 + statement JSON + issuer public key
        -> re-check the COSE signature over the statement hash
        -> recompute the inclusion proof to the committed log root
        -> confirm the receipt carries the same typed commitments as the signed statement

Design decisions for this release, each grounded in the live SCITT architecture
draft (draft-ietf-scitt-architecture, an Active Internet-Draft in the RFC Editor
queue, not yet a published RFC) and the COSE Receipts draft
(draft-ietf-cose-merkle-tree-proofs):

1. Self-contained receipts. The SCITT architecture states a Receipt "is
   universally verifiable without online access to the TS" and that a relying
   party "MAY decide to verify only a single Receipt". So normal verification
   needs only the receipt, the COSE bytes, the statement and the public key.
   The local log file is never required for verification; it is an OPTIONAL
   audit cross-check (verify_local_receipt_against_log), matching the SCITT
   separation between relying-party verification and auditor replay.

2. Recorded registration time. The SCITT architecture records "Registration
   time ... as the timestamp when the Transparency Service added the Signed
   Statement to its Verifiable Data Structure." This pilot records a
   registration_time in the log entry and the receipt. It is deliberately kept
   OUT of the hashed Merkle leaf preimage so leaf and root stay reproducible;
   the spec only requires that registration time be recorded, not that it be
   part of the leaf. Note: COSE label 394 is the `receipts` array, not a
   timestamp field; this pilot does not claim label-394 semantics.

3. ActProof as SCITT Issuer. The statement profile (scitt_profile) now carries
   a scitt_binding block naming the issuer model and the INTENDED SCITT media
   types. This pilot does not emit application/scitt-receipt+cose CBOR and does
   not register with any external Transparency Service.

4. Mechanism-vocabulary alignment. Where ActProof's receipt mechanics coincide
   with the signed-action-receipt family (ACTA / ASQAV), this release uses the
   shared names: canonicalization "JCS/RFC8785", policy_digest,
   previous_receipt_hash, and statement_ref (the ActProof analogue of an action
   receipt's action_ref, but referring to an ActProof typed statement rather than
   an agent action). ActProof-native commitment names are kept. This is
   alignment, not conformance: ACTA and ASQAV are individual / Independent
   Internet-Drafts, not IETF consensus, and no conformance is claimed.

Receipt verification here proves only local inclusion in a local log plus a
local COSE signature. It does not prove external transparency-service
registration, legal correctness, compliance, bank approval or supervisory
acceptance.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from actproof_events import __version__
from actproof_events.cose_signing import (
    COSE_HEADER_KID,
    load_cose_sign1,
    sha256_bytes,
    verify_cose_statement,
)
from actproof_events.scitt_profile import (
    CANONICALIZATION,
    HASH_ALGORITHM,
)
from actproof_events.statement_profiles import (
    compute_statement_hash_for_type,
    validate_statement,
    profile_commitments as _typed_profile_commitments,
    source_atom_commitments as _typed_source_atom_commitments,
    statement_subject as _typed_statement_subject,
)

# --- profile identifiers --------------------------------------------------

LOCAL_LOG_SCHEMA = "actproof.scitt_local_transparency_log.v1"
LOCAL_LOG_ENTRY_SCHEMA = "actproof.scitt_local_log_entry.v1"
LOCAL_RECEIPT_SCHEMA = "actproof.scitt_local_receipt.v1"
LOCAL_RECEIPT_VERIFICATION_SCHEMA = "actproof.scitt_local_receipt_verification.v1"

# SCITT media types. Referenced as the INTENDED types for a future external
# receipt. They are defined in the SCITT architecture draft with registration
# requested (reference "RFCthis"); registration is pending RFC publication.
# This pilot does not emit them.
SCITT_STATEMENT_MEDIA_TYPE = "application/scitt-statement+cose"
SCITT_RECEIPT_MEDIA_TYPE = "application/scitt-receipt+cose"

# Mechanism-vocabulary alignment with the signed-action-receipt family.
CANONICALIZATION_LABEL = "JCS/RFC8785"

REGISTRATION_STATUS_LOCAL = "registered_local_transparency_pilot"
RECEIPT_STATUS_LOCAL = "local_receipt_pilot"

ISSUER_MODEL = "actproof_as_scitt_issuer"
PAYLOAD_PROFILE_TYPE = "actproof/source-atom/v1"
PUBLIC_REGISTRATION_POLICY = "do_not_register_publicly_until_reviewed"
TRANSPARENCY_SERVICE_MODEL = (
    "service_selected_by_deployment; local pilot in 2.8.x; "
    "external SCITT Transparency Service deferred"
)

# First-entry sentinel for the per-entry hash chain (ACTA/ASQAV convention).
GENESIS_PREVIOUS_RECEIPT_HASH = "sha256:" + "0" * 64

NON_CLAIMS = [
    "Local registration adds the signed statement to a local append-only log only.",
    "The local receipt proves local inclusion plus a local COSE signature, nothing more.",
    "This release does not register statements with an external SCITT Transparency Service.",
    "This release does not emit application/scitt-receipt+cose CBOR receipts.",
    "This release does not claim conformance to the CCF or MMR COSE Receipt profiles.",
    "This release does not claim conformance to the ACTA or ASQAV signed-action-receipt drafts; vocabulary is aligned where mechanics coincide, not conformed.",
    "The SCITT architecture is an Active Internet-Draft in the RFC Editor queue and is not yet a published RFC.",
    "The SCITT media types are defined in the draft with registration requested; IANA registration is pending RFC publication.",
    "A local receipt does not prove legal correctness, compliance certification, bank approval or supervisory approval.",
    "Draft atom statements should not be treated as reviewed public trust artifacts.",
]


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------

def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _hex_only(value: str) -> str:
    return value.split(":", 1)[1] if ":" in value else value


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _leaf_hash(cose_sha256: str, statement_hash: str) -> str:
    """Deterministic leaf hash binding the COSE bytes to the statement hash.

    Domain-separated with a leaf tag (RFC 6962-style) so a leaf can never be
    confused with an interior node. The registration timestamp is deliberately
    NOT part of this preimage, so the leaf and the resulting root are fully
    reproducible.
    """
    payload = (
        b"actproof-scitt-local-leaf\x00"
        + _hex_only(cose_sha256).encode("ascii")
        + b"\x00"
        + _hex_only(statement_hash).encode("ascii")
    )
    return _sha256_hex(payload)


def _node_hash(left: str, right: str) -> str:
    payload = b"actproof-scitt-local-node\x01" + _hex_only(left).encode("ascii") + _hex_only(right).encode("ascii")
    return _sha256_hex(payload)


def _merkle_root(leaves: list[str]) -> str:
    if not leaves:
        return _sha256_hex(b"actproof-scitt-local-empty-log")
    level = list(leaves)
    while len(level) > 1:
        nxt: list[str] = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(_node_hash(left, right))
        level = nxt
    return level[0]


def _inclusion_path(leaves: list[str], index: int) -> list[dict[str, str]]:
    path: list[dict[str, str]] = []
    level = list(leaves)
    idx = index
    while len(level) > 1:
        nxt: list[str] = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(_node_hash(left, right))
        sibling_index = idx ^ 1
        if sibling_index >= len(level):
            sibling_index = idx  # duplicated last node
        side = "right" if (idx % 2 == 0) else "left"
        path.append({"sibling": level[sibling_index], "side": side})
        idx //= 2
        level = nxt
    return path


def _root_from_path(leaf: str, path: list[dict[str, str]]) -> str:
    acc = leaf
    for step in path:
        sibling = step["sibling"]
        if step.get("side") == "right":
            acc = _node_hash(acc, sibling)
        else:
            acc = _node_hash(sibling, acc)
    return acc


# ---------------------------------------------------------------------------
# Commitment extraction (the Profile View Export bridge)
# ---------------------------------------------------------------------------

def _profile_commitments(statement: dict[str, Any]) -> dict[str, Any]:
    return _typed_profile_commitments(statement)


def _source_atom_commitments(statement: dict[str, Any]) -> dict[str, Any]:
    return _typed_source_atom_commitments(statement)


def _policy_digest(statement: dict[str, Any]) -> str:
    """ACTA/ASQAV-aligned policy_digest over the ActProof policy object.

    For a source-atom statement the "policy object" is the maturity + scitt
    binding block: what registration policy ActProof applied to this statement.
    The digest is deterministic over the JCS-canonical policy object.
    """
    policy_object = {
        "maturity": statement.get("maturity") or {},
        "scitt_binding": statement.get("scitt_binding") or {},
        "profile": statement.get("profile"),
    }
    return _sha256_hex(_canonical_bytes(policy_object))


# ---------------------------------------------------------------------------
# Local append-only log
# ---------------------------------------------------------------------------

def init_local_log(log_path: str | Path, *, label: str | None = None) -> dict[str, Any]:
    """Create an empty local SCITT-style append-only log file.

    The log is a single JSON document with an ordered ``entries`` array and a
    running ``log_root``. It is plain JSON so it stays inspectable; the
    append-only discipline is enforced by this module.
    """
    path = Path(log_path)
    if path.exists():
        raise FileExistsError(f"local log already exists: {path}")
    log = {
        "schema": LOCAL_LOG_SCHEMA,
        "label": label or "actproof-local-scitt-pilot-log",
        "package": {"name": "actproof-events", "version": __version__},
        "registration_status": REGISTRATION_STATUS_LOCAL,
        "transparency_service_model": TRANSPARENCY_SERVICE_MODEL,
        "canonicalization": CANONICALIZATION_LABEL,
        "canonicalization_detail": CANONICALIZATION,
        "hash_algorithm": HASH_ALGORITHM,
        "merkle_scheme": "rfc6962-style-sha256-duplicate-last-domain-separated",
        "created_at": _utc_now(),
        "entry_count": 0,
        "entries": [],
        "log_root": _merkle_root([]),
        "non_claims": list(NON_CLAIMS),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(log, path)
    return log


def load_local_log(log_path: str | Path) -> dict[str, Any]:
    log = json.loads(Path(log_path).read_text(encoding="utf-8"))
    if log.get("schema") != LOCAL_LOG_SCHEMA:
        raise ValueError(f"not an actproof local SCITT log: {log.get('schema')}")
    return log


def _recompute_log_root(log: dict[str, Any]) -> str:
    leaves = [e["leaf_hash"] for e in log.get("entries", [])]
    return _merkle_root(leaves)


def register_signed_statement(
    log_path: str | Path,
    *,
    cose_path: str | Path,
    statement: dict[str, Any],
) -> dict[str, Any]:
    """Append a signed supported ActProof statement to the local log and issue a receipt.

    The statement must be a valid typed statement whose ``statement_hash``
    matches its content, and the COSE_Sign1 artifact must carry that same
    statement hash as its payload. The signature itself is verified at
    receipt-verification time, where the relying party supplies the public key.

    Supported statement types include ``actproof/source-atom/v1`` and
    ``actproof/profile-dependency/v1``. Returns the issued local receipt dict.
    """
    errors = validate_statement(statement)
    if errors:
        raise ValueError("invalid statement: " + "; ".join(errors))

    statement_hash = statement.get("statement_hash")
    if statement_hash != compute_statement_hash_for_type(statement):
        raise ValueError("statement_hash does not match statement content")

    cose = load_cose_sign1(cose_path)
    cose_bytes = cose["cose_bytes"]
    cose_sha256 = sha256_bytes(cose_bytes)
    payload = cose["payload"]
    if payload != str(statement_hash).encode("utf-8"):
        raise ValueError("COSE payload does not match statement_hash; sign the statement first")
    kid = (cose["unprotected"].get(COSE_HEADER_KID) or b"").decode("utf-8", errors="replace")

    log = load_local_log(log_path)
    if log.get("log_root") != _recompute_log_root(log):
        raise ValueError("local log root does not match its entries; log is inconsistent")

    index = int(log.get("entry_count", 0))
    leaf = _leaf_hash(cose_sha256, str(statement_hash))
    registration_time = _utc_now()

    # ACTA/ASQAV-aligned per-entry hash chain. previous_receipt_hash links to
    # the prior entry's receipt_hash; genesis is the all-zero sentinel.
    prior_entries = log.get("entries") or []
    previous_receipt_hash = (
        prior_entries[-1].get("receipt_hash") if prior_entries else GENESIS_PREVIOUS_RECEIPT_HASH
    )

    profile_commitments = _profile_commitments(statement)
    source_atom_commitments = _source_atom_commitments(statement)
    policy_digest = _policy_digest(statement)
    subject = _typed_statement_subject(statement)
    statement_ref = str(statement_hash)

    entry = {
        "schema": LOCAL_LOG_ENTRY_SCHEMA,
        "log_index": index,
        "leaf_hash": leaf,
        "statement_ref": statement_ref,
        "statement_hash": statement_hash,
        "cose_sha256": cose_sha256,
        "kid": kid,
        "registration_time": registration_time,
        "registration_time_semantics": "timestamp_when_local_transparency_pilot_added_signed_statement_to_log",
        "previous_receipt_hash": previous_receipt_hash,
        "policy_digest": policy_digest,
        "subject": subject,
        "statement_type": statement.get("statement_type"),
        "profile_commitments": profile_commitments,
        "source_atom_commitments": source_atom_commitments,
        "statement_media_type": SCITT_STATEMENT_MEDIA_TYPE,
    }

    log["entries"].append(entry)
    log["entry_count"] = index + 1
    leaves = [e["leaf_hash"] for e in log["entries"]]
    log["log_root"] = _merkle_root(leaves)
    log["updated_at"] = registration_time

    path = _inclusion_path(leaves, index)
    receipt = {
        "schema": LOCAL_RECEIPT_SCHEMA,
        "package": {"name": "actproof-events", "version": __version__},
        "issuer_model": ISSUER_MODEL,
        "payload_profile_type": statement.get("statement_type") or PAYLOAD_PROFILE_TYPE,
        "registration_status": REGISTRATION_STATUS_LOCAL,
        "receipt_status": RECEIPT_STATUS_LOCAL,
        "transparency_service_model": TRANSPARENCY_SERVICE_MODEL,
        "public_registration_policy": PUBLIC_REGISTRATION_POLICY,
        "statement_media_type": SCITT_STATEMENT_MEDIA_TYPE,
        "receipt_media_type_intended": SCITT_RECEIPT_MEDIA_TYPE,
        "canonicalization": CANONICALIZATION_LABEL,
        "canonicalization_detail": CANONICALIZATION,
        "hash_algorithm": HASH_ALGORITHM,
        "subject": subject,
        "statement_type": statement.get("statement_type"),
        "statement_ref": statement_ref,
        "statement_hash": statement_hash,
        "cose_sha256": cose_sha256,
        "kid": kid,
        "registration_time": registration_time,
        "registration_time_semantics": "timestamp_when_local_transparency_pilot_added_signed_statement_to_log",
        "previous_receipt_hash": previous_receipt_hash,
        "policy_digest": policy_digest,
        "log": {
            "label": log.get("label"),
            "log_index": index,
            "entry_count": log["entry_count"],
            "leaf_hash": leaf,
            "inclusion_path": path,
            "log_root": log["log_root"],
            "merkle_scheme": log.get("merkle_scheme"),
        },
        "profile_commitments": profile_commitments,
        "source_atom_commitments": source_atom_commitments,
        "vocabulary_alignment_note": (
            "statement_ref/policy_digest/previous_receipt_hash/canonicalization are named for "
            "mechanism compatibility with the ACTA/ASQAV signed-action-receipt family; this is "
            "alignment, not conformance. statement_ref refers to an ActProof typed statement, "
            "not an agent action."
        ),
        "non_claims": list(NON_CLAIMS),
    }
    receipt["receipt_hash_basis"] = "sha256 over canonical JSON excluding receipt_hash"
    receipt["receipt_hash"] = compute_receipt_hash(receipt)

    # Record the receipt_hash on the log entry so the next entry can chain to it
    # and an auditor can confirm the receipt belongs to the log.
    entry["receipt_hash"] = receipt["receipt_hash"]
    _write_json(log, log_path)

    return receipt


def compute_receipt_hash(receipt: dict[str, Any]) -> str:
    clone = dict(receipt)
    clone.pop("receipt_hash", None)
    return _sha256_hex(_canonical_bytes(clone))


# ---------------------------------------------------------------------------
# Receipt verification (self-contained; log not required)
# ---------------------------------------------------------------------------

def verify_local_receipt(
    receipt: dict[str, Any],
    *,
    cose_path: str | Path,
    statement: dict[str, Any],
    public_key_path: str | Path,
) -> dict[str, Any]:
    """Verify a local SCITT-style receipt end to end, without the log file.

    Per the SCITT architecture, a Receipt is universally verifiable without
    online access to the Transparency Service, so this function needs only the
    receipt, the COSE bytes, the statement and the issuer public key.

    Checks, in order:
    1. The receipt is well-formed and its ``receipt_hash`` matches its content.
    2. The statement is internally consistent and its hash matches the receipt.
    3. The COSE_Sign1 signature over the statement hash is valid (2.7.0 verifier).
    4. The receipt's ``cose_sha256`` matches the COSE bytes on disk.
    5. The Merkle inclusion path recomputes to the committed ``log_root``.
    6. The receipt's typed commitments equal the commitments inside the signed statement.
    7. The receipt's ``policy_digest`` recomputes from the statement.
    """
    result: dict[str, Any] = {
        "schema": LOCAL_RECEIPT_VERIFICATION_SCHEMA,
        "package": {"name": "actproof-events", "version": __version__},
        "registration_status": REGISTRATION_STATUS_LOCAL,
        "receipt_status": RECEIPT_STATUS_LOCAL,
        "registration_time": receipt.get("registration_time"),
        "checks": {
            "receipt_well_formed": False,
            "receipt_hash_matches": False,
            "statement_hash_matches": False,
            "cose_signature": False,
            "cose_sha256_matches_receipt": False,
            "inclusion_proof_root": False,
            "log_entry_present": False,
            "receipt_profile_commitments": False,
            "receipt_source_atom_commitments": False,
            "policy_digest_matches": False,
        },
        "trust_boundary": (
            "local SCITT-style inclusion proof plus local COSE_Sign1 signature only; "
            "no external transparency-service registration in this release"
        ),
        "non_claims": list(NON_CLAIMS),
    }

    if receipt.get("schema") != LOCAL_RECEIPT_SCHEMA:
        result.update({"ok": False, "reason": "not_a_local_receipt"})
        return result
    result["checks"]["receipt_well_formed"] = True

    if receipt.get("receipt_hash") != compute_receipt_hash(receipt):
        result.update({"ok": False, "reason": "receipt_hash_mismatch"})
        return result
    result["checks"]["receipt_hash_matches"] = True

    statement_errors = validate_statement(statement)
    if statement_errors:
        result.update({"ok": False, "reason": "invalid_statement", "errors": statement_errors})
        return result
    if statement.get("statement_hash") != receipt.get("statement_hash"):
        result.update({"ok": False, "reason": "statement_hash_does_not_match_receipt"})
        return result
    if compute_statement_hash_for_type(statement) != statement.get("statement_hash"):
        result.update({"ok": False, "reason": "statement_hash_does_not_match_content"})
        return result
    result["checks"]["statement_hash_matches"] = True

    cose_verdict = verify_cose_statement(
        cose_path, public_key_path=public_key_path, statement=statement,
        expected_cose_typ=statement.get("statement_type"),
    )
    result["cose_verification"] = {
        "ok": cose_verdict.get("ok"),
        "reason": cose_verdict.get("reason"),
        "signature_valid": cose_verdict.get("signature_valid"),
        "cose_sha256": cose_verdict.get("cose_sha256"),
    }
    if not cose_verdict.get("ok"):
        result.update({"ok": False, "reason": "cose_verification_failed"})
        return result
    result["checks"]["cose_signature"] = True

    if cose_verdict.get("cose_sha256") != receipt.get("cose_sha256"):
        result.update({"ok": False, "reason": "cose_sha256_mismatch"})
        return result
    result["checks"]["cose_sha256_matches_receipt"] = True

    log = receipt.get("log") or {}
    leaf = log.get("leaf_hash")
    expected_leaf = _leaf_hash(str(receipt.get("cose_sha256")), str(receipt.get("statement_hash")))
    if leaf != expected_leaf:
        result.update({"ok": False, "reason": "leaf_hash_mismatch"})
        return result
    result["checks"]["log_entry_present"] = True

    recomputed_root = _root_from_path(leaf, log.get("inclusion_path") or [])
    result["recomputed_log_root"] = recomputed_root
    if recomputed_root != log.get("log_root"):
        result.update({"ok": False, "reason": "inclusion_proof_root_mismatch"})
        return result
    result["checks"]["inclusion_proof_root"] = True

    if _profile_commitments(statement) == (receipt.get("profile_commitments") or {}):
        result["checks"]["receipt_profile_commitments"] = True
    else:
        result.update({"ok": False, "reason": "receipt_profile_commitments_mismatch"})
        return result

    if _source_atom_commitments(statement) == (receipt.get("source_atom_commitments") or {}):
        result["checks"]["receipt_source_atom_commitments"] = True
    else:
        result.update({"ok": False, "reason": "receipt_source_atom_commitments_mismatch"})
        return result

    if _policy_digest(statement) == receipt.get("policy_digest"):
        result["checks"]["policy_digest_matches"] = True
    else:
        result.update({"ok": False, "reason": "policy_digest_mismatch"})
        return result

    result.update({"ok": True, "reason": "local_receipt_verified"})
    return result


def verify_local_receipt_against_log(
    receipt: dict[str, Any],
    *,
    log_path: str | Path,
) -> dict[str, Any]:
    """Optional auditor cross-check: confirm the receipt's leaf is in the log.

    Receipt verification proper (verify_local_receipt) does not need the log;
    this is the separate auditor/replay role described by SCITT. A holder of
    the log can confirm the leaf, the per-entry chain and the committed root
    match the live log state.
    """
    log = load_local_log(log_path)
    live_root = _recompute_log_root(log)
    log_block = receipt.get("log") or {}
    idx = log_block.get("log_index")
    leaf = log_block.get("leaf_hash")
    entries = log.get("entries") or []
    present = isinstance(idx, int) and 0 <= idx < len(entries) and entries[idx].get("leaf_hash") == leaf
    chain_ok = (
        present
        and entries[idx].get("previous_receipt_hash") == receipt.get("previous_receipt_hash")
        and entries[idx].get("receipt_hash") == receipt.get("receipt_hash")
    )
    return {
        "ok": bool(present) and log_block.get("log_root") == live_root and bool(chain_ok),
        "leaf_present_at_index": bool(present),
        "chain_consistent": bool(chain_ok),
        "receipt_log_root": log_block.get("log_root"),
        "live_log_root": live_root,
        "log_root_matches": log_block.get("log_root") == live_root,
    }


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------

def _write_json(value: Any, path: str | Path, *, compact: bool = False) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=False, indent=None if compact else 2) + "\n",
        encoding="utf-8",
    )


def write_json(value: Any, path: str | Path, *, compact: bool = False) -> None:
    _write_json(value, path, compact=compact)


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
