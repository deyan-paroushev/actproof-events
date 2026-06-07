# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Official source-text capture support for ActProof source atoms.

This module deliberately treats official-text capture as a governed maturity
step, not as a bulk scraping operation. The 2.5.0 release is a pilot: three
representative DORA atoms carry captured official-text excerpts and hashes under
an explicit normalisation rule. All other atoms remain honest locator-bound
atoms until captured under the same rule.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from actproof_events import __version__
from actproof_events.source_binding import list_field_derivations, list_source_atoms

OFFICIAL_TEXT_NORMALISATION_BASIS = "actproof.official_text_normalisation.v1"
OFFICIAL_TEXT_HASH_BASIS = "sha256:utf8:actproof.official_text_normalisation.v1"
TEXT_CAPTURE_RULE_ID = "actproof.official_text_excerpt_rule.v1"
TEXT_CAPTURE_SCHEMA_ID = "actproof.atom_text_capture.v1"
TEXT_COVERAGE_SCHEMA_ID = "actproof.atom_text_coverage.v1"
DEPENDENCY_SCHEMA_ID = "actproof.atom_dependency_report.v1"
DORA_ACT_ID = "op:eu.dora.ict_incident_notification_initial.v1"


def normalise_official_text(text: str) -> str:
    """Normalise official-source excerpts before hashing (rule v1).

    Deterministic and minimal, and STRUCTURE-PRESERVING:
    * Unicode normalise to NFC.
    * Convert non-breaking spaces to regular spaces; CRLF/CR -> LF.
    * Collapse intra-line whitespace runs to a single ASCII space.
    * Strip each line; collapse blank-line runs; single trailing LF.
    * Preserve line structure (sub-paragraphs, points (a)/(b)/(c)), punctuation,
      numbering, case and legal wording. No reordering, no de-hyphenation.

    Line structure is preserved deliberately: collapsing an enumerated list to a
    single line destroys the point boundaries that carry legal meaning.
    """
    if text is None:
        raise ValueError("excerpt is None; nothing to normalise")
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u00a0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in text.split("\n")]
    out: list[str] = []
    blank = False
    for ln in lines:
        if ln == "":
            if not blank:
                out.append("")
            blank = True
        else:
            out.append(ln)
            blank = False
    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def compute_official_text_sha256(text: str) -> str:
    """Return sha256 over UTF-8 encoded normalised official excerpt text."""
    normalised = normalise_official_text(text)
    return "sha256:" + hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def capture_atom_official_text(
    atom: dict[str, Any],
    raw_excerpt: str,
    *,
    boundary_rule: str,
    official_text_source: dict[str, Any],
    text_locator: "dict[str, Any] | None" = None,
    captured_by: str = "maintainer",
    text_language: str = "en",
) -> dict[str, Any]:
    """Return a COPY of `atom` with official-text fields added additively.

    Identity is not disturbed. ``atom_identity_sha256`` is computed over a fixed
    identity basis that includes ``locator``; a finer paragraph reference used
    for capture is therefore recorded in ``text_locator`` and the identity
    ``locator`` is left intact, so the identity hash is byte-for-byte unchanged.

    Capture moves the atom on the BINDING axis only:
    ``text_capture_status`` -> ``captured_draft`` and ``binding_status`` ->
    ``text_locator_bound``. It does NOT set review status: captured official
    text is independently checkable, not legally attested.
    """
    if not raw_excerpt or not raw_excerpt.strip():
        raise ValueError("refusing to capture an empty official-text excerpt")
    out = dict(atom)
    identity_before = atom.get("atom_identity_sha256")
    out["text_excerpt"] = raw_excerpt
    out["official_text_sha256"] = compute_official_text_sha256(raw_excerpt)
    out["official_text_hash_basis"] = OFFICIAL_TEXT_HASH_BASIS
    out["official_text_normalisation_basis"] = OFFICIAL_TEXT_NORMALISATION_BASIS
    out["text_excerpt_rule_id"] = TEXT_CAPTURE_RULE_ID
    out["excerpt_boundary"] = {"boundary_rule": boundary_rule}
    out["official_text_source"] = official_text_source
    out["text_language"] = text_language
    out["text_captured_by"] = captured_by
    if text_locator is not None:
        out["text_locator"] = text_locator
    out["text_capture_status"] = "captured_draft"
    out["text_review_status"] = "draft"
    # binding_status is the review/verification axis (enum: verified|provisional)
    # and is intentionally NOT changed here: capturing official text makes an atom
    # checkable, not reviewed, so it stays provisional. Capture progress lives in
    # text_capture_status. (This keeps the atom valid against source_atoms.v1.)
    # invariant: capture must never change the identity hash
    if out.get("atom_identity_sha256") != identity_before:
        raise AssertionError("capture must not change atom_identity_sha256")
    return out


