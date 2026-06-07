"""Release assurance helpers for bank/internal deployment workflows.

The module deliberately avoids network calls and external signing dependencies.
It produces machine-readable artifacts that a bank or integrator can store,
verify, mirror, and sign using its own release controls.
"""

from __future__ import annotations

import base64
import csv
import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

from actproof_events import __spec_version__, __version__
from actproof_events.bank_operability import build_profile_lock, canonical_json_hash
from actproof_events.exports import build_profile_view
from actproof_events.profile_governance import build_governance_status
from actproof_events.source_binding import compute_source_atom_coverage, get_profile_completeness

RELEASE_ASSURANCE_SCHEMA = "actproof.release_assurance_pack.v1"
ARTIFACT_HASHES_SCHEMA = "actproof.artifact_hashes.v1"
CYCLONEDX_SCHEMA = "http://cyclonedx.org/schema/bom-1.5.schema.json"
SIGNING_INTENT_SCHEMA = "actproof.release_signing_intent.v1"

HASH_EXCLUDE_DIRS = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "dist",
    "build",
    ".venv",
    "venv",
    "env",
    "node_modules",
}
HASH_EXCLUDE_SUFFIXES = {".pyc", ".pyo"}
DEFAULT_HASH_INCLUDE_DIRS = [
    "actproof_events",
    "catalogue",
    "spec",
    "source_bindings",
    "profile_governance",
    "analysis",
    "examples",
    "docs",
]
DEFAULT_HASH_INCLUDE_FILES = [
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "CATALOGUE_LOADER_CONTRACT.md",
]


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _b64_sha256_file(path: Path) -> str:
    h = hashlib.sha256(path.read_bytes()).digest()
    return "sha256-" + base64.b64encode(h).decode("ascii")


def _repo_root_from(start: str | Path | None = None) -> Path:
    if start is not None:
        return Path(start).resolve()
    return Path.cwd().resolve()


def _should_skip(path: Path) -> bool:
    return any(part in HASH_EXCLUDE_DIRS for part in path.parts) or path.suffix in HASH_EXCLUDE_SUFFIXES


def _iter_hashable_files(root: Path, include_paths: Iterable[str] | None = None) -> Iterable[Path]:
    include_paths = list(include_paths or [*DEFAULT_HASH_INCLUDE_DIRS, *DEFAULT_HASH_INCLUDE_FILES])
    for rel in include_paths:
        target = root / rel
        if not target.exists():
            continue
        if target.is_file() and not _should_skip(target.relative_to(root)):
            yield target
        elif target.is_dir():
            for p in sorted(target.rglob("*")):
                if p.is_file() and not _should_skip(p.relative_to(root)):
                    yield p


