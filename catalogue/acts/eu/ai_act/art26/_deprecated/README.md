# Deprecated v1 catalogue entries

This directory contains catalogue entries from v1 of the OpenProof Events substrate, when the substrate modelled regulated acts as voting events. These entries are retained for namespace preservation only. They are not loaded by the current catalogue loader for new issuance.

## Why these were deprecated

v1 catalogue entries encoded fields that assumed regulated acts were voting tallies: `method_constraints`, `quorum_basis_points`, `threshold_basis_points`, `tally_output_hash`, `result_hash`. These fields did not describe the regulated acts themselves. They were artifacts of the substrate's earlier framing as a voting platform. v2 entries replace the v1 schema with act-native fields under `openproof.act_catalogue_entry.v2`.

## Migration map

| v1 act_type_id | v2 act_type_id | Status |
| --- | --- | --- |
| `op:eu.ai_act.art26.risk_assessment` | TBD | v2 successor planned for v1.5 |

A v2 successor for the AI Act Article 26 deployer risk assessment act type is planned for the v1.5 substrate release. The v2 entry will align with the AI Act's high-risk AI system deployer obligations under Regulation (EU) 2024/1689 with in-force date 2 August 2026.

## What this directory guarantees

Any party that issued attestations against `op:eu.ai_act.art26.risk_assessment` can still resolve their historical commitments. The v1 entry is read-only and remains valid as a reference for historical receipts. Catalogue loaders MUST allow read-only access to v1 entries for historical attestation rendering.

## What this directory does NOT permit

New issuance against `op:eu.ai_act.art26.risk_assessment` is rejected by the catalogue loader until a v2 successor is published.
