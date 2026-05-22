# ActProof Events Schema Versioning Policy

**Version**: v1.5-rc1
**Status**: Pre-release candidate
**License**: Spec text is CC0. Schemas and test vectors are Apache-2.0.
**Maintainer**: actproof-events project

---

## Abstract

This document governs how the ActProof Events catalogue entry schema changes over time. It defines which changes may be made within a schema version, which changes require a new schema version, and how the exact bytes of every published schema state are preserved so that a verifier can reproduce any historical schema hash.

---

## 1. Introduction

### 1.1 Scope

This policy governs the JSON Schema files under `spec/schemas/` that describe catalogue entries, currently `act_catalogue_entry.v2.json` and `act_catalogue_entry.v3.json`. It does not govern the manifest schema, the receipt envelope, or the on-chain note format, which are specified in `spec/actproof-events.spec.md`.

### 1.2 Normative language

The key words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are used as defined in RFC 2119 and RFC 8174, and apply only when in capitals.

### 1.3 Two distinct kinds of version

Two unrelated things are called a version in this substrate, and they MUST NOT be conflated.

The **entry schema version** is the version of the JSON Schema that describes a catalogue entry. It appears as the `vN` segment of the schema file name (`act_catalogue_entry.v3.json`), as the schema `$id`, and as the discriminator at `properties.schema.const` (`actproof.act_catalogue_entry.v3`). This policy governs the entry schema version.

The **catalogue entry version** is the integer `version` field on an individual entry, also encoded as the `.vN` suffix of its `act_type_id`, for example `op:eu.dora.ict_incident_notification_initial.v1`. It is the version of one act type's definition and is incremented when that act type's content changes. It is governed by `CONTRIBUTING_ACTS.md`, not by this policy.

The two are orthogonal. A single entry schema version describes entries at many different entry versions. The same act type at entry version 2 is still described by, for example, the v3 entry schema.

---

## 2. Why schema bytes are preserved

The reference loader computes a schema hash over the raw bytes of the entry schema file. The loaded catalogue carries that schema hash, and catalogue binding records it so that a receipt is bound to the exact schema state under which it was issued.

A verifier reproducing a receipt's proof trail must obtain the exact schema bytes that produced the recorded schema hash. Any change to a schema file's bytes produces a different hash, including a change that is strictly additive and rejects no previously valid entry. Reformatting alone, with no semantic change, also changes the bytes and the hash.

It follows that every byte-state a published schema file has ever had must be preserved verbatim. Section 5 defines where and how. This requirement applies to additive within-version changes just as much as to new versions.

---

## 3. Changes permitted within a schema version

A change MAY be made to a schema file in place, keeping the same version, if and only if every catalogue entry that was valid under the prior byte-state of that schema remains valid under the new byte-state. Such a change is additive and backward compatible.

Changes that satisfy this test include:

- Adding a value to an existing closed `enum`.
- Adding a new optional property, that is a property not listed in `required`.
- Adding or clarifying a `description`, `title`, or `$comment`.
- Relaxing a constraint in a way that rejects nothing previously valid, such as raising a `maxLength` or widening a `pattern` by alternation.

For a within-version change the schema `$id` and the `properties.schema.const` discriminator MUST NOT change, and the version segment of the file name MUST NOT change.

The v1.5-rc1 reconciliation of the v3 entry schema is the worked example. It added the context type `regulatory_filing`, the submission stage `reclassification_to_non_major`, and the signature label `external_qes_artifact` to existing enums, and it added the optional blocks `non_claims` and `submission_evidence_policy`. Every entry valid under the prior v3 byte-state remained valid. The change was therefore correctly made in place, as v3, with no new version.

The `validate-catalogue` CI gate confirms in practice that the catalogue still conforms after the change. A reviewer MUST additionally reason that no entry shape valid before the change is rejected after it, since the gate checks only the entries that currently exist.

---

## 4. Changes that require a new schema version

A change MUST be made as a new schema version if it could reject any entry that was valid before, or if it changes the meaning of an existing field. Such a change is breaking.

Breaking changes include:

- Removing or renaming a property.
- Making an optional property required.
- Removing a value from an `enum`.
- Tightening a constraint, such as lowering a `maxLength`, raising a `minLength`, or narrowing a `pattern`.
- Changing the type of a property.
- Changing the meaning of an existing field while leaving its shape unchanged.

