"""Optional ActProof MCP server.

The agent face of the shared services. It exposes source-bound regulatory
profiles three ways an MCP host understands:

  * tools   - deterministic, read-only calls (the agent grounds answers here);
  * resources - profiles as first-class context an agent can list and attach;
  * a prompt - a guided, safe-by-construction notification workflow.

Every result surfaces a field's interpretive_status (direct / derived /
interpretive) and the boundary, so a model can never present a judgement call
as settled law. The server returns catalogue facts only. It does not issue
legal advice, certification, supervisory approval, or a compliance opinion.
That deterministic, source-bound, logged, auditable shape is exactly what a
compliance MCP deployment should be.

Run:

    pip install "actproof-events[mcp]"
    actproof-mcp
"""
from __future__ import annotations

import functools
import inspect
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from . import auth as _auth
from . import services as svc
from .services import BOUNDARY, BOUNDARY_ID
from .source_binding import compute_field_source_coverage, explain_field_source as _explain_field_source

DEFAULT_ACT = "op:eu.dora.ict_incident_notification_initial.v1"


def _raise_not_found(exc: KeyError) -> None:
    """Re-raise an unknown profile/field as a clean error. FastMCP surfaces a
    raised exception as a tool error (isError true), so the agent treats an
    unknown identifier as a failed call rather than as data it can use."""
    raise ValueError(exc.args[0] if exc.args else "not found") from exc


# --- authorization + audit, applied once via secured_tool ------------------
# A dedicated audit logger. Lines are JSON objects (JSONL). No handler is
# attached here, so a deployment opts in to where audit goes; nothing is emitted
# by default in dev.
audit_logger = logging.getLogger("actproof.audit")

try:  # the SDK's tool error type if present; a local fallback otherwise
    from mcp.server.fastmcp.exceptions import ToolError  # type: ignore
except Exception:  # pragma: no cover
    class ToolError(Exception):
        """Raised to signal an MCP tool error (auth denial)."""


def _get_request_headers() -> dict[str, str] | None:
    """Best-effort inbound headers from the FastMCP request context. Returns None
    when unavailable (for example the stdio transport, which has no headers).
    Overridden in tests."""
    mcp_obj = globals().get("mcp")
    if mcp_obj is None:
        return None
    try:
        ctx = mcp_obj.get_context()
        req = getattr(getattr(ctx, "request_context", None), "request", None)
        headers = getattr(req, "headers", None)
        return {k: v for k, v in headers.items()} if headers is not None else None
    except Exception:
        return None


def resolve_auth_context() -> "_auth.AuthContext":
    """Resolve identity for this call. In disabled mode (the dev default) a
    full-scope context is returned. In any mode that requires identity, headers
    must be present: if they are not, authorization FAILS rather than silently
    downgrading to disabled, so a production HTTP deployment can never be bypassed
    by a missing request context."""
    mode = (os.environ.get(_auth.ENV_MODE) or _auth.AuthMode.DISABLED.value).strip().lower()
    if mode == _auth.AuthMode.DISABLED.value:
        return _auth.resolve_auth(env=os.environ)
    headers = _get_request_headers()
    if headers is None:
        raise _auth.AuthError(
            f"auth mode {mode!r} requires request identity but none was available; "
            "refusing to fall back to disabled mode"
        )
    return _auth.resolve_auth(headers=headers, env=os.environ)


def _audit_base(tool_name: str, params: dict[str, Any], ctx: "_auth.AuthContext") -> dict[str, Any]:
    base: dict[str, Any] = {
        "tool_name": tool_name,
        "subject": getattr(ctx, "subject", None),
        "client_id": getattr(ctx, "client_id", None),
        "scopes": ["*"] if getattr(ctx, "all_scopes", False) else sorted(ctx.scopes),
    }
    for key in ("act_id", "field_id", "assessment_id"):
        if params.get(key) is not None:
            base[key] = params[key]
    # For compare, log the field COUNT, never the schema contents.
    if tool_name == "compare_schema_to_profile":
        fields = params.get("fields")
        base["schema_field_count"] = len(fields) if isinstance(fields, list) else None
    return base


