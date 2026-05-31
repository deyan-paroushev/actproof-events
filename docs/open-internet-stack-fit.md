# ActProof Events as an Open Internet Stack building block

ActProof Events is a small digital-commons layer for machine-readable public-rule acts. It is not a compliance platform, a filing system, a legal-advice engine, a rules engine, or a timestamping service. It is a source-bound profile layer that other systems can inspect, reuse, fork and verify.

This note explains where it sits among other open systems, what consumes it, and what it deliberately does not do, so maintainers of adjacent projects can decide whether and how to build on it.

## Why this belongs in an Open Internet Stack conversation

Public rules are increasingly implemented through digital forms, APIs, workflows, schemas, reporting systems and compliance-data processes. The legal text stays public, but the operational machine profile that applies it often becomes private: embedded in a vendor product, an internal spreadsheet, a workflow engine or a closed compliance system. The public source can be read by everyone; the machine profile that applies it is often visible only to whoever built the tool.

ActProof Events addresses that gap. It provides an open catalogue of small, versioned JSON profiles for discrete acts performed under public rules. Each profile states what act is being performed, which official source artefacts the profile was built from, which fields and evidence labels are expected, which disclosure expectations apply, and what the profile explicitly does not claim. The purpose is to keep the machine-readable layer of public rules source-bound, inspectable and contestable.

## The layer it occupies

ActProof sits between public source material and downstream systems.

```text
official public source artefacts
        |
source-bound ActProof profile
        |
forms . workflows . APIs . reporting tools . compliance-data systems . verifiers
```

The catalogue does not replace those downstream tools. It gives them a reusable profile they can point to when someone asks: which public source shaped this machine logic?

## Core contribution

1. **Source-bound profiles.** Public-rule acts are represented as profile JSON. Each profile cites official source artefacts and pins their retrieved bytes by SHA-256.
2. **Profile-source verification.** A verifier confirms that a profile is the published catalogue entry and that its pinned source hashes match the cited official documents supplied by the reviewer.
3. **Public fidelity review.** A source hash proves provenance, not correctness. The mapping from source text to fields stays a public reading that can be inspected, challenged, corrected or replaced.
4. **Catalogue governance.** Profiles have status, versioning, non-claims, contribution rules, challenge paths and deprecation rules, so the catalogue is not merely a folder of JSON files.

## What it does not do

ActProof Events deliberately does not claim to provide legal advice, provide an official interpretation of law, prove compliance, prove that a filing is accepted by a competent authority, prove factual truth, or replace regulatory reporting systems, rules-as-code engines, digital identity, trust services, timestamping or transparency logs.

This boundary is part of the trust model. ActProof proves source provenance mechanically and exposes fidelity for public review. Legal judgement stays a human and institutional responsibility. The boundary is enforced by the format: non-claims are a required, machine-readable part of every profile and are checked by the conformance vectors, so a profile that overclaims fails conformance.

## Current worked example: DORA

The current source-bound worked example is `op:eu.dora.ict_incident_notification_initial.v1`, covering the DORA major ICT-related incident initial notification.

It is useful because the machine profile does not come from one paragraph alone. It draws from a source cluster: Regulation (EU) 2022/2554 Article 19; Commission Delegated Regulation (EU) 2024/1772; Commission Delegated Regulation (EU) 2025/301; and Commission Implementing Regulation (EU) 2025/302. The profile pins these artefacts by hash and makes the source cluster inspectable.

The point is not that ActProof can create JSON. Anyone can create JSON. The point is that the profile shows which official artefacts shaped the JSON and lets someone else check the binding without trusting the author.

## Why it is a commons

The value of a provenance-and-fidelity layer depends on it being neutral and inspectable by everyone, including parties who do not trust each other or the maintainer. The meaning layer of public rules should not become a private moat. The commons properties are open-source code, an open profile catalogue, source-bound profiles, conformance vectors, a public contribution and challenge process, a permissionless third-party namespace, an offline browser verification path, no hosted-service dependency for the core check, and explicit legal and non-claim boundaries.

Commercial products can build above this layer: authoring tools, monitoring, integration, reporting workflows, review services and enterprise APIs. The profile layer itself stays inspectable and reusable.

## How other open systems could use it

These systems do not need ActProof to run their whole workflow. They can use it for one narrower question: is the machine profile this workflow relies on bound to the public source artefacts it claims? Plausible consumers include compliance-data and structured-reporting tools, public-service and civil-service digital workflows, civic-technology systems, audit and assurance tools, rules-as-code engines, data-space compliance workflows, and open governance tools.

## Fit with Open Internet Stack values

ActProof contributes a small but reusable layer for openness (public profiles and public source bindings), trustworthiness (independently checkable source provenance), human oversight (fidelity stays reviewable and challengeable), interoperability (profiles consumable by different systems), resilience (profiles, schemas and vectors can be forked and self-hosted), accountability (non-claims and governance make the limits visible), and public benefit (public rules stay inspectable when turned into machine-readable form).

## Maturity statement

ActProof Events is currently a candidate commons component, not a finished public standard. The current implementation includes an installable package, specification text, a profile schema, catalogue entries, the DORA source-bound profile, a browser verifier, governance and contribution files, and conformance vectors. The next maturity steps are to harden the catalogue, improve conformance coverage, expand the set of source-bound profiles, improve the verification tooling, and make contribution and review workflows easier for independent implementers.

## Current public artefacts

- Project site: https://actproof.org/
- Principles: https://actproof.org/principles/
- Catalogue: https://actproof.org/catalogue/
- Verifier: https://actproof.org/verify/
- Governance guide: https://actproof.org/guide/
- Repository: https://github.com/deyan-paroushev/actproof-events
- Package: https://pypi.org/project/actproof-events/

## In one sentence

ActProof Events is a source-bound public-rule profile layer: it helps larger open systems keep machine-readable public rules inspectable, verifiable, contestable and reusable, without relying on the maintainer.
