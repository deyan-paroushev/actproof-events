# Release notes: actproof-events 2.9.0

## Summary

2.9.0 extends local COSE registration to a second typed statement, so a
profile-dependency statement can be COSE-signed, registered into the local
transparency-pilot log, and receipt-verified through the same path that
already serves source-atom statements. This makes the source-dependency
continuity worked example receipted end to end, rather than receipting only
the source-atom substrate.

This is a backward-compatible minor release. Existing `actproof/source-atom/v1`
callers are unchanged; the full test suite (203 passed, 10 skipped) confirms the
existing contract still holds.

## What changed

New:

- `actproof_events/statement_profiles.py`: a typed statement registry. It maps a
  `statement_type` to its validator and commitment extractor, and dispatches
  `validate_statement`. Supported types: `actproof/source-atom/v1` and the new
  `actproof/profile-dependency/v1`.
- `spec/schemas/scitt_source_atom_statement.v1.schema.json` and the `spec/scitt/`
  schema for the source-atom statement.

Modified:

- `actproof_events/scitt_registration.py` (+37 / -44): `register_signed_statement`
  and the local-receipt verification now dispatch through the typed registry, so
  they accept any supported statement type rather than source-atom only. The
  source-atom behaviour is preserved.
- `actproof_events/cose_signing.py` (+51 / -23): COSE signing and verification
  accept the supported typed statements, carrying the statement type as the COSE
  content type.
- `actproof_events/dora_continuity_demo.py`: the worked example now COSE-signs,
  registers and verifies the profile-dependency v1 and v2 statements, and binds
  the downstream record to the v1 dependency root, v1 statement hash and v1
  receipt hash. The continuity check compares receipted objects.
- `actproof_events/__main__.py`: adds the `demo` and `quickstart` subcommands;
  the `quickstart` import is guarded so a build without the module degrades
  gracefully instead of raising `ModuleNotFoundError`.
- `actproof_events/exports.py`: exposes the demo through the installed console
  path as well.
- `actproof_events/quickstart.py`: routes to the worked demo.

Unchanged:

- `actproof_events/scitt_profile.py` and the rest of the public API.

## Boundary, stated plainly

This release ships a **local transparency-pilot**. Receipts are produced and
verified locally. No external SCITT Transparency Service registration is
claimed. The worked example still uses summary descriptors for 2025/301 and one
2025/302 atom (labelled as such); Article 19(1) and 2025/302 Article 1(1)(a) are
verbatim official-text excerpts. The continuity result is `NEEDS_REVIEW` with
`legal_conclusion: not_assessed`: no compliance or legal-sufficiency
determination is made.

## Verification

See `PROD_VERIFICATION_LOG.txt`: full suite 203 passed / 10 skipped; the demo
(default and verbose), quickstart and the exports CLI path all exit 0;
profile-dependency v1 and v2 receipts verify with `verify_local_receipt`; the
committed example receipts verify from the committed tree alone; no private key
is committed.

## Next horizon (not in 2.9.0)

External SCITT Transparency Service registration; more verbatim 2025/301 and
2025/302 atoms beyond the current set; published JSON schemas for every object
type (profile_dependency_statement, downstream_binding, continuity_assessment,
local_receipt); release-assurance artifacts (SBOM, signed package).
