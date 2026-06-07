# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Bank-owned profile overlays for internal mappings and review decisions.

A bank overlay is a local control object. It records how an institution maps its
own field names to a pinned ActProof profile and how those candidate mappings are
reviewed internally. It never changes the public ActProof profile and never
turns a candidate mapping into legal equivalence, compliance certification, or
supervisory approval.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from actproof_events import __version__
from actproof_events.bank_operability import build_profile_lock, canonical_json_hash
from actproof_events.exports import build_profile_view
from actproof_events.schema_mapping import compare_schema_file
from actproof_events.services import list_fields

BANK_PROFILE_OVERLAY_SCHEMA_ID = "actproof.bank_profile_overlay.v1"
BANK_OVERLAY_STATUS_SCHEMA_ID = "actproof.bank_overlay_status.v1"
BANK_OVERLAY_REPORT_SCHEMA_ID = "actproof.bank_overlay_report.v1"

_ALLOWED_REVIEW_DECISIONS = {
    "accepted",
    "rejected",
    "needs_review",
    "split_mapping",
    "merged_mapping",
    "not_applicable",
    "deferred",
}
_ALLOWED_MAPPING_STATUSES = {
    "candidate_review_required",
    "approved_for_internal_review_use",
    "rejected_by_bank_review",
    "needs_bank_sme_review",
    "superseded",
}
_ALLOWED_EXCEPTION_TYPES = {
    "accepted_gap",
    "deferred_mapping",
    "internal_field_retained",
    "requires_legal_review",
    "requires_data_owner_review",
    "source_challenge_open",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_bank_overlay(path: str | Path) -> dict[str, Any]:
    """Load a bank overlay JSON file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != BANK_PROFILE_OVERLAY_SCHEMA_ID:
        raise ValueError(f"expected schema {BANK_PROFILE_OVERLAY_SCHEMA_ID}, got {payload.get('schema')!r}")
    return payload


def write_bank_overlay(overlay: dict[str, Any], path: str | Path, *, compact: bool = False) -> None:
    """Write a bank overlay JSON file."""
    indent = None if compact else 2
    Path(path).write_text(json.dumps(overlay, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def _mapping_report(payload_or_path: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(payload_or_path, (str, Path)):
        return json.loads(Path(payload_or_path).read_text(encoding="utf-8"))
    return payload_or_path


def _required_actproof_fields(act_id: str) -> set[str]:
    return {row["field_id"] for row in list_fields(act_id, required_only=True)}


def init_bank_overlay(
    act_id: str,
    mapping_report: dict[str, Any] | str | Path,
    *,
    institution: str | dict[str, Any] | None = None,
    overlay_id: str | None = None,
) -> dict[str, Any]:
    """Initialise a draft bank-owned overlay from a candidate mapping report.

    Candidate mappings are carried forward as review items only. Nothing is
    accepted automatically.
    """
    report = _mapping_report(mapping_report)
    profile_view = build_profile_view(act_id)
    profile_lock = build_profile_lock(act_id)
    if report.get("act_id") and report.get("act_id") != act_id:
        raise ValueError("mapping report act_id does not match requested act_id")
    if isinstance(institution, str):
        inst = {"name": institution, "identifier": None}
    elif isinstance(institution, dict):
        inst = dict(institution)
    else:
        inst = {"name": None, "identifier": None}
    overlay_id = overlay_id or f"overlay.local.{act_id.replace(':', '.').replace('/', '.')}.v1"

    mapping_items: list[dict[str, Any]] = []
    for item in report.get("mappings") or []:
        candidates = item.get("candidates") or []
        candidate_refs = [
            {
                "actproof_field_id": c.get("actproof_field_id"),
                "candidate_strength": c.get("candidate_strength"),
                "matched_by": c.get("matched_by") or [],
                "source_atoms": c.get("source_atoms") or [],
                "warnings": c.get("warnings") or [],
            }
            for c in candidates
        ]
        mapping_items.append({
            "external_field": item.get("external_field"),
            "external_label": item.get("external_label"),
            "external_type": item.get("external_type"),
            "candidate_actproof_fields": candidate_refs,
            "selected_actproof_field_id": candidate_refs[0].get("actproof_field_id") if candidate_refs else None,
            "candidate_strength": candidate_refs[0].get("candidate_strength") if candidate_refs else None,
            "mapping_status": "candidate_review_required",
            "review_required": True,
            "review_decision": "needs_review",
            "reviewed_by": None,
            "reviewed_at": None,
            "review_notes": None,
            "use_boundary": "internal_prevalidation_only",
            "warnings": [
                "Candidate only: bank review required before operational use.",
                "Do not rely on field-name similarity alone.",
                "This overlay does not create legal equivalence or supervisory approval.",
            ],
        })

    missing_required = [
        {
            "actproof_field_id": fid,
            "status": "missing_in_internal_schema",
            "decision": "needs_decision",
            "owner": None,
            "target_date": None,
            "review_required": True,
            "notes": None,
        }
        for fid in report.get("missing_actproof_required_fields") or []
    ]

    external_only = [
        {
            "external_field": f.get("external_field"),
            "label": f.get("label"),
            "classification": "external_unmapped_field",
            "actproof_mapping": None,
            "decision": "needs_review",
            "reason": f.get("reason") or "No candidate above threshold in mapping report.",
            "review_required": True,
            "notes": None,
        }
        for f in report.get("unmapped_external_fields") or []
    ]

    overlay = {
        "schema": BANK_PROFILE_OVERLAY_SCHEMA_ID,
        "overlay_id": overlay_id,
        "act_id": act_id,
        "profile_semantic_hash": profile_view.get("profile_semantic_hash"),
        "profile_lock_hash": profile_lock.get("profile_lock_hash"),
        "package": {"name": "actproof-events", "version": __version__},
        "institution": inst,
        "overlay_status": "draft",
        "overlay_scope": "DORA initial notification internal field mapping review",
        "source_mapping_report": {
            "schema": report.get("schema"),
            "external_system": report.get("external_system"),
            "mapping_report_hash": canonical_json_hash(report),
            "generated_at": report.get("generated_at"),
        },
        "mapping_policy": {
            "field_ids_universal": False,
            "mapping_status_default": "candidate_review_required",
            "review_required_default": True,
            "safe_use": "Bank-local reviewed mapping overlay for internal pre-validation only.",
            "do_not_use_for": [
                "legal advice",
                "compliance certification",
                "supervisory approval",
                "factual verification",
                "regulatory submission",
            ],
        },
        "mappings": mapping_items,
        "missing_required_field_decisions": missing_required,
        "external_only_fields": external_only,
        "exceptions": [],
        "review": {
            "review_status": "draft",
            "reviewed_by": None,
            "reviewed_at": None,
            "review_scope": "bank-local internal field mapping review",
            "review_limitations": [
                "not ActProof public profile review",
                "not external legal review",
                "not supervisory approval",
                "not compliance certification",
            ],
        },
        "boundaries": [
            "Overlay belongs to the institution and does not modify the public ActProof profile.",
            "All mapping decisions are bank-local and require internal ownership.",
            "ActProof field IDs are profile-local reference anchors, not universal market field names.",
        ],
        "created_at": _utc_now(),
    }
    overlay["overlay_hash"] = compute_overlay_hash(overlay)
    return overlay


def compute_overlay_hash(overlay: dict[str, Any]) -> str:
    """Compute a stable hash over the overlay excluding volatile/hash fields."""
    return _stable_hash({k: v for k, v in overlay.items() if k not in {"overlay_hash", "generated_at"}})


def validate_bank_overlay(overlay: dict[str, Any]) -> list[str]:
    """Validate a bank overlay's internal consistency.

    Validation is intentionally governance-focused. It never approves legal or
    regulatory equivalence.
    """
    errors: list[str] = []
    if overlay.get("schema") != BANK_PROFILE_OVERLAY_SCHEMA_ID:
        errors.append(f"expected schema {BANK_PROFILE_OVERLAY_SCHEMA_ID}")
        return errors
    act_id = overlay.get("act_id")
    if not act_id:
        errors.append("missing act_id")
        return errors
    current_hash = build_profile_view(act_id).get("profile_semantic_hash")
    if overlay.get("profile_semantic_hash") != current_hash:
        errors.append("profile_semantic_hash does not match installed profile; overlay impact review required")
    known_fields = {row["field_id"] for row in list_fields(act_id, required_only=False)}
    for idx, mapping in enumerate(overlay.get("mappings") or []):
        prefix = f"mappings[{idx}] {mapping.get('external_field') or '<unnamed>'}: "
        status = mapping.get("mapping_status")
        if status not in _ALLOWED_MAPPING_STATUSES:
            errors.append(prefix + f"invalid mapping_status {status!r}")
        decision = mapping.get("review_decision")
        if decision not in _ALLOWED_REVIEW_DECISIONS:
            errors.append(prefix + f"invalid review_decision {decision!r}")
        selected = mapping.get("selected_actproof_field_id")
        if selected and selected not in known_fields:
            errors.append(prefix + f"selected_actproof_field_id {selected!r} is not in profile")
        if decision == "accepted":
            if status != "approved_for_internal_review_use":
                errors.append(prefix + "accepted decision requires mapping_status approved_for_internal_review_use")
            if not selected:
                errors.append(prefix + "accepted decision requires selected_actproof_field_id")
            if not mapping.get("reviewed_by") or not mapping.get("reviewed_at"):
                errors.append(prefix + "accepted decision requires reviewed_by and reviewed_at")
        if decision == "rejected" and not mapping.get("review_notes"):
            errors.append(prefix + "rejected decision requires review_notes")
        # Only scan fields where the BANK asserts a decision — not the
        # auto-generated warnings/boundary text, which legitimately contains
        # negated phrases like "does not create legal equivalence".
        _claim_text = " ".join(str(mapping.get(k, "")) for k in (
            "review_notes", "mapping_status", "review_decision", "use_boundary",
        )).lower()
        for _phrase in (
            "legal_equivalence", "compliance_cert", "legally equivalent",
            "legal equivalence", "compliance certified", "compliance certification",
            "regulatory approval", "supervisory approval", "certified compliant",
        ):
            if _phrase in _claim_text:
                errors.append(prefix + f"must not claim legal equivalence or compliance certification (found {_phrase!r})")
                break
    for idx, item in enumerate(overlay.get("missing_required_field_decisions") or []):
        fid = item.get("actproof_field_id")
        if fid not in _required_actproof_fields(act_id):
            errors.append(f"missing_required_field_decisions[{idx}] references non-required/unknown field {fid!r}")
        if item.get("decision") not in {"needs_decision", "add_to_internal_form", "covered_elsewhere", "not_applicable", "deferred", "accepted_gap"}:
            errors.append(f"missing_required_field_decisions[{idx}] invalid decision {item.get('decision')!r}")
        if item.get("decision") not in {"needs_decision", None} and not item.get("owner"):
            errors.append(f"missing_required_field_decisions[{idx}] non-default decision requires owner")
    for idx, item in enumerate(overlay.get("external_only_fields") or []):
        if item.get("decision") not in {"needs_review", "retain_as_internal_field", "map_later", "remove_from_reporting_scope", "deferred"}:
            errors.append(f"external_only_fields[{idx}] invalid decision {item.get('decision')!r}")
        if item.get("decision") != "needs_review" and not item.get("reason"):
            errors.append(f"external_only_fields[{idx}] non-default decision requires reason")
    for idx, exc in enumerate(overlay.get("exceptions") or []):
        if exc.get("type") not in _ALLOWED_EXCEPTION_TYPES:
            errors.append(f"exceptions[{idx}] invalid type {exc.get('type')!r}")
        if not exc.get("reason"):
            errors.append(f"exceptions[{idx}] requires reason")
    return errors


def build_bank_overlay_status(overlay: dict[str, Any]) -> dict[str, Any]:
    """Build an operational status summary for a bank overlay."""
    errors = validate_bank_overlay(overlay)
    mappings = overlay.get("mappings") or []
    missing = overlay.get("missing_required_field_decisions") or []
    external_only = overlay.get("external_only_fields") or []
    accepted = [m for m in mappings if m.get("review_decision") == "accepted"]
    rejected = [m for m in mappings if m.get("review_decision") == "rejected"]
    needs_review = [m for m in mappings if m.get("review_decision") in {"needs_review", None}]
    missing_without_decision = [m for m in missing if m.get("decision") in {"needs_decision", None}]
    external_needs_review = [f for f in external_only if f.get("decision") in {"needs_review", None}]
    profile_hash_matches = True
    if overlay.get("act_id"):
        profile_hash_matches = overlay.get("profile_semantic_hash") == build_profile_view(overlay["act_id"]).get("profile_semantic_hash")
    ready = (
        profile_hash_matches and
        not errors and
        not needs_review and
        not missing_without_decision and
        not external_needs_review and
        bool(accepted or not mappings)
    )
    # Derived status with explicit self-degradation: if the profile moved since the
    # overlay's approvals were recorded, prior approvals no longer apply and the
    # overlay drops to needs_re_review regardless of its stored status. A bank's
    # approval against one profile hash is not valid against a different one.
    if not profile_hash_matches:
        derived_status = "needs_re_review"
    elif errors:
        derived_status = "invalid"
    elif needs_review or missing_without_decision or external_needs_review:
        derived_status = "review_in_progress"
    else:
        derived_status = "internal_review_complete"
    status = {
        "schema": BANK_OVERLAY_STATUS_SCHEMA_ID,
        "overlay_id": overlay.get("overlay_id"),
        "act_id": overlay.get("act_id"),
        "institution": overlay.get("institution"),
        "overlay_status": derived_status,
        "declared_overlay_status": overlay.get("overlay_status"),
        "profile_semantic_hash": overlay.get("profile_semantic_hash"),
        "profile_semantic_hash_matches": profile_hash_matches,
        "profile_semantic_hash_current": (
            build_profile_view(overlay["act_id"]).get("profile_semantic_hash")
            if overlay.get("act_id") else None
        ),
        "mapping_counts": {
            "total": len(mappings),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "needs_review": len(needs_review),
        },
        "missing_required_field_decisions": {
            "total": len(missing),
            "without_decision": len(missing_without_decision),
        },
        "external_only_fields": {
            "total": len(external_only),
            "needs_review": len(external_needs_review),
        },
        "exceptions": {"total": len(overlay.get("exceptions") or [])},
        "validation_errors": errors,
        "review_required": bool(errors or needs_review or missing_without_decision or external_needs_review or not profile_hash_matches),
        "ready_for_internal_poc": ready,
        "boundary": "Bank-local overlay status only; not legal advice, compliance certification or supervisory approval.",
        "generated_at": _utc_now(),
    }
    status["overlay_status_hash"] = _stable_hash({k: v for k, v in status.items() if k not in {"overlay_status_hash", "generated_at"}})
    return status


def build_bank_overlay_report(overlay: dict[str, Any]) -> dict[str, Any]:
    """Build an audit-friendly overlay report."""
    status = build_bank_overlay_status(overlay)
    report = {
        "schema": BANK_OVERLAY_REPORT_SCHEMA_ID,
        "overlay_id": overlay.get("overlay_id"),
        "act_id": overlay.get("act_id"),
        "package": {"name": "actproof-events", "version": __version__},
        "profile_semantic_hash": overlay.get("profile_semantic_hash"),
        "profile_lock_hash": overlay.get("profile_lock_hash"),
        "institution": overlay.get("institution"),
        "status": status,
        "mapping_decisions": overlay.get("mappings") or [],
        "missing_required_field_decisions": overlay.get("missing_required_field_decisions") or [],
        "external_only_fields": overlay.get("external_only_fields") or [],
        "exceptions": overlay.get("exceptions") or [],
        "review": overlay.get("review") or {},
        "next_actions": _overlay_next_actions(status),
        "boundaries": overlay.get("boundaries") or [],
        "generated_at": _utc_now(),
    }
    report["overlay_report_hash"] = _stable_hash({k: v for k, v in report.items() if k not in {"overlay_report_hash", "generated_at"}})
    return report


def _overlay_next_actions(status: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if not status.get("profile_semantic_hash_matches"):
        actions.append("Run overlay impact review because the pinned profile hash no longer matches the installed profile.")
    if status.get("mapping_counts", {}).get("needs_review"):
        actions.append("Review candidate mappings and record accept/reject/defer decisions with owner and timestamp.")
    if status.get("missing_required_field_decisions", {}).get("without_decision"):
        actions.append("Decide how to handle missing ActProof required fields in the internal schema.")
    if status.get("external_only_fields", {}).get("needs_review"):
        actions.append("Classify unmapped external-only fields as retained internal controls, deferred mappings, or out of reporting scope.")
    if status.get("validation_errors"):
        actions.append("Resolve overlay validation errors before relying on the overlay for an internal POC.")
    if not actions:
        actions.append("Overlay is ready for internal POC use under bank governance boundaries.")
    return actions


def init_bank_overlay_from_schema(
    act_id: str,
    external_schema_path: str | Path,
    *,
    institution: str | dict[str, Any] | None = None,
    external_system: str | None = None,
) -> dict[str, Any]:
    """Compare an external schema and initialise a draft overlay in one step."""
    mapping = compare_schema_file(act_id, external_schema_path, external_system=external_system)
    return init_bank_overlay(act_id, mapping, institution=institution)


__all__ = [
    "BANK_PROFILE_OVERLAY_SCHEMA_ID",
    "BANK_OVERLAY_STATUS_SCHEMA_ID",
    "BANK_OVERLAY_REPORT_SCHEMA_ID",
    "init_bank_overlay",
    "init_bank_overlay_from_schema",
    "validate_bank_overlay",
    "build_bank_overlay_status",
    "build_bank_overlay_report",
    "load_bank_overlay",
    "write_bank_overlay",
    "compute_overlay_hash",
]
