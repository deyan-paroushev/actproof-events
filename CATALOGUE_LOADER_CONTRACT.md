# Catalogue loader contract

This document is the binding contract between the ActProof Events substrate and any implementation that loads catalogue entries from the substrate's filesystem layout. An implementation that satisfies this contract is a conforming catalogue loader for v1.5-rc1 of the specification.

The contract is implementation-agnostic. The reference implementation is the actproof-py library, at `actproof/catalogue.py`. Implementations in other languages, such as Go, Rust, or TypeScript, MUST satisfy the same contract to be considered conforming. A consuming application, such as Quoruna, uses a conforming loader rather than reimplementing one.

## Scope

This document covers:

- How a loader discovers and reads catalogue entries from the filesystem
- Which entry schema versions a loader accepts
- How a loader validates each entry against its JSON Schema
- How a loader validates a candidate manifest against a catalogue entry
- How the optional v3 blocks are preserved and exposed
- How a consuming application caches and reloads the loaded catalogue
- How a loader reports errors

This document does NOT cover:

- The transport layer between the loader and any UI or API surface
- The persistence layer for issued attestations
- The signing or anchoring pipeline, which is downstream of the loader
- The semantics of the controlled vocabularies, which are governed by `spec/vocabularies.md`
- Any internal database schema choices in a consuming application

## Terminology

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, and OPTIONAL are interpreted per RFC 2119 and RFC 8174.

**Catalogue entry** is a JSON document conforming to `actproof.act_profile.v2` or `actproof.act_profile.v3`. v3 is the current entry schema and a strict additive superset of v2.

**v3 entry** is a catalogue entry whose `schema` field is `"actproof.act_profile.v3"`. **v2 entry** is one whose `schema` field is `"actproof.act_profile.v2"`.

**v1 entry** is a JSON document under a `_deprecated/` directory using the predecessor voting-shaped schema. v1 entries are not loaded. See Section 1.4.

**Manifest** is a candidate attestation manifest document, defined in the specification.

**New issuance** means the loader is being asked to surface or accept an act_type_id for the purpose of creating a new attestation.

**The load** is the act of discovering, validating, and indexing every catalogue entry. The reference loader performs the load through a single `load_catalogue` call that returns an immutable catalogue snapshot.

## 1. Loading requirements

### 1.1 Entry schemas the loader accepts

A conforming loader MUST accept entries carrying either the `actproof.act_profile.v2` or the `actproof.act_profile.v3` discriminator. Both are valid for new issuance.

v3 is the current entry schema and the schema under which new entries SHOULD be authored. Because v3 is a strict additive superset of v2, a v2 entry is a valid, if less rich, act type. A v2 entry carries none of the optional v3 blocks described in Section 3, so a consumer treats its claim fields with the default field type. See Section 3.2.

A JSON file under `catalogue/acts/` whose `schema` value is a string beginning with `actproof.act_profile.` but is neither of the two recognised discriminators MUST be treated as an error, per Section 5.1, not silently skipped. This catches a typo'd or wrong-version discriminator on a file that is clearly intended to be a catalogue entry.

### 1.2 Path discovery

A conforming loader MUST discover catalogue entries by recursively walking the `catalogue/acts/` directory tree. The discovery rules are:

- Files ending in `.json` are candidate catalogue entries.
- Files ending in `.test_vectors.json` are NOT catalogue entries and MUST be ignored.
- Files under any `_deprecated/` subdirectory are v1 entries and MUST be skipped. See Section 1.4.
- A `.json` file that is not a JSON object, or that has no `schema` field, or whose `schema` value does not look like a catalogue entry discriminator, is not a catalogue entry and MUST be ignored. This permits non-entry JSON files to coexist in the tree.
- `README.md` and other non-JSON files MUST be ignored.

The schema files used for validation, described in Section 1.3, live under `spec/schemas/`, as siblings of `catalogue/`, not under `catalogue/acts/`.

### 1.3 Schema validation is mandatory

A conforming loader MUST validate every discovered catalogue entry against the JSON Schema for its declared discriminator: `spec/schemas/act_profile.v3.json` for a v3 entry and `spec/schemas/act_profile.v2.json` for a v2 entry.

A catalogue entry that does not conform to its schema MUST cause the load to fail. The loader MUST NOT silently skip a non-conforming entry, and MUST NOT return a catalogue in which some entries were validated and others were not. The reference loader raises `CatalogueLoadError` and returns no catalogue at all when any entry fails validation.

This is the default behaviour. The reference loader exposes an explicit opt-out, the `validate_schema=False` argument to `load_catalogue`, for development use and for environments that do not ship the schema files or the validation library. The opt-out MUST be an explicit, non-default choice. A loader MUST NOT default to skipping schema validation.

