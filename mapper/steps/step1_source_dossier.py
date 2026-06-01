#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
ActProof Mapper - Step 1: Source Dossier
=========================================

WHAT THIS STEP DOES (in plain words)
------------------------------------
Before we can map any law into a JSON profile, we must first answer one
question honestly:

    "Which official documents are we using, and are they the real ones?"

This step reads a list of declared official sources (the "source bindings")
and, for each one, checks the local PDF file against the SHA-256 hash that was
pinned when the profile was authored. If the bytes match, the source is
verified. If the file is missing or the bytes differ, we say so plainly.

The output is a "source dossier": a record of what we are building on and
whether each piece is authentic.

WHY THIS MATTERS FOR AN OPEN-SOURCE PRODUCT
-------------------------------------------
ActProof Events is open source. Its whole point is that a stranger can check
our work without trusting us. This step is the first link in that chain: it
lets anyone confirm, by recomputing hashes themselves, that the profile was
built from the exact official documents it claims.

WHAT THIS STEP DOES NOT DO (the boundary)
-----------------------------------------
- It does not read or interpret the legal text. (That is later steps.)
- It does not decide whether the documents are the *current* law.
- A verified hash proves byte-for-byte identity with the pinned file. It does
  NOT prove the mapping is legally correct or complete.

INPUT
-----
--bindings   path to source-bindings.json   (schema: actproof.source_bindings.v0)
--sources    directory containing the source PDF files
--out        directory to write the dossier outputs

The script runs even when the PDFs are absent. Missing files are reported as
"missing", not treated as a crash, so the dossier can be built early and the
files added later.

OUTPUT (written to --out)
-------------------------
source-dossier.json    machine-readable dossier
source-dossier.md      human-readable summary
source-check.txt       short console-style check log

DETERMINISM
-----------
JSON output uses sorted keys, two-space indentation, LF line endings and a
trailing newline, so the same inputs always produce the same bytes.
"""

import argparse
import hashlib
import json
import os
import sys


SCHEMA_IN = "actproof.source_bindings.v0"
SCHEMA_OUT = "actproof.source_dossier.v0"


def normalise_hash(value):
    """Accept 'sha256:abc...' or bare 'abc...'; return the lowercase hex part."""
    if value is None:
        return None
    v = value.strip().lower()
    if v.startswith("sha256:"):
        v = v[len("sha256:"):]
    return v


def sha256_of_file(path):
    """Compute SHA-256 over the raw bytes of a file, reading in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_source(source, sources_dir):
    """Check one declared source against its local file. Returns a dossier row."""
    source_id = source.get("source_id")
    filename = source.get("filename")
    expected = normalise_hash(source.get("sha256"))

    row = {
        "source_id": source_id,
        "title": source.get("title"),
        "celex": source.get("celex"),
        "eli": source.get("eli"),
        "url": source.get("url"),
        "retrieved_at": source.get("retrieved_at"),
        "media_type": source.get("media_type"),
        "source_type": source.get("source_type"),
        "source_role": source.get("source_role"),
        "provisions": source.get("provisions", []),
        "filename": filename,
        "expected_sha256": expected,
        "computed_sha256": None,
        "byte_size": None,
        "status": None,
    }

    if not filename:
        row["status"] = "no_filename_declared"
        return row

    path = os.path.join(sources_dir, filename)
    if not os.path.isfile(path):
        row["status"] = "missing"
        return row

    computed = sha256_of_file(path)
    row["computed_sha256"] = computed
    row["byte_size"] = os.path.getsize(path)

    if expected is None:
        row["status"] = "no_expected_hash"
    elif computed == expected:
        row["status"] = "verified"
    else:
        row["status"] = "hash_mismatch"

    return row


