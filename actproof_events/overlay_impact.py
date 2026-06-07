# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Impact review between an ActProof profile change and a bank-owned overlay.

A bank overlay records bank-local mapping and review decisions against a pinned
ActProof profile hash. This module answers the change-control question that
follows from that design: when the public ActProof profile changes, which bank
mapping decisions, missing-required decisions, and review assumptions need to be
looked at again?

The output is deliberately conservative. It never migrates mappings, approves
carry-forward, decides legal materiality, or asserts regulatory compliance. When
in doubt, it asks for review.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from actproof_events import __version__
from actproof_events.bank_overlay import load_bank_overlay, compute_overlay_hash
from actproof_events.profile_diff import diff_profile_views, load_profile_view

BANK_OVERLAY_IMPACT_SCHEMA_ID = "actproof.bank_overlay_impact.v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _field_index(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for field in view.get("fields") or []:
        if isinstance(field, dict) and isinstance(field.get("field_id"), str):
            out[field["field_id"]] = field
    return out


def _diff_sets(profile_diff: dict[str, Any]) -> dict[str, set[str]]:
    field_changes = profile_diff.get("field_changes") if isinstance(profile_diff.get("field_changes"), dict) else {}
    review_changes = profile_diff.get("review_status_changes") or []
    return {
        "added": {x.get("field_id") for x in field_changes.get("added", []) if x.get("field_id")},
        "removed": {x.get("field_id") for x in field_changes.get("removed", []) if x.get("field_id")},
        "changed": {x.get("field_id") for x in field_changes.get("changed", []) if x.get("field_id")},
        "source_changed": {x.get("field_id") for x in profile_diff.get("source_atom_changes", []) if x.get("field_id")},
        "review_changed": {x.get("field_id") for x in review_changes if x.get("scope") == "field" and x.get("field_id")},
    }


def _changed_keys(profile_diff: dict[str, Any]) -> dict[str, list[str]]:
    field_changes = profile_diff.get("field_changes") if isinstance(profile_diff.get("field_changes"), dict) else {}
    out: dict[str, list[str]] = {}
    for row in field_changes.get("changed", []) or []:
        fid = row.get("field_id")
        if fid:
            out[fid] = list(row.get("changed_keys") or [])
    return out


def _mapping_refs(overlay: dict[str, Any]) -> set[str]:
    return {m.get("selected_actproof_field_id") for m in overlay.get("mappings") or [] if m.get("selected_actproof_field_id")}


def _missing_refs(overlay: dict[str, Any]) -> set[str]:
    return {m.get("actproof_field_id") for m in overlay.get("missing_required_field_decisions") or [] if m.get("actproof_field_id")}


def _impact_reasons(fid: str, sets: dict[str, set[str]]) -> list[str]:
    reasons: list[str] = []
    if fid in sets["removed"]:
        reasons.append("field_removed")
    if fid in sets["changed"]:
        reasons.append("field_changed")
    if fid in sets["source_changed"]:
        reasons.append("source_basis_changed")
    if fid in sets["review_changed"]:
        reasons.append("review_status_changed")
    return reasons


def _mapping_severity(fid: str, reasons: list[str], mapping: dict[str, Any]) -> str:
    if "field_removed" in reasons:
        return "blocking"
    decision = mapping.get("review_decision")
    if decision == "accepted" and reasons:
        return "review_required"
    if reasons:
        return "review_required"
    return "notice"


def _action_for_mapping(severity: str, reasons: list[str]) -> str:
    if severity == "blocking":
        return "replace_or_reject_mapping_before_overlay_carry_forward"
    if "source_basis_changed" in reasons:
        return "re_review_mapping_source_basis"
    if "review_status_changed" in reasons:
        return "re_review_mapping_review_status"
    if reasons:
        return "re_review_mapping"
    return "no_action"


def _field_required(field: dict[str, Any] | None) -> bool:
    return bool(field and field.get("required") is True)