The rationale is that the substrate's value depends on every loader rejecting the same non-conforming entries. A loader that surfaced a non-conforming entry would let issuers create attestations the substrate cannot describe. The actproof-events repository additionally runs a conformance gate, `scripts/validate_catalogue.py`, invoked by the `validate-catalogue` workflow, so that a non-conforming entry cannot be merged in the first place. The loader's load-time validation is the defence in depth at the point of consumption.

A loader MUST also fail the load if two entries share an `act_type_id`. A duplicate `act_type_id` makes resolution ambiguous and MUST be treated as a load failure, not a last-writer-wins merge.

### 1.4 v1 deprecated entries are not loaded

Entries under any `_deprecated/` directory use the predecessor voting-shaped v1 schema. A conforming loader MUST skip them. They do not appear in the loaded catalogue, they cannot be resolved through the loader, and new issuance against a v1 act_type_id is therefore impossible by construction. A request to resolve a v1 act_type_id resolves as not found, per Section 5.1.

Rendering historical receipts that reference a v1 act_type_id is outside the scope of this contract. It is a concern of the consuming application and of the self-contained provenance carried by the receipt itself. A loader MAY scan `_deprecated/` for the sole purpose of returning a more specific deprecated-entry error instead of a generic not-found error, but it MUST NOT load v1 entries as usable catalogue entries.

## 2. Manifest validation requirements

When a candidate manifest is submitted for transition to the `awaiting_commit` state, the loader MUST perform the following validations against the corresponding catalogue entry. Failure of any validation MUST block the transition and return a structured error, per Section 5.

These validations apply identically to v2 and v3 entries. They concern the fifteen v2 wire-schema fields, which v3 leaves unchanged.

### 2.1 act_type_id match

The manifest's `act_type_id` MUST exactly match the catalogue entry's `act_type_id`, compared case-sensitively.

### 2.2 catalogue_entry_version match

The manifest's `catalogue_entry_version` MUST exactly match the catalogue entry's `version`. A mismatch indicates the manifest was created against a different version of the entry. The consuming application MUST either re-validate against the current version or surface the mismatch as a structured error.

### 2.3 required_claim_fields presence

For every identifier in the entry's `required_claim_fields`, the manifest's claim fields MUST contain that key with a value that is not null, not an empty string, and not an empty array. The loader MUST report each missing required field individually, so the issuer can correct every gap in one revision cycle.

### 2.4 required_evidence_labels coverage

For every identifier in the entry's `required_evidence_labels`, the manifest's `evidence` array MUST contain at least one item whose `label` equals that identifier and whose hash value is non-null. The loader MUST report each missing label individually.

### 2.5 Recipient validation

Every recipient's `role` SHOULD match an identifier in the entry's `recommended_witness_roles`. A recipient with a non-recommended role MAY be permitted, but the loader MUST flag it as non-standard in a warning the consuming application surfaces to the issuer. The loader MUST report a syntactically invalid recipient email address as a structured error, and MUST report two recipients sharing the same `(role, email)` pair as a structured error.

### 2.6 signature_policy compatibility

If the entry's `signature_policy.minimum` is `external_signature`, the manifest MUST include at least one evidence item whose label appears in the entry's `signature_policy.supports` list. A manifest carrying only issuer-record-equivalent evidence MUST block the transition. If `signature_policy.minimum` is `issuer_record` or `either`, the loader MUST permit the transition without external signature evidence.

## 3. Optional v3 blocks

v3 adds six optional blocks to a catalogue entry: `regulated_context_profile`, `prior_receipts_profile`, `reliance_context`, `disclosure_profile`, `submission_evidence_policy`, and `claim_field_types`. A conforming loader MUST preserve and expose every optional block that is present on an entry. A loader MUST NOT drop a block it does not itself interpret, because a consuming application or a later loader version may rely on it.

The semantics of the controlled vocabularies used by these blocks are governed by `spec/vocabularies.md`.

### 3.1 Non-validating blocks

`regulated_context_profile`, `prior_receipts_profile`, `reliance_context`, and `disclosure_profile` describe receipt context, lifecycle, reliance, and disclosure semantics. They are entry metadata. A loader MUST expose them to consumers. `reliance_context.non_claims`, where present, enumerates the inferences a verifier must not draw from a receipt. A consuming application SHOULD render it on receipts and verification surfaces.

### 3.2 claim_field_types

