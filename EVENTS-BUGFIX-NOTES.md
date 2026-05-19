# Bugfix delivery for events Steps 1, 2, 3

Applies the "minimal patch" from ChatGPT's bug review of the May 19
sprint deliverables. Eight fixes across three step zips. Two further
items (8 and 10 in the review) are documentation roadmap and a
pre-existing test-vector hygiene issue respectively, both flagged
non-blocking for tonight's STS application and parked for post-STS.

## Map: bug to fix

| # | Bug | Fix landed in |
|---|-----|---------------|
| 1 | maintainer_legal_name = "Advisa EOOD" (should be the natural person) | Step 3 input + test vector. Parallel fix also lands in quoruna Step 6.2 (see separate bugfix zip). |
| 2 | Reliance statement claimed "commit references" but evidence has only versions and URLs | Step 2 entry: softened reliance_statement to "versions, repository URLs, and evidence references". |
| 3 | Non-claims buried in prose, not machine-readable | Step 2 entry: added `reliance_context.non_claims` array with 6 explicit non-claim identifiers. The prose reliance_statement remains, but the array is the authoritative enumeration. |
| 4 | No catalogue_entry_hash visible in test vector | Step 3 test vector: added top-level `profile` block carrying `act_type_id`, `catalogue_entry_version`, and `catalogue_entry_hash` (sha256:41fcb384...) with a basis explanation. |
| 5 | pyproject.toml had `rfc-9943` keyword (SCITT architecture is still draft-ietf-scitt-architecture-22) | Step 1 pyproject.toml: removed `rfc-9943`, added `ietf-scitt` and `cose-receipts`. |
| 6 | Test vector hardcoded `quoruna/v1:` as the ARC-2 prefix (application-specific in a generic vector) | Step 3 test vector: changed prefix to `actproof/v1:` and recomputed the full ARC-2 note. Added a `consumer_profile_note` explaining that downstream consumers may substitute. |
| 7 | `__init__.py` docstrings still said "v2 act-catalogue" while entries are v3 | Step 1 `__init__.py`: every v2 reference updated to v3 with historical-acknowledgement language. |
| 9 | related_specifications listed newer drafts (fassbender, hillier) ahead of core specs | Step 3 input + test vector. Parallel fix also lands in quoruna Step 6.2. New ordering: SCITT architecture, COSE Merkle Tree Proofs, RFC 8785, RFC 3161, then the two newer drafts as related implementation context. |

## What I deliberately did not change

- The `op:` namespace prefix. ChatGPT explicitly recommended keeping it stable; namespace governance is a post-STS conversation.
- Pre-existing test vectors with the `actproof.*` vs `openproof.*` schema mismatch (ChatGPT's bug 10). Non-blocking tonight, scheduled for post-STS hygiene.
- The "standards engagement record is too meta" framing (ChatGPT's bug 8). This is roadmap, not a code fix; the application-document work can show the next two regulatory profiles (DORA major ICT incident, EUDR DDS preparation) alongside this one.

## Hash changes propagated

Because the Step 2 entry changed (non_claims added, reliance softened) and the Step 3 manifest input changed (maintainer name, specs reordered), all derived values updated:

- **catalogue entry hash**: sha256:41fcb384eb34851002de34df80fbe5844ae8f6a83f4ace8cb4952eb047d01cf5 (was 4347cd71...)
- **manifest canonical bytes**: 3113 (was 3045)
- **manifest hash**: sha256:b2d67c1c0239f369cb3599e03d68cae5ae5c6c7ad5687e6df5d85ff7fabb723f (was a8fbc53c...)
- **envelope canonical bytes**: 317 (unchanged)
- **envelope hash**: sha256:1ca482b74c194f4965bc5a12a0e5d611231895b0893612496e71dd6d9fb91766 (was 144be1c5...)
- **ARC-2 full note byte length**: 184 (was 183; the `actproof/v1:` prefix is one byte longer than `quoruna/v1:`)

Evidence file hashes are byte-stable (the evidence file contents were not changed in this bugfix), so the two evidence labels' sha256_hex values remain `51de268b...` and `4f390624...` as before.

## Verified end to end

After applying these fixes, building the wheel, installing into a fresh venv, and running the Step 6.2 mint builder against the new catalogue:

- actproof.catalogue.load_catalogue loads the entry cleanly (no schema validation regression from the added non_claims field).
- The builder produces a valid manifest with maintainer "Deyan Paroushev", issuer "Advisa EOOD".
- manifest.catalogue.entry_hash auto-binds to the new sha256:41fcb384... value.
- The test vector self-consistency check (recanonicalize raw_manifest, recompute manifest_hash, recompute envelope_hash, recompose ARC-2 note from prefix + inner) holds.

11 verification checks pass cleanly.

## Apply order

For each of your three repos:

1. **actproof-events**: extract the three step bugfix zips. The pyproject.toml and __init__.py changes from Step 1 are surgical edits. Step 2 fully replaces `catalogue/acts/actproof/standards_engagement_record.v1.json`. Step 3 fully replaces `catalogue/acts/actproof/standards_engagement_record.v1.test_vectors.json` and `scripts/test_vector_inputs/actproof_standards_engagement_record_v1_001.json`. Commit each.
2. Rebuild the wheel: `python -m build --wheel` from the events repo root.
3. **actproof-py**: no changes in this bugfix.
4. **quoruna**: apply the separate Step 6.2 bugfix zip (which fixes the parallel maintainer and spec-ordering issues in the mint builder and clarifies the evidence files' Issuer vs Maintainer header). Reinstall actproof-events and re-run the mint script in `--mode draft` to confirm the new manifest hash before going to mainnet.

## Effect on the STS receipt content

The live STS mainnet mint will now produce a receipt that:

- Names Deyan Paroushev as maintainer and Advisa EOOD as issuer (ChatGPT's most important correction)
- Carries an explicit non_claims array a verifier UI can render
- Cryptographically commits to the catalogue entry bytes via the new sha256:41fcb384... hash
- Uses the actproof/v1: ARC-2 prefix appropriate for a generic substrate library
- Leads its related_specifications with the core IETF standards work
