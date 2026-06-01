#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
ActProof Mapper - Step 2: Source Fragments
===========================================

WHAT THIS STEP DOES (in plain words)
------------------------------------
Step 1 told us which official documents we are using and whether they are
authentic. But "DORA" is a large document. We cannot map "the profile came
from DORA" - that is too vague to check.

So this step breaks the law into small, stable, named pieces called
"fragments". For example, instead of "DORA", we get:

    src.dora.32022R2554.art19.para4   ->  Article 19(4)

Each fragment has a stable ID, says which source document it belongs to, what
kind of piece it is (article, paragraph, annex, etc.), and - importantly - WHY
a human selected it. Later steps will point every profile field at one of
these fragment IDs, so we can always answer "this field came from Article
19(4), not vaguely from DORA".

THE REVIEW GATE (why this is a controlled process)
--------------------------------------------------
This is the first human review gate. Fragments are NOT extracted automatically.
A person writes a "selected-provisions" file saying which provisions matter and
gives a reason for each. This step's job is to take that human selection,
check it is consistent with the verified source dossier, and produce a clean
fragment register. No fragment can refer to a source document that is not in
the dossier.

WHAT THIS STEP DOES NOT DO (the boundary)
-----------------------------------------
- It does not read the PDF text or auto-extract provisions. A human selects them.
- It does not decide whether the selection is legally complete. That is review.
- It does not interpret what the provision means. That is later steps.

INPUT
-----
--dossier      path to source-dossier.json   (output of Step 1)
--provisions   path to selected-provisions.json   (the human review gate)
--out          output directory

OUTPUT (written to --out)
-------------------------
source-fragments.json   machine-readable fragment register
source-fragments.md     human-readable summary
fragments-check.txt     short console-style check log

