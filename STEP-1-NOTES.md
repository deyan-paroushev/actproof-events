# Step 1: pip-installable scaffolding for actproof-events

This delivery adds two files to the actproof-events repository root,
making the package installable from a git URL or (eventually) from PyPI.
No existing files are touched. No content is moved or restructured.

## Files

- `pyproject.toml` (repo root)
- `actproof_events/__init__.py` (new directory)

## What pip install does after this

`pip install git+https://github.com/deyan-paroushev/actproof-events.git@v1.4-rc1`
produces a wheel that bundles `catalogue/acts/*` and `spec/schemas/*` as
package data accessible at runtime via three helpers:

- `actproof_events.get_data_root()` returns the bundled data root.
- `actproof_events.get_catalogue_path()` returns the catalogue/acts dir.
- `actproof_events.get_schema_path(name)` returns a schema file by name.
- `actproof_events.list_catalogue_entries()` enumerates authoritative entries.

The package also exposes two version constants:

- `actproof_events.__version__` = `"1.4.0rc1"` (PyPI/wheel version)
- `actproof_events.__spec_version__` = `"1.4-rc1"` (spec revision)

## Local validation that was run

Wheel build: succeeded. Build artifact:
  `actproof_events-1.4.0rc1-py3-none-any.whl` (24 files, ~177 KB)

Wheel contents confirmed via `unzip -l`:
- 7 authoritative v2 catalogue entries (NIS2, EUDR, civil society mandate,
  actproof software release, plus their companion CC0 test vectors).
- 3 deprecated v1 entries under `_deprecated/` directories (preserved per
  CATALOGUE_LOADER_CONTRACT.md section 1.3 for historical rendering).
- 2 JSON Schemas (v2 and v3 act_catalogue_entry).
- LICENSE (Apache-2.0, full text).
- Python module (__init__.py).

Install + API smoke test in a fresh venv: succeeded. All four authoritative
catalogue entries enumerated with their canonical `act_type_id` values:

  op:actproof.software_release.v1
  op:democracy.civil_society_mandate.settlement.v1
  op:eu.eudr.dds_preparation.v1
  op:eu.nis2.art20.management_body_approval.v1

## Commit suggestion

    git add pyproject.toml actproof_events/__init__.py
    git commit -m "pkg: pip-installable scaffolding for actproof-events 1.4.0rc1

    Adds pyproject.toml (hatchling) and actproof_events/__init__.py exposing
    get_data_root, get_catalogue_path, get_schema_path, and
    list_catalogue_entries. catalogue/acts and spec/schemas are bundled
    into the wheel under actproof_events/data/ via hatchling force-include,
    leaving the source tree layout untouched."
    git tag v1.4-rc1
    git push origin main --tags

After tagging, Quoruna can pin to it:

    actproof-events @ git+https://github.com/deyan-paroushev/actproof-events.git@v1.4-rc1
