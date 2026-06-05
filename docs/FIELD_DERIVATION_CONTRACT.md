# Field derivation contract

Status: stable for actproof-events 1.5.x. This document freezes how the package
states the provenance of a field's source basis. The source basis is field-level
for any field the Mapper has derived, and act-level otherwise. The flip is per
field: one field of an act can be field-level while its siblings are still
act-level, and the response says which, rather than implying field specificity
it does not have. Evidence labels remain profile-level for now (see the last
section).

## The flags

Three flags carry the provenance. `source_basis_scope` and `fallback_used` now
vary per field; `evidence_scope` is still fixed.

- `source_basis_scope`: `"field"` when the field carries a Mapper-derived source
  basis, otherwise `"act"`. At `"act"` the returned instruments are the act's
  source bindings, the same set for every act-level field. At `"field"` they are
  the specific fragments behind that field.
- `fallback_used`: `false` when the field-level derivation was used, `true` when
  the package fell back to the act-level bindings because no derivation exists
  for that field yet.
- `evidence_scope`: `"profile"`. The required evidence labels returned for a
  field are the profile's required evidence labels, the same set for every field.
  Narrowing evidence labels to the field is a later step.

The fallback scope constant lives in services as `SOURCE_BASIS_SCOPE = "act"`;
the field-level scope is the literal `"field"`. `EVIDENCE_SCOPE = "profile"`.

## The field-level source-basis entry

When a field is derived, each entry in its `source_basis` list has this shape:

```json
{
  "source_binding_id": "sb_dora_art19_1",
  "celex": "32022R2554",
  "locator": { "article": "19", "paragraph": "1", "point": null },
  "fragment_hash": "sha256:...",
  "mapping_type": "modelled",
  "review_status": "reviewed",
  "rationale": "Maps to the initial-notification trigger in Art 19(1).",
  "mapper_extraction_version": "actproof-mapper-extract.v1"
}
```

- `source_binding_id`: stable id of the source binding the fragment belongs to.
  This must match one of the profile's `source_bindings[].source_binding_id`
  values; a derivation may not reference a binding the profile does not contain.
- `celex`: CELEX identifier of the instrument.
- `locator`: object identifying the precise place in the instrument. It must
  carry at least one non-empty component from `article`, `paragraph`, `point`,
  `subpoint`, `annex`, `recital`, `table`, `row`, `field`. Other keys are
  allowed, but an empty object (or one whose only values are null or empty) is
  rejected.
- `fragment_hash`: must match `sha256:<64 lowercase hex chars>`. The basis is
  sha256 over the exact UTF-8 bytes of the Mapper's extracted source-fragment
  string after the Mapper's own extraction-normalisation step. That normalisation
  is versioned by `mapper_extraction_version`, so two Mapper versions cannot hash
  the same legal text differently over whitespace, hyphenation, footnotes or
  PDF-extraction quirks. The Mapper owns this hash; the package consumes it and
  does not recompute it, the same division as the manifest hash with actproof-py.
- `mapper_extraction_version`: optional in C2, reserved in the contract. A string
  naming the Mapper's extraction-normalisation version (for example
  `actproof-mapper-extract.v1`). It will become required once real rows exist, so
  a fragment hash is always interpretable against a known normalisation.
- `mapping_type`: one of `direct`, `normalised`, `transformed`, `reconciled`,
  `modelled`. This is the mapping of this one fragment, per fragment, and is
  distinct from the field's assessment-level `interpretive_load` in
  EVIDENCE_LAYER_RUBRIC.md (a field may draw on several fragments).
- `review_status`: one of `proposed`, `reviewed`, `affirmed`, `disputed`. Records
  where human authority stands on the AI-proposed interpretation link. AI may
  propose a link; a human holds final authority, so `proposed` is not the same as
  `affirmed`.
- `rationale`: short human-readable reason for the mapping.

The act-level fallback entry has a different shape (`instrument`, `authority`,
`provisions`, `celex`, `eli`, `sha256`); read `source_basis_scope` to know which
shape you are looking at.

The Mapper output is validated at load. A malformed entry (missing key, wrong
type, a `fragment_hash` that is not a `sha256:` digest, a `mapping_type` or
`review_status` outside the frozen vocabulary, a non-object `locator`) raises
rather than being silently accepted, so a bad mapping cannot quietly ship.

## Where each flag appears

- The field row (`list_fields`, and `GET /v1/profiles/{act_id}/fields`) carries
  `evidence_scope`. It does not carry `source_basis_scope` or `fallback_used`,
  because a row does not return source bindings.
- The grounding answer (`get_field`, and `GET /v1/profiles/{act_id}/fields/{field_id}/source`)
  carries all three flags alongside the `source_basis` list.
- The MCP tool `get_source_basis` returns `source_basis` with
  `source_basis_scope` and `fallback_used`, and validates the field id, so it
  never returns basis for a field that does not exist.

## Data location and rollout

Field-level derivations ship in `analysis/field_derivations.json`, keyed
`act_type_id -> field_id -> [entry, ...]`, bundled into the wheel under
`actproof_events/data/analysis/`. The file ships empty, so every field falls back
to the act-level basis until the Mapper populates it. Populating it and calling
`store.rebuild()` switches derived fields to field-level with no code change; the
store builds grounded fields through the same `source_basis_view`.

Reference integrity is enforced at store build by `check_derivation_references`.
The shipped DORA and NIS2 profiles now carry stable `source_binding_id` values
(C2.1), so the check is live: a derivation that references a binding the profile
does not contain fails the build. A profile that exposes no ids (the pre-C2.1
shape) is skipped, so a profile that has not yet been given ids never blocks a
read. The catalogue-byte change that added the ids was taken together with the
C1 manifest work, so `catalogue_entry_hash` moved once and the entry `version`
was bumped to 2.

## What this contract does not claim

An act-level `source_basis` does not assert that the listed instrument is the
single provision that produced that exact field; it asserts the act-level
bindings the field sits under, labelled `act` so the distinction is explicit. A
field-level `source_basis` does make the narrower claim, fragment by fragment,
and exposes the `review_status` so the strength of that claim is visible rather
than assumed. Evidence labels remain profile-level and are labelled `profile`.
