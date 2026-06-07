# actproof-events 2.1.0 — Bank profile overlay model

This release adds bank-owned profile overlays for internal field mappings and review decisions.

## Added

- `actproof_events.bank_overlay`
- `init_bank_overlay()`
- `init_bank_overlay_from_schema()`
- `validate_bank_overlay()`
- `build_bank_overlay_status()`
- `build_bank_overlay_report()`
- `load_bank_overlay()` / `write_bank_overlay()`

## New CLI commands

- `actproof-events init-overlay`
- `actproof-events init-overlay-from-schema`
- `actproof-events validate-overlay`
- `actproof-events overlay-status`
- `actproof-events export-overlay-report`

## Boundary

Overlay mappings are local bank control records. They are not legal equivalence, compliance certification, supervisory approval or public ActProof profile modifications.
