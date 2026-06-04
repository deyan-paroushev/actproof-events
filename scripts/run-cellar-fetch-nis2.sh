#!/usr/bin/env bash
# run-cellar-fetch-nis2.sh
#
# Build-time helper for actproof-events. Fetches the two official EU
# instruments behind the NIS2 Article 23(4)(a) early-warning act profile,
# hashes them, writes a source_bindings fragment, and packages the result
# as nis2-sources.zip with the same internal layout as dora-sources.zip.
#
# Run from wherever you have placed cellar_fetch_nis2.py (it expects the
# script in the same directory, mirroring the DORA scripts/ layout):
#     ./run-cellar-fetch-nis2.sh
#
# Output:
#   ./build/nis2-sources/artefacts/32022L2555.pdf
#   ./build/nis2-sources/artefacts/32024R2690.pdf
#   ./build/nis2-sources/source-bindings.json
#   ./nis2-sources.zip            (zips the nis2-sources/ directory)
#
# cellar_fetch_nis2.py uses only the Python standard library, so there is
# nothing to pip install. It needs open outbound network to reach
# publications.europa.eu and eur-lex.europa.eu. It will NOT run inside a
# sandbox whose egress is restricted to a package-registry allowlist.
set -euo pipefail

OUT="${1:-./build/nis2-sources}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 was not found on PATH." >&2
  exit 1
fi

echo "actproof-events :: cellar source fetch (NIS2)"
echo "output directory: ${OUT}"
echo

python3 "${SCRIPT_DIR}/cellar_fetch_nis2.py" --out "${OUT}"

# Package to nis2-sources.zip with the directory named nis2-sources/ inside,
# matching the dora-sources.zip convention (dora-sources/ at the archive root).
PARENT="$(cd "$(dirname "${OUT}")" && pwd)"
BASE="$(basename "${OUT}")"
ZIP_TARGET="${PARENT}/nis2-sources.zip"

# Normalise the inner directory name to nis2-sources regardless of --out path.
STAGE="$(mktemp -d)"
mkdir -p "${STAGE}/nis2-sources"
cp -R "${OUT}/." "${STAGE}/nis2-sources/"
( cd "${STAGE}" && zip -r -q "${ZIP_TARGET}" nis2-sources )
rm -rf "${STAGE}"

echo
echo "Wrote ${ZIP_TARGET}"
echo
echo "Done. Next: review nis2-sources/source-bindings.json and the fetched"
echo "artefacts, then paste the two sha256 values into the NIS2 act profile's"
echo "source_bindings (replacing PENDING_CELLAR_FETCH), set generation.reconciled"
echo "to true once you have confirmed the field surface against the PDFs, and"
echo "upload nis2-sources.zip back so the build can continue."
