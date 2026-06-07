# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Reviewed profile governance and bank POC packaging for ActProof profiles.

This module makes the profile governance state explicit. It does not turn a
maintainer review into legal review, bank approval, supervisory approval, or
compliance certification. Governance records are bounded evidence objects that
help a bank run a local POC under its own internal controls.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from actproof_events import __version__
from actproof_events.bank_operability import (
    build_bank_review_checklist,
    build_prevalidation_run_report,
    build_profile_lock,
    canonical_json_hash,
)
from actproof_events.exports import build_profile_view
from actproof_events.schema_mapping import compare_schema_file
from actproof_events.source_binding import compute_source_atom_coverage, get_profile_completeness

REVIEW_RECORDS_SCHEMA_ID = "actproof.review_records.v1"
CHALLENGE_RECORDS_SCHEMA_ID = "actproof.challenge_records.v1"
PROFILE_GOVERNANCE_STATUS_SCHEMA_ID = "actproof.profile_governance_status.v1"
BANK_POC_PACK_SCHEMA_ID = "actproof.bank_poc_pack.v1"

_DORA_ACT_ID = "op:eu.dora.ict_incident_notification_initial.v1"
_DORA_STEM = "ict_incident_notification_initial.v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _data_root() -> Path:
    # In a wheel, profile_governance is force-included under data/. In a source
    # checkout, use the repository root's profile_governance/ directory.
    wheel_root = Path(__file__).resolve().parent / "data" / "profile_governance"
    if wheel_root.exists():
        return wheel_root
    return _repo_root() / "profile_governance"


def _profile_paths(act_id: str) -> tuple[Path, Path]:
    if act_id != _DORA_ACT_ID:
        return Path("__missing__"), Path("__missing__")
    root = _data_root() / "eu" / "dora"
    return (
        root / f"{_DORA_STEM}.review_records.json",
        root / f"{_DORA_STEM}.challenge_records.json",
    )


def _load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_record(record: dict[str, Any]) -> str:
    return _stable_hash({k: v for k, v in record.items() if k != "review_record_hash"})


def list_review_records(act_id: str) -> list[dict[str, Any]]:
    """Return bounded maintainer/external review records for a profile."""
    review_path, _ = _profile_paths(act_id)
    doc = _load_json(review_path, {"schema": REVIEW_RECORDS_SCHEMA_ID, "act_id": act_id, "records": []})
    if doc.get("schema") != REVIEW_RECORDS_SCHEMA_ID:
        raise ValueError(f"{review_path}: expected schema {REVIEW_RECORDS_SCHEMA_ID}")
    view = build_profile_view(act_id, include_governance=False)
    lock = build_profile_lock(act_id)
    reviewed_artifacts = {
        # Semantic artifacts only: no generated_at-dependent lock or artifact hash.
        "profile_semantic_hash": view.get("profile_semantic_hash"),
        "source_atoms_hash": lock.get("component_hashes", {}).get("source_atoms_hash"),
        "field_derivations_hash": lock.get("component_hashes", {}).get("field_derivations_hash"),
        "source_atom_coverage_hash": lock.get("component_hashes", {}).get("source_atom_coverage_hash"),
        "completeness_hash": lock.get("component_hashes", {}).get("completeness_hash"),
    }
    records: list[dict[str, Any]] = []
    for raw in doc.get("records") or []:
        record = dict(raw)
        record.setdefault("act_id", act_id)
        record["reviewed_artifacts"] = dict(reviewed_artifacts)
        record["review_record_hash_basis"] = "sha256 over canonical JSON excluding review_record_hash"
        record["review_record_hash"] = _hash_record(record)
        records.append(record)
    return records


def latest_review_record(act_id: str) -> dict[str, Any] | None:
    records = list_review_records(act_id)
    return records[-1] if records else None


