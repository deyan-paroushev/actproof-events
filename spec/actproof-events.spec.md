# ActProof Events Specification

**Version**: v1.4-rc1
**Status**: Pre-release candidate
**License**: Spec text is CC0. Schemas and test vectors are Apache-2.0.
**Maintainer**: actproof-events project

---

## Abstract

ActProof Events specifies an open substrate for issuing verifiable attestations of regulated or governance acts. The substrate defines a catalogue of act types, a manifest format for attestation content, an envelope structure for anchoring, a canonical hashing pipeline, and an on-chain note format for public ledger commitment. Any conforming implementation that follows this specification produces test vector-reproducible attestations whose proof trails can be verified independently by any third party against the public ledger, without trusting either the issuer or any intermediary platform.

The v1.4 release is the first act-native release. Earlier v1.x releases modelled regulated acts as voting events. The v2 catalogue entry schema documented here removes those voting derivatives. This is a substrate change, not a behaviour change: any attestations issued under the deprecated v1 entries can still be resolved for historical reference.

---

## 1. Introduction

### 1.1 Scope

This specification defines:

- The catalogue entry schema (`actproof.act_profile.v2`)
- The attestation manifest schema (`actproof.attestation_manifest.v1`)
- The envelope schema (`actproof.attestation_envelope.v1`)
- The canonicalization pipeline (RFC 8785 JCS)
- The on-chain anchoring format (ARC-2 JCS note, disclosed mode)
- The verifier conformance test vector format (`actproof.test_vector.v1`)
- The witness recipient model
- The approval evidence model and its boundary with eIDAS

This specification does NOT define:

- The internal database schema of any specific implementation
- The user interface of any specific implementation
- The transport layer between implementations and recipients (email, webhook, etc.)
- The retention or archival policies of implementations beyond evidence durability requirements

### 1.2 Relationship to SCITT

ActProof Events is architecturally aligned with the IETF SCITT architecture (`draft-ietf-scitt-architecture`, RFC 9943 to-be, currently at AUTH48 as of the publication of this specification). The mapping of ActProof Events concepts to SCITT concepts is documented in Section 6. A COSE_Sign1 wire-format bridge is planned and will land in a v1.5 specification iteration once RFC 9943 is published. Until that bridge ships, ActProof Events implementations emit JSON-canonical receipts. They are NOT yet SCITT-compatible at the wire level.

### 1.3 Conformance language

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, and OPTIONAL in this document are to be interpreted as described in RFC 2119.

---

## 2. Catalogue

### 2.1 Catalogue entry schema v2

A catalogue entry describes a single regulated or governance act type. The schema is at `spec/schemas/act_profile.v2.json` and validates against JSON Schema draft 2020-12.

A v2 catalogue entry MUST include the following top-level fields:

- `schema`: the literal string `"actproof.act_profile.v2"`
- `act_type_id`: canonical identifier under the `op:` namespace
- `claim_type`: short snake_case identifier describing the semantic shape
- `display_name`: human-readable display name
- `regulatory_citation`: object with `instrument`, `article`, `jurisdiction`, `in_force_from`, or null for non-regulatory acts
- `required_claim_fields`: array of manifest field identifiers
- `optional_claim_fields`: array of manifest field identifiers
- `required_evidence_labels`: array of evidence label identifiers
- `eligible_issuer_roles`: array of role identifiers
- `recommended_witness_roles`: array of role identifiers
- `signature_policy`: object with `minimum` and `supports` keys
- `version`: monotonic integer
- `supersedes`: previous act_type_id or null
- `maintainer`: maintainer identifier
- `test_vector_reference`: repository-relative path to the entry's test vector file

A v2 catalogue entry MUST NOT include any of the following fields, which were present in v1 entries:

- `method_constraints` or any `method_*` field
- `receipt_profile_recommendations`
- `eligibility_snapshot_hash`
- `action_set_hash`
- `tally_output_hash`
- `result_hash`

These fields encoded voting-event assumptions that do not describe regulated acts.

### 2.2 act_type_id namespace

Canonical `op:` identifiers MUST match the pattern:

```
^op:[a-z0-9_]+(\.[a-z0-9_]+)+\.v[0-9]+$
```

Examples:

- `op:eu.nis2.art20.management_body_approval.v1`
- `op:eu.eudr.dds_preparation.v1`
- `op:actproof.software_release.v1`

