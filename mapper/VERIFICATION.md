# Verification record

This records that the ActProof Mapper pipeline was run end to end against the
genuine official EU source PDFs, not placeholders.

## Result

The full eight-step pipeline ran on the four official DORA-family source
documents. Step 1 computed SHA-256 over the raw PDF bytes and matched all four
against the hashes pinned in `examples/dora/inputs/source-bindings.json`.

| CELEX | Document | SHA-256 | Status |
|---|---|---|---|
| 32022R2554 | Regulation (EU) 2022/2554 (DORA) | `85307f9e2a0409826dd0f54489645935816d16e929f0db4db3ef15badd11d38c` | verified |
| 32025R0301 | Commission Delegated Regulation (EU) 2025/301 | `47a209a9f73e228e85e1dad2934d917d5791629fc98add06fc6fda0acb872dbf` | verified |
| 32025R0302 | Commission Implementing Regulation (EU) 2025/302 | `37ec431c7a11b8b30b39d1c1f0d95c39539d1c1e7236301ee3b06bb229ff009c` | verified |
| 32024R1772 | Commission Delegated Regulation (EU) 2024/1772 | `416fb104161f8b3eb0aae2601060ab869b1672cfa8452d20798800301538ceab` | verified |

Source dossier status: **all_verified** (4 verified, 0 missing, 0 mismatch).

## Pipeline run

```
STEP 1 - Source dossier            all_verified
STEP 2 - Source fragments          pass        (12 fragments)
STEP 3 - Legal actions             pass        (5 actions)
STEP 4 - Mapped fields             pass_with_warnings  (27 fields; see note)
STEP 5 - Evidence labels           pass        (2 labels)
STEP 6 - Interpretation decisions  pass        (10 decisions)
STEP 7 - Traceability matrix       pass        (29 rows)
STEP 8 - Profile assembler         PASS        (final profile assembled)
```

The final `actproof-profile.json` carries all four source bindings as
`verified`.

## Note on the Step 4 warnings

Step 4 reports `pass_with_warnings`, not errors. The warnings are observations
about the DORA mapping content, not faults in the pipeline:

- `competent_authority` is marked required but mapped as an operational support
  field;
- four intermediate-report fields rest on a fragment that no legal action
  references.

These are content review items for the human author of the DORA mapping, surfaced
on purpose. They do not block assembly.

## What this proves, and does not

Proves: the profile was built from these exact official documents, confirmed by
hash, and is structurally reproducible from the recorded steps.

Does not prove: legal correctness, completeness, compliance, that the documents
are the current consolidated law (currentness was not checked), or that an
authority accepted anything.
