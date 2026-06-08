# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""SCITT/COSE-ready source-atom statement profile exports.

The 2.6.0 release does not register atoms with a transparency service and does
not produce production COSE signatures. It defines and validates a conservative
ActProof statement profile that can later be signed as a COSE_Sign1 / SCITT
Signed Statement and registered with a SCITT Transparency Service.

A statement exported by this module proves only this package's deterministic
claim over a source atom and its hashes. It does not prove legal correctness,
compliance, supervisory acceptance, or that the official source itself is true.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from actproof_events import __version__
from actproof_events.exports import build_profile_view
from actproof_events.source_binding import get_source_atom, list_field_derivations, list_source_atoms
from actproof_events.text_capture import verify_atom_official_text

SCITT_SOURCE_ATOM_PROFILE_ID = "actproof.scitt.source_atom_statement.v1"
SCITT_SOURCE_ATOM_STATEMENT_TYPE = "actproof/source-atom/v1"
SCITT_SOURCE_ATOM_STATEMENT_SCHEMA = "actproof.scitt.source_atom_statement.v1"
SCITT_SOURCE_ATOM_MANIFEST_SCHEMA = "actproof.scitt.source_atom_manifest.v1"
CANONICALIZATION = "jcs-rfc8785-compatible-json-sort-keys-compact-v1"
HASH_ALGORITHM = "sha256"
PAYLOAD_MODE = "hash_commitment"
COSE_TYP = "actproof/source-atom/v1"
SCITT_REGISTRATION_STATUS = "not_registered"


NON_CLAIMS = [
    "Statement export does not prove legal correctness.",
    "The official legal source remains the source of law.",
    "The statement does not provide legal advice, compliance certification, bank approval or supervisory approval.",
    "A draft atom statement is a development artifact and should not be treated as a reviewed trust artifact.",
    "SCITT registration, when added later, will prove registration of an issuer statement, not legal truth.",
]


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    """Return sha256 over canonical JSON bytes."""
    return _sha256(value)


def _atom_dependencies(act_id: str, atom_id: str) -> dict[str, Any]:
    used_by_fields: list[str] = []
    used_by_derivations: list[str] = []
    for derivation in list_field_derivations(act_id):
        if atom_id in (derivation.get("source_atoms") or []):
            used_by_fields.append(derivation.get("field_id"))
            used_by_derivations.append(derivation.get("derivation_id") or derivation.get("field_id"))
    used_by_fields = sorted(x for x in set(used_by_fields) if x)
    used_by_derivations = sorted(x for x in set(used_by_derivations) if x)
    payload = {
        "atom_id": atom_id,
        "used_by_fields": used_by_fields,
        "used_by_derivations": used_by_derivations,
    }
    return {
        **payload,
        "dependency_count": len(used_by_fields),
        "dependency_root": _sha256(payload),
    }


def _source_locator(atom: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_system": "EUR-Lex" if atom.get("eli", "").startswith("http://data.europa.eu/eli/") else atom.get("source_id"),
        "source_id": atom.get("source_id"),
        "celex": atom.get("celex"),
        "eli": atom.get("eli"),
        "instrument": atom.get("instrument"),
        "authority": atom.get("authority"),
        "language": atom.get("language") or atom.get("text_language") or "en",
        "source_document_sha256": atom.get("source_document_sha256"),
        "locator": atom.get("locator") or {},
        "text_locator": atom.get("text_locator"),
        "atom_type": atom.get("atom_type"),
        "source_role": atom.get("source_role"),
        "normative_weight": atom.get("normative_weight"),
    }


