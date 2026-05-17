# Contributing to the OpenProof Events Act Catalogue

This document describes the contribution flow for proposing new entries to the OpenProof Events federated act-type catalogue. It is distinct from general code contributions to the reference implementation, the specification text, or the test infrastructure, each of which follows the standard GitHub pull-request flow described in `CONTRIBUTING.md`.

The catalogue is the substrate's mechanism for typing governance events by the regulatory or organizational act they record. Each catalogue entry codifies a recognized act (a NIS2 Article 20 director approval, an AI Act Article 26 deployer risk assessment, a corporate board resolution under articles of incorporation, an OpenSSF Alpha-Omega security advisory acknowledgment) as a structured schema that verifiers can apply to a receipt. The catalogue grows by accretion, not by central planning. Contributions are welcome from regulators, industry associations, standards bodies, downstream implementers, and individual experts.

## The two namespaces

OpenProof Events uses two parallel catalogue namespaces.

The canonical namespace `op:` is maintained by the OpenProof Events project. Entries in this namespace represent acts with sufficient regulatory weight, structural clarity, and likely broad adoption to justify central curation. The canonical namespace is a quality bar. Submissions go through the review process described in this document.

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

The catalogue entry is a single JSON file conforming to the `actproof.act_catalogue_entry.v1` schema defined in section 9.5 of the OpenProof Events specification. The file path follows the convention `catalogue/acts/<jurisdiction>/<instrument>/<article>/<short-name>.json`. For acts under EU directives or regulations, the convention is `catalogue/acts/eu/<directive-or-regulation>/<article>/<short-name>.json`. For acts under national law, `catalogue/acts/<iso-3166-1-alpha-2>/<instrument>/<short-name>.json`. For corporate or generic acts not tied to a specific jurisdiction, `catalogue/acts/corporate/<short-name>.json`.

The catalogue entry must contain all eleven required top-level fields specified in section 9.5 of the master specification: `schema`, `act_type_id`, `display_name`, `regulatory_citation`, `required_manifest_fields`, `method_constraints`, `receipt_profile_recommendations`, `version`, `supersedes`, `maintainer`, and `test_vector_reference`. The first canonical entry, `catalogue/acts/eu/nis2/art20/approval.json`, serves as the reference template for new submissions.

Required attention points when authoring the entry follow.

The `act_type_id` uses dot-separated lowercase ASCII under the `op:` namespace. The convention for EU directive articles is `op:eu.<instrument>.<article>.<short-name>`, where instrument is a short identifier (`nis2`, `ai_act`, `gdpr`, `cra`). For national-law acts, `op:<iso-3166-1-alpha-2>.<instrument>.<short-name>`. For corporate or generic acts, `op:corporate.<short-name>.<version>` where version disambiguates iterations.

The `regulatory_citation` block contains four fields. The `instrument` field carries the short instrument identifier as commonly cited, for example `Directive (EU) 2022/2555` for NIS2 or `Regulation (EU) 2024/1689` for the AI Act. The `article` field is the bare article number as a string, for example `20` or `26`, not `Article 20` or `Article 26`. The `jurisdiction` field is the issuing authority, for example `EU` for European Union instruments, or the ISO 3166-1 alpha-2 code for national instruments. The `in_force_from` field is the date on which obligated entities first become subject to the requirement, in ISO 8601 date format, not the date of enactment or publication. CELEX identifiers, EUR-Lex ELI URLs, and equivalent stable references for non-EU jurisdictions are proposed for inclusion as optional fields in v1.4 of the catalogue entry schema.

The `required_manifest_fields` list enumerates the dot-paths into the canonical manifest that a verifier must check for presence in order to consider the receipt structurally complete for this act type. By NIS2 reference convention, the list starts with `manifest_version` followed by the structural identifier fields (`decision_id`, `decision_type`, `tenant_id`, `system_created_at`), then `method_parameters` paths, then the four content-anchor hash fields (`eligibility_snapshot_hash`, `action_set_hash`, `tally_output_hash`, `result_hash`), with `attachment_hashes` last. The list should be neither over-inclusive (requiring fields a verifier cannot use) nor under-inclusive (omitting fields a verifier needs to validate the regulatory requirement). Authoring the field list well usually requires writing the test vectors in parallel; gaps surface quickly.

The `method_constraints` block is a nested object containing both `allowed_method_ids` and `minimum_quorum_basis_points`. The `method_constraints.allowed_method_ids` array names the voting or decision methods that satisfy the substantive regulatory requirement. For acts requiring management body or governance committee approval, methods that produce a clear binary approve-or-reject outcome (`simple_majority_v1`, `supermajority_two_thirds_v1`, `approval_voting_v1`, `consent_based_v1`) are typically included. Methods that produce ranked or scored outcomes without a clear binary decision are typically excluded unless the regulatory instrument explicitly permits them. Non-voting attestation methods such as a single designated officer attestation are a documented v1.4 schema gap; v1.0 catalogue entries support voting methods only.

