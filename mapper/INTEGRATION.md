# Integrating the mapper into actproof-events

This `mapper/` directory is self-contained and drops in at the repository root:

```
actproof-events/
  catalogue/
  sources/
  spec/
  schemas/
  mapper/            <-- this directory, added whole
    README.md
    VERIFICATION.md
    INTEGRATION.md
    run_all.py
    steps/
    examples/dora/
```

## What to commit

Add the whole `mapper/` directory. Nothing else in the repo needs to move.

## One optional touch elsewhere

In the repository root `README.md`, add a single line under the existing
sections so the capability is discoverable:

> **ActProof Mapper** (experimental): a controlled, inspectable process from
> official source PDFs to a profile, recording every step. See `mapper/README.md`.

## Status discipline

Keep this labelled **experimental** in the repo, consistent with the README and
with the NGI0 roadmap framing. It is the worked, runnable form of the WP3/WP7
source-to-profile mapping; it is not yet a packaged release and is not on PyPI.

## Licensing

The scripts are intended under the repository's Apache-2.0 licence, consistent
with the rest of actproof-events. The four PDFs under
`examples/dora/sources/` are official EU publications included for
reproducibility; they are not covered by the project licence.

## Reproduce the verification

```
cd mapper
python run_all.py --example dora
```

Step 1 will report `all_verified` (4/4) against the included official PDFs.
See VERIFICATION.md for the recorded hashes and run result.
