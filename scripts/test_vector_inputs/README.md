# Test vector inputs

This directory contains the raw manifest inputs used by `scripts/compute_test_vectors.py` to generate the test vector files under `catalogue/acts/`.

Each input file is a complete, production-shape `actproof.attestation_manifest.v1` document. It contains no documentation or annotation fields. The file is canonicalized byte-for-byte by the test vector generator. Any change to an input file changes the corresponding manifest hash in the test vector.

## Evidence fixtures

Evidence SHA-256 hashes in the input manifests are computed from deterministic UTF-8 byte strings, so any verifier implementation can reproduce them independently. The fixtures are:

| Evidence label | Fixture content (exact bytes, including trailing newline) | SHA-256 |
| --- | --- | --- |
| `signed_resolution_or_minutes` (NIS2) | `OpenProof Events test fixture: NIS2 Article 20 board resolution v1\n` | `e70e000faf7b5f745d460da46e9a12f4d051eb7e3315af8130e2c2a864d0bcbc` |
| `risk_management_measures_document` (NIS2) | `OpenProof Events test fixture: NIS2 Article 21 risk management measures document v1\n` | `9be63853a94ac3bcdc0993b4bee4d4bc87b800b343ea3c5a570cc1b9117defaa` |
| `geojson_plot_geometries` (EUDR) | `OpenProof Events test fixture: EUDR GeoJSON plot geometries v1\n` | `42d181cc68e5b949ba042fbc0d28a976f65ca64687aa16fc79ce5a06ada0bc4e` |
| `due_diligence_screening_report` (EUDR) | `OpenProof Events test fixture: EUDR due diligence screening report v1\n` | `11d539105027416569ffddd27c42b74dcf6de18472818e347bd51c1e3cfda131` |

Reproducibility check (Python):

```python
import hashlib
hashlib.sha256(b"OpenProof Events test fixture: NIS2 Article 20 board resolution v1\n").hexdigest()
# expected: e70e000faf7b5f745d460da46e9a12f4d051eb7e3315af8130e2c2a864d0bcbc
```

## Regenerating test vectors

Run from the repository root:

```bash
python scripts/compute_test_vectors.py \
    catalogue/acts/eu/nis2/art20/management_body_approval.v1.json \
    scripts/test_vector_inputs/nis2_art20_v1_001.json \
    catalogue/acts/eu/nis2/art20/management_body_approval.v1.test_vectors.json

python scripts/compute_test_vectors.py \
    catalogue/acts/eu/eudr/dds_preparation.v1.json \
    scripts/test_vector_inputs/eudr_dds_v1_001.json \
    catalogue/acts/eu/eudr/dds_preparation.v1.test_vectors.json
```

Re-running with unchanged inputs produces byte-identical test vector files. If the test vector file hash changes on a re-run, the generator script is non-deterministic and the bug should be fixed before any release.

## Conformance check for verifier implementations

A verifier implementation conforms to this substrate if, given any of these input manifests, it produces the `manifest_hash_hex`, `envelope_hash_hex`, and `arc2_note.full_note_b64` values recorded in the corresponding test vector file. Once the `reference_anchor.txid` is populated with a real Algorand testnet anchor, the verifier must additionally fetch the on-chain note and confirm byte-identical match against `arc2_note.full_note_b64`.