The trailing `.v[0-9]+` segment is REQUIRED for new act_type_ids. Legacy v1 identifiers without an explicit version segment (e.g., `op:eu.nis2.art20.approval`) are preserved in the namespace for historical reference but MUST NOT be used for new issuance.

### 2.3 Deprecated v1 entries

Catalogue directories MAY contain a `_deprecated/` subdirectory holding v1 entries that have been superseded by v2 entries. Each `_deprecated/` directory MUST contain a README documenting the migration map from v1 to v2.

Conforming catalogue loaders:

- MUST surface only v2 entries for new issuance.
- MUST refuse to load v1 entries for new issuance.
- MUST allow read-only access to v1 entries for historical attestation rendering (a receipt for an attestation issued against `op:eu.nis2.art20.approval` in v1 must still render).
- MUST cache catalogue entries in memory at process startup and reload only on explicit signal (no per-request filesystem reads).

### 2.4 Migration path

When a v1 entry is superseded by a v2 entry, the v1 file is moved into the `_deprecated/` subdirectory with git history preserved. The v2 entry's `supersedes` field references the v1 act_type_id. Issuers who previously issued attestations against the v1 act_type_id can still resolve their historical commitments because the namespace is preserved.

The reference v2 entries included with this release supersede the following v1 entries:

| v1 act_type_id | v2 act_type_id |
| --- | --- |
| `op:eu.nis2.art20.approval` | `op:eu.nis2.art20.management_body_approval.v1` |

New v2 entries with no v1 predecessor set `supersedes` to null.

---

## 3. Attestation manifest

### 3.1 Schema

An attestation manifest is the issuer-side representation of a single regulated act. The manifest carries the act type identifier, the issuer fields, the claim fields specified by the catalogue entry, the evidence references, and the designated recipients. The schema identifier is `actproof.attestation_manifest.v1`.

A manifest MUST include:

- `schema`: the literal string `"actproof.attestation_manifest.v1"`
- `manifest_version`: integer (currently 1)
- `act_type_id`: matches a v2 catalogue entry
- `catalogue_entry_version`: integer matching the catalogue entry's `version`
- `tenant_id`: implementation-specific tenant identifier
- `issuer_org_name`: legal name of the issuing entity
- `title`: short title for the act
- `system_created_at`: ISO 8601 timestamp
- `claim_fields`: object containing all `required_claim_fields` and any present `optional_claim_fields` per the catalogue entry
- `evidence`: array of evidence references (label, filename, SHA-256, byte size)
- `recipients`: array of designated recipients (role, organisation name, email)

A manifest MAY include:

- `subtitle`: short subtitle for the act
- `authority_label`: human-readable description of the issuer's authority basis

### 3.2 Required fields

A manifest is well-formed if and only if:

1. Every identifier in `catalogue_entry.required_claim_fields` is present as a key in the manifest's `claim_fields`.
2. Every identifier in `catalogue_entry.required_evidence_labels` is present as the `label` of at least one item in the manifest's `evidence` array.
3. Every recipient in the manifest's `recipients` array has a `role` listed in or compatible with the catalogue entry's `recommended_witness_roles`. Recipients with non-recommended roles MAY be included but SHOULD be flagged as non-standard by the implementation.

### 3.3 Canonicalization

Manifests MUST be canonicalized using JSON Canonicalization Scheme (JCS) as specified in RFC 8785 before hashing. JCS canonicalization:

- Sorts object keys lexicographically
- Removes insignificant whitespace
- Normalises number representations
- Produces deterministic UTF-8 bytes

Reference implementation: the Python `jcs` package on PyPI. Equivalent libraries exist for JavaScript, Go, Rust, and Java. Any conforming JCS implementation produces byte-identical output for the same input.

### 3.4 Manifest hash

The manifest hash is the SHA-256 hash of the JCS-canonical bytes of the manifest:

```
manifest_hash = SHA-256(JCS(manifest))
```

The hash is represented in test vectors and receipts as a lowercase hex string with no `0x` prefix.

---

## 4. Envelope

### 4.1 Schema

The envelope wraps the manifest hash with metadata required for on-chain anchoring. The schema identifier is `actproof.attestation_envelope.v1`.

An envelope MUST include:

- `schema`: the literal string `"actproof.attestation_envelope.v1"`
- `envelope_version`: integer (currently 1)
- `act_type_id`: matches the manifest's `act_type_id`
- `catalogue_entry_version`: matches the manifest's `catalogue_entry_version`
- `manifest_hash`: lowercase hex SHA-256 of the canonical manifest bytes
- `merkle_root`: lowercase hex root of the Merkle tree binding this attestation

