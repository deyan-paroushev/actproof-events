"""Tests for the assessment-keyed store spine (B8). The public API exposes no
assessment selector yet; this proves the internal contract: default resolution,
explicit-default identity (same body and same projection hash), unknown rejection
across every read path, and the assessment_selection metadata on the rich views.
Runs under pytest and directly."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # type: ignore  # noqa: E402

from actproof_events import store as st  # noqa: E402

DORA = "op:eu.dora.ict_incident_notification_initial.v1"
FIELD = "classification_criteria_triggered"
DEFAULT = st.DEFAULT_ASSESSMENT_ID


@pytest.fixture(scope="module")
def store():
    return st.rebuild()


def test_default_assessment_id_is_namespaced():
    assert DEFAULT == "actproof.evidence_layer_complexity.v1"


def test_store_keyed_by_act_and_assessment(store):
    assert (DORA, DEFAULT) in store.assessments_by_key
    assert store.default_assessment_by_act_id[DORA] == DEFAULT


def test_none_resolves_to_maintainer_default(store):
    implicit = store.profile_view(DORA)
    explicit = store.profile_view(DORA, assessment_id=DEFAULT)
    assert implicit == explicit  # identical body


def test_explicit_default_has_identical_projection_hash(store):
    implicit = store.cached_profile_view(DORA)
    explicit = store.cached_profile_view(DORA, assessment_id=DEFAULT)
    assert implicit.response_projection_hash == explicit.response_projection_hash
    assert implicit.body == explicit.body


def test_unknown_assessment_rejected_on_every_path(store):
    for call in (
        lambda: store.profile_view(DORA, assessment_id="bank-x.v1"),
        lambda: store.field_views(DORA, assessment_id="bank-x.v1"),
        lambda: store.field_view(DORA, FIELD, assessment_id="bank-x.v1"),
        lambda: store.grounded_field(DORA, FIELD, assessment_id="bank-x.v1"),
        lambda: store.evidence_checklist(DORA, assessment_id="bank-x.v1"),
        lambda: store.cached_profile_view(DORA, assessment_id="bank-x.v1"),
        lambda: store.cached_grounded_field(DORA, FIELD, assessment_id="bank-x.v1"),
        lambda: store.cached_evidence_checklist(DORA, assessment_id="bank-x.v1"),
        lambda: store.assessment_rows(DORA, assessment_id="bank-x.v1"),
    ):
        with pytest.raises(KeyError):
            call()


def test_rich_views_carry_assessment_selection(store):
    for body in (store.profile_view(DORA),
                 store.grounded_field(DORA, FIELD),
                 store.evidence_checklist(DORA)):
        sel = body["assessment_selection"]
        assert sel["selected"] == DEFAULT
        assert sel["selection_reason"] == "maintainer_default"
        assert sel["available_count"] == 1


def test_thin_views_do_not_carry_selection(store):
    # The bare field row, the field list, and the profiles index stay clean.
    assert "assessment_selection" not in store.field_view(DORA, FIELD)
    assert all("assessment_selection" not in r for r in store.field_views(DORA))
    assert all("assessment_selection" not in p for p in store.profiles_index())


def test_cached_grounded_resolves_assessment_and_field(store):
    cv = store.cached_grounded_field(DORA, FIELD)
    assert cv.body["field_id"] == FIELD
    assert cv.body["assessment_selection"]["selected"] == DEFAULT
    with pytest.raises(KeyError):
        store.cached_grounded_field(DORA, "no_such_field")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