def build_artifact_hashes(
    root: str | Path | None = None,
    *,
    include_paths: Iterable[str] | None = None,
    include_file_integrity: bool = True,
) -> dict[str, Any]:
    """Build a deterministic SHA-256 manifest for source/release artifacts.

    The manifest is intended for internal mirrors and bank release gates. It is
    not a signature. It is the object a bank can sign or compare after transfer.
    """
    root_path = _repo_root_from(root)
    files: list[dict[str, Any]] = []
    for path in _iter_hashable_files(root_path, include_paths):
        rel = path.relative_to(root_path).as_posix()
        entry: dict[str, Any] = {
            "path": rel,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        if include_file_integrity:
            entry["subresource_integrity_sha256"] = _b64_sha256_file(path)
        files.append(entry)
    files.sort(key=lambda x: x["path"])
    payload: dict[str, Any] = {
        "schema": ARTIFACT_HASHES_SCHEMA,
        "package": "actproof-events",
        "package_version": __version__,
        "generated_at": _utc_now(),
        "hash_algorithm": "sha256",
        "root_label": root_path.name,
        "file_count": len(files),
        "total_size_bytes": sum(int(f["size_bytes"]) for f in files),
        "files": files,
        "boundaries": [
            "artifact hashes prove byte identity for the listed files only",
            "this manifest is not a digital signature",
            "banks should sign, store, or compare the manifest under internal release controls",
        ],
    }
    basis = {k: payload[k] for k in payload if k not in {"generated_at", "manifest_hash"}}
    payload["manifest_hash"] = canonical_json_hash(basis)
    return payload


def _read_project_metadata(root: Path) -> dict[str, Any]:
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8") if pyproject.exists() else ""
    # Minimal standard-library parsing sufficient for this package's simple metadata.
    meta: dict[str, Any] = {"name": "actproof-events", "version": __version__, "dependencies": []}
    in_project = False
    in_deps = False
    deps: list[str] = []
    optional: dict[str, list[str]] = {}
    current_optional: str | None = None
    in_optional = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == "[project]":
            in_project = True; in_deps = False; in_optional = False; current_optional = None; continue
        if line.startswith("["):
            in_project = False; in_deps = False
            in_optional = line == "[project.optional-dependencies]"
            current_optional = None
            continue
        if in_project:
            if line.startswith("name ="):
                meta["name"] = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("version ="):
                meta["version"] = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("dependencies ="):
                in_deps = True
            elif in_deps and line == "]":
                in_deps = False
            elif in_deps and line.startswith('"'):
                deps.append(line.rstrip(",").strip().strip('"'))
        if in_optional:
            if "=" in line and line.endswith("["):
                current_optional = line.split("=", 1)[0].strip()
                optional[current_optional] = []
            elif current_optional and line == "]":
                current_optional = None
            elif current_optional and line.startswith('"'):
                optional[current_optional].append(line.rstrip(",").strip().strip('"'))
    meta["dependencies"] = deps
    meta["optional_dependencies"] = optional
    return meta


def build_sbom(root: str | Path | None = None, *, serial_number: str | None = None) -> dict[str, Any]:
    """Build a minimal CycloneDX 1.5 SBOM for the package.

    The package has no required runtime dependencies. Optional extras are
    reported as optional components so a bank can decide what to mirror.
    """
    root_path = _repo_root_from(root)
    meta = _read_project_metadata(root_path)
    bom_ref = f"pkg:pypi/{meta['name']}@{meta['version']}"
    components: list[dict[str, Any]] = []
    for extra, deps in sorted((meta.get("optional_dependencies") or {}).items()):
        for dep in deps:
            components.append({
                "type": "library",
                "name": dep,
                "bom-ref": f"optional:{extra}:{dep}",
                "scope": "optional",
                "properties": [
                    {"name": "actproof:optional_extra", "value": extra},
                    {"name": "actproof:dependency_specifier", "value": dep},
                ],
            })
    payload: dict[str, Any] = {
        "$schema": CYCLONEDX_SCHEMA,
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": serial_number or f"urn:uuid:actproof-events-{meta['version'].replace('.', '-')}",
        "version": 1,
        "metadata": {
            "timestamp": _utc_now(),
            "tools": [{"vendor": "ActProof", "name": "actproof-events", "version": __version__}],
            "component": {
                "type": "library",
                "bom-ref": bom_ref,
                "name": meta["name"],
                "version": meta["version"],
                "purl": bom_ref,
                "licenses": [{"license": {"id": "Apache-2.0"}}],
                "description": "Source-bound regulatory profile catalogue and local pre-validation tooling.",
            },
            "properties": [
                {"name": "actproof:spec_version", "value": __spec_version__},
                {"name": "actproof:required_runtime_dependency_count", "value": str(len(meta.get("dependencies") or []))},
            ],
        },
        "components": components,
        "dependencies": [{"ref": bom_ref, "dependsOn": [c["bom-ref"] for c in components]}],
        "properties": [
            {"name": "actproof:sbom_boundary", "value": "SBOM describes package and declared optional extras; it does not replace vulnerability analysis."},
            {"name": "actproof:runtime_network_dependency", "value": "none for core package use"},
        ],
    }
    payload["bom_hash"] = canonical_json_hash({k: payload[k] for k in payload if k != "bom_hash"})
    return payload


def build_signing_intent(root: str | Path | None = None, artifact_hashes: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a signing/attestation intent record for external release controls.

    ActProof does not generate a private-key signature. This record identifies
    what should be signed or attested by PyPI Trusted Publishing, Sigstore,
    GitHub attestations, or a bank's internal signing process.
    """
    root_path = _repo_root_from(root)
    artifact_hashes = artifact_hashes or build_artifact_hashes(root_path)
    payload: dict[str, Any] = {
        "schema": SIGNING_INTENT_SCHEMA,
        "package": "actproof-events",
        "package_version": __version__,
        "generated_at": _utc_now(),
        "artifact_manifest_hash": artifact_hashes.get("manifest_hash"),
        "recommended_attestations": [
            "PyPI Trusted Publishing / PEP 740 digital attestations when publishing from GitHub Actions",
            "GitHub artifact attestations or Sigstore/cosign for release archives where available",
            "bank-internal signing of artifact-hashes.json after mirroring into an internal repository",
        ],
        "verify_before_use": [
            "confirm PyPI project name and version",
            "compare wheel/sdist hashes against artifact-hashes.json or PyPI metadata",
            "verify profile lock hash for the ActProof profile in use",
            "store SBOM and artifact hash manifest in internal change records",
        ],
        "boundaries": [
            "this is an intent/verification aid, not a generated cryptographic signature",
            "banks should apply their own signing, attestation, and release approval process",
        ],
    }
    payload["signing_intent_hash"] = canonical_json_hash({k: payload[k] for k in payload if k != "signing_intent_hash"})
    return payload


def _latest_review_record_hash(act_id: str) -> str | None:
    """Best-effort fetch of the latest review-record hash for binding into the manifest."""
    try:
        from actproof_events.profile_governance import latest_review_record
        rec = latest_review_record(act_id)
        return rec.get("review_record_hash") if rec else None
    except Exception:
        return None


def build_release_assurance_manifest(act_id: str, root: str | Path | None = None) -> dict[str, Any]:
    root_path = _repo_root_from(root)
    profile_view = build_profile_view(act_id)
    profile_lock = build_profile_lock(act_id)
    artifact_hashes = build_artifact_hashes(root_path)
    sbom = build_sbom(root_path)
    signing_intent = build_signing_intent(root_path, artifact_hashes)
    payload: dict[str, Any] = {
        "schema": RELEASE_ASSURANCE_SCHEMA,
        "package": "actproof-events",
        "package_version": __version__,
        "act_id": act_id,
        "generated_at": _utc_now(),
        "profile": {
            "profile_semantic_hash": profile_view.get("profile_semantic_hash"),
            "profile_artifact_hash": profile_view.get("profile_artifact_hash"),
            "profile_lock_hash": profile_lock.get("profile_lock_hash"),
            "latest_review_record_hash": _latest_review_record_hash(act_id),
        },
        "governance": build_governance_status(act_id),
        "source_atom_coverage": compute_source_atom_coverage(act_id),
        "completeness": get_profile_completeness(act_id),
        "artifacts": {
            "artifact_hashes_manifest_hash": artifact_hashes.get("manifest_hash"),
            "sbom_hash": sbom.get("bom_hash"),
            "signing_intent_hash": signing_intent.get("signing_intent_hash"),
        },
        "bank_adoption_use": {
            "recommended_deployment": "local/internal package installation from pinned wheel or internal mirror",
            "public_hosted_api_boundary": "public discovery and examples only; do not send sensitive incident data to public endpoints",
            "core_runtime_network_dependency": "none",
        },
        "boundaries": [
            "release assurance artifacts support internal security/release review",
            "they do not certify legal compliance or supervisory acceptance",
            "SBOM and hashes do not replace vulnerability scanning, malware scanning, or bank change approval",
        ],
    }
    payload["release_assurance_manifest_hash"] = canonical_json_hash({k: payload[k] for k in payload if k != "release_assurance_manifest_hash"})
    return payload


def build_internal_mirror_guide(act_id: str) -> str:
    return f"""# ActProof Events internal mirror guide

Package: `actproof-events=={__version__}`  
Profile: `{act_id}`

This guide supports bank/internal deployment of ActProof as a local reference and pre-validation component. It is not a compliance certification, legal opinion, vulnerability scan, or supervisory submission process.

## Recommended internal flow

1. Download the pinned wheel and sdist from PyPI or the approved source repository.
2. Store the release artifacts in the bank's internal package repository or wheelhouse.
3. Store `sbom.cyclonedx.json`, `artifact-hashes.json`, `release-assurance-manifest.json`, and `signing-intent.json` in the internal change record.
4. Verify wheel/sdist hashes against PyPI metadata and/or the bank-approved artifact manifest.
5. Install from the internal mirror only.
6. Pin the profile using `actproof-events export-profile-lock {act_id} --out profile-lock.json`.
7. Run local pre-validation and overlay commands inside the bank environment. Do not send sensitive incident data to public hosted endpoints.

## Example: build a local wheelhouse

```bash
python -m pip download --only-binary=:all: --dest wheelhouse actproof-events=={__version__}
python -m pip hash wheelhouse/*.whl
```

## Example: install from local files only

```bash
python -m pip install --no-index --find-links wheelhouse actproof-events=={__version__}
```

## Example: install from an internal package index

```bash
python -m pip install --index-url https://internal.example/pypi/simple actproof-events=={__version__}
```

## Verification checklist

- [ ] Package version is pinned.
- [ ] Wheel/sdist hash is recorded.
- [ ] SBOM is stored.
- [ ] Artifact hash manifest is stored.
- [ ] Profile lock hash is stored.
- [ ] Governance status is reviewed.
- [ ] Bank overlay is reviewed locally.
- [ ] Public hosted endpoints are not used for sensitive incident data.

## Boundary

ActProof helps turn a regulatory reporting template into a controlled, source-bound field reference that can be mapped to internal systems, checked for missingness, and used for local pre-validation. It does not replace legal interpretation, factual investigation, incident response, audit approval, or regulatory submission.
"""


def export_release_assurance_pack(act_id: str, out_dir: str | Path, *, root: str | Path | None = None) -> dict[str, Any]:
    """Export SBOM, artifact hashes, signing intent, mirror guide and manifest."""
    root_path = _repo_root_from(root)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    artifact_hashes = build_artifact_hashes(root_path)
    sbom = build_sbom(root_path)
    signing = build_signing_intent(root_path, artifact_hashes)
    manifest = build_release_assurance_manifest(act_id, root_path)
    files = {
        "release-assurance-manifest.json": manifest,
        "artifact-hashes.json": artifact_hashes,
        "sbom.cyclonedx.json": sbom,
        "signing-intent.json": signing,
        "profile-lock.json": build_profile_lock(act_id),
        "governance-status.json": build_governance_status(act_id),
        "source-atom-coverage.json": compute_source_atom_coverage(act_id),
        "completeness.json": get_profile_completeness(act_id),
    }
    written: list[dict[str, Any]] = []
    for name, payload in files.items():
        p = out_path / name
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append({"path": name, "sha256": _sha256_file(p), "size_bytes": p.stat().st_size})
    guide_path = out_path / "INTERNAL_MIRROR_GUIDE.md"
    guide_path.write_text(build_internal_mirror_guide(act_id), encoding="utf-8")
    written.append({"path": "INTERNAL_MIRROR_GUIDE.md", "sha256": _sha256_file(guide_path), "size_bytes": guide_path.stat().st_size})
    sha_csv = out_path / "SHA256SUMS.csv"
    with sha_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "sha256", "size_bytes"])
        writer.writeheader(); writer.writerows(written)
    written.append({"path": "SHA256SUMS.csv", "sha256": _sha256_file(sha_csv), "size_bytes": sha_csv.stat().st_size})
    pack_manifest = {
        "schema": "actproof.release_assurance_pack_manifest.v1",
        "package": "actproof-events",
        "package_version": __version__,
        "act_id": act_id,
        "generated_at": _utc_now(),
        "files": written,
        "boundaries": [
            "pack files are local release-assurance artifacts",
            "signing/attestation is performed by PyPI/GitHub/bank controls outside this package",
        ],
    }
    pack_manifest["release_assurance_pack_hash"] = canonical_json_hash({k: pack_manifest[k] for k in pack_manifest if k != "release_assurance_pack_hash"})
    p = out_path / "release-assurance-pack-manifest.json"
    p.write_text(json.dumps(pack_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pack_manifest


def verify_artifact_hashes(manifest_path: str | Path, *, root: str | Path | None = None,
                           expected_profile_semantic_hash: str | None = None,
                           act_id: str | None = None) -> dict[str, Any]:
    """Verify listed artifact hashes against files in a root directory.

    If ``expected_profile_semantic_hash`` (and ``act_id``) are supplied, also
    re-checks that the CURRENTLY installed profile still matches that hash. This
    catches the case where the files verify but the regulatory content has
    drifted from what a release-assurance manifest recorded \u2014 the artifact and
    its regulatory content must be one coherent release.
    """
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    root_path = _repo_root_from(root or Path(manifest_path).parent)
    results = []
    ok = True
    for entry in manifest.get("files") or []:
        rel = entry.get("path")
        p = root_path / rel
        exists = p.exists() and p.is_file()
        actual = _sha256_file(p) if exists else None
        matches = actual == entry.get("sha256")
        ok = ok and matches
        results.append({"path": rel, "exists": exists, "expected_sha256": entry.get("sha256"), "actual_sha256": actual, "matches": matches})

    domain_check = None
    if expected_profile_semantic_hash and act_id:
        try:
            current = build_profile_view(act_id).get("profile_semantic_hash")
            dmatch = current == expected_profile_semantic_hash
            ok = ok and dmatch
            domain_check = {
                "act_id": act_id,
                "expected_profile_semantic_hash": expected_profile_semantic_hash,
                "current_profile_semantic_hash": current,
                "matches": dmatch,
            }
        except Exception as exc:  # pragma: no cover
            domain_check = {"act_id": act_id, "error": str(exc), "matches": False}
            ok = False

    return {"schema": "actproof.artifact_hash_verification.v1", "manifest": str(manifest_path),
            "root": str(root_path), "ok": ok, "results": results, "domain_check": domain_check}
