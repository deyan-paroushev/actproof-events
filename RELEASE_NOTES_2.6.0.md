# actproof-events 2.6.0 — SCITT / COSE source-atom statement profile

This release defines a standards-aligned statement profile for ActProof source atoms.

## Added

- `actproof_events/scitt_profile.py`
- `actproof-events export-scitt-source-atom-statement`
- `actproof-events export-scitt-source-atom-manifest`
- `actproof-events validate-scitt-source-atom-statement`
- `actproof-events validate-scitt-source-atom-manifest`
- `docs/SCITT_SOURCE_ATOM_PROFILE.v1.md`
- `docs/COSE_SOURCE_ATOM_STATEMENT.v1.md`
- `spec/schemas/scitt_source_atom_statement.v1.schema.json`
- examples and tests

## Boundary

2.6.0 does not create COSE signatures, SCITT registrations or SCITT receipts. It exports and validates the source-atom statement payloads that can support those later layers.
