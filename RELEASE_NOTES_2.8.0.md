# actproof-events 2.8.0 — local SCITT-style registration / receipt pilot

A local model of the SCITT registration flow on top of the 2.7.0 local
COSE_Sign1 signing prototype: a signed source-atom statement is appended to a
local append-only log, an RFC 6962-style Merkle inclusion proof is computed, and
a standalone-verifiable local receipt is issued and verified.

## Added

- `actproof_events/scitt_registration.py`
- CLI: `init-scitt-local-log`, `register-scitt-local-source-atom-statement`,
  `verify-scitt-local-receipt`
- `tests/test_scitt_registration.py` (14 tests)
- `docs/SCITT_REGISTRATION_RECEIPT_PILOT.v1.md`
- `docs/SCITT_RECEIPT_BOUNDARIES.v1.md`
- `docs/RECEIPT_VOCABULARY_ALIGNMENT.v1.md`
- `examples/scitt/source-atom.local-receipt.example.json`
- `examples/scitt/source-atom.local-receipt-verification.example.json`
- `examples/scitt/source-atom.local-log.example.json`

## Changed

- `actproof_events/scitt_profile.py`: source-atom statements now carry a
  `scitt_binding` block (issuer model, intended SCITT media types, payload
  profile, registration policy), with matching validation.

## Removed

- the 2.6.0 receipt / COSE placeholder text files under `examples/scitt/`.

## Design decisions (verified against the live IETF datatracker)

- **Self-contained receipts.** A SCITT Receipt "is universally verifiable
  without online access to the TS"; verification needs only the receipt, COSE
  bytes, statement and public key. The log is an optional auditor cross-check.
- **Registration time recorded, not hashed.** `registration_time` is carried in
  the receipt/log entry per SCITT's definition, but excluded from the Merkle
  leaf so leaf and root stay reproducible.
- **ActProof as SCITT Issuer.** The `scitt_binding` block names the issuer model
  and the intended media types. Registration is pending RFC publication; the
  package references the types but does not emit `application/scitt-receipt+cose`.
- **Mechanism-vocabulary alignment (ACTA/ASQAV-aware, not -derived).** Aligned
  field names where mechanics coincide (`canonicalization: "JCS/RFC8785"`,
  `policy_digest`, `previous_receipt_hash`, `statement_ref`); ActProof-native
  commitment names kept; no conformance claimed.

## Boundary

Local registration and receipts only. No external transparency-service
registration, no `application/scitt-receipt+cose` CBOR, no CCF/MMR/ACTA/ASQAV
conformance claim. The SCITT architecture is an Active Internet-Draft in the RFC
Editor queue, not yet a published RFC; the SCITT media types are defined in the
draft with registration pending. See `docs/SCITT_RECEIPT_BOUNDARIES.v1.md`.
