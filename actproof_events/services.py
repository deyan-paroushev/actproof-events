"""Read-only services for source-bound ActProof profiles.

Dependency-free shared core behind the human field browser, the optional REST
API, and the optional MCP server. Build the ProfileView once, expose it three
ways.

This is the merged version. It keeps the package home, the function set, and
the thin api/mcp wrappers, and it re-injects the layer that makes this ActProof
rather than a generic field API:

  * per-field ``origin`` (direct / derived / interpretive / unscored) and the
    ``rationale``, read from the evidence-layer scores, so a caller can see
    where human judgement entered;
  * the real, machine-readable ``non_claims`` for the profile (the specific
    "does not prove" statements), not a generic capability flag dict;
  * a ``boundary`` string carried on every grounded answer, because the API and
    the MCP server hand interpretation to a machine and the doubt must travel
    with the data.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from actproof_events import get_catalogue_path, list_catalogue_entries

# ---------------------------------------------------------------------------
# Boundary. Travels with every grounded answer.
# ---------------------------------------------------------------------------
BOUNDARY = (
    "ActProof shows what a machine-readable profile claims and where it came "
    "from. It does not certify legal compliance and is not legal advice."
)
# Stable id so consumers can dedupe or reference the boundary without re-parsing
# the prose. The full text still travels once at the top of each payload.
BOUNDARY_ID = "actproof.boundary.v1"

# Generic capability denials, kept as machine-friendly flags. The authoritative
# boundary for a given profile is its real ``non_claims`` array (see below).
CLAIM_FLAGS = {
    "legal_advice": False,
    "legal_certification": False,
    "supervisory_approval": False,
    "compliance_determination": False,
}

# interpretive_load -> origin label, from the evidence-layer scoring rubric.
# Evidence-layer rubric. Frozen as evidence_layer_complexity.v1. The scored data
# already uses the full 0..4 scale, so mapping_type and load agree by construction.
#   direct 0, normalised 1, transformed 2, reconciled 3, modelled 4
# The short interpretive_status collapses these: 0 -> direct, 1..2 -> derived,
# 3..4 -> interpretive. mapping_type and interpretive_load are exposed alongside
# so the nuance the short label drops is never lost.
RUBRIC_ID = "evidence_layer_complexity.v1"

_LOAD_TO_MAPPING = {0: "direct", 1: "normalised", 2: "transformed", 3: "reconciled", 4: "modelled"}
_MAPPING_TYPES = set(_LOAD_TO_MAPPING.values())


def _status_from_load(load: int | None) -> str:
    """Short, agent-facing label. direct | derived | interpretive | unscored."""
    if load is None:
        return "unscored"
    if load <= 0:
        return "direct"
    if load <= 2:
        return "derived"
    return "interpretive"


def _mapping_type(row: dict[str, Any] | None) -> str | None:
    """The five-term mapping class, taken from the scorer's rationale prefix and
    validated against the rubric. Falls back to the load table if the prefix is
    not a known term."""
    if not row:
        return None
    prefix = re.split(r"[.,]", row.get("rationale") or "")[0].strip().lower()
    if prefix in _MAPPING_TYPES:
        return prefix
    return _LOAD_TO_MAPPING.get(row.get("interpretive_load"))


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _normalise_act_id(act_id: str) -> str:
    return act_id.strip()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _profile_paths(catalogue_root: Path | None = None) -> list[Path]:
    if catalogue_root is None:
        try:
            bundled = list_catalogue_entries()
            if bundled:
                return bundled
        except Exception:
            pass
        # Source-checkout fallback: editable installs and repo runs do not
        # always have actproof_events/data populated before a wheel build.
        source_root = Path(__file__).resolve().parents[1] / "catalogue" / "acts"
        catalogue_root = source_root if source_root.exists() else get_catalogue_path()
    root = catalogue_root or get_catalogue_path()
    paths: list[Path] = []
    for p in sorted(root.rglob("*.json")):
        parts = set(p.parts)
        if "_deprecated" in parts or p.name.endswith(".test_vectors.json"):
            continue
        try:
            data = _load_json(p)
        except Exception:
            continue
        if data.get("act_type_id"):
            paths.append(p)
    return paths


@lru_cache(maxsize=1)
def _scores_index() -> dict[str, dict[str, dict[str, Any]]]:
    """Evidence-layer scores, keyed [act_type_id][field] -> row.

    Loaded from the analysis bundle. Absent in a minimal wheel install, in
    which case every field degrades cleanly to ``interpretive_status == 'unscored'``.
    """
    candidates = [
        # source checkout / editable install
        Path(__file__).resolve().parents[1] / "analysis" / "evidence_layer_scores.json",
        # bundled into the wheel under actproof_events/data/analysis/
        Path(__file__).resolve().parent / "data" / "analysis" / "evidence_layer_scores.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                data = _load_json(path)
            except Exception:
                continue
            index: dict[str, dict[str, dict[str, Any]]] = {}
            for result in data.get("results", []):
                index[result["act_type_id"]] = {r["field"]: r for r in result.get("rows", [])}
            return index
    return {}


def load_profiles(catalogue_root: Path | None = None) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for p in _profile_paths(catalogue_root):
        data = _load_json(p)
        act_id = data.get("act_type_id")
        if act_id:
            data["_catalogue_path"] = str(p)
            profiles[act_id] = data
    return profiles


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------
def catalogue_entry_hash(entry_path: str | Path) -> str:
    """SHA-256 of the raw catalogue entry JSON file bytes, exactly as written to
    disk. This is the object a receipt binds to: the substrate records the same
    value as ``profile.catalogue_entry_hash`` with basis "raw entry JSON file
    bytes". It is not a JCS canonicalisation, and it is computed locally with no
    dependency on actproof-py.

    We deliberately do NOT compute a "profile_hash" over the parsed object. The
    receipt commitment is the manifest hash (RFC 8785 JCS over the manifest),
    which is actproof-py's domain; the catalogue binding it carries is this raw
    file-bytes hash.
    """
    return "sha256:" + hashlib.sha256(Path(entry_path).read_bytes()).hexdigest()


# Basis string for catalogue_entry_hash, named once so every surface that emits
# it stays identical.
CATALOGUE_ENTRY_HASH_BASIS = "sha256(raw catalogue entry JSON file bytes)"


def disclosure_tier(profile: dict[str, Any], field_id: str) -> str:
    dp = profile.get("disclosure_profile") or {}
    for key, label in (("public_fields", "public"), ("commitment_fields", "commitment"), ("private_fields", "private")):
        if field_id in set(dp.get(key) or []):
            return label
    return "untiered"


def source_basis(profile: dict[str, Any], field_id: str | None = None) -> list[dict[str, Any]]:
    # Profiles bind sources at act level today. Field-level mapper output can
    # narrow this later without changing the external contract.
    out: list[dict[str, Any]] = []
    for src in profile.get("source_bindings") or []:
        art = src.get("artifact") or {}
        ids = src.get("identifiers") or {}
        out.append({
            "instrument": src.get("instrument"),
            "authority": src.get("authority"),
            "provisions": src.get("provisions") or [],
            "celex": ids.get("celex"),
            "eli": ids.get("eli"),
            "sha256": art.get("sha256"),
        })
    return out


# Scope of the source basis and evidence labels we can expose today. The source
# basis is field level for any field the Mapper has derived, act level otherwise
# (fallback_used True). Evidence labels remain profile level for now; that scope
# is a later step and is documented as such.
SOURCE_BASIS_SCOPE = "act"
EVIDENCE_SCOPE = "profile"

# Frozen vocabularies for a field-level derivation entry. mapping_type mirrors
# the evidence-layer rubric load levels (per source fragment, distinct from a
# field's assessment-level interpretive_load). review_status records where human
# authority stands on the AI-proposed interpretation link.
_FRAGMENT_MAPPING_TYPES = ("direct", "normalised", "transformed", "reconciled", "modelled")
_REVIEW_STATUSES = ("proposed", "reviewed", "affirmed", "disputed")
# Accepted locator components. A locator may carry others, but must carry at
# least one of these with a non-empty value; an empty object is rejected.
_LOCATOR_KEYS = ("article", "paragraph", "point", "subpoint", "annex",
                 "recital", "table", "row", "field")
_FRAGMENT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
# Basis for fragment_hash, owned and versioned by the Mapper. Consumed, not
# recomputed, here. The exact-bytes-after-normalisation wording avoids two Mapper
# versions hashing the same legal text differently over whitespace, hyphenation,
# footnotes or PDF-extraction quirks.
FRAGMENT_HASH_BASIS = (
    "sha256 over the exact UTF-8 bytes of the Mapper's extracted source-fragment "
    "string after the Mapper's own extraction-normalisation step, versioned by "
    "mapper_extraction_version"
)
DEFAULT_MAPPER_EXTRACTION_VERSION = "actproof-mapper-extract.v1"


def _validate_derivation_entry(entry: Any, act_id: str, field_id: str) -> dict[str, Any]:
    """Validate one field-level source-basis entry, raising ValueError on a
    malformed Mapper output rather than silently accepting it."""
    where = f"derivation for {act_id} / {field_id}"
    if not isinstance(entry, dict):
        raise ValueError(f"{where}: entry must be an object")
    for key in ("source_binding_id", "celex", "fragment_hash", "mapping_type", "review_status", "rationale"):
        if not isinstance(entry.get(key), str):
            raise ValueError(f"{where}: '{key}' must be a string")
    if entry["source_binding_id"] == "":
        raise ValueError(f"{where}: 'source_binding_id' must be non-empty")
    if not _FRAGMENT_HASH_RE.match(entry["fragment_hash"]):
        raise ValueError(f"{where}: 'fragment_hash' must match sha256:<64 lowercase hex chars>")
    if entry["mapping_type"] not in _FRAGMENT_MAPPING_TYPES:
        raise ValueError(f"{where}: 'mapping_type' must be one of {_FRAGMENT_MAPPING_TYPES}")
    if entry["review_status"] not in _REVIEW_STATUSES:
        raise ValueError(f"{where}: 'review_status' must be one of {_REVIEW_STATUSES}")
    locator = entry.get("locator")
    if not isinstance(locator, dict):
        raise ValueError(f"{where}: 'locator' must be an object")
    if not any(locator.get(k) not in (None, "") for k in _LOCATOR_KEYS):
        raise ValueError(f"{where}: 'locator' must include at least one non-empty component from {_LOCATOR_KEYS}")
    mev = entry.get("mapper_extraction_version")
    if mev is not None and not isinstance(mev, str):
        raise ValueError(f"{where}: 'mapper_extraction_version' must be a string when present")
    return entry


def _validate_derivations(data: Any, source: str) -> dict[str, dict[str, list[dict[str, Any]]]]:
    if not isinstance(data, dict):
        raise ValueError(f"field derivations in {source} must be an object keyed by act_type_id")
    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for act_id, fields in data.items():
        if not isinstance(fields, dict):
            raise ValueError(f"field derivations for {act_id} must be an object keyed by field_id")
        index[act_id] = {}
        for field_id, entries in fields.items():
            if not isinstance(entries, list):
                raise ValueError(f"derivations for {act_id} / {field_id} must be a list")
            index[act_id][field_id] = [_validate_derivation_entry(e, act_id, field_id) for e in entries]
    return index


@lru_cache(maxsize=1)
def _field_derivations_index() -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Field-level source-basis derivations, keyed [act_type_id][field_id] ->
    list of entries. Produced by the Mapper. Absent or empty until then, in which
    case every field falls back cleanly to the act-level source basis."""
    candidates = [
        Path(__file__).resolve().parents[1] / "analysis" / "field_derivations.json",
        Path(__file__).resolve().parent / "data" / "analysis" / "field_derivations.json",
    ]
    for path in candidates:
        if path.exists():
            return _validate_derivations(_load_json(path), source=str(path))
    return {}


