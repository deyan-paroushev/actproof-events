# Catalogue loader contract

This document is the binding contract between the OpenProof Events substrate and any implementation that loads catalogue entries from the substrate's filesystem layout. Implementations that satisfy this contract are conforming catalogue loaders for v1.4 of the specification.

The contract is intentionally implementation-agnostic. The reference implementation in Quoruna is written in Python and lives at `catalogue_loader.py` in the Quoruna repository. Future implementations in other languages (Go, Rust, TypeScript) MUST satisfy the same contract to be considered conforming.

## Scope

This document covers:

- How a loader reads catalogue entries from the filesystem
- How a loader distinguishes v2 entries from deprecated v1 entries
- How a loader validates a candidate manifest against a catalogue entry
- How a loader caches and reloads catalogue entries
- How a loader reports errors

This document does NOT cover:

- The transport layer between the loader and any UI or API surface
- The persistence layer for issued attestations (that lives in the consuming implementation)
- The signing or anchoring pipeline (that is downstream of the loader)
- Any internal database schema choices

## Terminology

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, and OPTIONAL are interpreted per RFC 2119.

**Catalogue entry** refers to a JSON document conforming to `openproof.act_catalogue_entry.v2` (defined in spec Section 2.1).

**v1 entry** refers to a JSON document under any `_deprecated/` directory that uses the predecessor voting-shaped schema.

**Manifest** refers to a candidate `openproof.attestation_manifest.v1` document (defined in spec Section 3).

**New issuance** means the loader is being asked to surface or accept an act_type_id for the purpose of creating a new attestation.

**Historical rendering** means the loader is being asked to resolve an act_type_id that was issued previously, in order to render a receipt or verification page for an existing attestation.

## 1. Loading requirements

### 1.1 Surfacing v2 entries

The loader MUST surface only v2 entries for new issuance. A v2 entry is one whose `schema` field equals the literal string `"openproof.act_catalogue_entry.v2"`.

The loader MUST validate each loaded entry against the JSON Schema at `spec/schemas/act_catalogue_entry.v2.json`. Entries that fail schema validation MUST NOT be surfaced for new issuance and SHOULD be logged at warning level for operator attention.

### 1.2 Refusing v1 entries for new issuance

The loader MUST refuse to surface entries from any `_deprecated/` directory for new issuance. Specifically:

- Any catalogue file whose path contains a `_deprecated/` segment MUST NOT appear in the list of available act types for new attestation creation.
- Any attempt to begin a new attestation against a v1 act_type_id (e.g., `op:eu.nis2.art20.approval`) MUST be rejected with a clear error message indicating the v1 entry has been superseded.

### 1.3 Allowing v1 read-only access for historical rendering

The loader MUST allow read-only access to v1 entries when resolving an act_type_id that was used in a previously committed attestation. This requirement preserves the namespace and ensures that historical receipts continue to render correctly.

The loader SHOULD distinguish at the API boundary between "list act types for new issuance" (returns only v2 entries) and "resolve act type for historical rendering" (returns v2 and v1 entries). Reference implementations expose two distinct functions for this purpose; see Section 6.

### 1.4 Path discovery

The loader MUST discover catalogue entries by walking the `catalogue/` directory tree. The discovery rules are:

- Files ending in `.json` are candidate catalogue entries.
- Files under a `_deprecated/` subdirectory are v1 entries (read-only, historical access only).
- Files under any other path are v2 entries (subject to v2 schema validation).
- Files ending in `.test_vectors.json` are NOT catalogue entries and MUST be ignored by the loader.
- `README.md` files and other non-JSON files MUST be ignored.

The loader MUST treat the `catalogue/` directory as the root. Catalogue entries deeper in the tree (under `catalogue/acts/eu/nis2/art20/` etc.) are discovered recursively.

## 2. Validation requirements

When a candidate manifest is submitted for transition to `awaiting_commit` state, the loader MUST perform the following validations against the corresponding catalogue entry. Failure of any validation MUST block the transition and return a structured error.

### 2.1 act_type_id match

The manifest's `act_type_id` MUST exactly match the catalogue entry's `act_type_id`. Case-sensitive comparison.

### 2.2 catalogue_entry_version match

The manifest's `catalogue_entry_version` MUST exactly match the catalogue entry's `version`. Mismatches indicate the manifest was created against a different version of the catalogue entry; the consuming implementation MUST either re-validate against the current version or surface the version mismatch as a structured error.

### 2.3 required_claim_fields presence

For every identifier in the catalogue entry's `required_claim_fields`, the manifest's `claim_fields` object MUST contain a key with the same identifier. The value of the key MUST NOT be null, empty string, or empty array.

The loader MUST report each missing required field individually, not as a single aggregate error, so the issuer can correct all gaps in a single revision cycle.

### 2.4 required_evidence_labels coverage

For every identifier in the catalogue entry's `required_evidence_labels`, the manifest's `evidence` array MUST contain at least one item whose `label` equals that identifier. The corresponding evidence item MUST have a non-null `sha256_hex` value.

The loader MUST report each missing required evidence label individually.

