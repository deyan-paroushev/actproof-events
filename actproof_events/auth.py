"""Authorization seam for the ActProof MCP server.

This module is the security vocabulary, frozen now and enforced later. It
defines the scope set, the tool-to-scope map, an immutable auth context, a
resolver for the supported modes, and ``require_scope`` / ``check_tool_access``
checks. It deliberately does NOT wire enforcement into any tool. B7 calls
``check_tool_access`` at the MCP touch-point and adds the audit log there.

Modes (ACTPROOF_AUTH_MODE):

  * disabled        no auth; every scope is granted. The default, so behaviour
                    is unchanged until a deployment opts in.
  * trusted_headers identity is read from X-ActProof-Subject / -Scopes /
                    -Client-Id. SAFE ONLY behind a gateway that strips inbound
                    client-supplied identity headers, otherwise a caller can
                    forge scopes.
  * static_token    a shared bearer token (or X-ActProof-Token) is compared in
                    constant time against ACTPROOF_STATIC_TOKEN; on match the
                    scopes in ACTPROOF_STATIC_TOKEN_SCOPES are granted, else the
                    context has no scopes and fails closed.
  * jwt_later       reserved. Full JWT/JWKS validation is not implemented yet;
                    resolving in this mode raises so it can never be mistaken
                    for working enforcement.

This module uses only the standard library, so it imports with or without the
optional API/MCP dependencies installed.
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

# -- scopes -----------------------------------------------------------------
SCOPE_PROFILES_READ = "actproof:profiles:read"
SCOPE_FIELDS_READ = "actproof:fields:read"
SCOPE_BINDINGS_CHECK = "actproof:bindings:check"
SCOPE_SCHEMA_COMPARE = "actproof:schema:compare"
# Reserved for the later delegated full receipt verification. Not granted by the
# default static-token scope set; full verification lives in actproof-py.
SCOPE_RECEIPTS_VERIFY = "actproof:receipts:verify"
SCOPE_REPORTS_LINT = "actproof:reports:lint"

ALL_SCOPES = frozenset({
    SCOPE_PROFILES_READ,
    SCOPE_FIELDS_READ,
    SCOPE_BINDINGS_CHECK,
    SCOPE_SCHEMA_COMPARE,
    SCOPE_RECEIPTS_VERIFY,
    SCOPE_REPORTS_LINT,
})

# Tool name -> required scope. Read tools read; the binding check is its own
# scope; schema comparison is its own scope. A tool absent from this map needs
# no scope.
TOOL_SCOPES: dict[str, str] = {
    "list_profiles": SCOPE_PROFILES_READ,
    "search_profiles": SCOPE_PROFILES_READ,
    "get_profile": SCOPE_PROFILES_READ,
    "list_fields": SCOPE_FIELDS_READ,
    "get_field": SCOPE_FIELDS_READ,
    "get_source_basis": SCOPE_FIELDS_READ,
    "generate_evidence_checklist": SCOPE_FIELDS_READ,
    "compare_schema_to_profile": SCOPE_SCHEMA_COMPARE,
    "check_profile_binding": SCOPE_BINDINGS_CHECK,
    "explain_field_source": SCOPE_FIELDS_READ,
    "source_coverage": SCOPE_PROFILES_READ,
    "lint_report": SCOPE_REPORTS_LINT,
    "prevalidate_report": SCOPE_REPORTS_LINT,
}

# The scopes a valid static token grants by default: everything except the
# reserved full-verification scope.
_DEFAULT_TOKEN_SCOPES = frozenset({
    SCOPE_PROFILES_READ, SCOPE_FIELDS_READ, SCOPE_BINDINGS_CHECK, SCOPE_SCHEMA_COMPARE,
    SCOPE_REPORTS_LINT,
})

# -- header and env names ---------------------------------------------------
HEADER_SUBJECT = "X-ActProof-Subject"
HEADER_SCOPES = "X-ActProof-Scopes"
HEADER_CLIENT_ID = "X-ActProof-Client-Id"
HEADER_TOKEN = "X-ActProof-Token"

ENV_MODE = "ACTPROOF_AUTH_MODE"
ENV_STATIC_TOKEN = "ACTPROOF_STATIC_TOKEN"
ENV_STATIC_TOKEN_SCOPES = "ACTPROOF_STATIC_TOKEN_SCOPES"


class AuthMode(str, Enum):
    DISABLED = "disabled"
    TRUSTED_HEADERS = "trusted_headers"
    STATIC_TOKEN = "static_token"
    JWT_LATER = "jwt_later"


class AuthError(Exception):
    """Raised when a required scope is absent. B7 converts this to an MCP tool
    error so an agent sees a denied call, not data."""


@dataclass(frozen=True)
class AuthContext:
    """An immutable, resolved identity. ``all_scopes`` is the disabled-mode
    shortcut so the default deployment grants everything."""
    mode: str
    subject: str | None = None
    client_id: str | None = None
    scopes: frozenset[str] = field(default_factory=frozenset)
    all_scopes: bool = False

    def has_scope(self, scope: str) -> bool:
        return self.all_scopes or scope in self.scopes


def _parse_scopes(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    parts = raw.replace(",", " ").split()
    return frozenset(p.strip() for p in parts if p.strip())


def _bearer(headers: Mapping[str, str]) -> str | None:
    auth = headers.get("authorization")
    if auth and auth.strip().lower().startswith("bearer "):
        return auth.strip()[7:].strip()
    return None


def resolve_auth(headers: Mapping[str, str] | None = None,
                 env: Mapping[str, str] | None = None) -> AuthContext:
    """Resolve an AuthContext from request headers and the environment mode."""
    env = os.environ if env is None else env
    h = {str(k).lower(): v for k, v in (headers or {}).items()}
    mode = (env.get(ENV_MODE) or AuthMode.DISABLED.value).strip().lower()

    if mode == AuthMode.DISABLED.value:
        return AuthContext(mode=mode, all_scopes=True)

    if mode == AuthMode.TRUSTED_HEADERS.value:
        return AuthContext(
            mode=mode,
            subject=h.get(HEADER_SUBJECT.lower()),
            client_id=h.get(HEADER_CLIENT_ID.lower()),
            scopes=_parse_scopes(h.get(HEADER_SCOPES.lower())),
        )

    if mode == AuthMode.STATIC_TOKEN.value:
        supplied = _bearer(h) or h.get(HEADER_TOKEN.lower())
        configured = env.get(ENV_STATIC_TOKEN)
        if configured and supplied and hmac.compare_digest(str(supplied), str(configured)):
            granted = _parse_scopes(env.get(ENV_STATIC_TOKEN_SCOPES)) or _DEFAULT_TOKEN_SCOPES
            return AuthContext(
                mode=mode,
                subject=h.get(HEADER_SUBJECT.lower()),
                client_id=h.get(HEADER_CLIENT_ID.lower()),
                scopes=granted,
            )
        # Missing or wrong token: a context with no scopes, fails closed.
        return AuthContext(mode=mode)

    if mode == AuthMode.JWT_LATER.value:
        raise NotImplementedError(
            "ACTPROOF_AUTH_MODE=jwt_later is reserved; full JWT/JWKS validation is "
            "not implemented yet. Use disabled, trusted_headers, or static_token."
        )

    raise ValueError(f"unknown {ENV_MODE}: {mode!r}")


def scope_for_tool(tool_name: str) -> str | None:
    """The scope a tool requires, or None if it needs none."""
    return TOOL_SCOPES.get(tool_name)


def require_scope(ctx: AuthContext, scope: str) -> None:
    """Raise AuthError unless the context holds the scope."""
    if not ctx.has_scope(scope):
        raise AuthError(f"missing required scope: {scope}")


def check_tool_access(tool_name: str, ctx: AuthContext) -> None:
    """The seam B7 calls before executing a tool. Looks up the tool's scope and
    enforces it. A tool with no mapped scope is allowed. This proves the seam is
    callable from a tool wrapper without wiring any specific tool yet."""
    scope = scope_for_tool(tool_name)
    if scope is not None:
        require_scope(ctx, scope)
