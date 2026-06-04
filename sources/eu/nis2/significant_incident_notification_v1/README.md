# NIS2 source bundle for ActProof Events

This folder contains the official source artefacts used to build and verify
the source bindings for the profile:

    op:eu.nis2.significant_incident_early_warning.v1

The profile maps the NIS2 significant-incident early warning under
Directive (EU) 2022/2555, Article 23(4)(a), together with the implementing
regulation used for the significant-incident thresholds that gate the
obligation.

This bundle is not legal advice and does not claim that any receipt proves NIS2
compliance. It exists so reviewers and independent implementers can reproduce
the source hashes used by the ActProof Events profile.

## A note on scope and the lex specialis carve-out

Financial entities within the scope of Regulation (EU) 2022/2554 (DORA) are
outside this profile's issuer scope. By the lex specialis rule recognised in
Directive (EU) 2022/2555, DORA major ICT-related incident reporting applies to
those entities instead of NIS2 Article 23. This profile therefore applies to
essential and important entities other than financial entities, including
non-financial-entity members of a banking group and shared service providers
whose incident may also bear on a financial-entity group member's separate DORA
obligation. The DORA and NIS2 profiles are built as a comparative pair for the
evidence-layer complexity study, not as a claim that a single entity files both.

## A note on operative divergence

NIS2 is a Directive. Unlike DORA, it has no harmonised EU-level early-warning
field template (there is no NIS2 equivalent of DORA's Implementing Regulation
(EU) 2025/302 Annex forms). The operative early-warning form is the national
CSIRT portal of the Member State of establishment, set by national
transposition. This profile binds to the EU instruments and records the
national reporting form as the locus of operative divergence. Where a national
form adds, renames, or retypes fields relative to this source-bound profile,
that difference is operative divergence in the sense defined by the framework.

## Files in this folder

- `README.md` (this file): explains what the bundle is and how to verify it.
- `source-bindings.json`: machine-readable record of which CELEX source, which
  article, and which SHA-256 each binding entry pins. Browsable on GitHub
  without download.
- `nis2-sources.zip`: the full source corpus, containing the two official PDFs
  and a copy of `source-bindings.json` for self-contained verification.
  (Generated locally by `cellar_fetch_nis2.py`; the `build/` directory is
  gitignored, so the zip is not committed. Re-run the fetcher to reproduce it.)

## Sources included in the bundle

Two official NIS2-family source artefacts, identified by CELEX number.

- CELEX 32022L2555, Directive (EU) 2022/2555. NIS 2 Directive. The primary
  legal act. The profile is source-bound to Article 23.
  sha256: 20d29e9c5300ae1095530996f04731311bf82bb7d4d6a7a0102cd0f075755cf3

- CELEX 32024R2690, Commission Implementing Regulation (EU) 2024/2690.
  Technical and methodological requirements and the exhaustive specification
  of the cases in which an incident is significant for Article 23(3). The
  profile is source-bound to Articles 3 and 4 (the horizontal significance
  criteria and the recurring-incident rule); Articles 5 to 14 carry the
  entity-type-specific significance cases and are conditional source dispersion
  applying only to the digital-infrastructure entity types the Regulation
  enumerates.
  sha256: 8799b1a7c352060c4f155ddc56241b0b2679e2204645361b134bbda3199d7199

## Bundle layout (inside nis2-sources.zip)

    nis2-sources/
      artefacts/
        32022L2555.pdf          (NIS 2 Directive)
        32024R2690.pdf          (Implementing 2024/2690, significance thresholds)
      source-bindings.json

## How to verify

1. Re-run the fetcher in an environment with open outbound network:

       ./run-cellar-fetch-nis2.sh

2. Compare the SHA-256 values it prints against the two hashes above and
   against `source-bindings.json`. A published Official Journal PDF is fixed,
   so a later re-run reproduces the same hash. A mismatch is a signal to check
   whether the instrument was amended, not a tool failure.
