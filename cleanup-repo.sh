#!/usr/bin/env bash
# cleanup-repo.sh — stop tracking build tooling that was committed by mistake.
# The delta tarball, the mint script, and the runner are build artifacts, not
# package source; they should not live in the repo history. This does NOT change
# anything PyPI receives (the wheel/sdist are built from the package).
# Run from the repo root, AFTER the build, BEFORE (or after) the push.
set -euo pipefail

# 1. ignore them in future
for f in "actproof-events-*.tar.gz" "build-*.sh" "run-*.sh"; do
  grep -qxF "$f" .gitignore 2>/dev/null || echo "$f" >> .gitignore
done

# 2. untrack the specific files committed in 2.5.0 (keep them on disk)
for f in actproof-events-2.5.0-update.tar.gz build-2.5.0.sh run-2.5.0.sh; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    git rm --cached "$f"
    echo "  untracked: $f"
  fi
done

git add .gitignore
git commit -m "chore: stop tracking release build tooling (tarball, build/run scripts)"
echo "done. these files remain on disk but are no longer tracked."
echo "they will not appear in future commits."