The `method_constraints.minimum_quorum_basis_points` field specifies the lowest quorum (in integer basis points, where 5001 means more than 50 percent) consistent with the regulatory requirement. For acts requiring majority participation, the minimum is 5001. For acts requiring supermajority participation, higher minimums apply.

The `receipt_profile_recommendations` list names the audiences for which receipts of this act type are typically rendered. Standard profiles include `regulator`, `auditor`, `director`, `competent_authority`, and `counterparty`. Custom profiles may be added if the act type has audiences that the standard list does not cover.

The remaining fields complete the entry. The `schema` field is the literal constant `"actproof.act_catalogue_entry.v1"` identifying the schema version, and is the first field in the file. The `version` field is the catalogue entry's own semantic version; the first publication is `"1.0"`. The `supersedes` field is `null` for new entries; when an updated entry replaces an older one, this field carries the repository path of the superseded file. The `maintainer` field carries the string `"actproof-events"` for canonical entries (a structured object form with organization, contact, and role is a documented v1.4 gap). The `test_vector_reference` field carries the repository path to the companion `.test_vectors.json` file produced in Step 3.

### Step 3: Prepare the conformance test vectors

Each canonical catalogue entry must ship with a companion conformance test vector file at the same path with the suffix `.test_vectors.json`. For example, `catalogue/acts/eu/nis2/art20/approval.json` is accompanied by `catalogue/acts/eu/nis2/art20/approval.test_vectors.json`.

The test vector file conforms to the `actproof.act_catalogue_test_vectors.v1` schema. It contains at minimum three test vectors: one positive case demonstrating `PASS_WITH_SEMANTICS` for a conforming manifest, and at least two negative cases demonstrating expected failure codes for the most likely conformance violations (typically: wrong method, below-quorum, missing required field).

Each test vector contains a synthetic manifest exercising the conformance check, a synthetic compact note as it would appear on the chain, the expected conformance result, the expected verifier result code, and a brief rationale explaining what the vector demonstrates. Synthetic hash placeholders should be deterministic and reproducible from a documented seed pattern, so reviewers can confirm hashes were not silently fabricated. Test vector files are published under CC0-1.0 to allow downstream verifier implementations to import them without attribution friction.

The first canonical entry's test vector file, `catalogue/acts/eu/nis2/art20/approval.test_vectors.json`, serves as the reference template.

### Step 4: Open the pull request

The pull request should include both the catalogue entry file and the test vector file as a single atomic change. The pull request description must include the following.

A summary of the act being codified, in plain language suitable for a non-specialist reviewer to understand.

A link to the prior GitHub Discussion from Step 1, if one was opened.

The full text of the regulatory citation, with a stable URL pointing to the authoritative version of the instrument. For EU instruments, this is typically a EUR-Lex ELI URL. For other jurisdictions, the equivalent authoritative source.

A justification for the canonical-namespace placement, addressing the four eligibility criteria in turn.

Any schema gaps surfaced during authoring. Many entries surface gaps in the v1.0 catalogue entry schema. Documenting them in the PR description helps the spec maintenance process and informs eventual v1.4 schema iteration.

### Step 5: Respond to review

The maintainer team reviews the pull request against the criteria in the next section. Substantive feedback may include requests for additional regulatory citation, refinement of method constraints, modification of required manifest fields, or additional test vectors. Once review is complete and the entry is accepted, the pull request is merged and the entry becomes part of the published canonical catalogue from the next tagged release.

## Review criteria for canonical entries

The maintainer team reviews canonical entry submissions against the following criteria, in approximate order of priority.

Regulatory citation quality. The cited instrument must be in force, the article or provision cited must be the correct one, the in-force date must reflect when obligated entities first become subject, and the authoritative source must be linked.

Schema conformance. The entry must validate against the `actproof.act_catalogue_entry.v1` schema as specified in section 9.5 of the master specification. Validation is automated where possible.

Required manifest fields completeness. The field list must be sufficient for a verifier to check structural conformance for the act type without being overly broad. Reviewers test this by inspecting the test vectors and confirming that the positive case exercises all listed fields and that the negative cases break only listed constraints.

Method constraint alignment. The allowed methods must satisfy the substantive regulatory requirement. Where the regulatory text is ambiguous, the maintainer team errs on the side of including more methods rather than fewer, with the rationale documented in the PR.

Quorum minimum justification. The quorum minimum must be defensible given the substantive regulatory requirement. For acts requiring majority participation, 5001 basis points is the floor.

Test vector coverage. Minimum three vectors (one positive, two negative). Vectors must use synthetic but realistic data. Hash placeholders must be deterministic and reproducible from a documented seed pattern.

License compatibility. Catalogue entries are Apache-2.0. Test vectors are CC0-1.0. Pull requests proposing other licenses are reformatted before merge.

Identifier conventions. The `act_type_id` follows the naming conventions described in Step 2. Deviation is permitted only where the standard convention would produce an unreasonably long or ambiguous identifier, and only with explicit maintainer agreement.

Documentation quality. The catalogue entry should include sufficient inline content that a reader of the JSON file alone can understand what the entry codifies. Brief description text in the `display_name` and similar natural-language fields is encouraged.

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