def _new_required_impacts(
    overlay: dict[str, Any],
    old_fields: dict[str, dict[str, Any]],
    new_fields: dict[str, dict[str, Any]],
    sets: dict[str, set[str]],
    changed_keys: dict[str, list[str]],
) -> list[dict[str, Any]]:
    mapped = _mapping_refs(overlay)
    missing_decisions = _missing_refs(overlay)
    impacts: list[dict[str, Any]] = []

    for fid in sorted(sets["added"]):
        new_f = new_fields.get(fid)
        if _field_required(new_f) and fid not in mapped and fid not in missing_decisions:
            impacts.append({
                "impact_type": "new_required_field_without_overlay_decision",
                "field_id": fid,
                "severity": "blocking",
                "recommended_action": "create_missing_required_field_decision_or_update_internal_schema",
                "new_field": new_f,
            })

    for fid, keys in sorted(changed_keys.items()):
        if "required" in keys and not _field_required(old_fields.get(fid)) and _field_required(new_fields.get(fid)):
            if fid not in mapped and fid not in missing_decisions:
                impacts.append({
                    "impact_type": "field_became_required_without_overlay_decision",
                    "field_id": fid,
                    "severity": "blocking",
                    "recommended_action": "create_missing_required_field_decision_or_update_internal_schema",
                    "old_required": False,
                    "new_required": True,
                })
    return impacts