### 2.5 Recipient role validation

For every recipient in the manifest's `recipients` array, the recipient's `role` SHOULD match an identifier in the catalogue entry's `recommended_witness_roles`. Recipients with non-recommended roles MAY be permitted but the loader MUST flag them as non-standard in a warning that the consuming implementation surfaces to the issuer.

The loader MUST validate that every recipient has a syntactically valid email address in the `email` field. Invalid email addresses MUST be reported as structured errors.

The loader MUST validate that no two recipients share the same `(role, email)` pair. Duplicate designations MUST be reported as structured errors.

### 2.6 signature_policy compatibility

If the catalogue entry's `signature_policy.minimum` is `external_signature`, the manifest MUST include at least one evidence item whose label appears in the catalogue entry's `signature_policy.supports` list. If the manifest contains only `issuer_record`-equivalent evidence, the loader MUST block the transition.

If the catalogue entry's `signature_policy.minimum` is `issuer_record` or `either`, the loader MUST permit transition without external signature evidence (the platform-recorded commit action satisfies the floor).

## 3. Caching requirements

### 3.1 Startup load

The loader MUST load and cache all catalogue entries in memory at process startup. After successful startup, no catalogue entry SHALL be read from the filesystem on the path of a request.

### 3.2 Explicit reload

The loader MUST support an explicit reload operation triggered by an operator signal. Acceptable signal mechanisms include:

- A POSIX signal (e.g., `SIGHUP`) handled by the process
- An admin HTTP endpoint that triggers an in-process reload
- A scheduled reload at known process restart points (e.g., daily deploy)

The loader MUST NOT reload catalogue entries based on file modification time, inotify events, or any other implicit trigger. All reloads MUST be operator-initiated.

### 3.3 Atomicity

The reload operation MUST be atomic with respect to concurrent reads. A consuming request that is mid-flight when reload begins MUST observe either the pre-reload catalogue or the post-reload catalogue in its entirety, never a mixed state.

The reference implementation accomplishes this by computing the new catalogue cache fully in a temporary structure, then atomically swapping the active cache pointer.

### 3.4 Reload failure handling

If reload fails (e.g., a newly added catalogue entry fails schema validation), the loader MUST retain the previous valid cache and surface the failure as a structured error. A failed reload MUST NOT leave the loader in an unloaded or partially-loaded state.

## 4. Error reporting

The loader MUST report validation errors as structured objects, not as opaque strings. The recommended structure is:

```
{
  "error_type": "REQUIRED_CLAIM_FIELD_MISSING",
  "field_path": "claim_fields.approving_body_name",
  "act_type_id": "op:eu.nis2.art20.management_body_approval.v1",
  "catalogue_entry_version": 1,
  "human_message": "The required claim field 'approving_body_name' is missing from the manifest."
}
```

Each structured error MUST include:

- `error_type`: an enumerated identifier from the error taxonomy in Section 4.1
- `human_message`: a human-readable explanation suitable for display to the issuer

Each structured error SHOULD include where applicable:

- `field_path`: a JSON pointer-like path identifying the offending field
- `act_type_id` and `catalogue_entry_version` for context
- `expected` and `actual` values for mismatches
- `valid_options` listing the permissible values when applicable

### 4.1 Error taxonomy

The loader MUST recognise and report the following error types:

- `CATALOGUE_ENTRY_NOT_FOUND`: requested act_type_id does not match any loaded entry
- `CATALOGUE_ENTRY_DEPRECATED`: requested act_type_id is a v1 entry; new issuance refused
- `CATALOGUE_ENTRY_VERSION_MISMATCH`: manifest's catalogue_entry_version does not match catalogue
- `REQUIRED_CLAIM_FIELD_MISSING`: a required claim field is absent or empty
- `REQUIRED_EVIDENCE_LABEL_MISSING`: no evidence item carries a required label
- `RECIPIENT_ROLE_NOT_RECOMMENDED`: a recipient's role is not in recommended_witness_roles (warning, not error, unless implementation enforces strict mode)
- `RECIPIENT_EMAIL_INVALID`: a recipient's email is malformed
- `RECIPIENT_DUPLICATE_DESIGNATION`: two recipients share the same (role, email) pair
- `SIGNATURE_POLICY_VIOLATED`: catalogue requires external signature but manifest provides none
- `CATALOGUE_ENTRY_SCHEMA_INVALID`: a catalogue entry on disk fails v2 schema validation (operator-facing error at startup or reload)

## 5. Concurrency

The loader's read operations (resolve catalogue entry, validate manifest) MUST be safe for concurrent invocation. Implementations MAY achieve concurrency safety by treating the cached catalogue as immutable after each reload and using atomic pointer swap for updates.

The loader's reload operation SHOULD be safe to invoke concurrently with read operations as described in Section 3.3. The loader MAY serialize concurrent reload calls to prevent redundant work.

## 6. Recommended interface

Reference implementations are RECOMMENDED to expose at least the following operations. Type signatures are written in Python-flavoured pseudocode for clarity; equivalent signatures in other languages are conforming.

