# actproof-events 1.9.0

Candidate schema mapping release.

## Added

- `actproof_events.schema_mapping.compare_schema(...)`
- `actproof_events.schema_mapping.compare_schema_file(...)`
- CLI command: `actproof-events compare-schema`
- candidate mapping report schema id: `actproof.external_schema_mapping.v1`
- documentation: `docs/CANDIDATE_SCHEMA_MAPPING.v1.md`

## Boundary

This release deliberately emits candidates only:

- `mapping_status: candidate_review_required`
- `review_required: true`
- `candidate_strength: weak | medium | strong`

It does not output legal equivalence, compliance certification, or final field mappings.
