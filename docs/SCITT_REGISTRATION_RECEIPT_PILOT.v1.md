# SCITT-style local registration and receipt pilot (v1)

actproof-events 2.8.0

## What this is

2.8.0 adds a local model of the SCITT registration flow on top of the 2.7.0
local COSE_Sign1 signing prototype:

```
canonical source atom
  -> actproof/source-atom/v1 statement        (2.6.0)
  -> COSE_Sign1 signed statement              (2.7.0)
  -> append to a local append-only log        (2.8.0)
  -> Merkle inclusion proof + local receipt   (2.8.0)
  -> standalone receipt verification          (2.8.0)
```

The log is a single JSON document with an ordered `entries` array and a running
`log_root`. Leaves are domain-separated SHA-256 hashes binding the COSE bytes to
the statement hash. The Merkle tree is RFC 6962-style (duplicate-last interior
nodes, leaf/node domain separation), so an inclusion proof is a short audit path
of sibling hashes from a leaf to the committed root.

## Commands

```bash
# one-off: dev key + signed statement (2.6.0 / 2.7.0)
actproof-events generate-cose-dev-keypair --out-dir keys
actproof-events export-scitt-source-atom-statement ACT_ID --atom-id ATOM_ID --out statement.json
actproof-events sign-cose-source-atom-statement statement.json \
    --key keys/source-atom.dev.private-key.pem --out statement.cose

# 1. create a local log
actproof-events init-scitt-local-log --out local-log.json --label my-pilot

# 2. register and get a receipt
actproof-events register-scitt-local-source-atom-statement statement.json \
    --cose statement.cose --log local-log.json --out receipt.json

# 3. verify the receipt (standalone; the log is NOT required)
actproof-events verify-scitt-local-receipt receipt.json \
    --cose statement.cose --statement statement.json \
    --public-key keys/source-atom.dev.public-key.pem

# optional: auditor cross-check against the live log
actproof-events verify-scitt-local-receipt receipt.json \
    --cose statement.cose --statement statement.json \
    --public-key keys/source-atom.dev.public-key.pem --log local-log.json
```

## Self-contained receipts

The SCITT architecture states a Receipt "is universally verifiable without
online access to the TS", and that a relying party "MAY decide to verify only a
single Receipt". So `verify-scitt-local-receipt` needs only the receipt, the
COSE bytes, the statement and the public key. The `--log` flag is an optional
auditor cross-check (the separate SCITT auditor/replay role), never required for
normal verification.

## Registration time

The SCITT architecture records "Registration time ... as the timestamp when the
Transparency Service added the Signed Statement to its Verifiable Data
Structure." The receipt and log entry carry a `registration_time` with that
semantics. It is deliberately excluded from the hashed Merkle leaf, so the leaf
and root stay byte-reproducible; the spec requires the time be recorded, not
that it be part of the leaf. Note: COSE label 394 is the `receipts` array, not a
timestamp; this pilot does not claim label-394 semantics.

## What the receipt carries

Alongside the inclusion proof: `statement_hash`/`cose_sha256` (what was
registered); the `log` block (`log_index`, `leaf_hash`, `inclusion_path`,
`log_root`); `profile_commitments` and `source_atom_commitments` (the Profile
View Export bridge); `registration_time`; and the mechanism-aligned fields
`statement_ref`, `policy_digest`, `previous_receipt_hash`, `canonicalization`.

## What verification proves

`verify-scitt-local-receipt` passes only if all hold: the receipt is well-formed
and its `receipt_hash` matches; the statement is consistent and its hash matches
the receipt; the COSE_Sign1 signature is valid; the receipt's `cose_sha256`
matches the COSE bytes; the Merkle inclusion path recomputes to the committed
`log_root`; the profile-view and source-atom commitments equal the statement's;
and the `policy_digest` recomputes from the statement.

See `SCITT_RECEIPT_BOUNDARIES.v1.md` and `RECEIPT_VOCABULARY_ALIGNMENT.v1.md`.
