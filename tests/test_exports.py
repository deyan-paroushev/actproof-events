import json
import re

from actproof_events import get_profile_view_schema_path
from actproof_events.exports import (
    PROFILE_ARTIFACT_HASH_BASIS,
    PROFILE_SEMANTIC_HASH_BASIS,
    PROFILE_VIEW_SCHEMA_ID,
    build_profile_view,
    compute_profile_artifact_hash,
    compute_profile_semantic_hash,
    compute_profile_view_hash,
    get_profile_view_schema,
    validate_profile_view,
    write_profile_view,
)

ACT_ID = "op:eu.dora.ict_incident_notification_initial.v1"


def test_build_profile_view_contains_rich_projection():
    view = build_profile_view(ACT_ID, generated_at="2026-01-01T00:00:00Z")
    assert view["profile_view_schema"] == PROFILE_VIEW_SCHEMA_ID
    assert view["canonical_object"]["act_id"] == ACT_ID
    assert view["canonical_object"]["catalogue_entry_hash"].startswith("sha256:")
    assert view["profile"]["non_claims"]
    assert view["coverage"]["field_counts"]["total"] == len(view["fields"])
    assert view["coverage"]["field_counts"]["required"] > 0
    assert view["coverage"]["assessment"]["scored_fields"] >= 0
    assert view["profile_semantic_hash_basis"] == PROFILE_SEMANTIC_HASH_BASIS
    assert view["profile_artifact_hash_basis"] == PROFILE_ARTIFACT_HASH_BASIS
    assert view["profile_view_hash"] == view["profile_semantic_hash"]
    assert re.match(r"^sha256:[0-9a-f]{64}$", view["profile_semantic_hash"])
    assert re.match(r"^sha256:[0-9a-f]{64}$", view["profile_artifact_hash"])


def test_profile_hashes_are_stable_when_only_generated_at_changes():
    a = build_profile_view(ACT_ID, generated_at="2026-01-01T00:00:00Z")
    b = build_profile_view(ACT_ID, generated_at="2026-01-02T00:00:00Z")
    assert a["profile_semantic_hash"] == b["profile_semantic_hash"]
    assert a["profile_artifact_hash"] == b["profile_artifact_hash"]
    assert compute_profile_semantic_hash(a) == a["profile_semantic_hash"]
    assert compute_profile_artifact_hash(a) == a["profile_artifact_hash"]
    assert compute_profile_view_hash(a) == a["profile_view_hash"]


def test_semantic_hash_ignores_package_version_but_artifact_hash_retains_it():
    a = build_profile_view(ACT_ID, generated_at="2026-01-01T00:00:00Z")
    b = json.loads(json.dumps(a))
    b["provenance"]["package_version"] = "9.9.9"
    assert compute_profile_semantic_hash(a) == compute_profile_semantic_hash(b)
    assert compute_profile_artifact_hash(a) != compute_profile_artifact_hash(b)


def test_write_profile_view(tmp_path):
    out = tmp_path / "dora.profile-view.json"
    payload = write_profile_view(ACT_ID, out, validate=True)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["act_id"] == ACT_ID
    assert loaded["profile_view_hash"] == payload["profile_view_hash"]
    assert loaded["profile_semantic_hash"] == payload["profile_semantic_hash"]
    assert loaded["profile_artifact_hash"] == payload["profile_artifact_hash"]


def test_profile_view_schema_accessor_resolves_schema():
    schema_path = get_profile_view_schema_path()
    assert schema_path.name == "profile_view.v1.schema.json"
    assert schema_path.exists()
    schema = get_profile_view_schema()
    assert schema["$id"].endswith("profile_view.v1.schema.json")


def test_profile_view_schema_validates_projection():
    view = build_profile_view(ACT_ID, generated_at="2026-01-01T00:00:00Z")
    assert validate_profile_view(view) == []


def test_verify_profile_view_passes_for_fresh_artifact(tmp_path):
    from actproof_events.exports import verify_profile_view

    out = tmp_path / "dora.profile-view.json"
    write_profile_view(ACT_ID, out)
    report = verify_profile_view(out)
    assert report["semantic_hash_matches"] is True
    assert report["artifact_hash_matches"] is True
    assert report["catalogue_entry_hash_present"] is True
    # 1.7.0 is act-level fallback, so this is a disclosed warning, not an error.
    assert any("act-level source fallback" in w for w in report["warnings"])
    assert report["field_derivations_complete"] is False


def test_verify_profile_view_detects_tampering():
    from actproof_events.exports import verify_profile_view

    view = build_profile_view(ACT_ID, generated_at="2026-01-01T00:00:00Z")
    # Tamper with content without updating the stored hashes.
    view["coverage"]["field_counts"]["total"] = 9999
    report = verify_profile_view(view)
    assert report["semantic_hash_matches"] is False
    assert report["ok"] is False
    assert any("semantic_hash mismatch" in e for e in report["errors"])


def test_verify_profile_view_accepts_path_and_dict_equivalently(tmp_path):
    from actproof_events.exports import verify_profile_view

    out = tmp_path / "dora.profile-view.json"
    payload = write_profile_view(ACT_ID, out)
    report_from_path = verify_profile_view(out)
    report_from_dict = verify_profile_view(payload)
    assert report_from_path["profile_semantic_hash"] == report_from_dict["profile_semantic_hash"]
    assert report_from_path["ok"] == report_from_dict["ok"]
