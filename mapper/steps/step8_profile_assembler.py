#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
ActProof Mapper - Step 8: Profile Assembler
============================================

WHAT THIS STEP DOES (in plain words)
------------------------------------
This is the destination. Steps 1 to 7 verified the sources, named the
fragments, decomposed the actions, mapped the fields, recorded the evidence and
the judgements, and bound it all into a traceability matrix.

This step does two things:

  1. Bundles the seven outputs into ONE canonical "mapping package" - the
     complete, self-contained record of the whole transformation.

  2. From that package, assembles the final ActProof profile JSON - the clean,
     operational artefact a downstream system would actually consume.

The journey is now complete:

    official PDF  ->  ...seven controlled steps...  ->  finished profile JSON

And because every step recorded its work, the finished JSON is not a black box.
The profile carries a pointer to its mapping package, so anyone can walk back
from any field to the exact source fragment and human decision behind it.

WHY TWO OUTPUTS (package AND profile)
-------------------------------------
- The MAPPING PACKAGE is the full evidence record: everything, including the
  reasoning and the traceability. It is what you inspect and challenge.
- The PROFILE is the lean operational form: schema, fields, evidence labels,
  source bindings, non-claims. It is what software uses.

Keeping both means the operational artefact never loses its chain of custody.

NO HUMAN REVIEW GATE
--------------------
Like Step 7, this is pure assembly. It introduces no new mapping or judgement.
It bundles and emits what the earlier human gates already produced, and checks
the result is internally consistent.

WHAT THIS STEP DOES NOT DO (the boundary)
-----------------------------------------
- It does not add fields, evidence or decisions.
- It does not claim the profile is legally correct, complete or compliant.
- It produces an inspectable artefact, not an official interpretation.

INPUT
-----
--dossier      source-dossier.json            (Step 1)
--fragments    source-fragments.json          (Step 2)
--actions      legal-actions.json             (Step 3)
--fields       mapped-fields.json             (Step 4)
--evidence     evidence-labels.json           (Step 5)
--decisions    interpretation-decisions.json  (Step 6)
--traceability traceability.json              (Step 7)
--out          output directory

OUTPUT (written to --out)
-------------------------
mapping-package.json   the complete bundled record (canonical nested shape)
actproof-profile.json  the final operational profile
actproof-profile.md    human-readable profile summary
assemble-check.txt     short console-style check log

