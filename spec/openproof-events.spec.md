# OpenProof Events Master Specification

## Amendment to Section 9: Typed Anchor Payload (v1.2 → v1.3)

<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
-->

**Status**: settled architecture, ready for implementation
**Amendment version**: 1.3 (additive, non-breaking)
**Revision**: r2, post-reconnaissance against the SCITT, EAS, OpenTimestamps, C2PA, Snapshot, ARC-2, and W3C DID/did:web ecosystems
**Amends**: `quoruna_algorand_anchoring_master_spec_v1_2.md`, Section 9 (Compact on-chain note)
**Date**: 13 May 2026
**Audience**: implementers, indexer authors, catalogue contributors, third-party issuers
**Scope**: schema extension, namespace grammar, catalogue resolution, verifier semantics, test vectors

---

## What changed in this revision

This is r2 of the v1.3 amendment, produced after a reconnaissance pass across the production open-source projects that occupy adjacent niches. The substance of the schema, grammar, modes, and verifier semantics is unchanged. Three citation additions and one new deferred item:

1. Section 9.2 now explicitly cites ARC-2 (Algorand Foundation transaction-note convention) and confirms the OpenProof Events compact note format is ARC-2 compliant out of the box. This unlocks Algorand block-explorer and indexer parsing without further work.
2. Section 9.3 now documents the structural alignment between the `x.<reverse-dns>:` third-party namespace and the W3C did:web method, so implementers who already operate did:web identities can adopt OpenProof Events catalogue contributions on the same DNS-rooted trust chain.
3. The "Open implementation items for v1.3 to v1.4" section adds a fourth deferred item: a COSE_Sign1 SCITT receipt bridge that brings Quoruna receipts into direct interoperability with SCITT-conformant verifiers (Sigstore Rekor v2, Microsoft scitt-ccf-ledger, GoDaddy ans).

No fields, modes, or test vectors changed. r1 implementations remain conformant.

---

## Why this amendment exists

Master spec v1.2 defined the compact on-chain note as a typed envelope with two reserved type tags: `t: "a"` for decision anchors and `t: "r"` for release anchors. The note carries the Merkle root over a batch of manifests plus an envelope hash. The note is private by construction: nothing about what the anchored manifests represent is visible from chain bytes alone.

That privacy default is correct as a baseline. It is the wrong default for the cases where the issuer wants the anchor to be publicly indexable by act category, where a third-party indexer wants to enumerate all anchors of a specific regulated act type across all issuers without contacting the originating platform, where a regulator wants to scan for the presence or absence of expected attestations on a public ledger, and where a researcher wants to study regulatory compliance patterns at scale.

This amendment adds an optional disclosed mode to the compact note schema. In disclosed mode, the note carries a small act-type identifier alongside the existing hash commitments. The identifier resolves to a catalogue entry that describes the act semantics, the required manifest fields, the regulatory citation, and the canonical receipt example. The identifier namespace is federated, not centrally controlled: any project that controls a DNS domain can mint act-types under that domain without asking Quoruna or anyone else, and those act-types coexist with the canonical OpenProof Events catalogue.

The change is additive. Existing private-mode anchors validate unchanged under v1.3 verifiers. The version field `q: "1"` is preserved because the schema extension is backward-compatible.

---

## Design goals for the open-source unlocking

The amendment is structured to maximise the number of independent projects that can build on top of OpenProof Events anchors without coordination. Five design goals govern the choices below.

**Permissionless extension.** Any project that controls a DNS domain can mint its own act-types under `x.<reverse-dns>:` and have those act-types coexist with the canonical catalogue. No registration, no approval, no fee, no Quoruna involvement. The DNS root is the authority.

**Zero-coordination interoperability.** A verifier written by Project A in Rust can parse and validate anchors produced by Project B's Python issuer for Project C's regulatory domain, given only the chain bytes plus the public catalogue endpoints. No bilateral agreement is required.

**Self-describing receipts.** A receipt found in isolation, with no platform context, can be resolved to its act-type semantics by following the identifier into the catalogue. The chain bytes plus the identifier plus a single HTTPS fetch is enough.

