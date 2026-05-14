#!/usr/bin/env bash
#
# deploy-v1.4-rc1.sh
#
# Deployment script for openproof-events v1.4-rc1.
#
# Walks through pre-flight checks, dependency installation, the seven pre-tag
# verifications from docs/releases/v1.4-rc1.md, commit with a structured
# message, annotated tag, push to the remote, and post-push verification.
#
# Usage:
#   ./scripts/deploy-v1.4-rc1.sh             # Interactive, default
#   ./scripts/deploy-v1.4-rc1.sh --dry-run   # Run all checks, do not commit/push
#   ./scripts/deploy-v1.4-rc1.sh --yes       # Skip confirmation prompts
#
# Prerequisites:
#   - Run from the openproof-events repository root.
#   - Python 3 available; jsonschema and jcs packages are auto-installed if missing.
#   - Git remote 'origin' configured with push access.

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

TAG_NAME="v1.4-rc1"
REMOTE_NAME="origin"
BRANCH_NAME="main"

# ============================================================================
# Argument parsing
# ============================================================================

SKIP_CONFIRMATIONS=false
DRY_RUN=false

for arg in "$@"; do
    case "$arg" in
        --yes|-y)
            SKIP_CONFIRMATIONS=true
            ;;
        --dry-run|-n)
            DRY_RUN=true
            ;;
        --help|-h)
            grep '^#' "$0" | head -25
            exit 0
            ;;
        *)
            printf "Unknown argument: %s\n" "$arg" >&2
            printf "Run with --help for usage.\n" >&2
            exit 2
            ;;
    esac
done

# ============================================================================
# Output helpers
# ============================================================================

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; BOLD=''; NC=''
fi

ok()      { printf "${GREEN}[OK]${NC}  %s\n" "$*"; }
fail()    { printf "${RED}[FAIL]${NC} %s\n" "$*" >&2; exit 1; }
warn()    { printf "${YELLOW}[WARN]${NC} %s\n" "$*"; }
info()    { printf "${BLUE}[INFO]${NC} %s\n" "$*"; }
section() { printf "\n${BOLD}%s${NC}\n%s\n" "$*" "------------------------------------------------------------"; }

confirm() {
    if [ "$SKIP_CONFIRMATIONS" = true ]; then
        info "Auto-confirmed (--yes): $*"
        return 0
    fi
    local prompt="$*"
    while true; do
        printf "${YELLOW}[?]${NC}    %s [y/N]: " "$prompt"
        read -r reply
        case "$reply" in
            [Yy]|[Yy][Ee][Ss])
                return 0
                ;;
            ""|[Nn]|[Nn][Oo])
                warn "Aborted by user at confirmation step."
                exit 1
                ;;
            *)
                printf "Please answer yes or no.\n"
                ;;
        esac
    done
}

# ============================================================================
# Phase 1: Pre-flight
# ============================================================================

section "Phase 1: Pre-flight checks"

# Repository root check
if [ ! -f "spec/openproof-events.spec.md" ] || [ ! -f "CATALOGUE_LOADER_CONTRACT.md" ]; then
    fail "Not in repository root. cd to the openproof-events directory first."
fi
ok "Running from repository root"

# Git repository check
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    fail "Not a git repository. Run 'git init' or clone the repo first."
fi
ok "Git repository detected"

# Git identity check
GIT_USER_NAME=$(git config --get user.name 2>/dev/null || echo "")
GIT_USER_EMAIL=$(git config --get user.email 2>/dev/null || echo "")
if [ -z "$GIT_USER_NAME" ] || [ -z "$GIT_USER_EMAIL" ]; then
    fail "Git user.name or user.email is unset. Configure with:
       git config user.name 'Your Name'
       git config user.email 'you@example.com'"
fi
ok "Git identity: $GIT_USER_NAME <$GIT_USER_EMAIL>"

# Remote check
if ! git remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
    fail "Git remote '$REMOTE_NAME' not configured. Add it with:
       git remote add origin <url>"
fi
REMOTE_URL=$(git remote get-url "$REMOTE_NAME")
ok "Remote $REMOTE_NAME: $REMOTE_URL"

# Branch check
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "DETACHED")
if [ "$CURRENT_BRANCH" = "DETACHED" ]; then
    fail "Detached HEAD. Check out a branch first."
