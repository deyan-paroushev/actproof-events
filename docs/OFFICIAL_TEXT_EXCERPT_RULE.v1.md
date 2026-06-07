# ActProof Official Text Excerpt Rule, v1

`actproof.official_text_excerpt_rule.v1`

This document is the authority for how a source atom's `text_excerpt` is captured
and how its `official_text_sha256` is computed. It exists so that the hash is
**recomputable by a third party**: an auditor who has this rule and the named
official source can extract the same bytes and arrive at the same hash. Without a
written rule, the hash is a number no one can independently confirm.

This is a v2.5.0 pilot. It applies, in this version, only to the three
DORA-regulation article/paragraph atoms named in section 6. It is deliberately
narrow. The rule is extended to template-field, glossary, and classification
atoms in later versions, after the article path is proven.

---

## 1. Scope and non-claims

This rule defines a reproducible capture of **official legal source text**. It
does not interpret that text, decide a field mapping, or assert compliance.
Capturing and hashing the text makes an atom **checkable**, not **attested**: a
captured atom is one whose source bytes can be independently verified; it is not
one a competent person has reviewed for legal correctness. Those are separate
steps with separate status fields (section 7).

A populated `official_text_sha256` proves only that the stored `text_excerpt`
matches the captured official text under this rule. It does not prove the excerpt
is the legally complete or correct basis for any field. That remains a review
question.

---

## 2. Canonical source

For DORA-regulation atoms (CELEX `32022R2554`), the canonical source is:

- **System**: EUR-Lex, the official EU legal database.
- **Identifier**: the ELI `http://data.europa.eu/eli/reg/2022/2554/oj`.
- **Language**: English (`en`). English is the capture language for v1. Other
  language versions are equally authentic under EU law; a multilingual capture
  is out of scope for the pilot and, when added, each language is a separate
  excerpt with its own hash.
- **Consolidation status**: **original OJ text** (`original_oj`), i.e. the text
  as published in OJ L 333, 27.12.2022. Consolidated, corrigendum-adjusted, and
  amended versions are explicitly **not** used in v1. If the official text is
  later amended, that is a new capture against a newly identified source, not a
  silent edit (section 8).
- **Format basis**: the EUR-Lex **HTML** rendering of the act
  (`text_format_basis: eurlex_html`). The Formex XML form is the more durable
  long-term basis and is the intended v2 upgrade; v1 uses HTML because it is the
  form a human reviewer reads and can confirm by eye. The format basis is
  recorded on every atom so a verifier knows which rendering to compare against.

The `retrieval_url` and the date of retrieval are recorded per atom in its
provenance block. A capture is pinned to the bytes retrieved on that date.

---

## 3. Excerpt boundary

The boundary rule says exactly what counts as the excerpt for a given atom type.
The hash is meaningless unless the boundary is reproducible.

### 3.1 Boundary rules in v1

- `article_full` — the entire numbered article: its heading line (e.g.
  `Article 19`) and its full body including all paragraphs, sub-paragraphs,
  points, and internal numbering. Excludes recitals and footnotes.
- `article_paragraph` — one specific numbered paragraph of an article: the
  paragraph number marker (e.g. `4.`) and that paragraph's text including its
  sub-paragraphs and points. Excludes the article heading, other paragraphs,
  recitals, and footnotes.

Each atom declares which boundary rule it uses (`excerpt_boundary.boundary_rule`)
and a one-line `boundary_note` stating in prose what was captured.

### 3.2 What is always included / excluded

Included: the article or paragraph numbering as printed; sub-paragraph and point
markers (`(a)`, `(i)`, etc.) as printed; the substantive text.

Excluded in v1: recitals; footnotes and their markers; cross-reference hyperlink
chrome (the link target is dropped, the visible link **text** is kept); editorial
annotations added by any non-official republisher (only EUR-Lex text is used);
the EUR-Lex page navigation, headers, and boilerplate.

### 3.3 The shared-locator problem (a real finding from the pilot data)

Two pilot atoms currently carry the same locator `{article: 19}` but are intended
to capture different provisions:

- `...art19.reporting_obligation` — the base obligation (Article 19(1)).
- `...art19.competent_authority_channel` — the competent-authority reporting
  context (the Article 19 provisions on the relevant competent authority).

A locator of `{article: 19}` is **not specific enough** to deterministically
extract two different excerpts. v1 resolves this by **refining the locator to the
paragraph level at capture time** and recording the refinement. The base
obligation binds to Article 19(1); the competent-authority channel binds to the
Article 19 paragraph(s) that designate the relevant competent authority. The
refined locator is written into the atom; the original coarse locator is retained
in `locator_supersedes` so the change is visible, not silent. This refinement is
itself a finding the pilot surfaces: coarse locators must be sharpened before
text can be bound.

