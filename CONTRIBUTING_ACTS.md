# Contributing to the ActProof Events Act Catalogue

This document describes the contribution flow for proposing new entries to the ActProof Events federated act-type catalogue. It is distinct from general code contributions to the reference implementation, the specification text, or the test infrastructure, each of which follows the standard GitHub pull-request flow.

The catalogue is how ActProof Events types an act. Each catalogue entry codifies a recognized regulatory or organizational act (a DORA major ICT-related incident notification, an EUDR Due Diligence Statement preparation, a NIS2 Article 20 management-body approval, an open-source software release attestation) as a structured profile that a verifier can apply to a receipt. The catalogue grows by accretion, not by central planning. Contributions are welcome from regulators, industry associations, standards bodies, downstream implementers, and individual experts.

## The two namespaces

ActProof Events uses two parallel catalogue namespaces.

The canonical namespace `op:` is maintained by the ActProof Events project. Entries in this namespace represent acts with sufficient regulatory weight, structural clarity, and likely broad adoption to justify central curation. The canonical namespace is a quality bar. Submissions go through the review process described in this document.

The third-party namespace `x.<reverse-dns>:` is permissionless. Any organization with control of a DNS domain may publish entries under that domain by serving JSON files at `.well-known/actproof-events/acts/`. No coordination with this project is required. No pull request is needed. Verifiers resolve third-party identifiers at receipt verification time by fetching the JSON from the authoritative DNS path.

Choosing between namespaces is usually straightforward. If the act is recognized across multiple organizations and jurisdictions, and if formal canonical curation would add value, propose it for the canonical namespace through the process below. If the act is specific to a single organization, a specific industry sub-segment, an internal corporate procedure, or a regulatory regime that has not yet stabilized, publish it under your own DNS domain in the third-party namespace. Both produce equivalent verifier behaviour for cryptographic conformance. The difference is only in how the act-type identifier resolves.

Third-party publication is not a downgrade. It is the architectural default. Many of the most valuable entries in the catalogue may live in third-party namespaces, where issuers can describe domain-specific constraints in their own documentation without negotiating consensus with the project maintainers.

## Eligibility for the canonical namespace

The canonical namespace is reserved for acts that meet all of the following criteria.

The act has a clear regulatory or organizational basis. Most canonical entries cite a specific instrument: a directive article, a regulation provision, a statute section, a national-law citation, or an internationally-recognized standard such as a published ISO standard or an IETF RFC. Acts arising from purely internal corporate practice belong in third-party namespaces under the issuing organization's DNS domain.

The act is reasonably stable. Regulations that are still under drafting, in public consultation, or subject to imminent substantive amendment are not appropriate for canonical entries. Once an instrument has been formally adopted and its in-force date has been published, canonical inclusion becomes appropriate.

The act has structural clarity. The maintainer team must be able to articulate, in plain language, what the regulatory or organizational requirement is, what mechanically-checkable constraints follow from the requirement, and which manifest fields a verifier must inspect. Acts whose substantive requirements cannot be reduced to mechanical constraints belong in the third-party namespace, where issuers can describe semantic constraints informally in their own documentation.

The act is plausibly broadly applicable. Canonical entries should be useful to multiple downstream issuers and verifiers, not narrowly scoped to a single organization's procedures.

If any of these criteria is unmet, the third-party namespace remains the appropriate path.

## Submission process for canonical entries

Submitting a canonical catalogue entry takes five steps.

### Step 1: Open a discussion before writing the entry

For canonical entries, open a GitHub Discussion in this repository before drafting. The discussion should name the regulatory instrument, the article or provision being codified, the jurisdiction, the in-force date, and a brief rationale for canonical-namespace inclusion. The maintainer team will respond with one of: encouragement to proceed, suggestion to use the third-party namespace instead, request for additional regulatory analysis, or notification that a similar entry is already in flight.

The discussion step prevents duplicated effort and surfaces scoping concerns before substantial work begins. Skipping it is permissible but increases the risk that the pull request is declined or substantially restructured after submission.

