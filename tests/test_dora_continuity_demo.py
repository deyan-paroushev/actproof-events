# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Tests for the source-dependency continuity demo (worked example: DORA 301 -> 302)."""

from __future__ import annotations

import json
from pathlib import Path

from actproof_events.dora_continuity_demo import (
    _continuity_state,
    _dependency_root_envelope,
    _profile_dependency_statement,
    _summary_atom,
    _verbatim_atom,
    run,
)
from actproof_events.scitt_profile import canonical_json_sha256


def _atom(atom_id, status="required"):
    return _summary_atom(atom_id, "32025R0301", "http://example/eli", "summary", "role", status)


def test_dependency_root_is_order_independent():
    a, b = _atom("eu.x.a"), _atom("eu.x.b")
    r1 = canonical_json_sha256(_dependency_root_envelope([a, b]))
    r2 = canonical_json_sha256(_dependency_root_envelope([b, a]))
    assert r1 == r2


def test_profile_version_not_in_dependency_root():
    a, b = _atom("eu.x.a"), _atom("eu.x.b")
    s1 = _profile_dependency_statement("v1", "policy one", [a, b])
    s2 = _profile_dependency_statement("v9", "policy nine", [a, b])
    assert s1["dependency_root"] == s2["dependency_root"]
    assert s1["profile_dependency_statement_hash"] != s2["profile_dependency_statement_hash"]


def test_demo_uses_package_canonicalizer_not_local_hashing():
    # The statement hash must equal the package canonicaliser over the statement
    # minus its own hash field. This guards against drifting back to a local hash.
    stmt = _profile_dependency_statement("v1", "policy", [_atom("eu.x.a")])
    from actproof_events.statement_profiles import compute_profile_dependency_statement_hash
    recomputed = compute_profile_dependency_statement_hash(stmt)
    assert stmt["profile_dependency_statement_hash"] == recomputed
    assert stmt["statement_hash"] == recomputed


def test_aligned_when_roots_match():
    a = _atom("eu.x.a")
    root = _profile_dependency_statement("v1", "p", [a])["dependency_root"]
    state, added, removed, replaced = _continuity_state(root, root, [a], [a])
    assert state == "ALIGNED"


def test_needs_review_when_dependency_added():
    a, b = _atom("eu.x.a"), _atom("eu.x.b")
    old = _profile_dependency_statement("v1", "p", [a])["dependency_root"]
    new = _profile_dependency_statement("v2", "p", [a, b])["dependency_root"]
    state, added, removed, replaced = _continuity_state(old, new, [a], [a, b])
    assert state == "NEEDS_REVIEW"
    assert added == ["eu.x.b"] and removed == []


def test_bare_removal_is_needs_review_not_superseded():
    a, b = _atom("eu.x.a"), _atom("eu.x.b")
    old = _profile_dependency_statement("v1", "p", [a, b])["dependency_root"]
    new = _profile_dependency_statement("v2", "p", [a])["dependency_root"]
    state, added, removed, replaced = _continuity_state(old, new, [a, b], [a])
    assert state == "NEEDS_REVIEW"
    assert removed == ["eu.x.b"] and replaced == []


def test_superseded_requires_explicit_replacement():
    old = [_atom("eu.x.old")]
    new = [_atom("eu.x.new")]
    old_root = _profile_dependency_statement("v1", "p", old)["dependency_root"]
    new_root = _profile_dependency_statement("v2", "p", new)["dependency_root"]
    state, added, removed, replaced = _continuity_state(
        old_root, new_root, old, new,
        replacements=[{"old": "eu.x.old", "new": "eu.x.new", "reason": "declared profile replacement"}],
    )
    assert state == "SUPERSEDED"
    assert replaced and replaced[0]["new"] == "eu.x.new"


def test_statement_is_eligible_for_cose_receipt():
    stmt = _profile_dependency_statement("v1", "p", [_atom("eu.x.a")])
    assert stmt["receipt_status"] == "eligible_for_local_cose_receipt"
    assert stmt["statement_type"] == "actproof/profile-dependency/v1"
    assert stmt["statement_hash"] == stmt["profile_dependency_statement_hash"]


def test_verbatim_atom_labels_role_correctly():
    atom = _verbatim_atom("eu.x.v", "32022R2554", "http://e/eli", "Art 1", "text\n", "base", "required")
    assert atom["source_role"] == "verbatim_official_text_excerpt"
    assert atom["official_text_sha256"].startswith("sha256:")


def test_summary_atom_does_not_claim_official_text():
    atom = _summary_atom("eu.x.s", "32025R0301", "http://e/eli", "summary", "role", "required")
    assert atom["source_role"] == "summary_descriptor"
    assert "official_text_sha256" not in atom
    assert "summary_text_sha256" in atom


def test_demo_runs_end_to_end_and_produces_needs_review(tmp_path: Path):
    rc = run(workdir=tmp_path)
    assert rc == 0
    assessment = json.loads((tmp_path / "continuity" / "continuity-check.v1-to-v2.json").read_text())
    assert assessment["continuity_state"] == "NEEDS_REVIEW"
    assert assessment["legal_conclusion"] == "not_assessed"
    # coherence chain: binding record binds to the v1 statement hash
    artifact = json.loads((tmp_path / "downstream-binding" / "bank-x-reporting-form.binding.v1.json").read_text())
    assert artifact["relied_on_profile_dependency_statement_hash"] == assessment["artifact_relied_on_statement_hash"]
    assert artifact["binding_status"] == "not_a_receipt"
    # real receipt over the source-atom statement (substrate proof)
    receipt = json.loads((tmp_path / "receipts" / "source-atom.receipt.json").read_text())
    assert receipt["registration_status"] == "registered_local_transparency_pilot"
    v1_receipt = json.loads((tmp_path / "receipts" / "profile-dependency.v1.receipt.json").read_text())
    v2_receipt = json.loads((tmp_path / "receipts" / "profile-dependency.v2.receipt.json").read_text())
    assert v1_receipt["statement_type"] == "actproof/profile-dependency/v1"
    assert v2_receipt["statement_type"] == "actproof/profile-dependency/v1"
    assert artifact["relied_on_profile_dependency_receipt_hash"] == v1_receipt["receipt_hash"]
    assert assessment["current_profile_receipt_hash"] == v2_receipt["receipt_hash"]


def test_no_private_key_committed_when_runtime_generated(tmp_path: Path):
    # Keys are generated into the output dir at runtime, which is fine; what matters
    # is that the committed examples tree does not ship a private key (checked separately).
    run(workdir=tmp_path)
    # the private key exists in the runtime output (expected), proving runtime generation
    assert (tmp_path / "source-atom.dev.private-key.pem").exists()
