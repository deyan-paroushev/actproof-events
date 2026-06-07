# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Profile diff and change-control helpers for ActProof profile-view JSON.

This module compares two exported ActProof profile-view objects. It is designed
for bank/change-control workflows: the output is a deterministic, reviewable
change report that names semantic-hash changes, added/removed/changed fields,
source-basis changes, review-status changes and coverage changes.

It does not decide whether a change is legally material. It surfaces the exact
places that require human review before a changed profile is relied upon.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from actproof_events import __version__

PROFILE_DIFF_SCHEMA_ID = "actproof.profile_diff.v1"

_VOLATILE_TOP_LEVEL_KEYS = {
    "profile_artifact_hash",
    "profile_view_hash",
}
_VOLATILE_PROVENANCE_KEYS = {
    "generated_at",
    "generator_runtime",
}

_FIELD_CHANGE_KEYS = [
    "required",
    "display_label",
    "rationale",
    "mapping_type",
    "interpretive_status",
    "interpretive_load",
    "disclosure_tier",
    "evidence_labels",
    "evidence_scope",
    "source_basis_scope",
    "fallback_used",
    "binding_granularity",
    "field_binding_status",
    "release_scope",
    "counts_toward_required_release_gate",
    "counts_toward_field_level_coverage",
    "field_derivation",
    "source_atoms",
    "source_basis",
    "boundary",
    "boundary_id",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(obj: Any) -> str:
    """Return a stable SHA-256 hash over JSON-compatible data."""
    return "sha256:" + hashlib.sha256(_stable_json(obj).encode("utf-8")).hexdigest()


def load_profile_view(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("profile-view JSON must be an object")
    if "fields" not in payload or not isinstance(payload["fields"], list):
        raise ValueError("profile-view JSON is missing a fields array")
    return payload


def diff_profile_view_files(
    old_path: str | Path,
    new_path: str | Path,
    *,
    old_label: str | None = None,
    new_label: str | None = None,
) -> dict[str, Any]:
    """Compare two profile-view JSON files and return a change-control report."""
    old = load_profile_view(old_path)
    new = load_profile_view(new_path)
    return diff_profile_views(
        old,
        new,
        old_label=old_label or str(old_path),
        new_label=new_label or str(new_path),
    )


def _field_index(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for f in view.get("fields") or []:
        if not isinstance(f, dict):
            continue
        fid = f.get("field_id")
        if isinstance(fid, str) and fid:
            out[fid] = f
    return out


def _extract_review_status_from_field(field: dict[str, Any]) -> Any:
    derivation = field.get("field_derivation") if isinstance(field.get("field_derivation"), dict) else {}
    review_gate = derivation.get("review_gate") if isinstance(derivation.get("review_gate"), dict) else {}
    return {
        "mapping_confidence": derivation.get("mapping_confidence"),
        "review_status": derivation.get("review_status") or review_gate.get("review_status"),
        "reviewed_by": review_gate.get("reviewed_by"),
        "reviewed_at": review_gate.get("reviewed_at"),
    }


def _normalised_field(field: dict[str, Any]) -> dict[str, Any]:
    return {k: field.get(k) for k in _FIELD_CHANGE_KEYS if k in field}


def _changed_keys(old_field: dict[str, Any], new_field: dict[str, Any]) -> list[str]:
    keys = sorted(set(_FIELD_CHANGE_KEYS) | (set(old_field) & set(new_field)))
    changed: list[str] = []
    for k in keys:
        if k == "field_id":
            continue
        if old_field.get(k) != new_field.get(k):
            changed.append(k)
    return changed


def _source_signature(field: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_atoms": field.get("source_atoms") or [],
        "source_basis_scope": field.get("source_basis_scope"),
        "binding_granularity": field.get("binding_granularity"),
        "source_basis": field.get("source_basis") or [],
        "fallback_used": field.get("fallback_used"),
    }


def _coverage_changes(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    old_cov = old.get("coverage") if isinstance(old.get("coverage"), dict) else {}
    new_cov = new.get("coverage") if isinstance(new.get("coverage"), dict) else {}
    changes: list[dict[str, Any]] = []
    for key in sorted(set(old_cov) | set(new_cov)):
        if old_cov.get(key) != new_cov.get(key):
            changes.append({
                "coverage_key": key,
                "old": old_cov.get(key),
                "new": new_cov.get(key),
            })
    return changes


def _review_status_changes(old: dict[str, Any], new: dict[str, Any], common_ids: set[str]) -> list[dict[str, Any]]:
    old_fields = _field_index(old)
    new_fields = _field_index(new)
    changes: list[dict[str, Any]] = []

    old_comp = old.get("completeness") if isinstance(old.get("completeness"), dict) else {}
    new_comp = new.get("completeness") if isinstance(new.get("completeness"), dict) else {}
    old_profile_review = old_comp.get("review_status")
    new_profile_review = new_comp.get("review_status")
    if old_profile_review != new_profile_review:
        changes.append({
            "scope": "profile",
            "old_review_status": old_profile_review,
            "new_review_status": new_profile_review,
        })

    for fid in sorted(common_ids):
        old_status = _extract_review_status_from_field(old_fields[fid])
        new_status = _extract_review_status_from_field(new_fields[fid])
        if old_status != new_status:
            changes.append({
                "scope": "field",
                "field_id": fid,
                "old": old_status,
                "new": new_status,
            })
    return changes


def diff_profile_views(
    old: dict[str, Any],
    new: dict[str, Any],
    *,
    old_label: str = "old",
    new_label: str = "new",
) -> dict[str, Any]:
    """Compare two profile-view dictionaries.

    The result is intentionally conservative: it identifies change surfaces and
    marks review_required=true. It does not decide whether a change is legally
    material or safe for production use.
    """
    # Refuse to diff two different acts rather than silently comparing them.
    old_act = old.get("act_id")
    new_act = new.get("act_id")
    if old_act and new_act and old_act != new_act:
        return {
            "schema": PROFILE_DIFF_SCHEMA_ID,
            "error": "act_id_mismatch",
            "old_act_id": old_act,
            "new_act_id": new_act,
            "note": (
                "Refusing to diff two different acts. Change control compares "
                "snapshots of the SAME profile across versions."
            ),
        }

    old_fields = _field_index(old)
    new_fields = _field_index(new)
    old_ids = set(old_fields)
    new_ids = set(new_fields)
    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    common = old_ids & new_ids

    changed_fields: list[dict[str, Any]] = []
    source_atom_changes: list[dict[str, Any]] = []

    for fid in sorted(common):
        old_f = old_fields[fid]
        new_f = new_fields[fid]
        changed_keys = _changed_keys(old_f, new_f)
        if changed_keys:
            changed_fields.append({
                "field_id": fid,
                "changed_keys": changed_keys,
                "old_field_hash": stable_hash(_normalised_field(old_f)),
                "new_field_hash": stable_hash(_normalised_field(new_f)),
                "change_review_required": True,
            })
        old_source = _source_signature(old_f)
        new_source = _source_signature(new_f)
        if old_source != new_source:
            source_atom_changes.append({
                "field_id": fid,
                "old_source_signature": old_source,
                "new_source_signature": new_source,
                "change_review_required": True,
            })

    semantic_hash_changed = old.get("profile_semantic_hash") != new.get("profile_semantic_hash")
    artifact_hash_changed = old.get("profile_artifact_hash") != new.get("profile_artifact_hash")
    catalogue_hash_changed = (old.get("profile") or {}).get("catalogue_entry_hash") != (new.get("profile") or {}).get("catalogue_entry_hash")

    coverage = _coverage_changes(old, new)
    review_changes = _review_status_changes(old, new, common)

    summary = {
        "semantic_hash_changed": semantic_hash_changed,
        "artifact_hash_changed": artifact_hash_changed,
        "catalogue_entry_hash_changed": catalogue_hash_changed,
        "fields_added": len(added),
        "fields_removed": len(removed),
        "fields_changed": len(changed_fields),
        "source_atom_changes": len(source_atom_changes),
        "review_status_changes": len(review_changes),
        "coverage_changes": len(coverage),
        "review_required": bool(
            semantic_hash_changed or catalogue_hash_changed or added or removed or changed_fields or source_atom_changes or review_changes or coverage
        ),
    }

    risk_reasons: list[str] = []
    if semantic_hash_changed:
        risk_reasons.append("profile_semantic_hash_changed")
    if added:
        risk_reasons.append("field_added")
    if removed:
        risk_reasons.append("field_removed")
    if changed_fields:
        risk_reasons.append("field_changed")
    if source_atom_changes:
        risk_reasons.append("source_atom_changed")
    if review_changes:
        risk_reasons.append("review_status_changed")
    if coverage:
        risk_reasons.append("coverage_changed")

    return {
        "schema": PROFILE_DIFF_SCHEMA_ID,
        "package": {"name": "actproof-events", "version": __version__},
        "comparison": {
            "old_label": old_label,
            "new_label": new_label,
            "old_profile_semantic_hash": old.get("profile_semantic_hash"),
            "new_profile_semantic_hash": new.get("profile_semantic_hash"),
            "old_profile_artifact_hash": old.get("profile_artifact_hash"),
            "new_profile_artifact_hash": new.get("profile_artifact_hash"),
            "old_package_version": (old.get("provenance") or {}).get("package_version"),
            "new_package_version": (new.get("provenance") or {}).get("package_version"),
        },
        "summary": summary,
        "risk_reasons": risk_reasons,
        "field_changes": {
            "added": [{"field_id": fid, "new_field": new_fields[fid], "review_required": True} for fid in added],
            "removed": [{"field_id": fid, "old_field": old_fields[fid], "review_required": True} for fid in removed],
            "changed": changed_fields,
        },
        "source_atom_changes": source_atom_changes,
        "review_status_changes": review_changes,
        "coverage_changes": coverage,
        "change_control_boundary": {
            "intended_use": "Identify profile-view changes that require implementation, mapping or regulatory review.",
            "not_for": [
                "automatic approval of changed regulatory mappings",
                "legal-materiality determination",
                "compliance certification",
                "supervisory acceptance",
            ],
            "recommended_next_steps": [
                "review added, removed and changed fields",
                "review source atom changes before relying on the updated profile",
                "review coverage changes and unused source atoms as gap signals",
                "pin the new profile hash only after internal review",
            ],
        },
        "generated_at": _utc_now(),
    }
