#!/usr/bin/env bash
# actproof-events 1.5.0rc1 deploy.
# Run from the repo root as:   bash deploy-1.5.0rc1.sh
# Do NOT paste this into the terminal and do NOT run it as a VS Code task.
set -uo pipefail   # no -e during preflight: collect every failure

fail=0; warn=0
ok()   { printf '  ok    %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; fail=1; }
note() { printf '  warn  %s\n' "$1"; warn=1; }

echo "actproof-events 1.5.0rc1 deploy"
echo "== preflight =="
grep -q 'name = "actproof-events"' pyproject.toml 2>/dev/null \
  && ok "actproof-events repo root" || bad "not in actproof-events repo root"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  && ok "git repo, branch $(git branch --show-current)" || bad "not a git repository"

CRIT=( pyproject.toml LICENSES/CC0-1.0.txt actproof_events/__init__.py actproof_events/py.typed
  .github/workflows/validate-catalogue.yml scripts/validate_vectors.py scripts/validate_catalogue.py
  spec/actproof-events.spec.md spec/schemas/act_profile.v3.json
  catalogue/acts/eu/dora/ict_incident_notification_initial.v1.json
  catalogue/acts/eu/dora/ict_incident_notification_initial.v1.test_vectors.json
  catalogue/acts/eu/eudr/dds_preparation.v1.json
  catalogue/acts/eu/eudr/dds_preparation.v1.test_vectors.json
  catalogue/acts/eu/nis2/art20/management_body_approval.v1.json
  catalogue/acts/eu/nis2/art20/management_body_approval.v1.test_vectors.json
  catalogue/acts/actproof/software_release.v1.json
  catalogue/acts/actproof/software_release.v1.test_vectors.json
  catalogue/acts/actproof/standards_engagement_record.v1.json
  catalogue/acts/actproof/standards_engagement_record.v1.test_vectors.json
  catalogue/acts/democracy/civil_society_mandate.settlement.v1.json
  catalogue/acts/democracy/civil_society_mandate.settlement.v1.test_vectors.json
  CONTRIBUTING_ACTS.md README.md )
for f in "${CRIT[@]}"; do [ -f "$f" ] && ok "$f" || bad "missing: $f"; done
for f in docs/release-hardening-1.5.0rc1.md docs/releases/v1.4-rc1.md; do
  [ -f "$f" ] && ok "$f" || note "missing doc: $f"; done

grep -q 'version = "1.5.0rc1"' pyproject.toml && ok "pyproject 1.5.0rc1" || bad "pyproject not 1.5.0rc1"
grep -q '"1.5.0rc1"' actproof_events/__init__.py && ok "__init__ 1.5.0rc1" || bad "__init__ not 1.5.0rc1"
if [ -f spec/actproof-events.spec.md ]; then
  grep -q '^\*\*Version\*\*: v1.5-rc1' spec/actproof-events.spec.md \
    && ok "spec v1.5-rc1" || bad "spec is NOT v1.5-rc1 (place the updated spec)"
fi
if [ -f docs/releases/v1.4-rc1.md ]; then
  grep -q 'Historical document' docs/releases/v1.4-rc1.md \
    && ok "v1.4-rc1.md banner present" || note "v1.4-rc1.md missing historical banner"
fi

if [ "$fail" -ne 0 ]; then
  echo
  echo "PREFLIGHT FAILED. Fix the FAIL items above, then re-run. Nothing was pushed."
  exit 1
fi
[ "$warn" -ne 0 ] && echo "(warnings are non-blocking)"
echo "preflight passed."
echo

set -e   # abort on error from here

echo "== validators =="
python3 -m pip install --quiet --upgrade build twine jsonschema jcs
python3 scripts/validate_catalogue.py
python3 scripts/validate_vectors.py

echo "== git =="
git add -A
if git diff --cached --quiet; then
  echo "nothing staged, skipping commit"
else
  git commit -F- <<'MSG'
Release hardening 1.5.0rc1: spec v3, DORA reference profile, packaging

- Unify version to 1.5.0rc1 across pyproject, __init__, and the spec
- Update the spec to act_profile.v3 with the optional profile-block model
- Regenerate all six catalogue test vectors
- Add validate_catalogue.py and validate_vectors.py plus the CI workflow
- Bundle spec, vocabularies, version policy, and loader contract in the wheel
- Add py.typed, the CC0 license file, and the profile_status maturity block
- Add the DORA initial-notification reference profile, reliance overclaim reworded
- Rewrite CONTRIBUTING_ACTS.md and README to the v3 act model
- Mark docs/releases/v1.4-rc1.md historical
MSG
fi
git push origin "$(git branch --show-current)"

echo "== build =="
rm -rf dist build ./*.egg-info
python3 -m build
python3 -m twine check dist/*
ls -la dist/

read -r -p "Upload actproof-events 1.5.0rc1 to PyPI? [y/N] " up
if [ "${up:-}" = "y" ]; then
  python3 -m twine upload dist/*
else
  echo "upload skipped"
fi

if git rev-parse v1.5-rc1 >/dev/null 2>&1; then
  echo "tag v1.5-rc1 exists, skipping"
else
  git tag -a v1.5-rc1 -m "actproof-events v1.5-rc1: act_profile.v3 schema, DORA reference profile"
  git push origin v1.5-rc1
fi
echo "done."
