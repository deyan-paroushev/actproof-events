# actproof-events 1.7.0 release notes

## Release purpose

`actproof-events` 1.7.0 is the first profile-view export and validation release.

The release makes the rich DORA profile-view JSON a first-class package output instead of a website-only script artifact. The canonical object remains the catalogue entry; the exported JSON is the reusable public projection for websites, APIs, MCP servers, audit packs and compliance interfaces.

## Main additions

- Added `actproof_events.exports.build_profile_view(...)`.
- Added `actproof_events.exports.write_profile_view(...)`.
- Added package-native coverage metrics via `compute_profile_coverage(...)`.
- Added CLI command:

```bash
actproof-events export-profile-view \
  op:eu.dora.ict_incident_notification_initial.v1 \
  --out dora.profile-view.json \
  --validate
```

- Added JSON Schema: `spec/schemas/profile_view.v1.schema.json`.
- Added public schema accessor: `actproof_events.get_profile_view_schema_path()`.
- Added validation helpers:
  - `get_profile_view_schema()`
  - `validate_profile_view(view)`
- Added CLI `--validate` flag.
- Added profile-view export documentation: `docs/PROFILE_VIEW_EXPORT.md`.

## Hash model

The 1.7.0 exporter uses two explicit hashes:

- `profile_semantic_hash`: version-independent reproducibility hash for the profile projection semantics. It excludes all profile hash fields, hash-basis fields and the `provenance` block.
- `profile_artifact_hash`: release-specific artifact hash. It excludes all profile hash fields and `provenance.generated_at`, but retains `provenance.package_version`.

`profile_view_hash` remains as a backward-compatible alias for `profile_semantic_hash`.

For the generated DORA profile-view JSON in this release:

```text
profile_semantic_hash: sha256:5a08a83ce7194da26a8f707509f1cda7c6cc5585ee726258ecb42cc2cd2f0651
profile_artifact_hash: sha256:cd03968bf621cfb85264832fe1a56c41baee494044111d5ae85e1a8bb64d93a3
```

## Verification performed before handoff

- `python -m pytest -q`: 74 passed.
- `python scripts/validate_catalogue.py --strict`: PASS, 7/7 entries.
- Source checkout CLI smoke test with `--validate`: PASS.
- DORA profile-view JSON regenerated with package version `1.7.0`.
- ActProof site copy of `assets/data/dora.profile-view.json` regenerated from the package exporter.

## Known note

`python scripts/validate_vectors.py` requires the optional `jcs` package for RFC 8785 canonicalization. It was not available in the current offline execution environment, so that optional gate was not rerun here.