DETERMINISM
-----------
JSON output uses sorted keys, two-space indent, LF endings, trailing newline.
Fragments preserve the human-declared selection order.
"""

import argparse
import json
import os
import re
import sys


SCHEMA_DOSSIER = "actproof.source_dossier.v0"
SCHEMA_PROVISIONS = "actproof.selected_provisions.v0"
SCHEMA_OUT = "actproof.source_fragments.v0"

# Recommended starter vocabulary. Unknown values are allowed but warned about,
# because fragment types are act-specific and will grow with new regulations.
KNOWN_FRAGMENT_TYPES = {
    "recital", "article", "article_paragraph", "article_range",
    "point", "annex", "template_section", "definition",
    "delegated_rule", "cross_reference",
}

# Fragment IDs are dot-separated, no spaces. Segments may contain letters,
# digits and underscores (e.g. 'annexI', 'arts1to7', 'art19.para4').
FRAGMENT_ID_RE = re.compile(r"^[A-Za-z0-9]+(\.[A-Za-z0-9_]+)+$")


def index_dossier_sources(dossier):
    """Map source_id -> status, so fragments can be checked against real sources."""
    out = {}
    for s in dossier.get("sources", []):
        out[s.get("source_id")] = s.get("status")
    return out


def build_fragments(dossier, provisions):
    source_status = index_dossier_sources(dossier)
    fragments = []
    findings = []
    seen_ids = set()

    for p in provisions.get("provisions", []):
        fid = p.get("fragment_id")
        src = p.get("source_id")
        ftype = p.get("fragment_type")

        # --- Checks (the controlled-process guardrails) ---

        # 1. Fragment must have an ID, and it must be well-formed.
        if not fid:
            findings.append({"severity": "error", "code": "fragment.no_id",
                             "message": "A selected provision has no fragment_id."})
            continue
        if not FRAGMENT_ID_RE.match(fid):
            findings.append({"severity": "warning", "code": "fragment.id_format",
                             "message": "Fragment id '{}' is not in the recommended dotted lowercase form.".format(fid)})

        # 2. Fragment IDs must be unique.
        if fid in seen_ids:
            findings.append({"severity": "error", "code": "fragment.duplicate_id",
                             "message": "Duplicate fragment_id '{}'.".format(fid)})
            continue
        seen_ids.add(fid)

        # 3. Fragment must point to a source that exists in the dossier.
        if src not in source_status:
            findings.append({"severity": "error", "code": "fragment.unknown_source",
                             "message": "Fragment '{}' refers to source '{}' that is not in the dossier.".format(fid, src)})
            # still record it, but flagged
        elif source_status[src] == "hash_mismatch":
            findings.append({"severity": "error", "code": "fragment.source_mismatch",
                             "message": "Fragment '{}' points to source '{}' whose hash does not match.".format(fid, src)})

        # 4. Every fragment must carry a human reason. No silent selection.
        if not (p.get("selection_reason") or "").strip():
            findings.append({"severity": "warning", "code": "fragment.no_reason",
                             "message": "Fragment '{}' has no selection_reason; the review gate is incomplete.".format(fid)})

        # 5. Fragment type sanity (open vocabulary -> warning only).
        if ftype and ftype not in KNOWN_FRAGMENT_TYPES:
            findings.append({"severity": "warning", "code": "fragment.unknown_type",
                             "message": "Fragment '{}' has fragment_type '{}' outside the recommended set.".format(fid, ftype)})

        fragments.append({
            "fragment_id": fid,
            "source_id": src,
            "label": p.get("label"),
            "fragment_type": ftype,
            "provision_reference": p.get("provision_reference"),
            "role": p.get("role"),
            "selection_reason": p.get("selection_reason"),
            "text_excerpt": p.get("text_excerpt", ""),
            "text_hash": p.get("text_hash"),
            "notes": p.get("notes"),
            "source_status": source_status.get(src, "unknown_source"),
        })

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    status = "fail" if errors else ("pass_with_warnings" if warnings else "pass")

    return {
        "schema": SCHEMA_OUT,
        "profile_id": provisions.get("profile_id"),
        "title": provisions.get("title"),
        "status": status,
        "review_gate": provisions.get("review_gate"),
        "summary": {
            "fragments_total": len(fragments),
            "errors": errors,
            "warnings": warnings,
            "selection_method": provisions.get("selection_method", "human_selected_provisions"),
        },
        "source_dossier_status": dossier.get("status"),
        "source_fragments": fragments,
        "findings": findings,
        "non_claims": [
            "Fragments are human-selected provisions, not an automatic extraction of the law.",
            "This register does not claim the selection of provisions is legally complete.",
            "A fragment identifies where a field comes from; it does not interpret the legal text.",
            "Fragment validity here is structural and reference-level only.",
        ],
    }


def render_markdown(reg):
    lines = []
    lines.append("# Source fragments")
    lines.append("")
    lines.append("**Profile:** `{}`".format(reg.get("profile_id")))
    lines.append("**Status:** `{}`".format(reg.get("status")))
    lines.append("")
    s = reg["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append("- Fragments: **{}**".format(s["fragments_total"]))
    lines.append("- Errors: **{}**".format(s["errors"]))
    lines.append("- Warnings: **{}**".format(s["warnings"]))
    lines.append("- Selection method: `{}`".format(s["selection_method"]))
    lines.append("")
    lines.append("## Fragments")
    lines.append("")
    lines.append("| Fragment | Source | Type | Provision | Role | Why selected |")
    lines.append("|---|---|---|---|---|---|")
    for f in reg["source_fragments"]:
        lines.append("| `{}` | `{}` | {} | {} | {} | {} |".format(
            f.get("fragment_id"),
            f.get("source_id"),
            f.get("fragment_type") or "",
            f.get("provision_reference") or "",
            f.get("role") or "",
            (f.get("selection_reason") or "").replace("|", "/"),
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
    lines.append("ActProof Mapper - Step 2: source fragments")
    lines.append("=" * 42)
    lines.append("Profile: {}".format(reg.get("profile_id")))
    lines.append("Status:  {}".format(reg.get("status")))
    s = reg["summary"]
    lines.append("Fragments: {} total, {} errors, {} warnings".format(
        s["fragments_total"], s["errors"], s["warnings"]))
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
        description="ActProof Mapper Step 2: build the source fragment register from a human provision selection.")
    ap.add_argument("--dossier", required=True, help="Path to source-dossier.json (Step 1 output)")
    ap.add_argument("--provisions", required=True, help="Path to selected-provisions.json (human review gate)")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    with open(args.dossier, encoding="utf-8") as fh:
        dossier = json.load(fh)
    with open(args.provisions, encoding="utf-8") as fh:
        provisions = json.load(fh)

    if dossier.get("schema") != SCHEMA_DOSSIER:
        print("WARNING: expected dossier schema '{}', got '{}'".format(
            SCHEMA_DOSSIER, dossier.get("schema")), file=sys.stderr)
    if provisions.get("schema") != SCHEMA_PROVISIONS:
        print("WARNING: expected provisions schema '{}', got '{}'".format(
            SCHEMA_PROVISIONS, provisions.get("schema")), file=sys.stderr)

    os.makedirs(args.out, exist_ok=True)
    reg = build_fragments(dossier, provisions)

    dump_json(reg, os.path.join(args.out, "source-fragments.json"))
    dump_text(render_markdown(reg), os.path.join(args.out, "source-fragments.md"))
    dump_text(render_check_log(reg), os.path.join(args.out, "fragments-check.txt"))

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