DETERMINISM
-----------
JSON output uses sorted keys, two-space indent, LF endings, trailing newline.
"""

import argparse
import json
import os
import sys


SCHEMA_PACKAGE = "actproof.mapping_package.v0"
SCHEMA_PROFILE = "actproof.profile.v0"


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build_package(dossier, fragments, actions, fields, evidence, decisions, traceability):
    """Bundle the seven step outputs into the canonical nested mapping package."""
    profile_id = fields.get("profile_id") or traceability.get("profile_id")

    # The profile_draft section: the field list, required/optional split.
    mapped = fields.get("mapped_fields", [])
    required = [m["field_id"] for m in mapped if m.get("required")]
    optional = [m["field_id"] for m in mapped if not m.get("required")]
    draft_fields = [
        {
            "field_id": m.get("field_id"),
            "label": m.get("label"),
            "type": m.get("type"),
            "required": m.get("required"),
            "disclosure": m.get("disclosure"),
        }
        for m in mapped
    ]

    coverage = {
        "profile_fields_total": len(mapped),
        "profile_fields_traced": sum(1 for r in traceability.get("traceability", [])
                                     if r.get("row_type") == "profile_field"),
        "evidence_labels_total": len(evidence.get("evidence_labels", [])),
        "evidence_labels_traced": sum(1 for r in traceability.get("traceability", [])
                                      if r.get("row_type") == "evidence_label"),
        "source_fragments": len(fragments.get("source_fragments", [])),
        "legal_actions": len(actions.get("legal_actions", [])),
        "interpretation_decisions": len(decisions.get("interpretation_decisions", [])),
    }

    return {
        "schema": SCHEMA_PACKAGE,
        "profile_id": profile_id,
        "profile_version": "v1",
        "status": "draft",
        "title": fields.get("title"),
        "summary": "Complete ActProof Mapper package: source dossier, fragments, "
                   "legal actions, mapped fields, evidence labels, interpretation "
                   "decisions and the traceability matrix.",
        "source_dossier": {
            "status": dossier.get("status"),
            "source_state": dossier.get("source_state"),
            "sources": dossier.get("sources", []),
        },
        "profile_draft": {
            "schema": "actproof.profile_draft.v0",
            "profile_id": profile_id,
            "title": fields.get("title"),
            "status": "draft",
            "required_fields": required,
            "optional_fields": optional,
            "fields": draft_fields,
            "non_claims": fields.get("non_claims", []),
        },
        "traceability_matrix": {
            "schema": traceability.get("schema"),
            "profile_id": profile_id,
            "status": traceability.get("status"),
            "summary": traceability.get("summary"),
            "inputs": traceability.get("inputs"),
            "traceability": traceability.get("traceability", []),
            "findings": traceability.get("findings", []),
            "non_claims": traceability.get("non_claims", []),
        },
        # The rich object arrays, preserved alongside the nested wrappers.
        "source_fragments": fragments.get("source_fragments", []),
        "legal_actions": actions.get("legal_actions", []),
        # The full Step 4 derivation register, preserved directly (not only via
        # the traceability matrix), because it is the core field-derivation layer.
        "mapped_fields": fields.get("mapped_fields", []),
        "evidence_labels": evidence.get("evidence_labels", []),
        "interpretation_decisions": decisions.get("interpretation_decisions", []),
        "coverage": coverage,
        "non_claims": [
            "This package records a controlled source-to-profile transformation.",
            "It does not prove legal correctness, completeness, compliance or authority acceptance.",
            "Source provenance is mechanical (hashes); fidelity is a reviewed, contestable reading.",
        ],
    }


def derive_source_bindings(dossier):
    """Lean source bindings for the operational profile, from the dossier."""
    out = []
    for s in dossier.get("sources", []):
        out.append({
            "source_id": s.get("source_id"),
            "celex": s.get("celex"),
            "eli": s.get("eli"),
            "title": s.get("title"),
            "sha256": s.get("expected_sha256"),
            "status": s.get("status"),
            "provisions": s.get("provisions", []),
            "source_role": s.get("source_role"),
        })
    return out


def build_profile(package):
    """Assemble the lean operational profile from the mapping package."""
    profile_id = package.get("profile_id")
    draft = package.get("profile_draft", {})
    dossier = package.get("source_dossier", {})

    # Derive a friendly act_type_id from the op: profile id, if present.
    act_type_id = profile_id
    if isinstance(profile_id, str) and profile_id.startswith("op:"):
        act_type_id = profile_id[len("op:"):]
        if act_type_id.endswith(".v1"):
            act_type_id = act_type_id[:-3]

    findings = []

    # Consistency check: every required/optional field must be a real field.
    field_ids = {f.get("field_id") for f in draft.get("fields", [])}
    for fid in draft.get("required_fields", []) + draft.get("optional_fields", []):
        if fid not in field_ids:
            findings.append({"severity": "error", "code": "profile.field_missing",
                             "message": "Field '{}' is listed but not defined in the field set.".format(fid)})

    evidence_labels = [
        {
            "evidence_id": e.get("evidence_id"),
            "label": e.get("label"),
            "basis": e.get("basis"),
            "supports_fields": e.get("supports_fields", []),
            "mandatory_legal_attachment_claimed": e.get("mandatory_legal_attachment_claimed", False),
            "disclosure": e.get("disclosure"),
        }
        for e in package.get("evidence_labels", [])
    ]

    # Per-field trace pointer: enough to jump back into the mapping package
    # without stuffing the whole chain into the profile. We pull mapping_status
    # from the Step 4 register preserved in the package.
    mapping_status_by_field = {
        m.get("field_id"): m.get("mapping_status")
        for m in package.get("mapped_fields", [])
    }
    profile_fields = []
    for f in draft.get("fields", []):
        fid = f.get("field_id")
        enriched = dict(f)
        enriched["trace_id"] = "trace.field.{}".format(fid)
        enriched["mapping_status"] = mapping_status_by_field.get(fid)
        profile_fields.append(enriched)

    status = "fail" if any(f["severity"] == "error" for f in findings) else "draft"

    return {
        "schema": SCHEMA_PROFILE,
        "profile_id": profile_id,
        "profile_version": package.get("profile_version", "v1"),
        "title": package.get("title"),
        "status": status,
        "profile_status": "draft",
        "act_type_id": act_type_id,
        "jurisdiction": "EU" if isinstance(act_type_id, str) and act_type_id.startswith("eu.") else None,
        "object": (act_type_id.split(".")[-1] if isinstance(act_type_id, str) else None),
        "description": package.get("summary"),
        "source_bindings": derive_source_bindings(dossier),
        # Honesty block surfaced on the profile itself: provenance is verified,
        # currentness is not claimed. Mirrors the source dossier so a reader who
        # inspects only the profile is not misled that "verified" means "current law".
        "source_state": dossier.get("source_state"),
        "required_fields": draft.get("required_fields", []),
        "optional_fields": draft.get("optional_fields", []),
        "fields": profile_fields,
        "evidence_labels": evidence_labels,
        # The pointer back to the full evidence record - the chain of custody.
        "traceability_ref": {
            "schema": package.get("schema"),
            "profile_id": profile_id,
            "rows": len(package.get("traceability_matrix", {}).get("traceability", [])),
            "note": "Full source-to-field traceability is recorded in the mapping package.",
        },
        "coverage": package.get("coverage", {}),
        "findings": findings,
        "non_claims": [
            "This profile is an inspectable public artefact, not an official legal interpretation.",
            "A source binding proves the profile was built against specific official artefacts; "
            "it does not prove the mapping is legally complete or correct.",
            "This profile does not prove legal compliance or that an authority accepted a filing.",
            "Source provenance is mechanical; fidelity is a reviewed, contestable reading.",
            "This profile does not provide legal advice.",
        ],
    }


def render_profile_markdown(profile):
    lines = []
    lines.append("# ActProof profile: {}".format(profile.get("profile_id")))
    lines.append("")
    lines.append("**Status:** `{}`  ".format(profile.get("status")))
    lines.append("**Act type:** `{}`  ".format(profile.get("act_type_id")))
    lines.append("**Jurisdiction:** {}".format(profile.get("jurisdiction") or "-"))
    lines.append("")
    lines.append("## Source bindings")
    lines.append("")
    lines.append("| Source | Role | Status | SHA-256 |")
    lines.append("|---|---|---|---|")
    for s in profile.get("source_bindings", []):
        lines.append("| `{}` | {} | `{}` | `{}` |".format(
            s.get("source_id"), s.get("source_role") or "", s.get("status") or "",
            (s.get("sha256") or "-")))
    lines.append("")
    lines.append("## Fields")
    lines.append("")
    lines.append("- Required: **{}**".format(len(profile.get("required_fields", []))))
    lines.append("- Optional: **{}**".format(len(profile.get("optional_fields", []))))
    lines.append("- Evidence labels: **{}**".format(len(profile.get("evidence_labels", []))))
    lines.append("")
    lines.append("Full source-to-field traceability: {} rows in the mapping package.".format(
        profile.get("traceability_ref", {}).get("rows")))
    lines.append("")
    lines.append("## Non-claims")
    lines.append("")
    for nc in profile.get("non_claims", []):
        lines.append("- {}".format(nc))
    lines.append("")
    return "\n".join(lines)


def render_check_log(package, profile):
    lines = []
    lines.append("ActProof Mapper - Step 8: profile assembler")
    lines.append("=" * 43)
    lines.append("Profile: {}".format(profile.get("profile_id")))
    lines.append("Profile status: {}".format(profile.get("status")))
    c = package.get("coverage", {})
    lines.append("Fields: {} total ({} required, {} optional)".format(
        c.get("profile_fields_total"),
        len(profile.get("required_fields", [])),
        len(profile.get("optional_fields", []))))
    lines.append("Evidence labels: {}".format(c.get("evidence_labels_total")))
    lines.append("Source bindings: {}".format(len(profile.get("source_bindings", []))))
    lines.append("Traceability rows: {}".format(profile.get("traceability_ref", {}).get("rows")))
    lines.append("")
    if profile.get("findings"):
        for fd in profile["findings"]:
            lines.append("[{}] {}: {}".format(fd["severity"], fd["code"], fd["message"]))
    else:
        lines.append("PASS: ActProof profile assembled from the mapping package.")
    return "\n".join(lines)


def dump_json(obj, path):
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2)
    text = text.replace("\r\n", "\n").rstrip("\n") + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def dump_text(text, path):
    text = text.replace("\r\n", "\n").rstrip("\n") + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def main():
    ap = argparse.ArgumentParser(
        description="ActProof Mapper Step 8: bundle the registers into the mapping package and assemble the final profile.")
    ap.add_argument("--dossier", required=True, help="source-dossier.json (Step 1)")
    ap.add_argument("--fragments", required=True, help="source-fragments.json (Step 2)")
    ap.add_argument("--actions", required=True, help="legal-actions.json (Step 3)")
    ap.add_argument("--fields", required=True, help="mapped-fields.json (Step 4)")
    ap.add_argument("--evidence", required=True, help="evidence-labels.json (Step 5)")
    ap.add_argument("--decisions", required=True, help="interpretation-decisions.json (Step 6)")
    ap.add_argument("--traceability", required=True, help="traceability.json (Step 7)")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    dossier = load(args.dossier)
    fragments = load(args.fragments)
    actions = load(args.actions)
    fields = load(args.fields)
    evidence = load(args.evidence)
    decisions = load(args.decisions)
    traceability = load(args.traceability)

    os.makedirs(args.out, exist_ok=True)

    package = build_package(dossier, fragments, actions, fields, evidence, decisions, traceability)
    profile = build_profile(package)

    dump_json(package, os.path.join(args.out, "mapping-package.json"))
    dump_json(profile, os.path.join(args.out, "actproof-profile.json"))
    dump_text(render_profile_markdown(profile), os.path.join(args.out, "actproof-profile.md"))
    dump_text(render_check_log(package, profile), os.path.join(args.out, "assemble-check.txt"))

    print(render_check_log(package, profile))

    if profile.get("status") == "fail":
        sys.exit(1)


if __name__ == "__main__":
    main()
