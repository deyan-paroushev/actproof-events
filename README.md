# OpenProof Events

**A federated cryptographic substrate for verifiable governance evidence.**

OpenProof Events is a specification, a reference implementation, a federated act-type catalogue, and a conformance test vector corpus that together let any organization cryptographically anchor its governance decisions to a public ledger, in a way that any verifier can independently confirm decades later, regardless of which vendor produced the original receipt.

The substrate addresses a structural gap in the contemporary governance ecosystem. Today, governance evidence is fragmented across incompatible systems. Board portal vendors, GRC platforms, audit firm PDFs, regulatory filing systems, crypto governance platforms, AI risk-assessment tools, and bespoke spreadsheets each maintain their own audit-trail formats. None of these systems are interoperable. None survive vendor death cleanly. None are independently verifiable decades later by an auditor or regulator who lacks access to the originating system. OpenProof Events provides the common primitive that these systems can adopt without lock-in: a canonical evidence schema, a public-ledger commitment protocol, and a permissionlessly extensible catalogue of regulated act types.

## Status

The v1.3 substrate specification is published. The Python reference implementation is operationally validated against Algorand testnet (transaction `ZOD6JHOWDDAAJUG37WNU4F2DLYGDAYZ7H6KHPYKTYQ52L744SWNA`, confirmed in round 63,336,268 on 13 May 2026, with full eleven-stage verification PASS). The federated act-type catalogue contains its first canonical seed entry, codifying NIS2 Article 20 director approval, with CC0-licensed conformance test vectors. The project is under active development. Sovereign Tech Agency and NLnet NGI0 Commons funding applications are in flight for the next stage of substrate maturation.

## The primitive

A governance decision in OpenProof Events terms is a structured event with a method (how the decision was reached), an eligibility set (who was entitled to participate), a tally (the result of counting), an attachment set (the substantive material under decision), and an authority chain (the source of authority for the decision).

Each event produces a canonical receipt under a deterministic JSON Canonicalization Scheme. The receipt content is hashed, the hash is committed to a public ledger through a signed transaction, and the resulting transaction identifier becomes the temporal anchor. A verifier consuming the receipt at any later date can recompute the canonical form, recompute the hash, fetch the on-chain transaction, and confirm the commitment was made when the issuer claims it was, by the issuer who claims to have made it.

The architecture follows the substrate-plus-vehicle pattern. The substrate (canonical evidence, commitment protocol, catalogue, verification grammar) is chain-agnostic. The vehicle (which public ledger anchors which receipts) is a chosen implementation detail. The v1 reference implementation anchors to Algorand because of the mature Python SDK, the ARC-2 transaction note convention that natively supports the substrate's compact note schema, and the low and predictable transaction cost. The substrate is not Algorand-specific; future implementations could anchor to Ethereum, to Bitcoin via OpenTimestamps, or to other public ledgers without changing the canonical evidence schema or the verification grammar.

## Federation through DNS

The act-type catalogue uses a two-namespace grammar. The canonical namespace `op:` is maintained by OpenProof Events as a quality bar. The third-party namespace `x.<reverse-dns>:` is permissionless. Any organization with control of a DNS domain can mint OpenProof-compatible act-types under that domain by serving a JSON file at `.well-known/openproof-events/acts/`. No coordination, no registry fee, no central approval. The DNS hierarchy is the trust root for third-party identifiers, structurally aligned with W3C did:web resolution.

This is the move that lets the substrate scale beyond what any single maintainer team could manage. A regulator in one jurisdiction can publish their own catalogue entry for a specific regulated act under their domain. An industry association can publish entries for their sector. A standards body can publish entries that ratify cross-organization practice. Verifiers resolve identifiers through the appropriate namespace at receipt verification time. The catalogue grows by accretion, not by central permission.

## Repository contents

The `spec/` directory contains the OpenProof Events specification, currently version 1.3 revision 2. The amendment publishes the typed anchor payload, ARC-2 compliance citation, did:web alignment, and the COSE_Sign1 SCITT receipt bridge as a Phase 2 deliverable.

The `catalogue/acts/` directory contains canonical seed entries published by the project maintainers. The first entry, at `eu/nis2/art20/approval.json`, codifies management body approval of cybersecurity risk-management measures under Directive (EU) 2022/2555 Article 20. Additional seed entries for AI Act Article 26 risk assessment and a generic corporate board resolution are scheduled for publication during the week of submission to STS.