def _emit_audit(outcome: str, base: dict[str, Any], *, duration_ms: float | None = None,
                failure_type: str | None = None, required_scope: str | None = None,
                detail: str | None = None) -> dict[str, Any]:
    payload = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": "mcp_tool_call",
        "outcome": outcome,
        **base,
    }
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    if failure_type:
        payload["failure_type"] = failure_type
    if required_scope:
        payload["required_scope"] = required_scope
    if detail:
        payload["detail"] = detail
    audit_logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return payload


def secured_tool(tool_name: str):
    """Wrap a tool with: resolve identity, enforce scope, run, audit. One place,
    so enforcement and the audit line never drift apart. functools.wraps keeps
    the original signature so FastMCP still builds the correct tool schema."""
    def decorator(fn):
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                bound = sig.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                params = dict(bound.arguments)
            except TypeError:
                params = dict(kwargs)
            try:
                ctx = resolve_auth_context()
            except _auth.AuthError as exc:
                _emit_audit("failure", {"tool_name": tool_name},
                            failure_type="auth_unavailable", detail=str(exc))
                raise ToolError(str(exc)) from exc
            base = _audit_base(tool_name, params, ctx)
            try:
                _auth.check_tool_access(tool_name, ctx)
            except _auth.AuthError as exc:
                _emit_audit("failure", base, failure_type="auth_denied",
                            required_scope=_auth.scope_for_tool(tool_name), detail=str(exc))
                raise ToolError(str(exc)) from exc
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                _emit_audit("failure", base, failure_type=type(exc).__name__, detail=str(exc),
                            duration_ms=round((time.perf_counter() - start) * 1000, 1))
                raise
            _emit_audit("success", base, duration_ms=round((time.perf_counter() - start) * 1000, 1))
            return result

        return wrapper
    return decorator

INSTRUCTIONS = (
    "ActProof exposes source-bound profiles of regulated acts as read-only, "
    "deterministic tools and resources. Ground answers about what a regulation "
    "requires by calling these tools rather than recalling the law. Always "
    "surface a field's interpretive_status (direct, derived, or interpretive) "
    "and the boundary to the user. " + BOUNDARY
)

try:  # the mcp SDK uses FastMCP as the common server path
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover
    FastMCP = None  # type: ignore

