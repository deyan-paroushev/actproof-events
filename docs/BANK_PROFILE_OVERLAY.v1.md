# Bank profile overlay v1

`actproof-events 2.1.0` introduces bank-owned profile overlays for internal field mappings and review decisions.

An overlay is a local control object. It records how an institution maps its own field names to a pinned ActProof profile. It does not modify the public ActProof profile, and it does not certify compliance.

## Intended use

Use overlays when a bank wants to:

- map internal incident-reporting fields to ActProof field IDs;
- record accepted, rejected, deferred or split mapping decisions;
- track missing ActProof required fields in its internal schema;
- retain internal-only fields without treating them as profile errors;
- export an audit-friendly overlay report for internal review.

## Boundary

An overlay is not:

- legal advice;
- compliance certification;
- supervisory approval;
- factual verification;
- regulatory submission;
- a universal field naming standard.

ActProof field IDs remain profile-local reference anchors. The source binding is the authority, not the field name.

## Typical workflow

```bash
actproof-events compare-schema \
  op:eu.dora.ict_incident_notification_initial.v1 \
  examples/external-schema.example.json \
  --out candidate-mapping-report.json

actproof-events init-overlay \
  op:eu.dora.ict_incident_notification_initial.v1 \
  --mapping-report candidate-mapping-report.json \
  --institution "Example Bank" \
  --out bank-overlay.json

actproof-events validate-overlay bank-overlay.json
actproof-events overlay-status bank-overlay.json
actproof-events export-overlay-report bank-overlay.json --out bank-overlay-report.json
```

## Review model

Mappings begin as `candidate_review_required` and `review_decision: needs_review`. Nothing is accepted automatically.

A bank may later edit the overlay to record:

- `review_decision: accepted`
- `mapping_status: approved_for_internal_review_use`
- `reviewed_by`
- `reviewed_at`
- `review_notes`

Accepted mappings require reviewer metadata. Rejected mappings require notes.
