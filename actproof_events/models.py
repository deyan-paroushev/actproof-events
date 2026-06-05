"""Pydantic response models for the /v1 API.

Strict at the top level, open underneath. Every model declares the fields the
contract guarantees today, with real types, so the OpenAPI schema documents them
and a drift in a guaranteed field (for example an unexpected interpretive_status)
fails loudly. ``extra="allow"`` is the escape hatch: any field not yet modelled,
or one we add later, passes through untouched instead of being dropped. This is
why the models can be precise now without freezing the surface against growth.

These import pydantic, so api.py imports this module only when the optional API
dependencies are installed.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    # Declared fields are typed and validated; unknown fields pass through.
    model_config = ConfigDict(extra="allow")


class AssessmentSelection(APIModel):
    """Which assessment produced the interpretive scoring on this view. There is
    no public selector yet, so selection_reason is maintainer_default today."""
    selected: str
    selection_reason: str
    available_count: int


class FieldView(APIModel):
    """One field row: the typed map plus the evidence-layer signal."""
    field_id: str
    required: bool
    type: str
    disclosure_tier: str
    interpretive_status: Literal["direct", "derived", "interpretive", "unscored"]
    mapping_type: str | None = None
    interpretive_load: int | None = None
    rubric_id: str | None = None
    interpretive: bool
    rationale: str = ""
    evidence_burden: int | None = None
    evidence_labels: list[str] = Field(default_factory=list)
    evidence_scope: Literal["profile", "field"]


class GroundedField(FieldView):
    """The full grounding answer for one field: the row plus citation,
    hash-pinned sources, the non-claims, and the boundary."""
    act_id: str
    regulatory_citation: dict[str, Any] | None = None
    source_basis: list[dict[str, Any]] = Field(default_factory=list)
    source_basis_scope: Literal["act", "field"]
    fallback_used: bool
    non_claims: list[str] = Field(default_factory=list)
    boundary: str
    boundary_id: str
    assessment_selection: AssessmentSelection | None = None
    catalogue_entry_hash: str | None = None
    catalogue_entry_hash_basis: str | None = None
    response_projection_hash: str | None = None


class FieldDetail(FieldView):
    """A single field served on its own endpoint. Carries the cache and binding
    hashes; the list endpoint serves bare FieldView rows without them."""
    catalogue_entry_hash: str | None = None
    catalogue_entry_hash_basis: str | None = None
    response_projection_hash: str | None = None


class ProfileSummary(APIModel):
    """One entry in the profiles index."""
    act_id: str
    display_name: str | None = None
    version: Any | None = None
    claim_type: str | None = None
    maturity: str | None = None
    scored: bool
    source_bound: bool
    total_field_count: int
    required_field_count: int
    optional_field_count: int
    interpretive_field_count: int
    required_evidence_count: int
    source_instrument_count: int


class ProfileView(APIModel):
    """A single profile. The raw profile fields pass through; the contract
    guarantees the computed and binding-relevant fields named here."""
    act_type_id: str | None = None
    display_name: str | None = None
    catalogue_entry_hash: str | None = None
    catalogue_entry_hash_basis: str | None = None
    response_projection_hash: str | None = None
    compatible_with_receipts: bool | None = None
    interpretive_summary: dict[str, int] | None = None
    boundary: str
    boundary_id: str
    assessment_selection: AssessmentSelection | None = None


class EvidenceChecklist(APIModel):
    act_id: str
    display_name: str | None = None
    required_evidence_labels: list[str] = Field(default_factory=list)
    required_fields: list[FieldView] = Field(default_factory=list)
    non_claims: list[str] = Field(default_factory=list)
    boundary: str
    boundary_id: str
    assessment_selection: AssessmentSelection | None = None
    catalogue_entry_hash: str | None = None
    catalogue_entry_hash_basis: str | None = None
    response_projection_hash: str | None = None


class DivergenceSummary(APIModel):
    matched_count: int
    missing_required_count: int
    missing_interpretive_required_count: int
    missing_optional_count: int
    extra_count: int
    severity: Literal["none", "low", "medium", "high"]


class DivergenceResult(APIModel):
    act_id: str
    matched: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    missing_optional: list[str] = Field(default_factory=list)
    extra: list[str] = Field(default_factory=list)
    missing_interpretive_required_fields: list[str] = Field(default_factory=list)
    divergence_summary: DivergenceSummary
    review_required: list[str] = Field(default_factory=list)
    non_claims: list[str] = Field(default_factory=list)
    boundary: str
    boundary_id: str


class BindingResult(APIModel):
    """Profile-binding check result. Never a receipt verification, so
    verification_grade is always false and binding_match is null unless an entry
    hash was supplied and compared."""
    check_type: str
    status: Literal["bound", "recognized_unbound", "mismatch", "unknown_profile", "invalid_input"]
    binding_match: bool | None = None
    verification_grade: bool
    act_type_id: str | None = None
    supplied_entry_hash: str | None = None
    local_entry_hash: str | None = None
    supplied_entry_hash_location: str | None = None
    transitional_descriptor: bool | None = None
    catalogue_entry_hash_basis: str | None = None
    supplied_entry_version: Any | None = None
    reason: str | None = None
    checks_performed: list[str] = Field(default_factory=list)
    checks_not_performed: list[str] = Field(default_factory=list)
    boundary: str
    boundary_id: str
