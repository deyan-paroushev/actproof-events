import json
from pathlib import Path

from actproof_events.profile_governance import (
    build_bank_poc_pack,
    build_governance_status,
    list_challenge_records,
    list_review_records,
    validate_profile_governance,
)

ACT_ID = "op:eu.dora.ict_incident_notification_initial.v1"


def test_governance_status_is_maintainer_reviewed_and_bounded():
    status = build_governance_status(ACT_ID)
    assert status["schema"] == "actproof.profile_governance_status.v1"
    # Honest scoping: 7 high-interpretation field derivations are held at draft,
    # so the WHOLE-PROFILE lifecycle is candidate (weakest-link), not
    # maintainer_reviewed. The maintainer review still exists and is hash-bound.
    assert status["lifecycle_state"] == "candidate"
    assert status["latest_review_status"] == "maintainer_reviewed"
    assert status["latest_review_record_hash"].startswith("sha256:")
    assert len(status["reviewed_field_ids"]) == 20
    assert len(status["held_at_draft_field_ids"]) == 7
    assert status["open_challenges"] >= 1
    assert "not standalone compliance authority" in status["bank_use_boundary"]


def test_review_records_are_hash_bound_to_artifacts():
    records = list_review_records(ACT_ID)
    assert records
    record = records[0]
    assert record["review_status"] == "maintainer_reviewed"
    assert record["review_record_hash"].startswith("sha256:")
    artifacts = record["reviewed_artifacts"]
    assert artifacts["profile_semantic_hash"].startswith("sha256:")
    assert artifacts["source_atoms_hash"].startswith("sha256:")
    assert "not external legal review" in record["review_limitations"]


def test_challenge_records_include_known_coverage_gap():
    records = list_challenge_records(ACT_ID)
    assert any(r["challenge_type"] == "coverage_gap" for r in records)
    assert any(r.get("source_atom_id") == "src.eu.dora.32025R0301.art1.content_rules" for r in records)
    assert all(r["challenge_record_hash"].startswith("sha256:") for r in records)


def test_validate_profile_governance_passes():
    assert validate_profile_governance(ACT_ID) == []


def test_bank_poc_pack_exports_expected_files(tmp_path: Path):
    out = tmp_path / "bank-poc-pack"
    manifest = build_bank_poc_pack(ACT_ID, out_dir=out)
    assert manifest["schema"] == "actproof.bank_poc_pack.v1"
    expected = {
        "dora.profile-view.json",
        "profile-lock.json",
        "source-atom-coverage.json",
        "completeness.json",
        "governance-status.json",
        "review-records.json",
        "challenge-records.json",
        "bank-review-checklist.json",
        "candidate-mapping-report.json",
        "prevalidation-report.json",
        "known-boundaries.json",
        "README_BANK_POC.md",
        "bank-poc-pack-manifest.json",
    }
    assert expected.issubset({p.name for p in out.iterdir()})
    status = json.loads((out / "governance-status.json").read_text())
    assert status["lifecycle_state"] == "candidate"


# --- merge: honesty guardrails (held fields keep profile from overclaiming) ---

def test_held_fields_keep_profile_below_maintainer_reviewed():
    """A partial maintainer review must NOT promote the whole profile."""
    status = build_governance_status(ACT_ID)
    # there is a real maintainer review, but with held fields
    assert status["latest_review_status"] == "maintainer_reviewed"
    assert status["held_at_draft_field_ids"]  # non-empty
    # therefore the whole-profile state is held below maintainer_reviewed
    assert status["lifecycle_state"] != "maintainer_reviewed"


def test_held_fields_are_the_high_interpretation_ones():
    import json as _json
    status = build_governance_status(ACT_ID)
    held = set(status["held_at_draft_field_ids"])
    derivs = _json.load(open(
        "source_bindings/eu/dora/ict_incident_notification_initial.v1.field_derivations.json"
    ))["field_derivations"]
    high = {x["field_id"] for x in derivs if (x.get("interpretive_load") or 0) >= 2}
    assert held == high  # exactly the high-interpretation fields are held