### 4.2 Envelope hash

The envelope hash is computed over the JCS-canonical envelope bytes:

```
envelope_hash = SHA-256(JCS(envelope))
```

The envelope hash is included in the ARC-2 JCS note (Section 5.1) so a verifier can independently confirm both the manifest binding and the envelope binding from the on-chain commitment.

### 4.3 Merkle root construction

For v2.0 implementations, the Merkle tree is single-leaf. The Merkle root equals the manifest hash:

```
merkle_root = manifest_hash
```

Future versions of this specification will define multi-leaf Merkle trees for batched anchoring. The envelope schema does not change; the `merkle_root` field accommodates both single-leaf and multi-leaf constructions.

---

## 5. Anchoring

### 5.1 ARC-2 JCS note format

Attestations are anchored on the Algorand public ledger using the ARC-2 transaction note convention. The note bytes consist of a protocol prefix followed by a JCS-canonical inner JSON object:

```
note = b"quoruna/v1:" + JCS(inner)
```

The inner object MUST include the following fields in disclosed mode:

- `r`: base64url-no-padding encoding of the Merkle root bytes
- `m`: integer count of leaves in the Merkle tree (1 for v2.0 single-leaf)
- `t`: type discriminator (`"a"` for attestation)
- `q`: Quoruna protocol version (`"1"`)
- `e`: base64url-no-padding encoding of the envelope hash bytes
- `s`: the `act_type_id` of the catalogue entry

Field key length is intentionally minimised because Algorand transaction notes have byte-size limits.

### 5.2 Disclosed mode

In disclosed mode (REQUIRED for v2.0), the inner object includes the `s` (act_type_id) field. This makes the act type publicly inspectable from the on-chain note alone, without requiring the verifier to fetch the manifest or envelope separately.

A future undisclosed mode is reserved for v1.5+ implementations that wish to anchor act_type_id privately. Undisclosed mode is NOT defined in this specification.

### 5.3 Algorand mainnet anchoring

Production implementations SHOULD anchor on Algorand mainnet. Development and testing implementations MAY anchor on Algorand testnet. Per-tenant configuration of the target network is RECOMMENDED.

A reference verifier verifies an anchored attestation by:

1. Fetching the transaction at the recorded `txid` from the Algorand indexer
2. Reading the transaction note bytes
3. Confirming the note begins with the `quoruna/v1:` prefix
4. Canonicalizing the remainder and parsing the inner JSON object
5. Confirming the `r` field matches the expected Merkle root
6. Confirming the `e` field matches the expected envelope hash
7. Confirming the `s` field matches the expected act_type_id

### 5.4 RFC 3161 timestamping

Implementations SHOULD acquire an RFC 3161 timestamp token for the manifest hash from a Qualified Trust Service Provider (QTSP) before submitting the on-chain anchor. The timestamp token provides corroborating evidence of when the manifest existed and is independently verifiable against the QTSP's certificate chain.

Reference implementations use QuoVadis EU QTSP as the primary timestamping authority with a failover chain to additional QTSPs.

---

## 6. SCITT alignment

ActProof Events is architecturally aligned with the IETF SCITT architecture (`draft-ietf-scitt-architecture`, RFC 9943 to-be, currently at AUTH48). The mapping of ActProof Events concepts to SCITT concepts is:

| ActProof Events | SCITT |
| --- | --- |
| Issuer | Issuer |
| Manifest | Signed Statement |
| Envelope + on-chain anchor | Transparency Service entry |
| Attestation receipt | Receipt |
| Anchored manifest | Transparent Statement |
| Witness recipient | Relying Party |
| Commit operation | Registration |

A COSE_Sign1 wire-format bridge is planned and will land in a v1.5 specification iteration once RFC 9943 is published. Until that bridge ships, ActProof Events implementations emit JSON-canonical receipts. They are NOT yet SCITT-compatible at the wire level.

Implementations and external publications MUST NOT describe ActProof Events as a "SCITT reference implementation" or "SCITT-compatible" prior to the publication of the COSE_Sign1 bridge in v1.5+. The accurate descriptor is "SCITT-aligned, COSE_Sign1 bridge planned."

---

## 7. Witness recipient model

Designated recipients in ActProof Events are addressed by email. Each recipient has a role drawn from the catalogue entry's `recommended_witness_roles`, describing the recipient's function in relation to the issuing entity (auditor, regulator, counsel, insurer, counterparty).