---

## 4. Normalisation

`actproof.official_text_normalisation.v1`. Applied to the captured excerpt
**before** hashing, so that trivial, non-substantive rendering differences do not
change the hash. The normalisation is deterministic and minimal:

1. **Unicode**: normalise to NFC.
2. **Line endings**: convert all CRLF and CR to LF.
3. **Whitespace within a line**: collapse runs of spaces/tabs to a single space.
4. **Trailing/leading whitespace**: strip from each line; strip from the whole
   excerpt.
5. **Blank lines**: collapse runs of blank lines to a single LF; the excerpt
   ends with a single trailing LF.
6. **No other change**: no case folding, no punctuation change, no spelling
   change, no reordering, no de-hyphenation. The words and their order are the
   official text, untouched.

The normalisation is intentionally conservative. It removes only rendering noise
that an auditor would agree is not part of the legal text. Anything that could
change meaning is left alone. Both the raw `text_excerpt` and the basis are
stored, so a verifier can re-run the normalisation and re-hash.

---

## 5. Hashing

- `official_text_sha256` = `"sha256:" + hex( SHA-256( normalised_excerpt.encode("utf-8") ) )`.
- `official_text_hash_basis` = `"sha256:utf8:actproof.official_text_normalisation.v1"`.
- The hash is computed over the **normalised** excerpt, UTF-8 encoded.
- This is **separate from** `atom_identity_sha256`, which hashes the atom's
  identity metadata and is **not changed** by text capture. Capturing text adds a
  new hash; it does not recompute the identity hash, so atoms already pinned by
  downstream overlays are not disturbed.

Verification (`verify-atom-text`): given an atom with a stored `text_excerpt`,
re-normalise it under the named basis, re-hash, and confirm it equals the stored
`official_text_sha256`. A mismatch means the excerpt was altered after capture or
the wrong normalisation was applied. This is the check that makes the capture
real rather than asserted.

---

## 6. The v1 pilot set

Exactly three atoms, all from CELEX `32022R2554` (the DORA regulation itself),
all real prose, single-article — chosen to prove the pipeline before any
template-cell or article-range atom is touched:

| atom_id (tail) | refined locator | boundary rule |
|---|---|---|
| `art19.reporting_obligation` | Article 19(1) | `article_paragraph` |
| `art19.p4.initial_intermediate_final` | Article 19(4) | `article_paragraph` |
| `art19.competent_authority_channel` | Article 19 (competent-authority provision) | `article_paragraph` |

The remaining 23 atoms keep `text_capture_status: not_captured` and are untouched
in v1. The article-range atom (`32024R1772.art1to7...`) is explicitly **excluded**
and flagged for re-atomisation before any text binding — capturing seven articles
as one excerpt would be the wrong move.

---

## 7. Maturity tiers (status this rule can set)

Capture moves an atom along the **binding** axis only. It does not touch the
review axis.

- `binding_status`: `provisional` → `text_locator_bound` once `text_excerpt` and
  `official_text_sha256` are populated under this rule and `verify-atom-text`
  passes.
- `text_capture_status`: `not_captured` → `captured_draft`.
- `text_review_status`: stays `draft`. Capture does **not** make text reviewed.
- `review_status`: unchanged by capture.

`text_locator_bound` means: the official text is captured and the hash is
recomputable. It does **not** mean a person has attested the excerpt is the
correct legal basis. That is `text_review_status: reviewed`, reached only by a
named reviewer in a separate step — exactly as maintainer self-attestation was
kept separate from independent legal review elsewhere in the project.

---

## 8. Change control

- The captured text is pinned to the source identified in section 2 on the
  retrieval date recorded in the atom.
- If the official text is later **amended** by the EU, that is a **new capture**
  against a newly identified consolidation, producing a new hash and triggering
  downstream review (`requires_downstream_review: true`). It is never a silent
  in-place edit.
- If the **excerpt boundary** is found to be wrong (e.g. a paragraph was
  mis-bound), correcting it is a recorded change with a reason, and any field or
  overlay depending on the atom is flagged for re-review.
- This rule itself is versioned. A change to the boundary or normalisation rules
  produces `actproof.official_text_excerpt_rule.v2`, and atoms record which rule
  version captured them, so a v1 capture remains verifiable under v1 forever.

---

## 9. What this rule deliberately does not do

- It does not use an AI model to fetch, summarise, paraphrase, or approximate the
  text. The excerpt is the official bytes, captured verbatim from the source in
  section 2. An AI-approximated excerpt would make `official_text_sha256` a hash
  of fiction — worse than an honest empty field.
- It does not capture template-field, glossary, classification, or article-range
  atoms in v1. Those need their own boundary rules, added after the article path
  is proven.
- It does not assert legal review, completeness, or supervisory acceptance.
