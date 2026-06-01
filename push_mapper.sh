#!/usr/bin/env bash
#
# push_mapper.sh
#
# Commits and pushes the ActProof Mapper (hybrid) into your actproof-events
# repository, from the terminal. It is deliberately cautious: it shows you what
# changed and asks for confirmation before committing, and again before pushing.
# Nothing is forced; nothing touches PyPI.
#
# HOW TO USE
# ----------
# 1. Unzip actproof-events-hybrid.zip. It contains a folder "actproof-events-main".
# 2. Copy its CONTENTS over your existing local clone of the repo (so the new
#    mapper/, the edited pyproject.toml, README.md, and actproof_events/cli.py
#    land in place). Easiest:
#
#       rsync -a actproof-events-main/  /path/to/your/actproof-events-clone/
#
#    (or just copy the files in your file manager)
#
# 3. From inside your repo clone, run:
#
#       bash push_mapper.sh
#
# It will: show status, show a diff summary, ask before committing, ask before
# pushing. You stay in control at each step.
#
# NOTE ON PyPI: this does git only. It does NOT build or publish a package. A
# PyPI release is a separate, later, deliberate step once schemas are frozen.

set -euo pipefail

# --- 0. sanity: are we inside the right repo? ---
if [ ! -f "pyproject.toml" ] || [ ! -d "mapper" ]; then
  echo "ERROR: run this from the root of your actproof-events clone."
  echo "Expected to find pyproject.toml and a mapper/ directory here."
  echo "Current directory: $(pwd)"
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: this directory is not a git repository."
  echo "Clone your repo first:  git clone <your-repo-url>"
  exit 1
fi

BRANCH="${1:-add-actproof-mapper}"
echo "============================================================"
echo "ActProof Mapper push"
echo "============================================================"
echo "Repo:    $(git remote get-url origin 2>/dev/null || echo '(no origin set)')"
echo "Branch:  will use '$BRANCH' (pass a different name as the first argument)"
echo ""

# --- 1. show what changed ---
echo "--- Files git sees as changed/new ---"
git add -A
git status --short
echo ""
echo "--- Summary of changes (insertions/deletions) ---"
git diff --cached --stat | tail -40
echo ""

# --- 2. confirm before committing ---
read -r -p "Commit these changes? [y/N] " ok
if [ "$ok" != "y" ] && [ "$ok" != "Y" ]; then
  echo "Aborted before commit. Nothing was committed. 'git reset' to unstage if you wish."
  exit 0
fi

# --- 3. create branch (if not already on it) and commit ---
CURRENT="$(git rev-parse --abbrev-ref HEAD)"
if [ "$CURRENT" != "$BRANCH" ]; then
  if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git checkout "$BRANCH"
  else
    git checkout -b "$BRANCH"
  fi
fi

git commit -m "Add experimental ActProof Mapper (hybrid): verified DORA source-to-profile pipeline

- Eight-step controlled pipeline (PDF -> profile JSON), runs end to end and
  verifies the four official DORA CELEX PDFs by SHA-256 (all_verified).
- Multi-proposal, host-neutral interpretation links (proposals + human
  affirmation + reserved vote slot); legacy flat list kept and deprecated.
- review_gate metadata carried through every step's output.
- Strict mode (--stop-on-warning) implemented at step level.
- AI-proposed interpretation links preserved as attributed, unaffirmed
  candidates; DORA mapping left unedited so warnings remain honest
  pending-affirmation markers. Final interpretive authority rests with humans.
- Exposed as repo-local CLI (actproof-mapper) via editable install; not on PyPI.

Experimental; not part of the published package."

echo ""
echo "Committed on branch '$BRANCH'."
echo ""

# --- 4. confirm before pushing ---
read -r -p "Push branch '$BRANCH' to origin now? [y/N] " push_ok
if [ "$push_ok" != "y" ] && [ "$push_ok" != "Y" ]; then
  echo "Committed locally but NOT pushed. When ready:  git push -u origin $BRANCH"
  exit 0
fi

git push -u origin "$BRANCH"

echo ""
echo "============================================================"
echo "Pushed branch '$BRANCH' to origin."
echo "Next: open a pull request on your repo's web UI to merge '$BRANCH'"
echo "into main, so the change goes through review (even if you self-merge)."
echo "============================================================"
