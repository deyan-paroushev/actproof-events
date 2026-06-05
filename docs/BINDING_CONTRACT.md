# Profile binding contract

This document defines how a relying party checks that a receipt binds to an
ActProof catalogue entry, and the one rule an implementer needs to get the field
names right. It is written for an outside consumer: nothing here depends on
trusting this project.

## What a binding check is, and is not

`check_profile_binding` answers one mechanical question: does the catalogue entry
hash carried by a supplied receipt, manifest, or profile descriptor equal the
hash of the catalogue entry bytes available locally. It returns a three-state
`status`:

- `bound`: a hash was supplied and equals the local raw-file-bytes hash.
  `binding_match: true`.
- `recognized_unbound`: the `act_type_id` is known but no catalogue entry hash
  was supplied, so the exact bytes were not bound. `binding_match: null`.
- `mismatch`: a hash was supplied and did not match. `binding_match: false`.

Plus `unknown_profile` (act not in the catalogue) and `invalid_input` (no
`act_type_id`). Every result carries `verification_grade: false`: a binding check
is not full receipt verification. It does not check the manifest hash, the
timestamp, the anchor, the signature, or the issuer. Those belong to the
substrate (the `actproof` package).

## The field-name rule (the one thing to get right)

Inside a `catalogue` object the keys are `entry_hash` and `entry_version`. The
parent already names the object, so the unprefixed form is correct and is what
the substrate mints:

```json
{
  "manifest": {
    "catalogue": {
      "act_type_id": "op:eu.dora.ict_incident_notification_initial.v1",
      "entry_hash": "sha256:<64 hex>",
      "entry_version": 2
    }
  }
}
```

The prefixed `catalogue_entry_hash` / `catalogue_entry_version` form is used only
in flat contexts that have no `catalogue.` parent, namely a top-level `profile`
descriptor block or a bare top level. A bare top-level `entry_hash` with no
`catalogue` parent is not accepted: `entry_hash` is meaningful only when its
parent names it.

## Where the hash is read, in order

The check reads the supplied hash from the first location present:

1. `manifest.catalogue.entry_hash`        canonical, covered by `manifest_hash`
2. `raw_manifest.catalogue.entry_hash`    canonical (test vectors key the manifest this way)
3. `catalogue.entry_hash`                 canonical, a manifest supplied bare
4. `profile.catalogue_entry_hash`         transitional, outside the manifest
5. top-level `catalogue_entry_hash`       transitional, outside the manifest

The result records which in `supplied_entry_hash_location`, and sets
`transitional_descriptor: true` for the flat locations (4 and 5), which are not
covered by `manifest_hash` and are therefore a weaker binding. Inside the
canonical `catalogue` objects the prefixed `catalogue_entry_hash` is tolerated as
an alias so an early adopter who emitted the stutter name still binds, but
`entry_hash` is the canonical key and is what the location label reports.

## Hash semantics

`entry_hash` is `sha256:` followed by the SHA-256 of the exact raw catalogue
entry JSON file bytes as shipped. No parsing, reserialisation, key sorting,
newline or Unicode normalisation, and no pretty-printing participate. An
implementation computes the identical value from the same bytes, which is why the
substrate and a relying party agree without coordination. The basis string is
`sha256(raw catalogue entry JSON file bytes)`.

A given `entry_version` maps to exactly one `entry_hash`. Changing the catalogue
entry bytes (for example adding stable `source_binding_id` values to the source
bindings) is a new revision: bump `entry_version` and the hash moves with it. The
previous version and its hash remain valid for anything pinned to that version.