The organization owns a DNS domain (for example, `example.com`). The organization decides on an act identifier under the reverse-DNS path (for example, `x.com.example.<segment>`). The organization writes a catalogue entry JSON conforming to the same `actproof.act_catalogue_entry.v1` schema used for canonical entries. The organization serves the JSON at `https://example.com/.well-known/actproof-events/acts/<segment>.json`.

Verifiers that encounter a third-party identifier in a receipt resolve it by reverse-mapping the identifier to the DNS path and fetching the JSON over HTTPS. The DNS hierarchy is the trust root; if the organization controls the domain, it controls the namespace under it.

Third-party entries are not required to publish test vectors, though doing so substantially aids downstream verifiers. Organizations may publish test vectors at `https://example.com/.well-known/actproof-events/test-vectors/<segment>.test_vectors.json` if they wish. The CC0-1.0 license is recommended for test vectors to maximize interoperability.

The third-party namespace is also the appropriate place to publish entries that are eventually intended for canonical promotion. Organizations may publish under `x.<reverse-dns>:` first, gather operational experience, and then propose canonical inclusion when the entry has stabilized.

## Promotion from third-party to canonical

A third-party entry may be promoted to the canonical namespace through the same submission process described above. Promotion is appropriate when the entry has demonstrated operational stability, broad applicability across multiple organizations, and clear alignment with a stable regulatory or organizational instrument.

The promotion submission references the third-party entry's stable URL and includes any documentation of operational deployment that supports the eligibility argument. Once accepted, the canonical entry takes its place in the catalogue. The third-party entry may remain published at its original DNS path for backward compatibility, or the issuing organization may issue an HTTP 301 redirect to the canonical URL.

The maintainer team encourages promotion of mature third-party entries. The third-party namespace is the architectural default; canonical promotion is recognition that a third-party entry has proven its broader value.

## Versioning and maintenance

Canonical catalogue entries are versioned through the `version` field of the schema. Substantive changes to an entry (changing required manifest fields, modifying method constraints, raising or lowering quorum minimums) require a version increment. Non-substantive changes (correcting typos in `display_name`, clarifying inline documentation, updating maintainer contact) do not require version increments but do follow the same pull-request review process.

When a canonical entry's underlying regulatory instrument is amended, the maintainer team produces an updated version of the entry. Older versions remain published at their original paths with the `version` field unchanged. New versions are published at paths suffixed with the new version number. Receipts issued against older versions remain verifiable indefinitely.

Deprecation of canonical entries is rare and only occurs when the underlying regulatory instrument is repealed or substantially superseded. Deprecated entries are marked with a `deprecated_at` field and a `superseded_by` field pointing to the replacement, but remain accessible at their original paths for historical verification.

## Maintainer commitments

The maintainer team is currently small. As of the date of this document, Advisa EOOD (Sofia, Bulgaria) is the sole maintainer organization. The commitments below reflect that operational reality. They may be tightened as additional maintainer organizations join.

Discussions opened on the canonical catalogue typically receive a first response within two weeks. Response times may extend during periods of grant deliverable focus or other project commitments. Where a response time exceeds three weeks, contributors are encouraged to send a polite follow-up.

Pull requests for canonical entries typically receive initial maintainer review within four to six weeks of opening. Subsequent review cycles after a contributor's response to feedback typically take two to three weeks. These targets are aspirational rather than guaranteed.

Catalogue entries published in the canonical namespace remain accessible at their original paths indefinitely, subject only to repository hosting changes that would receive at least sixty days of public notice and accompanying HTTP-level redirect plans.

Test vector files published with canonical entries remain CC0-1.0 licensed and importable by downstream verifier implementations without attribution.

The maintainer team does not commit to specific timelines for resolving substantive disagreements about regulatory interpretation. Where reviewers and contributors disagree on whether a method constraint matches a regulatory requirement, or whether an act is sufficiently stable for canonical inclusion, the maintainer team may defer decisions pending additional input from independent experts.

Where solo-maintainer bandwidth becomes a sustained bottleneck, the maintainer team will openly invite additional maintainer organizations through a public process and will document the invitation criteria.

## Security disclosures

Security issues affecting catalogue entries (incorrect citation, manifest fields that fail to detect material non-conformance, method constraints that admit improperly-validated decisions) should be reported by email to `deyan@advisa.tech` with the subject prefix `[OpenProof Security]`. The maintainer team commits to acknowledging receipt within five business days and coordinating disclosure timelines with the reporter.

Security issues affecting the substrate specification, the reference implementation, or the verification logic follow the security disclosure process documented in the main repository security policy.

## Code of conduct

Contributions and discussions in this repository are subject to a Code of Conduct that will be formally adopted from the Contributor Covenant once contributor activity warrants it. In the interim, contributors are expected to act with professional courtesy, technical good faith, and respect for the regulatory expertise that informs catalogue entries.

## Contact

For questions about this contribution flow, open a GitHub Discussion against this repository. For collaboration inquiries that do not fit the public discussion format, regulatory citation review at scale, or proposals to join the maintainer team, contact `deyan@advisa.tech`.
