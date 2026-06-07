# Release checklist — actproof-events 1.8.2

1. Run tests:

```bash
python -m pytest -q
```

2. Smoke-test bank-operability commands:

```bash
cat > draft-report.json <<'JSON'
{"entity_legal_identifier":"549300EXAMPLE00000001"}
JSON

actproof-events export-profile-lock op:eu.dora.ict_incident_notification_initial.v1 --out profile-lock.json
actproof-events export-review-checklist op:eu.dora.ict_incident_notification_initial.v1 --out bank-review-checklist.json
actproof-events export-prevalidation-report op:eu.dora.ict_incident_notification_initial.v1 draft-report.json --out prevalidation-report.json || true
```

3. Validate catalogue and profile view:

```bash
python scripts/validate_catalogue.py --strict
actproof-events export-profile-view op:eu.dora.ict_incident_notification_initial.v1 --out dora.profile-view.1.8.2.json --validate
actproof-events verify-profile-view dora.profile-view.1.8.2.json
```

4. Build and publish:

```bash
rm -rf dist build *.egg-info
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

Boundary: 1.8.2 is a bank-operable trust-pack release. It does not include candidate external schema mapping, hosted filing, evidence upload, legal certification, or production bank workflow functionality.
