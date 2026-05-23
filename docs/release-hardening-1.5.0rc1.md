# ActProof Events: pre-release hardening for 1.5.0rc1

## Purpose

This document records the hardening pass for the `actproof-events` package
before its first PyPI publication, in response to an external code review.
It is the working register for that pass and the gate that must be satisfied
before `twine upload`.

Target release: `actproof-events 1.5.0rc1`, specification `1.5-rc1`, schema
`actproof.act_profile.v3`. The version number is a recommendation, see item B.

## Status of the review

The review's factual claims were verified against the repository. Every
empirical claim that could be checked held. The verdict stands: the current
state should not be published as-is. The problem is not that the repository
is broken. It is that several files still behave like a fast-moving
pre-release folder while the package presents itself as a standard layer.
This pass closes that gap.

## 1. Scope boundary: actproof-events vs actproof-py

The review draws on material from two packages. Keeping the boundary clear
is itself part of the fix.

`actproof-events`, this package, owns the act-profile catalogue, the JSON
schemas, the specification text, the loader contract, and the
profile-conformance vectors.

`actproof-py` owns receipt canonicalisation, the on-chain note, RFC 3161
timestamping, Algorand anchoring, and the rendered PDF and JSON receipt
artefacts.

The following review items are `actproof-py` or Quoruna matters. They are
tracked there, not in this pass:

- The rendered receipt PDF and JSON format. The target format is the
  `final-dora-proof-card` and `final-dora-receipt-full` set. This is receipt
  presentation, produced by the anchoring library.
- The NIS2 receipt PDF labels the anchor "Algorand mainnet" in its header
  while the anchor section and explorer URL are `algorand-testnet`. This is a
  rendering defect in the receipt generator.
- The on-chain note format. The anchored DORA receipt carries an actproof
  `{h, t, v}` note. The conformance vectors in this package model an ARC-2
  `{e, m, q, r, t}` note. Reconciling the two is a cross-package design item,
  noted as Tier 3 item M.

One related item this pass does NOT fix, but which the NGI0 submission
depends on: the existing mainnet DORA receipt (`txid XQOS4...`, anchored
2026-05-19) was produced against the pre-reconciliation profile. Its
`catalogue.entry_hash` is `sha256:0b827fac...`, the current profile file is
`sha256:5ddbba75...`. Its `schema_hash` is `sha256:c3b4c164...`, the current
schema is `sha256:c8b7224a...`. Its claim still carries the old `art_8_*`
classification criteria and lacks `financial_entity_type`. Before that
receipt can serve as coherent NGI0 evidence, a fresh receipt must be anchored
against the 1.5.0rc1 profile. That is an `actproof-py` action, sequenced
after this release.

## 2. Verification results

| Review claim | Checked | Result |
|---|---|---|
| Conformance vectors are stale | Recomputed every `manifest_hash_hex` from `raw_manifest` via JCS | Confirmed. `software_release`, `civil_society_mandate`, `eudr`, `nis2` are stale. `dora`, `standards_engagement_record` are sound. |
| Wheel does not ship the spec it claims to | Read `pyproject` wheel `force-include` | Confirmed. Only `catalogue/acts` and `spec/schemas` are included. |
| Format validation is not enforced | Read `validate_catalogue.py` | Confirmed. `Draft202012Validator` is built without a `FormatChecker`. |
| `CONTRIBUTING_ACTS.md` is stale | Searched the file | Confirmed. The body still references `act_profile.v1`, `method_constraints`, `quorum`, `basis_points`, `approval.json`. |
| DORA profile overclaims submission | Read `reliance_context` and `submission_evidence_policy` | Confirmed. The statement asserts submission. Submission evidence is `required: false`. |
| `Typing :: Typed` without `py.typed` | Checked the package directory | Confirmed. `py.typed` is absent. |
| Version drift | Read all version strings | Confirmed. `1.4.0rc1` and `1.4-rc1` and `v3` and two release-note files coexist. |
| Manifest shape differs from real receipts | Compared a real `actproof` receipt | Confirmed. Receipt uses `manifest.claim`. Conformance input uses `claim_fields`. |

## 3. Remediation register

Three tiers. Tier 1 must be green before `twine upload`. Tier 2 is strongly
recommended before the same upload, because PyPI releases are immutable.
Tier 3 is the post-release roadmap, and it is the work the NGI0 grant is
intended to fund.

A change to any profile file changes its entry hash and invalidates that
profile's vector. Any profile edited in this pass has its vector regenerated
as the final content step. See section 5.

### Tier 1: release blockers

