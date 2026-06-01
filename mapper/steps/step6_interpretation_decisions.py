#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
ActProof Mapper - Step 6: Interpretation Decisions
===================================================

WHAT THIS STEP DOES (in plain words)
------------------------------------
Every mapping from law to JSON involves judgement. Someone decided to
normalise all times to UTC. Someone decided a sensitive field should be a
commitment rather than public. Someone decided to include a supporting record
the law does not explicitly demand.

In most legal tech, those judgements are invisible - buried in a developer's
head, a spreadsheet, or a vendor's config. That is exactly the "black box"
problem ActProof exists to fix.

This step is the judgement register. For every non-obvious choice it records:

    - the question that was faced
    - the option chosen
    - the alternatives that were considered
    - the reason
    - which source fragments informed it
    - which fields or evidence labels it affects
    - and a status: open_to_challenge, reviewed, settled, or superseded

This is the layer that makes the profile honest. It does not hide where
interpretation entered the system. Anyone can read a decision, disagree, and
challenge it in the open.

DECISION LIFECYCLE (so meaning never silently changes)
------------------------------------------------------
A decision can change over time. If it does, the meaning must not silently
shift under the same name. So each decision carries a version, and a changed
decision records what it supersedes:

    decision_id:      dec.dora.utc_normalisation
    decision_version: v2
    supersedes:       dec.dora.utc_normalisation@v1

Old trace rows that referenced v1 still mean what they meant.

THE REVIEW GATE
---------------
A human writes a "selected-interpretation-decisions" file. This step checks
each decision is anchored (real fragments, real affected elements), has a
status from the frozen set, and carries a question and a reason.

WHAT THIS STEP DOES NOT DO (the boundary)
-----------------------------------------
- It does not decide which interpretation is legally correct.
- It does not resolve a challenge. It records the decision and its status.
- A recorded decision is a transparent reading, not an official ruling.

INPUT
-----
--fields     path to mapped-fields.json   (output of Step 4)
--evidence   path to evidence-labels.json   (output of Step 5)
--decisions  path to selected-interpretation-decisions.json   (human review gate)
--out        output directory

OUTPUT (written to --out)
-------------------------
interpretation-decisions.json   machine-readable register
interpretation-decisions.md     human-readable summary
decisions-check.txt             short console-style check log

