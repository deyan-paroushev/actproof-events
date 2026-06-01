#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
ActProof Mapper - Step 5: Evidence Labels
==========================================

WHAT THIS STEP DOES (in plain words)
------------------------------------
A profile field says "we need the classification time". A reviewer or auditor
then asks the obvious next question:

    "What evidence backs that up?"

This step records evidence labels: the supporting records a profile expects,
such as a classification committee record or a detection system log excerpt.
Each label says which fields it supports, which legal actions and fragments it
rests on, and - most importantly - on what BASIS it is included.

THE MOST IMPORTANT BOUNDARY IN THE WHOLE PIPELINE
-------------------------------------------------
Evidence is where it would be easy, and dangerous, to overclaim. If the mapper
said "the law requires you to attach X", but the law does not actually say
that, the profile would be asserting a legal obligation that does not exist.

So this step enforces one hard rule:

    An evidence label may only claim to be a MANDATORY LEGAL ATTACHMENT if a
    source fragment genuinely supports that claim. Otherwise it must be marked
    as SUPPORTING or INTERPRETATION evidence - useful for review, but not
    asserted as a legal requirement.

This is what keeps ActProof on the right side of the line between "showing how
a rule maps to JSON" and "inventing legal obligations". Evidence labels are
subordinate to fields: they annotate and support them, they do not create new
duties.

THE REVIEW GATE
---------------
A human writes a "selected-evidence-labels" file. This step checks each label
is anchored, that its supported fields and cited actions/fragments exist, and
that any mandatory-attachment claim is honestly grounded.

WHAT THIS STEP DOES NOT DO (the boundary)
-----------------------------------------
- It does not decide what evidence a regulator will actually accept.
- It does not assert a legal attachment requirement unless the source does.
- It does not interpret the evidentiary value of any real document.

INPUT
-----
--actions   path to legal-actions.json   (output of Step 3)
--fields    path to mapped-fields.json   (output of Step 4)
--evidence  path to selected-evidence-labels.json   (human review gate)
--out       output directory

OUTPUT (written to --out)
-------------------------
evidence-labels.json   machine-readable evidence label register
evidence-labels.md     human-readable summary
evidence-check.txt     short console-style check log

