# Receipt vocabulary alignment (v1)

actproof-events 2.8.0

## Position: ASQAV/ACTA-aware, not -derived

There is a fast-moving family of "signed action receipt" Internet-Drafts for AI
agents: `draft-farley-acta-signed-receipts` (the base format) and
`draft-marques-asqav-compliance-receipts` (a compliance profile binding DORA
Article 17 and EU AI Act Articles 12 and 26, with a live reference SDK on PyPI,
`asqav`). Both are individual / Independent Internet-Drafts, not IETF consensus
and not RFCs.

ActProof's receipt and that family share proof *mechanics* but commit to
different *subjects*:

- An ACTA / ASQAV receipt is evidence that **an agent performed an action** under
  a policy.
- An ActProof receipt is evidence that **a source-bound regulatory atom / profile
  statement** was signed and locally registered.

So this release aligns the mechanism vocabulary where the concept is identical,
and keeps ActProof-native names where the subject differs. This is alignment for
interoperability and credibility, not conformance.

## Aligned mechanism fields (shared names)

| Field | Meaning in ActProof |
| --- | --- |
| `canonicalization: "JCS/RFC8785"` | Same JCS / RFC 8785 discipline already used. |
| `policy_digest` | sha256 over the ActProof policy object (maturity + scitt_binding + profile). |
| `previous_receipt_hash` | Per-entry hash chain to the prior receipt; genesis is the all-zero sentinel. |
| `statement_ref` | The ActProof analogue of an action receipt's `action_ref`. Refers to a source-atom **statement**, not an agent action. |

## ActProof-native fields (kept distinct)

`profile_commitments` (`profile_semantic_hash`, `profile_artifact_hash`),
`source_atom_commitments` (`atom_identity_sha256`, `canonical_atom_json_sha256`,
`official_text_sha256`, `dependency_root`), `registration_status`,
`receipt_status`, `registration_time`, and the `log` inclusion-proof block.

## Not adopted

`action_ref` is not used as a canonical ActProof field, because the referred
object is a regulatory source-atom statement, not an agent action. `statement_ref`
carries that meaning with a note pointing at the analogy.
