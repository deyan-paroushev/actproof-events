#!/usr/bin/env bash
# run-2.5.0.sh — runner for the actproof-events 2.5.0 release.
#
# It places the two release files into the repo root, runs the mint script
# (which applies the delta, bumps the version, tests, builds, commits, tags),
# and optionally publishes to PyPI.
#
# USAGE (from anywhere; pass the path to your cloned actproof-events repo):
#   bash run-2.5.0.sh /path/to/actproof-events            # build, no upload
#   bash run-2.5.0.sh /path/to/actproof-events --upload   # build + publish
#
# If you are ALREADY inside the repo root, you can omit the path:
#   bash run-2.5.0.sh .            # or
#   bash run-2.5.0.sh . --upload
#
# Expects these two files to sit next to this script:
#   actproof-events-2.5.0-update.tar.gz
#   build-2.5.0.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${1:-.}"
UPLOAD_FLAG="${2:-}"

DELTA="actproof-events-2.5.0-update.tar.gz"
MINT="build-2.5.0.sh"

echo "== checks =="
for f in "$DELTA" "$MINT"; do
  test -f "$HERE/$f" || { echo "ERROR: $f not found next to this runner ($HERE)"; exit 1; }
done
test -d "$REPO" || { echo "ERROR: repo path not found: $REPO"; exit 1; }
test -f "$REPO/pyproject.toml" || { echo "ERROR: $REPO does not look like the repo root (no pyproject.toml)"; exit 1; }
grep -q 'name = "actproof-events"' "$REPO/pyproject.toml" 2>/dev/null \
  || grep -q 'actproof' "$REPO/pyproject.toml" \
  || { echo "ERROR: $REPO/pyproject.toml is not the actproof-events project"; exit 1; }

REPO="$(cd "$REPO" && pwd)"
echo "  repo:    $REPO"
echo "  files:   $HERE/$DELTA"
echo "           $HERE/$MINT"
[ "$UPLOAD_FLAG" = "--upload" ] && echo "  mode:    BUILD + UPLOAD to PyPI" || echo "  mode:    build only (no upload)"

echo "== place release files into repo root =="
cp "$HERE/$DELTA" "$REPO/$DELTA"
cp "$HERE/$MINT"  "$REPO/$MINT"
chmod +x "$REPO/$MINT"

echo "== run the mint script from the repo root =="
cd "$REPO"
if [ "$UPLOAD_FLAG" = "--upload" ]; then
  bash "$MINT" --upload
else
  bash "$MINT"
fi

echo "== done =="
echo "Built actproof-events 2.5.0 in $REPO/dist:"
ls -1 "$REPO/dist" 2>/dev/null || true
if [ "$UPLOAD_FLAG" != "--upload" ]; then
  echo
  echo "Not published yet. To publish to PyPI, re-run with --upload:"
  echo "  bash run-2.5.0.sh \"$REPO\" --upload"
  echo "(twine will prompt for your PyPI token, or read it from ~/.pypirc / TWINE_* env vars.)"
fi
