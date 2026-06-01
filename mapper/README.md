# ActProof Mapper

**A controlled, inspectable process from official legal source to machine-readable profile JSON.**

Status: experimental. This lives inside ActProof Events as a capability, not as
a separate package.

---

## What this is

ActProof Events publishes source-bound profiles of public-rule acts. A profile
can prove, by hash, that it was built from the exact official documents it
cites. That proves *provenance*.

What it did not yet show is *how* the law became the profile, field by field.

ActProof Mapper fills that gap. It is the middle layer: a controlled process
that takes an official source and produces a profile, recording every step so
anyone can inspect it, reproduce it, and challenge it.

The difference it makes:

> A normal system says "here are the required fields."
> ActProof Mapper says "here is how each field came into existence, which
> source fragment supports it, where human judgement entered, and what this
> profile refuses to claim."

---

## The eight steps

```text
official PDF sources
   |
   v
[1] source dossier        verify the source PDFs against pinned hashes
   |
   v
[2] source fragments      break the law into stable, named pieces
   |                        (human selects which provisions matter, and why)
   v
[3] legal actions         who must do what, to whom, by when, on what condition
   |                        (human decomposes the duty)
   v
[4] mapped fields         derive each profile field and record HOW
   |                        (direct / derived / interpretive / support)
   v
[5] evidence labels       supporting records, never overclaimed as mandatory
   |                        unless the source truly requires it
   v
[6] interpretation        record every non-obvious judgement, open to challenge
    decisions
   |
   v
[7] traceability matrix   bind it all into one table:
   |                        fragment -> action -> field -> evidence
   |                        -> disclosure -> decision
   v
[8] profile assembler     emit the final profile JSON + the full mapping package
```

### The review gates

Steps 2 to 6 each consume a **human-authored selection file**. That file is the
review gate: it is where a person decides what to include and states a reason.
Nothing is auto-extracted from the legal text. The tools' job is to check those
human choices are consistent and anchored, not to make them.

Steps 1, 7 and 8 have no human gate. Step 1 verifies. Steps 7 and 8 assemble
and cross-check. They cannot invent anything.

---

## How to run it

Run the whole DORA example in one command:

```bash
python run_all.py --example dora
```

This reads:
- `examples/dora/inputs/` - the human-authored selection files
- `examples/dora/sources/` - the official PDFs (optional; see below)

and writes every step's output to `examples/dora/outputs/`.

Run a single step (each is self-contained):

```bash
python steps/step1_source_dossier.py \
  --bindings examples/dora/inputs/source-bindings.json \
  --sources  examples/dora/sources \
  --out      examples/dora/outputs
```

### About the source PDFs

The pipeline runs even without the PDFs present. Step 1 reports each source as
`missing` rather than failing. When you place the four official CELEX PDFs in
`examples/dora/sources/` (filenames in `source-bindings.json`), Step 1 computes
their SHA-256 and verifies them against the pinned hashes. That verified status
then flows through to the final profile.

---

## What you get

In the output directory:

| File | What it is |
|---|---|
| `actproof-profile.json` | the finished, lean operational profile |
| `mapping-package.json` | the complete evidence record (everything) |
| `traceability.json` / `.md` / `.csv` | how each field maps to its source |
| `source-dossier.json` | source verification result |
| `source-fragments.json` | the named pieces of law |
| `legal-actions.json` | the decomposed duties |
| `mapped-fields.json` | each field with its derivation |
| `evidence-labels.json` | supporting records and their basis |
| `interpretation-decisions.json` | the judgement register |
| `*-check.txt` | a short check log for each step |

The profile carries a pointer back to the mapping package, so from any field
you can trace the whole chain back to the source.

---

## The guardrails

Every step enforces structural honesty. The most important rules:

1. **No anonymous source.** Every fragment points to a verified source.
2. **Every field explains itself.** A field with no source fragment and no
   interpretation basis cannot pass.
3. **Interpretation is never hidden.** Modelling choices are recorded as
   decisions, open to challenge - not presented as the source's own words.
4. **Evidence is never overclaimed.** A record is only a "mandatory legal
   attachment" if the source genuinely requires it.
5. **Provenance is mechanical; fidelity is reviewed.** A hash match proves the
   source is authentic. The quality of the mapping is a public reading, open to
   challenge. The tools never present fidelity as a passed check.

---

## What this is not

- It is **not** automatic legal interpretation. Humans make every mapping
  choice; the tools check and bind them.
- It is **not** compliance automation. It does not decide whether a real duty
  was met or accepted.
- A finished profile is an **inspectable public artefact**, not an official
  legal interpretation, and not legal advice.

Provenance can be computed. Fidelity needs people. That is why this is built as
a commons: so the mapping can be read, forked, deprecated, and challenged in the
open.
