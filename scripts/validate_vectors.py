#!/usr/bin/env python3
"""
validate_vectors.py

Verify that every committed conformance test vector still matches the
deterministic output of compute_test_vectors.py.

A test vector is generated from a catalogue entry and a manifest input. If the
catalogue entry, the manifest, or the generator changes after a vector was
written, the committed vector goes stale: its stored hashes no longer match
what a verifier would recompute. validate_catalogue.py does not catch this. It
validates entries against the schema and never recomputes vector hashes.

This script closes that gap. For each vector it re-derives the whole vector
from the vector's own raw_manifest and the catalogue entry file that sits
beside it, using the exact logic in compute_test_vectors.py, then compares the
re-derivation field by field. Sharing the generator's code means the validator
and the generator cannot drift apart.

Two failure modes are reported distinctly:

  - stale: the vector re-derives but a stored field no longer matches, for
    example a manifest hash or an envelope hash.
  - non-conforming: the vector's manifest no longer validates against its
    catalogue entry, for example a required claim field was added to the
    profile after the vector was written.

The reference_anchor block is excluded from the comparison. It is meant to be
populated after a vector is anchored and is not part of the deterministic
derivation.

Exit status is 0 if every vector matches, 1 if any vector is stale, does not
conform, or cannot be read.

Usage:
    python scripts/validate_vectors.py
    python scripts/validate_vectors.py --root /path/to/repo

Dependencies:
    pip install jcs
"""

import argparse
import json
import sys
from pathlib import Path

# compute_test_vectors.py lives beside this script. Import its exact
# composition and hashing logic so the validator and the generator share a
# single source of truth and cannot drift apart.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import compute_test_vectors as ctv  # noqa: E402
except ImportError as exc:
    print(
        "ERROR: cannot import compute_test_vectors.py from "
        f"{Path(__file__).resolve().parent}: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(1)


# Fields that are not part of the deterministic derivation and are therefore
# not compared. reference_anchor is populated after a vector is anchored.
NON_DETERMINISTIC_KEYS = {"reference_anchor"}


def _truncate(value: str, limit: int = 88) -> str:
    """Format a string for an error line, shortening long canonical blobs.

    Hash fields are short and are shown in full. Canonical base64 fields can
    be several kilobytes, so they are cut to keep CI output readable.
    """
    if len(value) <= limit:
        return repr(value)
    return f"{value[:limit]!r}... ({len(value)} chars total)"


def catalogue_entry_for(vector_path: Path) -> Path:
    """Return the catalogue entry path that a vector file sits beside.

    A vector at <name>.test_vectors.json is generated from the catalogue
    entry <name>.json in the same directory.
    """
    stem = vector_path.name[: -len(".test_vectors.json")]
    return vector_path.with_name(stem + ".json")


def differing_keys(stored: dict, expected: dict) -> list[str]:
    """Return the top-level keys whose values differ between two vectors."""
    differing: list[str] = []
    for key in sorted(set(stored) | set(expected)):
        if key in NON_DETERMINISTIC_KEYS:
            continue
        if stored.get(key) != expected.get(key):
            differing.append(key)
    return differing


def validate_vector(vector_path: Path) -> list[str]:
    """Re-derive one vector and return a list of error strings, empty if OK."""
    try:
        stored = json.loads(vector_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read vector file: {exc}"]

    raw_manifest = stored.get("raw_manifest")
    if not isinstance(raw_manifest, dict):
        return ["vector has no object 'raw_manifest'"]

    entry_path = catalogue_entry_for(vector_path)
    if not entry_path.is_file():
        return [f"catalogue entry not found beside vector: {entry_path.name}"]

    try:
        catalogue_entry_bytes = entry_path.read_bytes()
        catalogue = json.loads(catalogue_entry_bytes.decode("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read catalogue entry {entry_path.name}: {exc}"]

    test_vector_id = stored.get("test_vector_id", vector_path.name)

    try:
        expected = ctv.compute_test_vector(
            catalogue=catalogue,
            catalogue_entry_bytes=catalogue_entry_bytes,
            raw_manifest=raw_manifest,
            test_vector_id=test_vector_id,
        )
    except ValueError as exc:
        # The manifest no longer validates against the catalogue entry: a
        # required claim field or evidence label was added, renamed, or removed
        # after the vector was written.
        return [f"manifest no longer conforms to catalogue entry: {exc}"]
    except Exception as exc:  # noqa: BLE001  - report, do not crash the run
        return [f"could not re-derive vector: {type(exc).__name__}: {exc}"]

    differing = differing_keys(stored, expected)
    if not differing:
        return []

    errors: list[str] = []
    for key in differing:
        stored_value = stored.get(key)
        expected_value = expected.get(key)
        if isinstance(stored_value, str) and isinstance(expected_value, str):
            errors.append(
                f"{key}: stored={_truncate(stored_value)} "
                f"recomputed={_truncate(expected_value)}"
            )
        else:
            errors.append(f"{key}: stored value does not match recomputed value")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify committed conformance test vectors against a fresh "
            "re-derivation. Exit 1 if any vector is stale."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: the parent of scripts/)",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    catalogue_dir = root / "catalogue" / "acts"
    if not catalogue_dir.is_dir():
        print(f"ERROR: catalogue directory not found: {catalogue_dir}", file=sys.stderr)
        return 1

    vector_paths = sorted(
        p
        for p in catalogue_dir.rglob("*.test_vectors.json")
        if "_deprecated" not in p.parts
    )

    print("actproof-events conformance vector validation")
    print(f"  catalogue: {catalogue_dir}")
    print()

    failed = 0
    for path in vector_paths:
        rel = path.relative_to(root)
        errors = validate_vector(path)
        if errors:
            failed += 1
            print(f"  STALE {rel}")
            for err in errors:
                print(f"        - {err}")
        else:
            print(f"  OK    {rel}")

    print()
    total = len(vector_paths)
    print(f"summary: {total} vectors, {total - failed} OK, {failed} stale or invalid")
    print(f"RESULT: {'PASS' if failed == 0 else 'FAIL'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