def _impacted_mappings(overlay: dict[str, Any], sets: dict[str, set[str]], changed_keys: dict[str, list[str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    impacted: list[dict[str, Any]] = []
    unaffected: list[dict[str, Any]] = []
    for mapping in overlay.get("mappings") or []:
        fid = mapping.get("selected_actproof_field_id")
        if not fid:
            continue
        reasons = _impact_reasons(fid, sets)
        summary = {
            "external_field": mapping.get("external_field"),
            "selected_actproof_field_id": fid,
            "review_decision": mapping.get("review_decision"),
            "mapping_status": mapping.get("mapping_status"),
            # preserve the bank's review ownership for the audit trail
            "reviewed_by": mapping.get("reviewed_by"),
            "reviewed_at": mapping.get("reviewed_at"),
        }
        if reasons:
            severity = _mapping_severity(fid, reasons, mapping)
            impacted.append({
                **summary,
                "impact_reasons": reasons,
                "changed_keys": changed_keys.get(fid, []),
                "severity": severity,
                "review_required": True,
                "recommended_action": _action_for_mapping(severity, reasons),
            })
        else:
            unaffected.append({**summary, "review_required": False})
    return impacted, unaffected


def _impacted_missing_decisions(
    overlay: dict[str, Any],
    old_fields: dict[str, dict[str, Any]],
    new_fields: dict[str, dict[str, Any]],
    sets: dict[str, set[str]],
    changed_keys: dict[str, list[str]],
) -> list[dict[str, Any]]:
    impacted: list[dict[str, Any]] = []
    for item in overlay.get("missing_required_field_decisions") or []:
        fid = item.get("actproof_field_id")
        if not fid:
            continue
        reasons = _impact_reasons(fid, sets)
        if fid in sets["removed"]:
            severity = "review_required"
            reasons = reasons or ["field_removed"]
            action = "review_missing_field_decision_removed_from_profile"
        elif "required" in changed_keys.get(fid, []) and _field_required(old_fields.get(fid)) and not _field_required(new_fields.get(fid)):
            severity = "review_required"
            reasons = list(set(reasons + ["field_no_longer_required"]))
            action = "review_whether_missing_required_decision_is_still_needed"
        elif reasons:
            severity = "review_required"
            action = "re_review_missing_required_field_decision"
        else:
            continue
        impacted.append({
            "actproof_field_id": fid,
            "decision": item.get("decision"),
            "owner": item.get("owner"),
            "impact_reasons": reasons,
            "changed_keys": changed_keys.get(fid, []),
            "severity": severity,
            "review_required": True,
            "recommended_action": action,
        })
    return impacted


def _external_only_recommendations(overlay: dict[str, Any], added: set[str]) -> list[dict[str, Any]]:
    if not added:
        return []
    out: list[dict[str, Any]] = []
    for item in overlay.get("external_only_fields") or []:
        out.append({
            "external_field": item.get("external_field"),
            "severity": "notice",
            "impact_reasons": ["new_actproof_fields_present"],
            "review_required": True,
            "recommended_action": "rerun_compare_schema_to_check_whether_new_profile_fields_match_external_only_fields",
            "new_fields_to_consider": sorted(added),
        })
    return out


def _recommended_actions(report: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if report.get("overlay_profile_hash_matches_new") is False:
        actions.append("Do not silently carry the overlay forward; review impact and update overlay hash only after bank review.")
    if report.get("new_required_field_impacts"):
        actions.append("Create missing-required-field decisions or update the internal schema for new required fields.")
    if report.get("impacted_mappings"):
        actions.append("Re-review impacted mapping decisions and record accept/reject/defer decisions in the bank overlay.")
    if report.get("impacted_missing_required_decisions"):
        actions.append("Re-review missing-required-field decisions affected by profile changes.")
    if report.get("external_only_field_recommendations"):
        actions.append("Rerun compare-schema to check whether new ActProof fields affect external-only fields.")
    if not actions:
        actions.append("No overlay-specific impact detected; retain audit record of the comparison.")
    return actions


def _impact_status(blocking_count: int, review_count: int, semantic_hash_changed: bool) -> str:
    if not semantic_hash_changed:
        return "no_profile_change"
    if blocking_count:
        return "blocking_review_required"
    if review_count:
        return "review_required"
    return "no_overlay_impact"


def build_overlay_impact_report(
    overlay: dict[str, Any],
    old_profile_view: dict[str, Any],
    new_profile_view: dict[str, Any] | None = None,
    *,
    old_label: str = "old_profile_view",
    new_label: str = "new_profile_view",
) -> dict[str, Any]:
    """Build a bank overlay impact report for a profile-view change.

    The report is a control artifact. It is descriptive and conservative: it
    identifies bank overlay decisions that require re-review; it does not
    migrate, approve, or determine legal materiality.

    If ``new_profile_view`` is omitted, the CURRENT profile for the overlay's act
    is built and used as the new view. This lets a bank check impact with just
    the overlay and the old profile-view it pinned against, without having to
    export the current profile separately.
    """
    act_id = overlay.get("act_id") or old_profile_view.get("act_id")
    if new_profile_view is None:
        # Build the current profile using the same convention the overlay pins
        # against (build_profile_view default), so hashes compare like-for-like.
        if not act_id:
            raise ValueError("cannot resolve current profile: no act_id on overlay or old profile-view")
        from actproof_events.exports import build_profile_view
        new_profile_view = build_profile_view(act_id)
    act_id = act_id or new_profile_view.get("act_id")
    if overlay.get("act_id") and old_profile_view.get("act_id") and overlay.get("act_id") != old_profile_view.get("act_id"):
        raise ValueError("overlay act_id does not match old profile-view act_id")
    if overlay.get("act_id") and new_profile_view.get("act_id") and overlay.get("act_id") != new_profile_view.get("act_id"):
        raise ValueError("overlay act_id does not match new profile-view act_id")

    profile_diff = diff_profile_views(old_profile_view, new_profile_view, old_label=old_label, new_label=new_label)
    if profile_diff.get("error"):
        return {
            "schema": BANK_OVERLAY_IMPACT_SCHEMA_ID,
            "error": profile_diff.get("error"),
            "profile_diff": profile_diff,
            "generated_at": _utc_now(),
        }

    old_hash = old_profile_view.get("profile_semantic_hash")
    new_hash = new_profile_view.get("profile_semantic_hash")
    overlay_hash = overlay.get("overlay_hash") or compute_overlay_hash(overlay)
    overlay_pinned_hash = overlay.get("profile_semantic_hash")
    sets = _diff_sets(profile_diff)
    keys = _changed_keys(profile_diff)
    old_fields = _field_index(old_profile_view)
    new_fields = _field_index(new_profile_view)

    impacted_mappings, unaffected_mappings = _impacted_mappings(overlay, sets, keys)
    impacted_missing = _impacted_missing_decisions(overlay, old_fields, new_fields, sets, keys)
    new_required = _new_required_impacts(overlay, old_fields, new_fields, sets, keys)
    external_recs = _external_only_recommendations(overlay, sets["added"])

    blocking_count = sum(1 for row in impacted_mappings + impacted_missing + new_required if row.get("severity") == "blocking")
    review_count = sum(1 for row in impacted_mappings + impacted_missing + external_recs if row.get("review_required")) + len(new_required)
    semantic_changed = bool(profile_diff.get("summary", {}).get("semantic_hash_changed"))
    status = _impact_status(blocking_count, review_count, semantic_changed)

    report: dict[str, Any] = {
        "schema": BANK_OVERLAY_IMPACT_SCHEMA_ID,
        "package": {"name": "actproof-events", "version": __version__},
        "act_id": act_id,
        "overlay_id": overlay.get("overlay_id"),
        "overlay_hash": overlay_hash,
        "old_profile_semantic_hash": old_hash,
        "new_profile_semantic_hash": new_hash,
        "overlay_pinned_profile_semantic_hash": overlay_pinned_hash,
        "profile_semantic_hash_changed": old_hash != new_hash,
        "overlay_profile_hash_matches_old": overlay_pinned_hash == old_hash,
        "overlay_profile_hash_matches_new": overlay_pinned_hash == new_hash,
        "impact_status": status,
        "ready_to_carry_forward": status in {"no_profile_change", "no_overlay_impact"} and overlay_pinned_hash == new_hash,
        "summary": {
            "accepted_mappings_impacted": sum(1 for m in impacted_mappings if m.get("review_decision") == "accepted"),
            "needs_review_mappings_impacted": sum(1 for m in impacted_mappings if m.get("review_decision") in {"needs_review", None}),
            "total_mappings_impacted": len(impacted_mappings),
            "missing_required_decisions_impacted": len(impacted_missing),
            "external_only_fields_recommended_for_review": len(external_recs),
            "new_required_field_impacts": len(new_required),
            "fields_added": profile_diff.get("summary", {}).get("fields_added", 0),
            "fields_removed": profile_diff.get("summary", {}).get("fields_removed", 0),
            "fields_changed": profile_diff.get("summary", {}).get("fields_changed", 0),
            "source_basis_changes": profile_diff.get("summary", {}).get("source_atom_changes", 0),
            "review_status_changes": profile_diff.get("summary", {}).get("review_status_changes", 0),
            "coverage_changed": bool(profile_diff.get("summary", {}).get("coverage_changes", 0)),
            "blocking_items": blocking_count,
            "review_items": review_count,
        },
        "impacted_mappings": impacted_mappings,
        "impacted_missing_required_decisions": impacted_missing,
        "new_required_field_impacts": new_required,
        "external_only_field_recommendations": external_recs,
        "unaffected_mappings": unaffected_mappings,
        "profile_diff": profile_diff,
        "recommended_actions": [],
        "boundary": {
            "intended_use": "Identify bank overlay decisions affected by a changed ActProof profile.",
            "not_for": [
                "automatic overlay migration",
                "automatic approval of mapping carry-forward",
                "legal-materiality determination",
                "compliance certification",
                "supervisory approval",
            ],
            "conservative_rule": "When a mapped field, source basis, required status or review status changes, bank review is required.",
        },
        "generated_at": _utc_now(),
    }
    report["recommended_actions"] = _recommended_actions(report)
    report["overlay_impact_report_hash"] = _stable_hash({k: v for k, v in report.items() if k not in {"overlay_impact_report_hash", "generated_at"}})
    return report


def diff_overlay_impact_files(
    overlay_path: str | Path,
    old_profile_view_path: str | Path,
    new_profile_view_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load files and build a bank overlay impact report.

    If ``new_profile_view_path`` is omitted, the current profile is used.
    """
    new_view = load_profile_view(new_profile_view_path) if new_profile_view_path else None
    return build_overlay_impact_report(
        load_bank_overlay(overlay_path),
        load_profile_view(old_profile_view_path),
        new_view,
        old_label=str(old_profile_view_path),
        new_label=str(new_profile_view_path) if new_profile_view_path else "current_profile",
    )


def write_overlay_impact_report(report: dict[str, Any], path: str | Path, *, compact: bool = False) -> None:
    indent = None if compact else 2
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


__all__ = [
    "BANK_OVERLAY_IMPACT_SCHEMA_ID",
    "build_overlay_impact_report",
    "diff_overlay_impact_files",
    "write_overlay_impact_report",
]
