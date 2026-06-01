#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
ActProof Mapper - Step 3: Legal Actions
========================================

WHAT THIS STEP DOES (in plain words)
------------------------------------
Step 2 gave us named pieces of law (fragments). But a fragment is still just
"a piece of text". For a compliance or legal user, the real question about any
rule is:

    Who must do what, to whom, by when, and under what condition?

This step decomposes the selected provisions into "legal actions" that answer
exactly that. For example, DORA Article 19(4) becomes an action like:

    actor:      financial_entity      (who must act)
    action:     submit                (what they must do)
    object:     initial_notification  (the thing submitted)
    recipient:  competent_authority   (to whom)
    condition:  incident_classified_as_major   (when the duty is triggered)
    deadline:   PT4H                  (by when)

This is what turns a profile from "a list of fields" into "a legal act broken
into its operational parts". It is the layer that makes the profile legally
intelligible.

THE REVIEW GATE (why this is a controlled process)
--------------------------------------------------
This is the second human review gate. Legal actions are NOT extracted
automatically from text. A person decomposes the provisions and writes a
"selected-legal-actions" file. This step's job is to check those actions are
well-formed and that every one points to fragments that actually exist in the
Step 2 register. An action cannot be invented out of nothing.

WHAT THIS STEP DOES NOT DO (the boundary)
-----------------------------------------
- It does not auto-extract obligations from legal text. A human decomposes them.
- It does not decide whether a real-world duty has been met.
- It does not compute a legal outcome. It records the rule's structure only.

INPUT
-----
--fragments   path to source-fragments.json   (output of Step 2)
--actions     path to selected-legal-actions.json   (the human review gate)
--out         output directory

OUTPUT (written to --out)
-------------------------
legal-actions.json    machine-readable legal action register
legal-actions.md      human-readable summary
actions-check.txt     short console-style check log

