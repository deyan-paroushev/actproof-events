# actproof-events 2.5.0 — official source-text capture (pilot)

This release begins capturing the verified official text of source atoms, closing
a previously disclosed gap: atoms pinned the locator and identity of each
provision but not the official text of it, so `text_excerpt` was empty and
`official_text_sha256` unset across the set.

## What is captured

Three DORA-regulation Article 19 atoms, verbatim from the official EUR-Lex OJ
source (`L_2022333EN_01000101_xml.html`, CELEX 32022R2554), each as its clean
paragraph body under `actproof.official_text_excerpt_rule.v1`:

- `art19.reporting_obligation` (Article 19(1), 2061 chars)
- `art19.p4.initial_intermediate_final` (Article 19(4), 859 chars)
- `art19.competent_authority_channel` (Article 19(6), 1128 chars)

The remaining 23 atoms stay honestly locator-bound (`not_captured`).

## Identity hashes are not disturbed

`official_text_sha256` is a new, separate hash over the normalised official text.
Because the identity basis includes `locator`, the finer paragraph reference used
for capture is recorded in a new `text_locator` field rather than by mutating
`locator`. Every atom's `atom_identity_sha256` is byte-for-byte unchanged, so no
downstream profile or overlay is disturbed.

## Captured is checkable, not attested

Capture moves an atom to `binding_status: text_locator_bound` /
`text_capture_status: captured_draft`. `text_review_status` stays `draft`:
the official text is independently recomputable, not legally reviewed.

## New module: actproof_events.text_capture

- `normalise_official_text` — deterministic, structure-preserving normalisation
  (NFC, LF line endings, intra-line whitespace collapse, single trailing LF;
  line structure and enumerated points are preserved).
- `compute_official_text_sha256` — hash over the normalised UTF-8 text.
- `capture_atom_official_text` — additive capture; asserts the identity hash is
  unchanged.
- `verify_atom_official_text` — recompute and confirm the stored hash (verdict).
- `atom_text_maturity` — M1..M6 maturity label per atom.
- `compute_atom_text_coverage` — coverage ratio, by-maturity and by-atom-type.
- `build_atom_dependency_report` — which fields/derivations depend on each atom.
- `export_atom_inventory` — atoms with maturity + dependency summary.

## New CLI

- `actproof-events atom-text-coverage ACT_ID [--json]`
- `actproof-events validate-atom-text ACT_ID` (re-hashes every captured atom)
- `actproof-events verify-atom-text ACT_ID [--atom-id ID] [--json]`
- `actproof-events atom-dependencies ACT_ID [--out f] [--json] [--compact]`
- `actproof-events export-atom-inventory ACT_ID --out f [--compact]`

## Boundary

This is not a bulk scrape. It is not a claim that all atoms are text-bound. It is
not external legal review or compliance certification. Template-field, glossary,
classification, and the article-range atom (flagged for re-atomisation) are not
captured here; they need their own boundary rules, added after the article path.

## Tests

`tests/test_text_capture.py` (11 tests): structure-preserving normalisation,
hashing, identity-hash-untouched on capture, binding-vs-review separation,
empty-excerpt refusal, tamper detection, that the three shipped atoms
capture-and-verify and report 3/26, that `validate-atom-text` passes on the
shipped set, and the coverage/dependency/inventory reports.
