# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Candidate external-schema mapping for ActProof profiles.

This module deliberately emits *candidates for human review*, never final or
legally authoritative mappings. External field names are not universal, and an
ActProof field_id is only canonical inside an ActProof profile. The safe bridge
between a bank/vendor/GRC schema and ActProof is an inspectable candidate report
that shows why a field may correspond to an ActProof field and where review is
required.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from actproof_events import __version__
from actproof_events.exports import build_profile_view
from actproof_events.services import BOUNDARY, BOUNDARY_ID, list_fields
from actproof_events.source_binding import explain_field_source, get_profile_completeness

EXTERNAL_SCHEMA_MAPPING_SCHEMA_ID = "actproof.external_schema_mapping.v1"
MAPPING_STATUS_CANDIDATE = "candidate_review_required"

_STOP_TOKENS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "code", "data", "date",
    "field", "for", "from", "id", "identifier", "in", "is", "of", "on", "or",
    "ref", "reference", "report", "reporting", "the", "to", "type", "value",
}
_SYNONYMS = {
    "lei": "legal entity identifier",
    "legalentityidentifier": "legal entity identifier",
    "nca": "competent authority",
    "authority": "competent authority",
    "classification": "classification criteria",
    "criteria": "classification criteria",
    "criterion": "classification criteria",
    "major": "classification criteria",
    "bcp": "business continuity plan",
    "continuity": "business continuity plan",
    "provider": "third party provider",
    "supplier": "third party provider",
    "outsourced": "outsourcing arrangement",
    "outsourcing": "outsourcing arrangement",
    "country": "member state",
    "countries": "member states",
    "ms": "member states",
    "detect": "detection",
    "detected": "detection",
    "discover": "discovery",
    "discovered": "discovery",
    "email": "email",
    "mail": "email",
    "currency": "currency",
    "amount": "financial amount",
    "clients": "clients affected",
    "customers": "clients affected",
    "gdpr": "gdpr breach notification",
    "nis2": "nis2 notification",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _split_identifier(text: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    return text.lower().strip()


def _tokens(*parts: Any) -> set[str]:
    raw = " ".join(str(p) for p in parts if p not in (None, ""))
    raw = _split_identifier(raw)
    expanded: list[str] = []
    for tok in raw.split():
        expanded.append(tok)
        if tok in _SYNONYMS:
            expanded.extend(_split_identifier(_SYNONYMS[tok]).split())
    return {t for t in expanded if t and t not in _STOP_TOKENS and len(t) > 1}


def _field_label(field_id: str) -> str:
    return field_id.replace("_", " ")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _string_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _extract_external_fields(payload: Any) -> tuple[str | None, list[dict[str, Any]], list[str]]:
    """Extract external field descriptors from common schema shapes.

    Supported inputs are intentionally broad but conservative: JSON Schema
    ``properties``, ``fields`` arrays, ``columns`` arrays, plain lists and simple
    report-like objects. The extractor does not infer legal equivalence; it only
    normalises candidate field metadata for scoring.
    """
    warnings: list[str] = []
    external_system: str | None = None
    fields: list[dict[str, Any]] = []

    def add_field(obj: Any, *, required_hint: bool | None = None, source: str = "unknown") -> None:
        if isinstance(obj, str):
            fields.append({
                "external_field": obj,
                "label": obj,
                "type": None,
                "description": None,
                "required": required_hint,
                "source": source,
                "source_atoms": [],
            })
            return
        if not isinstance(obj, dict):
            warnings.append(f"ignored non-field entry from {source}")
            return
        name = (
            obj.get("external_field") or obj.get("field") or obj.get("field_id") or
            obj.get("name") or obj.get("id") or obj.get("key") or obj.get("path")
        )
        if not name:
            warnings.append(f"ignored field entry without name/id from {source}")
            return
        fields.append({
            "external_field": str(name),
            "label": _string_or_none(obj.get("label") or obj.get("title") or obj.get("display_name") or name),
            "type": _string_or_none(obj.get("type") or obj.get("format") or obj.get("data_type")),
            "description": _string_or_none(obj.get("description") or obj.get("help") or obj.get("note")),
            "required": bool(obj.get("required")) if obj.get("required") is not None else required_hint,
            "source": source,
            "source_atoms": [str(x) for x in _as_list(obj.get("source_atoms") or obj.get("source_atom_ids"))],
            "celex": _string_or_none(obj.get("celex")),
            "locator": obj.get("locator") if isinstance(obj.get("locator"), dict) else None,
        })

    if isinstance(payload, list):
        for item in payload:
            add_field(item, source="root_list")
        return external_system, fields, warnings

    if not isinstance(payload, dict):
        raise TypeError("external schema must be a JSON object or array")

    external_system = _string_or_none(
        payload.get("external_system") or payload.get("system") or payload.get("name") or payload.get("title")
    )
    required_names = {str(x) for x in _as_list(payload.get("required"))}

    for key in ("fields", "columns"):
        if isinstance(payload.get(key), list):
            for item in payload[key]:
                add_field(item, source=key)

    properties = payload.get("properties")
    if isinstance(properties, dict):
        for name, spec in properties.items():
            if isinstance(spec, dict):
                enriched = dict(spec)
                enriched.setdefault("name", name)
                add_field(enriched, required_hint=name in required_names, source="json_schema_properties")
            else:
                add_field({"name": name, "type": type(spec).__name__}, required_hint=name in required_names, source="object_properties")

    # If no schema-like fields were found, treat a plain object as a sample report
    # and map its top-level keys. This is useful for quick POC checks.
    if not fields:
        reserved = {"schema", "external_system", "system", "name", "title", "required", "description"}
        for name, value in payload.items():
            if name in reserved:
                continue
            add_field({"name": name, "type": type(value).__name__}, source="sample_object")

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for f in fields:
        key = f["external_field"]
        if key in seen:
            warnings.append(f"duplicate external field ignored: {key}")
            continue
        seen.add(key)
        unique.append(f)
    return external_system, unique, warnings


def _actproof_field_index(act_id: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in list_fields(act_id, required_only=False):
        exp = explain_field_source(act_id, row["field_id"])
        source_atoms = exp.get("source_atoms") or []
        rows[row["field_id"]] = {
            **row,
            "label": _field_label(row["field_id"]),
            "source_atoms": list(source_atoms),
            "binding_granularity": exp.get("binding_granularity"),
            "release_scope": exp.get("release_scope"),
        }
    return rows


def _score_candidate(external: dict[str, Any], field: dict[str, Any]) -> tuple[float, list[str], dict[str, Any]]:
    ext_tokens = _tokens(
        external.get("external_field"), external.get("label"), external.get("description"), external.get("type")
    )
    fp_tokens = _tokens(field.get("field_id"), field.get("label"), field.get("rationale"), *(field.get("evidence_labels") or []))
    matched_tokens = sorted(ext_tokens & fp_tokens)
    token_union = ext_tokens | fp_tokens
    token_score = (len(matched_tokens) / max(len(ext_tokens), 1)) if ext_tokens else 0.0
    matched_by: list[str] = []
    details: dict[str, Any] = {"matched_tokens": matched_tokens}

    score = 0.0
    if external.get("external_field") == field.get("field_id"):
        score += 0.65
        matched_by.append("field_id_exact")
    elif _split_identifier(external.get("external_field", "")) == _split_identifier(field.get("field_id", "")):
        score += 0.55
        matched_by.append("field_id_normalised")

    if "lei" in ext_tokens and field.get("field_id") == "entity_legal_identifier":
        score += 0.42
        matched_by.append("lei_acronym")

    if matched_tokens:
        score += min(0.45, token_score * 0.45)
        matched_by.append("semantic_tokens")

    ext_type = str(external.get("type") or "").lower()
    field_type = str(field.get("type") or "").lower()
    type_match = False
    if ext_type and field_type:
        type_match = ext_type == field_type or ext_type in field_type or field_type in ext_type
        if not type_match and ext_type in {"array", "list"} and "list" in field_type:
            type_match = True
        if not type_match and field_type in {"array", "list"} and "list" in ext_type:
            type_match = True
    if type_match:
        score += 0.12
        matched_by.append("data_type")

    ext_atoms = set(external.get("source_atoms") or [])
    field_atoms = set(field.get("source_atoms") or [])
    atom_overlap = sorted(ext_atoms & field_atoms)
    if atom_overlap:
        score += 0.30
        matched_by.append("source_atom_overlap")
        details["source_atom_overlap"] = atom_overlap

    # Do not inflate weak matches just because common terms happen to overlap.
    if len(matched_tokens) == 1 and not any(m in matched_by for m in ("field_id_exact", "field_id_normalised", "source_atom_overlap")):
        score = min(score, 0.20)

    details["token_jaccard"] = round(len(matched_tokens) / len(token_union), 3) if token_union else 0.0
    return min(score, 1.0), matched_by or ["no_meaningful_signal"], details


def _candidate_strength(score: float) -> str:
    if score >= 0.62:
        return "strong"
    if score >= 0.30:
        return "medium"
    return "weak"


def _candidate_limit(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return candidates[: max(1, limit)]


def compare_schema(
    act_id: str,
    external_schema: dict[str, Any] | list[Any],
    *,
    external_system: str | None = None,
    max_candidates_per_field: int = 3,
    minimum_strength: str = "medium",
) -> dict[str, Any]:
    """Compare an external field list/schema to an ActProof profile.

    Returns a mapping report containing candidates only. Every candidate is
    marked ``candidate_review_required`` and ``review_required: true``. The
    function never declares that a field is conclusively mapped.
    """
    ext_system, external_fields, extraction_warnings = _extract_external_fields(external_schema)
    if external_system:
        ext_system = external_system
    profile_fields = _actproof_field_index(act_id)
    view = build_profile_view(act_id)
    completeness = get_profile_completeness(act_id)

    threshold = {"weak": 0.01, "medium": 0.30, "strong": 0.62}.get(minimum_strength, 0.30)
    candidate_rows: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    unmapped_external: list[dict[str, Any]] = []
    candidate_targets: set[str] = set()

    for external in external_fields:
        scored: list[dict[str, Any]] = []
        for field_id, field in profile_fields.items():
            score, matched_by, details = _score_candidate(external, field)
            if score >= threshold:
                scored.append({
                    "actproof_field_id": field_id,
                    "actproof_required": bool(field.get("required")),
                    "candidate_strength": _candidate_strength(score),
                    "candidate_score": round(score, 3),
                    "mapping_status": MAPPING_STATUS_CANDIDATE,
                    "review_required": True,
                    "matched_by": matched_by,
                    "match_details": details,
                    "source_atoms": field.get("source_atoms") or [],
                    "binding_granularity": field.get("binding_granularity"),
                    "evidence_labels": field.get("evidence_labels") or [],
                    "warnings": [
                        "Candidate only: human review required before operational or reporting use.",
                        "Do not rely on field-name similarity alone.",
                    ],
                })
        scored.sort(key=lambda x: (-x["candidate_score"], x["actproof_field_id"]))
        selected = _candidate_limit(scored, max_candidates_per_field) if scored else []
        if not selected:
            unmapped_external.append({
                "external_field": external["external_field"],
                "label": external.get("label"),
                "reason": "no_candidate_above_threshold",
                "review_required": True,
            })
            continue
        for candidate in selected:
            candidate_targets.add(candidate["actproof_field_id"])
        row = {
            "external_field": external["external_field"],
            "external_label": external.get("label"),
            "external_type": external.get("type"),
            "external_description": external.get("description"),
            "mapping_status": MAPPING_STATUS_CANDIDATE,
            "review_required": True,
            "candidates": selected,
        }
        candidate_rows.append(row)
        if len(selected) > 1 and selected[0]["candidate_score"] - selected[1]["candidate_score"] <= 0.12:
            ambiguous.append({
                "external_field": external["external_field"],
                "reason": "top_candidates_close_score",
                "review_required": True,
                "candidate_field_ids": [c["actproof_field_id"] for c in selected],
            })

    required_fields = {fid for fid, field in profile_fields.items() if field.get("required")}
    required_without_candidate = sorted(required_fields - candidate_targets)

    report = {
        "schema": EXTERNAL_SCHEMA_MAPPING_SCHEMA_ID,
        "act_id": act_id,
        "external_system": ext_system or "unspecified_external_schema",
        "package": {"name": "actproof-events", "version": __version__},
        "profile": {
            "profile_semantic_hash": view.get("profile_semantic_hash"),
            "catalogue_entry_hash": (view.get("canonical_object") or {}).get("catalogue_entry_hash"),
            "field_id_policy": (completeness.get("field_id_policy") or {}),
        },
        "mapping_policy": {
            "mapping_status": MAPPING_STATUS_CANDIDATE,
            "review_required": True,
            "candidate_strength_values": ["weak", "medium", "strong"],
            "not_authoritative": True,
            "field_ids_universal": False,
            "do_not_map_by": ["field name alone", "AI paraphrase alone", "vendor label alone", "form position alone"],
            "safe_use": "Use this report to prepare human-reviewed schema alignment, not as a final mapping decision.",
        },
        "summary": {
            "external_field_count": len(external_fields),
            "candidate_mapped_external_fields": len(candidate_rows),
            "unmapped_external_field_count": len(unmapped_external),
            "ambiguous_mapping_count": len(ambiguous),
            "actproof_required_total": len(required_fields),
            "actproof_required_without_candidate_count": len(required_without_candidate),
        },
        "mappings": candidate_rows,
        "unmapped_external_fields": unmapped_external,
        "missing_actproof_required_fields": required_without_candidate,
        "ambiguous_mappings": ambiguous,
        "extraction_warnings": extraction_warnings,
        "non_claims": [
            "candidate schema mapping only",
            "does not certify field equivalence",
            "does not certify compliance",
            "does not verify external schema semantics",
            "does not replace bank, legal, regulatory, audit or product-owner review",
        ],
        "boundary": BOUNDARY,
        "boundary_id": BOUNDARY_ID,
        "generated_at": _utc_now(),
    }
    return report


def compare_schema_file(act_id: str, path: str | Path, **kwargs: Any) -> dict[str, Any]:
    """Load an external JSON schema/field list and run :func:`compare_schema`."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return compare_schema(act_id, payload, **kwargs)


__all__ = [
    "EXTERNAL_SCHEMA_MAPPING_SCHEMA_ID",
    "MAPPING_STATUS_CANDIDATE",
    "compare_schema",
    "compare_schema_file",
]
