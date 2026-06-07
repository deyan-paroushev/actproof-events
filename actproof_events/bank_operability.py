# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Bank-operable trust-pack helpers for ActProof profiles.

These helpers do not turn ActProof into a bank workflow system. They make a
profile easier to adopt inside a controlled environment by producing: a pinned
profile lockfile, an audit-friendly pre-validation report, and a review
checklist template. All outputs are deterministic JSON objects suitable for
local storage in a bank's own change-control and audit systems.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from actproof_events import __version__
from actproof_events.exports import build_profile_view
from actproof_events.services import BOUNDARY, BOUNDARY_ID, get_profile, prevalidate_report
from actproof_events.source_binding import (
    compute_field_source_coverage,
    compute_source_atom_coverage,
    get_profile_completeness,
    list_field_derivations,
    list_source_atoms,
)

PROFILE_LOCK_SCHEMA_ID = "actproof.profile_lock.v1"
PREVALIDATION_REPORT_SCHEMA_ID = "actproof.prevalidation_report.v1"
REVIEW_CHECKLIST_SCHEMA_ID = "actproof.review_checklist.v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def canonical_json_hash(obj: Any) -> str:
    """Return a stable hash over canonical JSON for arbitrary JSON-like data."""
    return _stable_hash(obj)


def build_profile_lock(act_id: str) -> dict[str, Any]:
    """Build a pin-able profile lockfile for local/bank implementation.

    The lockfile captures the package version, catalogue/profile hashes, source
    atom and derivation hashes, source-atom coverage and completeness state. It
    lets a bank say exactly which profile object was used for a review or
    pre-validation run.
    """
    profile = get_profile(act_id)
    view = build_profile_view(act_id, include_governance=False)
    source_atoms = list_source_atoms(act_id)
    field_derivations = list_field_derivations(act_id)
    source_atom_coverage = compute_source_atom_coverage(act_id)
    field_source_coverage = compute_field_source_coverage(act_id)
    completeness = get_profile_completeness(act_id)

    lock = {
        "schema": PROFILE_LOCK_SCHEMA_ID,
        "act_id": act_id,
        "package": {
            "name": "actproof-events",
            "version": __version__,
        },
        "profile": {
            "display_name": profile.get("display_name") or profile.get("name"),
            "catalogue_entry_hash": profile.get("catalogue_entry_hash"),
            "catalogue_entry_hash_basis": profile.get("catalogue_entry_hash_basis"),
            "profile_semantic_hash": view.get("profile_semantic_hash"),
            "profile_artifact_hash": view.get("profile_artifact_hash"),
            "profile_view_schema": view.get("profile_view_schema"),
        },
        "component_hashes": {
            "source_atoms_hash": _stable_hash(source_atoms),
            "field_derivations_hash": _stable_hash(field_derivations),
            "source_atom_coverage_hash": _stable_hash(source_atom_coverage),
            "field_source_coverage_hash": _stable_hash(field_source_coverage),
            "completeness_hash": _stable_hash(completeness),
        },
        "coverage": {
            "field_source_coverage": field_source_coverage,
            "source_atom_coverage": source_atom_coverage,
        },
        "completeness": completeness,
        "bank_operability_boundary": {
            "intended_use": (
                "Local profile pinning, internal mapping review, pre-validation run records, "
                "change-control evidence and audit support."
            ),
            "not_for": [
                "legal advice",
                "compliance certification",
                "supervisory approval",
                "factual verification of incident data",
                "regulatory submission",
                "cryptographic receipt verification",
            ],
            "bank_responsibility": [
                "review source mappings before operational reliance",
                "map internal fields to ActProof profile fields under internal controls",
                "own final legal/regulatory interpretation",
                "pin profile version and hashes in change-management records",
            ],
        },
        "generated_at": _utc_now(),
    }
    lock["profile_lock_hash"] = _stable_hash({k: v for k, v in lock.items() if k != "profile_lock_hash"})
    return lock


def build_prevalidation_run_report(act_id: str, report: dict[str, Any]) -> dict[str, Any]:
    """Build an audit-friendly pre-validation run report.

    The input report is hashed, not embedded, so this object can usually travel
    more safely than the incident payload itself. It still carries all ActProof
    pre-validation findings and the exact profile lock used for the run.
    """
    lock = build_profile_lock(act_id)
    result = prevalidate_report(act_id, report)
    report_hash = _stable_hash(report)
    run = {
        "schema": PREVALIDATION_REPORT_SCHEMA_ID,
        "act_id": act_id,
        "package": {
            "name": "actproof-events",
            "version": __version__,
        },
        "profile_lock": lock,
        "input_report_hash": report_hash,
        "input_report_hash_basis": "sha256 over canonical JSON with sorted keys and compact separators",
        "prevalidation_result": result,
        "run_summary": {
            "prevalidation_status": result.get("prevalidation_status"),
            "ready_for_preverification": result.get("ready_for_preverification"),
            "required_present": result.get("required_present"),
            "required_total": result.get("required_total"),
            "finding_count": len(result.get("findings") or []),
            "missing_required_count": len(result.get("missing_required") or []),
            "unknown_field_count": len(result.get("unknown_fields") or []),
        },
        "audit_boundary": {
            "check_type": "prevalidation",
            "boundary": BOUNDARY,
            "boundary_id": BOUNDARY_ID,
            "not_performed": [
                "legal compliance determination",
                "factual verification of field values",
                "signature verification",
                "RFC 3161 timestamp verification",
                "ledger anchor verification",
                "supervisory submission",
            ],
        },
        "generated_at": _utc_now(),
    }
    run["prevalidation_report_hash"] = _stable_hash({k: v for k, v in run.items() if k != "prevalidation_report_hash"})
    return run


