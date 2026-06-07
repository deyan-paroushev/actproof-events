# actproof-events 1.8.2 — bank-operable trust pack

This is a bank-operability release. It does not add a workflow platform, hosted filing service, evidence store, or external schema auto-mapper.

## Added

- `actproof_events.bank_operability` module.
- `build_profile_lock(act_id)` for pinning profile version, hashes, source atom coverage and completeness state.
- `build_prevalidation_run_report(act_id, report)` for audit-friendly local pre-validation records.
- `build_bank_review_checklist(act_id)` for bank-side SME/legal/risk review.
- CLI commands:
  - `actproof-events export-profile-lock ACT_ID --out profile-lock.json`
  - `actproof-events export-prevalidation-report ACT_ID report.json --out prevalidation-report.json`
  - `actproof-events export-review-checklist ACT_ID --out review-checklist.json`
- `docs/BANK_IMPLEMENTATION_GUIDE.v1.md`.

## Boundary

The exported objects are implementation aids. They do not certify compliance, verify facts, submit reports, or replace bank-side legal/regulatory interpretation.

## Still planned

- Candidate external schema mapping (`compare-schema`) for 1.9.0.
- Profile diff/change-control command.
- Reviewed profile lifecycle and challenge-record workflow.
