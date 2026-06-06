# 1.8.0 mint checklist

Run from the repository root before publishing:

```bash
python -m pytest -q
python scripts/validate_catalogue.py --strict
python -m actproof_events.exports validate-source-bindings \
  op:eu.dora.ict_incident_notification_initial.v1
python -m actproof_events.exports export-profile-view \
  op:eu.dora.ict_incident_notification_initial.v1 \
  --out dora.profile-view.1.8.0.json \
  --validate
python -m actproof_events.exports verify-profile-view dora.profile-view.1.8.0.json
```

Expected results:

```text
82 tests passed
catalogue validation RESULT: PASS
required template-field coverage: 15/15 (100.0%)
release-gated field coverage: 15/27 (55.6%)
optional contextual derivations: 12/12 (not counted as template-field coverage)
profile-view verification OK: True
```

Build/publish in Codespaces or local environment with Hatchling available:

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine upload dist/*
```

This environment could not build the wheel because `hatchling` is not installed here. The source tree is prepared for normal PEP 517 build tooling.


## Final pre-mint gates added after market-alignment review

Run these from the repository root before uploading to PyPI:

```bash
python -m pytest -q
python scripts/validate_catalogue.py --strict
python -m actproof_events.exports validate-source-bindings op:eu.dora.ict_incident_notification_initial.v1
python -m actproof_events.exports source-coverage op:eu.dora.ict_incident_notification_initial.v1
python -m actproof_events.exports export-profile-view op:eu.dora.ict_incident_notification_initial.v1 --out dora.profile-view.1.8.0.json --validate
python -m actproof_events.exports verify-profile-view dora.profile-view.1.8.0.json
python -m actproof_events.exports prevalidate-report op:eu.dora.ict_incident_notification_initial.v1 path/to/report.json --json
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

Expected source-binding headline:

```text
required template-field coverage : 15/15 (100.0%)
release-gated field coverage     : 15/27 (55.6%)
optional contextual derivations  : 12/12 (not counted as template-field coverage)
```

Do not mint this release as a streaming incident-reporting server. Correct label: source-bound DORA profile with agent-readable pre-validation primitives.
