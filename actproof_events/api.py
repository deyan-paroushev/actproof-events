"""Optional REST API for ActProof Events.

The developer face of the shared services. Read-only. It exposes source-bound
profile facts, the per-field interpretive_status (direct / derived / interpretive)
and rationale, the hash-pinned sources, the divergence check, and a profile-binding
check (not full receipt verification). Every grounded answer carries the boundary.
It does not provide legal advice, legal certification, supervisory approval, or a
compliance determination.

Public routes are versioned under /v1. The unversioned paths remain as
development aliases (marked deprecated in the OpenAPI schema); the documented
surface is /v1 only. GET reads are served from the immutable ProfileStore, so
nothing is recomputed per request.

Run:

    pip install "actproof-events[api]"
    actproof-api --host 127.0.0.1 --port 8787
    # then: curl localhost:8787/v1/profiles
"""
from __future__ import annotations

import argparse
from typing import Any

from . import __version__
from .services import (
    BOUNDARY,
    BOUNDARY_ID,
    compare_schema_to_profile,
    check_profile_binding,
    lint_report,
    prevalidate_report,
)
from .store import get_store

try:  # optional dependency
    from fastapi import FastAPI, HTTPException, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    FastAPI = None  # type: ignore
    HTTPException = Exception  # type: ignore
    BaseModel = object  # type: ignore

# Note on routing: act ids look like
# "op:eu.dora.ict_incident_notification_initial.v1". They contain ":" and "."
# but never "/", so the default single-segment path converter ({act_id}) is
# correct. The earlier ":path" converter was greedy and swallowed the nested
# /fields/... routes; using the single-segment converter fixes that.

