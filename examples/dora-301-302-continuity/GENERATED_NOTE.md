# Generated example note

This directory contains a committed sample run of the DORA 301 -> 302 continuity demo.

The committed sample is inspectable and verifiable using the included public key, COSE artifacts, local log and receipts. The private development key used to create the sample was removed and must never be committed.

Regenerate with:

```bash
python -m actproof_events demo dora-301-302-continuity --out examples/dora-301-302-continuity
```

When regenerated, receipt hashes are expected to change because the local pilot creates fresh runtime signing material and registration timestamps.
