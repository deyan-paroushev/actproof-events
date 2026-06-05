"""Profile-binding contract.

The universal field-name rule: inside a ``catalogue`` object the key is
``entry_hash`` / ``entry_version`` (the parent qualifies it; this is what the
substrate mints and what consumers read). The prefixed ``catalogue_entry_hash``
is used only in flat contexts with no ``catalogue.`` parent (the profile block,
a bare top level), and those are transitional because they sit outside the
manifest and are not covered by ``manifest_hash``.

A bare top-level ``entry_hash`` with no ``catalogue`` parent is NOT accepted:
``entry_hash`` is meaningful only when the parent names it.
"""
import pytest

from actproof_events import services as svc

DORA = "op:eu.dora.ict_incident_notification_initial.v1"


def _local_hash():
    return svc.catalogue_entry_hash(svc.load_profiles()[DORA]["_catalogue_path"])


def test_canonical_manifest_catalogue_entry_hash_binds():
    h = _local_hash()
    r = svc.check_profile_binding(
        {"manifest": {"catalogue": {"act_type_id": DORA, "entry_hash": h, "entry_version": 2}}}
    )
    assert r["status"] == "bound"
    assert r["binding_match"] is True
    assert r["supplied_entry_hash_location"] == "manifest.catalogue.entry_hash"
    assert r["transitional_descriptor"] is False
    assert r["supplied_entry_version"] == 2
    assert r["verification_grade"] is False


def test_raw_manifest_catalogue_is_canonical():
    h = _local_hash()
    r = svc.check_profile_binding(
        {"raw_manifest": {"catalogue": {"act_type_id": DORA, "entry_hash": h}}}
    )
    assert r["status"] == "bound"
    assert r["supplied_entry_hash_location"] == "raw_manifest.catalogue.entry_hash"
    assert r["transitional_descriptor"] is False


def test_bare_catalogue_block_is_canonical():
    h = _local_hash()
    r = svc.check_profile_binding({"act_type_id": DORA, "catalogue": {"entry_hash": h}})
    assert r["status"] == "bound"
    assert r["supplied_entry_hash_location"] == "catalogue.entry_hash"
    assert r["transitional_descriptor"] is False


def test_nested_stutter_name_tolerated_as_alias():
    h = _local_hash()
    r = svc.check_profile_binding(
        {"manifest": {"catalogue": {"act_type_id": DORA, "catalogue_entry_hash": h}}}
    )
    assert r["status"] == "bound"
    # Reported under the canonical label even though the stutter key was used.
    assert r["supplied_entry_hash_location"] == "manifest.catalogue.entry_hash"


def test_profile_block_is_transitional():
    h = _local_hash()
    r = svc.check_profile_binding(
        {"act_type_id": DORA, "profile": {"catalogue_entry_hash": h, "catalogue_entry_version": 2}}
    )
    assert r["status"] == "bound"
    assert r["supplied_entry_hash_location"] == "profile.catalogue_entry_hash"
    assert r["transitional_descriptor"] is True
    assert r["supplied_entry_version"] == 2


def test_top_level_flat_is_transitional():
    h = _local_hash()
    r = svc.check_profile_binding({"act_type_id": DORA, "catalogue_entry_hash": h})
    assert r["status"] == "bound"
    assert r["transitional_descriptor"] is True


def test_bare_top_level_entry_hash_is_not_accepted():
    # entry_hash only means something inside a catalogue object. A bare top-level
    # entry_hash has no qualifying parent and must not bind.
    h = _local_hash()
    r = svc.check_profile_binding({"act_type_id": DORA, "entry_hash": h})
    assert r["status"] == "recognized_unbound"
    assert r["supplied_entry_hash_location"] is None


def test_wrong_hash_is_mismatch():
    r = svc.check_profile_binding(
        {"manifest": {"catalogue": {"act_type_id": DORA, "entry_hash": "sha256:" + "0" * 64}}}
    )
    assert r["status"] == "mismatch"
    assert r["binding_match"] is False
    assert r["verification_grade"] is False


def test_no_hash_is_recognized_unbound():
    r = svc.check_profile_binding({"act_type_id": DORA})
    assert r["status"] == "recognized_unbound"
    assert r["binding_match"] is None
    assert r["supplied_entry_hash_location"] is None


def test_unknown_profile():
    r = svc.check_profile_binding(
        {"manifest": {"catalogue": {"act_type_id": "op:does.not.exist.v1", "entry_hash": "sha256:" + "a" * 64}}}
    )
    assert r["status"] == "unknown_profile"
    assert r["verification_grade"] is False


def test_invalid_input_no_act():
    r = svc.check_profile_binding({"manifest": {"catalogue": {"entry_hash": "sha256:" + "a" * 64}}})
    assert r["status"] == "invalid_input"
    assert r["verification_grade"] is False


# --- Vector-bound: the shipped DORA conformance vector binds through the check ---

import json
from pathlib import Path

_DORA_VECTOR = (
    Path(__file__).resolve().parent.parent
    / "catalogue/acts/eu/dora/ict_incident_notification_initial.v1.test_vectors.json"
)


def test_shipped_dora_vector_binds():
    """The catalogue entry hash carried in the shipped DORA test vector binds to
    the catalogue entry available here. This locks the vector and the binding
    code together: if the catalogue bytes move without regenerating the vector,
    this fails."""
    vector = json.loads(_DORA_VECTOR.read_text())
    assert vector["catalogue_entry_version"] == 2
    r = svc.check_profile_binding({"profile": vector["profile"]})
    assert r["status"] == "bound"
    assert r["binding_match"] is True
    assert r["supplied_entry_hash_location"] == "profile.catalogue_entry_hash"
    assert r["transitional_descriptor"] is True  # flat profile block, outside the manifest
    assert r["supplied_entry_version"] == 2
    assert r["supplied_entry_hash"] == r["local_entry_hash"]
