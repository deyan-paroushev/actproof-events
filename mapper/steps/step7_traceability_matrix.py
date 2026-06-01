#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
ActProof Mapper - Step 7: Traceability Matrix
==============================================

WHAT THIS STEP DOES (in plain words)
------------------------------------
Steps 2 through 6 each produced one register: fragments, legal actions,
mapped fields, evidence labels, interpretation decisions. Each is useful on its
own, but the real value is in connecting them.

This step builds the traceability matrix: one row for every profile field and
every evidence label, where each row carries its WHOLE chain:

    source fragment(s)
        -> legal action(s)
        -> profile field (or evidence label)
        -> disclosure tier
        -> mapping status
        -> interpretation decision(s)

This is the single most important artefact in the whole pipeline. It is the
table that answers, for any field, "show me exactly how the law became this".
It is what a law firm can hand to an auditor, attach to a memo, or use to
challenge a vendor's schema.

NO HUMAN REVIEW GATE HERE
-------------------------
Unlike steps 2 to 6, this step has no new human input. It is pure assembly: it
weaves together what the human already decided in the earlier gates, and
CHECKS that everything connects. If a field points to a decision that does not
exist, or an evidence label supports a field that is not in the matrix, this
step surfaces it. It cannot invent anything; it can only bind and verify.

WHAT THIS STEP DOES NOT DO (the boundary)
-----------------------------------------
- It does not add new mappings or judgements.
- It does not decide legal correctness.
- It binds and cross-checks the human-authored layers and reports what connects
  and what does not.

INPUT
-----
--fragments   source-fragments.json            (Step 2)
--actions     legal-actions.json               (Step 3)
--fields      mapped-fields.json               (Step 4)
--evidence    evidence-labels.json             (Step 5)
--decisions   interpretation-decisions.json    (Step 6)
--out         output directory

OUTPUT (written to --out)
-------------------------
traceability.json   the matrix (machine-readable)
traceability.md     the matrix (human-readable table)
traceability.csv    the matrix (spreadsheet form)
traceability-check.txt   short console-style check log