**A. Regenerate the stale conformance vectors and add vector validation to CI.** `[ ]`
Review item 3. Four of six active vectors do not match their own stored hash.
`validate_catalogue.py` missed it because it validates entries against the
schema and does not recompute vector hashes.
Fix: regenerate all five non-DORA vectors with the corrected
`compute_test_vectors.py`, so the set is internally consistent and in one
format. Add `scripts/validate_vectors.py`, which recomputes
`manifest_hash_hex`, `manifest_canonical_b64`, and `envelope_hash` for every
vector, and wire it into the workflow next to `validate_catalogue.py`. The
regeneration validates each input against its profile, so if a profile and
its input have drifted the run fails and surfaces the bug. That is expected.
Lands in: the five `*.test_vectors.json` files, `scripts/validate_vectors.py`
(new), `.github/workflows/validate-catalogue.yml`.

**B. Unify the release version.** `[ ]`
Review item 1. The hard requirement is one coherent version string
everywhere. Recommended number: `1.5.0rc1`, spec `1.5-rc1`. Two files already
carry `v1.5-rc1` and the source-bound work is past the v1.4 line. It stays a
release candidate. A stable `1.x` would itself overclaim maturity at this
stage.
Lands in: `pyproject.toml`, `actproof_events/__init__.py` (both constants),
`spec/actproof-events.spec.md` (header), `README.md`. Mark
`docs/releases/v1.4-rc1.md` historical.

**C. Make the wheel carry what the documentation says it carries.** `[ ]`
Review item 2. The README and `__init__.py` state the specification is
bundled. The wheel does not contain it.
Fix: add the specification, vocabularies, schema version policy, and loader
contract to the wheel `force-include`. Add `get_spec_path`,
`get_vocabularies_path`, and `get_contract_path` accessors. A self-contained
package is the correct posture for a commons artefact.
Lands in: `pyproject.toml`, `actproof_events/__init__.py`.

**D. Remove the DORA submission overclaim.** `[ ]`
Review item 8. The `reliance_statement` asserts the notification "was
submitted to the named competent authority." The profile requires no evidence
of submission. A receipt under this profile would assert a fact it cannot
support. This is the exact class of claim the project exists to oppose, and
it mirrors the care already taken in Klimat, where the customer lodges and
the tool only prepares.
Fix: reword `reliance_statement` and the `issuer_role` text in
`reliance_context` so they assert what is actually proven, a
profile-conformant initial-notification record was prepared, and explicitly
disclaim that submission, receipt, or acceptance is proven unless a separate
submission-evidence artefact is attached and verified. Apply the same wording
to the transparency note if it repeats the claim. The full split into
preparation, submission, and acknowledgement profiles is Tier 3.
Lands in: `catalogue/acts/eu/dora/ict_incident_notification_initial.v1.json`,
`...v1.transparency.md` if affected.

**E. Rewrite the stale sections of CONTRIBUTING_ACTS.md.** `[ ]`
Review item 9. The opening is current. The body describes the abandoned
voting architecture.
Fix: rewrite the stale sections to the current profile-contribution model.
Add an explicit statement that the voting-era model is deprecated and that
new profiles must not use voting-method or quorum fields unless the act
itself is a voting act.
Lands in: `CONTRIBUTING_ACTS.md`.

**F. Enforce format validation.** `[ ]`
Review item 7. `format: date-time` and `format: email` are currently
annotations, not assertions.
Fix: `Draft202012Validator(schema, format_checker=FormatChecker())`. Apply
the same wherever the new `claim_schema` is validated.
Lands in: `scripts/validate_catalogue.py`.

**G. Add the typing marker.** `[ ]`
Review item 11. The `Typing :: Typed` classifier is set, `py.typed` is
absent.
Fix: add an empty `actproof_events/py.typed` and force-include it. The
package is genuinely typed, so keep the classifier.
Lands in: `actproof_events/py.typed` (new), `pyproject.toml`.

### Tier 2: strongly recommended before release

**H. Scope the README to the package.** `[ ]`
Review item 14. The README opens on the standard and the vision, including
anchoring to a public ledger, which `actproof-events` itself does not do.
Fix: rework the opening to describe what the package is, the catalogue,
schemas, and conformance vectors, and add a short "what this package can
prove" and "what it cannot prove" pair. The cannot-prove list is a strength
in a grant context.
Lands in: `README.md`.

**I. Make the mixed licensing explicit.** `[ ]`
Review item 10. The wheel contains both Apache-2.0 and CC0 artefacts.
Fix: state per-artefact licensing in one place. The lightweight option is
fine for this release: keep `license = "Apache-2.0"` for the package
metadata, bundle the CC0 text as a licence file, and state in the README
which artefacts are CC0.
Lands in: `pyproject.toml`, `README.md`, `LICENSES/` (new).

