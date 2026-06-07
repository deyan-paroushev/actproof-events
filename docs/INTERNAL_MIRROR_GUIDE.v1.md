# Internal mirror guide v1

Use `actproof-events export-release-assurance-pack` to generate a bank-facing release-assurance pack.

Recommended installation model:

1. Download a pinned wheel and sdist.
2. Store them in an internal package repository or wheelhouse.
3. Store the SBOM, artifact hashes and profile lock alongside the change ticket.
4. Install from the internal mirror only.
5. Run ActProof locally; do not send sensitive incident data to public endpoints.

Example:

```bash
python -m pip download --only-binary=:all: --dest wheelhouse actproof-events==2.3.0
python -m pip install --no-index --find-links wheelhouse actproof-events==2.3.0
```

Boundary: this guide supports bank/internal deployment hygiene. It does not replace bank security review, vulnerability scanning, or software approval.
