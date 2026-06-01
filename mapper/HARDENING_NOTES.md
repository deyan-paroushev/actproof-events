# Mapper hardening notes (hybrid)

This is the hybrid of two independently hardened versions, taking the better
half of each and resolving one principled fork in favour of human authority
over interpretation.

## Engineering changes applied

- `--stop-on-warning` is now real: each step exits code 2 on warnings when
  `ACTPROOF_STRICT=1` (set by the runner). This works even when a single step
  is run directly, not only through the runner.
- Final profile fields carry `trace_id` and `mapping_status` (a pointer back
  into the mapping package), plus the profile surfaces `source_state`.
- `mapping-package.json` preserves the full Step 4 `mapped_fields` register and
  the review-gate metadata.
- Evidence trace rows use the shared `mapping_status` vocabulary, with the
  evidence-specific meaning in a separate `evidence_basis` field (no invented
  `evidence_*` statuses).
- `review_gate` metadata is carried from the human-authored input files into
  each step's output, so the audit trail travels with the registers.
- Step 7 honesty check broadened to all non-direct rows (kept at WARNING level;
  see principled fork below).

## Multi-proposal interpretation model (new)

Interpretation links now use a multi-proposal, host-neutral record:

- `proposals[]`  one or more attributed proposals (which AI/version or which
  human proposed the reading, when, citing which decision, and why).
- `affirmation`  the human record: proposed | affirmed | overruled, by whom,
  when, which proposal, and a note.
- `discussion_ref`  OPTIONAL, host-neutral pointer to the deliberation venue
  (a GitHub discussion today, another host tomorrow). The link is meaningful
  without it; the commons does not depend on any single host.
- `vote_ref`  RESERVED, unused: the slot for a future mechanism that resolves a
  contested link.

This is additive. The legacy flat `interpretation_decisions` list is preserved
alongside it and marked DEPRECATED, slated for removal at the v0->v1 freeze, so
no consumer breaks. This follows standard schema-evolution practice: add new
fields, deprecate old ones, never rename or remove in place.

## The principled fork: human authority over interpretation

The other hardened version cleared the Step 4 warnings by linking fields to
interpretation decisions automatically. We did NOT adopt that.

The law was written by humans. An AI can PROPOSE a reading; the FINAL call on
interpretation rests with a human maintainer. Different AIs, and different
maintainers, may read the same provision differently. Accuracy in this commons
comes from attributed plurality plus human convergence, not from trusting any
single interpreter. Removing the human from the loop would turn this into an
automation interpreter and remove the reason for maintainers to exist - which
would remove the reason it is a commons.

So:

- The DORA mapping data is left UNEDITED. The Step 4 warnings remain visible.
  They are pending-affirmation markers, not faults.
- The required-operational-support check stays a WARNING, not an error.
- The 13 AI-proposed links from the other version are preserved as attributed,
  unaffirmed candidates in
  `examples/dora/candidates/ai-proposed-interpretation-links.json`
  (all `affirmation.status: proposed`, attributed to GPT-5.5). A maintainer -
  possibly cross-checking with a different model - can later affirm, overrule
  or adjust each one. Proposals are kept on the record, affirmed or overruled,
  never deleted.

## Boundary unchanged

The mapper validates structure and provenance only. It does not prove legal
correctness, completeness, compliance, factual truth or authority acceptance.
Provenance is mechanical (hashes); fidelity is a reviewed, contestable reading;
final interpretive authority rests with human maintainers.
