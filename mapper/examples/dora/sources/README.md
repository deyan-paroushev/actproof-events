# DORA source PDFs

Place the four official CELEX PDF files here, using the filenames declared in
`../inputs/source-bindings.json`:

```
CELEX_32022R2554.pdf
CELEX_32025R0301.pdf
CELEX_32025R0302.pdf
CELEX_32024R1772.pdf
```

The pipeline runs without these files: Step 1 reports each as `missing` rather
than failing. When the files are present, Step 1 computes SHA-256 over the raw
bytes and verifies them against the pinned hashes in `source-bindings.json`.
