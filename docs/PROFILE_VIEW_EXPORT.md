# Profile-view export

`actproof-events` can generate a public, renderable JSON projection from a catalogue entry.

The catalogue entry remains the canonical profile object. The profile-view JSON is a generated projection intended for websites, APIs, MCP servers, audit packs and compliance interfaces.

## CLI

```bash
actproof-events export-profile-view \
  op:eu.dora.ict_incident_notification_initial.v1 \
  --out dora.profile-view.json \
  --validate
```

Compact output is also available:

```bash
actproof-events export-profile-view \
  op:eu.dora.ict_incident_notification_initial.v1 \
  --compact \
  --out dora.profile-view.json
```

## Python API

```python
from actproof_events import get_profile_view_schema_path
from actproof_events.exports import (
    build_profile_view,
    validate_profile_view,
    write_profile_view,
)

view = build_profile_view("op:eu.dora.ict_incident_notification_initial.v1")
validate_profile_view(view)

write_profile_view(
    "op:eu.dora.ict_incident_notification_initial.v1",
    "dora.profile-view.json",
    validate=True,
)

schema_path = get_profile_view_schema_path()
```

## What the projection contains

The exported JSON includes:

- profile identity and regulatory citation
- catalogue entry hash and hash basis
- semantic profile hash, artifact hash, and their hash bases
- package provenance and package version
- boundary and non-claims metadata
- required evidence labels
- source-basis instruments
- coverage metrics
- field rows with required/optional status, disclosure tier, mapping type, interpretive load, evidence labels, source-basis scope and fallback status

## Schema

The projection declares:

```json
{
  "profile_view_schema": "actproof.profile_view.v1"
}
```

The JSON Schema is shipped at:

```text
spec/schemas/profile_view.v1.schema.json
```

When installed as a wheel, the schema is bundled under `actproof_events/data/schemas/profile_view.v1.schema.json`. Consumers should prefer the accessor:

```python
from actproof_events import get_profile_view_schema_path

schema_path = get_profile_view_schema_path()
```

## Hash semantics

The profile-view export carries two hashes. Neither is a receipt hash and neither is a legal proof.

`profile_semantic_hash` is the version-independent reproducibility hash. It is calculated over canonical JSON with sorted keys and compact separators, excluding all profile hash fields, hash-basis fields and the `provenance` block. This lets the same profile projection keep the same semantic hash even when the package version or generation timestamp changes.

`profile_artifact_hash` is the release-specific artifact hash. It excludes all profile hash fields and `provenance.generated_at`, but retains `provenance.package_version`. This lets consumers distinguish the exact package release that generated the artifact.

`profile_view_hash` remains as a backward-compatible alias for `profile_semantic_hash`. New integrations should read `profile_semantic_hash` and `profile_artifact_hash` explicitly.

## Verification

Any profile-view artifact can be verified against what this release guarantees, using only the installed package:

```bash
actproof-events verify-profile-view dora.profile-view.json
```

or programmatically:

```python
from actproof_events.exports import verify_profile_view

report = verify_profile_view("dora.profile-view.json")
assert report["ok"]
```

The verifier recomputes both hashes from the artifact and compares them to the stored values, validates the artifact against the bundled `profile_view.v1` schema, and confirms the canonical catalogue entry hash is carried. It returns a structured report with `valid_schema`, `semantic_hash_matches`, `artifact_hash_matches`, `catalogue_entry_hash_present` and `ok`. Hard checks set `ok`; disclosed limitations are reported as warnings. In this release all DORA fields use act-level source fallback, so the verifier emits a coverage warning and reports `field_derivations_complete: false`; field-level source binding arrives in a later release.

## Boundary

A profile view is a projection of source-bound catalogue data. It does not certify legal compliance, does not provide legal advice and does not replace receipt verification by `actproof-py`.
