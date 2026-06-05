"""C2 field-level derivation contract.

The source basis is field level for any field the Mapper has derived, and falls
back to the act-level instruments otherwise. The flip is per field. Malformed
Mapper output is rejected at load rather than silently accepted.
"""
import pytest

from actproof_events import services as svc

DORA = "op:eu.dora.ict_incident_notification_initial.v1"


def _two_fields():
    rows = svc.list_fields(DORA, required_only=False)
    return rows[0]["field_id"], rows[1]["field_id"]


def _entry(article="19", paragraph="1"):
    return {
        "source_binding_id": "sb_dora_art19_1",
        "celex": "32022R2554",
        "locator": {"article": article, "paragraph": paragraph, "point": None},
        "fragment_hash": "sha256:" + "ab" * 32,
        "mapping_type": "modelled",
        "review_status": "reviewed",
        "rationale": "Maps to the initial-notification trigger in Art 19(1).",
    }


@pytest.fixture
def derived(monkeypatch):
    """Install a synthetic derivation for the first field only."""
    f0, _ = _two_fields()
    monkeypatch.setattr(svc, "_field_derivations_index", lambda: {DORA: {f0: [_entry()]}})
    return f0


def test_empty_sidecar_falls_back_to_act(monkeypatch):
    monkeypatch.setattr(svc, "_field_derivations_index", lambda: {})
    f0, _ = _two_fields()
    view = svc.source_basis_view(svc.load_profiles()[DORA], f0)
    assert view["source_basis_scope"] == "act"
    assert view["fallback_used"] is True


def test_derived_field_flips_to_field_scope(derived):
    view = svc.source_basis_view(svc.load_profiles()[DORA], derived)
    assert view["source_basis_scope"] == "field"
    assert view["fallback_used"] is False
    entry = view["source_basis"][0]
    assert entry["locator"] == {"article": "19", "paragraph": "1", "point": None}
    assert entry["mapping_type"] == "modelled"
    assert entry["review_status"] == "reviewed"
    assert entry["fragment_hash"].startswith("sha256:")


def test_sibling_without_derivation_stays_act(derived):
    _, f1 = _two_fields()
    view = svc.source_basis_view(svc.load_profiles()[DORA], f1)
    assert view["source_basis_scope"] == "act"
    assert view["fallback_used"] is True


def test_get_field_reflects_field_level_basis(derived):
    gf = svc.get_field(DORA, derived)
    assert gf["source_basis_scope"] == "field"
    assert gf["fallback_used"] is False
    assert gf["source_basis"][0]["source_binding_id"] == "sb_dora_art19_1"


@pytest.mark.parametrize("mutate", [
    {"fragment_hash": "nothex"},
    {"mapping_type": "guessed"},
    {"review_status": "maybe"},
    {"locator": "art19"},
    {"source_binding_id": ""},
    {"celex": 32022},
])
def test_malformed_entry_raises(mutate):
    entry = _entry()
    entry.update(mutate)
    with pytest.raises(ValueError):
        svc._validate_derivation_entry(entry, DORA, "field_x")


@pytest.mark.parametrize("fragment_hash,ok", [
    ("sha256:" + "a" * 64, True),
    ("sha256:" + "A" * 64, False),   # uppercase rejected
    ("sha256:" + "a" * 63, False),   # too short
    ("sha256:abc", False),
    ("md5:" + "a" * 64, False),
])
def test_fragment_hash_strict_regex(fragment_hash, ok):
    entry = _entry()
    entry["fragment_hash"] = fragment_hash
    if ok:
        assert svc._validate_derivation_entry(entry, DORA, "f")["fragment_hash"] == fragment_hash
    else:
        with pytest.raises(ValueError):
            svc._validate_derivation_entry(entry, DORA, "f")


@pytest.mark.parametrize("locator,ok", [
    ({"article": "19"}, True),
    ({"annex": "II"}, True),
    ({"recital": "12", "point": "a"}, True),
    ({}, False),
    ({"article": None, "point": ""}, False),
    ({"unknown_key": "x"}, False),
])
def test_locator_must_have_a_component(locator, ok):
    entry = _entry()
    entry["locator"] = locator
    if ok:
        assert svc._validate_derivation_entry(entry, DORA, "f")["locator"] == locator
    else:
        with pytest.raises(ValueError):
            svc._validate_derivation_entry(entry, DORA, "f")


@pytest.mark.parametrize("mev,ok", [
    (None, True),
    ("actproof-mapper-extract.v1", True),
    (123, False),
])
def test_mapper_extraction_version_optional_but_typed(mev, ok):
    entry = _entry()
    if mev is not None:
        entry["mapper_extraction_version"] = mev
    if ok:
        svc._validate_derivation_entry(entry, DORA, "f")
    else:
        with pytest.raises(ValueError):
            svc._validate_derivation_entry(entry, DORA, "f")


def test_reference_integrity_dormant_without_profile_ids(monkeypatch):
    # A profile that exposes no source_binding_id (the pre-C2.1 shape) skips the
    # check entirely, so partial rollout never blocks a read.
    f0, _ = _two_fields()
    profile = dict(svc.load_profiles()[DORA])
    profile["source_bindings"] = [
        {k: v for k, v in b.items() if k != "source_binding_id"}
        for b in (profile.get("source_bindings") or [])
    ]
    monkeypatch.setattr(svc, "_field_derivations_index",
                        lambda: {DORA: {f0: [_entry()]}})
    svc.check_derivation_references(profile)  # no raise: no ids to check against


def test_reference_integrity_live_on_real_profile(monkeypatch):
    # The shipped DORA profile now carries source_binding_id values (C2.1), so the
    # check is live: a real id passes, a ghost id fails.
    f0, _ = _two_fields()
    good = _entry(); good["source_binding_id"] = "sb_dora_reg_2022_2554"
    monkeypatch.setattr(svc, "_field_derivations_index", lambda: {DORA: {f0: [good]}})
    svc.check_derivation_references(svc.load_profiles()[DORA])  # no raise
    ghost = _entry(); ghost["source_binding_id"] = "sb_does_not_exist"
    monkeypatch.setattr(svc, "_field_derivations_index", lambda: {DORA: {f0: [ghost]}})
    with pytest.raises(ValueError):
        svc.check_derivation_references(svc.load_profiles()[DORA])


def test_reference_integrity_active_with_profile_ids(monkeypatch):
    f0, _ = _two_fields()
    profile = dict(svc.load_profiles()[DORA])
    profile["source_bindings"] = [{"source_binding_id": "sb_real"}]
    # A dangling reference now fails.
    monkeypatch.setattr(svc, "_field_derivations_index",
                        lambda: {DORA: {f0: [_entry()]}})  # source_binding_id sb_dora_art19_1
    with pytest.raises(ValueError):
        svc.check_derivation_references(profile)
    # A matching reference passes.
    good = _entry(); good["source_binding_id"] = "sb_real"
    monkeypatch.setattr(svc, "_field_derivations_index",
                        lambda: {DORA: {f0: [good]}})
    svc.check_derivation_references(profile)  # no raise


def test_validate_derivations_rejects_non_object():
    with pytest.raises(ValueError):
        svc._validate_derivations([1, 2, 3], source="test")


def test_shipped_sidecar_is_empty_and_valid():
    # The shipped sidecar is empty until the Mapper populates it, so every field
    # falls back. _field_derivations_index loads it without error.
    svc._field_derivations_index.cache_clear()
    assert svc._field_derivations_index() == {}
