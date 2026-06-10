# Source-dependency continuity demo

This is the official ActProof Events worked example for source-dependency continuity.

It demonstrates one narrow claim:

> A downstream artifact can be bound to a receipted source-dependency statement and later checked against the current receipted source-dependency statement. If the maintained source basis moved, the result is `NEEDS_REVIEW`, not a compliance conclusion.

## Worked example

- Profile v1 depends on DORA Article 19(1) and EU 2025/301.
- A downstream reporting-form binding is created against profile v1.
- Profile v2 adds EU 2025/302 forms/templates/procedures.
- The continuity check returns `NEEDS_REVIEW`.

## What is receipted

This example includes local COSE receipts for:

- `statements/profile-dependency-statement.v1.json`
- `statements/profile-dependency-statement.v2.json`
- `source-atom.statement.json` as an optional substrate source-atom check

The committed tree includes the public key, COSE objects, local log and receipts from one sample run. It does not include the private development key.

## Install

The worked example signs and verifies COSE statements, which needs the optional
`cose-signing` extra:

```bash
pip install "actproof-events[cose-signing]"
```

Without the extra the package imports fine, but the demo will stop with a clear
message telling you to install it.

## Run it

```bash
python -m actproof_events demo dora-301-302-continuity --out /tmp/actproof-dora-demo
python -m actproof_events demo dora-301-302-continuity --verbose --out /tmp/actproof-dora-demo-verbose
```

The deterministic source atoms and dependency roots should remain stable for the same package version and source text. Runtime receipt artifacts include fresh development keys, COSE signatures, local-log entries and registration timestamps, so their receipt hashes are expected to differ between runs.

## Boundary

ActProof does not determine legal compliance, legal sufficiency, regulatory approval, bank approval or supervisory acceptance. It shows that the source basis of reliance moved and that review is required.
