from pathlib import Path

from actproof_events.release_assurance import (
    ARTIFACT_HASHES_SCHEMA,
    build_artifact_hashes,
    build_release_assurance_manifest,
    build_sbom,
    build_signing_intent,
    export_release_assurance_pack,
    verify_artifact_hashes,
)

ACT_ID = "op:eu.dora.ict_incident_notification_initial.v1"


def test_build_sbom_has_cyclonedx_shape():
    sbom = build_sbom(Path.cwd())
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert sbom["metadata"]["component"]["name"] == "actproof-events"
    assert sbom["bom_hash"].startswith("sha256:")


def test_artifact_hashes_manifest_shape():
    manifest = build_artifact_hashes(Path.cwd(), include_paths=["pyproject.toml", "actproof_events/__init__.py"])
    assert manifest["schema"] == ARTIFACT_HASHES_SCHEMA
    assert manifest["file_count"] >= 2
    assert manifest["manifest_hash"].startswith("sha256:")
    paths = {f["path"] for f in manifest["files"]}
    assert "pyproject.toml" in paths


def test_signing_intent_is_not_a_signature():
    intent = build_signing_intent(Path.cwd(), build_artifact_hashes(Path.cwd(), include_paths=["pyproject.toml"]))
    assert intent["schema"] == "actproof.release_signing_intent.v1"
    assert intent["signing_intent_hash"].startswith("sha256:")
    assert any("not a generated cryptographic signature" in x for x in intent["boundaries"])


def test_release_assurance_manifest_links_profile_and_artifacts():
    manifest = build_release_assurance_manifest(ACT_ID, Path.cwd())
    assert manifest["schema"] == "actproof.release_assurance_pack.v1"
    assert manifest["profile"]["profile_semantic_hash"].startswith("sha256:")
    assert manifest["artifacts"]["sbom_hash"].startswith("sha256:")


def test_export_release_assurance_pack_and_verify_hashes(tmp_path):
    pack = export_release_assurance_pack(ACT_ID, tmp_path / "pack", root=Path.cwd())
    assert pack["release_assurance_pack_hash"].startswith("sha256:")
    for name in ["sbom.cyclonedx.json", "artifact-hashes.json", "INTERNAL_MIRROR_GUIDE.md"]:
        assert (tmp_path / "pack" / name).exists()
    # Verify a small generated pack manifest by using the pack root.
    result = verify_artifact_hashes(tmp_path / "pack" / "artifact-hashes.json", root=Path.cwd())
    assert result["schema"] == "actproof.artifact_hash_verification.v1"


# --- merge: domain re-check + review-record binding guardrails ---------------

import json as _json
import tempfile as _tempfile
import os as _os
from actproof_events.release_assurance import (
    build_release_assurance_manifest as _ram,
    build_artifact_hashes as _bah,
    verify_artifact_hashes as _vah,
)

_ACT = "op:eu.dora.ict_incident_notification_initial.v1"


def test_manifest_binds_review_record_hash():
    m = _ram(_ACT)
    # the merge adds the review-record hash binding to the profile block
    assert "latest_review_record_hash" in m["profile"]


def test_verify_domain_check_passes_for_current_profile():
    m = _ram(_ACT)
    phash = m["profile"]["profile_semantic_hash"]
    ah = _bah(".")
    fd = _tempfile.mktemp(suffix=".json")
    open(fd, "w").write(_json.dumps(ah))
    try:
        r = _vah(fd, root=".", expected_profile_semantic_hash=phash, act_id=_ACT)
        assert r["domain_check"]["matches"] is True
    finally:
        _os.unlink(fd)


def test_verify_domain_check_fails_on_drifted_profile():
    ah = _bah(".")
    fd = _tempfile.mktemp(suffix=".json")
    open(fd, "w").write(_json.dumps(ah))
    try:
        r = _vah(fd, root=".", expected_profile_semantic_hash="sha256:" + "0" * 64, act_id=_ACT)
        assert r["domain_check"]["matches"] is False
        assert r["ok"] is False  # a drifted profile fails the whole verification
    finally:
        _os.unlink(fd)
