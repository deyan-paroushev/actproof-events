# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Typed ActProof statement profiles used by local receipt registration.

This module keeps statement validation and hash computation separate from the
COSE/log mechanics. The registration layer can then accept more than one
statement type without weakening validation.
"""
from __future__ import annotations

from typing import Any

from actproof_events.scitt_profile import (
    SCITT_SOURCE_ATOM_STATEMENT_TYPE,
    compute_statement_hash as compute_source_atom_statement_hash,
    validate_source_atom_statement,
    canonical_json_sha256,
)

PROFILE_DEPENDENCY_STATEMENT_TYPE = "actproof/profile-dependency/v1"
PROFILE_DEPENDENCY_STATEMENT_SCHEMA = "actproof.profile_dependency_statement.v1"


def compute_profile_dependency_statement_hash(statement: dict[str, Any]) -> str:
    """Hash a profile-dependency statement over canonical JSON.

    Both the common ``statement_hash`` and the legacy/detail
    ``profile_dependency_statement_hash`` field are excluded from the hash basis.
    """
    clone = dict(statement)
    clone.pop("statement_hash", None)
    clone.pop("profile_dependency_statement_hash", None)
    return canonical_json_sha256(clone)


def validate_profile_dependency_statement(statement: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if statement.get("schema") != PROFILE_DEPENDENCY_STATEMENT_SCHEMA:
        errors.append(f"schema must be {PROFILE_DEPENDENCY_STATEMENT_SCHEMA}")
    if statement.get("statement_type") != PROFILE_DEPENDENCY_STATEMENT_TYPE:
        errors.append(f"statement_type must be {PROFILE_DEPENDENCY_STATEMENT_TYPE}")
    if not statement.get("profile_id"):
        errors.append("profile_id is required")
    if not statement.get("profile_version"):
        errors.append("profile_version is required")
    if not isinstance(statement.get("expected_dependencies"), list):
        errors.append("expected_dependencies must be a list")

    envelope = statement.get("dependency_root_envelope")
    dependency_root = statement.get("dependency_root")
    if not isinstance(envelope, dict):
        errors.append("dependency_root_envelope must be an object")
    elif canonical_json_sha256(envelope) != dependency_root:
        errors.append("dependency_root does not match dependency_root_envelope")
    if not (isinstance(dependency_root, str) and dependency_root.startswith("sha256:")):
        errors.append("dependency_root must be a sha256: value")

    stored = statement.get("statement_hash")
    legacy = statement.get("profile_dependency_statement_hash")
    recomputed = compute_profile_dependency_statement_hash(statement)
    if not (isinstance(stored, str) and stored.startswith("sha256:")):
        errors.append("statement_hash must be present")
    elif stored != recomputed:
        errors.append(f"statement_hash mismatch: stored {stored}, recomputed {recomputed}")
    if legacy is not None and legacy != recomputed:
        errors.append("profile_dependency_statement_hash must equal statement_hash when present")
    if not statement.get("non_claims"):
        errors.append("non_claims are required")
    return errors


def compute_statement_hash_for_type(statement: dict[str, Any]) -> str:
    typ = statement.get("statement_type")
    if typ == SCITT_SOURCE_ATOM_STATEMENT_TYPE:
        return compute_source_atom_statement_hash(statement)
    if typ == PROFILE_DEPENDENCY_STATEMENT_TYPE:
        return compute_profile_dependency_statement_hash(statement)
    raise ValueError(f"unsupported statement_type: {typ!r}")


def validate_statement(statement: dict[str, Any]) -> list[str]:
    typ = statement.get("statement_type")
    if typ == SCITT_SOURCE_ATOM_STATEMENT_TYPE:
        return validate_source_atom_statement(statement)
    if typ == PROFILE_DEPENDENCY_STATEMENT_TYPE:
        return validate_profile_dependency_statement(statement)
    return [f"unsupported statement_type: {typ!r}"]


def statement_subject(statement: dict[str, Any]) -> dict[str, Any]:
    typ = statement.get("statement_type")
    if typ == SCITT_SOURCE_ATOM_STATEMENT_TYPE:
        subject = statement.get("subject") or {}
        return {
            "subject_type": "source_atom",
            "act_id": subject.get("act_id"),
            "atom_id": subject.get("atom_id"),
        }
    if typ == PROFILE_DEPENDENCY_STATEMENT_TYPE:
        return {
            "subject_type": "profile_dependency",
            "profile_id": statement.get("profile_id"),
            "profile_version": statement.get("profile_version"),
        }
    return {"subject_type": "unknown"}


def profile_commitments(statement: dict[str, Any]) -> dict[str, Any]:
    typ = statement.get("statement_type")
    if typ == SCITT_SOURCE_ATOM_STATEMENT_TYPE:
        c = statement.get("commitments") or {}
        return {
            "profile_semantic_hash": c.get("profile_semantic_hash"),
            "profile_artifact_hash": c.get("profile_artifact_hash"),
        }
    if typ == PROFILE_DEPENDENCY_STATEMENT_TYPE:
        return {
            "profile_id": statement.get("profile_id"),
            "profile_version": statement.get("profile_version"),
            "dependency_root": statement.get("dependency_root"),
            "profile_dependency_statement_hash": statement.get("statement_hash"),
        }
    return {}


def source_atom_commitments(statement: dict[str, Any]) -> dict[str, Any]:
    if statement.get("statement_type") != SCITT_SOURCE_ATOM_STATEMENT_TYPE:
        return {}
    c = statement.get("commitments") or {}
    return {
        "atom_identity_sha256": c.get("atom_identity_sha256"),
        "canonical_atom_json_sha256": c.get("canonical_atom_json_sha256"),
        "official_text_sha256": c.get("official_text_sha256"),
        "official_text_hash_basis": c.get("official_text_hash_basis"),
        "dependency_root": c.get("dependency_root"),
    }