def field_derivation(act_id: str | None, field_id: str | None) -> list[dict[str, Any]] | None:
    """The field-level source basis for one field, or None if the Mapper has not
    derived it yet."""
    if not act_id or not field_id:
        return None
    return _field_derivations_index().get(act_id, {}).get(field_id)


def act_derivations(act_id: str | None) -> dict[str, list[dict[str, Any]]]:
    """All field-level derivations for one act, keyed field_id -> entries."""
    if not act_id:
        return {}
    return _field_derivations_index().get(act_id, {})


def binding_ids(profile: dict[str, Any]) -> set[str]:
    """The stable source_binding_id values a profile exposes. Empty until
    profiles carry ids (C2.1, alongside the C1 vector regeneration)."""
    return {
        b["source_binding_id"]
        for b in (profile.get("source_bindings") or [])
        if isinstance(b, dict) and b.get("source_binding_id")
    }


def check_derivation_references(profile: dict[str, Any]) -> None:
    """When a profile exposes stable source_binding_id values, every field-level
    derivation for that act must reference one of them, so a row cannot carry a
    plausible CELEX and locator yet link to no act-level binding.

    Dormant by design: a profile that exposes no ids yet (the case today) skips
    the check, so partial rollout never blocks reads. It activates the moment
    profiles carry ids."""
    ids = binding_ids(profile)
    if not ids:
        return
    act_id = profile.get("act_type_id")
    for field_id, entries in act_derivations(act_id).items():
        for entry in entries:
            ref = entry.get("source_binding_id")
            if ref not in ids:
                raise ValueError(
                    f"derivation for {act_id} / {field_id}: source_binding_id "
                    f"'{ref}' does not match any source binding in the profile"
                )


