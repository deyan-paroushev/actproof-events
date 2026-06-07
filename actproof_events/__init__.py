"""actproof-events: open catalogue and JSON schemas for source-bound act profiles.

This package ships the actproof-events artefacts that other software needs
at runtime: the act-catalogue entries, the JSON Schema files that define
their structure, the specification text, the controlled vocabularies, the
schema versioning policy, and the catalogue loader contract. Each catalogue
entry has a companion ``*.test_vectors.json`` file carrying CC0-licensed
conformance vectors.

The repository keeps the source tree organised for humans: catalogue
entries live at the top-level ``catalogue/`` directory, schemas at
``spec/schemas/``, and the specification text at ``spec/``. The wheel rolls
all of these into a single ``actproof_events/data/`` hierarchy so that
installed consumers see one place to look.

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
package version of ``2.1.0`` ships the v1.5-rc1 specification and the
catalogue state at that release tag.

References:
    Specification:             get_spec_path()
    Controlled vocabularies:   get_vocabularies_path()
    Schema versioning policy:  get_schema_version_policy_path()
    Catalogue loader contract: get_contract_path()
    Contributing acts:         CONTRIBUTING_ACTS.md (repository only)
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
    "get_profile_view_schema_path",
    "get_source_atoms_schema_path",
    "get_field_derivations_schema_path",
    "get_source_bindings_path",
    "get_spec_path",
    "get_vocabularies_path",
    "get_schema_version_policy_path",
    "get_contract_path",
    "list_catalogue_entries",
]

# ─── Version metadata ───────────────────────────────────────────────────────
#
# The package version is the authoritative source. The specification version
# is exposed as a separate constant so that consumers can record which
# specification revision a given installation embodies (useful when a
# downstream artefact records "issued against actproof-events specification
# v1.5-rc1").

__version__: Final[str] = "2.1.0"
__spec_version__: Final[str] = "1.5-rc1"


# ─── Bundled data location ──────────────────────────────────────────────────
#
# The wheel places catalogue and schema bytes under ``actproof_events/data/``.
# We resolve paths relative to this module's filesystem location, which
# works for both wheel installs and editable installs from a source checkout.

_DATA_ROOT: Final[Path] = Path(__file__).parent / "data"


def get_data_root() -> Path:
    """Return the root directory of bundled actproof-events data.

    The directory contains the following:

    - ``catalogue/acts/``: act-catalogue entries, keyed by act_type_id.
      Authoritative entries currently follow the
      ``actproof.act_profile.v3`` schema. Older v1 and v2 entries
      may exist for historical rendering and are loaded as best-effort.
      For example, ``eu/nis2/art20/management_body_approval.v1.json``.
    - ``schemas/``: JSON Schema files describing catalogue entry structure.
    - ``spec/``: the specification text, the controlled vocabularies, and
      the schema versioning policy.
    - ``CATALOGUE_LOADER_CONTRACT.md``: the catalogue loader contract.

    Prefer the ``get_*_path`` accessors below over composing these paths by
    hand, so that a later change to the bundled layout does not break
    callers.

    Returns:
        Path: The absolute path to the bundled data directory.
    """
    return _DATA_ROOT


def get_catalogue_path() -> Path:
    """Return the bundled act-catalogue directory.

    The directory contains JSON files following the
    ``actproof.act_profile.v3`` schema for authoritative entries
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
            ``"act_profile.v3"`` or
            ``"act_profile.v3.json"``.

    Returns:
        Path: The path under ``actproof_events/data/schemas/``.

    Example:
        >>> from actproof_events import get_schema_path
        >>> schema_path = get_schema_path("act_profile.v3")
        >>> assert schema_path.exists()
    """
    if not name.endswith(".json"):
        name = f"{name}.json"
    return _DATA_ROOT / "schemas" / name




def get_profile_view_schema_path() -> Path:
    """Return the path to the bundled profile-view JSON Schema.

    The profile-view schema defines the public projection produced by
    ``actproof_events.exports.build_profile_view`` and the
    ``actproof-events export-profile-view`` CLI. In wheels the schema is
    located under ``actproof_events/data/schemas/``. In source checkouts,
    where build-time data materialisation may not have happened yet, this
    accessor falls back to ``spec/schemas/``.

    Returns:
        Path: The path to ``profile_view.v1.schema.json``.
    """
    installed = get_schema_path("profile_view.v1.schema")
    if installed.exists():
        return installed
    source_tree = Path(__file__).resolve().parents[1] / "spec" / "schemas" / "profile_view.v1.schema.json"
    return source_tree



def get_source_atoms_schema_path() -> Path:
    """Return the path to the bundled source-atoms JSON Schema."""
    installed = get_schema_path("source_atoms.v1.schema")
    if installed.exists():
        return installed
    return Path(__file__).resolve().parents[1] / "spec" / "schemas" / "source_atoms.v1.schema.json"


def get_field_derivations_schema_path() -> Path:
    """Return the path to the bundled field-derivations JSON Schema."""
    installed = get_schema_path("field_derivations.v1.schema")
    if installed.exists():
        return installed
    return Path(__file__).resolve().parents[1] / "spec" / "schemas" / "field_derivations.v1.schema.json"


def get_source_bindings_path() -> Path:
    """Return the bundled field-level source-binding data directory.

    In wheels this resolves under ``actproof_events/data/source_bindings``.
    In source checkouts it falls back to the repository ``source_bindings``
    directory when the wheel data tree has not been materialised.
    """
    installed = _DATA_ROOT / "source_bindings"
    if installed.exists():
        return installed
    return Path(__file__).resolve().parents[1] / "source_bindings"


def get_spec_path() -> Path:
    """Return the path to the bundled actproof-events specification.

    ``actproof-events.spec.md`` is the normative specification. It defines
    the catalogue model, the attestation manifest, the envelope, anchoring,
    federation, and the verifier conformance rules.

    Returns:
        Path: The path to
            ``actproof_events/data/spec/actproof-events.spec.md``.

    Example:
        >>> from actproof_events import get_spec_path
        >>> spec_text = get_spec_path().read_text(encoding="utf-8")
    """
    return _DATA_ROOT / "spec" / "actproof-events.spec.md"


def get_vocabularies_path() -> Path:
    """Return the path to the bundled controlled vocabularies.

    ``vocabularies.md`` defines the closed enumeration terms referenced by
    catalogue entries and schemas, the ``non_claims`` vocabulary, and the
    process by which those vocabularies change.

    Returns:
        Path: The path to ``actproof_events/data/spec/vocabularies.md``.
    """
    return _DATA_ROOT / "spec" / "vocabularies.md"


def get_schema_version_policy_path() -> Path:
    """Return the path to the bundled schema versioning policy.

    ``schema_version_policy.md`` describes what may change within a schema
    version, what requires a new schema version, and how the schema archive
    is maintained. Consult it before pinning a schema major version.

    Returns:
        Path: The path to
            ``actproof_events/data/spec/schema_version_policy.md``.
    """
    return _DATA_ROOT / "spec" / "schema_version_policy.md"


def get_contract_path() -> Path:
    """Return the path to the bundled catalogue loader contract.

    ``CATALOGUE_LOADER_CONTRACT.md`` specifies the behaviour a conforming
    catalogue loader must implement: the loading rules, manifest validation
    requirements, error reporting, and the conformance test scenarios a
    loader is checked against.

    Returns:
        Path: The path to
            ``actproof_events/data/CATALOGUE_LOADER_CONTRACT.md``.
    """
    return _DATA_ROOT / "CATALOGUE_LOADER_CONTRACT.md"


def list_catalogue_entries(
    include_deprecated: bool = False,
    include_test_vectors: bool = False,
) -> list[Path]:
    """Enumerate the catalogue entry JSON files bundled with this release.

    By default returns only authoritative entries: paths under
    ``_deprecated/`` directories are excluded, and companion
    ``*.test_vectors.json`` files are excluded. Authoritative entries
    follow ``actproof.act_profile.v3`` for the current release;
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