DETERMINISM
-----------
JSON output uses sorted keys, two-space indent, LF endings, trailing newline.
Labels preserve declared order.
"""

import argparse
import json
import os
import sys


SCHEMA_ACTIONS = "actproof.legal_actions.v0"
SCHEMA_FIELDS = "actproof.mapped_fields.v0"
SCHEMA_EVIDENCE_IN = "actproof.selected_evidence_labels.v0"
SCHEMA_OUT = "actproof.evidence_labels.v0"

# Canonical basis vocabulary (collapsed from the drifted legacy values).
#   direct        -> the source explicitly requires this evidence
#   supporting    -> evidence supports a field but is not source-mandated
#   interpretation-> evidence is included on the basis of a recorded judgement
KNOWN_BASIS = {"direct", "supporting", "interpretation"}

# Legacy basis values normalised on the way in.
BASIS_NORMALISE = {
    "direct_source_requirement": "direct",
    "supporting": "supporting",
    "supporting_interpretive": "interpretation",
    "interpretive": "interpretation",
    "operational_support": "supporting",
}


def index_actions(actions_reg):
    return {a.get("action_id") for a in actions_reg.get("legal_actions", [])}


def index_fragments(actions_reg):
    frags = set()
    for a in actions_reg.get("legal_actions", []):
        for f in a.get("source_fragments", []) or []:
            frags.add(f)
        for key in ("deadline", "outer_limit"):
            v = a.get(key)
            if isinstance(v, dict):
                frags.update(v.get("source_fragments", []) or [])
    return frags


def index_fields(fields_reg):
    return {m.get("field_id") for m in fields_reg.get("mapped_fields", [])}


def build_evidence(actions_reg, fields_reg, selection):
    action_ids = index_actions(actions_reg)
    frag_ids = index_fragments(actions_reg)
    field_ids = index_fields(fields_reg)

    labels = []
    findings = []
    seen = set()

    for e in selection.get("evidence_labels", []):
        eid = e.get("evidence_id")
        basis = BASIS_NORMALISE.get(e.get("basis"), e.get("basis"))
        mandatory = bool(e.get("mandatory_legal_attachment_claimed"))
        frags = e.get("source_fragments", []) or []
        las = e.get("legal_actions", []) or []
        supports = e.get("supports_fields", []) or []

        # 1. Must have a unique id.
        if not eid:
            findings.append({"severity": "error", "code": "evidence.no_id",
                             "message": "An evidence label has no evidence_id."})
            continue
        if eid in seen:
            findings.append({"severity": "error", "code": "evidence.duplicate_id",
                             "message": "Duplicate evidence_id '{}'.".format(eid)})
            continue
        seen.add(eid)

        # 2. Basis must be from the canonical set.
        if basis not in KNOWN_BASIS:
            findings.append({"severity": "error", "code": "evidence.bad_basis",
                             "message": "Evidence '{}' has basis '{}' outside the allowed set {}.".format(
                                 eid, basis, sorted(KNOWN_BASIS))})

        # 3. THE CORE SAFETY RULE.
        #    A mandatory legal attachment claim is only honest if the basis is
        #    'direct' AND at least one source fragment backs it.
        if mandatory:
            if basis != "direct":
                findings.append({"severity": "error", "code": "evidence.unsafe_mandatory_claim",
                                 "message": "Evidence '{}' claims to be a mandatory legal attachment but its basis is '{}', not 'direct'.".format(eid, basis)})
            if not frags:
                findings.append({"severity": "error", "code": "evidence.mandatory_no_source",
                                 "message": "Evidence '{}' claims to be a mandatory legal attachment but cites no source fragment.".format(eid)})

        # 4. Anchoring: references must exist upstream.
        for la in las:
            if la not in action_ids:
                findings.append({"severity": "error", "code": "evidence.unknown_action",
                                 "message": "Evidence '{}' references legal action '{}' that does not exist.".format(eid, la)})
        for fr in frags:
            if fr not in frag_ids:
                findings.append({"severity": "warning", "code": "evidence.fragment_not_in_actions",
                                 "message": "Evidence '{}' cites fragment '{}' not referenced by any legal action.".format(eid, fr)})
        for fld in supports:
            if fld not in field_ids:
                findings.append({"severity": "error", "code": "evidence.supports_unknown_field",
                                 "message": "Evidence '{}' supports field '{}' that is not in the mapped fields.".format(eid, fld)})

        # 5. Must carry a human reason.
        if not (e.get("derivation_reason") or "").strip():
            findings.append({"severity": "warning", "code": "evidence.no_reason",
                             "message": "Evidence '{}' has no derivation_reason; the review gate is incomplete.".format(eid)})

        labels.append({
            "evidence_id": eid,
            "label": e.get("label"),
            "basis": basis,
            "evidence_role": e.get("evidence_role"),
            "legal_actions": las,
            "source_fragments": frags,
            "supports_fields": supports,
            "required_for_profile_review": bool(e.get("required_for_profile_review")),
            "mandatory_legal_attachment_claimed": mandatory,
            "disclosure": e.get("disclosure"),
            "derivation_reason": e.get("derivation_reason"),
            "review_note": e.get("review_note"),
        })

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    status = "fail" if errors else ("pass_with_warnings" if warnings else "pass")

    return {
        "schema": SCHEMA_OUT,
        "profile_id": selection.get("profile_id"),
        "title": selection.get("title"),
        "status": status,
        "review_gate": selection.get("review_gate"),
        "summary": {
            "evidence_total": len(labels),
            "errors": errors,
            "warnings": warnings,
            "mandatory_claims": sum(1 for l in labels if l["mandatory_legal_attachment_claimed"]),
            "by_basis": {b: sum(1 for l in labels if l["basis"] == b) for b in sorted(KNOWN_BASIS)},
        },
        "legal_actions_status": actions_reg.get("status"),
        "mapped_fields_status": fields_reg.get("status"),
        "evidence_labels": labels,
        "findings": findings,
        "non_claims": [
            "Evidence labels are supporting annotations on fields, not new legal duties.",
            "An evidence label is not a mandatory legal attachment unless the source explicitly requires it.",
            "This register does not decide what evidence a regulator will accept.",
            "Evidence labels mark how supporting records relate to fields; they do not assert legal completeness.",
        ],
    }


def render_markdown(reg):
    lines = []
    lines.append("# Evidence labels")
    lines.append("")
    lines.append("**Profile:** `{}`".format(reg.get("profile_id")))
    lines.append("**Status:** `{}`".format(reg.get("status")))
    lines.append("")
    s = reg["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append("- Evidence labels: **{}**".format(s["evidence_total"]))
    lines.append("- Errors: **{}**".format(s["errors"]))
    lines.append("- Warnings: **{}**".format(s["warnings"]))
    lines.append("- Mandatory legal attachment claims: **{}**".format(s["mandatory_claims"]))
    lines.append("- By basis: {}".format(", ".join("{}: {}".format(k, v) for k, v in s["by_basis"].items() if v)))
    lines.append("")
    lines.append("## Evidence")
    lines.append("")
    lines.append("| Evidence | Basis | Mandatory? | Supports fields | Source fragments |")
    lines.append("|---|---|---|---|---|")
    for l in reg["evidence_labels"]:
        lines.append("| `{}` | `{}` | {} | {} | {} |".format(
            l.get("evidence_id"),
            l.get("basis"),
            "yes" if l.get("mandatory_legal_attachment_claimed") else "no",
            ", ".join("`{}`".format(f) for f in l.get("supports_fields", [])) or "-",
            ", ".join("`{}`".format(f) for f in l.get("source_fragments", [])) or "-",
        ))
    lines.append("")
    if reg["findings"]:
        lines.append("## Findings")
        lines.append("")
        for fd in reg["findings"]:
            lines.append("- **{}** `{}` - {}".format(fd["severity"].upper(), fd["code"], fd["message"]))
        lines.append("")
    lines.append("## Non-claims")
    lines.append("")
    for nc in reg["non_claims"]:
        lines.append("- {}".format(nc))
    lines.append("")
    return "\n".join(lines)


def render_check_log(reg):
    lines = []
    lines.append("ActProof Mapper - Step 5: evidence labels")
    lines.append("=" * 41)
    lines.append("Profile: {}".format(reg.get("profile_id")))
    lines.append("Status:  {}".format(reg.get("status")))
    s = reg["summary"]
    lines.append("Evidence: {} total, {} errors, {} warnings, {} mandatory claims".format(
        s["evidence_total"], s["errors"], s["warnings"], s["mandatory_claims"]))
    lines.append("")
    for fd in reg["findings"]:
        lines.append("[{}] {}: {}".format(fd["severity"], fd["code"], fd["message"]))
    if not reg["findings"]:
        lines.append("No findings.")
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
        description="ActProof Mapper Step 5: build the evidence label register with a hard mandatory-attachment guardrail.")
    ap.add_argument("--actions", required=True, help="Path to legal-actions.json (Step 3 output)")
    ap.add_argument("--fields", required=True, help="Path to mapped-fields.json (Step 4 output)")
    ap.add_argument("--evidence", required=True, help="Path to selected-evidence-labels.json (human review gate)")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    with open(args.actions, encoding="utf-8") as fh:
        actions_reg = json.load(fh)
    with open(args.fields, encoding="utf-8") as fh:
        fields_reg = json.load(fh)
    with open(args.evidence, encoding="utf-8") as fh:
        selection = json.load(fh)

    if actions_reg.get("schema") != SCHEMA_ACTIONS:
        print("WARNING: expected actions schema '{}', got '{}'".format(
            SCHEMA_ACTIONS, actions_reg.get("schema")), file=sys.stderr)
    if fields_reg.get("schema") != SCHEMA_FIELDS:
        print("WARNING: expected fields schema '{}', got '{}'".format(
            SCHEMA_FIELDS, fields_reg.get("schema")), file=sys.stderr)
    if selection.get("schema") != SCHEMA_EVIDENCE_IN:
        print("WARNING: expected evidence schema '{}', got '{}'".format(
            SCHEMA_EVIDENCE_IN, selection.get("schema")), file=sys.stderr)

    os.makedirs(args.out, exist_ok=True)
    reg = build_evidence(actions_reg, fields_reg, selection)

    dump_json(reg, os.path.join(args.out, "evidence-labels.json"))
    dump_text(render_markdown(reg), os.path.join(args.out, "evidence-labels.md"))
    dump_text(render_check_log(reg), os.path.join(args.out, "evidence-check.txt"))

    print(render_check_log(reg))

    # Exit codes: 0 = pass, 1 = structural failure, 2 = warnings under strict mode.
    # When ACTPROOF_STRICT=1 (set by run_all.py --stop-on-warning), warnings stop
    # the pipeline. By default warnings are surfaced but do not stop the run.
    if reg["status"] == "fail":
        sys.exit(1)
    if reg["status"] == "pass_with_warnings" and os.environ.get("ACTPROOF_STRICT") == "1":
        sys.exit(2)


if __name__ == "__main__":
    main()
