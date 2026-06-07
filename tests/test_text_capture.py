"""Tests for v2.5.0 merged official-text capture + reporting."""
import hashlib
import pytest

from actproof_events.source_binding import (
    list_source_atoms, compute_source_atom_identity_hash,
)
from actproof_events.text_capture import (
    normalise_official_text, compute_official_text_sha256,
    capture_atom_official_text, verify_atom_official_text,
    compute_atom_text_coverage, validate_atom_text, atom_text_maturity,
    build_atom_dependency_report, export_atom_inventory,
    OFFICIAL_TEXT_NORMALISATION_BASIS,
)

ACT = "op:eu.dora.ict_incident_notification_initial.v1"
ATOM = {"source_atom_id": "src.test.art19", "celex": "32022R2554",
        "eli": "http://data.europa.eu/eli/reg/2022/2554/oj", "atom_type": "article",
        "locator": {"article": "19"}, "source_role": "base_obligation",
        "normative_weight": "primary", "source_document_sha256": "sha256:abc",
        "derivation_note": "n"}
SRC = {"system": "EUR-Lex", "celex": "32022R2554", "format_basis": "eurlex_html",
       "source_file": "L_2022333EN_01000101_xml.html", "retrieved_at": "2026-06-07"}


def _with_identity(a):
    a = dict(a); a["atom_identity_sha256"] = compute_source_atom_identity_hash(a); return a


def test_normalisation_preserves_line_structure():
    # points (a)/(b) must stay on separate lines, not collapse to one
    raw = "4. Submit:\n(a)\nan initial notification;\n(b)\nan intermediate report;"
    n = normalise_official_text(raw)
    assert "\n(a)\n" in n or n.count("\n") >= 3  # structure preserved
    assert n.endswith("\n") and "\r" not in n


def test_normalisation_idempotent():
    raw = "1.\u00a0\u00a0\u00a0Financial   entities  shall report.\r\n\r\n\r\n"
    n = normalise_official_text(raw)
    assert n == normalise_official_text(n)
    assert "\u00a0" not in n and "  " not in n


def test_hash_over_normalised_utf8():
    raw = "  Article 19  \n"
    expected = "sha256:" + hashlib.sha256(normalise_official_text(raw).encode("utf-8")).hexdigest()
    assert compute_official_text_sha256(raw) == expected


def test_capture_does_not_change_identity_hash():
    atom = _with_identity(ATOM)
    before = atom["atom_identity_sha256"]
    cap = capture_atom_official_text(atom, "Article 19(1) text.", boundary_rule="article_paragraph",
                                     official_text_source=SRC, text_locator={"article": "19", "paragraph": "1"})
    assert cap["atom_identity_sha256"] == before
    assert cap["locator"] == {"article": "19"}                       # identity locator untouched
    assert cap["text_locator"] == {"article": "19", "paragraph": "1"}  # refinement recorded separately


def test_capture_sets_binding_not_review():
    cap = capture_atom_official_text(_with_identity(ATOM), "x", boundary_rule="article_paragraph",
                                     official_text_source=SRC)
    # capture must NOT introduce or change binding_status (the review/verification
    # axis, schema enum verified|provisional); it only sets the capture axis.
    assert "binding_status" not in cap  # was absent on the input atom, stays absent
    assert cap["text_capture_status"] == "captured_draft"
    assert cap["text_review_status"] == "draft"


def test_capture_refuses_empty():
    with pytest.raises(ValueError):
        capture_atom_official_text(_with_identity(ATOM), "   ", boundary_rule="x", official_text_source=SRC)


def test_verify_passes_and_detects_tamper():
    cap = capture_atom_official_text(_with_identity(ATOM), "Article 19(1) text.",
                                     boundary_rule="article_paragraph", official_text_source=SRC)
    assert verify_atom_official_text(cap)["ok"] is True
    cap["text_excerpt"] += " TAMPERED"
    v = verify_atom_official_text(cap)
    assert v["ok"] is False and v["reason"] == "hash_mismatch"


def test_shipped_pilot_atoms_capture_and_verify():
    atoms = list_source_atoms(ACT)
    captured = [a for a in atoms if a.get("text_excerpt")]
    assert len(captured) == 3
    for a in captured:
        assert verify_atom_official_text(a)["ok"] is True
        assert a["atom_identity_sha256"] == compute_source_atom_identity_hash(a)
        assert a["binding_status"] == "provisional"
        assert a["text_review_status"] == "draft"
        assert atom_text_maturity(a) == "M5_text_hashed_draft"


def test_validate_atom_text_passes_on_shipped_set():
    # validate re-hashes every captured atom; clean captures must produce no errors
    assert validate_atom_text(ACT) == []


def test_coverage_reports_three_of_twentysix_pilot():
    cov = compute_atom_text_coverage(ACT)
    assert cov["atoms_total"] == 26
    assert cov["text_captured_and_hashed"] == 3
    assert cov["text_capture_status"] == "pilot"
    assert cov["by_maturity"].get("M5_text_hashed_draft") == 3
    assert cov["by_maturity"].get("M2_identity_hashed_locator_bound") == 23


def test_dependency_report_and_inventory():
    dep = build_atom_dependency_report(ACT)
    assert dep["summary"]["atoms_total"] == 26
    assert dep["summary"]["text_hashed_atoms"] == 3
    inv = export_atom_inventory(ACT)
    assert len(inv["atoms"]) == 26
    assert all("text_maturity" in a for a in inv["atoms"])