def verify_atom_official_text(atom: dict[str, Any]) -> dict[str, Any]:
    """Recompute official_text_sha256 from the stored excerpt and confirm match.

    Returns a verdict dict. ok=True only if a non-empty excerpt re-hashes to the
    stored value under the recorded normalisation basis. This is the check that
    makes a capture verifiable rather than asserted.
    """
    excerpt = atom.get("text_excerpt")
    stored = atom.get("official_text_sha256")
    aid = atom.get("source_atom_id")
    if not excerpt:
        return {"ok": False, "atom": aid, "reason": "no_text_excerpt"}
    if not stored:
        return {"ok": False, "atom": aid, "reason": "no_stored_official_text_sha256"}
    basis = atom.get("official_text_normalisation_basis")
    if basis != OFFICIAL_TEXT_NORMALISATION_BASIS:
        return {"ok": False, "atom": aid, "reason": f"unknown_normalisation_basis:{basis}"}
    recomputed = compute_official_text_sha256(excerpt)
    ok = recomputed == stored
    return {
        "ok": ok,
        "atom": aid,
        "stored_official_text_sha256": stored,
        "recomputed_official_text_sha256": recomputed,
        "reason": "match" if ok else "hash_mismatch",
    }


def atom_text_maturity(atom: dict[str, Any]) -> str:
    """Return a simple maturity label for one source atom."""
    if atom.get("official_text_sha256") and atom.get("text_excerpt"):
        if atom.get("review_status") in {"maintainer_reviewed", "independent_reviewed", "external_legal_reviewed"}:
            return "M6_maintainer_or_higher_reviewed"
        return "M5_text_hashed_draft"
    if atom.get("text_excerpt"):
        return "M4_text_captured_no_hash"
    if atom.get("atom_identity_sha256"):
        return "M2_identity_hashed_locator_bound"
    return "M1_locator_bound"


def compute_atom_text_coverage(act_id: str) -> dict[str, Any]:
    """Compute text-capture coverage for all atoms in a profile."""
    atoms = list_source_atoms(act_id)
    total = len(atoms)
    captured = [a for a in atoms if a.get("text_excerpt")]
    hashed = [a for a in atoms if a.get("official_text_sha256")]
    captured_and_hashed = [a for a in atoms if a.get("text_excerpt") and a.get("official_text_sha256")]
    pilot = [a for a in captured_and_hashed if a.get("text_capture_status") == "captured_draft"]
    missing = [a["source_atom_id"] for a in atoms if not a.get("text_excerpt") or not a.get("official_text_sha256")]
    by_maturity: dict[str, int] = {}
    by_atom_type: dict[str, dict[str, int]] = {}
    for atom in atoms:
        maturity = atom_text_maturity(atom)
        by_maturity[maturity] = by_maturity.get(maturity, 0) + 1
        typ = atom.get("atom_type", "unknown")
        bucket = by_atom_type.setdefault(typ, {"total": 0, "text_hashed": 0})
        bucket["total"] += 1
        if atom.get("text_excerpt") and atom.get("official_text_sha256"):
            bucket["text_hashed"] += 1

    pct = lambda n, d: round((n / d) * 100, 1) if d else 0.0
    return {
        "schema": TEXT_COVERAGE_SCHEMA_ID,
        "act_id": act_id,
        "package": {"name": "actproof-events", "version": __version__},
        "text_capture_status": "pilot",
        "atoms_total": total,
        "text_excerpts_captured": len(captured),
        "official_text_hashes_present": len(hashed),
        "text_captured_and_hashed": len(captured_and_hashed),
        "text_capture_coverage_ratio": pct(len(captured_and_hashed), total),
        "pilot_atom_ids": [a["source_atom_id"] for a in pilot],
        "atoms_pending_text_capture": missing,
        "by_maturity": dict(sorted(by_maturity.items())),
        "by_atom_type": dict(sorted(by_atom_type.items())),
        "normalisation_basis": OFFICIAL_TEXT_NORMALISATION_BASIS,
        "official_text_hash_basis": OFFICIAL_TEXT_HASH_BASIS,
        "boundary": (
            "2.5.0 is a controlled pilot. Text-captured atoms are captured_draft, "
            "not externally reviewed and not legal advice. Locator-only atoms remain honest."
        ),
    }


