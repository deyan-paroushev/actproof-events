# DORA source bundle for ActProof Events

This folder contains the official source artefacts used to build and verify
the source bindings for the profile:

    op:eu.dora.ict_incident_notification_initial.v1

The profile maps DORA major ICT-related incident initial notification under
Regulation (EU) 2022/2554, Article 19, together with the delegated and
implementing acts used for classification, report content, time limits, forms,
templates and procedures.

This bundle is not legal advice and does not claim that any receipt proves DORA
compliance. It exists so reviewers and independent implementers can reproduce
the source hashes used by the ActProof Events profile.

## Files in this folder

- `README.md` (this file): explains what the bundle is and how to verify it.
- `source-bindings.json`: machine-readable record of which CELEX source, which
  article or annex, and which SHA-256 each binding entry pins. Browsable on
  GitHub without download.
- `dora-sources.zip`: the full source corpus, containing the four official PDFs,
  the CELLAR notice metadata, and a copy of `source-bindings.json` for
  self-contained verification.

## Sources included in the bundle

Four official DORA-family source artefacts, identified by CELEX number.

- CELEX 32022R2554, Regulation (EU) 2022/2554. DORA. The primary legal act.
  The profile is source-bound to Article 19.
  sha256: 85307f9e2a0409826dd0f54489645935816d16e929f0db4db3ef15badd11d38c

- CELEX 32024R1772, Commission Delegated Regulation (EU) 2024/1772. Incident
  classification criteria, materiality thresholds and report details. The
  profile is source-bound to Article 8.
  sha256: 416fb104161f8b3eb0aae2601060ab869b1672cfa8452d20798800301538ceab

- CELEX 32025R0301, Commission Delegated Regulation (EU) 2025/301. Content
  and time limits for initial, intermediate and final reports. The profile is
  source-bound to Articles 1, 2 and 5.
  sha256: 47a209a9f73e228e85e1dad2934d917d5791629fc98add06fc6fda0acb872dbf

- CELEX 32025R0302, Commission Implementing Regulation (EU) 2025/302. Standard
  forms, templates and procedures. The profile is source-bound to Annexes I
  and II.
  sha256: 37ec431c7a11b8b30b39d1c1f0d95c39539d1c1e7236301ee3b06bb229ff009c

## Bundle layout (inside dora-sources.zip)

    dora-sources/
      artefacts/
        32022R2554.pdf          (DORA, the Digital Operational Resilience Act)
        32024R1772.pdf          (Delegated 2024/1772, classification and materiality)
        32025R0301.pdf          (Delegated 2025/301, content and time limits)
        32025R0302.pdf          (Implementing 2025/302, forms and procedures)
      notices/
        32022R2554.branch.xml
        32022R2554.manifestation-*.object.xml   (CELLAR manifestation metadata)
      source-bindings.json      (identical to the sibling file beside the zip)

The `artefacts/` folder holds the four Official Journal PDFs as retrieved from
the EU Cellar service. The `notices/` folder holds the CELLAR notice metadata
used during retrieval. The `source-bindings.json` file is the machine-readable
record of all seven binding entries pinning four distinct PDF SHA-256 digests
to specific articles and annexes of the profile.

## Bundle digest

dora-sources.zip SHA-256:

    a004be82aa308402d1d8bce251a55522c55c576b5e88ba0981dcaed6149c7c37

This hash is also published in the GitHub Release notes and in the NGI Zero
Commons Fund application package (Attachment 2: Reference Implementation
Evidence Pack). The zip is content-stable. This README and any future edits
to it do not change the zip hash, because the README lives next to the zip,
not inside it.

## Provenance and reuse

The EU legal texts are reused from EUR-Lex and the Publications Office of the
European Union. EU legal-document reuse is governed by the EUR-Lex legal
notice and Commission Decision 2011/833/EU. The ActProof Events metadata,
retrieval scripts, source-bindings file and test vectors are licensed
separately under the repository licences (Apache-2.0 for code, CC0-1.0 for
conformance vectors and test data).

## What this bundle proves

This bundle proves only that the ActProof Events DORA profile was mapped
against specific, named source artefacts and that the recorded SHA-256
digests can be independently recomputed from the included PDFs. It does not
prove that the mapping is legally complete, that a receipt satisfies DORA, or
that any competent authority accepts a filing. Those questions remain outside
the scope of ActProof Events.

## How to verify

1. Compute the SHA-256 of `dora-sources.zip` and compare to the Bundle digest
   above. They must match exactly.
2. Unpack the zip. For each PDF under `artefacts/`, compute its SHA-256 and
   compare to the value listed under "Sources included in the bundle" above
   and to the value recorded in `source-bindings.json`. These four hashes are
   what the profile is bound to.
3. Optionally fetch the same CELEX entries directly from EUR-Lex using the
   `retrieved_from` URLs in `source-bindings.json` and confirm byte equality
   with the retained artefacts.

## Project context

ActProof Events is an open catalogue of source-bound machine profiles for
public-interest acts. See https://actproof.org and the actproof-events
repository for the full project. This bundle is the reproducibility exhibit
for the candidate DORA Article 19 profile.

At submission of the NGI Zero Commons Fund application, this is the only
fully source-bound EU regulatory profile in the catalogue. The grant produces
three additional EU public-rule profiles (NIS2 Article 23, GDPR Article 33,
EUDR Due Diligence Statement preparation) and a smaller commons-native
profile set (software release, standards engagement, plus one civic or
public-sector profile).