### Step 2: Prepare the catalogue entry

A catalogue entry is a single JSON file conforming to the `actproof.act_profile.v3` schema. The schema, published at `spec/schemas/act_profile.v3.json`, is the authority on structure; this section describes the authoring task rather than restating the schema.

The file lives under `catalogue/acts/`, in a path that reflects the act's jurisdiction and instrument. The existing entries show the convention: `catalogue/acts/eu/dora/ict_incident_notification_initial.v1.json`, `catalogue/acts/eu/nis2/art20/management_body_approval.v1.json`, `catalogue/acts/eu/eudr/dds_preparation.v1.json`. The filename ends with the entry version, `.v1`, `.v2`, and so on. For an act not tied to a regulatory instrument, a domain segment such as `actproof/` or `democracy/` takes the place of the jurisdiction path.

An entry has fifteen required top-level fields: `schema`, `act_type_id`, `claim_type`, `display_name`, `regulatory_citation`, `required_claim_fields`, `optional_claim_fields`, `required_evidence_labels`, `eligible_issuer_roles`, `recommended_witness_roles`, `signature_policy`, `version`, `supersedes`, `maintainer`, and `test_vector_reference`. The reconciled DORA profile, `catalogue/acts/eu/dora/ict_incident_notification_initial.v1.json`, is the worked reference for a new submission.

Authoring attention points follow.

The `schema` field is the literal constant `"actproof.act_profile.v3"` and is the first field in the file.

The `act_type_id` is a dot-separated lowercase identifier under the `op:` namespace, ending with the entry version. The canonical identifiers follow the shape `op:<jurisdiction>.<instrument>[.<article>].<short_name>.v<n>`, for example `op:eu.dora.ict_incident_notification_initial.v1` or `op:eu.nis2.art20.management_body_approval.v1`. The version segment matches the filename and the integer `version` field.

The `claim_type` field is a short identifier for the kind of claim a receipt under this act type carries, for example `ict_incident_notification_initial`.

The `regulatory_citation` block carries `instrument`, `article`, `jurisdiction`, and `in_force_from`. The `instrument` is the instrument as commonly cited, for example `Regulation (EU) 2022/2554`. The `article` is the bare article number as a string, for example `19(4)`, not `Article 19(4)`. The `jurisdiction` is the issuing authority, `EU` or an ISO 3166-1 alpha-2 code. The `in_force_from` field is the date on which obligated entities first become subject to the requirement, as an RFC 3339 full-date, not the date of enactment or publication. For an organizational act with no regulatory basis, `regulatory_citation` is `null`.

The `required_claim_fields` and `optional_claim_fields` arrays name the claim fields a receipt under this act type carries. The optional `claim_field_types` block records the data type of each named field. The `required_evidence_labels` array names the evidence files a conforming receipt must carry. The field lists should be neither over-inclusive, requiring fields a verifier cannot use, nor under-inclusive, omitting fields a verifier needs. Authoring them well usually means preparing the test vector input in parallel, where gaps surface quickly.

The `eligible_issuer_roles` and `recommended_witness_roles` arrays name who may issue a receipt under this act type and who is expected to witness it. The `signature_policy` block records the minimum signature form and the forms supported.

The `version` field is the entry's own version as an integer, `1` for a first publication. The `supersedes` field is `null` for a new entry, or the `act_type_id` of the entry this one replaces. The `maintainer` field is the string `"actproof-events"` for canonical entries. The `test_vector_reference` field is the repository path to the companion `*.test_vectors.json` file produced in Step 3.

A v3 entry may also carry optional blocks that strengthen it. The `reliance_context` block states what a receipt asserts and, in its `non_claims` array, what it does not. The `regulated_context_profile`, `prior_receipts_profile`, `disclosure_profile`, and `submission_evidence_policy` blocks refine the act's context further. A canonical entry SHOULD additionally be source-bound: `source_bindings` cites each official source by a stable identifier and pins its SHA-256, `generation` records how the entry was produced and reconciled, and `transparency_note_reference` points to a prose transparency note. The DORA profile carries all of these. Finally, `profile_status` declares the entry's maturity: an entry that is not yet source-bound declares `draft`, and a source-bound, reconciled entry declares `candidate`.