def source_basis_view(profile: dict[str, Any], field_id: str | None = None) -> dict[str, Any]:
    """source_basis plus an explicit scope. A field the Mapper has derived
    returns its own field-level bindings with source_basis_scope 'field' and
    fallback_used False. Any other field falls back to the act-level instruments
    with source_basis_scope 'act' and fallback_used True. The flip is per field."""
    derived = field_derivation(profile.get("act_type_id"), field_id)
    if derived:
        return {
            "source_basis": [dict(e) for e in derived],
            "source_basis_scope": "field",
            "fallback_used": False,
        }
    return {
        "source_basis": source_basis(profile, field_id),
        "source_basis_scope": SOURCE_BASIS_SCOPE,
        "fallback_used": True,
    }


def field_evidence_labels(profile: dict[str, Any], field_id: str) -> list[str]:
    # v3 profiles expose required evidence at profile level. Conservative until
    # field-level mapper data refines the association.
    return list(profile.get("required_evidence_labels") or [])


def real_non_claims(profile: dict[str, Any]) -> list[str]:
    """The profile's own machine-readable enumeration of what it does NOT prove."""
    return list((profile.get("reliance_context") or {}).get("non_claims") or [])


def _score_row(act_id: str, field_id: str) -> dict[str, Any] | None:
    return _scores_index().get(act_id, {}).get(field_id)


