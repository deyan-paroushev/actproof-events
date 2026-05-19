"""actproof-events: federated cryptographic substrate for verifiable regulatory acts.

This package ships the actproof-events specification artefacts that other
software needs at runtime: the act-catalogue entries, the JSON Schema files
that define their structure, and (when present) the expanded profile JSON
files used to drive profile-conformant evidence receipts.

The repository keeps the source tree organised for humans: catalogue entries
live at the top-level ``catalogue/`` directory, schemas at ``spec/schemas/``,
and (in subsequent releases) profile files at ``profiles/``. The wheel rolls
all of these into a single ``actproof_events/data/`` hierarchy so that
installed consumers see one place to look regardless of how the package was
installed.

Typical usage from a consuming application::

    import json
    from actproof_events import get_catalogue_path

    catalogue_dir = get_catalogue_path()
    for entry_path in catalogue_dir.rglob("*.v*.json"):
        if entry_path.name.endswith(".test_vectors.json"):
            continue
        with entry_path.open() as f:
            entry = json.load(f)
            ...

The package version tracks the actproof-events specification version. A
package version of ``1.4.0rc1`` ships the v1.4-rc1 specification and the
catalogue state at that release tag.

References:
    Specification: spec/actproof-events.spec.md (bundled at install time)
    Catalogue loader contract: CATALOGUE_LOADER_CONTRACT.md
    Contributing acts:        CONTRIBUTING_ACTS.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

__all__ = [
    "__version__",
    "__spec_version__",
    "get_data_root",
    "get_catalogue_path",
    "get_schema_path",
    "list_catalogue_entries",
]

# ─── Version metadata ───────────────────────────────────────────────────────
#
# The package version is the authoritative source. The specification version
# is exposed as a separate constant so that consumers can record which
# specification revision a given installation embodies (useful when receipts
# need to claim "issued against actproof-events specification v1.4-rc1").

__version__: Final[str] = "1.4.0rc1"
__spec_version__: Final[str] = "1.4-rc1"


# ─── Bundled data location ──────────────────────────────────────────────────
#
# The wheel places catalogue and schema bytes under ``actproof_events/data/``.
# We resolve paths relative to this module's filesystem location, which
# works for both wheel installs and editable installs from a source checkout.

_DATA_ROOT: Final[Path] = Path(__file__).parent / "data"


def get_data_root() -> Path:
    """Return the root directory of bundled actproof-events data.

    The directory contains the following subdirectories:

    - ``catalogue/acts/``: act-catalogue entries, keyed by act_type_id.
      Authoritative entries currently follow the
      ``actproof.act_catalogue_entry.v3`` schema. Older v1 and v2 entries
      may exist for historical rendering and are loaded as best-effort.
      For example, ``eu/nis2/art20/management_body_approval.v1.json``.
    - ``schemas/``: JSON Schema files describing catalogue entry structure.

    Future releases of actproof-events may add additional subdirectories
    such as ``profiles/`` for expanded profile JSON files. Callers should
    test for the existence of subdirectories before relying on them.

    Returns:
        Path: The absolute path to the bundled data directory.
    """
    return _DATA_ROOT


def get_catalogue_path() -> Path:
    """Return the bundled act-catalogue directory.

    The directory contains JSON files following the
    ``actproof.act_catalogue_entry.v3`` schema for authoritative entries
    (with v1 and v2 entries potentially present for historical
    rendering), plus companion ``*.test_vectors.json`` files providing
    CC0-licensed conformance test vectors for each entry. Deprecated
    entries live in ``_deprecated/`` subdirectories and should not be
    loaded as authoritative.

    Returns:
        Path: The absolute path to ``actproof_events/data/catalogue/acts``.

    Example:
        >>> from actproof_events import get_catalogue_path
        >>> for entry in get_catalogue_path().rglob('*.v*.json'):
        ...     if '_deprecated' in entry.parts:
        ...         continue
        ...     if entry.name.endswith('.test_vectors.json'):
        ...         continue
        ...     print(entry.relative_to(get_catalogue_path()))
    """
    return _DATA_ROOT / "catalogue" / "acts"


def get_schema_path(name: str) -> Path:
    """Return the path to a bundled JSON Schema file by base name.

    The ``.json`` suffix is appended automatically if not already present.
    The returned path is not guaranteed to exist; callers should check
    ``.exists()`` if the schema name is not known to ship with this
    release.

    Args:
        name: The schema's base name. For example,
            ``"act_catalogue_entry.v3"`` or
            ``"act_catalogue_entry.v3.json"``.

    Returns:
        Path: The path under ``actproof_events/data/schemas/``.

    Example:
        >>> from actproof_events import get_schema_path
        >>> schema_path = get_schema_path("act_catalogue_entry.v3")
        >>> assert schema_path.exists()
    """
    if not name.endswith(".json"):
        name = f"{name}.json"
    return _DATA_ROOT / "schemas" / name


def list_catalogue_entries(
    include_deprecated: bool = False,
    include_test_vectors: bool = False,
) -> list[Path]:
    """Enumerate the catalogue entry JSON files bundled with this release.

    By default returns only authoritative entries: paths under
    ``_deprecated/`` directories are excluded, and companion
    ``*.test_vectors.json`` files are excluded. Authoritative entries
    follow ``actproof.act_catalogue_entry.v3`` for the current release;
    historical v1 and v2 entries may also surface and are returned
    as-is.

    Args:
        include_deprecated: If True, include entries living under
            ``_deprecated/`` subdirectories. Default False.
        include_test_vectors: If True, include companion test vector
            files alongside the entries they describe. Default False.

    Returns:
        list[Path]: Catalogue entry paths sorted lexically for deterministic
            iteration order, suitable for hashing or reproducible loading.

    Example:
        >>> from actproof_events import list_catalogue_entries
        >>> entries = list_catalogue_entries()
        >>> # entries is a sorted list of authoritative catalogue files.
    """
    paths: list[Path] = []
    for path in get_catalogue_path().rglob("*.json"):
        if not include_deprecated and "_deprecated" in path.parts:
            continue
        if not include_test_vectors and path.name.endswith(".test_vectors.json"):
            continue
        paths.append(path)
    paths.sort()
    return paths