if FastMCP is not None:
    mcp = FastMCP("actproof-events", instructions=INSTRUCTIONS)

    # ----- tools: deterministic catalogue calls -----------------------
    @mcp.tool()
    @secured_tool("list_profiles")
    def list_profiles() -> dict[str, Any]:
        """List source-bound regulatory profiles, with per-profile interpretive-field counts."""
        return {"boundary": BOUNDARY, "boundary_id": BOUNDARY_ID, "profiles": svc.list_profiles()}

    @mcp.tool()
    @secured_tool("search_profiles")
    def search_profiles(query: str) -> dict[str, Any]:
        """Find profiles by act id, display name, or instrument (e.g. 'DORA', 'NIS2', 'incident')."""
        q = query.lower().strip()
        hits = [p for p in svc.list_profiles()
                if q in p["act_id"].lower()
                or q in (p["display_name"] or "").lower()
                or q in (p.get("claim_type") or "").lower()]
        return {"boundary": BOUNDARY, "boundary_id": BOUNDARY_ID, "query": query, "profiles": hits}

    @mcp.tool()
    @secured_tool("get_profile")
    def get_profile(act_id: str) -> dict[str, Any]:
        """Return one profile with its interpretive_summary, real non_claims, and catalogue_entry_hash."""
        try:
            return svc.get_profile(act_id)
        except KeyError as exc:
            _raise_not_found(exc)

    @mcp.tool()
    @secured_tool("list_fields")
    def list_fields(act_id: str, required_only: bool = False) -> dict[str, Any]:
        """List a profile's fields with interpretive_status (direct/derived/interpretive) and rationale."""
        try:
            fields = svc.list_fields(act_id, required_only=required_only)
        except KeyError as exc:
            _raise_not_found(exc)
        return {"boundary": BOUNDARY, "boundary_id": BOUNDARY_ID, "act_id": act_id, "fields": fields}

    @mcp.tool()
    @secured_tool("get_field")
    def get_field(act_id: str, field_id: str) -> dict[str, Any]:
        """Ground one field: interpretive_status, rationale, disclosure, pinned sources, non_claims, boundary."""
        try:
            return svc.get_field(act_id, field_id)
        except KeyError as exc:
            _raise_not_found(exc)

    @mcp.tool()
    @secured_tool("get_source_basis")
    def get_source_basis(act_id: str, field_id: str) -> dict[str, Any]:
        """Return the hash-pinned source instruments behind a profile/field."""
        try:
            profile = svc.get_profile(act_id)
        except KeyError as exc:
            _raise_not_found(exc)
        known = set(profile.get("required_claim_fields") or []) | set(profile.get("optional_claim_fields") or [])
        if field_id not in known:
            raise ValueError(f"Unknown field {field_id!r} for profile {act_id}")
        return {"act_id": act_id, "field_id": field_id,
                **svc.source_basis_view(profile, field_id), "boundary": BOUNDARY, "boundary_id": BOUNDARY_ID}

    @mcp.tool()
    @secured_tool("generate_evidence_checklist")
    def generate_evidence_checklist(act_id: str) -> dict[str, Any]:
        """Evidence checklist for a profile: required evidence labels and required fields."""
        try:
            return svc.generate_evidence_checklist(act_id)
        except KeyError as exc:
            _raise_not_found(exc)


    @mcp.tool()
    @secured_tool("explain_field_source")
    def explain_field_source(act_id: str, field_id: str) -> dict[str, Any]:
        """Explain one profile field's source binding.

        Returns source atoms, binding_granularity, release_scope, review status,
        field_binding_status and explicit boundary metadata. This grounds an
        agent's answer in the inspectable ActProof source-binding layer; it does
        not determine legal compliance.
        """
        try:
            return _explain_field_source(act_id, field_id)
        except KeyError as exc:
            _raise_not_found(exc)

    @mcp.tool()
    @secured_tool("source_coverage")
    def source_coverage(act_id: str) -> dict[str, Any]:
        """Return precision-tiered source-binding coverage for one profile.

        The headline 1.8.0 gate is required template-field coverage, not a
        blanket claim that all optional contextual derivations are equally
        precise.
        """
        try:
            coverage = compute_field_source_coverage(act_id)
        except KeyError as exc:
            _raise_not_found(exc)
        return {"act_id": act_id, "coverage": coverage, "boundary": BOUNDARY, "boundary_id": BOUNDARY_ID}

    @mcp.tool()
    @secured_tool("lint_report")
    def lint_report(act_id: str, report: dict[str, Any]) -> dict[str, Any]:
        """Lint a DORA incident-report payload before verification.

        Reports missing required fields, unknown fields, high-interpretive-load
        fields and evidence-readiness signals. It does not verify bytes,
        signatures, timestamps, anchors or issuer identity.
        """
        try:
            return svc.lint_report(act_id, report)
        except KeyError as exc:
            _raise_not_found(exc)

    @mcp.tool()
    @secured_tool("prevalidate_report")
    def prevalidate_report(act_id: str, report: dict[str, Any]) -> dict[str, Any]:
        """Pre-validate a report payload and return ready_for_preverification.

        This is the 1.8.0 pre-validation primitive. It remains outside streaming
        session management and outside cryptographic receipt verification.
        """
        try:
            return svc.prevalidate_report(act_id, report)
        except KeyError as exc:
            _raise_not_found(exc)

    @mcp.tool()
    @secured_tool("compare_schema_to_profile")
    def compare_schema_to_profile(act_id: str, fields: list[str]) -> dict[str, Any]:
        """Compare a vendor/internal field list against a profile. Returns missing_interpretive_required_fields plus a divergence_summary with severity."""
        if not isinstance(fields, list) or not all(isinstance(f, str) for f in fields):
            raise ValueError("invalid schema input: 'fields' must be a list of field-id strings")
        try:
            return svc.compare_schema_to_profile(act_id, fields)
        except KeyError as exc:
            _raise_not_found(exc)

    @mcp.tool()
    @secured_tool("check_profile_binding")
    def check_profile_binding(receipt: dict[str, Any]) -> dict[str, Any]:
        """Check whether a supplied receipt, manifest, or profile descriptor binds
        to a catalogue entry held here. Returns a three-state status: bound,
        recognized_unbound, mismatch, unknown_profile, or invalid_input.

        This is NOT full receipt verification. Manifest hash, RFC 3161 timestamp,
        ledger anchor, signature and issuer identity are not checked here; those
        live in actproof-py. Recognising an act is not the same as binding to its
        bytes, so this never reports a match without a supplied entry hash.
        """
        return svc.check_profile_binding(receipt)

    # ----- resources: profiles as attachable context ------------------
    @mcp.resource("actproof://profiles")
    def resource_profiles() -> str:
        """The profile catalogue as JSON."""
        return json.dumps({"boundary": BOUNDARY, "boundary_id": BOUNDARY_ID, "profiles": svc.list_profiles()},
                          ensure_ascii=False, indent=2)

    @mcp.resource("actproof://profile/{act_id}")
    def resource_profile(act_id: str) -> str:
        """One full source-bound profile as JSON, attachable as model context."""
        try:
            return json.dumps(svc.get_profile(act_id), ensure_ascii=False, indent=2)
        except KeyError as exc:
            _raise_not_found(exc)

    # ----- prompt: a guided, safe-by-construction workflow ------------
    @mcp.prompt()
    def prepare_notification(act_id: str = DEFAULT_ACT) -> str:
        """Guide an assistant to prepare a regulated notification, grounded and
        honest about where judgement enters."""
        try:
            profile = svc.get_profile(act_id)
            fields = svc.list_fields(act_id, required_only=True)
        except KeyError as exc:
            _raise_not_found(exc)
        cite = profile.get("regulatory_citation") or {}
        art = ("Art. " + cite["article"]) if cite.get("article") else ""
        lines = [
            f"You are helping prepare: {profile.get('display_name')} "
            f"({cite.get('instrument', '')} {art}).".rstrip(),
            "Ground every statement by calling the ActProof tools. Do not rely on your own memory of the law.",
            "",
            "Required fields:",
        ]
        for f in fields:
            tag = "  [INTERPRETIVE: a judgement call]" if f["interpretive_status"] == "interpretive" else ""
            why = f"  why: {f['rationale']}" if f.get("rationale") else ""
            lines.append(f"- {f['field_id']} ({f['type']}, {f['disclosure_tier']}){tag}{why}")
        lines.append("")
        if profile.get("required_evidence_labels"):
            lines.append("Attach this evidence: " + ", ".join(profile["required_evidence_labels"]) + ".")
        lines.append("For every field marked INTERPRETIVE, tell the user it is a judgement call and show the rationale.")
        lines.append("Do not assert that the entity is compliant. This profile does not prove:")
        for nc in profile.get("non_claims", []):
            lines.append(f"  - {str(nc).replace('_', ' ')}")
        lines += ["", BOUNDARY]
        return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the optional ActProof MCP server.")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio",
                        help="stdio for local hosts (no request headers); streamable-http "
                             "to serve over HTTP where trusted-header auth applies.")
    parser.add_argument("--host", default="127.0.0.1", help="host for streamable-http")
    parser.add_argument("--port", default=8000, type=int, help="port for streamable-http")
    args = parser.parse_args()
    if FastMCP is None:
        raise SystemExit('Install optional dependencies: pip install "actproof-events[mcp]"')
    if args.transport == "streamable-http":
        # Best-effort host/port; FastMCP exposes these via settings.
        try:
            mcp.settings.host = args.host
            mcp.settings.port = args.port
        except Exception:
            pass
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
