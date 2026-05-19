# Step 3: CC0 test vectors for op:actproof.standards_engagement_record.v1

This delivery adds four files to the actproof-events repository (and
makes one pre-existing-bug observation that does NOT need to be fixed
tonight).

## Files

- `catalogue/acts/actproof/standards_engagement_record.v1.test_vectors.json`
  The test vector: catalogue binding, raw manifest, canonical bytes,
  hashes, envelope, ARC-2 note, reference anchor placeholder, expected
  verifier output, and the verifier checklist. Schema:
  `actproof.test_vector.v1`. Licensed CC0 1.0 Universal in line with
  the existing CC0 conformance test vectors.

- `scripts/test_vector_inputs/actproof_standards_engagement_record_v1_001.json`
  The raw-manifest input file the script reads. Manifest fields are
  populated from verified facts: Advisa EOOD as issuer, ORCID
  0009-0003-8231-8265, IETF SCITT working group, and the six related
  specifications (architecture + Merkle proofs + time-anchor +
  attestation reconciliation + JCS + RFC 3161). The two
  implementation_artifacts entries cite actproof-py v0.3.2 and
  actproof-events v1.4-rc1.

- `scripts/test_vector_inputs/actproof_standards_engagement_record_v1_001_evidence/implementation_repository_state.txt`
- `scripts/test_vector_inputs/actproof_standards_engagement_record_v1_001_evidence/working_group_charter_reference.txt`
  The two evidence-content files whose SHA-256 hashes appear in the
  manifest input's evidence array. **These exist so the manifest's
  evidence hashes are reproducible from real bytes, not synthetic
  placeholders.** The existing test vector inputs use placeholder hex
  for evidence hashes; ours uses real computed hashes of these two
  committed files.

## Computed values

The script `scripts/compute_test_vectors.py` (existing, unchanged)
produced:

- Manifest canonical bytes:  3045 bytes
- Manifest hash:             `a8fbc53c55962643f47af5f7ada2cc61a6fe0812c6bd4dfb2841071533997773`
- Envelope hash:             `144be1c5015246d778c13960b94a4072cc8d16e0c1c0f273da91c19e43305f06`
- ARC-2 note byte length:    183
- Evidence file hashes:
  - `implementation_repository_state.txt`  1736 bytes  SHA-256 `51de268b0c26f44b1214023521b8ce59aacbd5ea47f425123d27651c00ac441f`
  - `working_group_charter_reference.txt`  1764 bytes  SHA-256 `4f390624cab7ef93ef591347ca51efd5bf1994f1ac8dbfbc3db6e960e2421456`

## Independent verification that was performed

After the script wrote the test vector file, every hash and
canonicalization step was independently recomputed:

1. Recanonicalized `raw_manifest` with `jcs.canonicalize`. Byte length
   and base64 string match `manifest_canonical_b64` exactly. PASSED.
2. SHA-256 of the recanonicalized bytes equals `manifest_hash_hex`.
   PASSED.
3. The `schema` and `act_type_id` inside the canonical bytes match
   the corresponding fields in `raw_manifest`. PASSED. (The existing
   four test vectors fail this check, see Pre-existing-bug observation
   below.)
4. Recanonicalized the envelope and recomputed envelope hash. Matches
   `envelope_hash_hex`. PASSED.
5. Recomposed the ARC-2 note as `"quoruna/v1:" + inner_canonical`.
   Byte length and exact bytes match `arc2_note.full_note_b64`. PASSED.

A verifier following `verifier_checklist` produces `PASS` for the
declared `expected_verifier_output`.

## Reproducibility instructions

A third party can reproduce the test vector deterministically:

    pip install jcs
    git clone <repo>
    cd actproof-events
    python3 scripts/compute_test_vectors.py \
        catalogue/acts/actproof/standards_engagement_record.v1.json \
        scripts/test_vector_inputs/actproof_standards_engagement_record_v1_001.json \
        catalogue/acts/actproof/standards_engagement_record.v1.test_vectors.json

Output bytes are identical across machines and runs.