`claim_field_types` maps each claim field identifier to its primitive data type. A consuming application uses it to render the input control, parse the submitted value, and serialise the manifest with no hardcoded per-act-type knowledge. A loader MUST expose `claim_field_types` where present. A consumer that encounters a claim field absent from the map, or an entry that declares no map at all, such as any v2 entry, MUST treat that field as type `string`.

### 3.3 submission_evidence_policy

`submission_evidence_policy` declares whether submission or transmission evidence is required for the act type and which evidence labels it recognises. A loader MUST expose the block where present. A loader MAY additionally validate a candidate manifest against it: where `submission_evidence_policy.required` is `true`, a conforming manifest is expected to carry at least one recognised submission evidence artifact. Manifest validation against `submission_evidence_policy` is not yet a requirement of this contract. A loader that does not perform it is still conforming.

## 4. Catalogue lifecycle in a consuming application

The reference loader's `load_catalogue` is a stateless function. It reads the catalogue from disk and returns an immutable snapshot. Caching that snapshot, and reloading it, is the responsibility of the consuming application.

### 4.1 Load at startup

A consuming application MUST perform the load once at process startup and hold the resulting snapshot in memory. After startup, no catalogue entry SHALL be read from the filesystem on the path of a request.

### 4.2 Explicit, operator-initiated reload

A consuming application that supports reloading the catalogue without a process restart MUST trigger the reload only by an explicit operator signal: a POSIX signal, an authenticated admin endpoint, or a scheduled restart point. It MUST NOT reload based on file modification time, filesystem watch events, or any other implicit trigger.

### 4.3 Atomic swap

A reload MUST be atomic with respect to concurrent reads. A request in flight when a reload begins MUST observe either the pre-reload snapshot or the post-reload snapshot in its entirety, never a mixed state. The immutable-snapshot model of the reference loader makes this straightforward: build the new snapshot fully, then swap the active reference in one step.

### 4.4 Reload failure preserves the prior snapshot

If a reload fails, for example because a newly added entry fails schema validation, the consuming application MUST retain the previous snapshot and surface the failure as a structured error. A failed reload MUST NOT leave the application with no catalogue or a partial one.

## 5. Error reporting

A loader MUST report errors as structured objects, not opaque strings. The recommended structure is:

```
{
  "error_type": "REQUIRED_CLAIM_FIELD_MISSING",
  "field_path": "claim.approving_body_name",
  "act_type_id": "op:eu.nis2.art20.management_body_approval.v1",
  "catalogue_entry_version": 1,
  "human_message": "The required claim field 'approving_body_name' is missing from the manifest."
}
```

Each structured error MUST include `error_type`, an identifier from the taxonomy in Section 5.1, and `human_message`, a human-readable explanation suitable for display to the issuer. Each error SHOULD include, where applicable, a `field_path`, the `act_type_id` and `catalogue_entry_version` for context, `expected` and `actual` values for a mismatch, and `valid_options` listing the permissible values.

### 5.1 Error taxonomy

A conforming loader MUST recognise and report the following error types:

- `CATALOGUE_ENTRY_NOT_FOUND`: the requested act_type_id matches no loaded entry.
- `CATALOGUE_ENTRY_SCHEMA_INVALID`: a catalogue entry on disk fails schema validation. This stops the load, per Section 1.3.
- `CATALOGUE_DUPLICATE_ACT_TYPE_ID`: two entries share an act_type_id. This stops the load, per Section 1.3.
- `CATALOGUE_ENTRY_VERSION_MISMATCH`: the manifest's catalogue_entry_version does not match the entry's version.
- `REQUIRED_CLAIM_FIELD_MISSING`: a required claim field is absent or empty.
- `REQUIRED_EVIDENCE_LABEL_MISSING`: no evidence item carries a required label.
- `RECIPIENT_ROLE_NOT_RECOMMENDED`: a recipient's role is not in recommended_witness_roles. This is a warning unless the consuming application enforces a strict mode.
- `RECIPIENT_EMAIL_INVALID`: a recipient email is malformed.
- `RECIPIENT_DUPLICATE_DESIGNATION`: two recipients share the same (role, email) pair.
- `SIGNATURE_POLICY_VIOLATED`: the entry requires an external signature but the manifest provides none.

A loader MAY additionally report `CATALOGUE_ENTRY_DEPRECATED` when it can determine that a requested act_type_id corresponds to a v1 entry under `_deprecated/`, in order to give a more specific error than `CATALOGUE_ENTRY_NOT_FOUND`. This is OPTIONAL, per Section 1.4.

## 6. Concurrency

