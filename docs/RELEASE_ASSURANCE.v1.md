# ActProof release assurance v1

`actproof-events 2.3.0` adds local release-assurance artifacts for bank and enterprise deployment review.

The release assurance pack contains:

- `sbom.cyclonedx.json` — a minimal CycloneDX SBOM for the package and optional extras.
- `artifact-hashes.json` — SHA-256 hashes for source/package artifacts.
- `signing-intent.json` — the artifacts and attestations that should be signed or verified by PyPI/GitHub/bank release controls.
- `profile-lock.json` — the pinned ActProof profile hash and package version.
- `governance-status.json` — reviewed profile governance status.
- `source-atom-coverage.json` — missingness/coverage signal.
- `completeness.json` — explicit known-scope and non-exhaustiveness statement.
- `INTERNAL_MIRROR_GUIDE.md` — instructions for bank/internal package mirroring.
- `SHA256SUMS.csv` — simple hash table for pack files.

## Boundary

The pack supports internal review, mirroring, verification and change-control. It is not a legal opinion, not a compliance certification, not a vulnerability scan, and not a generated private-key signature.

Banks should store the pack in internal change records and apply their own signing, attestation and approval process.
