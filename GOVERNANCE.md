# ActProof Events Catalogue Governance

This document describes how the ActProof Events act-type catalogue is governed: what the maturity status of a profile means, what a profile does and does not claim, how a profile is challenged or corrected, and where the boundary lies between what the project guarantees mechanically and what remains a matter of human and legal judgement.

It is the policy companion to `CONTRIBUTING_ACTS.md`, which describes the step-by-step mechanics of submitting an entry. Read this document to understand how to trust the catalogue. Read `CONTRIBUTING_ACTS.md` to understand how to add to it.

A catalogue is only worth as much as the discipline by which entries enter it and the honesty with which their limits are stated. That discipline is not bureaucracy around the product. For a commons whose purpose is verifiable provenance, the governance is part of the product.

## The two claims, and what governance protects

ActProof Events rests on a deliberate division between two kinds of claim, and everything in this document follows from it.

Source provenance is mechanical. Each profile pins the SHA-256 of the official source artefacts it is built from. Anyone can fetch those artefacts, recompute the hashes, and confirm that the profile is built against exactly those documents. This requires no trust in the author and no judgement. It is true or false by computation.

Fidelity is contributed. Whether a profile faithfully represents what the law requires, whether the mapping from rule to fields is complete and correct, cannot be settled by a hash. It is a reading. It is published openly, accompanied by a plain-language transparency note, and it is open to challenge, correction and replacement.

Governance exists to keep these two claims separate and honest. It protects the mechanical claim by enforcing that source bindings are real and reproducible. It protects the contributed claim by making fidelity inspectable and contestable, and by never letting a fidelity judgement be presented as if it were a mechanical proof.

## Profile status model

Every catalogue entry declares a `profile_status` that signals its maturity to anyone relying on it. A buyer, an auditor or a downstream implementer needs to know at a glance whether a profile is experimental or production-suitable. The status ladder has four levels.

`draft`. The entry exists and validates against the schema, but it is not yet source-bound, or its mapping has not been reconciled against the official sources. A draft profile is a work in progress. It must not be relied upon for any operational purpose. It is visible so that work can happen in the open and so that others can contribute early.

`candidate`. The entry is source-bound: it pins the SHA-256 of each official source artefact it cites, its `generation` block records how it was produced and reconciled, and a transparency note accompanies it. Candidate status further requires at least one successful source-binding verification run, in which each pinned source hash has been recomputed from the cited artefact and confirmed to match, so that the profile is source-bound by demonstrated check and not merely by declaration. A candidate profile has passed mechanical provenance and the maintainer's own fidelity reconciliation, but it has not yet been independently reviewed. The single DORA major ICT-incident initial-notification profile is candidate status at the time of writing. Candidate is the highest status a profile reaches on the strength of the author's and maintainer's work alone.

`reviewed`. The entry's fidelity has been examined by at least one named party independent of the author, and that review is recorded with the profile. A profile reaches `reviewed` only when the review record states the reviewer's name or organisation, their relationship to the author and maintainer, the date, the profile version and entry hash reviewed, the official source artefacts reviewed, the scope of the review, the findings, any unresolved objections, and an explicit statement that the review is not an official legal interpretation unless the reviewer is a competent authority and says so expressly. Review does not make the mapping officially correct (see the legal boundary below); it records that a competent independent party examined the mapping and that their findings are public. These minimum requirements exist precisely so that `reviewed` cannot become marketing language. `reviewed` is the status a production user should look for, and the point at which paid, named review workflows attach (see below).

`deprecated`. The entry is retired because its underlying instrument was repealed or amended, or because it was superseded by an incompatible successor. In the current implementation, deprecated entries are moved into a `_deprecated/` directory and are not loaded by the catalogue loader, so they cannot be newly resolved or built against. Artefacts already produced against a deprecated entry remain verifiable only where they carry self-contained provenance, or where the deprecated profile is supplied explicitly. A future archival-resolution mode is planned so deprecated profiles can remain resolvable for verification while remaining blocked for new use.

Source-binding is a property, not a status. A profile either pins its sources by hash or it does not. The status ladder describes maturity of review; source-binding describes whether the mechanical claim is present at all. A `candidate` and a `reviewed` profile are both source-bound; they differ in whether an independent party has examined the fidelity.

## The legal-review boundary

This is the most important boundary in the project, and it is stated here so that no commercial or institutional use can mistake what a profile claims.