The `test-vectors/` directory contains CC0-1.0 licensed conformance test vectors. Each canonical catalogue entry ships with a companion test vector file demonstrating positive and negative conformance cases. The CC0 license is chosen to allow other transparency-service implementations to import the test vectors into their own conformance suites without attribution friction or license negotiation.

The `python/` directory contains the reference Python implementation. JCS canonicalization, domain-separated Merkle aggregation, compact note encoding under ARC-2, KMS-backed Ed25519 signing, end-to-end anchoring, and independent verification are implemented as thirteen modules totaling approximately four thousand lines of code. The implementation depends only on Apache-2.0 and MIT-licensed components.

The `salt-erasure/` directory contains the standalone salt-erasure module, implementing pseudonymized-evidence-then-key-deletion semantics suitable for GDPR-compliant audit trails. CC0 test vectors demonstrate before-erasure linkability and after-erasure unlinkability per EDPB Guidelines 02/2025.

The `CONTRIBUTING_ACTS.md` document specifies the contribution flow for new canonical catalogue entries, including the regulatory citation requirement, the required manifest fields specification, the allowed methods constraints, the conformance test vector requirement, and the review checklist applied by the maintainer team.

## Quick start: verify the first OpenProof anchor

To verify the first OpenProof Events anchor on Algorand testnet, clone this repository, install the Python reference implementation, and run the verifier against the published proof file:

```
git clone https://github.com/deyan-paroushev/openproof-events
cd openproof-events/python
pip install -e .
python -m openproof_events.verifier ../examples/anchor-testnet-20260513.json
```

The verifier runs seven offline verification stages (structural field validation, version conformance, manifest canonical byte reproduction, manifest hash recomputation, Merkle root recomputation, envelope schema validation, envelope hash recomputation) and three online stages (transaction confirmation on Algorand testnet, on-chain note byte match against the stored proof, on-chain note decoded hash match against the stored proof). All eleven stages return PASS for the published anchor.

Verification is deterministic and reproducible. Any party with internet access to a public Algorand testnet node can run the same verification and obtain the same result. No access to OpenProof Events infrastructure, the original issuing system, or any private credentials is required.

## Reference implementation and adjacent projects

The reference Python implementation in `python/` is the first implementation of the v1.3 specification. Quoruna, a decision-recording product maintained by Advisa EOOD, uses OpenProof Events as its anchoring substrate. The Quoruna product layer (multi-tenant orchestration, persistent storage, customer-facing user interfaces, operational tooling) is separately licensed and out of scope for this repository.

Implementers building additional reference implementations in other languages (TypeScript, Rust, Go) are welcome and encouraged. Conformance is demonstrated by passing the CC0 test vector corpus. The maintainer team is committed to keeping the specification and test vectors stable enough to support cross-language conformance without continuous spec churn.

## Standards trajectory

OpenProof Events is positioned for engagement with three standards bodies in parallel.

The IETF Supply Chain Integrity, Transparency and Trust (SCITT) working group is converging on COSE_Sign1 receipts with tile-backed Merkle log roots. The OpenProof Events v1.4 amendment will add a COSE_Sign1 wire format option to the canonical receipt schema, making OpenProof receipts directly consumable by SCITT-conformant verifiers including Sigstore Rekor v2 (GA March 2026), Microsoft scitt-ccf-ledger, and GoDaddy ans.

The Algorand Foundation maintains the ARC (Algorand Request for Comments) process for ecosystem standards. The OpenProof Events compact note schema, which already conforms to ARC-2's `<dapp-name>:<format><data>` shape with format code `j` for JCS-canonicalised JSON, is positioned for submission as a new ARC during 2026. The submission establishes formal Algorand-ecosystem recognition in parallel with the IETF SCITT engagement.

The W3C Verifiable Credentials working group provides the integration path to the EU Digital Identity Wallet ecosystem. The third-party namespace `x.<reverse-dns>:` is structurally aligned with did:web, allowing implementers who already operate did:web infrastructure to expose OpenProof catalogue entries alongside their existing DID documents. From 2027, EU regulated private sectors are required to accept EUDI Wallet authentication, opening a sector-wide integration window for governance evidence that maps to Qualified Electronic Attestations of Attributes.