def list_challenge_records(act_id: str) -> list[dict[str, Any]]:
    """Return public challenge/gap records for a profile."""
    _, challenge_path = _profile_paths(act_id)
    doc = _load_json(challenge_path, {"schema": CHALLENGE_RECORDS_SCHEMA_ID, "act_id": act_id, "challenge_records": []})
    if doc.get("schema") != CHALLENGE_RECORDS_SCHEMA_ID:
        raise ValueError(f"{challenge_path}: expected schema {CHALLENGE_RECORDS_SCHEMA_ID}")
    records = [dict(r) for r in doc.get("challenge_records") or []]
    # Augment with computed coverage gap records if the static registry omitted
    # them. This keeps the challenge surface honest with the actual coverage.
    known_ids = {r.get("source_atom_id") for r in records if r.get("source_atom_id")}
    coverage = compute_source_atom_coverage(act_id)
    for atom_id in coverage.get("unused_source_atom_ids") or []:
        if atom_id not in known_ids:
            records.append({
                "challenge_id": f"challenge.auto.{atom_id}",
                "challenge_type": "coverage_gap",
                "status": "open",
                "field_id": None,
                "source_atom_id": atom_id,
                "summary": "Source atom is recorded but currently unused by field derivations.",
                "impact": "gap_signal",
                "resolution": None,
                "created_at": None,
                "boundary": "Automatically surfaced gap signal; not confirmation that a required field is missing.",
            })
    for r in records:
        r.setdefault("challenge_record_hash_basis", "sha256 over canonical JSON excluding challenge_record_hash")
        r["challenge_record_hash"] = _stable_hash({k: v for k, v in r.items() if k != "challenge_record_hash"})
    return records


def build_governance_status(act_id: str) -> dict[str, Any]:
    """Build a review/governance status object for a profile."""
    view = build_profile_view(act_id, include_governance=False)
    completeness = get_profile_completeness(act_id)
    review = latest_review_record(act_id)
    challenges = list_challenge_records(act_id)
    open_challenges = [c for c in challenges if c.get("status") in {"open", "under_review"}]
    blocking = [c for c in open_challenges if c.get("impact") == "blocking"]
    lifecycle_state = "candidate"
    if review and review.get("review_status") == "maintainer_reviewed":
        lifecycle_state = "maintainer_reviewed"
    if blocking:
        lifecycle_state = "candidate"
    # Weakest-link honesty: if the maintainer review deliberately held any field
    # derivations at draft (e.g. high-interpretation fields), the WHOLE-PROFILE
    # lifecycle cannot be maintainer_reviewed. A partial review does not promote
    # the profile.
    excluded_field_ids = (review.get("excluded_field_ids") if review else None) or []
    if excluded_field_ids and lifecycle_state == "maintainer_reviewed":
        lifecycle_state = "candidate"
    status = {
        "schema": PROFILE_GOVERNANCE_STATUS_SCHEMA_ID,
        "act_id": act_id,
        "package": {"name": "actproof-events", "version": __version__},
        "lifecycle_state": lifecycle_state,
        "profile_semantic_hash": view.get("profile_semantic_hash"),
        "profile_artifact_hash": view.get("profile_artifact_hash"),
        "latest_review_status": review.get("review_status") if review else completeness.get("review_status", "draft"),
        "latest_review_record_hash": review.get("review_record_hash") if review else None,
        "review_type": review.get("review_type") if review else None,
        "reviewed_field_ids": (review.get("reviewed_field_ids") if review else None),
        "held_at_draft_field_ids": (review.get("excluded_field_ids") if review else None),
        "review_limitations": review.get("review_limitations") if review else [
            "no maintainer review record available",
            "not external legal review",
            "not bank SME approval",
            "not supervisory approval",
        ],
        "open_challenges": len(open_challenges),
        "blocking_challenges": len(blocking),
        "challenge_summary": {
            "total": len(challenges),
            "open": len(open_challenges),
            "blocking": len(blocking),
            "by_type": _count_by(challenges, "challenge_type"),
            "by_status": _count_by(challenges, "status"),
        },
        "bank_use_boundary": (
            "Suitable for local POC and internal review support under explicit boundaries; "
            "not standalone compliance authority, legal advice, factual verification, or regulatory submission."
        ),
        "bank_poc_pitch": (
            "Run ActProof locally against one DORA initial-notification draft and one internal field list. "
            "It will show missing required fields, high-judgement fields, source atoms, evidence expectations, "
            "source-atom coverage, and where field names need reviewed mapping."
        ),
        "generated_at": _utc_now(),
    }
    status["governance_status_hash"] = _stable_hash({k: v for k, v in status.items() if k not in {"governance_status_hash", "generated_at"}})
    return status