Whether the email address belongs to an individual or to an organisational intake address is an implementation choice for the issuer. Both are supported. Organisational intake addresses (e.g., `audit-evidence@firm.example`) SHOULD be preferred for durability across staff changes at the receiving organisation.

A `recipient_contact_name` field MAY be carried as informational metadata. It is not used as the authoritative delivery target; the email address is authoritative.

The set of `recommended_witness_roles` in any v2 catalogue entry SHOULD be drawn from a stable role vocabulary:

- `external_auditor`
- `competent_authority_supervisor`
- `outside_counsel`
- `internal_audit`
- `do_insurer`
- `cyber_insurer`
- `downstream_buyer`
- `supply_chain_finance_provider`
- `notified_body`
- `certification_body`
- `release_subscriber`
- `downstream_integrator`
- `package_registry`
- `security_researcher`

Implementations MAY extend the vocabulary with custom roles for their specific use cases. Custom roles SHOULD follow the snake_case convention and SHOULD be documented in the catalogue entry's accompanying notes.

---

## 8. Approval evidence model

This section is the eIDAS firewall. It bounds the legal claims that any conforming implementation may make about its output.

### 8.1 issuer_record is an evidence record, not an eIDAS signature

The catalogue entry's `signature_policy.minimum` field specifies the floor of what must be present at commit time. The `issuer_record` value means the implementation records the issuer's commit action as an evidence record. This evidence record SHOULD include:

- The issuer's authenticated email address
- The IP address of the commit request
- The user agent string of the commit request
- A single-use token hash for the commit action
- The manifest hash
- The version of any consent or attestation text the issuer agreed to
- The exact UTC timestamp of the commit action

This evidence record is an **evidence record only**. It is NOT an Advanced Electronic Signature (AES), Qualified Electronic Signature (QES), or any other category of electronic signature under Regulation (EU) 910/2014 (eIDAS) or its successor regulations.

Implementations MUST NOT claim that the platform-recorded issuer action is itself an eIDAS-grade signature. Implementations MUST NOT describe the `issuer_record` as a "signature" in user-facing surfaces without explicit qualification (e.g., "evidence record of the issuer's commit action").

### 8.2 External signature evidence

Issuers who require eIDAS AES or QES MUST attach an externally produced signature file as evidence under one of the labels specified in the catalogue entry's `signature_policy.supports`:

- `external_qes_pdf`: a PDF signed with a Qualified Electronic Signature
- `external_aes_certificate`: a certificate of Advanced Electronic Signature
- `signed_board_minutes`: board minutes signed by the relevant body
- `third_party_signing_service_certificate`: a certificate from a third-party signing service
- `internal_attestation_record`: an internal attestation document
- `gpg_signed_release`: a GPG-signed software release
- `sigstore_cosign_signature`: a Sigstore cosign signature

The externally produced signature artifact is treated as evidence in the manifest. Its SHA-256 hash is included in the canonical manifest. The implementation does NOT verify the cryptographic validity of the external signature itself; verification of external signatures is the responsibility of whoever later relies on them. The implementation only commits the binding between the act and the signature artifact.

### 8.3 Allocation of legal responsibility

The substrate externalizes the proof trail. It does NOT externalize legal responsibility. The parties to an attestation (issuer, recipients, future verifiers) remain accountable for the substance and truth of their claims. What changes is the durability and independent verifiability of the evidentiary record on which any later claim, defense, audit, or insurance recovery is argued.

---

## 9. Federation

Federation of the catalogue across third-party namespaces is preserved in this specification for forward compatibility. The grammar for third-party namespaces is:

```
^x\.<reverse-dns>:[a-z0-9_]+(\.[a-z0-9_]+)+\.v[0-9]+$
```

Examples:

- `x.com.example.acme:internal.governance_act.v1`
- `x.org.example.consortium:joint_disclosure.v1`

Federation is **a v1.5+ feature**. v2.0 reference implementations are expected to ship canonical `op:` entries only. Third-party namespace minting and resolution under `x.<reverse-dns>:` is deferred to a future specification iteration and is NOT REQUIRED for v1.4 conformance. Implementations MAY defer federation support without losing conformance to this version of the specification.

---

## 10. Verifier conformance

A verifier implementation conforms to this specification if, given any test vector input file from `scripts/test_vector_inputs/`, it produces the `manifest_hash_hex`, `envelope_hash_hex`, and `arc2_note.full_note_b64` values recorded in the corresponding test vector file.

