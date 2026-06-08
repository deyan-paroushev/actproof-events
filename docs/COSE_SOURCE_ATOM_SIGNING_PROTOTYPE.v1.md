# COSE source-atom signing prototype v1

ActProof Events 2.7.0 adds a local COSE signing prototype for the `actproof/source-atom/v1` statement profile introduced in 2.6.0.

The prototype signs a source-atom statement hash into a compact COSE_Sign1-shaped CBOR object using Ed25519 / COSE EdDSA (`alg = -8`). The signature is local only. It is not a SCITT Transparency Service registration and it does not produce a SCITT or COSE receipt.

## Intended flow

```text
source atom
→ actproof/source-atom/v1 statement JSON
→ statement_hash
→ COSE_Sign1 local prototype
→ local verifier
```

## Commands

Generate a development-only keypair:

```bash
actproof-events generate-cose-dev-keypair \
  --out-dir cose-dev-keys \
  --kid actproof-dev-ed25519-001
```

Export a source-atom statement:

```bash
actproof-events export-scitt-source-atom-statement \
  op:eu.dora.ict_incident_notification_initial.v1 \
  --atom-id src.eu.dora.32022R2554.art19.reporting_obligation \
  --out source-atom.statement.json
```

Sign it locally:

```bash
actproof-events sign-cose-source-atom-statement \
  source-atom.statement.json \
  --key cose-dev-keys/source-atom.dev.private-key.pem \
  --kid actproof-dev-ed25519-001 \
  --out source-atom.cose \
  --metadata-out source-atom.cose.metadata.json
```

Verify it locally:

```bash
actproof-events verify-cose-source-atom-statement \
  source-atom.cose \
  --public-key cose-dev-keys/source-atom.dev.public-key.pem \
  --statement source-atom.statement.json \
  --out source-atom.verify-result.json
```

## Payload mode

The COSE payload is the UTF-8 `statement_hash` string, not the full statement JSON. The verifier must supply the statement JSON, recompute `statement_hash`, confirm that the COSE payload matches it, and then verify the Ed25519 signature over the COSE `Sig_structure`.

This keeps the release close to the later SCITT / hash-envelope direction while avoiding public transparency registration before the atom layer is reviewed.

## Prototype boundary

2.7.0 proves local signability and local verification only.

It does not claim:

- SCITT registration;
- COSE receipt verification;
- legal correctness;
- compliance certification;
- bank approval;
- supervisory approval;
- production key management.

A signature proves that the supplied key signed the statement hash. It does not prove that the atom is legally correct.
