# ActProof SCITT source-atom statement profile v1

ActProof Events 2.6.0 defines a conservative SCITT/COSE-ready statement profile for source atoms.

The profile identifier is:

```text
actproof.scitt.source_atom_statement.v1
```

The statement type is:

```text
actproof/source-atom/v1
```

## Purpose

The profile lets a source atom be represented as a standards-aligned statement payload that can later be wrapped in COSE and registered with a SCITT Transparency Service.

2.6.0 deliberately stops before production signing and before public registration. Its job is to define the payload shape, hashes, maturity fields and non-claims.

## Mapping to SCITT vocabulary

| SCITT term | ActProof mapping |
| --- | --- |
| Issuer | ActProof maintainer, reviewer or future profile issuer |
| Statement | `actproof/source-atom/v1` JSON payload |
| Artifact / subject | A source atom and the official-source locator it represents |
| Transparency Service | Future SCITT service, CCF ledger, public ledger backend or private transparency service |
| Receipt | Future verifiable proof of registration, not produced in 2.6.0 |
| Relying Party | Bank, auditor, GRC tool, agent, regulator or reviewer |

## What the statement commits

A source-atom statement commits at least:

- `atom_identity_sha256`
- `canonical_atom_json_sha256`
- `official_text_sha256` when captured
- `profile_semantic_hash`
- `dependency_root`
- current maturity and review state

## What the statement does not claim

The statement does not claim legal correctness, compliance certification, supervisory approval, bank approval or final legal interpretation.

A draft atom may be exported as a statement for inspection. Public trust-facing registration should wait until the atom is reviewed or should disclose `review_status: draft` clearly.

## 2.6.0 boundary

2.6.0 is a profile/export release. It does not create a COSE signature, submit to a SCITT Transparency Service or verify a SCITT receipt.