Test vectors are produced by the deterministic generator at `scripts/compute_test_vectors.py`. Verifier conformance can be tested without any network connectivity, by recomputing the hashes locally from the raw manifest input.

Once `reference_anchor.txid` is populated with a real Algorand testnet transaction, additional conformance checks become available:

- Fetching the on-chain note and confirming byte-identical match against `arc2_note.full_note_b64`
- Decoding the on-chain note and confirming the inner fields match the test vector's recorded values

Reference test vectors are included for:

- `op:eu.nis2.art20.management_body_approval.v1` at `catalogue/acts/eu/nis2/art20/management_body_approval.v1.test_vectors.json`
- `op:eu.eudr.dds_preparation.v1` at `catalogue/acts/eu/eudr/dds_preparation.v1.test_vectors.json`

Additional test vectors will be added for other catalogue entries as they land.

---

## Appendix A. Schema files

The authoritative JSON Schema files for v1.4-rc1 are:

- `spec/schemas/act_profile.v2.json`

The attestation manifest schema and envelope schema are described prose-only in Sections 3 and 4 of this document. JSON Schema files for these schemas are deferred to v1.5.

---

## Appendix B. Reference catalogue entries

The reference catalogue entries included with v1.4-rc1 are:

- `catalogue/acts/eu/nis2/art20/management_body_approval.v1.json`
- `catalogue/acts/eu/eudr/dds_preparation.v1.json`

Deprecated v1 entries are preserved under their respective `_deprecated/` directories with migration documentation.

---

## Appendix C. Glossary

**Act type**: a regulated or governance act recognised by the substrate, identified by a canonical `op:` namespace identifier.

**Anchor**: the on-chain commitment of an attestation, expressed as an Algorand transaction whose note field contains the ARC-2 JCS encoded merkle root and envelope hash.

**Attestation**: an issued instance of an act type, comprising a manifest and (after commit) an anchor.

**Catalogue entry**: a JSON document describing an act type's required and optional fields, its evidence requirements, its eligible issuer roles, its recommended witness roles, and its signature policy.

**Envelope**: a structure wrapping the manifest hash and merkle root with metadata required for anchoring.

**Issuer**: the party who creates and commits an attestation.

**Manifest**: the issuer-side document describing a single attestation's content (act type, issuer, claim fields, evidence, recipients).

**Merkle root**: the root hash of a Merkle tree binding one or more attestations to a single anchor. v2.0 implementations use single-leaf trees where the Merkle root equals the manifest hash.

**Recipient**: a designated party receiving the verification handle for an attestation, with a role drawn from the catalogue entry.

**Settlement**: the moment at which an attestation transitions from `awaiting_commit` to `committed`, comprising manifest canonicalization, envelope composition, RFC 3161 timestamp acquisition, and Algorand anchor submission.

**Test vector**: a JSON document binding a catalogue entry to a concrete manifest input and the deterministic outputs (manifest hash, envelope hash, ARC-2 note bytes) that any conforming verifier should reproduce.

**Witness**: a designated recipient of an attestation. The term is used interchangeably with "recipient" in this specification.

---

## Appendix D. Changelog

### v1.4-rc1 (this release)

**Substrate changes**:
- Introduced `actproof.act_profile.v2` schema with act-native fields.
- Deprecated v1 voting-derivative fields: `method_constraints`, `eligibility_snapshot_hash`, `action_set_hash`, `tally_output_hash`, `result_hash`, `receipt_profile_recommendations`.
- Introduced `_deprecated/` directory convention for v1 namespace preservation.

**New catalogue entries**:
- `op:eu.nis2.art20.management_body_approval.v1`
- `op:eu.eudr.dds_preparation.v1`

**New sections**:
- Section 6 SCITT alignment downgraded from "reference implementation" to "aligned, COSE_Sign1 bridge planned."
- Section 7 witness recipient model formally defined.
- Section 8 approval evidence model added (eIDAS firewall).
- Section 9 federation flagged as v1.5+ feature.

**Tooling**:
- `scripts/compute_test_vectors.py` for deterministic test vector generation.
- Reference test vectors for both new catalogue entries.

### v1.3 and earlier

See git history for the substrate's voting-event-shaped predecessor releases. v1.3 was the last release under the previous schema.

---

*This specification is licensed CC0 1.0 Universal. The accompanying schema files and test vectors are licensed Apache-2.0. Implementations of this specification may be released under any license their authors choose.*