DETERMINISM
-----------
JSON output uses sorted keys, two-space indent, LF endings, trailing newline.
Rows follow field order, then evidence-label order.
"""

import argparse
import csv
import io
import json
import os
import sys


SCHEMA_OUT = "actproof.traceability_matrix.v0"


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build_matrix(fragments_reg, actions_reg, fields_reg, evidence_reg, decisions_reg):
    frag_ids = {f.get("fragment_id") for f in fragments_reg.get("source_fragments", [])}
    action_ids = {a.get("action_id") for a in actions_reg.get("legal_actions", [])}
    decision_ids = {d.get("decision_id") for d in decisions_reg.get("interpretation_decisions", [])}
    field_ids = {m.get("field_id") for m in fields_reg.get("mapped_fields", [])}
    evidence_ids = {e.get("evidence_id") for e in evidence_reg.get("evidence_labels", [])}

    # Which decisions affect which elements, so each row can pick up its decisions.
    decisions_for_element = {}
    for d in decisions_reg.get("interpretation_decisions", []):
        for el in d.get("affected_elements", []) or []:
            decisions_for_element.setdefault(el, []).append(d.get("decision_id"))

    # Which evidence labels support which fields.
    evidence_for_field = {}
    for e in evidence_reg.get("evidence_labels", []):
        for fld in e.get("supports_fields", []) or []:
            evidence_for_field.setdefault(fld, []).append(e.get("evidence_id"))

    rows = []
    findings = []

    # --- One row per profile field ---
    for m in fields_reg.get("mapped_fields", []):
        fid = m.get("field_id")
        las = m.get("legal_actions", []) or []
        frags = m.get("source_fragments", []) or []
        decs = m.get("interpretation_decisions", []) or []
        # Pick up any decisions that declared they affect this field.
        decs = sorted(set(decs) | set(decisions_for_element.get(fid, [])))
        ev = sorted(set(evidence_for_field.get(fid, [])))

        # Cross-checks (binding integrity).
        for la in las:
            if la not in action_ids:
                findings.append({"severity": "error", "code": "trace.field_unknown_action",
                                 "message": "Field '{}' references action '{}' not in the action register.".format(fid, la)})
        for fr in frags:
            if fr not in frag_ids:
                findings.append({"severity": "error", "code": "trace.field_unknown_fragment",
                                 "message": "Field '{}' references fragment '{}' not in the fragment register.".format(fid, fr)})
        for dc in decs:
            if dc not in decision_ids:
                findings.append({"severity": "error", "code": "trace.field_unknown_decision",
                                 "message": "Field '{}' references decision '{}' not in the decision register.".format(fid, dc)})

        # Honesty cross-check: any non-direct field row should carry an
        # interpretation decision (or an AI-proposed link awaiting affirmation).
        # Kept at WARNING level on purpose: a missing decision is a pending human
        # judgement, surfaced - not a hard failure that would force the call by
        # breaking the build. Escalating to error would bake the decision in
        # through the back door.
        non_direct = ("interpretive_mapping", "operational_support_field", "derived_from_legal_action")
        if m.get("mapping_status") in non_direct and not decs:
            findings.append({"severity": "warning", "code": "trace.non_direct_no_decision",
                             "message": "Field '{}' is non-direct ({}) but no interpretation decision is linked (pending human affirmation).".format(fid, m.get("mapping_status"))})

        rows.append({
            "trace_id": "trace.field.{}".format(fid),
            "row_type": "profile_field",
            "profile_field": fid,
            "evidence_label": None,
            "evidence_labels": ev,
            "disclosure": m.get("disclosure"),
            "mapping_status": m.get("mapping_status"),
            "review_status": m.get("review_note") and "draft" or "draft",
            "source_fragments": frags,
            "legal_actions": las,
            "interpretation_decisions": decs,
            "mapping_note": m.get("derivation_reason"),
            "review_note": m.get("review_note"),
        })

    # --- One row per evidence label ---
    for e in evidence_reg.get("evidence_labels", []):
        eid = e.get("evidence_id")
        las = e.get("legal_actions", []) or []
        frags = e.get("source_fragments", []) or []
        decs = sorted(set(decisions_for_element.get(eid, [])))
        supports = e.get("supports_fields", []) or []

        for fld in supports:
            if fld not in field_ids:
                findings.append({"severity": "error", "code": "trace.evidence_unknown_field",
                                 "message": "Evidence '{}' supports field '{}' not in the matrix.".format(eid, fld)})

        # Keep mapping_status drawn from the SAME frozen vocabulary as field
        # rows (no invented 'evidence_*' statuses). The evidence-specific meaning
        # lives in a separate evidence_basis field.
        basis = e.get("basis") or "supporting"
        evidence_status_map = {
            "direct": "direct_source_mapping",
            "supporting": "operational_support_field",
            "interpretation": "interpretive_mapping",
        }
        rows.append({
            "trace_id": "trace.evidence.{}".format(eid),
            "row_type": "evidence_label",
            "profile_field": None,
            "evidence_label": eid,
            "evidence_labels": [eid],
            "supports_fields": supports,
            "disclosure": e.get("disclosure"),
            "mapping_status": evidence_status_map.get(basis, "operational_support_field"),
            "evidence_basis": basis,
            "review_status": "draft",
            "source_fragments": frags,
            "legal_actions": las,
            "interpretation_decisions": decs,
            "mapping_note": e.get("derivation_reason"),
            "review_note": e.get("review_note"),
        })

    # Coverage: every field must appear as a row (it does, by construction),
    # and we record which decisions were never linked to any row.
    linked_decisions = set()
    for r in rows:
        linked_decisions.update(r.get("interpretation_decisions", []))
    orphan_decisions = sorted(decision_ids - linked_decisions)
    for dc in orphan_decisions:
        findings.append({"severity": "warning", "code": "trace.decision_unlinked",
                         "message": "Decision '{}' is not linked to any field or evidence row.".format(dc)})

    field_rows = [r for r in rows if r["row_type"] == "profile_field"]
    evidence_rows = [r for r in rows if r["row_type"] == "evidence_label"]
    by_status = {}
    for r in field_rows:
        by_status[r["mapping_status"]] = by_status.get(r["mapping_status"], 0) + 1

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    status = "fail" if errors else ("pass_with_warnings" if warnings else "pass")

    return {
        "schema": SCHEMA_OUT,
        "profile_id": fields_reg.get("profile_id"),
        "title": "{} traceability matrix".format(fields_reg.get("profile_id")),
        "status": status,
        "summary": {
            "trace_rows_total": len(rows),
            "profile_field_rows": len(field_rows),
            "evidence_label_rows": len(evidence_rows),
            "source_fragments_referenced": len({f for r in rows for f in r["source_fragments"]}),
            "legal_actions_referenced": len({a for r in rows for a in r["legal_actions"]}),
            "interpretation_decisions_referenced": len(linked_decisions),
            "by_field_mapping_status": by_status,
            "errors": errors,
            "warnings": warnings,
        },
        "inputs": {
            "source_fragments_status": fragments_reg.get("status"),
            "legal_actions_status": actions_reg.get("status"),
            "mapped_fields_status": fields_reg.get("status"),
            "evidence_labels_status": evidence_reg.get("status"),
            "interpretation_decisions_status": decisions_reg.get("status"),
        },
        "traceability": rows,
        "findings": findings,
        "non_claims": [
            "The matrix binds human-authored layers; it adds no new mapping or judgement.",
            "A traceable field is one whose chain is recorded, not one proven legally correct.",
            "This matrix does not assert legal completeness or compliance.",
            "Binding integrity here is structural: every reference resolves to a known element.",
        ],
    }


def render_markdown(reg):
    lines = []
    lines.append("# Traceability matrix")
    lines.append("")
    lines.append("**Profile:** `{}`".format(reg.get("profile_id")))
    lines.append("**Status:** `{}`".format(reg.get("status")))
    lines.append("")
    s = reg["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append("- Total rows: **{}** ({} field rows, {} evidence rows)".format(
        s["trace_rows_total"], s["profile_field_rows"], s["evidence_label_rows"]))
    lines.append("- Source fragments referenced: **{}**".format(s["source_fragments_referenced"]))
    lines.append("- Legal actions referenced: **{}**".format(s["legal_actions_referenced"]))
    lines.append("- Interpretation decisions referenced: **{}**".format(s["interpretation_decisions_referenced"]))
    lines.append("- Errors: **{}**, Warnings: **{}**".format(s["errors"], s["warnings"]))
    lines.append("")
    lines.append("## Matrix")
    lines.append("")
    lines.append("| Element | Type | Disclosure | Mapping status | Source fragments | Actions | Decisions |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in reg["traceability"]:
        element = r.get("profile_field") or r.get("evidence_label")
        lines.append("| `{}` | {} | {} | `{}` | {} | {} | {} |".format(
            element,
            r.get("row_type"),
            r.get("disclosure") or "",
            r.get("mapping_status"),
            ", ".join("`{}`".format(f) for f in r.get("source_fragments", [])) or "-",
            ", ".join("`{}`".format(a) for a in r.get("legal_actions", [])) or "-",
            ", ".join("`{}`".format(d) for d in r.get("interpretation_decisions", [])) or "-",
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


def render_csv(reg):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["element", "row_type", "disclosure", "mapping_status",
                "source_fragments", "legal_actions", "interpretation_decisions",
                "mapping_note"])
    for r in reg["traceability"]:
        element = r.get("profile_field") or r.get("evidence_label")
        w.writerow([
            element, r.get("row_type"), r.get("disclosure") or "",
            r.get("mapping_status"),
            "; ".join(r.get("source_fragments", [])),
            "; ".join(r.get("legal_actions", [])),
            "; ".join(r.get("interpretation_decisions", [])),
            (r.get("mapping_note") or "").replace("\n", " "),
        ])
    return buf.getvalue()


def render_check_log(reg):
    lines = []
    lines.append("ActProof Mapper - Step 7: traceability matrix")
    lines.append("=" * 45)
    lines.append("Profile: {}".format(reg.get("profile_id")))
    lines.append("Status:  {}".format(reg.get("status")))
    s = reg["summary"]
    lines.append("Rows: {} total ({} field, {} evidence), {} errors, {} warnings".format(
        s["trace_rows_total"], s["profile_field_rows"], s["evidence_label_rows"],
        s["errors"], s["warnings"]))
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
        description="ActProof Mapper Step 7: assemble the traceability matrix from the five registers.")
    ap.add_argument("--fragments", required=True, help="source-fragments.json (Step 2)")
    ap.add_argument("--actions", required=True, help="legal-actions.json (Step 3)")
    ap.add_argument("--fields", required=True, help="mapped-fields.json (Step 4)")
    ap.add_argument("--evidence", required=True, help="evidence-labels.json (Step 5)")
    ap.add_argument("--decisions", required=True, help="interpretation-decisions.json (Step 6)")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    fragments_reg = load(args.fragments)
    actions_reg = load(args.actions)
    fields_reg = load(args.fields)
    evidence_reg = load(args.evidence)
    decisions_reg = load(args.decisions)

    os.makedirs(args.out, exist_ok=True)
    reg = build_matrix(fragments_reg, actions_reg, fields_reg, evidence_reg, decisions_reg)

    dump_json(reg, os.path.join(args.out, "traceability.json"))
    dump_text(render_markdown(reg), os.path.join(args.out, "traceability.md"))
    dump_text(render_csv(reg), os.path.join(args.out, "traceability.csv"))
    dump_text(render_check_log(reg), os.path.join(args.out, "traceability-check.txt"))

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