```python
class CatalogueLoader:
    def load_all(self, catalogue_root: Path) -> None:
        """
        Discover and cache all catalogue entries. Called at process startup
        and on explicit reload signal.
        """

    def list_act_types_for_issuance(self) -> list[ActTypeDescriptor]:
        """
        Return the list of v2 act types currently available for new
        attestation creation. v1 entries are excluded.
        """

    def resolve_for_issuance(self, act_type_id: str) -> CatalogueEntry:
        """
        Return the v2 catalogue entry matching act_type_id. Raises
        CatalogueEntryNotFound if no match exists, or CatalogueEntryDeprecated
        if the match is a v1 entry.
        """

    def resolve_for_history(self, act_type_id: str) -> CatalogueEntry:
        """
        Return the catalogue entry matching act_type_id, including v1 entries.
        Used for rendering receipts of attestations issued before the v2
        migration.
        """

    def validate_manifest(
        self,
        manifest: dict,
        catalogue_entry: CatalogueEntry,
    ) -> list[ValidationError]:
        """
        Validate a candidate manifest against a catalogue entry. Returns a
        list of structured errors; empty list means the manifest is valid
        for transition to awaiting_commit.
        """

    def reload(self) -> ReloadResult:
        """
        Re-discover and re-cache all catalogue entries atomically. Returns
        a summary of what changed.
        """
```

Implementations MAY add additional operations beyond this minimum (e.g., bulk validation, partial reload, schema diff). Such extensions MUST NOT change the semantics of the operations above.

## 7. Test scenarios

A conforming loader implementation MUST pass at least the following test scenarios. The reference implementation in Quoruna includes these as integration tests under `tests/test_catalogue_loader.py` (added in Batch B).

### Scenario A: Successful v2 load

Given a clean catalogue directory containing `management_body_approval.v1.json` and `dds_preparation.v1.json`, the loader's `load_all` succeeds, `list_act_types_for_issuance` returns both entries, and `resolve_for_issuance` returns the correct entry for each act_type_id.

### Scenario B: v1 namespace preservation

Given a catalogue directory containing the v1 `_deprecated/approval.json` alongside the v2 `management_body_approval.v1.json`:

- `list_act_types_for_issuance` returns only the v2 entry.
- `resolve_for_issuance("op:eu.nis2.art20.approval")` raises CatalogueEntryDeprecated.
- `resolve_for_history("op:eu.nis2.art20.approval")` succeeds and returns the v1 entry.

### Scenario C: Missing required claim field

Given a manifest against `management_body_approval.v1` that omits `responsible_officers`, `validate_manifest` returns a single structured error of type `REQUIRED_CLAIM_FIELD_MISSING` with `field_path: "claim_fields.responsible_officers"`.

### Scenario D: Missing required evidence label

Given a manifest against `dds_preparation.v1` that includes only the `geojson_plot_geometries` evidence and omits `due_diligence_screening_report`, `validate_manifest` returns a `REQUIRED_EVIDENCE_LABEL_MISSING` error for the missing label.

### Scenario E: Duplicate recipient

Given a manifest with two recipients sharing the same `(role, email)`, `validate_manifest` returns a `RECIPIENT_DUPLICATE_DESIGNATION` error identifying both indices.

### Scenario F: Non-recommended role warning

Given a manifest with a recipient whose role is not in `recommended_witness_roles`, `validate_manifest` returns a warning (not an error) of type `RECIPIENT_ROLE_NOT_RECOMMENDED`. The transition to `awaiting_commit` is permitted but the consuming implementation MUST surface the warning to the issuer.

### Scenario G: Invalid catalogue entry on disk

Given a catalogue directory where one of the JSON files fails v2 schema validation, `load_all` succeeds for the valid entries, logs the failure at warning level, and `list_act_types_for_issuance` returns only the valid v2 entries. The invalid entry is NOT surfaced.

### Scenario H: Reload preserves prior cache on failure

After successful initial load, given a `reload` call where one of the catalogue files has been corrupted, the reload fails atomically. The loader's existing cache remains active and serving requests. The failure is reported as a structured error.

### Scenario I: No filesystem read on issuance path

A profiling test confirms that calling `resolve_for_issuance` for any cached act_type_id triggers zero filesystem reads after the initial `load_all` completes.

## 8. Reference implementation

The reference implementation lives in the Quoruna repository at `catalogue_loader.py`. It is implemented in Python with `asyncpg` for any database-side persistence concerns and `jsonschema` for v2 schema validation. The full implementation lands in Quoruna Batch B alongside the attestation schema and the issuer flow.

Future implementations in other languages may diverge in idioms, frameworks, and persistence choices, but MUST satisfy the contract documented here to be considered conforming.

## 9. Versioning

This contract is bound to v1.4 of the OpenProof Events specification. Substrate changes that affect the loader contract (new schema versions, new validation requirements, new error types) will be accompanied by a new version of this contract. Implementations that satisfy the v1.4 contract are NOT automatically conforming to future contract versions; each substrate release MUST be reviewed against the corresponding contract.

---

*This contract is licensed CC0. Any implementation may incorporate or paraphrase this text without attribution.*
