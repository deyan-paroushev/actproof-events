# ActProof Events bank implementation guide v1

ActProof Events is designed to run inside a bank or regulated institution as a local, source-bound pre-validation/reference component. It is not a filing channel, legal opinion, compliance certification, or factual verification engine.

## Minimal bank-safe deployment pattern

1. Pin the package version, for example `actproof-events==1.8.2`.
2. Export a profile lockfile and store it in internal change records.
3. Map internal/GRC fields to ActProof profile fields by source atoms, template locators, required status, data type and evidence expectations, not by name alone.
4. Run pre-validation locally against draft report payloads.
5. Store the pre-validation run report, including input report hash and profile lock hash.
6. Review blocked and attention-required findings under the bank's own regulatory reporting controls.

## Commands

```bash
actproof-events export-profile-lock \
  op:eu.dora.ict_incident_notification_initial.v1 \
  --out profile-lock.json

actproof-events export-review-checklist \
  op:eu.dora.ict_incident_notification_initial.v1 \
  --out bank-review-checklist.json

actproof-events export-prevalidation-report \
  op:eu.dora.ict_incident_notification_initial.v1 \
  draft-report.json \
  --out prevalidation-report.json
```

## Boundary

ActProof Events checks profile structure, missing required fields, unknown fields, evidence-readiness signals, high interpretive load and source-binding metadata. It does not determine legal compliance, validate facts, sign data, timestamp data, anchor data, submit reports or replace bank-side legal/regulatory review.