fi
if [ "$CURRENT_BRANCH" != "$BRANCH_NAME" ]; then
    warn "Current branch is '$CURRENT_BRANCH', expected '$BRANCH_NAME'."
    confirm "Continue deploying from '$CURRENT_BRANCH'?"
fi
ok "On branch: $CURRENT_BRANCH"

# Tag does not exist locally
if git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
    fail "Tag $TAG_NAME already exists locally. Delete with:
       git tag -d $TAG_NAME
   if you intend to recreate it."
fi
ok "Tag $TAG_NAME does not exist locally"

# Tag does not exist remotely
info "Checking remote for existing tag (may require network)..."
if git ls-remote --tags "$REMOTE_NAME" "refs/tags/$TAG_NAME" 2>/dev/null | grep -q "$TAG_NAME"; then
    fail "Tag $TAG_NAME already exists on $REMOTE_NAME. Delete remotely with:
       git push $REMOTE_NAME :refs/tags/$TAG_NAME
   if you intend to recreate it."
fi
ok "Tag $TAG_NAME does not exist on remote"

# ============================================================================
# Phase 2: Dependencies
# ============================================================================

section "Phase 2: Python dependencies"

if ! command -v python3 >/dev/null 2>&1; then
    fail "python3 not in PATH. Install Python 3 and retry."
fi
ok "python3 available: $(python3 --version)"

for pkg in jsonschema jcs; do
    if python3 -c "import $pkg" >/dev/null 2>&1; then
        ok "Python package '$pkg' available"
    else
        info "Installing Python package '$pkg' ..."
        python3 -m pip install --quiet --user "$pkg" 2>/dev/null \
            || python3 -m pip install --quiet --break-system-packages "$pkg" \
            || fail "Failed to install $pkg. Install manually:
       python3 -m pip install $pkg"
        ok "Python package '$pkg' installed"
    fi
done

# ============================================================================
# Phase 3: Pre-tag verifications
# ============================================================================

section "Phase 3: Pre-tag verifications"

# Verification 1: schema validates against draft 2020-12 meta-schema
python3 - >/dev/null 2>&1 <<'PYEOF' || fail "Schema validation failed against draft 2020-12 meta-schema"
import json
from jsonschema import Draft202012Validator
with open('spec/schemas/act_catalogue_entry.v2.json') as f:
    schema = json.load(f)
Draft202012Validator.check_schema(schema)
PYEOF
ok "v2 schema validates against draft 2020-12 meta-schema"

# Verification 2: both v2 catalogue entries validate against the schema
python3 - >/dev/null 2>&1 <<'PYEOF' || fail "One or more v2 catalogue entries failed schema validation"
import json, sys
from jsonschema import Draft202012Validator
with open('spec/schemas/act_catalogue_entry.v2.json') as f:
    schema = json.load(f)
validator = Draft202012Validator(schema)
for path in [
    'catalogue/acts/eu/nis2/art20/management_body_approval.v1.json',
    'catalogue/acts/eu/eudr/dds_preparation.v1.json',
]:
    with open(path) as f:
        entry = json.load(f)
    errors = list(validator.iter_errors(entry))
    if errors:
        for e in errors:
            print(f"{path}: {e.message}", file=sys.stderr)
        sys.exit(1)
PYEOF
ok "Both v2 catalogue entries validate against the schema"

# Verification 3 and 4: test vectors match fresh regeneration (determinism)
TMPDIR_DEPLOY=$(mktemp -d)
trap "rm -rf $TMPDIR_DEPLOY" EXIT

python3 scripts/compute_test_vectors.py \
    catalogue/acts/eu/nis2/art20/management_body_approval.v1.json \
    scripts/test_vector_inputs/nis2_art20_v1_001.json \
    "$TMPDIR_DEPLOY/nis2_fresh.json" >/dev/null 2>&1 \
    || fail "NIS2 test vector regeneration failed"

if ! diff -q catalogue/acts/eu/nis2/art20/management_body_approval.v1.test_vectors.json \
              "$TMPDIR_DEPLOY/nis2_fresh.json" >/dev/null 2>&1; then
    fail "NIS2 committed test vector does not match fresh regeneration. Refresh with:
       python3 scripts/compute_test_vectors.py \\
           catalogue/acts/eu/nis2/art20/management_body_approval.v1.json \\
           scripts/test_vector_inputs/nis2_art20_v1_001.json \\
           catalogue/acts/eu/nis2/art20/management_body_approval.v1.test_vectors.json"
fi
ok "NIS2 test vector is deterministic and matches committed file"

