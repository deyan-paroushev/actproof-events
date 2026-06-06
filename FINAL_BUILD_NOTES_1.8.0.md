# ActProof Events 1.8.0 final build notes

This is the final 1.8.0 source-bound DORA profile release, scoped deliberately below the 1.9.0 pre-validation runtime.

## Correct release claim

ActProof Events 1.8.0 provides a source-bound DORA initial-notification profile with agent-readable pre-validation primitives.

- 15/15 required DORA fields are template-field bound.
- 12 optional fields carry experimental contextual derivations.
- Optional contextual derivations are exported and inspectable but do not count as template-field release coverage.
- Field derivations retain draft review gates.
- Source atoms are provisional locator-bound: CELEX/ELI + source document hash are present; official_text_sha256 remains pending.
- This is not a stateful MCP streaming incident-reporting server and not a cryptographic receipt verifier.

## Final gates run in this environment

- `python -m pytest -q` -> 94 passed
- `python scripts/validate_catalogue.py --strict` -> PASS, 7/7 entries OK
- `python -m actproof_events.exports validate-source-bindings ...` -> OK
- `python -m actproof_events.exports source-coverage ...` -> required template-cell 15/15, optional contextual 12/12
- `python -m actproof_events.exports export-profile-view ... --validate` -> valid JSON generated
- `python -m actproof_events.exports verify-profile-view ...` -> OK

## Environment limitation

This runtime did not have `build` / `hatchling` installed, so the PyPI wheel/sdist was not rebuilt here. Build in Codespaces with:

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```
