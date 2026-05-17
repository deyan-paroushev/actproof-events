# Deprecated v1 catalogue entries

This directory contains catalogue entries from v1 of the ActProof Events substrate, when the substrate modelled regulated acts as voting events. These entries are retained for namespace preservation only. They are not loaded by the current catalogue loader for new issuance.

## Why these were deprecated

v1 catalogue entries encoded fields that assumed regulated acts were voting tallies: `method_constraints`, `quorum_basis_points`, `threshold_basis_points`, `tally_output_hash`, `result_hash`. These fields did not describe the regulated acts themselves. They were artifacts of the substrate's earlier framing as a voting platform. v2 entries replace the v1 schema with act-native fields under `actproof.act_catalogue_entry.v2`.

## Migration map

| v1 act_type_id | v2 act_type_id | Status |
| --- | --- | --- |
| `op:corporate.board.resolution.v1` | TBD | v2 successor planned for v1.5 |

A v2 successor for the corporate board resolution act type is planned for the v1.5 substrate release. Issuers who require corporate board resolution attestations in the interim should either wait for the v1.5 v2 entry, or define a domain-specific entry under their organization's `x.<reverse-dns>:` namespace per the federation grammar in the specification.

## What this directory guarantees

Any party that issued attestations against `op:corporate.board.resolution.v1` can still resolve their historical commitments. The v1 entry is read-only and remains valid as a reference for historical receipts. Catalogue loaders MUST allow read-only access to v1 entries for historical attestation rendering.

## What this directory does NOT permit

New issuance against `op:corporate.board.resolution.v1` is rejected by the catalogue loader until a v2 successor is published.