ActProof Events proves source provenance mechanically and exposes fidelity for review. It does not, and cannot, certify that a profile is a legally correct interpretation of the law.

A profile is not an official interpretation. No competent authority has endorsed the mapping unless one separately and explicitly does so. A `reviewed` status records that an independent party examined the mapping; it does not transfer legal authority to that party or to the project. Legal correctness, fitness for a particular regulatory filing, and compliance with an obligation remain the responsibility of the entity relying on the profile and its own legal advisers.

The honest answer to "who says this mapping is right" is therefore: the project says which official source artefacts the profile is built on, and proves it by hash; the project and any named reviewers say, in the open and under their own names, how they read those sources into the profile; and the law itself remains the only authority on what is correct. The profile makes the reading inspectable. It does not make it official.

Paid and institutional review workflows can attach to this model without breaking it. A reviewer, an auditor, a law firm or a regulator may examine a profile, record named findings, attach audit notes, or grant an institutional approval, and that record travels with the profile. What the open profile itself must never do is claim official interpretation, legal compliance, or regulatory acceptance on its own. The commons stays honest about its limits; the value others add by reviewing it is recorded as theirs, by name, not absorbed into an implied authority the project does not have.

## How a profile is challenged or corrected

A source-bound catalogue is only trustworthy if anyone can contest a mapping in the open. Challenge is a first-class part of governance, not an exception to it.

A challenge to source provenance is mechanical and decisive. If the SHA-256 a profile pins does not match the official artefact it claims, the profile is wrong, and the fix is not a discussion. Report it as a security issue (see `CONTRIBUTING_ACTS.md`), and the entry is corrected or withdrawn.

A challenge to fidelity is a reading against a reading, and is resolved in the open. Anyone may open a public issue arguing that a profile's mapping is incomplete, incorrect, or misleading: that a required field is missing, that a classification threshold is mapped wrongly, that a disclosure tier misreads what the law protects. The maintainer responds in the open. Where the challenge is correct, the entry is revised at an incremented version (the prior version remains published and verifiable). Where reviewer and maintainer disagree on a matter of regulatory interpretation, the maintainer does not adjudicate it by fiat: the disagreement is recorded publicly, and the challenger always retains the option to publish a competing profile in the permissionless `x.<reverse-dns>:` namespace. The open namespace is the ultimate check: no maintainer can suppress a competing reading, because no maintainer controls the namespace.

This is why the federation matters for governance and not only for scale. A catalogue with a single gatekeeper and no exit is a private authority wearing an open licence. A catalogue where any domain holder can publish a competing, equally-verifiable profile is a genuine commons, because disagreement has a public, permissionless outlet.

## Tooling: the profile authoring workbench (planned)

Authoring a good profile today is a manual, expert task: read the source cluster, map clauses to fields, generate the source bindings, draft the transparency note, produce the conformance vectors, lint the result, and assemble the contribution package. That work is exactly the labour the catalogue needs and exactly where tooling helps most.

A profile authoring workbench is on the roadmap as a tool, separate from the standard and the catalogue themselves. It would support source upload and import, clause-to-field mapping, source-binding generation, transparency-note drafting, conformance-vector generation, profile linting against the schema and the review criteria, and export of a complete contribution package. Such a tool is where open standard and commercial service legitimately meet: the profiles and the standard stay open, while authoring, review and integration tooling can be built and offered commercially above the commons. The workbench is named here so the boundary is clear in advance. It is a tool that helps produce profiles; it is not part of what a profile claims, and it confers no authority on the profiles it helps author.

## Why governance is the product

For most software, governance is overhead. For a verifiable-provenance commons, it is the substance. A profile that anyone can generate is worth little; an AI can produce a plausible one in seconds. What is scarce, and what this governance produces, is a profile whose source provenance is proven, whose fidelity is reviewable and reviewed, whose status is honestly declared, whose limits are stated rather than hidden, and which can be challenged and corrected in the open. That is the difference between a folder of JSON and a commons a regulated organisation can actually rely on. The discipline described here is what makes the catalogue trustworthy, and trustworthiness is the whole point.

## Relationship to other documents

`CONTRIBUTING_ACTS.md` describes the mechanics of submission: the namespaces, eligibility, the five-step process, review criteria, and third-party publication. This document describes the policy those mechanics serve: the status model, the legal boundary, and the challenge process. The `spec/` directory holds the normative schema and versioning policy. Where this document and the specification appear to differ on a normative point, the specification governs.