# ---------------------------------------------------------------------------
# Public surface (signatures match the api/mcp wrappers)
# ---------------------------------------------------------------------------
def list_profiles(catalogue_root: Path | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for act_id, profile in load_profiles(catalogue_root).items():
        required = profile.get("required_claim_fields") or []
        optional = profile.get("optional_claim_fields") or []
        sources = profile.get("source_bindings") or []
        status = profile.get("profile_status") or {}
        scored = _scores_index().get(act_id, {})
        interpretive = sum(1 for f in (required + optional)
                           if _status_from_load((scored.get(f) or {}).get("interpretive_load")) == "interpretive")
        out.append({
            "act_id": act_id,
            "display_name": profile.get("display_name") or profile.get("claim_type") or act_id,
            "claim_type": profile.get("claim_type"),
            "version": profile.get("version"),
            "maturity": status.get("maturity") or "unspecified",
            "source_bound": bool(sources),
            "scored": bool(scored),
            "required_field_count": len(required),
            "optional_field_count": len(optional),
            "total_field_count": len(required) + len(optional),
            "interpretive_field_count": interpretive,
            "source_instrument_count": len(sources),
            "required_evidence_count": len(profile.get("required_evidence_labels") or []),
        })
    # source-bound and scored profiles first, then alphabetical
    return sorted(out, key=lambda x: (not x["source_bound"], not x["scored"], x["act_id"]))


def get_profile(act_id: str, catalogue_root: Path | None = None) -> dict[str, Any]:
    profiles = load_profiles(catalogue_root)
    act_id = _normalise_act_id(act_id)
    if act_id not in profiles:
        raise KeyError(f"Unknown ActProof profile: {act_id}")
    raw = profiles[act_id]
    entry_path = raw.get("_catalogue_path")
    profile = {k: v for k, v in raw.items() if not k.startswith("_")}
    fields = list_fields(act_id, required_only=False, catalogue_root=catalogue_root)
    counts = {"direct": 0, "derived": 0, "interpretive": 0, "unscored": 0}
    for f in fields:
        counts[f["interpretive_status"]] = counts.get(f["interpretive_status"], 0) + 1
    if entry_path:
        profile["catalogue_entry_hash"] = catalogue_entry_hash(entry_path)
        profile["catalogue_entry_hash_basis"] = CATALOGUE_ENTRY_HASH_BASIS
        profile["compatible_with_receipts"] = True
    profile["non_claims"] = real_non_claims(profile)
    profile["claim_flags"] = CLAIM_FLAGS
    profile["interpretive_summary"] = counts
    profile["boundary"] = BOUNDARY
    profile["boundary_id"] = BOUNDARY_ID
    return profile


def list_fields(act_id: str, required_only: bool = False, catalogue_root: Path | None = None) -> list[dict[str, Any]]:
    profiles = load_profiles(catalogue_root)
    act_id = _normalise_act_id(act_id)
    if act_id not in profiles:
        raise KeyError(f"Unknown ActProof profile: {act_id}")
    profile = profiles[act_id]
    required = list(profile.get("required_claim_fields") or [])
    optional = [] if required_only else list(profile.get("optional_claim_fields") or [])
    field_types = profile.get("claim_field_types") or {}
    rows: list[dict[str, Any]] = []
    for field in required + optional:
        row = _score_row(act_id, field)
        load = (row or {}).get("interpretive_load")
        status = _status_from_load(load)
        rows.append({
            "field_id": field,
            "required": field in required,
            "type": field_types.get(field, "unspecified"),
            "disclosure_tier": disclosure_tier(profile, field),
            "interpretive_status": status,          # short label: direct|derived|interpretive|unscored
            "mapping_type": _mapping_type(row),      # direct|normalised|transformed|reconciled|modelled|None
            "interpretive_load": load,               # 0..4 or None
            "rubric_id": RUBRIC_ID if row else None,
            "interpretive": status == "interpretive",
            "rationale": (row or {}).get("rationale", ""),
            "evidence_burden": (row or {}).get("evidence_burden"),
            "evidence_labels": field_evidence_labels(profile, field),
            "evidence_scope": EVIDENCE_SCOPE,
        })
    return rows


def get_field(act_id: str, field_id: str, catalogue_root: Path | None = None) -> dict[str, Any]:
    """One field, as a self-contained grounded answer. interpretive_status and
    boundary are always present so a model can never mistake a judgement call
    for settled fact."""
    profiles = load_profiles(catalogue_root)
    act_id = _normalise_act_id(act_id)
    if act_id not in profiles:
        raise KeyError(f"Unknown ActProof profile: {act_id}")
    profile = profiles[act_id]
    for row in list_fields(act_id, required_only=False, catalogue_root=catalogue_root):
        if row["field_id"] == field_id:
            cite = profile.get("regulatory_citation") or {}
            return {
                **row,
                "act_id": act_id,
                "regulatory_citation": {
                    "instrument": cite.get("instrument"),
                    "article": cite.get("article"),
                    "jurisdiction": cite.get("jurisdiction"),
                },
                **source_basis_view(profile, field_id),
                "non_claims": real_non_claims(profile),
                "boundary": BOUNDARY, "boundary_id": BOUNDARY_ID,
            }
    raise KeyError(f"Unknown field {field_id!r} for profile {act_id!r}")


def generate_evidence_checklist(act_id: str, catalogue_root: Path | None = None) -> dict[str, Any]:
    profile = get_profile(act_id, catalogue_root)
    return {
        "act_id": act_id,
        "display_name": profile.get("display_name"),
        "required_evidence_labels": profile.get("required_evidence_labels") or [],
        "required_fields": list_fields(act_id, required_only=True, catalogue_root=catalogue_root),
        "non_claims": real_non_claims(profile),
        "boundary": BOUNDARY, "boundary_id": BOUNDARY_ID,
    }


def compare_schema_to_profile(act_id: str, schema_fields: list[str], catalogue_root: Path | None = None) -> dict[str, Any]:
    """Compare a vendor/internal field list against a profile.

    Beyond plain set matching, this flags divergence on the judgement fields:
    the required interpretive fields are where implementations actually drift
    and where a supervisor looks first. Missing one of those is not the same as
    missing a direct field, and the result says so.
    """
    profile = get_profile(act_id, catalogue_root)
    required = set(profile.get("required_claim_fields") or [])
    optional = set(profile.get("optional_claim_fields") or [])
    profile_fields = required | optional
    submitted = set(schema_fields)

    interpretive = {r["field_id"] for r in list_fields(act_id, catalogue_root=catalogue_root)
                    if r["interpretive_status"] == "interpretive"}
    required_interpretive = required & interpretive

    matched = sorted(profile_fields & submitted)
    missing_required = sorted(required - submitted)
    missing_optional = sorted(optional - submitted)
    extra = sorted(submitted - profile_fields)
    missing_interpretive_required = sorted(required_interpretive - submitted)

    mir = len(missing_interpretive_required)
    mr = len(missing_required)
    extra_count = len(extra)
    if mir >= 1 or mr >= 2:
        severity = "high"
    elif mr == 1 or extra_count >= 1:
        severity = "medium"
    elif missing_optional:
        severity = "low"
    else:
        severity = "none"

    return {
        "act_id": act_id,
        "matched": matched,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "extra": extra,
        "missing_interpretive_required_fields": missing_interpretive_required,
        "divergence_summary": {
            "matched_count": len(matched),
            "missing_required_count": mr,
            "missing_interpretive_required_count": mir,
            "missing_optional_count": len(missing_optional),
            "extra_count": extra_count,
            "severity": severity,
        },
        "review_required": sorted((submitted - profile_fields) | (required - submitted)),
        "non_claims": real_non_claims(profile),
        "boundary": BOUNDARY, "boundary_id": BOUNDARY_ID,
    }


_BINDING_CHECKS_NOT_PERFORMED = [
    "manifest_hash_reproduced",
    "rfc3161_timestamp",
    "ledger_anchor",
    "envelope_signature",
    "issuer_identity",
]

_BINDING_BOUNDARY = (
    "This checks catalogue profile binding only. Full receipt verification "
    "(manifest hash, timestamp, anchor, signature, issuer identity) is performed "
    "by actproof-py, not here."
)
_BINDING_BOUNDARY_ID = "actproof.boundary.binding_check.v1"


def _dig(obj: Any, *names: str) -> Any:
    """First value found for any of `names`, searching the dict and one level of
    common nested containers. Receipts and manifests vary in shape, so we look in
    a few likely places rather than assume one path."""
    if not isinstance(obj, dict):
        return None
    for n in names:
        if obj.get(n) not in (None, ""):
            return obj[n]
    for container in ("manifest", "raw_manifest", "profile", "catalogue",
                      "catalogue_entry", "envelope"):
        sub = obj.get(container)
        if isinstance(sub, dict):
            v = _dig(sub, *names)
            if v is not None:
                return v
    return None


# Ordered locations for a supplied catalogue entry hash, with the key to read at
# each. The universal rule: inside a `catalogue` object the field is `entry_hash`
# / `entry_version` (the parent already qualifies it; this is what the substrate
# mints and what consumers read), and the prefixed `catalogue_entry_hash` is used
# only in flat contexts that have no `catalogue.` parent (the profile block, a
# bare top level). The canonical, manifest-covered location is the first match;
# flat locations sit outside the manifest and are transitional. Inside catalogue
# objects the prefixed name is tolerated as an alias so an early adopter who
# emitted the stutter name still binds, but `entry_hash` is canonical.
# Each row: (container_path, hash_keys, version_keys, label, transitional).
_ENTRY_HASH_LOCATIONS: tuple[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], str, bool], ...] = (
    (("manifest", "catalogue"), ("entry_hash", "catalogue_entry_hash"),
     ("entry_version", "catalogue_entry_version"), "manifest.catalogue.entry_hash", False),
    (("raw_manifest", "catalogue"), ("entry_hash", "catalogue_entry_hash"),
     ("entry_version", "catalogue_entry_version"), "raw_manifest.catalogue.entry_hash", False),
    (("catalogue",), ("entry_hash", "catalogue_entry_hash"),
     ("entry_version", "catalogue_entry_version"), "catalogue.entry_hash", False),
    (("profile",), ("catalogue_entry_hash",), ("catalogue_entry_version",),
     "profile.catalogue_entry_hash", True),
    ((), ("catalogue_entry_hash",), ("catalogue_entry_version",),
     "catalogue_entry_hash", True),
)