### Step 3: Prepare the conformance test vectors

Each canonical catalogue entry ships with one companion conformance test vector file, at the same path with the suffix `.test_vectors.json`. For example, `ict_incident_notification_initial.v1.json` is accompanied by `ict_incident_notification_initial.v1.test_vectors.json`.

A test vector is not written by hand. It is generated by `scripts/compute_test_vectors.py`, a pure and deterministic function of two inputs: the catalogue entry, and a manifest input file that is a concrete example of a receipt manifest for the act type. From those, the script computes the canonical manifest bytes, the manifest hash, the envelope and its hash, the ARC-2 JCS note bytes, the hash of the catalogue entry the vector was computed against, and a verifier checklist. The same two inputs produce a byte-identical file on any machine.

To produce the vector, prepare a representative manifest input that exercises every required claim field, then run:

    python scripts/compute_test_vectors.py <entry>.json <manifest_input>.json <entry>.test_vectors.json

The script depends on the `jcs` package for RFC 8785 canonicalization. Run `python scripts/compute_test_vectors.py --help` for the current invocation, and use the DORA entry and its companion vector as the worked example.

Commit the generated file unmodified. A `*.test_vectors.json` file must never be hand-edited: `scripts/validate_vectors.py` re-derives every vector from its inputs and fails the build if a committed file no longer matches, so a hand-edit is caught as staleness. When the catalogue entry changes, regenerate the vector.

Test vector files are published under CC0-1.0 so that downstream verifier implementations can import them without attribution friction. A broader conformance set, with negative vectors that exercise expected failure modes, is on the project roadmap; a contributed entry today ships the single positive vector that its inputs produce.

### Step 4: Open the pull request

The pull request should include both the catalogue entry file and the test vector file as a single atomic change. The pull request description must include the following.

A summary of the act being codified, in plain language suitable for a non-specialist reviewer to understand.

A link to the prior GitHub Discussion from Step 1, if one was opened.

The full text of the regulatory citation, with a stable URL pointing to the authoritative version of the instrument. For EU instruments, this is typically a EUR-Lex ELI URL. For other jurisdictions, the equivalent authoritative source.

A justification for the canonical-namespace placement, addressing the four eligibility criteria in turn.

Any schema gaps surfaced during authoring. If the `actproof.act_profile.v3` schema cannot express something the act genuinely needs, describe the gap in the pull request description. This feeds the schema versioning process, which is governed by `spec/schema_version_policy.md`.

### Step 5: Respond to review

The maintainer team reviews the pull request against the criteria in the next section. Substantive feedback may include requests for additional regulatory citation, refinement of method constraints, modification of required manifest fields, or additional test vectors. Once review is complete and the entry is accepted, the pull request is merged and the entry becomes part of the published canonical catalogue from the next tagged release.

## Review criteria for canonical entries

The maintainer team reviews canonical entry submissions against the following criteria, in approximate order of priority.

Regulatory citation quality. For an act with a regulatory basis, the cited instrument must be in force, the article or provision cited must be the correct one, the in-force date must reflect when obligated entities first become subject, and an authoritative source must be linked. For an organizational act with no regulatory basis, `regulatory_citation` is `null` and this criterion does not apply.

Schema conformance. The entry must validate against the `actproof.act_profile.v3` schema. This is checked automatically by `scripts/validate_catalogue.py`, which also enforces the `format` constraints declared in the schema and rejects a duplicate `act_type_id`.

Claim and evidence field completeness. The `required_claim_fields`, `optional_claim_fields`, and `required_evidence_labels` lists must be sufficient for a verifier to check structural conformance for the act type, without being overly broad. Reviewers test this against the companion test vector: the manifest input should exercise every required claim field.

Test vector freshness. The companion `.test_vectors.json` file must be the unmodified output of `scripts/compute_test_vectors.py` for the committed entry. `scripts/validate_vectors.py` re-derives it and fails the build if it has drifted.

