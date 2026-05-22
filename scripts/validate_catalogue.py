#!/usr/bin/env python3
"""
validate_catalogue.py

Validate every ActProof Events catalogue entry against its JSON Schema.

This is the catalogue conformance gate. It walks catalogue/acts/, validates
each entry against the schema for its discriminator in spec/schemas/, checks
for duplicate act_type_id values across the catalogue, and reports
claim_field_types coverage. It is self-contained: it depends only on the
jsonschema package and the schema files in this repository, not on the
actproof-py reference loader.

The actproof-py loader performs the same schema validation at load time
(load_catalogue(validate_schema=True)). This script is the repository-side
gate that runs in CI so that a non-conforming entry cannot be merged.

Usage:
    python scripts/validate_catalogue.py [--root REPO_ROOT] [--strict]

    --root    Catalogue repository root. Defaults to the parent of the
              directory containing this script.
    --strict  Treat warnings, for example incomplete claim_field_types
              coverage, as failures.

Exit status:
    0  All entries conform. Warnings may have been printed.
    1  One or more entries failed, or --strict was set and warnings were
       present, or the gate could not run.

Dependencies:
    pip install jsonschema
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from jsonschema.exceptions import SchemaError
    from jsonschema.validators import Draft202012Validator
except ImportError:
    print(
        "Error: the 'jsonschema' package is required. "
        "Install it with: pip install jsonschema",
        file=sys.stderr,
    )
    sys.exit(1)


# Catalogue entry schema discriminators all share this prefix. A JSON file
# under catalogue/acts/ whose `schema` value starts with this prefix is
# treated as a catalogue entry, so a typo'd or wrong-version discriminator
# is reported rather than silently skipped.
ENTRY_DISCRIMINATOR_PREFIX = "actproof.act_catalogue_entry."


def fail_setup(message):
    """Print a setup failure and exit. Used when the gate cannot run."""
    print(f"validate_catalogue: cannot run: {message}", file=sys.stderr)
    sys.exit(1)


def load_validators(schema_dir):
    """Build a mapping from schema discriminator to a JSON Schema validator.

    Reads every act_catalogue_entry.*.json file in the schema directory,
    checks each against the JSON Schema 2020-12 metaschema, and keys it by
    the discriminator declared at properties.schema.const (or .enum).
    """
    if not schema_dir.is_dir():
        fail_setup(f"schema directory not found: {schema_dir}")

    schema_files = sorted(schema_dir.glob("act_catalogue_entry.*.json"))
    if not schema_files:
        fail_setup(
            f"no act_catalogue_entry.*.json schema files in {schema_dir}"
        )

    validators = {}
    for path in schema_files:
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except (OSError, json.JSONDecodeError, SchemaError) as exc:
            fail_setup(f"schema file {path.name} is not usable: {exc}")

        schema_prop = schema.get("properties", {}).get("schema", {})
        if "const" in schema_prop:
            discriminators = [schema_prop["const"]]
        elif "enum" in schema_prop:
            discriminators = list(schema_prop["enum"])
        else:
            fail_setup(
                f"schema file {path.name} declares no discriminator at "
                f"properties.schema.const or properties.schema.enum"
            )

        validator = Draft202012Validator(schema)
        for discriminator in discriminators:
            validators[discriminator] = validator

    return validators


def iter_entry_files(acts_dir):
    """Yield every candidate catalogue entry file under the acts directory.

    Files in any _deprecated subdirectory and files matching
    *.test_vectors.json are skipped, matching the reference loader.
    """
    for path in sorted(acts_dir.rglob("*.json")):
        if "_deprecated" in path.parts:
            continue
        if path.name.endswith(".test_vectors.json"):
            continue
        yield path


def check_entry(data, validators):
    """Validate one parsed entry. Return (errors, warnings) as string lists.

    The discriminator is assumed to be recognised: the caller resolves the
    skip, error, and entry cases before calling this function.
    """
    errors = []
    warnings = []

    validator = validators[data["schema"]]
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        location = "/".join(str(p) for p in err.path) or "(root)"
        errors.append(f"{location}: {err.message}")
    if errors:
        return errors, warnings

    # The entry conforms. Report claim_field_types coverage. The schema
    # makes claim_field_types optional, so a gap is a warning, not an
    # error, unless the gate is run with --strict.
    declared = set(data.get("required_claim_fields", [])) | set(
        data.get("optional_claim_fields", [])
    )
    typed = set((data.get("claim_field_types") or {}).keys())

    untyped = sorted(declared - typed)
    if untyped:
        warnings.append(
            f"claim_field_types: {len(untyped)} of {len(declared)} claim "
            f"field(s) untyped ({', '.join(untyped)})"
        )

    spurious = sorted(typed - declared)
    if spurious:
        warnings.append(
            f"claim_field_types: typed field(s) not declared as claim "
            f"fields ({', '.join(spurious)})"
        )

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Validate the ActProof Events catalogue against its "
        "JSON Schema."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="catalogue repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as failures",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    acts_dir = root / "catalogue" / "acts"
    schema_dir = root / "spec" / "schemas"
    if not acts_dir.is_dir():
        fail_setup(f"catalogue directory not found: {acts_dir}")

    validators = load_validators(schema_dir)

    print("actproof-events catalogue validation")
    print(f"  catalogue: {acts_dir}")
    print(f"  schemas:   {', '.join(sorted(validators))}")
    print()

    total = 0
    ok = 0
    skipped = 0
    files_with_errors = 0
    files_with_warnings = 0
    act_type_ids = {}  # act_type_id -> list of relative path strings

    for path in iter_entry_files(acts_dir):
        rel = path.relative_to(acts_dir)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            total += 1
            files_with_errors += 1
            print(f"  {'ERROR':<5} {rel}")
            print(f"        - file is not readable JSON: {exc}")
            continue

        discriminator = data.get("schema") if isinstance(data, dict) else None
        is_entry = isinstance(discriminator, str) and discriminator in validators
        looks_like_entry = isinstance(discriminator, str) and (
            discriminator.startswith(ENTRY_DISCRIMINATOR_PREFIX)
        )

        if not is_entry:
            if looks_like_entry:
                total += 1
                files_with_errors += 1
                print(f"  {'ERROR':<5} {rel}")
                print(
                    f"        - looks like a catalogue entry but its schema "
                    f"discriminator {discriminator!r} is not recognised; "
                    f"known: {sorted(validators)}"
                )
            else:
                skipped += 1
                print(f"  {'SKIP':<5} {rel}  (not a catalogue entry)")
            continue

        total += 1
        errors, warnings = check_entry(data, validators)

        act_type_id = data.get("act_type_id")
        if isinstance(act_type_id, str):
            act_type_ids.setdefault(act_type_id, []).append(str(rel))

        if errors:
            files_with_errors += 1
            print(f"  {'ERROR':<5} {rel}")
            for message in errors:
                print(f"        - {message}")
        elif warnings:
            files_with_warnings += 1
            print(f"  {'WARN':<5} {rel}")
            for message in warnings:
                print(f"        - {message}")
        else:
            ok += 1
            print(f"  {'OK':<5} {rel}")

    duplicates = {
        act_type_id: paths
        for act_type_id, paths in act_type_ids.items()
        if len(paths) > 1
    }
    if duplicates:
        print()
        for act_type_id, paths in sorted(duplicates.items()):
            print(
                f"  {'ERROR':<5} duplicate act_type_id {act_type_id!r} in: "
                f"{', '.join(sorted(paths))}"
            )

    print()
    entry_word = "entry" if total == 1 else "entries"
    summary = (
        f"summary: {total} {entry_word}, {ok} OK, "
        f"{files_with_warnings} with warnings, "
        f"{files_with_errors} with errors, {skipped} skipped"
    )
    if duplicates:
        summary += f", {len(duplicates)} duplicate act_type_id(s)"
    print(summary)

    failed = files_with_errors > 0 or bool(duplicates)
    if args.strict and files_with_warnings > 0:
        failed = True
        print("strict mode: warnings are treated as failures")

    print("RESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