if FastAPI is not None:
    app = FastAPI(
        title="ActProof Events API",
        version=__version__,
        description="Read-only API for source-bound regulatory profiles, field maps, "
                    "per-field interpretive status, divergence checks and profile-binding "
                    "checks. Not full receipt verification (that lives in actproof-py). "
                    "Not legal advice; does not certify compliance. Public routes are /v1.",
    )

    # Open CORS so the static field browser or a notebook can call it in dev.
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"],
    )

    # Resource-consumption guard (OWASP API4): reject oversized request bodies
    # before they are parsed. The local service serves small schema/report
    # payloads only; 512 KiB is generous for that and caps the blast radius.
    MAX_BODY_BYTES = 512 * 1024

    @app.middleware("http")
    async def _limit_body_size(request: "Request", call_next):
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > MAX_BODY_BYTES:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=413,
                        content={"error": "request_too_large", "max_bytes": MAX_BODY_BYTES},
                    )
            except ValueError:
                pass
        return await call_next(request)

    class SchemaCompareRequest(BaseModel):
        fields: list[str]

    from .models import (
        BindingResult,
        DivergenceResult,
        EvidenceChecklist,
        FieldDetail,
        FieldView,
        GroundedField,
        ProfileSummary,
        ProfileView,
    )

    # Public catalogue views are cacheable for a short window.
    CACHE_CONTROL = "public, max-age=300"

    def _etag_token(value: str) -> str:
        """Normalise one If-None-Match token to a bare hash for comparison:
        strips weak prefix and surrounding quotes. Accepts "sha256:..",
        sha256:.., and W/"sha256:..".."""
        v = value.strip()
        if v.startswith("W/"):
            v = v[2:].strip()
        if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            v = v[1:-1]
        return v

    def _if_none_match(header: str | None, etag: str) -> bool:
        if not header:
            return False
        target = _etag_token(etag)
        for raw in header.split(","):
            token = raw.strip()
            if token == "*" or _etag_token(token) == target:
                return True
        return False

    def _conditional(request: "Request", response: "Response", cv):
        """Set ETag and Cache-Control, returning a bare 304 when the client's
        validator already matches, otherwise the cached body (response_model
        still applies on the 200 path)."""
        if _if_none_match(request.headers.get("if-none-match"), cv.etag):
            return Response(status_code=304, headers={"ETag": cv.etag, "Cache-Control": CACHE_CONTROL})
        response.headers["ETag"] = cv.etag
        response.headers["Cache-Control"] = CACHE_CONTROL
        return cv.body

    @app.get("/")
    def root() -> dict[str, Any]:
        return {
            "service": "actproof-events-api",
            "version": __version__,
            "boundary": BOUNDARY, "boundary_id": BOUNDARY_ID,
            "endpoints": [
                "GET /v1/profiles",
                "GET /v1/profiles/{act_id}",
                "GET /v1/profiles/{act_id}/fields",
                "GET /v1/profiles/{act_id}/fields/{field_id}",
                "GET /v1/profiles/{act_id}/fields/{field_id}/source",
                "GET /v1/profiles/{act_id}/evidence-checklist",
                "POST /v1/profiles/{act_id}/compare-schema",
                "POST /v1/profiles/{act_id}/lint-report",
                "POST /v1/profiles/{act_id}/prevalidate-report",
                "POST /v1/profile-bindings/check",
                "GET /v1/service-info",
                "GET /v1/profiles/{act_id}/governance-status",
                "GET /v1/profiles/{act_id}/lock",
                "GET /v1/profiles/{act_id}/source-atom-coverage",
                "GET /v1/profiles/{act_id}/completeness",
                "GET /v1/release/sbom",
                "GET /v1/release/manifest",
                "GET /health",
            ],
            "note": "Unversioned paths are deprecated development aliases.",
        }

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "actproof-events-api", "profiles": len(get_store().act_ids())}

    @app.get("/v1/profiles", response_model=list[ProfileSummary])
    @app.get("/profiles", deprecated=True)
    def api_list_profiles(request: Request, response: Response):
        return _conditional(request, response, get_store().cached_profiles_index())

    @app.get("/v1/profiles/{act_id}", response_model=ProfileView)
    @app.get("/profiles/{act_id}", deprecated=True)
    def api_get_profile(act_id: str, request: Request, response: Response):
        try:
            cv = get_store().cached_profile_view(act_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return _conditional(request, response, cv)

    @app.get("/v1/profiles/{act_id}/fields", response_model=list[FieldView])
    @app.get("/profiles/{act_id}/fields", deprecated=True)
    def api_list_fields(act_id: str, request: Request, response: Response, required_only: bool = False):
        try:
            cv = get_store().cached_field_views(act_id, required_only=required_only)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return _conditional(request, response, cv)

    @app.get("/v1/profiles/{act_id}/fields/{field_id}", response_model=FieldDetail)
    @app.get("/profiles/{act_id}/fields/{field_id}", deprecated=True)
    def api_get_field(act_id: str, field_id: str, request: Request, response: Response):
        try:
            cv = get_store().cached_field_view(act_id, field_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return _conditional(request, response, cv)

    @app.get("/v1/profiles/{act_id}/fields/{field_id}/source", response_model=GroundedField)
    @app.get("/profiles/{act_id}/fields/{field_id}/source", deprecated=True)
    def api_ground_field(act_id: str, field_id: str, request: Request, response: Response):
        """The grounding endpoint. Returns the field's interpretive_status,
        rationale, disclosure tier, hash-pinned sources, the non-claims, and the
        boundary."""
        try:
            cv = get_store().cached_grounded_field(act_id, field_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return _conditional(request, response, cv)

    @app.get("/v1/profiles/{act_id}/evidence-checklist", response_model=EvidenceChecklist)
    @app.get("/profiles/{act_id}/evidence-checklist", deprecated=True)
    def api_evidence_checklist(act_id: str, request: Request, response: Response):
        try:
            cv = get_store().cached_evidence_checklist(act_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return _conditional(request, response, cv)

    @app.post("/v1/profiles/{act_id}/compare-schema", response_model=DivergenceResult)
    @app.post("/profiles/{act_id}/compare-schema", deprecated=True)
    def api_compare_schema(act_id: str, request: SchemaCompareRequest) -> dict[str, Any]:
        try:
            return compare_schema_to_profile(act_id, request.fields)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/v1/profiles/{act_id}/lint-report")
    @app.post("/profiles/{act_id}/lint-report", deprecated=True)
    def api_lint_report(act_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Lint an incident-report payload against a profile.

        Accepts the report as a field_id -> value object (or wrapped as
        {"report": {...}}) and returns missing/unknown fields plus which present
        fields still warrant attention (high interpretive load, committee-grade
        evidence, non-public disclosure tier). This is a readiness check, not a
        compliance certification.
        """
        report = body.get("report", body) if isinstance(body, dict) else {}
        try:
            return lint_report(act_id, report)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))


    @app.post("/v1/profiles/{act_id}/prevalidate-report")
    def api_prevalidate_report(act_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Pre-validate an incident-report payload against a profile.

        This is a pre-verification readiness check. It does not verify report
        bytes, evidence files, timestamps, signatures, ledger anchors or issuer
        identity.
        """
        report = body.get("report", body) if isinstance(body, dict) else {}
        try:
            return prevalidate_report(act_id, report)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/v1/profile-bindings/check", response_model=BindingResult)
    @app.post("/profile-bindings/check", deprecated=True)
    @app.post("/verify-receipt", deprecated=True)
    def api_check_profile_binding(body: dict[str, Any]) -> dict[str, Any]:
        """Profile-binding check. Accepts a receipt, manifest, or profile
        descriptor and returns a three-state ``status``: bound,
        recognized_unbound, mismatch, unknown_profile, or invalid_input. Every
        result carries verification_grade: false, since this is a binding check,
        not receipt verification.

        Manifest hash, RFC 3161 timestamp, ledger anchor, signature and issuer
        identity are not checked here; those live in actproof-py. The canonical
        path is /v1/profile-bindings/check; the unversioned paths and
        /verify-receipt are deprecated aliases.
        """
        # Accept either the descriptor directly or the older {"receipt": {...}} shape.
        obj = body.get("receipt", body) if isinstance(body, dict) else body
        return check_profile_binding(obj)

    # --- 2.4.0: read-only views of the 2.x bank-control layer -----------------
    # These expose the PUBLIC, source-bound assurance facts (governance status of
    # the published profile, the SBOM, the release manifest) as read-only GETs.
    # The bank's OWN overlay and its impact report are deliberately NOT exposed
    # over HTTP: they contain the bank's internal review decisions and reviewer
    # identities, and stay file-local via the CLI. The API never receives bank
    # incident data or bank governance data. No route below performs any network
    # egress; every answer is computed from the local immutable store.

    @app.get("/v1/service-info")
    def api_service_info() -> dict[str, Any]:
        """Declare the local-only, no-egress posture verifiably."""
        return {
            "service": "actproof-events-api",
            "version": __version__,
            "deployment_posture": {
                "default_bind": "127.0.0.1 (loopback only)",
                "network_egress": "none — every response is computed from the local immutable store",
                "receives_bank_incident_data": False,
                "receives_bank_overlay_or_governance_decisions": False,
                "read_only": True,
                "stores_reports": False,
                "stores_evidence": False,
                "requires_database": False,
                "external_network_calls": False,
                "body_limit_bytes": 512 * 1024,
            },
            "bank_private_features_not_exposed_over_http": [
                "bank overlay (init/validate/status)",
                "overlay impact report",
            ],
            "reason": (
                "The overlay and its impact carry the bank's own internal review "
                "decisions and reviewer identities. They stay file-local via the "
                "CLI by design; the API exposes only public source-bound facts."
            ),
            "boundary": BOUNDARY, "boundary_id": BOUNDARY_ID,
        }

    @app.get("/v1/profiles/{act_id}/governance-status")
    def api_governance_status(act_id: str) -> dict[str, Any]:
        """Read-only governance status of the PUBLISHED profile (review tiers,
        held-at-draft fields, lifecycle state). Source-bound; no bank data."""
        from .profile_governance import build_governance_status
        if act_id not in get_store().act_ids():
            raise HTTPException(status_code=404, detail="unknown_profile")
        out = build_governance_status(act_id)
        out["boundary"] = BOUNDARY
        out["boundary_id"] = BOUNDARY_ID
        return out

    @app.get("/v1/release/sbom")
    def api_sbom() -> dict[str, Any]:
        """Read-only CycloneDX SBOM for the installed package."""
        from .release_assurance import build_sbom
        return build_sbom()

    @app.get("/v1/release/manifest")
    def api_release_manifest(act_id: str = "op:eu.dora.ict_incident_notification_initial.v1") -> dict[str, Any]:
        """Read-only release-assurance manifest binding artifacts to domain hashes."""
        from .release_assurance import build_release_assurance_manifest
        if act_id not in get_store().act_ids():
            raise HTTPException(status_code=404, detail="unknown_profile")
        return build_release_assurance_manifest(act_id)

    @app.get("/v1/profiles/{act_id}/lock")
    def api_profile_lock(act_id: str) -> dict[str, Any]:
        """Read-only profile lock (component hashes, self-sealing lock hash)."""
        from .bank_operability import build_profile_lock
        if act_id not in get_store().act_ids():
            raise HTTPException(status_code=404, detail="unknown_profile")
        return build_profile_lock(act_id)

    @app.get("/v1/profiles/{act_id}/source-atom-coverage")
    def api_source_atom_coverage(act_id: str) -> dict[str, Any]:
        """Read-only source-atom coverage for the published profile."""
        from .bank_operability import compute_source_atom_coverage
        if act_id not in get_store().act_ids():
            raise HTTPException(status_code=404, detail="unknown_profile")
        return compute_source_atom_coverage(act_id)

    @app.get("/v1/profiles/{act_id}/completeness")
    def api_completeness(act_id: str) -> dict[str, Any]:
        """Read-only profile completeness for the published profile."""
        from .bank_operability import get_profile_completeness
        if act_id not in get_store().act_ids():
            raise HTTPException(status_code=404, detail="unknown_profile")
        return get_profile_completeness(act_id)


def _is_loopback(host: str) -> bool:
    h = (host or "").strip().lower()
    if h in {"127.0.0.1", "::1", "localhost"}:
        return True
    return h.startswith("127.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the optional ActProof Events REST API (read-only, local by default, no egress)."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1, loopback only)")
    parser.add_argument("--port", default=8787, type=int)
    parser.add_argument(
        "--allow-non-loopback", action="store_true",
        help="Required to bind a non-loopback address. ActProof is local-first; "
             "exposing this service on a network is the operator's deliberate choice.",
    )
    args = parser.parse_args()
    if FastAPI is None:
        raise SystemExit('Install optional dependencies: pip install "actproof-events[api]"')

    if not _is_loopback(args.host) and not args.allow_non_loopback:
        raise SystemExit(
            f"refusing to bind non-loopback host {args.host!r} without --allow-non-loopback.\n"
            "ActProof Events is local-first and read-only: it serves source-bound "
            "profile facts from a local immutable store and performs no network egress.\n"
            "Binding to a network interface is a deliberate operator decision; "
            "if you mean it, pass --allow-non-loopback and place it behind your own "
            "gateway/auth. The default 127.0.0.1 keeps the blast radius local."
        )
    if not _is_loopback(args.host):
        print(
            f"WARNING: binding non-loopback host {args.host!r}. This read-only service "
            "has no built-in auth; put it behind your own gateway. No bank incident "
            "data or overlay/governance decisions are accepted by this API.",
        )

    import uvicorn
    uvicorn.run("actproof_events.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
