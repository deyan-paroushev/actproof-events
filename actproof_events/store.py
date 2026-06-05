"""Immutable, layered profile store.

Builds every profile view, field view, catalogue entry hash and assessment row
once, at construction, then serves deep copies. Nothing is recomputed per
request and nothing a caller receives can mutate the cache. To refresh, build a
new store (or call ``rebuild()``); never mutate a live one.

Layers, as agreed for Sprint B:

    raw_profiles_by_act_id            act_id -> parsed catalogue profile
    catalogue_entry_hash_by_act_id    act_id -> sha256 of the raw entry file bytes
    assessments_by_key                (act_id, assessment_id) -> scored rows
    default_assessment_by_act_id      act_id -> the maintainer default assessment_id
    computed_profile_views_by_act_id  act_id -> get_profile() output, built once
    computed_field_views_by_act_id    act_id -> list_fields() output, built once
    computed_grounded_fields_by_act_id act_id -> {field_id: get_field() output}
    computed_evidence_checklist_by_act_id act_id -> generate_evidence_checklist()

A profiles index (list_profiles output) is built once as well, so every GET the
API serves is a cached deep copy and nothing is derived per request.

Assessments are keyed by ``(act_id, assessment_id)`` from the start so the later
profile / derivations / assessment split does not force a refactor. Today each
profile carries a single maintainer-default assessment, the evidence-layer
scores, recorded under DEFAULT_ASSESSMENT_ID. Service methods can already accept
``assessment_id``; passing None selects the default, and an unknown id raises.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from actproof_events import services as svc

# The single assessment present today, namespaced by maintainer and rubric so a
# second maintainer's assessment (for example "bank-x.evidence_layer_complexity.v1")
# slots in without renaming. Callers and the store already speak the
# multi-assessment contract before a second assessment exists.
DEFAULT_ASSESSMENT_ID = "actproof.evidence_layer_complexity.v1"


def _selection_block(assessment_id: str, available_count: int) -> dict[str, Any]:
    """Assessment provenance carried on the rich views. There is no public
    selector yet, so selection_reason is always maintainer_default and there is
    no 'requested' field; that keeps implicit and explicit-default bodies
    identical, and therefore their projection hashes identical."""
    return {
        "selected": assessment_id,
        "selection_reason": "maintainer_default",
        "available_count": available_count,
    }


@dataclass(frozen=True)
class CachedView:
    """A GET response body with its HTTP cache identity. response_projection_hash
    is sha256 of the stable-JSON projection (the body minus the hash field
    itself), and is an HTTP caching artefact only, not a receipt hash."""
    body: Any
    response_projection_hash: str
    etag: str


def _stable_json(obj: Any) -> str:
    # Stable Python JSON. Good enough for an HTTP cache key. NOT JCS, and it does
    # not imply receipt compatibility.
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _projection_hash(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(_stable_json(obj).encode("utf-8")).hexdigest()


def _build_cached_view(body: Any, catalogue_entry_hash: str | None = None) -> CachedView:
    """Compute the projection hash and ETag for a response body. For dict bodies
    the deterministic ``catalogue_entry_hash`` is included in the hashed
    projection and both hashes are exposed in the body; the projection excludes
    ``response_projection_hash`` itself to avoid self-reference. List bodies stay
    pure arrays and carry their identity through the ETag only."""
    body = copy.deepcopy(body)
    if isinstance(body, dict):
        if catalogue_entry_hash is not None:
            body.setdefault("catalogue_entry_hash", catalogue_entry_hash)
            body.setdefault("catalogue_entry_hash_basis", svc.CATALOGUE_ENTRY_HASH_BASIS)
        projection = {k: v for k, v in body.items() if k != "response_projection_hash"}
    else:
        projection = body
    digest = _projection_hash(projection)
    if isinstance(body, dict):
        body["response_projection_hash"] = digest
    return CachedView(body=body, response_projection_hash=digest, etag=f'"{digest}"')


class ProfileStore:
    """A built-once, read-only view over the catalogue. Frozen after build."""

    def __init__(self, catalogue_root: Path | None = None) -> None:
        raw = svc.load_profiles(catalogue_root)
        scores = svc._scores_index()

        raw_profiles_by_act_id: dict[str, dict[str, Any]] = {}
        catalogue_entry_hash_by_act_id: dict[str, str | None] = {}
        assessments_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        default_assessment_by_act_id: dict[str, str] = {}
        computed_profile_views_by_act_id: dict[str, dict[str, Any]] = {}
        computed_field_views_by_act_id: dict[str, list[dict[str, Any]]] = {}
        computed_grounded_fields_by_act_id: dict[str, dict[str, dict[str, Any]]] = {}
        computed_evidence_checklist_by_act_id: dict[str, dict[str, Any]] = {}

        for act_id, profile in raw.items():
            raw_profiles_by_act_id[act_id] = copy.deepcopy(profile)

            # Field-level derivations must reference a real source binding once
            # profiles carry ids. No-op today (profiles expose none yet).
            svc.check_derivation_references(profile)

            entry_path = profile.get("_catalogue_path")
            catalogue_entry_hash_by_act_id[act_id] = (
                svc.catalogue_entry_hash(entry_path) if entry_path else None
            )

            assessments_by_key[(act_id, DEFAULT_ASSESSMENT_ID)] = copy.deepcopy(scores.get(act_id, {}))
            default_assessment_by_act_id[act_id] = DEFAULT_ASSESSMENT_ID

            # Built once. get_profile / list_fields carry the rubric, scope flags
            # and boundary id, so the heavy derivation happens here, not per call.
            profile_view = copy.deepcopy(svc.get_profile(act_id, catalogue_root))
            computed_field_views_by_act_id[act_id] = svc.list_fields(
                act_id, required_only=False, catalogue_root=catalogue_root
            )
            # The grounding answer and the checklist are built once too, so the
            # API's hot read paths (/source, /evidence-checklist) are cache hits.
            grounded = {
                row["field_id"]: svc.get_field(act_id, row["field_id"], catalogue_root)
                for row in computed_field_views_by_act_id[act_id]
            }
            checklist = svc.generate_evidence_checklist(act_id, catalogue_root)

            # Assessment provenance on the rich views. available_count is the
            # number of assessments held for this act (one today).
            available = sum(1 for (a, _) in assessments_by_key if a == act_id)
            sel = _selection_block(DEFAULT_ASSESSMENT_ID, available)
            profile_view["assessment_selection"] = dict(sel)
            checklist["assessment_selection"] = dict(sel)
            for g in grounded.values():
                g["assessment_selection"] = dict(sel)

            computed_profile_views_by_act_id[act_id] = profile_view
            computed_grounded_fields_by_act_id[act_id] = grounded
            computed_evidence_checklist_by_act_id[act_id] = checklist

        self._catalogue_root = catalogue_root
        self.raw_profiles_by_act_id = raw_profiles_by_act_id
        self.catalogue_entry_hash_by_act_id = catalogue_entry_hash_by_act_id
        self.assessments_by_key = assessments_by_key
        self.default_assessment_by_act_id = default_assessment_by_act_id
        self.computed_profile_views_by_act_id = computed_profile_views_by_act_id
        self.computed_field_views_by_act_id = computed_field_views_by_act_id
        self.computed_grounded_fields_by_act_id = computed_grounded_fields_by_act_id
        self.computed_evidence_checklist_by_act_id = computed_evidence_checklist_by_act_id
        self._profiles_index = svc.list_profiles(catalogue_root)

        # Precompute HTTP cache views (response_projection_hash + ETag) once. The
        # /fields list has two deterministic shapes (full and required_only), so
        # both are cached.
        self._cv_profiles_index = _build_cached_view(self._profiles_index)
        cv_profile_view: dict[tuple[str, str], CachedView] = {}
        cv_field_views: dict[tuple[str, str], dict[bool, CachedView]] = {}
        cv_field_view: dict[tuple[str, str, str], CachedView] = {}
        cv_grounded: dict[tuple[str, str, str], CachedView] = {}
        cv_evidence_checklist: dict[tuple[str, str], CachedView] = {}
        for act_id in raw:
            aid = default_assessment_by_act_id[act_id]
            ceh = catalogue_entry_hash_by_act_id[act_id]
            cv_profile_view[(act_id, aid)] = _build_cached_view(computed_profile_views_by_act_id[act_id], ceh)
            full_rows = computed_field_views_by_act_id[act_id]
            req_rows = [r for r in full_rows if r["required"]]
            cv_field_views[(act_id, aid)] = {
                False: _build_cached_view(full_rows),
                True: _build_cached_view(req_rows),
            }
            for row in full_rows:
                cv_field_view[(act_id, aid, row["field_id"])] = _build_cached_view(row, ceh)
            for field_id, grounded in computed_grounded_fields_by_act_id[act_id].items():
                cv_grounded[(act_id, aid, field_id)] = _build_cached_view(grounded, ceh)
            cv_evidence_checklist[(act_id, aid)] = _build_cached_view(
                computed_evidence_checklist_by_act_id[act_id], ceh
            )
        self._cv_profile_view = cv_profile_view
        self._cv_field_views = cv_field_views
        self._cv_field_view = cv_field_view
        self._cv_grounded = cv_grounded
        self._cv_evidence_checklist = cv_evidence_checklist

        # Freeze. From here, attribute assignment is refused.
        object.__setattr__(self, "_frozen", True)

    # -- immutability -------------------------------------------------------
    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise AttributeError(
                "ProfileStore is immutable. Build a new store with rebuild() "
                "instead of mutating a live one."
            )
        object.__setattr__(self, name, value)

    # -- internal helpers ---------------------------------------------------
    def _require_act(self, act_id: str) -> str:
        act_id = svc._normalise_act_id(act_id)
        if act_id not in self.raw_profiles_by_act_id:
            raise KeyError(f"Unknown ActProof profile: {act_id}")
        return act_id

    def _resolve_assessment(self, act_id: str, assessment_id: str | None) -> str:
        """None selects the maintainer default; an unknown id is an error, never
        a silent fall-back, so a caller asking for an assessment that does not
        exist is told so rather than handed the default."""
        if assessment_id is None:
            return self.default_assessment_by_act_id[act_id]
        if (act_id, assessment_id) not in self.assessments_by_key:
            raise KeyError(f"Unknown assessment {assessment_id!r} for profile {act_id}")
        return assessment_id

    # -- reads (every return is a deep copy) --------------------------------
    def act_ids(self) -> list[str]:
        return sorted(self.raw_profiles_by_act_id)

    def raw_profile(self, act_id: str) -> dict[str, Any]:
        return copy.deepcopy(self.raw_profiles_by_act_id[self._require_act(act_id)])

    def catalogue_entry_hash(self, act_id: str) -> str | None:
        return self.catalogue_entry_hash_by_act_id[self._require_act(act_id)]

    def profile_view(self, act_id: str, assessment_id: str | None = None) -> dict[str, Any]:
        act_id = self._require_act(act_id)
        self._resolve_assessment(act_id, assessment_id)
        return copy.deepcopy(self.computed_profile_views_by_act_id[act_id])

    def field_views(self, act_id: str, assessment_id: str | None = None) -> list[dict[str, Any]]:
        act_id = self._require_act(act_id)
        self._resolve_assessment(act_id, assessment_id)
        return copy.deepcopy(self.computed_field_views_by_act_id[act_id])

    def field_view(self, act_id: str, field_id: str, assessment_id: str | None = None) -> dict[str, Any]:
        for row in self.field_views(act_id, assessment_id):
            if row["field_id"] == field_id:
                return row
        raise KeyError(f"Unknown field {field_id!r} for profile {self._require_act(act_id)}")

    def assessment_rows(self, act_id: str, assessment_id: str | None = None) -> dict[str, Any]:
        act_id = self._require_act(act_id)
        resolved = self._resolve_assessment(act_id, assessment_id)
        return copy.deepcopy(self.assessments_by_key[(act_id, resolved)])

    def profiles_index(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._profiles_index)

    def grounded_field(self, act_id: str, field_id: str, assessment_id: str | None = None) -> dict[str, Any]:
        """The full grounding answer for a field (citation, hash-pinned sources,
        non-claims, boundary), served from cache."""
        act_id = self._require_act(act_id)
        self._resolve_assessment(act_id, assessment_id)
        grounded = self.computed_grounded_fields_by_act_id[act_id]
        if field_id not in grounded:
            raise KeyError(f"Unknown field {field_id!r} for profile {act_id}")
        return copy.deepcopy(grounded[field_id])

    def evidence_checklist(self, act_id: str, assessment_id: str | None = None) -> dict[str, Any]:
        act_id = self._require_act(act_id)
        self._resolve_assessment(act_id, assessment_id)
        return copy.deepcopy(self.computed_evidence_checklist_by_act_id[act_id])

    # -- cached views for HTTP (body + response_projection_hash + ETag) ------
    def _copy_cv(self, cv: CachedView) -> CachedView:
        return CachedView(copy.deepcopy(cv.body), cv.response_projection_hash, cv.etag)

    def cached_profiles_index(self) -> CachedView:
        return self._copy_cv(self._cv_profiles_index)

    def cached_profile_view(self, act_id: str, assessment_id: str | None = None) -> CachedView:
        act_id = self._require_act(act_id)
        aid = self._resolve_assessment(act_id, assessment_id)
        return self._copy_cv(self._cv_profile_view[(act_id, aid)])

    def cached_field_views(self, act_id: str, required_only: bool = False,
                           assessment_id: str | None = None) -> CachedView:
        act_id = self._require_act(act_id)
        aid = self._resolve_assessment(act_id, assessment_id)
        return self._copy_cv(self._cv_field_views[(act_id, aid)][bool(required_only)])

    def cached_field_view(self, act_id: str, field_id: str,
                          assessment_id: str | None = None) -> CachedView:
        act_id = self._require_act(act_id)
        aid = self._resolve_assessment(act_id, assessment_id)
        key = (act_id, aid, field_id)
        if key not in self._cv_field_view:
            raise KeyError(f"Unknown field {field_id!r} for profile {act_id}")
        return self._copy_cv(self._cv_field_view[key])

    def cached_grounded_field(self, act_id: str, field_id: str,
                              assessment_id: str | None = None) -> CachedView:
        act_id = self._require_act(act_id)
        aid = self._resolve_assessment(act_id, assessment_id)
        key = (act_id, aid, field_id)
        if key not in self._cv_grounded:
            raise KeyError(f"Unknown field {field_id!r} for profile {act_id}")
        return self._copy_cv(self._cv_grounded[key])

    def cached_evidence_checklist(self, act_id: str, assessment_id: str | None = None) -> CachedView:
        act_id = self._require_act(act_id)
        aid = self._resolve_assessment(act_id, assessment_id)
        return self._copy_cv(self._cv_evidence_checklist[(act_id, aid)])


# Process-wide singleton. Built lazily, refreshed only by rebuild().
_STORE: ProfileStore | None = None
_LOCK = threading.Lock()


def get_store(catalogue_root: Path | None = None) -> ProfileStore:
    global _STORE
    if _STORE is None:
        with _LOCK:
            if _STORE is None:
                _STORE = ProfileStore(catalogue_root)
    return _STORE


def rebuild(catalogue_root: Path | None = None) -> ProfileStore:
    """Replace the live store with a freshly built one and return it. The old
    store is left untouched for any caller still holding it."""
    global _STORE
    new = ProfileStore(catalogue_root)
    with _LOCK:
        _STORE = new
    return new
