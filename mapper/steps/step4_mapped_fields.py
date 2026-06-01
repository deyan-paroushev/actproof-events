#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
ActProof Mapper - Step 4: Mapped Fields
========================================

WHAT THIS STEP DOES (in plain words)
------------------------------------
By now we have: verified sources (Step 1), named fragments of the law
(Step 2), and the legal actions broken into who/what/when (Step 3).

This step produces the actual fields of the profile - and, crucially, records
HOW each field was derived. For every field it answers:

    - Which legal action(s) does this field serve?
    - Which source fragment(s) does it rest on?
    - Is it a direct reading of the source, a derivation, an interpretation,
      or just an operational support field?
    - Why was it mapped this way? (the human reason)

This is the step that makes the difference between "here are 27 fields" and
"here is each field, and exactly where it came from".

THE REVIEW GATE (why this is a controlled process)
--------------------------------------------------
This is the third human review gate, and the most important one. A person
writes a "selected-field-derivations" file declaring how each field maps back
to actions and fragments. This step joins that against the field list and the
legal actions, and enforces the core rule:

    Every field must explain itself. A field with no source fragment AND no
    interpretation basis is not allowed to pass silently.

WHAT THIS STEP DOES NOT DO (the boundary)
-----------------------------------------
- It does not invent fields. Fields come from the profile draft.
- It does not auto-derive mappings. A human declares each derivation.
- It does not judge whether the mapping is legally correct - only whether it
  is structurally honest: anchored, typed, and with its basis stated.

INPUT
-----
--actions       path to legal-actions.json   (output of Step 3)
--profile       path to profile-draft.json   (the field list to map)
--derivations   path to selected-field-derivations.json   (the human review gate)
--out           output directory

OUTPUT (written to --out)
-------------------------
mapped-fields.json    machine-readable mapped-field register
mapped-fields.md      human-readable summary
fields-check.txt      short console-style check log

