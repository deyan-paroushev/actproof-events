# Evidence-layer complexity scores

This directory holds the reproducible output of the evidence-layer complexity
scorer applied to the source-bound act profiles in `catalogue/`.

## What this is

`evidence_layer_scores.json` is generated, not hand-authored. It is the output
of `scripts/evidence_layer_score.py` scoring two profiles on the four field-level
dimensions of the evidence-layer complexity framework:

- interpretive load (0-4)
- evidence burden (0-2)
- disclosure complexity (0-2)
- reconstruction burden (0-2)

## Two classes of score, kept distinct

- DERIVED (mechanical). The disclosure-complexity score is read directly from
  each profile's `disclosure_profile`: public -> 0, commitment -> 1,
  private -> 2. An untiered field is reported and excluded from the disclosure
  ratio rather than silently coerced. This column is fully reproducible from the
  source-bound artefact.
- RUBRIC (documented judgement). Interpretive load, evidence burden and
  reconstruction burden are assigned from the framework rubric, with an inline
  rationale per field in the scorer. These are transparent and auditable, but
  they are judgement, not measurement.

## Reproduce

From the repository root:

    python scripts/evidence_layer_score.py \
        --dora catalogue/acts/eu/dora/ict_incident_notification_initial.v1.json \
        --nis2 catalogue/acts/eu/nis2/significant_incident_early_warning.v1.json \
        --compare --check \
        --json analysis/evidence_layer_scores.json

`--check` asserts that the DORA non-disclosure aggregates match the published
paper (Section 6.4). It passes. `--check` also prints a disclosure
reconciliation: the paper's Table 1 hand-typed five disclosure cells that
disagree with the live DORA profile's own tiers. The profile is ground truth;
the paper's Table 1 disclosure column and 6.4 private/restricted figure are to
be updated to the derived values (7 of 14 tiered fields private-or-restricted,
1 untiered).

## Headline comparison

DORA initial notification vs NIS2 early warning, from the current profiles:

| metric                         | DORA  | NIS2 |
|--------------------------------|-------|------|
| required fields                | 15    | 11   |
| source instruments (pinned)    | 4     | 2    |
| average interpretive load      | 1.53  | 1.45 |
| high load (>= 3)               | 4/15  | 3/11 |
| evidence-bearing               | 8/15  | 4/11 |
| private/restricted (of tiered) | 7/14  | 5/11 |

Near-identical interpretive intensity carried through opposite structures: DORA
disperses judgement across more fields and four hash-pinned instruments with an
EU template; NIS2 concentrates the same proportional judgement into two
maximum-load early-warning flags on a thinner EU base with no EU-level template,
displacing implementation weight into national CSIRT portals.