Source binding, where applicable. For an act with a regulatory basis, `source_bindings` should cite each official source by a stable identifier and pin its SHA-256, `generation` should record how the entry was produced and reconciled, and a transparency note should accompany it. An entry without these is accepted, but it declares `profile_status` `draft` rather than `candidate`.

Reliance honesty. Where `reliance_context` is present, its `reliance_statement` and `counterparty_action` must not claim more than a receipt actually proves, and `non_claims` must enumerate the limits as machine-readable identifiers. A receipt evidences an issuer's attestation and the integrity of the committed content; it does not by itself prove that any authority accepted the act.

License compatibility. Catalogue entries are Apache-2.0. Test vectors are CC0-1.0. Pull requests proposing other licenses are reformatted before merge.

Identifier conventions. The `act_type_id` follows the naming conventions described in Step 2. Deviation is permitted only where the standard convention would produce an unreasonably long or ambiguous identifier, and only with explicit maintainer agreement.

Documentation quality. The catalogue entry should carry enough inline natural-language content, in `display_name` and similar fields, that a reader of the JSON file alone can understand what the entry codifies.

## Common reasons for declining canonical status

The maintainer team declines canonical-namespace status in the following situations. In each case, the proposed act remains eligible for the third-party namespace under the proposer's DNS domain.

The instrument is not yet in force. Canonical entries are reserved for active law. Pre-enactment proposals are better placed in third-party namespaces with clear draft-version markers.

The instrument is in active substantive amendment. If the regulatory text is expected to change materially within twelve months, the maintainer team typically defers canonical inclusion until the text stabilizes.

The act is narrowly applicable to a single organization. Canonical entries should serve multiple downstream issuers. Narrowly applicable acts belong in third-party namespaces.

The substantive requirement cannot be reduced to mechanical constraints. Catalogue entries express what a verifier can check automatically. Acts whose substantive requirement is purely qualitative (board approval is "well-considered", risk assessment is "comprehensive") cannot be codified usefully in the canonical catalogue. Third-party namespaces, where issuers can describe their own informal constraints, remain appropriate.

The proposed entry conflicts with existing canonical entries. Where two canonical entries codify substantially the same act under different identifiers, the maintainer team works with proposers to consolidate.

Decline is not a rejection of the act's importance. Many third-party entries are more valuable to specific communities than any canonical entry could be. The DNS-rooted federation is what allows the catalogue to be useful to organizations and use cases that the maintainer team cannot anticipate.

## Third-party namespace publication

Third-party catalogue entries are published by the issuing organization at their own DNS domain. There is no pull request, no maintainer review, and no central registry. The publication flow is straightforward.

The organization owns a DNS domain (for example, `example.com`). The organization decides on an act identifier under the reverse-DNS path (for example, `x.com.example.<segment>`). The organization writes a catalogue entry JSON conforming to the same `actproof.act_profile.v3` schema used for canonical entries. The organization serves the JSON at `https://example.com/.well-known/actproof-events/acts/<segment>.json`.

Verifiers that encounter a third-party identifier in a receipt resolve it by reverse-mapping the identifier to the DNS path and fetching the JSON over HTTPS. The DNS hierarchy is the trust root; if the organization controls the domain, it controls the namespace under it.

Third-party entries are not required to publish test vectors, though doing so substantially aids downstream verifiers. Organizations may publish test vectors at `https://example.com/.well-known/actproof-events/test-vectors/<segment>.test_vectors.json` if they wish. The CC0-1.0 license is recommended for test vectors to maximize interoperability.

The third-party namespace is also the appropriate place to publish entries that are eventually intended for canonical promotion. Organizations may publish under `x.<reverse-dns>:` first, gather operational experience, and then propose canonical inclusion when the entry has stabilized.

## Promotion from third-party to canonical

A third-party entry may be promoted to the canonical namespace through the same submission process described above. Promotion is appropriate when the entry has demonstrated operational stability, broad applicability across multiple organizations, and clear alignment with a stable regulatory or organizational instrument.