## Adjacent projects

OpenProof Events occupies a distinct niche from existing transparency and attestation infrastructure. Sigstore solves supply chain integrity for software artifacts. C2PA solves content provenance for digital media. Ethereum Attestation Service provides a generic attestation registry on EVM chains. OpenTimestamps provides Bitcoin-anchored timestamp proofs. Snapshot provides off-chain voting infrastructure for crypto-native DAOs. None of these projects addresses governance evidence as a distinct domain with regulatory mapping, multi-chain anchoring, and a federated catalogue of regulated act types.

The architectural patterns are deliberately consistent with these neighbouring projects where consistency is possible. The DNS-rooted federation pattern matches the pattern used by did:web, IndieAuth, Webmention, Mastodon, and Bluesky. The canonical receipt with public-ledger commitment matches the pattern used by OpenTimestamps. The permissionless registry of typed schemas matches the pattern used by EAS. The catalogue-of-types-with-content-addressed-identifiers pattern is conceptually similar to C2PA's assertion types. Compatibility with these patterns is a design goal, not a coincidence.

## Licensing

Code and specifications in this repository are licensed under Apache License 2.0. See `LICENSE` for the full text. Apache 2.0 is chosen to maximize adoption: the substrate is intended to be implementable by closed-source vendors, regulated entities, and open-source projects without copyleft friction.

Conformance test vectors in `test-vectors/` are licensed under Creative Commons Zero v1.0 Universal (CC0-1.0). The CC0 license is chosen to allow other transparency-service implementations to import the test vectors into their own conformance suites without attribution friction.

The Quoruna product layer, hosted at a separate repository by Advisa EOOD, is licensed under GNU Affero General Public License v3.0 or later. Code in this OpenProof Events repository does not depend on the Quoruna product layer.

## Contributing

The project welcomes contributions across four tracks.

New canonical catalogue entries under the `op:` namespace require regulatory citation, required manifest fields specification, allowed methods constraints, and conformance test vectors. See `CONTRIBUTING_ACTS.md` for the full contribution flow and review criteria.

Third-party catalogue entries under the `x.<reverse-dns>:` namespace require no coordination with this project. Publish them at your domain's `.well-known/openproof-events/acts/` path. Verifiers will resolve them at receipt verification time. The substrate is designed so that downstream issuers do not need our permission to extend the catalogue.

Reference implementations in additional languages are welcome. Conformance is demonstrated by passing the CC0 test vector corpus. Open a discussion before starting substantial implementation work so the maintainer team can offer guidance on spec ambiguities and known edge cases.

Specification clarifications, bug reports, and security disclosures should be filed as GitHub issues. A formal Code of Conduct adapted from the Contributor Covenant will be added shortly.

## Maintainers

OpenProof Events is currently maintained by Advisa EOOD (Bulgarian Unified Identification Code 206448172, registered office in Sofia, Bulgaria), the company behind the Quoruna decision-recording product. Long-term governance is expected to transition to a multi-organization maintainer team as additional reference implementations and downstream adopters establish the substrate as shared infrastructure across organizations.

## Funding

This work has been produced without external funding through 13 May 2026, the date of the first public release. Applications for partial support are pending with the Sovereign Tech Agency and NLnet NGI0 Commons. The substrate specification, reference implementation, federated catalogue, and conformance test vector corpus published as of this README's commit date were produced independently by Advisa EOOD (UIC 206448172, Sofia, Bulgaria).

## Citation

Academic and industry citations should reference the specification version and the catalogue entries as separate artifacts:

> Paroushev, D. (2026). OpenProof Events: A Federated Cryptographic Substrate for Verifiable Governance Evidence. Specification version 1.3, revision 2. https://github.com/deyan-paroushev/openproof-events/blob/main/spec/openproof-events.spec.md

> Advisa EOOD. (2026). OpenProof Events canonical act-type catalogue entry: op:eu.nis2.art20.approval. Published 13 May 2026. https://github.com/deyan-paroushev/openproof-events/blob/main/catalogue/acts/eu/nis2/art20/approval.json

## Contact

For technical questions, open a GitHub issue against this repository. For collaboration inquiries, regulatory citation review, contributions to the canonical catalogue, or research partnership proposals, contact `deyan@advisa.tech`.
