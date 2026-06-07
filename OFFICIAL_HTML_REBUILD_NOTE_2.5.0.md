# 2.5.0 build note — merged module, verbatim captures

This 2.5.0 takes the best of two parallel builds:

- The **module structure and reporting** (a standalone `text_capture.py` with the
  maturity ladder, coverage-by-type, dependency report, and inventory export, plus
  the `atom-text-coverage` / `validate-atom-text` / `atom-dependencies` /
  `export-atom-inventory` CLI) is adopted as the foundation.
- The **captures** are the verbatim, boundary-clean Article 19 paragraph texts,
  extracted deterministically from the official OJ HTML
  (`L_2022333EN_01000101_xml.html`). Each is exactly its paragraph body — no
  article heading glued on — so `official_text_sha256` is reproducible by anyone
  extracting the same paragraph from the source.

Two corrections were made to the adopted module:

1. **Structure-preserving normalisation.** Whitespace is collapsed within a line
   but line breaks are preserved, so enumerated points (a)/(b)/(c) keep their
   boundaries. Collapsing everything to one line would destroy structure that
   carries legal meaning.
2. **Identity-safe locator refinement.** The paragraph refinement (19 -> 19(1),
   19 -> 19(6)) is recorded in `text_locator`, leaving the identity `locator`
   untouched so `atom_identity_sha256` does not change. Two atoms that share the
   identity locator `{article: 19}` are distinguished by `text_locator` and by
   their distinct captured paragraph text.

`validate-atom-text` re-hashes every captured atom and PASSES on this set; the
same check would fail any capture whose stored hash did not match its text.