python3 scripts/compute_test_vectors.py \
    catalogue/acts/eu/eudr/dds_preparation.v1.json \
    scripts/test_vector_inputs/eudr_dds_v1_001.json \
    "$TMPDIR_DEPLOY/eudr_fresh.json" >/dev/null 2>&1 \
    || fail "EUDR test vector regeneration failed"

if ! diff -q catalogue/acts/eu/eudr/dds_preparation.v1.test_vectors.json \
              "$TMPDIR_DEPLOY/eudr_fresh.json" >/dev/null 2>&1; then
    fail "EUDR committed test vector does not match fresh regeneration. Refresh with:
       python3 scripts/compute_test_vectors.py \\
           catalogue/acts/eu/eudr/dds_preparation.v1.json \\
           scripts/test_vector_inputs/eudr_dds_v1_001.json \\
           catalogue/acts/eu/eudr/dds_preparation.v1.test_vectors.json"
fi
ok "EUDR test vector is deterministic and matches committed file"

# Verification 5: no voting derivatives in non-deprecated v2 paths
if grep -rn 'method_constraints\|tally_output_hash\|result_hash\|eligibility_snapshot_hash\|action_set_hash\|receipt_profile_recommendations' \
    catalogue/acts/ \
    --include='*.json' \
    --exclude-dir='_deprecated' >/dev/null 2>&1; then
    grep -rn 'method_constraints\|tally_output_hash\|result_hash\|eligibility_snapshot_hash\|action_set_hash\|receipt_profile_recommendations' \
        catalogue/acts/ \
        --include='*.json' \
        --exclude-dir='_deprecated' >&2
    fail "Voting derivative fields found in non-deprecated v2 entry paths (see above)"
fi
ok "No voting derivative fields in non-deprecated v2 entry paths"

# Verification 6: all deprecated v1 entries reachable
for path in \
    catalogue/acts/eu/nis2/art20/_deprecated/approval.json \
    catalogue/acts/eu/nis2/art20/_deprecated/README.md \
    catalogue/acts/corporate/_deprecated/board_resolution_v1.json \
    catalogue/acts/corporate/_deprecated/README.md \
    catalogue/acts/eu/ai_act/art26/_deprecated/risk_assessment.json \
    catalogue/acts/eu/ai_act/art26/_deprecated/README.md
do
    if [ ! -f "$path" ]; then
        fail "Missing deprecated file: $path"
    fi
done
ok "All deprecated v1 entries reachable for historical resolution"

# Verification 7: all Batch A deliverables present
for path in \
    CATALOGUE_LOADER_CONTRACT.md \
    spec/openproof-events.spec.md \
    spec/schemas/act_catalogue_entry.v2.json \
    catalogue/acts/eu/nis2/art20/management_body_approval.v1.json \
    catalogue/acts/eu/nis2/art20/management_body_approval.v1.test_vectors.json \
    catalogue/acts/eu/eudr/dds_preparation.v1.json \
    catalogue/acts/eu/eudr/dds_preparation.v1.test_vectors.json \
    scripts/compute_test_vectors.py \
    scripts/test_vector_inputs/nis2_art20_v1_001.json \
    scripts/test_vector_inputs/eudr_dds_v1_001.json \
    docs/releases/v1.4-rc1.md
do
    if [ ! -f "$path" ]; then
        fail "Missing Batch A deliverable: $path"
    fi
done
ok "All Batch A deliverables present"

# ============================================================================
# Phase 4: Review pending changes
# ============================================================================

section "Phase 4: Review pending changes"

STATUS_OUTPUT=$(git status --short)
if [ -z "$STATUS_OUTPUT" ]; then
    info "Working tree is already clean. Nothing new to commit."
    HAS_CHANGES=false
else
    HAS_CHANGES=true
    echo ""
    info "Files with pending changes:"
    git status --short
    echo ""
    info "Summary of changes against HEAD:"
    git diff HEAD --stat 2>/dev/null || true
fi

if [ "$DRY_RUN" = true ]; then
    section "Dry run complete"
    info "All pre-tag verifications passed."
    info "No commit, tag, or push was performed."
    info "Run without --dry-run when ready to ship."
    exit 0
fi

# ============================================================================
# Phase 5: Commit
# ============================================================================

if [ "$HAS_CHANGES" = true ]; then
    section "Phase 5: Commit"
    confirm "Stage all changes and create the v1.4-rc1 commit?"

    git add .

    COMMIT_MSG="v1.4-rc1: act-native catalogue substrate