DETERMINISM
-----------
JSON output uses sorted keys, two-space indent, LF endings, trailing newline.
Fields preserve the profile-draft order.
"""

import argparse
import json
import os
import sys

# Shared multi-proposal interpretation-link model (additive; the flat
# interpretation_decisions list is preserved alongside it and deprecated).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _interpretation_link import link_from_legacy  # noqa: E402


SCHEMA_ACTIONS = "actproof.legal_actions.v0"
SCHEMA_PROFILE = "actproof.profile_draft.v0"
SCHEMA_DERIV_IN = "actproof.selected_field_derivations.v0"
SCHEMA_OUT = "actproof.mapped_fields.v0"

# Frozen vocabulary for how a field relates to its source.
KNOWN_MAPPING_STATUS = {
    "direct_source_mapping",       # field text maps directly to a source fragment
    "derived_from_legal_action",   # field derived from a decomposed legal action
    "interpretive_mapping",        # field rests on a recorded interpretation decision
    "operational_support_field",   # operational support, not source-required
    "untraced",                    # no trace yet (validation flags this)
}

# Legacy synonyms normalised on the way in, so old data converges on canonical.
MAPPING_STATUS_NORMALISE = {
    "direct": "direct_source_mapping",
    "direct_plus_interpretation": "interpretive_mapping",
}

# A mapping_status that requires an interpretation basis to be honest.
REQUIRES_INTERPRETATION = {"interpretive_mapping"}


def _legacy_links(derivation):
    """Build a multi-proposal interpretation link from a derivation's flat list.

    Each decision id in the flat interpretation_decisions list becomes one
    attributed proposal. Attribution comes from the derivation's optional
    'proposed_by' field (a model name+version, or a human handle); if absent we
    record it as 'unattributed' rather than guess. Affirmation defaults to
    'proposed': no human has affirmed yet. This is the honest migration of the
    legacy flat list into the multi-proposal model without claiming a human
    affirmed anything.
    """
    decision_ids = derivation.get("interpretation_decisions", []) or []
    if not decision_ids:
        return None
    proposed_by = derivation.get("proposed_by", "unattributed")
    proposed_at = derivation.get("proposed_at")
    rationale = derivation.get("derivation_reason")
    link = link_from_legacy(decision_ids, proposed_by=proposed_by,
                            proposed_at=proposed_at, rationale=rationale)
    return link


def index_actions(actions_reg):
    return {a.get("action_id") for a in actions_reg.get("legal_actions", [])}


def index_fragments_from_actions(actions_reg):
    """Collect every fragment referenced by any action, so field fragments can be checked."""
    frags = set()
    for a in actions_reg.get("legal_actions", []):
        for f in a.get("source_fragments", []) or []:
            frags.add(f)
        for key in ("deadline", "outer_limit"):
            val = a.get(key)
            if isinstance(val, dict):
                for f in val.get("source_fragments", []) or []:
                    frags.add(f)
    return frags


def index_field_meta(profile_draft):
    out = {}
    for f in profile_draft.get("fields", []):
        out[f.get("field_id")] = f
    return out


def build_mapped_fields(actions_reg, profile_draft, derivations):
    action_ids = index_actions(actions_reg)
    known_frags = index_fragments_from_actions(actions_reg)
    field_meta = index_field_meta(profile_draft)
    deriv_by_field = {d.get("field_id"): d for d in derivations.get("field_derivations", [])}

    draft_field_ids = [f.get("field_id") for f in profile_draft.get("fields", [])]

    mapped = []
    findings = []

    for fid in draft_field_ids:
        meta = field_meta.get(fid, {})
        d = deriv_by_field.get(fid)

        # 1. Every field in the draft must have a derivation declared.
        if d is None:
            findings.append({"severity": "error", "code": "field.no_derivation",
                             "message": "Field '{}' is in the profile draft but has no declared derivation.".format(fid)})
            mapped.append({
                "field_id": fid, "label": meta.get("label"), "type": meta.get("type"),
                "required": meta.get("required"), "disclosure": meta.get("disclosure"),
                "mapping_status": "untraced", "legal_actions": [], "source_fragments": [],
                "derivation_reason": None, "review_note": None,
            })
            continue

        status = MAPPING_STATUS_NORMALISE.get(d.get("mapping_status"), d.get("mapping_status"))
        las = d.get("legal_actions", []) or []
        frags = d.get("source_fragments", []) or []
        reason = d.get("derivation_reason")

        # 2. mapping_status must be from the frozen vocabulary.
        if status not in KNOWN_MAPPING_STATUS:
            findings.append({"severity": "error", "code": "field.bad_mapping_status",
                             "message": "Field '{}' has mapping_status '{}' outside the allowed set.".format(fid, status)})

        # 3. The core honesty rule: a field must be anchored.
        #    Source-backed statuses need a fragment; interpretive needs a reason;
        #    operational support needs at least a reason. Nothing passes empty.
        if status in ("direct_source_mapping", "derived_from_legal_action"):
            if not frags:
                findings.append({"severity": "error", "code": "field.unanchored",
                                 "message": "Field '{}' is '{}' but cites no source fragment.".format(fid, status)})
        if status in REQUIRES_INTERPRETATION and not (reason or "").strip():
            findings.append({"severity": "error", "code": "field.interpretation_no_reason",
                             "message": "Field '{}' is interpretive but gives no derivation_reason.".format(fid)})
        if status == "operational_support_field" and not (reason or "").strip():
            findings.append({"severity": "warning", "code": "field.support_no_reason",
                             "message": "Operational support field '{}' has no derivation_reason.".format(fid)})

        # 4. A direct mapping should NOT silently rest on interpretation.
        #    (This is a cross-layer honesty check.)
        if status == "direct_source_mapping" and d.get("interpretation_decisions"):
            findings.append({"severity": "warning", "code": "field.direct_with_interpretation",
                             "message": "Field '{}' is marked direct but also lists interpretation decisions.".format(fid)})

        # 5. Referenced actions and fragments must actually exist upstream.
        for la in las:
            if la not in action_ids:
                findings.append({"severity": "error", "code": "field.unknown_action",
                                 "message": "Field '{}' references legal action '{}' that does not exist.".format(fid, la)})
        for fr in frags:
            if fr not in known_frags:
                findings.append({"severity": "warning", "code": "field.fragment_not_in_actions",
                                 "message": "Field '{}' cites fragment '{}' not referenced by any legal action.".format(fid, fr)})

        # 6. Required fields should not be operational support.
        if meta.get("required") and status == "operational_support_field":
            findings.append({"severity": "warning", "code": "field.required_is_support",
                             "message": "Field '{}' is required but mapped as operational_support_field.".format(fid)})

        mapped.append({
            "field_id": fid,
            "label": meta.get("label"),
            "type": meta.get("type"),
            "required": meta.get("required"),
            "disclosure": meta.get("disclosure"),
            "mapping_status": status,
            "legal_actions": las,
            "source_fragments": frags,
            # DEPRECATED (kept on record, slated for removal at the v0->v1 freeze):
            # the flat list of decision ids with no attribution. Consumers should
            # migrate to interpretation_links below. Retained so nothing breaks.
            "interpretation_decisions": d.get("interpretation_decisions", []),
            # NEW: multi-proposal, host-neutral interpretation links. Each AI or
            # human proposal is attributed; affirmation defaults to 'proposed'
            # until a human maintainer affirms. Built from the flat list, marking
            # these as proposals (here attributed to the model that drafted them).
            "interpretation_links": (
                d.get("interpretation_links")
                or _legacy_links(d)
            ),
            "derivation_reason": reason,
            "review_note": d.get("review_note"),
        })

    # Note any derivations for fields that are not in the draft (orphans).
    for fid in deriv_by_field:
        if fid not in field_meta:
            findings.append({"severity": "warning", "code": "field.derivation_orphan",
                             "message": "A derivation exists for '{}' which is not in the profile draft.".format(fid)})

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    status_overall = "fail" if errors else ("pass_with_warnings" if warnings else "pass")

    return {
        "schema": SCHEMA_OUT,
        "profile_id": derivations.get("profile_id"),
        "title": derivations.get("title"),
        "status": status_overall,
        "review_gate": derivations.get("review_gate"),
        "summary": {
            "fields_total": len(mapped),
            "errors": errors,
            "warnings": warnings,
            "by_status": {s: sum(1 for m in mapped if m["mapping_status"] == s)
                          for s in sorted(KNOWN_MAPPING_STATUS)},
        },
        "legal_actions_status": actions_reg.get("status"),
        "profile_draft_status": profile_draft.get("status"),
        "mapped_fields": mapped,
        "findings": findings,
        "non_claims": [
            "Mapped fields are a human-declared derivation, not an automatic mapping.",
            "A field's mapping_status records how it was derived, not that the derivation is legally correct.",
            "This register does not assert legal completeness of the field set.",
            "Validity here is structural: every field is anchored, typed and its basis stated.",
        ],
    }


def render_markdown(reg):
    lines = []
    lines.append("# Mapped fields")
    lines.append("")
    lines.append("**Profile:** `{}`".format(reg.get("profile_id")))
    lines.append("**Status:** `{}`".format(reg.get("status")))
    lines.append("")
    s = reg["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append("- Fields: **{}**".format(s["fields_total"]))
    lines.append("- Errors: **{}**".format(s["errors"]))
    lines.append("- Warnings: **{}**".format(s["warnings"]))
    lines.append("- By status: {}".format(", ".join("{}: {}".format(k, v) for k, v in s["by_status"].items() if v)))
    lines.append("")
    lines.append("## Fields")
    lines.append("")
    lines.append("| Field | Type | Req | Disclosure | Mapping status | Source fragments |")
    lines.append("|---|---|---|---|---|---|")
    for m in reg["mapped_fields"]:
        lines.append("| `{}` | {} | {} | {} | `{}` | {} |".format(
            m.get("field_id"),
            m.get("type") or "",
            "yes" if m.get("required") else "no",
            m.get("disclosure") or "",
            m.get("mapping_status"),
            ", ".join("`{}`".format(f) for f in m.get("source_fragments", [])) or "-",
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
    lines.append("ActProof Mapper - Step 4: mapped fields")
    lines.append("=" * 39)
    lines.append("Profile: {}".format(reg.get("profile_id")))
    lines.append("Status:  {}".format(reg.get("status")))
    s = reg["summary"]
    lines.append("Fields: {} total, {} errors, {} warnings".format(
        s["fields_total"], s["errors"], s["warnings"]))
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
        description="ActProof Mapper Step 4: derive mapped fields from legal actions and a human derivation selection.")
    ap.add_argument("--actions", required=True, help="Path to legal-actions.json (Step 3 output)")
    ap.add_argument("--profile", required=True, help="Path to profile-draft.json (field list)")
    ap.add_argument("--derivations", required=True, help="Path to selected-field-derivations.json (human review gate)")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    with open(args.actions, encoding="utf-8") as fh:
        actions_reg = json.load(fh)
    with open(args.profile, encoding="utf-8") as fh:
        profile_draft = json.load(fh)
    with open(args.derivations, encoding="utf-8") as fh:
        derivations = json.load(fh)

    if actions_reg.get("schema") != SCHEMA_ACTIONS:
        print("WARNING: expected actions schema '{}', got '{}'".format(
            SCHEMA_ACTIONS, actions_reg.get("schema")), file=sys.stderr)
    if derivations.get("schema") != SCHEMA_DERIV_IN:
        print("WARNING: expected derivations schema '{}', got '{}'".format(
            SCHEMA_DERIV_IN, derivations.get("schema")), file=sys.stderr)

    os.makedirs(args.out, exist_ok=True)
    reg = build_mapped_fields(actions_reg, profile_draft, derivations)

    dump_json(reg, os.path.join(args.out, "mapped-fields.json"))
    dump_text(render_markdown(reg), os.path.join(args.out, "mapped-fields.md"))
    dump_text(render_check_log(reg), os.path.join(args.out, "fields-check.txt"))

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
