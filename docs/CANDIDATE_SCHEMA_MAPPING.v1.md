# Candidate schema mapping

`actproof-events 1.9.0` introduces candidate external-schema mapping.

The feature compares an external bank, vendor, GRC, or sample-report field list
against an ActProof profile and returns **mapping candidates for human review**.
It never declares that an external field is definitively equivalent to an
ActProof field.

## Command

```bash
actproof-events compare-schema \
  op:eu.dora.ict_incident_notification_initial.v1 \
  external-schema.json \
  --out mapping-report.json
```

## Boundaries

- `mapping_status` is always `candidate_review_required`.
- `review_required` is always `true`.
- `candidate_strength` is `weak`, `medium`, or `strong`; it is not a legal confidence score.
- Do not map by field name alone.
- ActProof field IDs are stable inside the ActProof profile, not universal market field names.
- The output is for bank/vendor/product-owner review, not regulatory filing reliance.

## What the report shows

- candidate mappings from external fields to ActProof profile fields
- unmapped external fields
- required ActProof fields without any candidate
- ambiguous external fields whose top candidates are close
- why each candidate was proposed (`matched_by` and `match_details`)

## Supported input shapes

- JSON Schema with `properties`
- object with `fields` or `columns`
- array of field names or field objects
- sample report object with top-level keys

Default CLI filtering includes medium and strong candidates. Use `--minimum-strength weak` only for broad exploratory review.