def _count_by(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in records:
        val = str(r.get(key) or "unknown")
        out[val] = out.get(val, 0) + 1
    return dict(sorted(out.items()))


def validate_profile_governance(act_id: str) -> list[str]:
    """Validate governance consistency without making legal approval claims."""
    errors: list[str] = []
    status = build_governance_status(act_id)
    records = list_review_records(act_id)
    challenges = list_challenge_records(act_id)
    view_hash = build_profile_view(act_id, include_governance=False).get("profile_semantic_hash")
    if not records:
        errors.append("no review records available")
    for record in records:
        if record.get("review_status") == "maintainer_reviewed":
            artifacts = record.get("reviewed_artifacts") or {}
            if artifacts.get("profile_semantic_hash") != view_hash:
                errors.append(f"review record {record.get('review_id')} does not bind current profile_semantic_hash")
            if not record.get("review_record_hash"):
                errors.append(f"review record {record.get('review_id')} has no review_record_hash")
    for challenge in challenges:
        if not challenge.get("challenge_id"):
            errors.append("challenge record missing challenge_id")
        if challenge.get("status") not in {"open", "under_review", "accepted", "rejected", "resolved", "superseded"}:
            errors.append(f"challenge {challenge.get('challenge_id')} has invalid status {challenge.get('status')!r}")
    if status.get("lifecycle_state") == "maintainer_reviewed" and not status.get("latest_review_record_hash"):
        errors.append("maintainer_reviewed lifecycle state requires latest_review_record_hash")
    return errors


def build_bank_poc_pack(
    act_id: str,
    *,
    external_schema_path: str | Path | None = None,
    sample_report_path: str | Path | None = None,
    out_dir: str | Path,
) -> dict[str, Any]:
    """Export a concrete local bank POC pack directory.

    The pack is intentionally file-based: banks can inspect, archive, and import
    each JSON artifact into their own controls without calling a hosted service.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    profile_view = build_profile_view(act_id, include_governance=False)
    profile_lock = build_profile_lock(act_id)
    source_atom_coverage = compute_source_atom_coverage(act_id)
    completeness = get_profile_completeness(act_id)
    governance_status = build_governance_status(act_id)
    review_records = {"schema": REVIEW_RECORDS_SCHEMA_ID, "act_id": act_id, "records": list_review_records(act_id)}
    challenge_records = {"schema": CHALLENGE_RECORDS_SCHEMA_ID, "act_id": act_id, "challenge_records": list_challenge_records(act_id)}
    review_checklist = build_bank_review_checklist(act_id)

    files: dict[str, Any] = {
        "dora.profile-view.json": profile_view,
        "profile-lock.json": profile_lock,
        "source-atom-coverage.json": source_atom_coverage,
        "completeness.json": completeness,
        "governance-status.json": governance_status,
        "review-records.json": review_records,
        "challenge-records.json": challenge_records,
        "bank-review-checklist.json": review_checklist,
        "known-boundaries.json": _known_boundaries(),
    }

    copied_files: list[str] = []

    if external_schema_path is not None:
        mapping = compare_schema_file(act_id, external_schema_path)
        files["candidate-mapping-report.json"] = mapping
        shutil.copyfile(external_schema_path, out / "sample-internal-field-list.json")
        copied_files.append("sample-internal-field-list.json")
    else:
        files["candidate-mapping-report.json"] = {
            "schema": "actproof.external_schema_mapping.v1",
            "act_id": act_id,
            "mapping_status": "not_run",
            "note": "Provide --external-schema to include candidate mapping output.",
            "review_required": True,
        }

    if sample_report_path is not None:
        report = json.loads(Path(sample_report_path).read_text(encoding="utf-8"))
        files["prevalidation-report.json"] = build_prevalidation_run_report(act_id, report)
        shutil.copyfile(sample_report_path, out / "sample-draft-report.json")
        copied_files.append("sample-draft-report.json")
    else:
        sample = _sample_draft_report()
        files["sample-draft-report.json"] = sample
        files["prevalidation-report.json"] = build_prevalidation_run_report(act_id, sample)

    for name, payload in files.items():
        (out / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readme = _bank_poc_readme(act_id, files)
    (out / "README_BANK_POC.md").write_text(readme, encoding="utf-8")

    manifest = {
        "schema": BANK_POC_PACK_SCHEMA_ID,
        "act_id": act_id,
        "package": {"name": "actproof-events", "version": __version__},
        "directory": str(out),
        "files": sorted(set(files.keys()) | set(copied_files) | {"README_BANK_POC.md", "bank-poc-pack-manifest.json"}),
        "profile_semantic_hash": profile_view.get("profile_semantic_hash"),
        "governance_status_hash": governance_status.get("governance_status_hash"),
        "intended_use": "Local bank POC package for source-bound DORA profile inspection, mapping review and pre-validation.",
        "not_for": _known_boundaries()["not_for"],
        "generated_at": _utc_now(),
    }
    manifest["bank_poc_pack_hash"] = _stable_hash({k: v for k, v in manifest.items() if k not in {"bank_poc_pack_hash", "generated_at", "directory"}})
    (out / "bank-poc-pack-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _known_boundaries() -> dict[str, Any]:
    return {
        "schema": "actproof.known_boundaries.v1",
        "not_for": [
            "legal advice",
            "compliance certification",
            "supervisory approval",
            "factual verification of incident data",
            "regulatory submission",
            "cryptographic receipt verification",
            "bank SME approval",
            "external legal review",
        ],
        "bank_responsibility": [
            "own final legal/regulatory interpretation",
            "review source mappings before operational reliance",
            "approve internal field mappings under bank controls",
            "decide whether open challenge records are acceptable for the POC scope",
            "run ActProof locally or in an approved internal environment for sensitive data",
        ],
    }


def _sample_draft_report() -> dict[str, Any]:
    return {
        "entity_legal_identifier": "549300EXAMPLE00000001",
        "entity_legal_name": "Example Bank SA",
        "classification_criteria_triggered": ["clients_affected"],
    }


def _bank_poc_readme(act_id: str, files: dict[str, Any]) -> str:
    return f"""# ActProof bank POC pack

Profile: `{act_id}`
Package: `actproof-events {__version__}`

## What this pack is for

Run ActProof locally against one DORA initial-notification draft and one internal
field list. It shows missing required fields, high-judgement fields, source
atoms, evidence expectations, source-atom coverage, and where field names need
reviewed mapping.

## Files

""" + "\n".join(f"- `{name}`" for name in sorted(files)) + """
- `bank-poc-pack-manifest.json`
- `README_BANK_POC.md`

## Boundary

This pack is not legal advice, compliance certification, bank approval,
supervisory approval, factual verification or regulatory submission. Bank SMEs
own final interpretation and internal approval.
"""


__all__ = [
    "REVIEW_RECORDS_SCHEMA_ID",
    "CHALLENGE_RECORDS_SCHEMA_ID",
    "PROFILE_GOVERNANCE_STATUS_SCHEMA_ID",
    "BANK_POC_PACK_SCHEMA_ID",
    "list_review_records",
    "latest_review_record",
    "list_challenge_records",
    "build_governance_status",
    "validate_profile_governance",
    "build_bank_poc_pack",
]
