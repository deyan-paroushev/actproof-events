# Release checklist — actproof-events 2.8.0

- [ ] `pyproject.toml` version is `2.8.0`; `__version__` is `2.8.0`
- [ ] `pip install -e ".[cose-signing]"` succeeds
- [ ] `python -m pytest tests/test_scitt_registration.py -q` passes (14)
- [ ] `python -m pytest tests/test_scitt_profile.py tests/test_cose_signing.py tests/test_text_capture.py -q` passes
- [ ] full suite passes (191 passed, 10 skipped)
- [ ] `python -m compileall actproof_events` passes
- [ ] CLI smoke path passes end to end (keygen, statement, sign, init-log, register, verify)
- [ ] standalone `verify-scitt-local-receipt` (no `--log`) → PASS, all 10 checks
- [ ] optional `--log` cross-check → ok
- [ ] statement carries `scitt_binding`; receipt carries `registration_time`,
      `policy_digest`, `previous_receipt_hash`, `statement_ref`
- [ ] registration_time excluded from the hashed leaf (leaf reproducible)
- [ ] catalogue validation PASS (7/7)
- [ ] `python -m build` + `twine check dist/*` pass
- [ ] tag `v2.8.0`
