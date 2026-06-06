# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Field-level source binding for ActProof regulatory profiles.

The source-binding layer is deliberately separate from the canonical catalogue
entry. Catalogue entries remain the canonical profile objects; source atoms and
field derivations are a reviewable read layer that explains why a generated
profile field exists, which official-source units it depends on, and where
interpretation entered.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from actproof_events import (
    get_field_derivations_schema_path,
    get_source_atoms_schema_path,
    get_source_bindings_path,
)
from actproof_events.services import BOUNDARY, BOUNDARY_ID, get_profile, list_fields

SOURCE_ATOMS_SCHEMA_ID = "actproof.source_atoms.v1"
FIELD_DERIVATIONS_SCHEMA_ID = "actproof.field_derivations.v1"

_DORA_ACT_ID = "op:eu.dora.ict_incident_notification_initial.v1"
_DORA_STEM = "ict_incident_notification_initial.v1"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _source_bindings_root() -> Path:
    return get_source_bindings_path()


def _profile_paths(act_id: str) -> tuple[Path, Path]:
    if act_id != _DORA_ACT_ID:
        # 1.8.0 only ships field-level bindings for this DORA profile. The
        # function is still shaped for future profiles so callers get a clear
        # empty result rather than a hard-coded DORA-only API.
        return (Path("__missing__"), Path("__missing__"))
    root = _source_bindings_root() / "eu" / "dora"
    return (
        root / f"{_DORA_STEM}.source_atoms.json",
        root / f"{_DORA_STEM}.field_derivations.json",
    )


@lru_cache(maxsize=None)
def _source_atom_document(act_id: str) -> dict[str, Any]:
    atoms_path, _ = _profile_paths(act_id)
    if not atoms_path.exists():
        return {"schema": SOURCE_ATOMS_SCHEMA_ID, "profile_id": act_id, "source_atoms": []}
    doc = _load_json(atoms_path)
    if doc.get("schema") != SOURCE_ATOMS_SCHEMA_ID:
        raise ValueError(f"{atoms_path}: expected schema {SOURCE_ATOMS_SCHEMA_ID}")
    return doc


@lru_cache(maxsize=None)
def _field_derivation_document(act_id: str) -> dict[str, Any]:
    _, derivations_path = _profile_paths(act_id)
    if not derivations_path.exists():
        return {"schema": FIELD_DERIVATIONS_SCHEMA_ID, "profile_id": act_id, "field_derivations": []}
    doc = _load_json(derivations_path)
    if doc.get("schema") != FIELD_DERIVATIONS_SCHEMA_ID:
        raise ValueError(f"{derivations_path}: expected schema {FIELD_DERIVATIONS_SCHEMA_ID}")
    return doc


def get_source_atoms_schema() -> dict[str, Any]:
    """Load the packaged source-atoms JSON Schema."""
    return _load_json(get_source_atoms_schema_path())


def get_field_derivations_schema() -> dict[str, Any]:
    """Load the packaged field-derivations JSON Schema."""
    return _load_json(get_field_derivations_schema_path())


def list_source_atoms(act_id: str) -> list[dict[str, Any]]:
    """Return all source atoms shipped for a profile."""
    return [dict(a) for a in _source_atom_document(act_id).get("source_atoms", [])]


def source_atom_index(act_id: str) -> dict[str, dict[str, Any]]:
    """Return source atoms keyed by ``source_atom_id``."""
    return {a["source_atom_id"]: a for a in list_source_atoms(act_id)}


def get_source_atom(source_atom_id: str, *, act_id: str = _DORA_ACT_ID) -> dict[str, Any]:
    """Return one source atom by id."""
    index = source_atom_index(act_id)
    if source_atom_id not in index:
        raise KeyError(f"Unknown source atom {source_atom_id!r} for {act_id!r}")
    return dict(index[source_atom_id])


def list_field_derivations(act_id: str) -> list[dict[str, Any]]:
    """Return all field derivations shipped for a profile."""
    return [dict(d) for d in _field_derivation_document(act_id).get("field_derivations", [])]


def field_derivation_index(act_id: str) -> dict[str, dict[str, Any]]:
    """Return field derivations keyed by field id."""
    return {d["field_id"]: d for d in list_field_derivations(act_id)}