- Catalogue entry schema v2 (openproof.act_catalogue_entry.v2)
- New v2 entries: NIS2 Article 20 management body approval, EUDR DDS preparation
- All v1 entries moved to _deprecated/ for namespace continuity
- Deterministic test vectors via scripts/compute_test_vectors.py
- v1.4-rc1 specification with SCITT alignment downgrade, witness recipient
  model, and eIDAS firewall
- Federation flagged as v1.5+ feature
- CATALOGUE_LOADER_CONTRACT.md cross-implementation contract

Pre-release candidate. v1.4 final lands with Quoruna v2.0.0."

    git commit -m "$COMMIT_MSG"
    ok "Committed: $(git log -1 --oneline)"
else
    info "Skipping commit phase (working tree was clean)"
fi

# ============================================================================
# Phase 6: Tag
# ============================================================================

section "Phase 6: Annotated tag"

TAG_MSG="v1.4-rc1: act-native catalogue entry schema v2

- New JSON Schema spec/schemas/act_catalogue_entry.v2.json
- NIS2 Article 20 management body approval v1 (op:eu.nis2.art20.management_body_approval.v1)
- EUDR DDS preparation v1 (op:eu.eudr.dds_preparation.v1)
- All v1 entries preserved in _deprecated/ for namespace continuity
- Deterministic test vectors via scripts/compute_test_vectors.py
- Spec v1.4-rc1 with SCITT alignment downgraded to 'aligned, COSE_Sign1 bridge planned'
- Witness recipient model formally defined
- eIDAS firewall: issuer_record MUST NOT be claimed as AES or QES
- Federation flagged as v1.5+ feature
- CATALOGUE_LOADER_CONTRACT.md cross-implementation contract

This is a pre-release candidate. v1.4 final lands with Quoruna v2.0.0."

confirm "Create annotated tag $TAG_NAME?"
git tag -a "$TAG_NAME" -m "$TAG_MSG"
ok "Tagged $TAG_NAME locally"

# ============================================================================
# Phase 7: Push to remote
# ============================================================================

section "Phase 7: Push to public remote"

info "About to push the following to $REMOTE_NAME ($REMOTE_URL):"
info "  - Branch:  $CURRENT_BRANCH"
info "  - Tag:     $TAG_NAME (annotated)"
echo ""
warn "This is a public remote. The commit and tag will be visible to anyone."

confirm "Push commits and tag to $REMOTE_NAME?"

info "Pushing branch $CURRENT_BRANCH ..."
git push "$REMOTE_NAME" "$CURRENT_BRANCH"
ok "Pushed branch"

info "Pushing tag $TAG_NAME ..."
git push "$REMOTE_NAME" "$TAG_NAME"
ok "Pushed tag"

# ============================================================================
# Phase 8: Post-push verification
# ============================================================================

section "Phase 8: Post-push verification"

info "Fetching remote tags ..."
git fetch "$REMOTE_NAME" --tags --quiet

if git ls-remote --tags "$REMOTE_NAME" "refs/tags/$TAG_NAME" 2>/dev/null | grep -q "$TAG_NAME"; then
    ok "Tag $TAG_NAME confirmed on $REMOTE_NAME"
else
    warn "Tag push reported success but ls-remote did not confirm yet."
    warn "This is usually propagation delay. Re-check in a minute:"
    warn "    git ls-remote --tags $REMOTE_NAME $TAG_NAME"
fi

# Construct GitHub release URL (heuristic)
if [[ "$REMOTE_URL" == *"github.com"* ]]; then
    BASE_URL="${REMOTE_URL%.git}"
    BASE_URL="${BASE_URL/git@github.com:/https://github.com/}"
    RELEASE_URL="${BASE_URL}/releases/new?tag=${TAG_NAME}"
    TAG_URL="${BASE_URL}/releases/tag/${TAG_NAME}"
    echo ""
    info "Tag is browseable at:"
    info "    $TAG_URL"
    info ""
    info "Optionally create a GitHub release at:"
    info "    $RELEASE_URL"
    info "and paste the release notes from docs/releases/v1.4-rc1.md"
fi

section "Deployment complete"
ok "v1.4-rc1 tagged and pushed to $REMOTE_NAME"
echo ""
info "Next steps:"
info "  1. (Optional) Create the GitHub release using the URL above"
info "  2. Move on to Batch B in the Quoruna repository"
