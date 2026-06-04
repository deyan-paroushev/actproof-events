#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
evidence_layer_score.py

Reproducible evidence-layer complexity scorer for ActProof Events act profiles.

Scores a source-bound act profile on the four field-level dimensions defined in
"Measuring Regulatory Complexity at the Evidence Layer" (Section 6.2) and emits
the per-field table and the aggregate metrics. Built to score the DORA initial
notification and the NIS2 significant-incident early warning with one code path,
so any difference between the two is a property of the profiles, not of the
method.

Two classes of score, kept deliberately distinct
------------------------------------------------
1. DERIVED (mechanical, zero judgement). The disclosure-complexity score is
   read straight from the profile's disclosure_profile:
       public_field      -> 0
       commitment_field  -> 1
       private_field     -> 2
   An untiered field is reported as None and excluded from the disclosure
   numerator and denominator, surfaced explicitly rather than silently coerced.
   This column is fully reproducible from the source-bound artefact: re-running
   the script on the same profile yields the same disclosure scores, always.

2. RUBRIC (documented judgement). Interpretive load (0-4), evidence burden
   (0-2) and reconstruction burden (0-2) are assigned from the Section 6.2
   rubric. Each assignment carries an inline rationale string. These are
   transparent and auditable, but they are judgement, not measurement, and the
   script labels them as such. A reviewer who disagrees with a rationale can
   change one line and re-run; the aggregates recompute.

The split is itself a finding the paper promises in Section 6.7: it shows which
numbers are mechanical and which are reasoned.