def validate_atom_text(act_id: str) -> list[str]:
    """Validate internal consistency of official-text capture fields."""
    errors: list[str] = []
    for atom in list_source_atoms(act_id):
        atom_id = atom.get("source_atom_id", "<unknown>")
        text = atom.get("text_excerpt") or ""
        stored = atom.get("official_text_sha256")
        has_text = bool(text)
        has_hash = bool(stored)
        if has_text and not has_hash:
            errors.append(f"{atom_id}: text_excerpt present but official_text_sha256 missing")
        if has_hash and not has_text:
            errors.append(f"{atom_id}: official_text_sha256 present but text_excerpt missing")
        if has_hash and not str(stored).startswith("sha256:"):
            errors.append(f"{atom_id}: official_text_sha256 must start with sha256:")
        if has_text and has_hash:
            recomputed = compute_official_text_sha256(text)
            if stored != recomputed:
                errors.append(f"{atom_id}: official_text_sha256 mismatch; expected {recomputed}")
            for key in (
                "text_capture_status",
                "official_text_hash_basis",
                "official_text_normalisation_basis",
                "official_text_source",
                "excerpt_boundary",
            ):
                if not atom.get(key):
                    errors.append(f"{atom_id}: captured text atom missing {key}")
            boundary = atom.get("excerpt_boundary") or {}
            if boundary.get("locator_precision") == "article_range" and not boundary.get("range_text_binding_justification"):
                errors.append(f"{atom_id}: article-range text binding requires explicit justification")
    return errors


def build_atom_dependency_report(act_id: str) -> dict[str, Any]:
    """Show which fields and derivations depend on each source atom."""
    atoms = list_source_atoms(act_id)
    derivations = list_field_derivations(act_id)
    deps: dict[str, dict[str, Any]] = {}
    for atom in atoms:
        deps[atom["source_atom_id"]] = {
            "source_atom_id": atom["source_atom_id"],
            "atom_type": atom.get("atom_type"),
            "source_role": atom.get("source_role"),
            "normative_weight": atom.get("normative_weight"),
            "text_maturity": atom_text_maturity(atom),
            "official_text_sha256": atom.get("official_text_sha256"),
            "used_by_fields": [],
            "used_by_derivations": [],
        }
    for derivation in derivations:
        field_id = derivation.get("field_id")
        for atom_id in derivation.get("source_atoms") or []:
            if atom_id in deps:
                deps[atom_id]["used_by_fields"].append(field_id)
                deps[atom_id]["used_by_derivations"].append(derivation.get("derivation_id") or field_id)
    for entry in deps.values():
        entry["used_by_fields"] = sorted(set(entry["used_by_fields"]))
        entry["used_by_derivations"] = sorted(set(entry["used_by_derivations"]))
        entry["dependency_count"] = len(entry["used_by_fields"])
        entry["coverage_status"] = "used" if entry["used_by_fields"] else "unused_gap_signal"
    return {
        "schema": DEPENDENCY_SCHEMA_ID,
        "act_id": act_id,
        "package": {"name": "actproof-events", "version": __version__},
        "atoms": list(deps.values()),
        "summary": {
            "atoms_total": len(atoms),
            "atoms_used": sum(1 for d in deps.values() if d["used_by_fields"]),
            "atoms_unused": sum(1 for d in deps.values() if not d["used_by_fields"]),
            "text_hashed_atoms": sum(1 for d in deps.values() if d.get("official_text_sha256")),
        },
    }


def export_atom_inventory(act_id: str) -> dict[str, Any]:
    """Export source atoms with text maturity and dependency summary."""
    dependency = {a["source_atom_id"]: a for a in build_atom_dependency_report(act_id)["atoms"]}
    atoms: list[dict[str, Any]] = []
    for atom in list_source_atoms(act_id):
        item = dict(atom)
        item["text_maturity"] = atom_text_maturity(atom)
        item["dependency_summary"] = dependency.get(atom["source_atom_id"], {})
        atoms.append(item)
    return {
        "schema": "actproof.atom_inventory.v1",
        "act_id": act_id,
        "package": {"name": "actproof-events", "version": __version__},
        "coverage": compute_atom_text_coverage(act_id),
        "atoms": atoms,
    }


def write_json(payload: dict[str, Any], out: str | Path, *, compact: bool = False) -> dict[str, Any]:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=None if compact else 2, sort_keys=False), encoding="utf-8")
    return payload


__all__ = [
    "OFFICIAL_TEXT_NORMALISATION_BASIS",
    "OFFICIAL_TEXT_HASH_BASIS",
    "TEXT_CAPTURE_RULE_ID",
    "normalise_official_text",
    "compute_official_text_sha256",
    "capture_atom_official_text",
    "verify_atom_official_text",
    "atom_text_maturity",
    "compute_atom_text_coverage",
    "validate_atom_text",
    "build_atom_dependency_report",
    "export_atom_inventory",
    "write_json",
]