def _first(container: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if container.get(k) not in (None, ""):
            return container[k]
    return None


def _find_entry_hash(receipt: Any) -> tuple[Any, Any, str | None, bool]:
    """Return (hash, version, location_label, transitional) for the supplied
    catalogue entry hash, canonical (manifest-covered) location first. Flat
    locations outside the manifest are transitional. (None, None, None, False)
    if absent."""
    if not isinstance(receipt, dict):
        return None, None, None, False
    for path, hash_keys, version_keys, label, transitional in _ENTRY_HASH_LOCATIONS:
        container: Any = receipt
        for key in path:
            container = container.get(key) if isinstance(container, dict) else None
        if isinstance(container, dict):
            value = _first(container, hash_keys)
            if value is not None:
                return value, _first(container, version_keys), label, transitional
    return None, None, None, False


def check_profile_binding(receipt: dict[str, Any], catalogue_root: Path | None = None) -> dict[str, Any]:
    """Check whether a supplied receipt, manifest, or profile descriptor binds to
    a catalogue entry available here.

    This is a profile-binding check, not full receipt verification. It returns a
    three-state ``status``:

      * ``bound``              an entry hash was supplied and matches our local
                               raw-file-bytes hash;
      * ``recognized_unbound`` the act_type_id is known but no entry hash was
                               supplied, so the exact bytes were not bound;
      * ``mismatch``           an entry hash was supplied and did not match.

    Recognising an act is not the same as cryptographically binding to its
    bytes, so we never report ``binding_match: true`` without a supplied hash.
    Manifest hash, timestamp, anchor, signature and issuer are not checked here;
    those live in actproof-py. Every result carries verification_grade:
    false, because a binding check is not receipt verification and can
    never grade a receipt as verified.
    """
    act_id = _dig(receipt, "act_type_id", "catalogue_act_type_id", "act_id", "profile_id")
    if not act_id:
        return {
            "check_type": "profile_binding", "status": "invalid_input", "binding_match": False,
            "reason": "no act_type_id found in supplied object",
            "checks_performed": [], "checks_not_performed": list(_BINDING_CHECKS_NOT_PERFORMED),
            "verification_grade": False, "boundary": _BINDING_BOUNDARY, "boundary_id": _BINDING_BOUNDARY_ID,
        }

    profiles = load_profiles(catalogue_root)
    if act_id not in profiles:
        return {
            "check_type": "profile_binding", "status": "unknown_profile", "binding_match": False,
            "act_type_id": act_id, "reason": f"unknown act_type_id: {act_id}",
            "checks_performed": [], "checks_not_performed": list(_BINDING_CHECKS_NOT_PERFORMED),
            "verification_grade": False, "boundary": _BINDING_BOUNDARY, "boundary_id": _BINDING_BOUNDARY_ID,
        }

    entry_path = profiles[act_id].get("_catalogue_path")
    local_hash = catalogue_entry_hash(entry_path) if entry_path else None
    supplied_hash, supplied_version, supplied_hash_location, supplied_transitional = _find_entry_hash(receipt)

    # No entry hash supplied: recognised, but not bound. Never true.
    if supplied_hash is None:
        return {
            "check_type": "profile_binding", "status": "recognized_unbound", "binding_match": None,
            "act_type_id": act_id,
            "supplied_entry_hash": None, "local_entry_hash": local_hash,
            "supplied_entry_hash_location": None,
            "supplied_entry_version": supplied_version,
            "checks_performed": ["act_type_id_known"],
            "checks_not_performed": ["catalogue_entry_hash_match", *_BINDING_CHECKS_NOT_PERFORMED],
            "reason": ("The supplied object identifies a known ActProof profile, but no "
                       "catalogue entry hash was supplied. Exact catalogue profile binding "
                       "was not checked."),
            "verification_grade": False, "boundary": _BINDING_BOUNDARY, "boundary_id": _BINDING_BOUNDARY_ID,
        }

    # Entry hash supplied: strong (or transitional descriptor) binding check.
    match = (str(supplied_hash) == str(local_hash))
    return {
        "check_type": "profile_binding",
        "status": "bound" if match else "mismatch",
        "binding_match": match,
        "act_type_id": act_id,
        "supplied_entry_hash": supplied_hash,
        "local_entry_hash": local_hash,
        "supplied_entry_hash_location": supplied_hash_location,
        "transitional_descriptor": supplied_transitional,
        "catalogue_entry_hash_basis": CATALOGUE_ENTRY_HASH_BASIS,
        "supplied_entry_version": supplied_version,
        "checks_performed": ["act_type_id_known", "catalogue_entry_hash_match"],
        "checks_not_performed": list(_BINDING_CHECKS_NOT_PERFORMED),
        "verification_grade": False, "boundary": _BINDING_BOUNDARY, "boundary_id": _BINDING_BOUNDARY_ID,
    }


# Backward-compatible alias. The API endpoint and MCP tool are renamed in the
# next A-step; until then their existing import of verify_profile_receipt
# continues to resolve to the binding check.
verify_profile_receipt = check_profile_binding