**Chain-agnostic format.** The note grammar is bytes-in, bytes-out. The JSON envelope works on Algorand transaction notes, Bitcoin OP_RETURN (with compression), Ethereum calldata, any blob substrate. The act-type semantics are independent of the witness chain.

**Implementer-friendly.** No proprietary dependencies. Off-the-shelf RFC 8785 JCS plus JSON Schema 2020-12 is enough to validate. The grammar fits in two pages. Any language with a UTF-8 string library can parse it.

---

## 9.2 Amended note schema

The compact on-chain note schema in v1.3 is:

```json
{
  "q": "1",
  "t": "a",
  "r": "base64url_merkle_root",
  "e": "base64url_envelope_hash",
  "m": 37,
  "s": "op:eu.nis2.art20.approval"
}
```

The five v1.2 fields (`q`, `t`, `r`, `e`, `m`) retain their existing semantics from master spec section 9.

The new field `s` (act-type identifier) is **OPTIONAL**. Its presence or absence selects between the two operating modes defined in section 9.4. When present, `s` MUST conform to the grammar in section 9.3.

The note prefix `quoruna/v1:` is unchanged. The full encoded note MUST remain under 1000 bytes after JCS canonicalisation. The `s` field MUST be a JSON string with byte length at most 128 octets after UTF-8 encoding.

### 9.2.1 ARC-2 compliance

The compact note format defined here is fully compliant with ARC-2, the Algorand Foundation's transaction-note-field convention. ARC-2 specifies the format `<dapp-name>:<format><data>` where `<dapp-name>` is between 5 and 32 characters, and `<format>` is one of `m` (MsgPack), `b` (byte string), `u` (UTF-8 string), or `j` (JSON). The OpenProof Events compact note satisfies this shape with `<dapp-name>` = `quoruna/v1`, `<format>` = `j`, and `<data>` = the JCS-canonicalised JSON payload. Standard Algorand block explorers and ARC-2-aware indexers will therefore identify and filter OpenProof Events anchors without any custom parsing, both in private mode (no `s` field) and in disclosed mode (with `s`).

The Algorand Foundation maintains an open Request-for-Comments process at the `algorandfoundation/ARCs` GitHub repository. The OpenProof Events compact note schema will be submitted as a new ARC alongside the IETF SCITT engagement, establishing formal Algorand-ecosystem recognition in parallel with the IETF temporal-anchoring conversation. This is a parallel standardisation track: the IETF route addresses the broader transparency-service ecosystem, the ARC route addresses Algorand-specific block-explorer and indexer interoperability.

---

## 9.3 Act-type identifier grammar

The `s` field uses one of two reserved namespace prefixes.

### Canonical namespace: `op:`

Reserved for the OpenProof Events catalogue maintained at `openproof-events/catalogue/acts/`. Identifiers under this namespace resolve to canonical catalogue entries reviewed by the OpenProof Events maintainers and the SCITT-aligned working group when one exists.

```
canonical_id = "op:" segment ("." segment)*
```

Examples:
- `op:eu.nis2.art20.approval`
- `op:eu.ai_act.art26.risk_assessment`
- `op:corporate.board.resolution.v1`
- `op:eu.csrd.director.attestation`

### Third-party namespace: `x.<reverse-dns>:`

Reserved for projects that control a DNS domain. The DNS label after `x.` is the authoritative domain in reverse-DNS form. Anyone who can prove control of the DNS root can publish a catalogue entry under that namespace. No coordination with Quoruna or OpenProof Events maintainers is required.

```
third_party_id = "x." dns_label ("." dns_label)* ":" segment ("." segment)*
```

Examples:
- `x.example.com:internal.budget.approval`
- `x.acme.org:supplier.code_of_conduct.attestation`
- `x.bib.bg:notary.act.recordation`

The reverse-DNS form (`x.example.com` rather than `x.com.example`) is chosen for human readability. Implementers MUST NOT attempt to reverse it for canonicalisation purposes; the string is matched as-is.

### Alignment with W3C did:web

The `x.<reverse-dns>:` namespace is structurally aligned with the W3C `did:web` method, which resolves decentralised identifiers through DNS plus `.well-known` URIs. An implementer who already operates a `did:web:example.com` identity can expose the corresponding OpenProof Events catalogue entries by serving JSON files at `https://example.com/.well-known/openproof-events/acts/<segment>/<segment>.json` alongside the existing `https://example.com/.well-known/did.json`. The two systems coexist on the same domain and share the same trust root: the DNS hierarchy and the domain's HTTPS certificate.