**J. Add a machine-readable maturity marker per profile.** `[ ]`
Review item 15. The README says in prose that DORA is source-bound and the
rest is migrating. That should be checkable.
Fix: add a `profile_status` block to each catalogue entry recording maturity,
source-bound state, transparency-note presence, and vector coverage. Add it
as an optional property in the schema.
Lands in: `spec/schemas/act_profile.v3.json`, all six active catalogue
entries.

**K. Add a real claim schema to the DORA profile.** `[ ]`
Review item 6. `claim_field_types` is a flat type map. It cannot express
enums, patterns, formats, array item types, or required versus optional
precisely.
Fix: add a `claim_schema` property holding a JSON Schema fragment for the
claim object, and author it for the DORA profile. Keep `required_claim_fields`
and `claim_field_types` as indices that must stay consistent with it. Optional
for the other profiles for now, required in CI for source-bound profiles.
Lands in: `spec/schemas/act_profile.v3.json`,
`catalogue/acts/eu/dora/ict_incident_notification_initial.v1.json`.

### Tier 3: roadmap, funded by the grant

These are specified, not dropped. They are the commons-layer hardening the
NGI0 application should name as the funded work.

**L. Full conformance vector set.** Review items 4 and 16. The current vectors
are one positive case per profile. A conformance suite needs valid-minimal,
valid-full, and a set of invalid cases per profile, with an explicit error
model, a vector-set schema, and a validator that checks failure semantics.
For the DORA reference profile a small set of negative vectors is high value
and may be pulled forward into this release if time allows.

**M. Harmonise the conformance-vector input shape with the receipt manifest.**
Review item 5. The conformance input uses `claim_fields`. The `actproof`
receipt manifest uses `claim` and `evidence`. The two should converge. This
is a deliberate schema decision and must be made with `actproof-py`, not
rushed before an immutable publish.

**N. Release manifest.** Review item 18. A `releases/actproof-events-1.5.0rc1.json`
recording the hash of every schema, profile, and vector in the release, with
a generator script. It makes the catalogue auditable as a unit and fits the
project's hash-everything design.

**O. pytest suite.** Review item 19. Wrap the validation logic in `tests/` so
the package has a conventional test suite, not only scripts.

**P. Robust resource access.** Review items 12 and 13. Move bundled-data
access to `importlib.resources` and add a loader that fails loudly when
expected data is absent. The current `Path(__file__).parent` approach works
for wheel installs but is not the standard mechanism.

## 4. Release gate

Before `twine upload`, all of the following must hold:

- `[ ]` Every Tier 1 item complete.
- `[ ]` `python scripts/validate_catalogue.py` passes.
- `[ ]` `python scripts/validate_vectors.py` passes for every active vector.
- `[ ]` `python -m build` produces an sdist and a wheel.
- `[ ]` The built wheel contains the catalogue, schemas, specification,
  vocabularies, version policy, and loader contract.
- `[ ]` `python -m twine check dist/*` passes.
- `[ ]` A clean-venv install imports `actproof_events` and resolves
  `get_catalogue_path`, `get_schema_path`, and `get_spec_path`.
- `[ ]` One version string across `pyproject.toml`, `__init__.py`, the
  specification, and the README.

## 5. Delivery sequence

One file per message, stop for review after each. Schema changes land before
the profiles that use them. Vector regeneration is the final content step, so
it captures every profile edit.

1. `scripts/validate_vectors.py`, plus a diagnostic regeneration of the four
   stale vectors. This surfaces any profile-input drift early.
2. `pyproject.toml`: version, wheel contents, licence files.
3. `actproof_events/__init__.py`: version constants and the new path
   accessors.
4. `actproof_events/py.typed` and the `validate-catalogue.yml` workflow
   update.
5. `scripts/validate_catalogue.py`: the format checker.
6. `spec/schemas/act_profile.v3.json`: the additive optional properties
   `profile_status` and `claim_schema`. Tier 2.
7. `catalogue/acts/eu/dora/ict_incident_notification_initial.v1.json`: the
   reliance reword, and, if Tier 2 is in scope, `profile_status` and
   `claim_schema`. Transparency note updated alongside if affected.
8. The five other catalogue entries: the `profile_status` block. Tier 2.
9. `CONTRIBUTING_ACTS.md`: rewrite of the stale sections.
10. `README.md`: scope and licensing.
11. Final regeneration of every test vector whose profile was edited. With
    Tier 1 only, this is DORA. With Tier 2, this is all six.

If Tier 2 is not taken before the release, steps 6 and 8 drop and step 11
regenerates DORA only.