A new version is published as a new schema file, `act_catalogue_entry.v<N+1>.json`, with a new `$id` and a new discriminator, `actproof.act_catalogue_entry.v<N+1>`. The prior schema file is retained in `spec/schemas/` unchanged. The loader continues to accept the prior version, exactly as it accepts v2 entries today alongside v3. Entries migrate to the new version one at a time, by changing their discriminator and conforming to the new schema. There is no flag day and no bulk rewrite.

Because a new version is a new file and leaves the prior file's bytes untouched, it does not by itself trigger the archival described in Section 5. The prior schema file remains live.

---

## 5. The schema archive

### 5.1 The archive directory

Superseded byte-states of a schema file are kept under `spec/schemas/archive/`. The currently live schema files remain directly under `spec/schemas/`. A within-version change, per Section 3, supersedes the live file's byte-state, and the superseded bytes are moved to the archive before the live file is edited.

### 5.2 Revision tags and file names

Every published byte-state of a schema file is assigned a sequential revision tag `rN`, starting at `r1` for the first published state. The live `spec/schemas/<name>.json` always holds the highest revision. Each superseded state is stored as `spec/schemas/archive/<name>.r<N>.json`, for example `spec/schemas/archive/act_catalogue_entry.v3.r1.json`.

An archived copy MUST be byte-exact. It MUST NOT be reformatted, re-indented, or re-serialised. The hash of the archived file MUST equal the schema hash recorded by receipts issued under that state.

### 5.3 The archive index

`spec/schemas/archive/index.md` records every byte-state of every schema file, archived and live. Each row carries the schema discriminator, the revision tag, the SHA-256 of the bytes, the date the state took effect, the date it was superseded (blank for the live state), and a one-line summary of the change that produced it. The recommended form is a table:

| Discriminator | Revision | SHA-256 | Effective | Superseded | Change |
| --- | --- | --- | --- | --- | --- |
| actproof.act_catalogue_entry.v3 | r1 | sha256:... | YYYY-MM-DD | YYYY-MM-DD | first published v3 schema |
| actproof.act_catalogue_entry.v3 | r2 | sha256:... | YYYY-MM-DD |  | v1.5-rc1 reconciliation, added regulatory_filing and others |

### 5.4 Resolving a historical schema hash

A verifier holding a schema hash from a receipt's catalogue binding finds the matching row in the archive index, retrieves the named bytes from `spec/schemas/archive/` if the state is superseded or from `spec/schemas/` if it is live, and confirms the hash. A schema hash that appears in no index row cannot be bound to any known schema state, which is itself a verification finding.

---

## 6. Change process

### 6.1 An additive within-version change

1. Confirm the change is additive by the test in Section 3.
2. Copy the current live schema file, byte-exact, to `spec/schemas/archive/<name>.r<N>.json`, where `rN` is the next revision tag.
3. Record the archived state in `spec/schemas/archive/index.md`, setting its superseded date.
4. Edit the live schema file in place.
5. Record the new live state in the index as the next revision, with no superseded date.
6. If a controlled vocabulary changed, update `spec/vocabularies.md`.
7. If loader-visible behaviour changed, review `CATALOGUE_LOADER_CONTRACT.md`.
8. The `validate-catalogue` CI gate confirms the catalogue still conforms.

### 6.2 A new-version change

1. Leave every existing schema file unchanged.
2. Add `spec/schemas/act_catalogue_entry.v<N+1>.json` with the new `$id` and discriminator.
3. Add the new discriminator to the loader's accepted set. In actproof-py this is `SCHEMA_DISCRIMINATORS` in `actproof/catalogue.py`.
4. Update `CATALOGUE_LOADER_CONTRACT.md` to cover the new version.
5. Record the new schema file's first byte-state in the archive index as `r1` for that schema.
6. Migrate entries to the new version individually, as authoring effort allows.

---

## 7. Relationship to other documents

This policy works alongside `spec/vocabularies.md`, which governs the controlled vocabularies whose enumerated values are widened by additive within-version changes; `CATALOGUE_LOADER_CONTRACT.md`, which specifies how a conforming loader consumes the schema; and `CONTRIBUTING_ACTS.md`, which governs the catalogue entry `version` field described in Section 1.3. This policy is itself versioned with the ActProof Events specification and takes effect at v1.5-rc1.
