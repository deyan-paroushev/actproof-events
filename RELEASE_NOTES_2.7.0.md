# actproof-events 2.7.0 — COSE signing prototype for source-atom statements

This release adds local COSE_Sign1 prototype signing and verification for the `actproof/source-atom/v1` statements introduced in 2.6.0.

## Added

- `actproof_events/cose_signing.py`
- `generate-cose-dev-keypair`
- `sign-cose-source-atom-statement`
- `verify-cose-source-atom-statement`
- `docs/COSE_SOURCE_ATOM_SIGNING_PROTOTYPE.v1.md`
- `docs/COSE_SIGNING_BOUNDARIES.v1.md`
- example COSE verification output
- tests for local signature generation, verification and tamper detection

## Boundary

2.7.0 signs statement hashes locally. It does not register statements with SCITT, produce receipts, verify transparency-service inclusion, or claim legal/compliance correctness.

The release is a signing prototype and bridge toward a future SCITT registration / receipt verification pilot.