DETERMINISM
-----------
JSON output uses sorted keys, two-space indent, LF endings, trailing newline.
Decisions preserve declared order.
"""

import argparse
import json
import os
import re
import sys


SCHEMA_FIELDS = "actproof.mapped_fields.v0"
SCHEMA_EVIDENCE = "actproof.evidence_labels.v0"
SCHEMA_DECISIONS_IN = "actproof.selected_interpretation_decisions.v0"
SCHEMA_OUT = "actproof.interpretation_decisions.v0"

# Frozen status vocabulary for a decision's challenge lifecycle.
KNOWN_STATUS = {"open_to_challenge", "reviewed", "settled", "superseded"}

# decision_id@version reference, used by supersedes / superseded_by.
SUPERSEDE_RE = re.compile(r"^[A-Za-z0-9]+(\.[A-Za-z0-9_]+)+@v\d+$")


def index_fields(fields_reg):
    return {m.get("field_id") for m in fields_reg.get("mapped_fields", [])}


def index_evidence(evidence_reg):
    return {e.get("evidence_id") for e in evidence_reg.get("evidence_labels", [])}


def index_fragments_from_fields(fields_reg):
    frags = set()
    for m in fields_reg.get("mapped_fields", []):
        frags.update(m.get("source_fragments", []) or [])
    return frags


def build_decisions(fields_reg, evidence_reg, selection):
    field_ids = index_fields(fields_reg)
    evidence_ids = index_evidence(evidence_reg)
    known_elements = field_ids | evidence_ids
    known_frags = index_fragments_from_fields(fields_reg)

    decisions = []
    findings = []
    seen = set()

    for d in selection.get("interpretation_decisions", []):
        did = d.get("decision_id")
        status = d.get("status")
        version = d.get("decision_version", "v1")
        supersedes = d.get("supersedes")
        affected = d.get("affected_elements", []) or []
        frags = d.get("source_fragments", []) or []

        # 1. Unique id.
        if not did:
            findings.append({"severity": "error", "code": "decision.no_id",
                             "message": "An interpretation decision has no decision_id."})
            continue
        key = "{}@{}".format(did, version)
        if key in seen:
            findings.append({"severity": "error", "code": "decision.duplicate",
                             "message": "Duplicate decision '{}'.".format(key)})
            continue
        seen.add(key)

        # 2. Status must be from the frozen set.
        if status not in KNOWN_STATUS:
            findings.append({"severity": "error", "code": "decision.bad_status",
                             "message": "Decision '{}' has status '{}' outside the allowed set {}.".format(
                                 did, status, sorted(KNOWN_STATUS))})

        # 3. Must carry a question and a reason (no silent judgement).
        if not (d.get("question") or "").strip():
            findings.append({"severity": "error", "code": "decision.no_question",
                             "message": "Decision '{}' records no question.".format(did)})
        if not (d.get("reason") or "").strip():
            findings.append({"severity": "error", "code": "decision.no_reason",
                             "message": "Decision '{}' records no reason.".format(did)})

        # 4. Must affect at least one element, and affected elements must exist.
        if not affected:
            findings.append({"severity": "warning", "code": "decision.no_affected",
                             "message": "Decision '{}' affects no field or evidence label.".format(did)})
        for el in affected:
            if el not in known_elements:
                findings.append({"severity": "error", "code": "decision.affects_unknown",
                                 "message": "Decision '{}' affects '{}' which is not a known field or evidence label.".format(did, el)})

        # 5. Cited fragments should exist among the mapped fields' fragments.
        for fr in frags:
            if fr not in known_frags:
                findings.append({"severity": "warning", "code": "decision.fragment_unknown",
                                 "message": "Decision '{}' cites fragment '{}' not used by any mapped field.".format(did, fr)})

        # 6. Lifecycle integrity.
        if supersedes and not SUPERSEDE_RE.match(supersedes):
            findings.append({"severity": "warning", "code": "decision.bad_supersedes",
                             "message": "Decision '{}' supersedes '{}' which is not in the 'id@vN' form.".format(did, supersedes)})
        if status == "superseded" and not d.get("superseded_by"):
            findings.append({"severity": "warning", "code": "decision.superseded_no_target",
                             "message": "Decision '{}' is marked superseded but names no superseded_by.".format(did)})

        decisions.append({
            "decision_id": did,
            "decision_version": version,
            "question": d.get("question"),
            "chosen": d.get("chosen"),
            "alternatives_considered": d.get("alternatives_considered", []),
            "reason": d.get("reason"),
            "source_fragments": frags,
            "affected_elements": affected,
            "decision_type": d.get("decision_type"),
            "status": status,
            "supersedes": supersedes,
            "superseded_by": d.get("superseded_by"),
            "reviewer": d.get("reviewer"),
            "date": d.get("date"),
            "notes": d.get("notes"),
        })

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    status_overall = "fail" if errors else ("pass_with_warnings" if warnings else "pass")

    return {
        "schema": SCHEMA_OUT,
        "profile_id": selection.get("profile_id"),
        "title": selection.get("title"),
        "status": status_overall,
        # Carry the human-authored review-gate metadata downstream so the audit
        # trail (who authored, when, why) travels with the register, not only
        # with the input file.
        "review_gate": selection.get("review_gate"),
        "summary": {
            "decisions_total": len(decisions),
            "errors": errors,
            "warnings": warnings,
            "by_status": {s: sum(1 for x in decisions if x["status"] == s) for s in sorted(KNOWN_STATUS)},
        },
        "mapped_fields_status": fields_reg.get("status"),
        "evidence_labels_status": evidence_reg.get("status"),
        "interpretation_decisions": decisions,
        "non_claims": [
            "An interpretation decision is a transparent reading, not an official legal ruling.",
            "Recording a decision does not make it correct; it makes it visible and challengeable.",
            "'open_to_challenge' means exactly that: the choice can be disputed in the open.",
            "This register does not resolve disputes or assert legal completeness.",
        ],
        "findings": findings,
    }


def render_markdown(reg):
    lines = []
    lines.append("# Interpretation decisions")
    lines.append("")
    lines.append("**Profile:** `{}`".format(reg.get("profile_id")))
    lines.append("**Status:** `{}`".format(reg.get("status")))
    lines.append("")
    s = reg["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append("- Decisions: **{}**".format(s["decisions_total"]))
    lines.append("- Errors: **{}**".format(s["errors"]))
    lines.append("- Warnings: **{}**".format(s["warnings"]))
    lines.append("- By status: {}".format(", ".join("{}: {}".format(k, v) for k, v in s["by_status"].items() if v)))
    lines.append("")
    lines.append("## Decisions")
    lines.append("")
    for d in reg["interpretation_decisions"]:
        lines.append("### `{}` ({}) - `{}`".format(d.get("decision_id"), d.get("decision_version"), d.get("status")))
        lines.append("")
        lines.append("- **Question:** {}".format(d.get("question") or ""))
        lines.append("- **Chosen:** {}".format(d.get("chosen") or ""))
        if d.get("alternatives_considered"):
            lines.append("- **Alternatives considered:** {}".format("; ".join(d["alternatives_considered"])))
        lines.append("- **Reason:** {}".format(d.get("reason") or ""))
        lines.append("- **Affects:** {}".format(", ".join("`{}`".format(e) for e in d.get("affected_elements", [])) or "-"))
        lines.append("- **Source fragments:** {}".format(", ".join("`{}`".format(f) for f in d.get("source_fragments", [])) or "-"))
        if d.get("supersedes"):
            lines.append("- **Supersedes:** `{}`".format(d["supersedes"]))
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
    lines.append("ActProof Mapper - Step 6: interpretation decisions")
    lines.append("=" * 50)
    lines.append("Profile: {}".format(reg.get("profile_id")))
    lines.append("Status:  {}".format(reg.get("status")))
    s = reg["summary"]
    lines.append("Decisions: {} total, {} errors, {} warnings".format(
        s["decisions_total"], s["errors"], s["warnings"]))
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
        description="ActProof Mapper Step 6: build the interpretation decision register.")
    ap.add_argument("--fields", required=True, help="Path to mapped-fields.json (Step 4 output)")
    ap.add_argument("--evidence", required=True, help="Path to evidence-labels.json (Step 5 output)")
    ap.add_argument("--decisions", required=True, help="Path to selected-interpretation-decisions.json (human review gate)")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    with open(args.fields, encoding="utf-8") as fh:
        fields_reg = json.load(fh)
    with open(args.evidence, encoding="utf-8") as fh:
        evidence_reg = json.load(fh)
    with open(args.decisions, encoding="utf-8") as fh:
        selection = json.load(fh)

    if fields_reg.get("schema") != SCHEMA_FIELDS:
        print("WARNING: expected fields schema '{}', got '{}'".format(
            SCHEMA_FIELDS, fields_reg.get("schema")), file=sys.stderr)
    if evidence_reg.get("schema") != SCHEMA_EVIDENCE:
        print("WARNING: expected evidence schema '{}', got '{}'".format(
            SCHEMA_EVIDENCE, evidence_reg.get("schema")), file=sys.stderr)
    if selection.get("schema") != SCHEMA_DECISIONS_IN:
        print("WARNING: expected decisions schema '{}', got '{}'".format(
            SCHEMA_DECISIONS_IN, selection.get("schema")), file=sys.stderr)

    os.makedirs(args.out, exist_ok=True)
    reg = build_decisions(fields_reg, evidence_reg, selection)

    dump_json(reg, os.path.join(args.out, "interpretation-decisions.json"))
    dump_text(render_markdown(reg), os.path.join(args.out, "interpretation-decisions.md"))
    dump_text(render_check_log(reg), os.path.join(args.out, "decisions-check.txt"))

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