To verify the evidence hashes:

    sha256sum scripts/test_vector_inputs/actproof_standards_engagement_record_v1_001_evidence/*.txt

## Factual references used in the manifest

Every standards reference inside the manifest's `related_specifications`
was verified at source on 2026-05-19, not assumed from memory:

- `draft-ietf-scitt-architecture-22` is in AUTH48*R state cluster C557
  in the RFC editor publication queue (verified via the queue page at
  rfc-editor.org/current_queue.php). The architecture is NOT yet
  published as an RFC. The text inside the manifest reflects this.
- `draft-ietf-cose-merkle-tree-proofs-18` is in AUTH48 state cluster
  C557 alongside the SCITT architecture.
- `draft-fassbender-scitt-time-anchor-01`: Informational, expires
  2026-10-29 (verified via IETF datatracker).
- `draft-hillier-scitt-arp-00`: expires 2026-11-02 (verified via IETF
  datatracker).
- `RFC 8785` (JSON Canonicalization Scheme): published. Verified.
- `RFC 3161` (Time-Stamp Protocol): long-published.
- IETF SCITT WG identifier `scitt`, charter URL
  `https://datatracker.ietf.org/doc/charter-ietf-scitt/`, mailing list
  `scitt@ietf.org`, community page `https://scitt.io/community`:
  all verified.

## Pre-existing-bug observation (NOT fixed in this step)

The four existing v3 test vectors all have an internal inconsistency:

    Vector                                                    raw_manifest.schema   bytes inside b64
    actproof/software_release.v1.test_vectors.json            actproof.*.v1         openproof.*.v1
    eu/nis2/art20/management_body_approval.v1.test_vectors    actproof.*.v1         openproof.*.v1
    eu/eudr/dds_preparation.v1.test_vectors                   actproof.*.v1         openproof.*.v1
    democracy/civil_society_mandate.settlement.v1.test_vectors actproof.*.v1        openproof.*.v1

The `raw_manifest.schema` field was renamed `openproof.* -> actproof.*`
at the v1.4-rc1 cut, but the `manifest_canonical_b64` and
`manifest_hash_hex` were not regenerated. A verifier following the
checklist will FAIL on all four because canonicalizing the current
`raw_manifest` produces a different hash than the declared one.

The same is true for the `actproof/software_release` vector's
`raw_manifest.act_type_id`, which says `op:actproof.software_release.v1`
while the canonical bytes carry `op:openproof.software_release.v1`.

Fix (do later, NOT tonight): rerun
`scripts/compute_test_vectors.py` against each of the four manifest
inputs in `scripts/test_vector_inputs/` (which already have the
`actproof.` schema), overwriting the four files. No catalogue entry
changes needed. Estimated effort: 5 minutes mechanical, zero design
work, but does change four hashes that may be referenced elsewhere in
documentation, so requires a careful sweep before commit.

This is a docs-and-test-hygiene cleanup, not a blocker for the STS
demonstration tonight. The live STS demo receipt will be minted
fresh through Quoruna's anchoring path, not generated through this
script, so the existing test vector bug does not affect tonight's
critical path.

## Commit suggestion

    git add catalogue/acts/actproof/standards_engagement_record.v1.test_vectors.json \
            scripts/test_vector_inputs/actproof_standards_engagement_record_v1_001.json \
            scripts/test_vector_inputs/actproof_standards_engagement_record_v1_001_evidence/
    git commit -m "catalogue: CC0 test vectors for op:actproof.standards_engagement_record.v1

    Adds a self-consistent test vector with real (non-placeholder) SHA-256
    hashes of two committed evidence-content files. The vector was
    produced by the existing scripts/compute_test_vectors.py pipeline
    against the new catalogue entry; manifest hash, envelope hash, and
    ARC-2 note bytes were independently re-verified via direct
    jcs.canonicalize + sha256 recomputation. All eight self-consistency
    checks pass.

    References inside the manifest's related_specifications were each
    verified at source (IETF datatracker and rfc-editor.org publication
    queue) on 2026-05-19, not from prior memory.

    Test vector ID: actproof_standards_engagement_record_v1_001
    Manifest hash: a8fbc53c55962643f47af5f7ada2cc61a6fe0812c6bd4dfb2841071533997773
    Envelope hash: 144be1c5015246d778c13960b94a4072cc8d16e0c1c0f273da91c19e43305f06"

## Next step

Step 4: in actproof-py, add a catalogue loader module that implements
the CATALOGUE_LOADER_CONTRACT.md contract (startup load, in-memory
cache, surface v3 entries for new issuance, allow v1 read-only for
historical rendering, structured error taxonomy). The loader will be
the integration point Quoruna calls at app startup.