The promotion submission references the third-party entry's stable URL and includes any documentation of operational deployment that supports the eligibility argument. Once accepted, the canonical entry takes its place in the catalogue. The third-party entry may remain published at its original DNS path for backward compatibility, or the issuing organization may issue an HTTP 301 redirect to the canonical URL.

The maintainer team encourages promotion of mature third-party entries. The third-party namespace is the architectural default; canonical promotion is recognition that a third-party entry has proven its broader value.

## Versioning and maintenance

Each catalogue entry carries its own version as an integer in the `version` field, starting at `1`. A substantive change to an entry, changing the required claim fields, the evidence labels, the eligible issuer roles, or the reliance context, requires a new entry at an incremented version: a new file whose name and `act_type_id` carry the new version, with the `supersedes` field of the new entry pointing to the `act_type_id` of the one it replaces. The superseded entry remains published at its original path, and receipts issued against it remain verifiable. A non-substantive change, correcting a typo in `display_name` or clarifying inline text, is made in place and does not increment the version.

When a canonical entry's underlying regulatory instrument is amended, the maintainer team produces a new version of the entry in the same way.

Deprecation is handled structurally. When an entry is retired, because its instrument was repealed or because it was replaced by an incompatible successor, the entry file is moved into a `_deprecated/` directory beside the active entries. The catalogue loader does not load entries under `_deprecated/`: they cannot be resolved and cannot be issued against, by construction. The predecessor voting-shaped v1 entries are retained this way. Receipts already issued against a now-deprecated entry remain verifiable from the self-contained provenance carried by the receipt itself.

## Maintainer commitments

The maintainer team is currently small. As of the date of this document, Advisa EOOD (Sofia, Bulgaria) is the sole maintainer organization. The commitments below reflect that operational reality. They may be tightened as additional maintainer organizations join.

Discussions opened on the canonical catalogue typically receive a first response within two weeks. Response times may extend during periods of grant deliverable focus or other project commitments. Where a response time exceeds three weeks, contributors are encouraged to send a polite follow-up.

Pull requests for canonical entries typically receive initial maintainer review within four to six weeks of opening. Subsequent review cycles after a contributor's response to feedback typically take two to three weeks. These targets are aspirational rather than guaranteed.

Catalogue entries published in the canonical namespace remain accessible at their original paths indefinitely, subject only to repository hosting changes that would receive at least sixty days of public notice and accompanying HTTP-level redirect plans.

Test vector files published with canonical entries remain CC0-1.0 licensed and importable by downstream verifier implementations without attribution.

The maintainer team does not commit to specific timelines for resolving substantive disagreements about regulatory interpretation. Where reviewers and contributors disagree on whether a method constraint matches a regulatory requirement, or whether an act is sufficiently stable for canonical inclusion, the maintainer team may defer decisions pending additional input from independent experts.

Where solo-maintainer bandwidth becomes a sustained bottleneck, the maintainer team will openly invite additional maintainer organizations through a public process and will document the invitation criteria.

## Security disclosures

Security issues affecting catalogue entries (incorrect citation, manifest fields that fail to detect material non-conformance, method constraints that admit improperly-validated decisions) should be reported by email to `deyan@advisa.tech` with the subject prefix `[ActProof Security]`. The maintainer team commits to acknowledging receipt within five business days and coordinating disclosure timelines with the reporter.

Security issues affecting the substrate specification, the reference implementation, or the verification logic follow the security disclosure process documented in the main repository security policy.

## Code of conduct

Contributions and discussions in this repository are subject to a Code of Conduct that will be formally adopted from the Contributor Covenant once contributor activity warrants it. In the interim, contributors are expected to act with professional courtesy, technical good faith, and respect for the regulatory expertise that informs catalogue entries.

## Contact

For questions about this contribution flow, open a GitHub Discussion against this repository. For collaboration inquiries that do not fit the public discussion format, regulatory citation review at scale, or proposals to join the maintainer team, contact `deyan@advisa.tech`.
