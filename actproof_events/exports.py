# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Profile-view exports for source-bound ActProof catalogue entries.

The catalogue entry remains the canonical profile object. A profile view is a
deterministic, renderable projection for websites, APIs, MCP servers, audit
packs and compliance interfaces. It is intentionally richer than a summary,
but it is not a receipt and it is not a legal-compliance determination.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

from actproof_events import get_profile_view_schema_path
from actproof_events.services import (
    BOUNDARY,
    BOUNDARY_ID,
    CLAIM_FLAGS,
    CATALOGUE_ENTRY_HASH_BASIS,
    get_field,
    get_profile,
    list_fields,
    source_basis,
)

PROFILE_VIEW_SCHEMA_ID = "actproof.profile_view.v1"
PROFILE_SEMANTIC_HASH_BASIS = (
    "sha256 over canonical JSON with sorted keys and compact separators, "
    "excluding profile hash fields, hash-basis fields and provenance"
)
PROFILE_ARTIFACT_HASH_BASIS = (
    "sha256 over canonical JSON with sorted keys and compact separators, "
    "excluding profile hash fields and provenance.generated_at; "
    "including provenance.package_version"
)
# Backward-compatible alias for consumers introduced to the initial profile-view export.
PROFILE_VIEW_HASH_BASIS = PROFILE_SEMANTIC_HASH_BASIS
DEFAULT_PROFILE_VIEW_TYPE = "public_projection"

_HASH_FIELDS = {
    "profile_view_hash",
    "profile_view_hash_basis",
    "profile_semantic_hash",
    "profile_semantic_hash_basis",
    "profile_artifact_hash",
    "profile_artifact_hash_basis",
}


def _package_version() -> str:
    """Return the installed package version, degrading cleanly in source checkouts."""
    try:
        return metadata.version("actproof-events")
    except metadata.PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        if pyproject.exists():
            for line in pyproject.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("version ="):
                    return line.split("=", 1)[1].strip().strip("'\"")
        return "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _pct(n: int, d: int) -> float:
    return round((n / d) * 100, 1) if d else 0.0


def _strip_hash_fields(view: dict[str, Any]) -> dict[str, Any]:
    clone = copy.deepcopy(view)
    for key in _HASH_FIELDS:
        clone.pop(key, None)
    return clone


def _semantic_hashable_payload(view: dict[str, Any]) -> dict[str, Any]:
    """Return the version-independent semantic projection hash basis.

    The semantic hash is intended for the public reproducibility claim: if the
    catalogue/profile projection says the same thing, consumers should receive
    the same hash even when the exporting package version or generation time
    changes. Provenance remains present in the JSON file but does not define
    the profile semantics.
    """
    clone = _strip_hash_fields(view)
    clone.pop("provenance", None)
    return clone


def _artifact_hashable_payload(view: dict[str, Any]) -> dict[str, Any]:
    """Return the release-specific artifact hash basis.

    The artifact hash is useful for release/package traceability. It retains
    package-version provenance but excludes the volatile generation timestamp
    and all self-referential hash fields.
    """
    clone = _strip_hash_fields(view)
    provenance = clone.get("provenance")
    if isinstance(provenance, dict):
        provenance.pop("generated_at", None)
    return clone


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def compute_profile_semantic_hash(view: dict[str, Any]) -> str:
    """Compute the version-independent semantic hash of a profile view."""
    return _hash_payload(_semantic_hashable_payload(view))


def compute_profile_artifact_hash(view: dict[str, Any]) -> str:
    """Compute the release-specific artifact hash of a profile view."""
    return _hash_payload(_artifact_hashable_payload(view))


def compute_profile_view_hash(view: dict[str, Any]) -> str:
    """Compute the backward-compatible profile-view hash.

    This is an alias for the semantic hash. New consumers should prefer
    ``compute_profile_semantic_hash`` and read ``profile_semantic_hash``.
    """
    return compute_profile_semantic_hash(view)