def get_field_derivation(act_id: str, field_id: str) -> dict[str, Any]:
    """Return the reviewable derivation for one field."""
    index = field_derivation_index(act_id)
    if field_id not in index:
        raise KeyError(f"No field-level derivation for {act_id!r} / {field_id!r}")
    return dict(index[field_id])


_IDENTITY_HASH_FIELDS = (
    "source_atom_id",
    "celex",
    "eli",
    "atom_type",
    "locator",
    "source_role",
    "normative_weight",
    "source_document_sha256",
    "derivation_note",
)


def compute_source_atom_identity_hash(atom: dict[str, Any]) -> str:
    """Recompute an atom's identity hash from a fixed, canonical basis.

    The hash is taken over a deterministic JSON serialisation (sorted keys,
    compact separators) of a fixed subset of identity-bearing fields. It is an
    identity hash over the ActProof binding's stable identifiers and locator —
    NOT a hash of official legal text (see official_text_sha256 for that). The
    point of defining it here is that the shipped hash is reproducible by anyone
    running this function, so the verifier can check it rather than trust it.
    """
    basis = {k: atom.get(k) for k in _IDENTITY_HASH_FIELDS}
    payload = json.dumps(basis, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def verify_source_atom_identity_hash(atom: dict[str, Any]) -> bool:
    """True iff the atom's stored atom_identity_sha256 matches the recompute."""
    stored = atom.get("atom_identity_sha256")
    return bool(stored) and stored == compute_source_atom_identity_hash(atom)


def _source_atom_summary(atom: dict[str, Any]) -> dict[str, Any]:
    """Small source-atom projection embedded into profile-view field rows."""
    return {
        "source_atom_id": atom["source_atom_id"],
        "source_binding_id": atom["source_binding_id"],
        "source_id": atom["source_id"],
        "celex": atom["celex"],
        "eli": atom["eli"],
        "instrument": atom["instrument"],
        "atom_type": atom["atom_type"],
        "locator": atom["locator"],
        "source_role": atom["source_role"],
        "normative_weight": atom["normative_weight"],
        "source_document_sha256": atom["source_document_sha256"],
        "atom_identity_sha256": atom["atom_identity_sha256"],
        "official_text_sha256": atom.get("official_text_sha256"),
        "binding_status": atom.get("binding_status", "provisional"),
        "review_status": atom["review_status"],
    }


def explain_field_source(act_id: str, field_id: str) -> dict[str, Any]:
    """Explain where a profile field comes from.

    The function returns a field-level source explanation if the profile ships a
    derivation for the field. If not, the caller receives an act-level fallback
    marker. The fallback is explicit so consumers never mistake a broad source
    basis for a clause-level binding.
    """
    derivations = field_derivation_index(act_id)
    if field_id not in derivations:
        return {
            "act_id": act_id,
            "field_id": field_id,
            "source_basis_scope": "act",
            "fallback_used": True,
            "source_atoms": [],
            "field_derivation": None,
            "boundary": BOUNDARY,
            "boundary_id": BOUNDARY_ID,
        }

    derivation = dict(derivations[field_id])
    atoms = source_atom_index(act_id)
    source_atom_ids = list(derivation.get("source_atoms") or [])
    expanded = [_source_atom_summary(atoms[a]) for a in source_atom_ids if a in atoms]

    # The two stored facts.
    binding_granularity = derivation.get("binding_granularity", "obligation_context")
    release_scope = derivation.get("release_scope", "experimental_optional")
    # The conclusions — COMPUTED from those two facts, never stored, so the
    # data carries one source of truth per fact and these cannot drift.
    is_required_scope = release_scope == "required_release_scope"
    is_template_cell = binding_granularity == "template_field"
    counts_toward_required_release_gate = is_required_scope and is_template_cell
    counts_toward_field_level_coverage = is_template_cell

    # field_binding_status — a computed one-word summary of how firmly this field
    # is bound to official text. Derived from the atoms' binding_status and
    # whether an official_text_sha256 is present; never stored.
    atom_objs = [atoms[a] for a in source_atom_ids if a in atoms]
    any_text_hash = any(a.get("official_text_sha256") for a in atom_objs)
    all_verified = atom_objs and all(a.get("binding_status") == "verified" for a in atom_objs)
    if all_verified and any_text_hash:
        field_binding_status = "text_verified"
    elif atom_objs:
        # ELI locator + pinned-PDF hash present, official text hash pending
        field_binding_status = "provisional_locator_bound"
    else:
        field_binding_status = "unbound"

    return {
        "act_id": act_id,
        "field_id": field_id,
        "source_basis_scope": "field",
        "fallback_used": False,
        "binding_granularity": binding_granularity,
        "release_scope": release_scope,
        "field_binding_status": field_binding_status,
        "counts_toward_required_release_gate": counts_toward_required_release_gate,
        "counts_toward_field_level_coverage": counts_toward_field_level_coverage,
        "source_atoms": source_atom_ids,
        "source_basis": expanded,
        "field_derivation": {
            "derivation_type": derivation["derivation_type"],
            "mapping_confidence": derivation["mapping_confidence"],
            "interpretive_load": derivation["interpretive_load"],
            "binding_granularity": binding_granularity,
            "release_scope": release_scope,
            "field_binding_status": field_binding_status,
            "derivation_note": derivation["derivation_note"],
            "non_claims": list(derivation.get("non_claims") or []),
        },
        "boundary": BOUNDARY,
        "boundary_id": BOUNDARY_ID,
    }


def field_source_projection(act_id: str, field_id: str) -> dict[str, Any] | None:
    """Return fields to merge into a profile-view field row, if field-bound."""
    explanation = explain_field_source(act_id, field_id)
    if explanation["fallback_used"]:
        return None
    return {
        "source_basis_scope": "field",
        "fallback_used": False,
        "binding_granularity": explanation["binding_granularity"],
        "release_scope": explanation["release_scope"],
        "field_binding_status": explanation["field_binding_status"],
        "counts_toward_required_release_gate": explanation["counts_toward_required_release_gate"],
        "counts_toward_field_level_coverage": explanation["counts_toward_field_level_coverage"],
        "source_atoms": explanation["source_atoms"],
        "source_basis": explanation["source_basis"],
        "field_derivation": explanation["field_derivation"],
    }


def compute_field_source_coverage(act_id: str) -> dict[str, Any]:
    """Compute field-source coverage independently of the exporter.

    Precision tiers and required/optional/template-cell conclusions are all
    DERIVED here from the two stored facts on each derivation
    (``binding_granularity`` and ``release_scope``). Nothing about coverage is
    stored per-derivation; the source of truth stays minimal and the
    conclusions are computed, so the two can never drift apart.
    """
    fields = list_fields(act_id, required_only=False)
    derivations = field_derivation_index(act_id)
    total = len(fields)
    required_fields = [f for f in fields if f.get("required")]
    required_total = len(required_fields)
    contextual_field_level = sum(1 for f in fields if f["field_id"] in derivations)
    required_field_level = sum(1 for f in required_fields if f["field_id"] in derivations)
    pct = lambda n, d: round((n / d) * 100, 1) if d else 0.0

    # Derive precision tiers from binding_granularity on each derivation.
    def gran(field_id: str) -> str:
        d = derivations.get(field_id)
        if not d:
            return "act_fallback"
        return d.get("binding_granularity", "obligation_context")

    precision: dict[str, int] = {}
    for f in fields:
        precision[gran(f["field_id"])] = precision.get(gran(f["field_id"]), 0) + 1

    # Required fields bound specifically at template-cell precision (the claim).
    required_template_cell = sum(
        1 for f in required_fields if gran(f["field_id"]) == "template_field"
    )
    # Optional fields and their (lower) precision, derived not stored.
    optional_fields = [f for f in fields if not f.get("required")]
    optional_template_cell = sum(
        1 for f in optional_fields if gran(f["field_id"]) == "template_field"
    )
    optional_field_level = sum(
        1 for f in optional_fields if f["field_id"] in derivations
    )
    release_gated_field_level = required_template_cell
    contextual_not_release_gated = contextual_field_level - release_gated_field_level

    return {
        "field_source_basis": {
            # Market-facing meaning: release-gated, template-field precision.
            # Optional contextual derivations are useful and exported, but are
            # deliberately NOT counted as equivalent to required template-cell
            # source binding.
            "field_level": release_gated_field_level,
            "contextual_field_level": contextual_not_release_gated,
            "act_level_fallback": total - contextual_field_level,
            "fallback_used": total - contextual_field_level,
            "coverage_ratio": pct(release_gated_field_level, total),
            "coverage_basis": "release_gated_template_field_bindings",
            "by_scope": {
                "field_template": release_gated_field_level,
                "field_contextual": contextual_not_release_gated,
                "act": total - contextual_field_level,
            },
        },
        "required_field_source_basis": {
            "required_total": required_total,
            "field_level": required_field_level,
            "template_cell_bound": required_template_cell,
            "fallback_used": required_total - required_field_level,
            "coverage_ratio": pct(required_template_cell, required_total),
            "coverage_basis": "required_template_field_bindings",
        },
        "optional_field_source_basis": {
            "optional_total": len(optional_fields),
            "field_level": optional_field_level,
            "template_cell_bound": optional_template_cell,
            "section_or_obligation_bound": optional_field_level - optional_template_cell,
            "act_level_fallback": len(optional_fields) - optional_field_level,
            "coverage_ratio": pct(optional_template_cell, len(optional_fields)),
            "coverage_basis": "optional_template_field_bindings_only",
            "release_scope": "experimental_optional",
        },
        # Precision-tiered coverage: the honest gradient. Derived from
        # binding_granularity; a template_field binding is never counted the
        # same as a section or obligation binding. Three headline tiers.
        "source_binding_precision": {
            "template_field": precision.get("template_field", 0),
            "template_section": precision.get("template_section", 0),
            "obligation_context": precision.get("obligation_context", 0),
            "act_fallback": precision.get("act_fallback", 0),
        },
    }


def compute_source_atom_coverage(act_id: str) -> dict[str, Any]:
    """Compute coverage from the SOURCE side: which atoms feed a field.

    The field-side coverage (``compute_field_source_coverage``) answers
    "how many fields are bound?". This answers the inverse and more honest
    question for missingness: "is there a source provision we recorded as an
    atom that NO field yet represents?". An unused atom is not a bug — it is a
    signal that a provision is captured but not yet surfaced as a field, which
    is exactly what a reviewer checking for gaps wants to see.

    Everything here is derived from the stored ``source_atoms`` references on
    each derivation; nothing is stored per-atom.
    """
    atoms = list_source_atoms(act_id)
    atom_ids = {a["source_atom_id"] for a in atoms}
    derivations = list_field_derivations(act_id)

    used: set[str] = set()
    required_used: set[str] = set()
    for d in derivations:
        refs = set(d.get("source_atoms", []))
        used |= refs
        if d.get("required"):
            required_used |= refs

    used_existing = used & atom_ids
    unused = sorted(atom_ids - used)
    only_contextual = sorted((used_existing - required_used))
    dangling = sorted(used - atom_ids)  # refs to atoms that do not exist

    return {
        "total_source_atoms": len(atom_ids),
        "atoms_used_by_fields": len(used_existing),
        "unused_source_atoms": len(unused),
        "unused_source_atom_ids": unused,
        "atoms_with_required_field_bindings": len(required_used & atom_ids),
        "atoms_only_in_contextual_bindings": len(only_contextual),
        "atoms_only_in_contextual_binding_ids": only_contextual,
        "dangling_atom_references": len(dangling),
        "dangling_atom_reference_ids": dangling,
        "coverage_basis": "atoms_referenced_by_at_least_one_field_derivation",
        "interpretation_note": (
            "An unused source atom means a recorded provision is not yet "
            "represented by any field. It is a gap signal for review, not a "
            "defect. This coverage does not prove the atom set itself is "
            "exhaustive of the underlying instruments."
        ),
    }


def get_profile_completeness(act_id: str) -> dict[str, Any]:
    """Return the profile's explicit completeness / known-scope declaration.

    Read from the field-derivations document's ``completeness`` block when
    present; otherwise a conservative default that does NOT claim exhaustiveness.
    This exists so the profile never implies "if it is not here, it does not
    matter": it names what the profile models and what it does not.
    """
    doc = _field_derivation_document(act_id)
    declared = doc.get("completeness")
    if declared:
        return declared
    return {
        "completeness_status": "candidate",
        "review_status": doc.get("review_status", "draft"),
        "known_scope": "Fields modelled in this profile only.",
        "not_exhaustive_of": [
            "provisions of the underlying instruments not yet recorded as atoms",
            "report stages or portals outside this profile's scope",
            "future supervisory guidance or Q&A",
        ],
        "field_id_policy": {
            "universal_claim": False,
            "note": (
                "Field IDs are stable identifiers within this ActProof profile, "
                "not universal market field names. Align external systems by "
                "source atom, template locator, required status, data type and "
                "evidence expectation \u2014 not by field name alone."
            ),
        },
        "challenge_allowed": True,
        "challenge_types": [
            "missing_field",
            "wrong_source_atom",
            "weak_derivation",
            "incorrect_required_status",
            "outdated_source",
            "ambiguous_mapping",
        ],
        "challenge_channel": "https://github.com/deyan-paroushev/actproof-events/issues",
    }


def validate_field_source_bindings(act_id: str) -> list[str]:
    """Validate the field-level source-binding contract for a profile.

    Returns human-readable errors. An empty list means the shipped source atoms
    and field derivations are internally consistent and all required fields are
    bound at field level.
    """
    errors: list[str] = []
    profile = get_profile(act_id)
    known_binding_ids = {
        src.get("source_binding_id") for src in profile.get("source_bindings") or []
    }
    required = set(profile.get("required_claim_fields") or [])
    all_fields = set((profile.get("required_claim_fields") or []) + (profile.get("optional_claim_fields") or []))
    atoms = source_atom_index(act_id)
    derivations = field_derivation_index(act_id)

    missing_required = sorted(required - set(derivations))
    for field_id in missing_required:
        errors.append(f"required field {field_id!r} has no field-level derivation")

    unknown_fields = sorted(set(derivations) - all_fields)
    for field_id in unknown_fields:
        errors.append(f"derivation references unknown field {field_id!r}")

    for atom_id, atom in atoms.items():
        if atom.get("source_binding_id") not in known_binding_ids:
            errors.append(f"source atom {atom_id!r} references unknown source_binding_id {atom.get('source_binding_id')!r}")
        for key in ("celex", "eli", "source_document_sha256", "atom_identity_sha256"):
            if not atom.get(key):
                errors.append(f"source atom {atom_id!r} is missing {key}")
        if not str(atom.get("source_document_sha256", "")).startswith("sha256:"):
            errors.append(f"source atom {atom_id!r} has invalid source_document_sha256")
        if not str(atom.get("atom_identity_sha256", "")).startswith("sha256:"):
            errors.append(f"source atom {atom_id!r} has invalid atom_identity_sha256")
        # Recompute check: a shipped sha256-looking field must be reproducible,
        # not merely asserted. This is the 1.8.0 credibility gate.
        elif not verify_source_atom_identity_hash(atom):
            errors.append(
                f"source atom {atom_id!r} atom_identity_sha256 does not match recompute "
                f"(expected {compute_source_atom_identity_hash(atom)})"
            )

    for field_id, derivation in derivations.items():
        ids = list(derivation.get("source_atoms") or [])
        if not ids:
            errors.append(f"derivation for {field_id!r} has no source atoms")
        for atom_id in ids:
            if atom_id not in atoms:
                errors.append(f"derivation for {field_id!r} references missing source atom {atom_id!r}")
        if derivation.get("required") and field_id not in required:
            errors.append(f"derivation for {field_id!r} is marked required but profile does not mark it required")

    coverage = compute_field_source_coverage(act_id)
    req = coverage["required_field_source_basis"]
    if req["coverage_ratio"] < 100.0:
        errors.append(f"required field-level coverage is {req['coverage_ratio']}%, expected 100.0%")
    return errors


__all__ = [
    "SOURCE_ATOMS_SCHEMA_ID",
    "FIELD_DERIVATIONS_SCHEMA_ID",
    "get_source_atoms_schema",
    "get_field_derivations_schema",
    "list_source_atoms",
    "get_source_atom",
    "list_field_derivations",
    "get_field_derivation",
    "explain_field_source",
    "field_source_projection",
    "compute_field_source_coverage",
    "validate_field_source_bindings",
]