def build_bank_review_checklist(act_id: str) -> dict[str, Any]:
    """Build a bank-facing implementation/review checklist template."""
    lock = build_profile_lock(act_id)
    completeness = lock["completeness"]
    checklist = {
        "schema": REVIEW_CHECKLIST_SCHEMA_ID,
        "act_id": act_id,
        "package": {"name": "actproof-events", "version": __version__},
        "profile_lock": {
            "profile_lock_hash": lock["profile_lock_hash"],
            "profile_semantic_hash": lock["profile"]["profile_semantic_hash"],
            "catalogue_entry_hash": lock["profile"].get("catalogue_entry_hash"),
        },
        "review_status": completeness.get("review_status", "draft"),
        "completeness_status": completeness.get("completeness_status", "candidate"),
        "checklist": [
            {
                "section": "Profile scope and boundary",
                "items": [
                    "Confirm the profile scope matches the intended internal use case.",
                    "Confirm not_exhaustive_of items are acceptable or captured as bank-side controls.",
                    "Confirm ActProof is treated as pre-validation/reference tooling, not legal advice or certification.",
                ],
            },
            {
                "section": "Source identity and source-atom coverage",
                "items": [
                    "Review the official source instruments, CELEX/ELI identifiers and source document hashes.",
                    "Review unused_source_atom_ids as gap signals and decide whether action is required.",
                    "Review atoms_only_in_contextual_binding_ids and determine whether any require stronger field representation.",
                ],
            },
            {
                "section": "Field derivations and evidence expectations",
                "items": [
                    "Review all required fields and their source atoms.",
                    "Review high-interpretive-load fields and evidence expectations.",
                    "Confirm disclosure tiers align with bank handling requirements.",
                ],
            },
            {
                "section": "Internal field mapping",
                "items": [
                    "Map bank/internal/GRC fields to ActProof field IDs by source atoms, template locators and meaning — not by name alone.",
                    "Mark all mappings candidate_review_required until reviewed by the bank owner.",
                    "Record unmapped internal fields and missing ActProof required fields.",
                ],
            },
            {
                "section": "Pre-validation run governance",
                "items": [
                    "Run pre-validation locally or in an approved internal environment.",
                    "Store the profile lock, input report hash and pre-validation report in internal records.",
                    "Escalate blocked or attention_required findings under the bank's incident-reporting controls.",
                ],
            },
            {
                "section": "Change management",
                "items": [
                    "Pin actproof-events package version and profile hashes.",
                    "Require review when profile_semantic_hash, source_atoms_hash or field_derivations_hash changes.",
                    "Do not update the operational profile without bank-side change approval.",
                ],
            },
        ],
        "challenge_model": {
            "challenge_allowed": completeness.get("challenge_allowed", True),
            "challenge_types": completeness.get("challenge_types", []),
            "challenge_channel": completeness.get("challenge_channel"),
        },
        "generated_at": _utc_now(),
    }
    checklist["review_checklist_hash"] = _stable_hash({k: v for k, v in checklist.items() if k != "review_checklist_hash"})
    return checklist


def verify_profile_lock(lock: "dict[str, Any] | str | Path") -> dict[str, Any]:
    """Re-check a stored profile lock against the installed package.

    This is the operational other half of ``build_profile_lock``: a bank pins a
    lock, then later proves the profile it depends on has not silently moved.
    It re-derives the lock from the installed package and compares the
    time-independent identity fields (version + all hashes). ``generated_at`` and
    ``profile_lock_hash`` are excluded from the comparison because they vary by
    run; everything that defines *which profile* is checked.

    Returns ``{ok, act_id, checks, mismatches, note}``.
    """
    import json as _json
    from pathlib import Path as _Path

    if isinstance(lock, (str, _Path)):
        lock = _json.loads(_Path(lock).read_text(encoding="utf-8"))

    act_id = lock.get("act_id")
    current = build_profile_lock(act_id)

    def _flat(d: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        out["package_version"] = (d.get("package") or {}).get("version")
        prof = d.get("profile") or {}
        for k in ("profile_semantic_hash", "profile_artifact_hash", "catalogue_entry_hash"):
            out[k] = prof.get(k)
        for k, v in (d.get("component_hashes") or {}).items():
            out[k] = v
        return out

    exp = _flat(lock)
    got = _flat(current)
    checks: dict[str, bool] = {}
    mismatches: list[dict[str, Any]] = []
    for k in exp:
        ok = exp.get(k) == got.get(k)
        checks[k] = ok
        if not ok:
            mismatches.append({"field": k, "expected": exp.get(k), "actual": got.get(k)})

    return {
        "ok": not mismatches,
        "act_id": act_id,
        "checks": checks,
        "mismatches": mismatches,
        "note": (
            "A version mismatch is expected after a package upgrade; re-pin "
            "against the version you intend to use. A hash mismatch at the SAME "
            "version means the profile content moved and must be reviewed before "
            "continued reliance."
        ),
    }


__all__ = [
    "PROFILE_LOCK_SCHEMA_ID",
    "PREVALIDATION_REPORT_SCHEMA_ID",
    "REVIEW_CHECKLIST_SCHEMA_ID",
    "canonical_json_hash",
    "build_profile_lock",
    "build_prevalidation_run_report",
    "build_bank_review_checklist",
    "verify_profile_lock",
]