def compute_profile_coverage(act_id: str, *, fields: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Compute projection coverage metrics for one ActProof profile.

    Coverage metrics are package-native so website builders and other consumers
    do not have to reimplement the same counting logic.
    """
    fields = fields if fields is not None else [
        get_field(act_id, row["field_id"])
        for row in list_fields(act_id, required_only=False)
    ]
    total = len(fields)
    required = sum(1 for f in fields if f.get("required"))
    optional = total - required
    field_level = sum(1 for f in fields if f.get("source_basis_scope") == "field")
    act_level = sum(1 for f in fields if f.get("source_basis_scope") == "act")
    fallback = sum(1 for f in fields if f.get("fallback_used") is True)
    evidence_field = sum(1 for f in fields if f.get("evidence_scope") == "field")
    evidence_profile = sum(1 for f in fields if f.get("evidence_scope") == "profile")
    scored = sum(1 for f in fields if f.get("interpretive_status") != "unscored")
    unscored = total - scored
    tiered = sum(1 for f in fields if f.get("disclosure_tier") != "untiered")
    untiered = total - tiered
    by_status: dict[str, int] = {}
    by_mapping_type: dict[str, int] = {}
    by_disclosure_tier: dict[str, int] = {}
    by_source_scope: dict[str, int] = {}
    for f in fields:
        status = str(f.get("interpretive_status") or "unscored")
        mapping_type = str(f.get("mapping_type") or "unscored")
        disclosure = str(f.get("disclosure_tier") or "untiered")
        source_scope = str(f.get("source_basis_scope") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_mapping_type[mapping_type] = by_mapping_type.get(mapping_type, 0) + 1
        by_disclosure_tier[disclosure] = by_disclosure_tier.get(disclosure, 0) + 1
        by_source_scope[source_scope] = by_source_scope.get(source_scope, 0) + 1

    return {
        "field_counts": {
            "total": total,
            "required": required,
            "optional": optional,
        },
        "field_source_basis": {
            "field_level": field_level,
            "act_level_fallback": act_level,
            "fallback_used": fallback,
            "coverage_ratio": _pct(field_level, total),
            "by_scope": dict(sorted(by_source_scope.items())),
        },
        "evidence_scope": {
            "field_level": evidence_field,
            "profile_level": evidence_profile,
        },
        "assessment": {
            "scored_fields": scored,
            "unscored_fields": unscored,
            "coverage_ratio": _pct(scored, total),
            "by_interpretive_status": dict(sorted(by_status.items())),
            "by_mapping_type": dict(sorted(by_mapping_type.items())),
        },
        "disclosure": {
            "tiered_fields": tiered,
            "untiered_fields": untiered,
            "coverage_ratio": _pct(tiered, total),
            "by_tier": dict(sorted(by_disclosure_tier.items())),
        },
    }


def build_profile_view(
    act_id: str,
    *,
    assessment_id: str | None = None,
    include_fields: bool = True,
    include_source_basis: bool = True,
    include_non_claims: bool = True,
    include_provenance: bool = True,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a rich public projection for one source-bound profile.

    Args:
        act_id: The ActProof act_type_id, for example
            ``op:eu.dora.ict_incident_notification_initial.v1``.
        assessment_id: Optional caller-defined assessment identifier to carry
            into provenance. It does not alter the canonical catalogue object.
        include_fields: Include the per-field projection rows.
        include_source_basis: Include act-level and field-level source basis.
        include_non_claims: Include machine-readable non-claims.
        include_provenance: Include package/build provenance.
        generated_at: Optional ISO timestamp override for reproducible builds.

    Returns:
        A JSON-serialisable profile-view dictionary. The canonical object remains
        the catalogue entry addressed by ``catalogue_entry_hash``.
    """
    profile = get_profile(act_id)
    field_rows = [
        get_field(act_id, row["field_id"])
        for row in list_fields(act_id, required_only=False)
    ]

    if not include_source_basis:
        for f in field_rows:
            f.pop("source_basis", None)
            f.pop("source_basis_scope", None)
            f.pop("fallback_used", None)

    coverage = compute_profile_coverage(act_id, fields=field_rows)
    required_labels = list(profile.get("required_evidence_labels") or [])
    source_instruments = source_basis(profile) if include_source_basis else []
    non_claims = list(profile.get("non_claims") or []) if include_non_claims else []

    projection: dict[str, Any] = {
        "profile_view_schema": PROFILE_VIEW_SCHEMA_ID,
        "profile_view_type": DEFAULT_PROFILE_VIEW_TYPE,
        "profile_view_semantics": "derived renderable view, not the canonical catalogue entry",
        "act_id": act_id,
        "assessment_id": assessment_id,
        "generated_from": "actproof-events public export layer",
        "canonical_object": {
            "kind": "actproof-events catalogue entry",
            "act_id": act_id,
            "catalogue_entry_hash": profile.get("catalogue_entry_hash"),
            "catalogue_entry_hash_basis": profile.get("catalogue_entry_hash_basis") or CATALOGUE_ENTRY_HASH_BASIS,
        },
        "profile": {
            "display_name": profile.get("display_name"),
            "claim_type": profile.get("claim_type"),
            "version": profile.get("version"),
            "maturity": (profile.get("profile_status") or {}).get("maturity"),
            "regulatory_citation": profile.get("regulatory_citation") or {},
            "catalogue_entry_hash": profile.get("catalogue_entry_hash"),
            "catalogue_entry_hash_basis": profile.get("catalogue_entry_hash_basis") or CATALOGUE_ENTRY_HASH_BASIS,
            "compatible_with_receipts": bool(profile.get("compatible_with_receipts")),
            "boundary": profile.get("boundary") or BOUNDARY,
            "boundary_id": profile.get("boundary_id") or BOUNDARY_ID,
            "claim_flags": profile.get("claim_flags") or CLAIM_FLAGS,
            "non_claims": non_claims,
            "required_evidence_labels": required_labels,
            "interpretive_summary": profile.get("interpretive_summary") or {},
        },
        "source_basis": {
            "scope": "act",
            "instruments": source_instruments,
        },
        "evidence": {
            "required_evidence_labels": required_labels,
            "evidence_scope": "profile",
        },
        "coverage": coverage,
        "non_claims": non_claims,
        "boundary": {
            "boundary_id": profile.get("boundary_id") or BOUNDARY_ID,
            "text": profile.get("boundary") or BOUNDARY,
        },
    }

    if include_fields:
        projection["fields"] = field_rows

    if include_provenance:
        projection["provenance"] = {
            "generated_from": "actproof-events",
            "package_name": "actproof-events",
            "package_version": _package_version(),
            "export_function": "actproof_events.exports.build_profile_view",
            "cli_command": "actproof-events export-profile-view",
            "act_id": act_id,
            "assessment_id": assessment_id,
            "catalogue_entry_hash": profile.get("catalogue_entry_hash"),
            "catalogue_entry_hash_basis": profile.get("catalogue_entry_hash_basis") or CATALOGUE_ENTRY_HASH_BASIS,
            "profile_view_schema": PROFILE_VIEW_SCHEMA_ID,
            "profile_view_type": DEFAULT_PROFILE_VIEW_TYPE,
            "profile_view_semantics": projection["profile_view_semantics"],
            "generated_at": generated_at or _utc_now(),
        }

    projection["profile_semantic_hash_basis"] = PROFILE_SEMANTIC_HASH_BASIS
    projection["profile_artifact_hash_basis"] = PROFILE_ARTIFACT_HASH_BASIS
    projection["profile_view_hash_basis"] = PROFILE_VIEW_HASH_BASIS
    projection["profile_semantic_hash"] = compute_profile_semantic_hash(projection)
    projection["profile_view_hash"] = projection["profile_semantic_hash"]
    projection["profile_artifact_hash"] = compute_profile_artifact_hash(projection)
    return projection


def write_profile_view(
    act_id: str,
    out: str | Path,
    *,
    assessment_id: str | None = None,
    pretty: bool = True,
    include_fields: bool = True,
    include_source_basis: bool = True,
    include_non_claims: bool = True,
    include_provenance: bool = True,
    validate: bool = False,
) -> dict[str, Any]:
    """Build and write a profile view JSON file, returning the payload."""
    payload = build_profile_view(
        act_id,
        assessment_id=assessment_id,
        include_fields=include_fields,
        include_source_basis=include_source_basis,
        include_non_claims=include_non_claims,
        include_provenance=include_provenance,
    )
    if validate:
        errors = validate_profile_view(payload)
        if errors:
            raise ValueError(
                "generated projection failed profile_view.v1 schema validation: "
                + "; ".join(errors)
            )

    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    if pretty:
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    else:
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    path.write_text(text, encoding="utf-8")
    return payload



def get_profile_view_schema() -> dict[str, Any]:
    """Load the packaged profile-view JSON Schema as a dictionary.

    In an installed wheel the schema lives under ``data/schemas/``. In a raw
    source checkout that built tree is not materialised, so this falls back to
    the repository source path ``spec/schemas/`` when available.

    Raises:
        FileNotFoundError: if the schema cannot be located in either place.
    """
    schema_path = get_profile_view_schema_path()
    if not schema_path.exists():
        repo_path = (
            Path(__file__).resolve().parents[1]
            / "spec"
            / "schemas"
            / "profile_view.v1.schema.json"
        )
        if repo_path.exists():
            schema_path = repo_path
        else:
            raise FileNotFoundError(
                "profile_view.v1 schema not found in the installed package "
                f"({schema_path}) or the repository source tree ({repo_path})."
            )
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_profile_view(view: dict[str, Any]) -> list[str]:
    """Validate a profile-view projection against the packaged schema.

    Returns a list of human-readable validation error messages. An empty list
    means the projection conforms. This is intentionally non-raising so callers
    (including :func:`verify_profile_view`) can aggregate results.

    Raises:
        RuntimeError: if the optional ``jsonschema`` dependency is not
            installed, or if the schema file cannot be located.
    """
    try:
        from jsonschema.validators import Draft202012Validator  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "profile-view validation requires jsonschema; "
            "install actproof-events[schema-validation]"
        ) from exc

    try:
        schema = get_profile_view_schema()
    except FileNotFoundError as exc:
        raise RuntimeError(str(exc)) from exc

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(view), key=lambda e: list(e.path))
    messages: list[str] = []
    for err in errors:
        location = "/".join(str(p) for p in err.path) or "<root>"
        messages.append(f"{location}: {err.message}")
    return messages