This alignment is intentional. `did:web` is the most widely-deployed decentralised-identifier method as of 2026, used by the AT Protocol (Bluesky) and by parts of the EUDI Wallet ecosystem. Implementers familiar with `did:web` can adopt OpenProof Events catalogue contributions with no new infrastructure or trust assumptions, and a future v1.4 amendment MAY define an explicit canonical mapping from `x.<dns>:<segments>` identifiers to `did:web:<dns>` DID URLs for systems that want to consume OpenProof Events catalogue entries through the W3C DID Resolution stack.

The short `x.<dns>:<segments>` form remains the canonical wire form for the on-chain note, because the 128-byte size budget on `s` is tight and DID URLs are longer than the equivalent OpenProof Events identifiers. The DID URL is a derived rendering, not the canonical form.

### Common grammar rules

Both namespaces share the following lexical rules.

```
segment    = lowercase_alpha (lowercase_alpha | digit | "_")*
dns_label  = letter (letter | digit | "-")* letter  ; per RFC 1035 §2.3.1
lowercase_alpha = "a" .. "z"
digit      = "0" .. "9"
letter     = "a" .. "z" | "A" .. "Z"  ; case-preserving for DNS labels
```

DNS labels follow RFC 1035 case-insensitivity rules but the identifier string is matched octet-for-octet after lowercasing the DNS portion. Segments after the colon are case-sensitive and MUST be all-lowercase.

Total `s` value length MUST NOT exceed 128 bytes.

A note whose `s` field violates this grammar MUST be rejected by conformant verifiers with result code `FAIL_MALFORMED_ACT_TYPE`. This is the only new FAIL case introduced by this amendment.

---

## 9.4 Operating modes

The presence or absence of the `s` field selects between two operating modes, both of which are first-class.

### Private mode (default)

The `s` field is absent. The note carries only the hash commitments and the type tag. From chain bytes alone, an observer learns that an OpenProof Events anchor exists, the protocol version, the type (decision or release), the Merkle root, the envelope hash, and the manifest count. Nothing about the anchored act category, the regulatory domain, or the act semantics is disclosed.

Private mode is the recommended default for any anchor whose category is sensitive or whose disclosure could identify the issuer when combined with the sender address.

### Disclosed mode

The `s` field is present and well-formed per section 9.3. The note carries everything private mode carries plus the act-type identifier. An indexer can resolve the identifier into a catalogue entry and learn the act semantics, the regulatory citation, and the structural shape of the underlying manifest. The manifest content itself remains off-chain.

Disclosed mode is the recommended choice for any anchor whose category is already public information about the issuer (board resolutions of a listed company, regulator-required attestations with public deadlines, public-good civic decisions) or where the issuer affirmatively wants the anchor to be discoverable by third-party indexers.

The choice between modes is per-anchor, not per-issuer. The same issuing key can produce private-mode and disclosed-mode anchors interleaved, and the verifier handles each according to the `s` field on that specific note.

---

## 9.5 Catalogue resolution

When the `s` field is present, conformant verifiers and indexers MAY resolve it to a catalogue entry to obtain act semantics. The resolution rules differ by namespace.

### Canonical namespace resolution

For an identifier `op:<segment1>.<segment2>.<segment3>`, the catalogue entry is located at:

```
openproof-events/catalogue/acts/<segment1>/<segment2>/<segment3>.json
```

Dots in the identifier map to path separators. The canonical hosting endpoint is `https://openproof.events/catalogue/acts/<segment1>/<segment2>/<segment3>.json`, with a public Git mirror at `https://github.com/openproof-events/spec/tree/main/catalogue/acts/`. Both endpoints serve identical canonical-JSON content addressed by the file path. Content hashing of every catalogue release is published in the Trust Root Package alongside the schemas.

### Third-party namespace resolution

For an identifier `x.<dns>:<segment1>.<segment2>`, the catalogue entry is located at:

```
https://<dns>/.well-known/openproof-events/acts/<segment1>/<segment2>.json
```

The `.well-known` path is reserved per RFC 8615. Third-party domain operators publish their catalogue entries at this conventional location. A verifier that wants to resolve a third-party identifier issues a single HTTPS GET to the well-known path and parses the returned JSON against the catalogue entry schema.

Domains MAY publish a catalogue index at `https://<dns>/.well-known/openproof-events/index.json` listing all act-types they mint, but the index is not required for resolution of any specific identifier.

### Catalogue entry schema

Every catalogue entry, canonical or third-party, conforms to a single JSON Schema:

```json
{
  "schema": "openproof.act_catalogue_entry.v1",
  "act_type_id": "op:eu.nis2.art20.approval",
  "display_name": "NIS2 Article 20 management body approval",
  "regulatory_citation": {
    "instrument": "Directive (EU) 2022/2555",
    "article": "20",
    "jurisdiction": "EU",
    "in_force_from": "2024-10-17"
  },
  "required_manifest_fields": [
    "decision_id",
    "decision_type",
    "tenant_id",
    "method_parameters.method_id",
    "result_hash"
  ],
  "method_constraints": {
    "allowed_method_ids": ["management_body_approval_v1"],
    "minimum_quorum_basis_points": 5001
  },
  "receipt_profile_recommendations": [
    "regulator",
    "auditor",
    "director"
  ],
  "version": "1.0",
  "supersedes": null,
  "maintainer": "openproof-events",
  "test_vector_reference": "catalogue/acts/eu/nis2/art20/approval.test_vectors.json"
}
```

The schema is intentionally minimal. It carries enough metadata for a verifier to validate that a manifest matches the declared act-type, for a renderer to pick the right receipt profile, and for a regulator or researcher to map the act-type back to its statutory basis. It does not carry the manifest itself or any participant-level data.

The catalogue entry schema is normative and is published under Apache 2.0 alongside this amendment in `openproof-events/spec/schemas/act_catalogue_entry.v1.schema.json`.

---

## 9.6 Verifier semantics update

Master spec section 21 (verifier result codes) is extended with three new codes that apply specifically to disclosed-mode anchors. None of them replace existing v1.2 codes; the existing codes remain authoritative for the cryptographic verification path.

```
PASS_WITH_SEMANTICS
  Disclosed mode. The `s` field is well-formed per §9.3. The verifier
  resolved the identifier to a catalogue entry. The manifest conforms
  to the catalogue entry's required fields and method constraints.
  The cryptographic proof path passes per §2.

PASS_SEMANTICS_UNRESOLVED
  Disclosed mode. The `s` field is well-formed per §9.3. The verifier
  did not resolve the catalogue entry. Either: (a) the verifier is
  running in offline-strict mode and was not asked to fetch external
  resources; (b) the third-party namespace endpoint is unreachable
  at verification time; (c) the canonical catalogue does not contain
  an entry for this identifier (act-type minted by an external
  contributor under a third-party namespace and not yet seen by this
  verifier). The cryptographic proof path passes per §2. The act
  semantics are unverified at this evaluation, not invalid.

FAIL_MALFORMED_ACT_TYPE
  Disclosed mode. The `s` field violates the grammar in §9.3.
  This is the only new FAIL code introduced by v1.3. It indicates
  a misconfigured issuer or a tampered note. The anchor is rejected
  regardless of whether the cryptographic proof path otherwise passes.
```

The verifier MUST treat `PASS_SEMANTICS_UNRESOLVED` as a PASS, not a WARN. The cryptographic argument the anchor makes is intact; the verifier just does not know what category of act it represents. This distinction matters for downstream tooling: an indexer can record the anchor as "well-formed, semantics pending" and re-resolve later, rather than dropping it as suspect.

Private-mode anchors continue to produce the v1.2 result codes (`PASS_QUALIFIED_TIMESTAMP`, `PASS_TIMESTAMP_VALID_NON_QUALIFIED`, etc.) unchanged.

---

## 9.7 Privacy and threat-model considerations

Disclosed mode is a deliberate disclosure choice by the issuer. The threat model below documents what it leaks and how to mitigate.

