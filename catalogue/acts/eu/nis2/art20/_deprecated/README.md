# Deprecated v1 catalogue entries

This directory contains catalogue entries from v1 of the ActProof Events substrate, when the substrate modelled regulated acts as voting events. These entries are retained for namespace preservation only. They are not loaded by the current catalogue loader for new issuance.

## Why these were deprecated

v1 catalogue entries encoded fields that assumed regulated acts were voting tallies: `method_constraints`, `quorum_basis_points`, `threshold_basis_points`, `tally_output_hash`, `result_hash`. These fields did not describe the regulated acts themselves. They were artifacts of the substrate's earlier framing as a voting platform. v2 entries replace the v1 schema with act-native fields under `actproof.act_catalogue_entry.v2`.

## Migration map

| v1 act_type_id | v2 act_type_id | Status |
| --- | --- | --- |
| `op:eu.nis2.art20.approval` | `op:eu.nis2.art20.management_body_approval.v1` | Migrated |

## What this directory guarantees

Any party that issued attestations against a deprecated v1 act_type_id can still resolve their historical commitments. The v1 entries are read-only and remain valid as references for historical receipts. Catalogue loaders MUST allow read-only access to v1 entries for historical attestation rendering.

## What this directory does NOT permit

New issuance against v1 act_type_ids is rejected by the catalogue loader. Issuers MUST use the corresponding v2 entries listed in the migration map above.
