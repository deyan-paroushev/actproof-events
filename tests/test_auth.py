"""Tests for the auth seam (B6). Covers scope pass/fail across every mode and a
small integration placeholder proving the seam is callable from a tool wrapper.
Runs under pytest and directly: ``python tests/test_auth.py``."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # type: ignore  # noqa: E402

from actproof_events import auth  # noqa: E402
from actproof_events.auth import (  # noqa: E402
    ALL_SCOPES,
    AuthError,
    SCOPE_BINDINGS_CHECK,
    SCOPE_FIELDS_READ,
    SCOPE_PROFILES_READ,
    SCOPE_RECEIPTS_VERIFY,
    SCOPE_SCHEMA_COMPARE,
    TOOL_SCOPES,
    check_tool_access,
    require_scope,
    resolve_auth,
    scope_for_tool,
)

# The MCP tools the map must cover.
MCP_TOOLS = {
    "list_profiles", "search_profiles", "get_profile", "list_fields", "get_field",
    "get_source_basis", "generate_evidence_checklist", "compare_schema_to_profile",
    "check_profile_binding", "explain_field_source", "source_coverage",
    "lint_report", "prevalidate_report",
}


def test_disabled_grants_all_scopes():
    ctx = resolve_auth(env={"ACTPROOF_AUTH_MODE": "disabled"})
    assert ctx.all_scopes is True
    for scope in ALL_SCOPES:
        require_scope(ctx, scope)  # no raise
    for tool in MCP_TOOLS:
        check_tool_access(tool, ctx)  # no raise


def test_default_mode_is_disabled():
    ctx = resolve_auth(env={})
    assert ctx.mode == "disabled" and ctx.all_scopes is True


def test_trusted_headers_grants_only_listed_scopes():
    ctx = resolve_auth(
        headers={
            "X-ActProof-Subject": "svc-a",
            "X-ActProof-Client-Id": "client-1",
            "X-ActProof-Scopes": "actproof:profiles:read actproof:fields:read",
        },
        env={"ACTPROOF_AUTH_MODE": "trusted_headers"},
    )
    assert ctx.subject == "svc-a" and ctx.client_id == "client-1"
    require_scope(ctx, SCOPE_PROFILES_READ)
    require_scope(ctx, SCOPE_FIELDS_READ)
    with pytest.raises(AuthError):
        require_scope(ctx, SCOPE_BINDINGS_CHECK)
    # comma separated also parses
    ctx2 = resolve_auth(headers={"X-ActProof-Scopes": "actproof:schema:compare,actproof:bindings:check"},
                        env={"ACTPROOF_AUTH_MODE": "trusted_headers"})
    require_scope(ctx2, SCOPE_SCHEMA_COMPARE)
    require_scope(ctx2, SCOPE_BINDINGS_CHECK)


def test_trusted_headers_without_scopes_denies():
    ctx = resolve_auth(headers={}, env={"ACTPROOF_AUTH_MODE": "trusted_headers"})
    for scope in ALL_SCOPES:
        with pytest.raises(AuthError):
            require_scope(ctx, scope)


def test_static_token_match_grants_default_scopes_but_not_receipts_verify():
    env = {"ACTPROOF_AUTH_MODE": "static_token", "ACTPROOF_STATIC_TOKEN": "s3cret"}
    ctx = resolve_auth(headers={"Authorization": "Bearer s3cret"}, env=env)
    require_scope(ctx, SCOPE_PROFILES_READ)
    require_scope(ctx, SCOPE_BINDINGS_CHECK)
    # receipts:verify is reserved and not granted by a default token
    with pytest.raises(AuthError):
        require_scope(ctx, SCOPE_RECEIPTS_VERIFY)


def test_static_token_via_x_token_header_and_custom_scopes():
    env = {
        "ACTPROOF_AUTH_MODE": "static_token",
        "ACTPROOF_STATIC_TOKEN": "abc",
        "ACTPROOF_STATIC_TOKEN_SCOPES": "actproof:profiles:read",
    }
    ctx = resolve_auth(headers={"X-ActProof-Token": "abc"}, env=env)
    require_scope(ctx, SCOPE_PROFILES_READ)
    with pytest.raises(AuthError):
        require_scope(ctx, SCOPE_FIELDS_READ)


def test_static_token_wrong_or_absent_fails_closed():
    env = {"ACTPROOF_AUTH_MODE": "static_token", "ACTPROOF_STATIC_TOKEN": "right"}
    wrong = resolve_auth(headers={"Authorization": "Bearer wrong"}, env=env)
    absent = resolve_auth(headers={}, env=env)
    for ctx in (wrong, absent):
        assert ctx.scopes == frozenset()
        with pytest.raises(AuthError):
            require_scope(ctx, SCOPE_PROFILES_READ)


def test_jwt_later_is_reserved_and_raises():
    with pytest.raises(NotImplementedError):
        resolve_auth(env={"ACTPROOF_AUTH_MODE": "jwt_later"})


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        resolve_auth(env={"ACTPROOF_AUTH_MODE": "nonsense"})


def test_tool_scope_map_covers_every_mcp_tool():
    assert set(TOOL_SCOPES) == MCP_TOOLS
    assert scope_for_tool("get_profile") == SCOPE_PROFILES_READ
    assert scope_for_tool("check_profile_binding") == SCOPE_BINDINGS_CHECK


def test_receipts_verify_scope_reserved():
    # In the scope set, but mapped to no tool yet.
    assert SCOPE_RECEIPTS_VERIFY in ALL_SCOPES
    assert SCOPE_RECEIPTS_VERIFY not in set(TOOL_SCOPES.values())


def test_integration_placeholder_seam_callable_from_a_wrapper():
    """Prove check_tool_access is callable from a tool-wrapper shape, without
    wiring any real tool. B7 will use exactly this shape."""
    calls = {"ran": 0}

    def fake_tool_wrapper(tool_name, ctx, fn):
        check_tool_access(tool_name, ctx)   # the seam
        calls["ran"] += 1
        return fn()

    allowed = resolve_auth(env={"ACTPROOF_AUTH_MODE": "disabled"})
    assert fake_tool_wrapper("get_profile", allowed, lambda: "ok") == "ok"
    assert calls["ran"] == 1

    denied = resolve_auth(headers={"X-ActProof-Scopes": "actproof:profiles:read"},
                          env={"ACTPROOF_AUTH_MODE": "trusted_headers"})
    with pytest.raises(AuthError):
        fake_tool_wrapper("check_profile_binding", denied, lambda: "should not run")
    assert calls["ran"] == 1  # the denied call never reached fn


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