DETERMINISM
-----------
JSON output uses sorted keys, two-space indent, LF endings, trailing newline.
Actions preserve the human-declared order.
"""

import argparse
import json
import os
import re
import sys


SCHEMA_FRAGMENTS = "actproof.source_fragments.v0"
SCHEMA_ACTIONS_IN = "actproof.selected_legal_actions.v0"
SCHEMA_OUT = "actproof.legal_actions.v0"

# Frozen vocabulary. A legal action is one of these kinds.
# (prohibition is reserved for future acts; permitted but currently unused.)
KNOWN_MODALITIES = {"obligation", "permission", "prohibition", "procedure"}

# Action IDs: dotted, no spaces.
ACTION_ID_RE = re.compile(r"^[A-Za-z0-9]+(\.[A-Za-z0-9_]+)+$")

# ISO 8601 duration sanity check for deadlines (e.g. PT4H, PT24H, P1M).
DURATION_RE = re.compile(r"^P(\d+[YMWD])*(T(\d+[HMS])+)?$")


def index_fragments(fragments_reg):
    """Map fragment_id -> role, so actions can be checked and enriched."""
    out = {}
    for f in fragments_reg.get("source_fragments", []):
        out[f.get("fragment_id")] = f.get("role")
    return out


def build_actions(fragments_reg, selection):
    frag_roles = index_fragments(fragments_reg)
    actions = []
    findings = []
    seen_ids = set()

    for a in selection.get("legal_actions", []):
        aid = a.get("action_id")
        modality = a.get("modality")
        src_frags = a.get("source_fragments", []) or []

        # --- Guardrails ---

        # 1. Must have a well-formed, unique ID.
        if not aid:
            findings.append({"severity": "error", "code": "action.no_id",
                             "message": "A selected legal action has no action_id."})
            continue
        if not ACTION_ID_RE.match(aid):
            findings.append({"severity": "warning", "code": "action.id_format",
                             "message": "Action id '{}' is not in the recommended dotted form.".format(aid)})
        if aid in seen_ids:
            findings.append({"severity": "error", "code": "action.duplicate_id",
                             "message": "Duplicate action_id '{}'.".format(aid)})
            continue
        seen_ids.add(aid)

        # 2. Modality must be from the frozen vocabulary.
        if modality not in KNOWN_MODALITIES:
            findings.append({"severity": "error", "code": "action.bad_modality",
                             "message": "Action '{}' has modality '{}' outside the allowed set {}.".format(
                                 aid, modality, sorted(KNOWN_MODALITIES))})

        # 3. Must reference at least one source fragment, and each must exist.
        if not src_frags:
            findings.append({"severity": "error", "code": "action.no_source",
                             "message": "Action '{}' has no source_fragments; it is not anchored to any provision.".format(aid)})
        unknown = [f for f in src_frags if f not in frag_roles]
        if unknown:
            findings.append({"severity": "error", "code": "action.unknown_fragment",
                             "message": "Action '{}' references fragment(s) not in the register: {}.".format(aid, unknown)})

        # 4. An obligation should say to whom and under what condition.
        #    (warning, not error: some obligations are unconditional.)
        if modality == "obligation":
            if not a.get("recipient") and not a.get("authority"):
                findings.append({"severity": "warning", "code": "action.obligation_no_recipient",
                                 "message": "Obligation '{}' names neither a recipient nor an authority.".format(aid)})
            if not a.get("condition"):
                findings.append({"severity": "warning", "code": "action.obligation_no_condition",
                                 "message": "Obligation '{}' has no trigger condition.".format(aid)})

        # 5. Deadline, if present, should be a valid ISO 8601 duration.
        #    In the real model a deadline may be a bare string ("PT4H") OR a
        #    structured object {"value": "PT4H", "trigger": ..., "source_fragments": [...]}.
        #    We validate the duration value in either shape.
        for key in ("deadline", "outer_limit"):
            val = a.get(key)
            if not val:
                continue
            duration = val.get("value") if isinstance(val, dict) else val
            if not isinstance(duration, str) or not DURATION_RE.match(duration):
                findings.append({"severity": "warning", "code": "action.bad_duration",
                                 "message": "Action '{}' {} '{}' is not a valid ISO 8601 duration.".format(aid, key, duration)})
            # If the deadline object cites its own source fragments, they must exist too.
            if isinstance(val, dict):
                for f in val.get("source_fragments", []) or []:
                    if f not in frag_roles:
                        findings.append({"severity": "error", "code": "action.deadline_unknown_fragment",
                                         "message": "Action '{}' {} cites fragment '{}' not in the register.".format(aid, key, f)})

        # 6. Every action should carry an operational purpose (the human reason).
        if not (a.get("operational_purpose") or "").strip():
            findings.append({"severity": "warning", "code": "action.no_purpose",
                             "message": "Action '{}' has no operational_purpose; the review gate is incomplete.".format(aid)})

        actions.append({
            "action_id": aid,
            "modality": modality,
            "actor": a.get("actor"),
            "action": a.get("action"),
            "object": a.get("object"),
            "recipient": a.get("recipient"),
            "authority": a.get("authority"),
            "condition": a.get("condition"),
            "deadline": a.get("deadline"),
            "outer_limit": a.get("outer_limit"),
            "exception": a.get("exception"),
            "source_fragments": src_frags,
            # Enrich with the roles of the cited fragments, for readability.
            "source_fragment_roles": [frag_roles.get(f) for f in src_frags if f in frag_roles],
            "operational_purpose": a.get("operational_purpose"),
            "review_note": a.get("review_note"),
            "notes": a.get("notes"),
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
            "actions_total": len(actions),
            "errors": errors,
            "warnings": warnings,
            "selection_method": selection.get("selection_method", "human_decomposed_actions"),
        },
        "source_fragment_register_status": fragments_reg.get("status"),
        "legal_actions": actions,
        "findings": findings,
        "non_claims": [
            "Legal actions are a human decomposition of selected provisions, not an automatic extraction.",
            "This register records the structure of a duty; it does not decide whether a real duty was met.",
            "This register does not compute legal outcomes or assert legal completeness.",
            "Validity here is structural and reference-level only.",
        ],
    }


def render_markdown(reg):
    lines = []
    lines.append("# Legal actions")
    lines.append("")
    lines.append("**Profile:** `{}`".format(reg.get("profile_id")))
    lines.append("**Status:** `{}`".format(reg.get("status")))
    lines.append("")
    s = reg["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append("- Actions: **{}**".format(s["actions_total"]))
    lines.append("- Errors: **{}**".format(s["errors"]))
    lines.append("- Warnings: **{}**".format(s["warnings"]))
    lines.append("")
    lines.append("## Actions")
    lines.append("")
    lines.append("| Action | Modality | Actor | Action | To whom | Condition | Deadline |")
    lines.append("|---|---|---|---|---|---|---|")
    for a in reg["legal_actions"]:
        lines.append("| `{}` | {} | {} | {} | {} | {} | {} |".format(
            a.get("action_id"),
            a.get("modality") or "",
            a.get("actor") or "",
            a.get("action") or "",
            a.get("recipient") or a.get("authority") or "",
            a.get("condition") or "",
            a.get("deadline") or "",
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
    lines.append("ActProof Mapper - Step 3: legal actions")
    lines.append("=" * 39)
    lines.append("Profile: {}".format(reg.get("profile_id")))
    lines.append("Status:  {}".format(reg.get("status")))
    s = reg["summary"]
    lines.append("Actions: {} total, {} errors, {} warnings".format(
        s["actions_total"], s["errors"], s["warnings"]))
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
        description="ActProof Mapper Step 3: decompose selected provisions into legal actions.")
    ap.add_argument("--fragments", required=True, help="Path to source-fragments.json (Step 2 output)")
    ap.add_argument("--actions", required=True, help="Path to selected-legal-actions.json (human review gate)")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    with open(args.fragments, encoding="utf-8") as fh:
        fragments_reg = json.load(fh)
    with open(args.actions, encoding="utf-8") as fh:
        selection = json.load(fh)

    if fragments_reg.get("schema") != SCHEMA_FRAGMENTS:
        print("WARNING: expected fragments schema '{}', got '{}'".format(
            SCHEMA_FRAGMENTS, fragments_reg.get("schema")), file=sys.stderr)
    if selection.get("schema") != SCHEMA_ACTIONS_IN:
        print("WARNING: expected actions schema '{}', got '{}'".format(
            SCHEMA_ACTIONS_IN, selection.get("schema")), file=sys.stderr)

    os.makedirs(args.out, exist_ok=True)
    reg = build_actions(fragments_reg, selection)

    dump_json(reg, os.path.join(args.out, "legal-actions.json"))
    dump_text(render_markdown(reg), os.path.join(args.out, "legal-actions.md"))
    dump_text(render_check_log(reg), os.path.join(args.out, "actions-check.txt"))

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
