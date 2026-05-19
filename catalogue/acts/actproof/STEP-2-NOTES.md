# Step 2: catalogue entry for op:actproof.standards_engagement_record.v1

This delivery adds one new file to the actproof-events repository.

## File

- `catalogue/acts/actproof/standards_engagement_record.v1.json`

## What it does

Defines a new act type for open-source maintainer engagement with any
standards-developing organisation working group (IETF, W3C, OASIS, ISO,
NIST, IEEE, etc.). The catalogue entry itself is deliberately generic.
Body-specific facts (e.g., IETF, SCITT WG, the specific drafts) live in
each issued manifest, not in this catalogue entry.

## Standards verification done before drafting

Per the legal-precision requirement, every external reference was
verified at source rather than assumed from prior memory:

- **SCITT architecture**: confirmed as `draft-ietf-scitt-architecture-22`
  (10 October 2025), authors H. Birkholz / A. Delignat-Lavaud / C. Fournet /
  Y. Deshpande / S. Lasker, intended Standards Track, currently in
  AUTH48*R state in cluster C557 in the RFC editor publication queue.
  **It is not yet an RFC.** Memory entries referring to "RFC 9943" are
  inaccurate as of today's date; the draft form should be used in manifests
  and the cover letter until the RFC editor publishes.
- **draft-fassbender-scitt-time-anchor-01**: confirmed (J. Fassbender,
  Umarise; 27 April 2026; expires 29 October 2026; Informational; Bitcoin
  via OpenTimestamps as external temporal anchor; references SCITT
  architecture).
- **draft-hillier-scitt-arp-00**: confirmed (J. Hillier; 1 May 2026;
  expires 2 November 2026; Attestation Reconciliation Protocol;
  cross-sovereign claim reconciliation; references SCITT architecture).
- **IETF SCITT WG**: confirmed active at
  https://datatracker.ietf.org/wg/scitt/ , mailing list scitt@ietf.org ,
  community page https://scitt.io/community .
- **RFC 8785 (JSON Canonicalization Scheme)**: confirmed published.
- **RFC 3161 (Time-Stamp Protocol)**: confirmed long-published.

## Schema validation that was run

The entry was validated against the actproof.act_catalogue_entry.v3 JSON
Schema using the `jsonschema` library (Draft 2020-12). Eleven
additional loader-contract checks were also performed:

1. JSON Schema validation: PASSED
2. act_type_id matches required regex `^op:[a-z0-9_]+(\.[a-z0-9_]+)+\.v[0-9]+$`: PASSED
3. test_vector_reference ends in .json: PASSED
4. test_vector_reference path consistent with entry path: PASSED
5. claim_type snake_case 3-64 chars: PASSED (27 chars)
6. All claim and evidence field names snake_case: PASSED
7. supersedes is null (first version): PASSED
8. disclosure_profile.private_fields is empty (v1.4-rc1 constraint): PASSED
9. default_context_type ∈ allowed_context_types: PASSED
10. Disclosure tiers (public / commitment / private) are disjoint: PASSED
11. back_propagation_scope keys all declared as prior_receipts roles: PASSED

After dropping the file in and rebuilding the wheel:

- 5 authoritative entries (was 4)
- Enumeration via `actproof_events.list_catalogue_entries()` confirmed
  the new entry surfaces cleanly with the canonical act_type_id
  `op:actproof.standards_engagement_record.v1`.

## Design notes

**Generic, not SCITT-specific.** The catalogue entry covers any
standards-engagement act. Each manifest fills `standards_body_name`
(e.g., "IETF", "W3C"), `working_group_identifier` (e.g., "scitt",
"credentials"), and the specific `related_specifications` list. This
makes the entry usable beyond the STS application (any future
standards-engagement attestation can use the same entry).

**Non-claims explicit per the "must not say compliant" rule.** The
`reliance_context.reliance_statement` enumerates what the receipt does
NOT prove: admission to the working group, acceptance of a contribution,
completion of standards work, technical-merit evaluation, endorsement by
the standards-developing organisation, or any obligation by chairs or
area directors. Working group membership and contribution acceptance
are explicitly named as determined exclusively by the standards body's
own published processes.

**signature_policy supports OSS-flavoured artifacts.** `gpg_signed_release`,
`sigstore_cosign_signature`, and `internal_attestation_record` are the
externally-produced signature labels the entry recognises alongside the
platform-recorded issuer_record. eIDAS-grade external signatures
(QES/AES) are not in the supports list since they do not match how
open-source maintainers normally sign engagement records.

**v3 disclosure_profile with everything public.** The whole point of
a standards engagement record is to be publicly verifiable. All claim
fields, plus `manifest.title` and `manifest.issuer.legal_name`, are in
`public_fields`. `commitment_fields` and `private_fields` are empty.

## Commit suggestion

    git add catalogue/acts/actproof/standards_engagement_record.v1.json
    git commit -m "catalogue: add op:actproof.standards_engagement_record.v1

    Generic act type for open-source maintainer engagement with a named
    standards-developing organisation working group (IETF, W3C, OASIS,
    ISO, NIST, IEEE, etc.). Body-specific facts live in each issued
    manifest, not in this catalogue entry. Non-claims explicit per the
    legal precision rule. Validated against actproof.act_catalogue_entry.v3
    schema plus eleven loader-contract checks."

## Next step

Step 3: companion CC0 test vectors at
`catalogue/acts/actproof/standards_engagement_record.v1.test_vectors.json`,
following the shape and field conventions of the existing
software_release.v1.test_vectors.json. Test vectors use computed hashes
(not synthetic placeholders) per the schema requirement that
"test vectors MUST use computed hashes (not synthetic placeholders)
so verifier implementations can reproduce them."
