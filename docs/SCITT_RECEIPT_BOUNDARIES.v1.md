# SCITT receipt boundaries (v1)

actproof-events 2.8.0

## The pilot is local

2.8.0 registration and receipts are local. The log lives in one JSON file, the
inclusion proof is a local Merkle proof, and the signature is the 2.7.0 local
COSE_Sign1 prototype. Nothing in 2.8.0 talks to an external service.

## Explicit non-claims

- Local registration adds the signed statement to a local append-only log only.
- A local receipt proves local inclusion plus a local COSE signature, nothing more.
- 2.8.0 does NOT register with an external SCITT Transparency Service.
- 2.8.0 does NOT emit `application/scitt-receipt+cose` CBOR receipts.
- 2.8.0 does NOT claim conformance to the CCF or MMR COSE Receipt profiles.
- 2.8.0 does NOT claim conformance to the ACTA or ASQAV signed-action-receipt
  drafts. Vocabulary is aligned where mechanics coincide; conformance is not claimed.
- A receipt does not prove legal correctness, compliance certification, bank
  approval, supervisory approval, or production-grade key management.
- Draft atom statements should not be treated as reviewed public trust artifacts.

## Standards status as verified for this release (against the live IETF datatracker)

Stated conservatively, on purpose.

- SCITT architecture (`draft-ietf-scitt-architecture`) is an **Active
  Internet-Draft, currently at -22**, IESG state "RFC Ed Queue", RFC Editor
  state "Blocked", intended status Proposed Standard. The draft body still
  carries the note "to be removed before publishing as an RFC." It is **in the
  RFC Editor queue but not yet a published RFC**. This release does not assert
  any RFC number for it.
- COSE Receipts (`draft-ietf-cose-merkle-tree-proofs`) is an active
  Standards-Track Internet-Draft, not a published RFC. Label 394 is the
  `receipts` header parameter (an array of COSE receipts), not a timestamp.
- The CCF profile (`draft-ietf-scitt-receipts-ccf-profile`, currently -03) and
  the Merkle Mountain Range profile are active working-group Internet-Drafts,
  not published RFCs.
- The SCITT media types `application/scitt-statement+cose` and
  `application/scitt-receipt+cose` are **defined in the SCITT architecture draft
  with IANA registration requested** (the registration templates reference
  "RFCthis"). Registration is **pending RFC publication**. This release
  references them as the intended types for a future external receipt and does
  not emit them.
- `RFC 9052` (COSE structures) and `RFC 9596` (COSE `typ` header) are published
  RFCs and underpin the 2.7.0 signing prototype.
- `RFC 8785` (JCS) is the canonicalization discipline referenced by the
  `canonicalization: "JCS/RFC8785"` label.

Because these specifications are still moving, ActProof keeps the public
registration policy at `do_not_register_publicly_until_reviewed` and treats the
local pilot as the only registration surface in the 2.8.x line.