Correctness check
-----------------
Run with --check to assert that the DORA aggregates match the values the paper
reports, EXCEPT for the disclosure figures, which this script corrects against
the live profile (the paper's Table 1 hand-typed 5 disclosure cells that
disagree with the profile's own tiers; the profile is ground truth). The check
prints the disclosure reconciliation so the paper can be updated to match.

Usage
-----
    python evidence_layer_score.py --profile <path> [--profile <path> ...]
    python evidence_layer_score.py --dora <path> --nis2 <path> --compare
    python evidence_layer_score.py --dora <path> --check
    python evidence_layer_score.py ... --json out.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# RUBRIC SCORES. Judgement, documented per field. Keyed by field name.
# Each entry: (interpretive_load, evidence_burden, reconstruction_burden, rationale)
# Interpretive load 0-4: 0 direct, 1 normalised/renamed, 2 transformed,
#   3 reconciled, 4 modelled/judgement-heavy.
# Evidence burden 0-2; reconstruction burden 0-2 (see Section 6.2 scales).
# ---------------------------------------------------------------------------

DORA_RUBRIC = {
    "entity_legal_identifier":
        (0, 0, 0, "Direct. Stable institutional identifier (LEI)."),
    "entity_legal_name":
        (0, 0, 0, "Direct. Stable institutional identity."),
    "financial_entity_type":
        (2, 0, 1, "Transformed. Category selection against the regulated-entity typology."),
    "submission_type":
        (0, 0, 0, "Direct. Phase or template metadata."),
    "incident_reference_code":
        (1, 1, 1, "Normalised. Internal reference; log-backed; commitment-only disclosure."),
    "detection_datetime_utc":
        (1, 1, 1, "Normalised. Timestamp normalisation; log-backed."),
    "classification_datetime_utc":
        (3, 1, 2, "Reconciled. Depends on when the institution classified the incident."),
    "classification_criteria_triggered":
        (4, 2, 2, "Modelled. High-judgement classification requiring committee evidence."),
    "affected_member_states":
        (3, 1, 2, "Reconciled. Depends on affected services, users, branches, jurisdictions."),
    "incident_discovery_method":
        (2, 1, 1, "Transformed. Operational categorisation from the detection process."),
    "business_continuity_plan_activated":
        (1, 1, 1, "Normalised, evidence-backed. Factual yes/no but evidence-backed."),
    "initial_impact_description":
        (4, 2, 2, "Modelled. Narrative, provisional, judgement-heavy."),
    "primary_contact_name":
        (0, 0, 0, "Direct. Personal/contact data."),
    "primary_contact_email":
        (0, 0, 0, "Direct. Personal/contact data."),
    "competent_authority":
        (2, 0, 1, "Transformed. Depends on jurisdiction, channel, supervisory allocation."),
}

NIS2_RUBRIC = {
    "entity_legal_identifier":
        (0, 0, 0, "Direct. Stable institutional identifier."),
    "entity_legal_name":
        (0, 0, 0, "Direct. Stable institutional identity."),
    "entity_type":
        (2, 0, 1, "Transformed. Essential/important entity category selection; gates "
                  "which Art 5-14 significance cases apply."),
    "submission_type":
        (0, 0, 0, "Direct. Phase or stage metadata (early warning)."),
    "incident_reference_code":
        (1, 1, 1, "Normalised. Internal reference; commitment-only disclosure."),
    "awareness_datetime_utc":
        (3, 1, 2, "Reconciled. 'Becoming aware' starts the 24h clock; depends on "
                  "reconciling detection, triage and significance determination."),
    "suspected_unlawful_or_malicious":
        (4, 1, 2, "Modelled. Article 23(4)(a) judgement flag under stress, pre-assessment, "
                  "with limited early information."),
    "possible_cross_border_impact":
        (4, 1, 2, "Modelled. Article 23(4)(a) judgement flag; forward-looking impact "
                  "assessment across Member States."),
    "primary_contact_name":
        (0, 0, 0, "Direct. Personal/contact data."),
    "primary_contact_email":
        (0, 0, 0, "Direct. Personal/contact data."),
    "recipient_csirt_or_competent_authority":
        (2, 0, 1, "Transformed. Depends on Member State of establishment and the national "
                  "CSIRT/CA allocation; no EU-level routing table."),
}


# ---------------------------------------------------------------------------
# DERIVED disclosure score, straight from the profile.
# ---------------------------------------------------------------------------

def disclosure_score(profile: dict, field: str):
    """Return 0/1/2 from the profile's disclosure tiers, or None if untiered."""
    disc = profile.get("disclosure_profile", {})
    if field in disc.get("private_fields", []):
        return 2
    if field in disc.get("commitment_fields", []):
        return 1
    if field in disc.get("public_fields", []):
        return 0
    return None


# ---------------------------------------------------------------------------
# Scoring.
# ---------------------------------------------------------------------------

RUBRICS = {
    "op:eu.dora.ict_incident_notification_initial.v1": DORA_RUBRIC,
    "op:eu.nis2.significant_incident_early_warning.v1": NIS2_RUBRIC,
}


def score_profile(profile: dict) -> dict:
    act_id = profile["act_type_id"]
    rubric = RUBRICS.get(act_id)
    if rubric is None:
        raise SystemExit(
            f"No rubric registered for act_type_id {act_id!r}. "
            f"Add one to RUBRICS before scoring."
        )
    required = profile["required_claim_fields"]

    rows = []
    missing_rubric = [f for f in required if f not in rubric]
    if missing_rubric:
        raise SystemExit(
            f"Rubric for {act_id} is missing required field(s): {missing_rubric}"
        )

    for f in required:
        il, eb, rb, why = rubric[f]
        dc = disclosure_score(profile, f)
        rows.append({
            "field": f,
            "interpretive_load": il,
            "evidence_burden": eb,
            "disclosure_complexity": dc,   # None if untiered
            "reconstruction_burden": rb,
            "rationale": why,
            "disclosure_untiered": dc is None,
        })

    n = len(rows)
    il_vals = [r["interpretive_load"] for r in rows]
    eb_vals = [r["evidence_burden"] for r in rows]
    rb_vals = [r["reconstruction_burden"] for r in rows]
    dc_vals = [r["disclosure_complexity"] for r in rows if r["disclosure_complexity"] is not None]
    dc_untiered = sum(1 for r in rows if r["disclosure_complexity"] is None)

    def ratio(count):
        return round(100.0 * count / n, 1) if n else 0.0

    agg = {
        "required_fields": n,
        "direct_field_count": sum(1 for v in il_vals if v == 0),
        "direct_field_ratio_pct": ratio(sum(1 for v in il_vals if v == 0)),
        "avg_interpretive_load": round(sum(il_vals) / n, 2) if n else 0.0,
        "il_ge_2_count": sum(1 for v in il_vals if v >= 2),
        "il_ge_2_ratio_pct": ratio(sum(1 for v in il_vals if v >= 2)),
        "high_load_ge_3_count": sum(1 for v in il_vals if v >= 3),
        "high_load_ge_3_ratio_pct": ratio(sum(1 for v in il_vals if v >= 3)),
        "evidence_bearing_count": sum(1 for v in eb_vals if v >= 1),
        "evidence_bearing_ratio_pct": ratio(sum(1 for v in eb_vals if v >= 1)),
        "reconstruction_heavy_count": sum(1 for v in rb_vals if v == 2),
        "reconstruction_heavy_ratio_pct": ratio(sum(1 for v in rb_vals if v == 2)),
        # disclosure: tiered fields only in numerator AND denominator
        "disclosure_tiered_fields": len(dc_vals),
        "disclosure_untiered_fields": dc_untiered,
        "private_or_restricted_count": sum(1 for v in dc_vals if v >= 1),
        "private_or_restricted_ratio_pct": (
            round(100.0 * sum(1 for v in dc_vals if v >= 1) / len(dc_vals), 1)
            if dc_vals else 0.0
        ),
    }
    return {
        "act_type_id": act_id,
        "display_name": profile.get("display_name", act_id),
        "source_instruments": sorted({
            b["identifiers"]["celex"] for b in profile.get("source_bindings", [])
        }),
        "rows": rows,
        "aggregates": agg,
    }


# ---------------------------------------------------------------------------
# Rendering.
# ---------------------------------------------------------------------------

def fmt_dc(v):
    return "-" if v is None else str(v)


def print_table(result: dict) -> None:
    print(f"\n{result['display_name']}")
    print(f"  act_type_id: {result['act_type_id']}")
    print(f"  source instruments ({len(result['source_instruments'])}): "
          f"{', '.join(result['source_instruments'])}")
    print()
    hdr = f"  {'#':>2}  {'field':40} {'IL':>3} {'EB':>3} {'DC':>3} {'RB':>3}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for i, r in enumerate(result["rows"], 1):
        print(f"  {i:>2}  {r['field']:40} "
              f"{r['interpretive_load']:>3} {r['evidence_burden']:>3} "
              f"{fmt_dc(r['disclosure_complexity']):>3} {r['reconstruction_burden']:>3}")
    print("  IL=interpretive load (0-4)  EB=evidence burden (0-2)  "
          "DC=disclosure (0-2, derived)  RB=reconstruction (0-2)")
    a = result["aggregates"]
    print()
    print("  Aggregates")
    print(f"    required fields assessed         {a['required_fields']}")
    print(f"    direct fields                    {a['direct_field_count']}/{a['required_fields']}"
          f"  ({a['direct_field_ratio_pct']}%)")
    print(f"    average interpretive load        {a['avg_interpretive_load']} / 4")
    print(f"    interpretive load >= 2           {a['il_ge_2_count']}/{a['required_fields']}"
          f"  ({a['il_ge_2_ratio_pct']}%)")
    print(f"    high load (>= 3)                 {a['high_load_ge_3_count']}/{a['required_fields']}"
          f"  ({a['high_load_ge_3_ratio_pct']}%)")
    print(f"    evidence-bearing                 {a['evidence_bearing_count']}/{a['required_fields']}"
          f"  ({a['evidence_bearing_ratio_pct']}%)")
    print(f"    reconstruction-heavy (= 2)       {a['reconstruction_heavy_count']}/{a['required_fields']}"
          f"  ({a['reconstruction_heavy_ratio_pct']}%)")
    print(f"    private/restricted (derived)     {a['private_or_restricted_count']}/"
          f"{a['disclosure_tiered_fields']}"
          f"  ({a['private_or_restricted_ratio_pct']}% of tiered)")
    if a["disclosure_untiered_fields"]:
        print(f"    disclosure-untiered fields       {a['disclosure_untiered_fields']} "
              f"(excluded from disclosure ratio)")


def print_comparison(dora: dict, nis2: dict) -> None:
    da, na = dora["aggregates"], nis2["aggregates"]
    print("\n" + "=" * 64)
    print("COMPARISON: DORA initial notification vs NIS2 early warning")
    print("=" * 64)
    rows = [
        ("required fields", da["required_fields"], na["required_fields"]),
        ("source instruments (hash-pinned)",
         len(dora["source_instruments"]), len(nis2["source_instruments"])),
        ("direct fields", f"{da['direct_field_count']}/{da['required_fields']}",
         f"{na['direct_field_count']}/{na['required_fields']}"),
        ("avg interpretive load", da["avg_interpretive_load"], na["avg_interpretive_load"]),
        ("interpretive load >= 2", f"{da['il_ge_2_count']}/{da['required_fields']}",
         f"{na['il_ge_2_count']}/{na['required_fields']}"),
        ("high load >= 3", f"{da['high_load_ge_3_count']}/{da['required_fields']}",
         f"{na['high_load_ge_3_count']}/{na['required_fields']}"),
        ("evidence-bearing", f"{da['evidence_bearing_count']}/{da['required_fields']}",
         f"{na['evidence_bearing_count']}/{na['required_fields']}"),
        ("reconstruction-heavy", f"{da['reconstruction_heavy_count']}/{da['required_fields']}",
         f"{na['reconstruction_heavy_count']}/{na['required_fields']}"),
        ("private/restricted (of tiered)",
         f"{da['private_or_restricted_count']}/{da['disclosure_tiered_fields']}",
         f"{na['private_or_restricted_count']}/{na['disclosure_tiered_fields']}"),
    ]
    print(f"  {'metric':36} {'DORA':>14} {'NIS2':>14}")
    print("  " + "-" * 64)
    for label, dv, nv in rows:
        print(f"  {label:36} {str(dv):>14} {str(nv):>14}")
    print()
    print("  Reading: DORA concentrates a DISPERSED but fully EU-pinned surface")
    print("  (more instruments, a real template, higher average interpretive load).")
    print("  NIS2's EU surface is THINNER but its two required judgement flags are")
    print("  both modelled (IL=4), and its real implementation weight is displaced")
    print("  into national CSIRT portals the EU bundle cannot hash. Two opposite")
    print("  shapes of the same problem.")


# ---------------------------------------------------------------------------
# Correctness check against the paper's reported DORA aggregates.
# ---------------------------------------------------------------------------

def run_check(dora_result: dict) -> int:
    a = dora_result["aggregates"]
    # Paper Section 6.4 reported values (non-disclosure):
    expected = {
        "required_fields": 15,
        "direct_field_count": 5,
        "avg_interpretive_load": 1.53,
        "il_ge_2_count": 7,
        "high_load_ge_3_count": 4,
        "evidence_bearing_count": 8,
        "reconstruction_heavy_count": 4,
    }
    print("\nCORRECTNESS CHECK vs paper Section 6.4 (non-disclosure metrics)")
    ok = True
    for k, exp in expected.items():
        got = a[k]
        match = (got == exp)
        ok = ok and match
        print(f"  {k:28} expected {str(exp):>6}  got {str(got):>6}  "
              f"{'OK' if match else 'MISMATCH'}")
    print("\nDISCLOSURE RECONCILIATION (profile is ground truth; paper to be updated)")
    print(f"  Paper Table 1 hand-typed: 8/15 private-or-restricted.")
    print(f"  Live profile (derived):   {a['private_or_restricted_count']}/"
          f"{a['disclosure_tiered_fields']} of tiered, "
          f"{a['disclosure_untiered_fields']} untiered.")
    print("  Drift: incident_reference_code, classification_criteria_triggered,")
    print("  affected_member_states, initial_impact_description were paper=2 but")
    print("  profile=commitment(1); business_continuity_plan_activated paper=1 but")
    print("  profile=untiered. Update the paper's Table 1 disclosure column and the")
    print("  6.4 private/restricted figure to the derived values above.")
    print("\nRESULT:", "non-disclosure metrics REPRODUCED" if ok
          else "MISMATCH in non-disclosure metrics, investigate rubric")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------

def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Evidence-layer complexity scorer.")
    ap.add_argument("--profile", action="append", default=[],
                    help="path to an act profile JSON (repeatable)")
    ap.add_argument("--dora", help="path to the DORA profile (for --compare/--check)")
    ap.add_argument("--nis2", help="path to the NIS2 profile (for --compare)")
    ap.add_argument("--compare", action="store_true",
                    help="print the DORA vs NIS2 comparison (needs --dora and --nis2)")
    ap.add_argument("--check", action="store_true",
                    help="assert DORA aggregates match the paper (needs --dora)")
    ap.add_argument("--json", help="write full results to this JSON path")
    args = ap.parse_args(argv)

    results = []
    dora_result = nis2_result = None

    if args.dora:
        dora_result = score_profile(load(args.dora))
        results.append(dora_result)
    if args.nis2:
        nis2_result = score_profile(load(args.nis2))
        results.append(nis2_result)
    for p in args.profile:
        results.append(score_profile(load(p)))

    if not results:
        ap.error("provide at least one of --dora, --nis2, or --profile")

    for r in results:
        print_table(r)

    if args.compare:
        if not (dora_result and nis2_result):
            ap.error("--compare requires both --dora and --nis2")
        print_comparison(dora_result, nis2_result)

    rc = 0
    if args.check:
        if not dora_result:
            ap.error("--check requires --dora")
        rc = run_check(dora_result)

    if args.json:
        Path(args.json).write_text(
            json.dumps({"results": results}, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {args.json}")

    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
