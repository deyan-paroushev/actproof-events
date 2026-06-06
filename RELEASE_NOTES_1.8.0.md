# actproof-events 1.8.0 — Field-Level Source Binding (final, market-aligned)

The release where ActProof becomes a library in its own right: each required
DORA field is bound to a specific ITS template cell, binding precision is
reported honestly in tiers, and the package exposes the read-only surfaces a GRC
system or compliance copilot grounds against.

## Release claim (precise)

ActProof Events 1.8.0 introduces **draft field-level source binding** for the 15
required fields in the DORA initial-notification profile. Each required field is
linked to inspectable **ITS template-field atoms** and supporting legal-source
atoms. The 12 optional fields carry experimental contextual derivations
(template-section / obligation-context granularity) and are **not** counted
toward the required-field release gate. The profile remains inspectable,
reproducible and challengeable; it is not legal advice or a compliance
certification.

## What's in this build (best-of-both, market-aligned)

Naming / framing:
- Three headline binding-granularity tiers: template_field, template_section,
  obligation_context (+ act_fallback). Glossary nuance retained as an optional
  binding_granularity_detail sub-marker, not a headline tier.
- field_binding_status as a one-word readiness summary (provisional_locator_bound
  in 1.8.0 -> text_verified in 1.8.1).
- coverage_semantics_note and market-aligned release language.

Integrity (the spine):
- binding_granularity + release_scope are the only two stored facts per
  derivation. counts_toward_required_release_gate, counts_toward_field_level_coverage,
  and field_binding_status are COMPUTED at read time and exported in the API/view,
  never stored, so the data carries one source of truth per fact and conclusions
  cannot drift. (SCITT/C2PA pattern: store primitives, derive conclusions.)
- atom_identity_sha256 is recomputed by a canonical function and VERIFIED by the
  conformance gate; a shipped sha256 field is reproducible, not asserted.
- review_status: draft preserved with full review_gate and the graded enum
  (draft / maintainer_reviewed / independent_reviewed / external_legal_reviewed).
- Precision-tiered coverage: a template-field binding is never counted equal to a
  section or obligation binding.

Market surfaces (library-as-product):
- REST API (api.py): profiles, fields, field source, evidence-checklist,
  compare-schema, profile-bindings/check, and NEW lint-report.
- CLI: export-profile-view, verify-profile-view, validate-source-bindings,
  explain-field, and NEW source-coverage and lint-report.

## Reference hashes (DORA initial notification, 1.8.0)

- profile_semantic_hash: sha256:a86a219365f5831af53332bc667095d5f70103130bae037354bcd13ded3e7d9e
- profile_artifact_hash: sha256:4e3e9e26a249196e5463fc53003929b6e1dfab8de719566fcd527b9ae60ecdc7

Version-independence holds within 1.8.0 (semantic hash stable across package
versions). It differs from 1.7.0 because the projection now asserts clause-level
provenance, precision tiers, review state, and binding status it did not carry.

## Honest, disclosed states (not bugs)

- review_status: draft — authored, not yet maintainer/independently reviewed.
  1.8.1 reaches maintainer_reviewed after a recorded pass against
  docs/REVIEW_METHOD.v1.md (manual_source_locator_review.v1).
- field_binding_status: provisional_locator_bound — ELI locator + pinned-PDF hash
  present; official_text_sha256 pending. 1.8.1 seals it to text_verified.

## Verification performed (clean wheel, from /tmp)

- 94 tests pass. Three gates PASS (catalogue strict, vectors, source-atoms incl.
  identity-hash recompute).
- Required: 15/15 template-cell bound = 100%. Precision tiers
  template_field:15, template_section:9, obligation_context:3.
- lint-report, source-coverage, explain-field, compare-schema all resolve from
  site-packages. Identity hashes recompute from the installed package.
- verify-profile-view: OK, review_status: draft.

---

# Mint checklist (run in Codespaces before PyPI upload)

    # 0. Branch
    git checkout main && git pull && git checkout -b release/1.8.0

    # 1. Confirm version
    grep '^version' pyproject.toml          # -> 1.8.0

    # 2. Install + dev deps
    pip install -e . jsonschema jcs pytest build twine

    # 3. Tests + all three gates (must all pass)
    pytest -q                                # -> 94 passed
    python scripts/validate_catalogue.py --strict
    python scripts/validate_vectors.py
    python scripts/validate_source_atoms.py  # -> RESULT: PASS, identity hashes recompute

    # 4. Build NATIVELY in Codespaces, then clean-venv verify
    python -m build
    python -m venv /tmp/verify && /tmp/verify/bin/pip install dist/*.whl jsonschema
    /tmp/verify/bin/python - <<'PY'
    from actproof_events.exports import build_profile_view, verify_profile_view, write_profile_view
    ACT='op:eu.dora.ict_incident_notification_initial.v1'
    write_profile_view(ACT,'/tmp/v.json'); v=build_profile_view(ACT)
    assert v['profile_semantic_hash']=='sha256:a86a219365f5831af53332bc667095d5f70103130bae037354bcd13ded3e7d9e'
    r=verify_profile_view('/tmp/v.json'); assert r['ok'] and r['review_status']=='draft'
    print('clean-wheel verify OK')
    PY

    # 5. Commit, push, CI green
    git add -A && git commit -m "actproof-events 1.8.0: field-level source binding (market-aligned)"
    git push -u origin release/1.8.0
    # wait for GitHub Actions: catalogue + vectors + source-atoms jobs green

    # 6. Merge, tag
    git checkout main && git merge --no-ff release/1.8.0 -m "Release 1.8.0"
    git tag -a v1.8.0 -m "actproof-events 1.8.0 - field-level source binding"
    git push origin main --tags

    # 7. Publish
    twine check dist/*
    twine upload dist/*                       # __token__ / PyPI token

    # 8. Confirm from the live index
    pip index versions actproof-events        # -> 1.8.0 listed


## Final 1.8.0 release posture

This release deliberately stays inside pre-validation territory. It does not implement streaming incident sessions, evidence storage, tenant state, JWT/JWKS production auth, timestamping, signing or ledger anchoring. Those belong to the later pre-validation runtime and actproof-py verification bridge.

Market-facing source-binding claim:

- 15/15 required DORA initial-notification fields are template-field bound.
- 12 optional fields carry experimental contextual derivations.
- Optional contextual derivations are exported and inspectable, but they do not count as template-field release coverage.
- The derivation review gate remains draft: authored and inspectable, not yet maintainer-reviewed or independently reviewed.
- Official text hashes remain pending: source atoms are provisional locator-bound using ELI/CELEX locators and pinned source-document hashes.

Agent-facing surfaces added in the final build:

- MCP: `explain_field_source`, `source_coverage`, `lint_report`, `prevalidate_report`.
- REST: package-version metadata and `/v1/profiles/{act_id}/prevalidate-report`.
- CLI: `prevalidate-report`.
- Services: `prevalidate_report()` with deterministic `prevalidation_status`.

The correct product description is: source-bound DORA profile with agent-readable pre-validation primitives. It is not yet a stateful DORA incident-reporting MCP streaming server.
