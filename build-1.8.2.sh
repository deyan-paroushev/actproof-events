#!/usr/bin/env bash
# ============================================================================
# build-1.8.2.sh  —  ActProof Events 1.8.2 trust release, minted in Codespaces.
#
# 1.8.2 is a TRUST release: no new surface area. It adds, computed from the
# existing catalogue (never stored):
#   - source-atom coverage (the missingness signal; 1 of 26 atoms unused)
#   - profile completeness / known-scope declaration
#   - field-ID non-universality policy (universal_claim: false)
#   - 4 new regression tests
#
# This script applies a small delta tarball onto the working tree, verifies,
# builds wheel+sdist, twine-checks, tags, and (optionally) uploads to PyPI.
#
# USAGE (from the repo root in a Codespace):
#   1) place actproof-events-1.8.2-update.tar.gz next to this script
#   2) chmod +x build-1.8.2.sh
#   3) ./build-1.8.2.sh            # build + verify + tag, NO upload
#      ./build-1.8.2.sh --upload   # also twine upload to PyPI
# ============================================================================
set -euo pipefail

UPDATE_TARBALL="${UPDATE_TARBALL:-actproof-events-1.8.2-update.tar.gz}"
DO_UPLOAD="no"
[ "${1:-}" = "--upload" ] && DO_UPLOAD="yes"

EXPECT_VERSION="1.8.2"
BASE_VERSION="1.8.1"

say() { printf '\n=== %s ===\n' "$*"; }

# --- 0. sanity: are we in the repo root, on a clean-ish tree? ----------------
say "0. preflight"
[ -f pyproject.toml ] || { echo "ERROR: run from the repo root (no pyproject.toml here)"; exit 1; }
[ -f "$UPDATE_TARBALL" ] || { echo "ERROR: update tarball not found: $UPDATE_TARBALL"; exit 1; }
CURRENT_VERSION="$(grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)".*/\1/')"
echo "current tree version: $CURRENT_VERSION"
if [ "$CURRENT_VERSION" != "$BASE_VERSION" ] && [ "$CURRENT_VERSION" != "$EXPECT_VERSION" ]; then
  echo "WARNING: expected to start from $BASE_VERSION (or already $EXPECT_VERSION); got $CURRENT_VERSION"
  echo "         continuing, but check this is the right tree."
fi

# --- 1. apply the delta ------------------------------------------------------
say "1. apply 1.8.2 delta tarball"
tar -tzf "$UPDATE_TARBALL" | sed 's/^/  patch: /'
tar -xzf "$UPDATE_TARBALL"
NEW_VERSION="$(grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)".*/\1/')"
echo "version after patch: $NEW_VERSION"
[ "$NEW_VERSION" = "$EXPECT_VERSION" ] || { echo "ERROR: version did not become $EXPECT_VERSION"; exit 1; }

# --- 2. install + test -------------------------------------------------------
say "2. install (editable) + run tests"
python -m pip install -q -e . 
python -m pip install -q pytest jsonschema rfc8785 jcs build twine >/dev/null 2>&1 || true
python -m pytest -q

# --- 3. verify the new behaviour is actually live ----------------------------
say "3. verify 1.8.2 features"
python - <<'PY'
import actproof_events as ae
from actproof_events.bank_operability import build_profile_lock, verify_profile_lock
ACT = "op:eu.dora.ict_incident_notification_initial.v1"
assert ae.__version__ == "1.8.2", ae.__version__
lock = build_profile_lock(ACT)
assert lock["profile"]["profile_semantic_hash"].startswith("sha256:")
assert lock["component_hashes"]["source_atoms_hash"].startswith("sha256:")
assert lock["profile_lock_hash"].startswith("sha256:")
res = verify_profile_lock(lock)
assert res["ok"] is True, res["mismatches"]
print(f"  version {ae.__version__} OK")
print(f"  lock pins: {lock['package']['version']} / {lock['profile']['profile_semantic_hash'][:24]}...")
print(f"  verify-profile-lock: ok={res['ok']}")
PY

# --- 4. build wheel + sdist from a clean dist/ -------------------------------
say "4. build wheel + sdist"
rm -rf dist build ./*.egg-info .pytest_cache
python -m build
ls -la dist/

# --- 5. twine check ----------------------------------------------------------
say "5. twine check"
python -m twine check dist/*

# --- 6. confirm the built wheel installs clean & runs ------------------------
say "6. clean-venv smoke test of the built wheel"
TMPV="$(mktemp -d)"
python -m venv "$TMPV"
"$TMPV/bin/pip" install -q "dist/actproof_events-${EXPECT_VERSION}-py3-none-any.whl"
"$TMPV/bin/python" -c "import actproof_events; assert actproof_events.__version__=='${EXPECT_VERSION}'; print('  wheel installs as', actproof_events.__version__)"
"$TMPV/bin/actproof-events" export-profile-lock op:eu.dora.ict_incident_notification_initial.v1 --out /tmp/smoke.lock
rm -rf "$TMPV"

# --- 7. git commit + tag -----------------------------------------------------
say "7. git commit + tag v${EXPECT_VERSION}"
git add -A
git commit -m "actproof-events ${EXPECT_VERSION}: trust release (profile lockfile (pinnable version+hashes), audit-anchored prevalidation reports)" || echo "  (nothing to commit)"
if git rev-parse "v${EXPECT_VERSION}" >/dev/null 2>&1; then
  echo "  tag v${EXPECT_VERSION} already exists, skipping"
else
  git tag -a "v${EXPECT_VERSION}" -m "actproof-events ${EXPECT_VERSION} trust release"
  echo "  tagged v${EXPECT_VERSION}"
fi

# --- 8. upload (only with --upload) ------------------------------------------
if [ "$DO_UPLOAD" = "yes" ]; then
  say "8. twine upload to PyPI"
  echo "  uploading dist/* — you will be prompted for your PyPI token"
  python -m twine upload dist/*
  echo "  pushing commit + tag"
  git push && git push --tags
else
  say "8. upload SKIPPED (run with --upload to publish)"
  echo "  to publish:  python -m twine upload dist/*"
  echo "  then:        git push && git push --tags"
fi

say "DONE — 1.8.2 built and verified."