def build_source_atom_statement(
    act_id: str,
    atom_id: str,
    *,
    issuer_name: str = "ActProof Events",
    issuer_role: str = "profile_maintainer",
    issuer_key_id: str | None = None,
    _profile_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build one ActProof SCITT/COSE-ready source-atom statement.

    The output is JSON and is intentionally not a COSE object yet. It is the
    typed payload that a later release can wrap into COSE_Sign1 and submit to a
    SCITT Transparency Service. ``scitt_registration_status`` is always
    ``not_registered`` in 2.6.0.
    """
    atom = get_source_atom(atom_id, act_id=act_id)
    if _profile_hashes is None:
        profile_view = build_profile_view(act_id, include_fields=False, include_source_basis=True, include_provenance=False)
        _profile_hashes = {
            "profile_semantic_hash": profile_view.get("profile_semantic_hash"),
            "profile_artifact_hash": profile_view.get("profile_artifact_hash"),
        }
    deps = _atom_dependencies(act_id, atom_id)
    atom_payload_hash = canonical_json_sha256(atom)
    text_verdict = verify_atom_official_text(atom) if atom.get("text_excerpt") else {
        "ok": False,
        "atom": atom_id,
        "reason": "no_text_excerpt",
    }
    commitments = {
        "atom_identity_sha256": atom.get("atom_identity_sha256"),
        "canonical_atom_json_sha256": atom_payload_hash,
        "official_text_sha256": atom.get("official_text_sha256"),
        "official_text_hash_basis": atom.get("official_text_hash_basis"),
        "profile_semantic_hash": _profile_hashes.get("profile_semantic_hash"),
        "profile_artifact_hash": _profile_hashes.get("profile_artifact_hash"),
        "dependency_root": deps["dependency_root"],
    }
    statement: dict[str, Any] = {
        "schema": SCITT_SOURCE_ATOM_STATEMENT_SCHEMA,
        "statement_type": SCITT_SOURCE_ATOM_STATEMENT_TYPE,
        "profile": SCITT_SOURCE_ATOM_PROFILE_ID,
        "package": {"name": "actproof-events", "version": __version__},
        "issuer": {
            "issuer_name": issuer_name,
            "issuer_role": issuer_role,
            "issuer_key_id": issuer_key_id,
        },
        "subject": {
            "subject_type": "source_atom",
            "act_id": act_id,
            "atom_id": atom_id,
            "jurisdiction": "EU" if str(atom.get("celex") or "").startswith("3") else None,
            **_source_locator(atom),
        },
        "commitments": commitments,
        "maturity": {
            "binding_status": atom.get("binding_status", "provisional"),
            "review_status": atom.get("review_status", "draft"),
            "text_capture_status": atom.get("text_capture_status", "not_captured"),
            "text_review_status": atom.get("text_review_status", atom.get("review_status", "draft")),
            "registration_recommendation": (
                "do_not_register_publicly_until_reviewed"
                if atom.get("review_status", "draft") == "draft"
                else "eligible_for_policy_controlled_registration"
            ),
        },
        "dependencies": deps,
        "verification": {
            "canonicalization": CANONICALIZATION,
            "hash_algorithm": HASH_ALGORITHM,
            "payload_mode": PAYLOAD_MODE,
            "cose_typ": COSE_TYP,
            "cose_status": "profile_defined_not_signed",
            "scitt_registration_status": SCITT_REGISTRATION_STATUS,
            "scitt_receipt_status": "no_receipt_in_2_6_0",
            "official_text_verification": text_verdict,
        },
        "future_scitt_mapping": {
            "issuer": "issuer of the future COSE/SCITT Signed Statement",
            "statement": "this JSON payload or a hash envelope over its canonical hash",
            "subject": "source atom and official-source locator",
            "transparency_service": "SCITT Transparency Service selected by relying party or deployment",
            "receipt": "future verifiable registration proof; not produced in 2.6.0",
            "relying_party": "bank, reviewer, auditor, agent, GRC system or regulator verifying the statement and receipt",
        },
        "non_claims": list(NON_CLAIMS),
    }
    statement["statement_hash_basis"] = "sha256 over canonical JSON excluding statement_hash"
    statement["statement_hash"] = compute_statement_hash(statement)
    return statement


def compute_statement_hash(statement: dict[str, Any]) -> str:
    # Note: the statement embeds package version and profile_semantic_hash, so
    # this hash is OF a package version and profile state. It is a stable
    # commitment surface for signing/registration within a version, not a
    # cross-version permanent anchor. The atom's own atom_identity_sha256 /
    # official_text_sha256 are the durable per-atom anchors.
    clone = dict(statement)
    clone.pop("statement_hash", None)
    return _sha256(clone)


def validate_source_atom_statement(statement: dict[str, Any]) -> list[str]:
    """Validate the internal consistency of one source-atom statement."""
    errors: list[str] = []
    if statement.get("schema") != SCITT_SOURCE_ATOM_STATEMENT_SCHEMA:
        errors.append(f"schema must be {SCITT_SOURCE_ATOM_STATEMENT_SCHEMA}")
    if statement.get("statement_type") != SCITT_SOURCE_ATOM_STATEMENT_TYPE:
        errors.append(f"statement_type must be {SCITT_SOURCE_ATOM_STATEMENT_TYPE}")
    subject = statement.get("subject") or {}
    commitments = statement.get("commitments") or {}
    verification = statement.get("verification") or {}
    maturity = statement.get("maturity") or {}
    if not subject.get("act_id"):
        errors.append("subject.act_id is required")
    if not subject.get("atom_id"):
        errors.append("subject.atom_id is required")
    for key in ["atom_identity_sha256", "canonical_atom_json_sha256", "profile_semantic_hash", "dependency_root"]:
        val = commitments.get(key)
        if not (isinstance(val, str) and val.startswith("sha256:")):
            errors.append(f"commitments.{key} must be a sha256: value")
    if commitments.get("official_text_sha256") is not None and not str(commitments.get("official_text_sha256")).startswith("sha256:"):
        errors.append("commitments.official_text_sha256 must be null or sha256:")
    if verification.get("scitt_registration_status") != SCITT_REGISTRATION_STATUS:
        errors.append("2.6.0 statements must carry scitt_registration_status=not_registered")
    if verification.get("cose_status") != "profile_defined_not_signed":
        errors.append("2.6.0 statements must carry cose_status=profile_defined_not_signed")
    if maturity.get("review_status") == "draft" and maturity.get("registration_recommendation") != "do_not_register_publicly_until_reviewed":
        errors.append("draft statements must recommend against public registration until reviewed")
    stored = statement.get("statement_hash")
    if not (isinstance(stored, str) and stored.startswith("sha256:")):
        errors.append("statement_hash must be present")
    else:
        recomputed = compute_statement_hash(statement)
        if recomputed != stored:
            errors.append(f"statement_hash mismatch: stored {stored}, recomputed {recomputed}")
    if not statement.get("non_claims"):
        errors.append("non_claims are required")
    return errors


def verify_source_atom_statement(statement: dict[str, Any], act_id: str | None = None) -> dict[str, Any]:
    """Verify a statement against the LIVE atom it commits to.

    This is distinct from validate_source_atom_statement, which only checks the
    statement is internally consistent (its hashes match itself). This function
    recomputes the committed hashes from the current atom in the package and
    confirms the statement still matches it, catching drift between a saved
    statement and an evolving atom. That is what makes a statement verifiable
    rather than merely well-formed. Returns a verdict dict.
    """
    subject = statement.get("subject") or {}
    aid = subject.get("atom_id")
    act = act_id or subject.get("act_id")
    if not aid or not act:
        return {"ok": False, "reason": "statement_missing_atom_or_act_id"}
    atoms = {a["source_atom_id"]: a for a in list_source_atoms(act)}
    atom = atoms.get(aid)
    if atom is None:
        return {"ok": False, "atom": aid, "reason": "atom_not_found_in_profile"}

    committed = statement.get("commitments") or {}
    checks = {
        "atom_identity_sha256": (
            committed.get("atom_identity_sha256"),
            atom.get("atom_identity_sha256"),
        ),
        "canonical_atom_json_sha256": (
            committed.get("canonical_atom_json_sha256"),
            canonical_json_sha256(atom),
        ),
        "official_text_sha256": (
            committed.get("official_text_sha256"),
            atom.get("official_text_sha256"),
        ),
    }
    mismatches = {
        k: {"committed": c, "recomputed": r}
        for k, (c, r) in checks.items()
        if c != r
    }
    ok = not mismatches
    return {
        "ok": ok,
        "atom": aid,
        "reason": "match" if ok else "hash_mismatch",
        "mismatches": mismatches,
    }


def build_source_atom_manifest(act_id: str) -> dict[str, Any]:
    """Build a manifest of SCITT/COSE-ready statements for all atoms in a profile."""
    profile_view = build_profile_view(act_id, include_fields=False, include_source_basis=True, include_provenance=False)
    profile_hashes = {
        "profile_semantic_hash": profile_view.get("profile_semantic_hash"),
        "profile_artifact_hash": profile_view.get("profile_artifact_hash"),
    }
    statements = [
        build_source_atom_statement(act_id, atom["source_atom_id"], _profile_hashes=profile_hashes)
        for atom in list_source_atoms(act_id)
    ]
    entries = [
        {
            "atom_id": s["subject"]["atom_id"],
            "statement_type": s["statement_type"],
            "statement_hash": s["statement_hash"],
            "atom_identity_sha256": s["commitments"].get("atom_identity_sha256"),
            "canonical_atom_json_sha256": s["commitments"].get("canonical_atom_json_sha256"),
            "official_text_sha256": s["commitments"].get("official_text_sha256"),
            "review_status": s["maturity"].get("review_status"),
            "text_capture_status": s["maturity"].get("text_capture_status"),
            "scitt_registration_status": s["verification"].get("scitt_registration_status"),
        }
        for s in statements
    ]
    root_payload = {"act_id": act_id, "entries": entries}
    manifest = {
        "schema": SCITT_SOURCE_ATOM_MANIFEST_SCHEMA,
        "profile": SCITT_SOURCE_ATOM_PROFILE_ID,
        "act_id": act_id,
        "package": {"name": "actproof-events", "version": __version__},
        "statement_type": SCITT_SOURCE_ATOM_STATEMENT_TYPE,
        "statement_count": len(entries),
        "entries": entries,
        "manifest_root_hash_basis": "sha256 over canonical JSON of act_id + entries",
        "manifest_root_hash": _sha256(root_payload),
        "scitt_registration_status": SCITT_REGISTRATION_STATUS,
        "boundary": "2.6.0 defines statement payloads and hashes only. It does not create COSE signatures, SCITT receipts or transparency-service registrations.",
        "non_claims": list(NON_CLAIMS),
    }
    manifest["manifest_hash_basis"] = "sha256 over canonical JSON excluding manifest_hash"
    manifest["manifest_hash"] = compute_manifest_hash(manifest)
    return manifest


def compute_manifest_hash(manifest: dict[str, Any]) -> str:
    clone = dict(manifest)
    clone.pop("manifest_hash", None)
    return _sha256(clone)


def validate_source_atom_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema") != SCITT_SOURCE_ATOM_MANIFEST_SCHEMA:
        errors.append(f"schema must be {SCITT_SOURCE_ATOM_MANIFEST_SCHEMA}")
    if manifest.get("statement_type") != SCITT_SOURCE_ATOM_STATEMENT_TYPE:
        errors.append(f"statement_type must be {SCITT_SOURCE_ATOM_STATEMENT_TYPE}")
    entries = manifest.get("entries") or []
    if manifest.get("statement_count") != len(entries):
        errors.append("statement_count does not match entries length")
    for i, e in enumerate(entries):
        if not e.get("atom_id"):
            errors.append(f"entries[{i}].atom_id is required")
        for key in ["statement_hash", "atom_identity_sha256", "canonical_atom_json_sha256"]:
            if not (isinstance(e.get(key), str) and e.get(key).startswith("sha256:")):
                errors.append(f"entries[{i}].{key} must be sha256:")
        if e.get("scitt_registration_status") != SCITT_REGISTRATION_STATUS:
            errors.append(f"entries[{i}].scitt_registration_status must be not_registered")
    root_payload = {"act_id": manifest.get("act_id"), "entries": entries}
    if manifest.get("manifest_root_hash") != _sha256(root_payload):
        errors.append("manifest_root_hash mismatch")
    if manifest.get("manifest_hash") != compute_manifest_hash(manifest):
        errors.append("manifest_hash mismatch")
    return errors


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(payload: dict[str, Any], out: str | Path, *, compact: bool = False) -> dict[str, Any]:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=False, indent=None if compact else 2) + "\n",
        encoding="utf-8",
    )
    return payload