def verify_profile_view(view: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Verify a profile-view artifact against what this release guarantees.

    Accepts either a parsed projection dict or a path to a profile-view JSON
    file. Returns a structured report. This verifier checks only what
    actproof-events 1.7.0 actually ships:

      * ``valid_schema``          — conforms to the bundled profile_view.v1 schema.
      * ``semantic_hash_matches`` — recomputed profile_semantic_hash equals the
                                     stored one (version-independent identity).
      * ``artifact_hash_matches`` — recomputed profile_artifact_hash equals the
                                     stored one (release-specific identity).
      * ``catalogue_entry_hash_present`` — the canonical catalogue hash is carried.

    Field-level source binding does not exist in 1.7.0, so the report does not
    claim it is verified. It surfaces the current source-basis coverage as a
    forward-looking warning, which is the honest signal for the next release.

    ``ok`` is True only when every hard check passes. Warnings describe known,
    disclosed limitations and do not set ``ok`` to False.
    """
    if isinstance(view, (str, Path)):
        view = json.loads(Path(view).read_text(encoding="utf-8"))

    report: dict[str, Any] = {
        "ok": False,
        "valid_schema": False,
        "semantic_hash_matches": False,
        "artifact_hash_matches": False,
        "catalogue_entry_hash_present": False,
        "errors": [],
        "warnings": [],
    }

    try:
        schema_errors = validate_profile_view(view)
        report["valid_schema"] = not schema_errors
        report["errors"].extend(schema_errors)
    except RuntimeError as exc:
        report["warnings"].append(str(exc))
        report["valid_schema"] = None  # could not be checked

    stored_semantic = view.get("profile_semantic_hash")
    stored_artifact = view.get("profile_artifact_hash") or view.get("profile_view_hash")

    recomputed_semantic = compute_profile_semantic_hash(view)
    recomputed_artifact = compute_profile_artifact_hash(view)

    report["semantic_hash_matches"] = bool(
        stored_semantic and stored_semantic == recomputed_semantic
    )
    report["artifact_hash_matches"] = bool(
        stored_artifact and stored_artifact == recomputed_artifact
    )
    report["profile_semantic_hash"] = recomputed_semantic
    report["profile_artifact_hash"] = recomputed_artifact

    if stored_semantic and not report["semantic_hash_matches"]:
        report["errors"].append(
            f"profile_semantic_hash mismatch: stored {stored_semantic}, "
            f"recomputed {recomputed_semantic}"
        )
    if stored_artifact and not report["artifact_hash_matches"]:
        report["errors"].append(
            f"profile_artifact_hash mismatch: stored {stored_artifact}, "
            f"recomputed {recomputed_artifact}"
        )

    provenance = view.get("provenance") or {}
    catalogue_hash = provenance.get("catalogue_entry_hash") or (
        view.get("canonical_object") or {}
    ).get("catalogue_entry_hash")
    report["catalogue_entry_hash_present"] = bool(catalogue_hash)
    if catalogue_hash:
        report["catalogue_entry_hash"] = catalogue_hash
    else:
        report["errors"].append("no catalogue_entry_hash carried in the artifact")

    coverage = view.get("coverage") or {}
    basis = coverage.get("field_source_basis") or {}
    fallback_used = basis.get("fallback_used")
    field_level = basis.get("field_level")
    if field_level == 0 and fallback_used:
        report["warnings"].append(
            f"{fallback_used} fields use act-level source fallback; "
            f"field-level source binding is not present in this release"
        )
    report["field_derivations_complete"] = bool(field_level) and not fallback_used

    hard_checks = [
        report["semantic_hash_matches"],
        report["artifact_hash_matches"],
        report["catalogue_entry_hash_present"],
    ]
    if report["valid_schema"] is not None:
        hard_checks.append(report["valid_schema"])
    report["ok"] = all(hard_checks)
    return report


def _print_usage() -> None:
    print("actproof-events - public profile-view export utilities")
    print("")
    print("Usage:")
    print("  actproof-events export-profile-view ACT_ID --out profile-view.json [--pretty] [--validate]")
    print("")
    print("Example:")
    print("  actproof-events export-profile-view op:eu.dora.ict_incident_notification_initial.v1 --out dora.profile-view.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="actproof-events", description="ActProof Events export utilities")
    sub = parser.add_subparsers(dest="command")

    export = sub.add_parser("export-profile-view", help="Generate a public profile-view JSON projection")
    export.add_argument("act_id", help="ActProof act_type_id to export")
    export.add_argument("--out", required=True, help="Output JSON path")
    export.add_argument("--assessment-id", default=None, help="Optional caller-defined assessment id")
    export.add_argument("--pretty", action="store_true", help="Write indented JSON. This is the default.")
    export.add_argument("--compact", action="store_true", help="Write compact JSON instead of indented JSON")
    export.add_argument("--no-fields", action="store_true", help="Omit per-field rows")
    export.add_argument("--no-source-basis", action="store_true", help="Omit source-basis entries")
    export.add_argument("--no-non-claims", action="store_true", help="Omit non-claims from the projection")
    export.add_argument("--no-provenance", action="store_true", help="Omit provenance block")
    export.add_argument("--validate", action="store_true", help="Validate the generated projection against the packaged schema before writing")

    verify = sub.add_parser(
        "verify-profile-view",
        help="Verify an existing profile-view JSON (schema + both hashes + catalogue hash)",
    )
    verify.add_argument("path", help="Path to a profile-view JSON file to verify")

    args = parser.parse_args(argv)
    if args.command is None:
        _print_usage()
        return 0

    if args.command == "verify-profile-view":
        try:
            report = verify_profile_view(args.path)
        except Exception as exc:
            print(f"actproof-events: verify failed: {exc}", file=sys.stderr)
            return 1
        print(f"verifying {args.path}")
        print(f"  schema valid           : {report['valid_schema']}")
        print(f"  semantic hash matches  : {report['semantic_hash_matches']}")
        print(f"  artifact hash matches  : {report['artifact_hash_matches']}")
        print(f"  catalogue hash present  : {report['catalogue_entry_hash_present']}")
        print(f"  profile_semantic_hash  : {report.get('profile_semantic_hash')}")
        print(f"  profile_artifact_hash  : {report.get('profile_artifact_hash')}")
        for w in report["warnings"]:
            print(f"  warning: {w}")
        for e in report["errors"]:
            print(f"  error  : {e}", file=sys.stderr)
        print(f"  OK                      : {report['ok']}")
        return 0 if report["ok"] else 1

    if args.command != "export-profile-view":
        parser.error(f"unknown command: {args.command}")

    try:
        payload = write_profile_view(
            args.act_id,
            args.out,
            assessment_id=args.assessment_id,
            pretty=not args.compact,
            include_fields=not args.no_fields,
            include_source_basis=not args.no_source_basis,
            include_non_claims=not args.no_non_claims,
            include_provenance=not args.no_provenance,
            validate=args.validate,
        )
    except Exception as exc:
        print(f"actproof-events: export failed: {exc}", file=sys.stderr)
        return 1

    field_count = (payload.get("coverage") or {}).get("field_counts", {}).get("total")
    print(f"wrote {args.out}")
    if field_count is not None:
        print(f"fields: {field_count}")
    print(f"profile_semantic_hash: {payload.get('profile_semantic_hash')}")
    print(f"profile_artifact_hash: {payload.get('profile_artifact_hash')}")
    return 0


__all__ = [
    "PROFILE_VIEW_SCHEMA_ID",
    "PROFILE_VIEW_HASH_BASIS",
    "PROFILE_SEMANTIC_HASH_BASIS",
    "PROFILE_ARTIFACT_HASH_BASIS",
    "build_profile_view",
    "write_profile_view",
    "compute_profile_coverage",
    "compute_profile_view_hash",
    "compute_profile_semantic_hash",
    "compute_profile_artifact_hash",
    "get_profile_view_schema",
    "validate_profile_view",
    "verify_profile_view",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