**What disclosed mode reveals on chain.** The act-type identifier reveals that this anchor is of a specific regulated category. Combined with the sender address (always visible on chain), it reveals that the address issues attestations of that category. Combined with the timestamp and frequency, it reveals patterns of attestation activity for that issuer.

**What it does not reveal.** No participant identity. No manifest content. No decision result. No authority chain. No reliance party. No private-mode anchors from the same issuer (each anchor's mode is independent).

**Recommended mitigations for issuers who want to use disclosed mode without revealing aggregate patterns.** Rotate the anchoring address per act-type or per time window, recording the rotation in the address registry with appropriate validity windows. Use a stable anchoring address only for one act category, or only for public-good acts where aggregate disclosure is intended. Mix private-mode and disclosed-mode anchors from the same address to limit pattern inference.

**Threat model exclusions.** Disclosed mode does not protect against an adversary who combines on-chain act-type tags with off-chain knowledge of the issuer's identity. That correlation is unavoidable in any disclosure mode and is a feature, not a vulnerability: regulators specifically want to verify that an identified entity anchored an expected category of attestation.

---

## 9.8 Catalogue contribution flow

The canonical catalogue under `op:` is maintained by the OpenProof Events project at `openproof-events/spec/catalogue/acts/`. Contributions are received as Git pull requests against the public repository. The contribution flow is documented in `openproof-events/spec/CONTRIBUTING_ACTS.md` (published alongside this amendment).

A pull request that adds a new canonical act-type entry MUST include the catalogue JSON conforming to the schema in section 9.5, at least one positive test vector (a manifest that conforms to the entry plus a verifier transcript showing `PASS_WITH_SEMANTICS`), at least one negative test vector (a manifest that fails the method or field constraints, with the resulting failure code), and a regulatory citation that can be independently verified by a reviewer.

Third-party catalogue entries under `x.<dns>:` follow no contribution flow at this layer. The DNS domain operator publishes whatever they consider valid at the `.well-known` path. Verifier behaviour for unrecognised third-party namespaces is defined in section 9.6.

This federation pattern means the canonical catalogue is a quality bar, not a gatekeeper. Anyone who finds the bar too slow can mint their own namespace today and propagate it through normal DNS distribution.

---

## Test vectors

Four test vectors accompany this amendment. They are published under CC0-1.0 as part of the OpenProof Events conformance corpus at `openproof-events/spec/test-vectors/typed-anchor-payload/v1/`.

### TV-1: Private-mode anchor (canonical baseline)

```json
{
  "test_vector_id": "typed-anchor-payload.v1.tv01.private_mode",
  "description": "Existing v1.2 private-mode anchor under v1.3 verifier. The `s` field is absent. The note validates with no change in semantics.",
  "note_decoded": {
    "q": "1",
    "t": "a",
    "r": "R64rrFLZbTzwNF_p8hbDjj7c83gqM4Y0OqJpZkrIbE4",
    "e": "WqHvVwI4nKbY_3MqV2WZTSe-zUcdNyESu8FBgr1nKtA",
    "m": 1
  },
  "note_canonical_bytes_hex": "<deterministic JCS output, computed by reference canonicaliser>",
  "expected_verifier_result": "PASS_QUALIFIED_TIMESTAMP",
  "rationale": "Backward compatibility. Every v1.2 note remains valid under v1.3."
}
```

### TV-2: Disclosed-mode anchor with canonical namespace

```json
{
  "test_vector_id": "typed-anchor-payload.v1.tv02.disclosed_canonical",
  "description": "Disclosed-mode anchor referencing the canonical OpenProof catalogue entry for NIS2 Art. 20 management body approval. Catalogue entry is resolvable. Manifest conforms.",
  "note_decoded": {
    "q": "1",
    "t": "a",
    "r": "R64rrFLZbTzwNF_p8hbDjj7c83gqM4Y0OqJpZkrIbE4",
    "e": "WqHvVwI4nKbY_3MqV2WZTSe-zUcdNyESu8FBgr1nKtA",
    "m": 1,
    "s": "op:eu.nis2.art20.approval"
  },
  "note_canonical_bytes_hex": "<deterministic JCS output>",
  "catalogue_entry_reference": "openproof-events/spec/catalogue/acts/eu/nis2/art20/approval.json",
  "expected_verifier_result": "PASS_WITH_SEMANTICS",
  "rationale": "The end-to-end happy path: well-formed disclosed mode, catalogue entry present, manifest conforms to the entry's required fields and method constraints."
}
```

### TV-3: Disclosed-mode anchor with third-party namespace, unresolved

```json
{
  "test_vector_id": "typed-anchor-payload.v1.tv03.disclosed_third_party_unresolved",
  "description": "Disclosed-mode anchor referencing a third-party catalogue entry that the verifier does not resolve (offline-strict mode, or the third-party endpoint is unreachable at verification time). The cryptographic proof path passes.",
  "note_decoded": {
    "q": "1",
    "t": "a",
    "r": "R64rrFLZbTzwNF_p8hbDjj7c83gqM4Y0OqJpZkrIbE4",
    "e": "WqHvVwI4nKbY_3MqV2WZTSe-zUcdNyESu8FBgr1nKtA",
    "m": 1,
    "s": "x.example.com:internal.budget.approval"
  },
  "note_canonical_bytes_hex": "<deterministic JCS output>",
  "expected_verifier_result": "PASS_SEMANTICS_UNRESOLVED",
  "rationale": "Federation works: third-party identifiers are accepted as well-formed and the proof path passes even when the verifier has not (yet) fetched the catalogue entry. This is the load-bearing case for permissionless extension."
}
```

### TV-4: Malformed act-type identifier (negative case)

```json
{
  "test_vector_id": "typed-anchor-payload.v1.tv04.malformed_s",
  "description": "Disclosed-mode anchor with an `s` field that violates the grammar in §9.3 (uppercase segment, missing colon). Verifier rejects the anchor regardless of cryptographic proof validity.",
  "note_decoded": {
    "q": "1",
    "t": "a",
    "r": "R64rrFLZbTzwNF_p8hbDjj7c83gqM4Y0OqJpZkrIbE4",
    "e": "WqHvVwI4nKbY_3MqV2WZTSe-zUcdNyESu8FBgr1nKtA",
    "m": 1,
    "s": "OP:EU.NIS2.ART20.APPROVAL"
  },
  "note_canonical_bytes_hex": "<deterministic JCS output>",
  "expected_verifier_result": "FAIL_MALFORMED_ACT_TYPE",
  "rationale": "Grammar enforcement. The verifier rejects the note before reaching the cryptographic verification path. This is the only new FAIL case introduced by v1.3."
}
```

The four test vectors are sufficient for an implementer to validate the typed anchor payload extension end-to-end. The actual `note_canonical_bytes_hex` values are computed by the reference Quoruna-JCS-v1 canonicaliser at v1.3 release and pinned in the published test vector file at the time of release.

---

## Cross-reference impact on other master spec sections

The amendment is additive. Most existing sections are unaffected. The following table records every downstream cross-reference for implementers updating to v1.3.

| Section | Impact | Action |
|---|---|---|
| §2 (proof path) | No change. Steps 1 through 10 unchanged. | None. |
| §4 (manifest schema) | No change. Manifest does not carry the act-type tag. | None. |
| §5 (Quoruna-JCS-v1) | No change. The new field follows the same canonicalisation rules. | None. |
| §6 (Merkle tree) | No change. | None. |
| §7 (decision anchor envelope) | Optional extension. The envelope MAY carry the same `s` value for off-chain correlation. | Optional. |
| §9 (compact note) | **Amended per this document.** | Update implementation. |
| §10 (batch anchor proof) | The receipt MAY carry the resolved catalogue entry alongside the proof. | Optional. |
| §11 (membership proof) | No change. | None. |
| §12 (top-level receipt) | The receipt schema gains an optional `act_type_id` field mirroring the note's `s` value when present. | Update receipt schema. |
| §15 (signing infrastructure) | No change. The signer adapter is type-agnostic. | None. |
| §16 (transaction policy) | The note prefix check is unchanged. The allowlist now accepts notes with the new optional field. | Update allowlist parser. |
| §18 (Trust Root Package) | The TRP now includes the catalogue entries it knows about, with content hashes. | Update TRP composer. |
| §19 (address registry) | No change. | None. |
| §21 (verifier) | **Three new result codes per §9.6.** | Update verifier. |
| §22 (hosting and operations) | No change. | None. |
| §23 (threat model) | New section per §9.7 on disclosure trade-offs. | Update threat model document. |

---

## Open implementation items for v1.3 to v1.4

Four items are noted but deferred. They do not block v1.3.

**Catalogue entry signing.** Canonical catalogue entries are content-addressed via the Trust Root Package. Third-party catalogue entries served from `.well-known` are TLS-protected by the domain's HTTPS certificate but are not independently signed. A v1.4 iteration MAY add a JWS-style detached signature per catalogue entry so that consumers can pin a third-party publisher's key independently of the TLS chain. Deferred because it adds complexity without unlocking new use cases in the first year.

**Catalogue entry supersession chains.** The catalogue entry schema includes a `supersedes` field that is currently always `null` in v1.0 entries. A v1.4 iteration MAY define the supersession chain semantics: when act-type X is superseded by act-type Y, what does a verifier do with old anchors referencing X. Deferred because no real supersession case has arisen yet.

**Cross-namespace aliasing.** A canonical act-type might one day correspond to a third-party act-type that pre-dated it (e.g., `x.acme.org:supplier.coc.attestation` is later canonicalised to `op:corporate.supplier.code_of_conduct`). A v1.4 iteration MAY define how aliases are recorded. Deferred until the case arises.

**COSE_Sign1 SCITT receipt bridge.** The IETF SCITT working group has converged on COSE_Sign1 (RFC 9052, CBOR Object Signing and Encryption, tag 18) as the canonical wire format for transparency-service receipts, with ES256 as the default signing algorithm. Three production implementations exist as of May 2026: Sigstore Rekor v2 (which went GA in March 2026, simplified to two entry types and a tile-backed Merkle log backend), Microsoft `scitt-ccf-ledger` (a Confidential Consortium Framework application targeting AMD SEV-SNP), and GoDaddy `ans` (a transparency-log-backed Agent Name Service, MIT-licensed, also tile-backed with sumdb-note root keys). All three consume COSE_Sign1 receipts. Quoruna v1.3 ships JSON-canonical receipts as the load-bearing format because that is what the offline-strict verifier path uses. A v1.4 iteration WILL add a parallel COSE_Sign1 wire format that carries the same canonical receipt content. The bridge is a single small artefact (same data, two encodings) and is the move that makes Quoruna receipts directly consumable by any SCITT-conformant verifier without further protocol negotiation. Deferred to v1.4 because the SCITT WG has not yet finalised the receipt format normatively: `draft-ietf-scitt-architecture` is in the RFC Editor AUTH48 queue and `draft-ietf-scitt-scrapi-09` is in IESG evaluation as of April 2026. The bridge can land as soon as the normative receipt format stabilises in the published RFC, which is expected mid-2026.

---

## Implementer checklist for v1.2 → v1.3 upgrade

For a project currently implementing master spec v1.2, the upgrade to v1.3 requires the following changes.

1. Update the compact note schema validator to accept an optional `s` field bound to the grammar in §9.3.
2. Extend the verifier result code enum with `PASS_WITH_SEMANTICS`, `PASS_SEMANTICS_UNRESOLVED`, and `FAIL_MALFORMED_ACT_TYPE` per §9.6.
3. Implement (or defer) catalogue entry resolution per §9.5. Offline-strict verifiers MAY skip resolution and always return `PASS_SEMANTICS_UNRESOLVED` for disclosed-mode anchors.
4. Run the four test vectors from this amendment against the implementation. All four MUST produce the expected verifier result.
5. Update the receipt schema in §12 to include the optional `act_type_id` field.
6. If issuing anchors in disclosed mode, decide per anchor whether disclosure is appropriate per §9.7 and document the choice.

The total implementation cost of the v1.2 → v1.3 upgrade is approximately one engineer-day for the schema and verifier changes, plus catalogue resolution which is optional and can be deferred to a later release.

---

*End of amendment.*

*This amendment is published under Apache-2.0. The accompanying test vectors are published under CC0-1.0. The OpenProof Events catalogue and the canonical catalogue entries it contains are published under Apache-2.0.*
