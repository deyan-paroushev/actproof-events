#!/usr/bin/env bash
# run-cellar-fetch.sh
#
# Build-time helper for actproof-events. Fetches the official EU Formex
# sources behind the DORA initial incident-notification act profile through
# the CELLAR REST API, hashes them, and writes a source_bindings fragment.
#
# Run from the repository root:
#     ./scripts/run-cellar-fetch.sh
#
# Output goes to ./build/dora-sources/ (artefacts/, notices/,
# source-bindings.json). The build/ directory is gitignored.
#
# cellar_fetch.py uses only the Python standard library, so there is nothing
# to pip install. It needs open outbound network to reach
# publications.europa.eu.
set -euo pipefail

OUT="${1:-./build/dora-sources}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 was not found on PATH." >&2
  exit 1
fi

echo "actproof-events :: cellar source fetch"
echo "output directory: ${OUT}"
echo

python3 "${SCRIPT_DIR}/cellar_fetch.py" --out "${OUT}"

echo
echo "Done. Next: review ${OUT}/source-bindings.json and the fetched"
echo "artefacts, then hand them to Step 3, source-binding the DORA profile."