A loader's read operations, resolving an entry and validating a manifest, MUST be safe for concurrent invocation. The reference loader achieves this by returning an immutable snapshot: once returned, a snapshot is never mutated. A consuming application achieves concurrency-safe reload by the atomic reference swap of Section 4.3.

## 7. Reference interface

The reference implementation, actproof-py, exposes the surface below. Type signatures are written in Python-flavoured pseudocode. Equivalent signatures in other languages are conforming, and a loader in another language MAY use different names and idioms, provided the obligations of Sections 1 through 6 are met.

```python
def load_catalogue(
    acts_path: Path | None = None,
    *,
    schema_path: Path | None = None,
    source_uri: str | None = None,
    git_commit: str | None = None,
    validate_schema: bool = True,
) -> Catalogue:
    """
    Discover, validate, and index every catalogue entry, and return an
    immutable Catalogue snapshot. validate_schema defaults to True; see
    Section 1.3. Raises CatalogueLoadError on a non-conforming entry, on
    a duplicate act_type_id, or on a missing schema or validation library.
    """

class Catalogue:
    """
    An immutable snapshot. Holds every loaded entry indexed by
    act_type_id, the source paths, and the schema hash used for catalogue
    binding. Resolving an act_type_id returns its CatalogueEntry or
    signals CATALOGUE_ENTRY_NOT_FOUND.
    """

class CatalogueEntry:
    """
    One catalogue entry: the fifteen v2 wire-schema fields, two derived
    fields, and the optional v3 fields, including claim_field_types,
    populated where the entry declares them and otherwise None.
    """

def validate_manifest(
    manifest: dict,
    entry: CatalogueEntry,
) -> list[ValidationIssue]:
    """
    Validate a candidate manifest against a catalogue entry, per
    Section 2. Returns a list of structured issues; an empty list means
    the manifest may transition to awaiting_commit.
    """
```

A consuming application performs the load once and caches the `Catalogue`, per Section 4. It reloads by calling `load_catalogue` again and swapping the cached reference.

## 8. Conformance test scenarios

A conforming loader MUST pass at least the following scenarios.

**Scenario A, successful load.** Given a catalogue directory of well-formed v3 entries and the v3 schema file, the load succeeds and every entry is resolvable by its act_type_id.

**Scenario B, non-conforming entry stops the load.** Given a catalogue directory where one entry does not conform to its schema, the load fails with a `CATALOGUE_ENTRY_SCHEMA_INVALID` error and returns no catalogue. No entry is surfaced.

**Scenario C, duplicate act_type_id stops the load.** Given two entries sharing an act_type_id, the load fails with a `CATALOGUE_DUPLICATE_ACT_TYPE_ID` error.

**Scenario D, deprecated entries are skipped.** Given a `_deprecated/` directory alongside the active entries, no v1 entry appears in the loaded catalogue, and resolving a v1 act_type_id signals not found.

**Scenario E, missing required claim field.** Given a manifest that omits a required claim field, `validate_manifest` returns a single `REQUIRED_CLAIM_FIELD_MISSING` issue identifying that field.

**Scenario F, missing required evidence label.** Given a manifest that omits a required evidence label, `validate_manifest` returns a `REQUIRED_EVIDENCE_LABEL_MISSING` issue for the missing label.

**Scenario G, duplicate recipient.** Given a manifest with two recipients sharing a `(role, email)` pair, `validate_manifest` returns a `RECIPIENT_DUPLICATE_DESIGNATION` issue.

**Scenario H, non-recommended role warning.** Given a manifest with a recipient whose role is not in `recommended_witness_roles`, `validate_manifest` returns a `RECIPIENT_ROLE_NOT_RECOMMENDED` warning, and the transition is permitted.

**Scenario I, claim_field_types exposure.** Given a v3 entry that declares `claim_field_types`, the loaded entry exposes the map. Given a v2 entry, or a claim field absent from the map, a consumer treats the field as type `string`.

**Scenario J, reload preserves the prior snapshot on failure.** After a successful initial load, a reload in which a catalogue file has been corrupted fails atomically. The prior snapshot remains active and the failure is reported as a structured error.

**Scenario K, no filesystem read on the issuance path.** After the initial load, resolving any cached act_type_id triggers no filesystem read.

## 9. Versioning

This contract is bound to v1.5-rc1 of the ActProof Events specification, the release that introduces the v3 entry schema. A substrate change that affects the loader contract, such as a new entry schema version, a new validation requirement, or a new error type, will be accompanied by a new version of this contract. An implementation conforming to one contract version is not automatically conforming to another. Each substrate release MUST be reviewed against its corresponding contract.

---

*This contract is licensed CC0. Any implementation may incorporate or paraphrase this text without attribution.*
