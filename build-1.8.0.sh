#!/usr/bin/env bash
# actproof-events 1.8.0 — Codespaces build & mint sequence
# Wheel + sdist are built NATIVELY here for clean provenance.
# Run from the repo root of the published actproof-events (currently at 1.7.0).
#
# Usage:
#   1) put actproof-events-1.7.0-to-1.8.0-update.tar.gz somewhere reachable
#   2) bash build-1.8.0.sh /absolute/path/to/actproof-events-1.7.0-to-1.8.0-update.tar.gz
#
set -euo pipefail

UPDATE_TARBALL="${1:?Pass the path to actproof-events-1.7.0-to-1.8.0-update.tar.gz}"
EXPECTED_SEMANTIC="sha256:4309e6c004401a5a00b37cdea54651ac820bdf382b13fd0ba879cb05c8fd9ae5"
EXPECTED_ARTIFACT="sha256:47d18f80bf33884c06e4266eeb0fcb57a8e2ffc7b19d0942ba60a01a3f52bb94"
ACT="op:eu.dora.ict_incident_notification_initial.v1"

echo "==> 0. Sanity: are we in the actproof-events repo root?"
test -f pyproject.toml || { echo "ERROR: run from repo root (no pyproject.toml here)"; exit 1; }
echo "    current version: $(grep '^version' pyproject.toml)"

echo "==> 1. Branch"
git checkout main
git pull --ff-only
git checkout -b release/1.8.0

echo "==> 2. Apply the 1.7.0 -> 1.8.0 update bundle"
tar -xzf "$UPDATE_TARBALL" -C .
echo "    new version: $(grep '^version' pyproject.toml)"   # -> 1.8.0
grep -q 'version = "1.8.0"' pyproject.toml || { echo "ERROR: version is not 1.8.0 after applying update"; exit 1; }

echo "==> 3. Show what changed (sanity-check the diff is only the expected files)"
git status --short

echo "==> 4. Clean env + install with dev deps"
rm -rf .venv dist build ./*.egg-info
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -e . jsonschema jcs pytest build twine

echo "==> 5. Tests (must be 94 passed)"
pytest -q

echo "==> 6. All three conformance gates"
python scripts/validate_catalogue.py --strict
python scripts/validate_vectors.py
python scripts/validate_source_atoms.py   # includes atom-identity-hash recompute

echo "==> 7. Build wheel + sdist NATIVELY in this environment"
python -m build
ls -l dist/

echo "==> 8. Clean-venv verification against the expected canonical hashes"
deactivate || true
rm -rf /tmp/verify180
python3 -m venv /tmp/verify180
/tmp/verify180/bin/pip install --upgrade pip >/dev/null
/tmp/verify180/bin/pip install dist/*.whl jsonschema
/tmp/verify180/bin/python - "$ACT" "$EXPECTED_SEMANTIC" "$EXPECTED_ARTIFACT" <<'PY'
import sys
from actproof_events.exports import build_profile_view, verify_profile_view, write_profile_view
from actproof_events.source_binding import verify_source_atom_identity_hash, source_atom_index
ACT, exp_sem, exp_art = sys.argv[1], sys.argv[2], sys.argv[3]
write_profile_view(ACT, "/tmp/v.json")
v = build_profile_view(ACT)
assert v["profile_semantic_hash"] == exp_sem, f"semantic mismatch: {v['profile_semantic_hash']}"
assert v["profile_artifact_hash"] == exp_art, f"artifact mismatch: {v['profile_artifact_hash']}"
assert all(verify_source_atom_identity_hash(a) for a in source_atom_index(ACT).values()), "identity hash recompute failed"
r = verify_profile_view("/tmp/v.json")
assert r["ok"] is True, "verify_profile_view not OK"
assert r["review_status"] == "draft", "review_status drifted from draft"
cov = v["coverage"]["field_source_basis"]
assert cov["field_level"] == 15, f"field_source_basis.field_level should be 15, got {cov['field_level']}"
print("clean-wheel verify OK")
print("  semantic:", v["profile_semantic_hash"])
print("  artifact:", v["profile_artifact_hash"])
print("  field_source_basis.field_level:", cov["field_level"], "(15 = release-gated, not 27)")
print("  review_status:", r["review_status"])
PY

echo "==> 9. twine check"
twine check dist/*

echo "==> 10. Commit + push the release branch"
git add -A
git commit -m "actproof-events 1.8.0: field-level source binding (market-aligned, pre-validation primitives)"
git push -u origin release/1.8.0
echo "    --> wait for GitHub Actions (catalogue + vectors + source-atoms jobs) to go GREEN before continuing"

cat <<'NEXT'

================  MANUAL STEPS AFTER CI IS GREEN  ================

# 11. Merge + tag
git checkout main
git merge --no-ff release/1.8.0 -m "Release 1.8.0"
git tag -a v1.8.0 -m "actproof-events 1.8.0 - field-level source binding"
git push origin main --tags

# 12. Publish to PyPI (username: __token__, password: your PyPI token)
twine upload dist/*

# 13. Confirm from the live index
pip index versions actproof-events           # -> 1.8.0 listed
# optional full post-publish check:
python3 -m venv /tmp/post && /tmp/post/bin/pip install "actproof-events==1.8.0" jsonschema
/tmp/post/bin/python -c "import actproof_events as a; print('live:', a.__version__)"

=================================================================
NEXT

echo "==> Build sequence complete through push. Finish steps 11-13 after CI is green."
