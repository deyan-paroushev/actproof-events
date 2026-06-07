#!/usr/bin/env bash
# Mint actproof-events 2.5.0 from the shipped 2.4.0 base + this delta.
# Official source-text capture pilot (DORA Article 19(1),(4),(6)).
# Run in Codespaces from the repo root. Uploads to PyPI only with --upload.
set -euo pipefail

EXPECT_VERSION="2.5.0"
BASE_VERSION="2.4.0"
DELTA="actproof-events-2.5.0-update.tar.gz"
ACT="op:eu.dora.ict_incident_notification_initial.v1"
DO_UPLOAD="no"
[ "${1:-}" = "--upload" ] && DO_UPLOAD="yes"

echo "== preflight =="
test -f "$DELTA" || { echo "missing $DELTA in cwd"; exit 1; }
CURRENT=$(grep -m1 '^version' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')
echo "repo version: $CURRENT (expecting base $BASE_VERSION)"

echo "== apply delta =="
tar -xzf "$DELTA" -C .
NEWV=$(grep -m1 '^version' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')
test "$NEWV" = "$EXPECT_VERSION" || { echo "version is $NEWV, expected $EXPECT_VERSION"; exit 1; }
grep -q '"'"$EXPECT_VERSION"'"' actproof_events/__init__.py || { echo "__init__ version not bumped"; exit 1; }
echo "version now $NEWV"

echo "== install =="
pip install -e ".[schema-validation]" >/dev/null 2>&1 || pip install -e . >/dev/null
python -c "import actproof_events; assert actproof_events.__version__ == '$EXPECT_VERSION'"

echo "== full test suite =="
python -m pytest -q

echo "== VERIFY BLOCK: official-text capture, on the installed package =="
python - "$ACT" <<'PY'
import sys
from actproof_events.text_capture import (
    compute_atom_text_coverage, validate_atom_text, verify_atom_official_text,
    atom_text_maturity,
)
from actproof_events.source_binding import list_source_atoms, compute_source_atom_identity_hash
ACT = sys.argv[1]

# 1. validate (re-hashes every captured atom; clean captures => no errors)
errs = validate_atom_text(ACT)
assert errs == [], f"validate-atom-text errors: {errs}"

# 2. coverage is the 3/26 pilot
cov = compute_atom_text_coverage(ACT)
assert cov["atoms_total"] == 26, cov["atoms_total"]
assert cov["text_captured_and_hashed"] == 3, cov["text_captured_and_hashed"]
assert cov["text_capture_status"] == "pilot"
assert cov["by_maturity"].get("M5_text_hashed_draft") == 3
assert cov["by_maturity"].get("M2_identity_hashed_locator_bound") == 23

# 3. each captured atom verifies AND its identity hash is unchanged by capture
captured = [a for a in list_source_atoms(ACT) if a.get("text_excerpt")]
assert len(captured) == 3
for a in captured:
    assert verify_atom_official_text(a)["ok"], a["source_atom_id"]
    assert a["atom_identity_sha256"] == compute_source_atom_identity_hash(a), \
        f"identity drift on {a['source_atom_id']}"
    assert a["binding_status"] == "provisional"   # schema enum verified|provisional; capture leaves it provisional
    assert a["text_capture_status"] == "captured_draft"   # capture axis carries progress
    assert a["text_review_status"] == "draft"   # captured != attested
    assert atom_text_maturity(a) == "M5_text_hashed_draft"
print("VERIFY OK: 3/26 captured & verified; identity hashes unchanged; review draft; validate-atom-text clean")
PY

echo "== CLI smoke =="
actproof-events atom-text-coverage "$ACT"
actproof-events validate-atom-text "$ACT"
actproof-events verify-atom-text "$ACT" >/dev/null && echo "verify-atom-text exit OK"
actproof-events export-atom-inventory "$ACT" --out /tmp/atom-inventory.json >/dev/null && echo "inventory export OK"

echo "== build =="
rm -rf dist build ./*.egg-info
python -m build
python -m twine check dist/*

# confirm captured atoms ship inside the wheel and re-verify from it
python - <<'PY'
import os, zipfile, json
from actproof_events.text_capture import verify_atom_official_text
whl = [f"dist/{n}" for n in os.listdir("dist") if n.endswith(".whl")][0]
z = zipfile.ZipFile(whl)
name = [n for n in z.namelist() if n.endswith("source_atoms.json")][0]
cap = [a for a in json.load(z.open(name))["source_atoms"] if a.get("text_excerpt")]
assert len(cap) == 3, f"wheel ships {len(cap)} captured atoms, expected 3"
assert all(verify_atom_official_text(a)["ok"] for a in cap), "a wheel atom failed verify"
print("wheel ships 3 captured atoms; all verify OK")
PY

echo "== git =="
git add -A
git commit -m "actproof-events $EXPECT_VERSION: official source-text capture pilot (DORA Art 19(1),(4),(6)); text_capture module + CLI"
git tag "v$EXPECT_VERSION"

if [ "$DO_UPLOAD" = "yes" ]; then
  echo "== upload to PyPI =="
  python -m twine upload dist/*
  git push && git push --tags
else
  echo "== built, committed, tagged. Re-run with --upload to publish to PyPI. =="
fi