def build_dossier(bindings, sources_dir):
    rows = [check_source(s, sources_dir) for s in bindings.get("sources", [])]

    total = len(rows)
    verified = sum(1 for r in rows if r["status"] == "verified")
    missing = sum(1 for r in rows if r["status"] == "missing")
    mismatch = sum(1 for r in rows if r["status"] == "hash_mismatch")

    # Overall dossier status, in plain terms.
    if total == 0:
        overall = "empty"
    elif mismatch > 0:
        overall = "hash_mismatch_present"
    elif missing > 0:
        overall = "incomplete_missing_files"
    elif verified == total:
        overall = "all_verified"
    else:
        overall = "incomplete"

    return {
        "schema": SCHEMA_OUT,
        "profile_id": bindings.get("profile_id"),
        "title": bindings.get("title"),
        "status": overall,
        "source_state": {
            # Honest provenance / currentness block. Step 1 records what we know;
            # it does not claim the sources are the current law.
            "basis": "pinned_original_sources",
            "as_of_date": bindings.get("retrieved_at_default"),
            "consolidation_policy": "not_consolidated",
            "currentness_check": "not_performed",
            "known_updates": [],
        },
        "summary": {
            "sources_total": total,
            "sources_verified": verified,
            "sources_missing": missing,
            "hash_mismatches": mismatch,
        },
        "sources": rows,
        "non_claims": [
            "This dossier verifies source artefact identity and hash status only.",
            "A verified hash proves byte identity with the pinned file, not legal correctness.",
            "This dossier does not extract legal fragments or interpret legal text.",
            "This dossier does not claim the sources represent the current consolidated law.",
            "Missing files are allowed at dossier-build time but must be resolved before source-bound review.",
        ],
    }


def render_markdown(dossier):
    lines = []
    lines.append("# Source dossier")
    lines.append("")
    lines.append("**Profile:** `{}`".format(dossier.get("profile_id")))
    lines.append("**Status:** `{}`".format(dossier.get("status")))
    lines.append("")
    s = dossier["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append("- Sources total: **{}**".format(s["sources_total"]))
    lines.append("- Verified: **{}**".format(s["sources_verified"]))
    lines.append("- Missing: **{}**".format(s["sources_missing"]))
    lines.append("- Hash mismatches: **{}**".format(s["hash_mismatches"]))
    lines.append("")
    lines.append("## Sources")
    lines.append("")
    lines.append("| Source | Role | File | Status | Expected SHA-256 | Computed SHA-256 |")
    lines.append("|---|---|---|---|---|---|")
    for r in dossier["sources"]:
        lines.append("| `{}`<br>{} | {} | `{}` | `{}` | `{}` | `{}` |".format(
            r.get("source_id"),
            r.get("title") or "",
            r.get("source_role") or "",
            r.get("filename") or "",
            r.get("status"),
            r.get("expected_sha256") or "-",
            r.get("computed_sha256") or "-",
        ))
    lines.append("")
    lines.append("## Non-claims")
    lines.append("")
    for nc in dossier["non_claims"]:
        lines.append("- {}".format(nc))
    lines.append("")
    return "\n".join(lines)


def render_check_log(dossier):
    lines = []
    lines.append("ActProof Mapper - Step 1: source dossier")
    lines.append("=" * 40)
    lines.append("Profile: {}".format(dossier.get("profile_id")))
    lines.append("Status:  {}".format(dossier.get("status")))
    s = dossier["summary"]
    lines.append("Sources: {} total, {} verified, {} missing, {} mismatch".format(
        s["sources_total"], s["sources_verified"], s["sources_missing"], s["hash_mismatches"]))
    lines.append("")
    for r in dossier["sources"]:
        lines.append("[{}] {} ({})".format(r["status"], r["source_id"], r["filename"]))
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
        description="ActProof Mapper Step 1: build a source dossier and verify source PDFs by hash.")
    ap.add_argument("--bindings", required=True, help="Path to source-bindings.json")
    ap.add_argument("--sources", required=True, help="Directory containing source PDF files")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    with open(args.bindings, encoding="utf-8") as fh:
        bindings = json.load(fh)

    if bindings.get("schema") != SCHEMA_IN:
        print("WARNING: expected schema '{}', got '{}'".format(
            SCHEMA_IN, bindings.get("schema")), file=sys.stderr)

    os.makedirs(args.out, exist_ok=True)
    dossier = build_dossier(bindings, args.sources)

    dump_json(dossier, os.path.join(args.out, "source-dossier.json"))
    dump_text(render_markdown(dossier), os.path.join(args.out, "source-dossier.md"))
    dump_text(render_check_log(dossier), os.path.join(args.out, "source-check.txt"))

    # Console summary
    print(render_check_log(dossier))

    # Exit code: non-zero only on a hash mismatch (an actual integrity problem).
    # Missing files are not a failure at this stage.
    if dossier["summary"]["hash_mismatches"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
