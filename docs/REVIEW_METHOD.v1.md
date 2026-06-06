# ActProof Review Method v1 (`manual_source_locator_review.v1`)

This document defines what `review_status` means for ActProof field-source
bindings, and the checklist a binding must pass before its status is upgraded.
It exists so that review status is an *earned, recorded* state — not a self-
asserted label. It is shipped in 1.8.0 (where all bindings are `draft`) precisely
so the criteria are public before any binding claims to have met them.

## Review status ladder

Bindings move along this ladder; they never start above `draft`:

- `draft` — authored by the maintainer, not yet reviewed against this checklist.
- `maintainer_reviewed` — passed the full checklist below in a recorded pass by
  the profile maintainer.
- `independent_reviewed` — additionally checked by a second reviewer who is not
  the author.
- `external_legal_reviewed` — additionally checked by a qualified external legal
  or regulatory reviewer. Reserved; not claimable without such a reviewer.
- `deprecated` / `superseded` — lifecycle end states.

1.8.0 ships everything at `draft`. 1.8.1 targets `maintainer_reviewed` for the
15 required DORA fields after a recorded pass.

## The checklist (all 10 must pass to leave `draft`)

1. **Source existence** — for every atom: CELEX exists, ELI exists, instrument
   title correct, `source_document_sha256` matches the pinned source artefact.
2. **Locator precision** — the locator is specific, not vague. For template
   atoms this means annex → section → field/cell, not just "Annex I".
3. **Field-to-template** — each required field maps to a real template/glossary
   requirement, or is explicitly an operational-support field.
4. **Field-to-obligation** — the field belongs in the initial-notification
   profile under the DORA incident-reporting sequence, not merely present in some
   template.
5. **Role classification** — where a field draws on 2024/1772, 2025/301 or
   2025/302, its role is classified (base obligation / template field / content
   requirement / time-limit / classification criterion / glossary / support).
6. **Derivation type** — direct / normalised / transformed / reconciled /
   modelled / interpretive is confirmed correct.
7. **Interpretive load not understated** — e.g. `entity_legal_identifier` low/
   direct; `classification_criteria_triggered` high/interpretive;
   `initial_impact_description` high/modelled. Understatement fails review.
8. **Non-claims present** — high-judgement fields carry boundary non-claims
   (e.g. "does_not_constitute_final_legal_classification").
9. **Hash / artefact reconciliation** — each atom references the same pinned
   source hash the profile's act-level source-basis uses.
10. **Sign-off record** — a recorded `review_gate` with reviewer, role, date,
    method (`manual_source_locator_review.v1`), scope, and notes.

## Recorded sign-off shape (on upgrade)

```json
{
  "review_status": "maintainer_reviewed",
  "reviewed_by": "<name>",
  "reviewed_role": "profile maintainer",
  "reviewed_at": "<date>",
  "review_method": "manual_source_locator_review.v1",
  "review_scope": "15 required DORA initial-notification fields",
  "review_notes": "<what was checked>"
}
```

Checklist items 1, 2 and 9 are also enforced automatically by
`scripts/validate_source_atoms.py` on every CI run; items 3–8 and 10 require
recorded human judgement and are what distinguishes `maintainer_reviewed` from
the automated structural gate.
