"""Tests for the MCP enforcement + audit wrapper (B7). Exercises secured_tool
directly (no SDK needed): allowed succeeds, missing scope raises a tool error,
success and failure are audited, audit logs identifiers not contents, stdio
disabled keeps working, and a non-disabled mode without identity fails closed
rather than downgrading. Runs under pytest and directly."""
from __future__ import annotations

import inspect
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # type: ignore  # noqa: E402

from actproof_events import mcp_server as m  # noqa: E402


@pytest.fixture
def cap():
    records: list[str] = []
    handler = logging.Handler()
    handler.emit = lambda r: records.append(r.getMessage())  # type: ignore
    m.audit_logger.addHandler(handler)
    m.audit_logger.setLevel(logging.INFO)
    try:
        yield records
    finally:
        m.audit_logger.removeHandler(handler)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("ACTPROOF_AUTH_MODE", "ACTPROOF_STATIC_TOKEN", "ACTPROOF_STATIC_TOKEN_SCOPES"):
        monkeypatch.delenv(k, raising=False)


def test_disabled_allows_and_audits_success(monkeypatch, cap):
    monkeypatch.setenv("ACTPROOF_AUTH_MODE", "disabled")

    @m.secured_tool("get_profile")
    def fake(act_id):
        return {"act_id": act_id}

    assert fake(act_id="op:eu.dora.x.v1") == {"act_id": "op:eu.dora.x.v1"}
    rec = json.loads(cap[-1])
    assert rec["outcome"] == "success" and rec["tool_name"] == "get_profile"
    assert rec["act_id"] == "op:eu.dora.x.v1" and rec["scopes"] == ["*"]
    assert rec["event"] == "mcp_tool_call" and "duration_ms" in rec


def test_missing_scope_raises_tool_error_and_audits(monkeypatch, cap):
    monkeypatch.setenv("ACTPROOF_AUTH_MODE", "trusted_headers")
    monkeypatch.setattr(m, "_get_request_headers", lambda: {
        "X-ActProof-Scopes": "actproof:profiles:read",
        "X-ActProof-Subject": "u@x", "X-ActProof-Client-Id": "c1",
    })

    @m.secured_tool("compare_schema_to_profile")
    def fake(act_id, fields):
        return {"ran": True}

    with pytest.raises(m.ToolError):
        fake(act_id="op:x", fields=["a", "b", "c"])
    rec = json.loads(cap[-1])
    assert rec["outcome"] == "failure" and rec["failure_type"] == "auth_denied"
    assert rec["required_scope"] == "actproof:schema:compare"
    assert rec["subject"] == "u@x" and rec["client_id"] == "c1"


def test_granted_scope_runs_and_logs_count_not_contents(monkeypatch, cap):
    monkeypatch.setenv("ACTPROOF_AUTH_MODE", "trusted_headers")
    monkeypatch.setattr(m, "_get_request_headers", lambda: {
        "X-ActProof-Scopes": "actproof:schema:compare", "X-ActProof-Subject": "u@x",
    })

    @m.secured_tool("compare_schema_to_profile")
    def fake(act_id, fields):
        return {"ran": True}

    assert fake(act_id="op:x", fields=["secret_field_1", "secret_field_2"])["ran"]
    line = cap[-1]
    rec = json.loads(line)
    assert rec["outcome"] == "success" and rec["scopes"] == ["actproof:schema:compare"]
    assert rec["schema_field_count"] == 2
    assert "fields" not in rec and "secret_field_1" not in line


def test_tool_body_failure_audited_and_reraised(monkeypatch, cap):
    monkeypatch.setenv("ACTPROOF_AUTH_MODE", "disabled")

    @m.secured_tool("get_field")
    def fake(act_id, field_id):
        raise ValueError("Unknown field 'nope'")

    with pytest.raises(ValueError):
        fake(act_id="op:x", field_id="nope")
    rec = json.loads(cap[-1])
    assert rec["outcome"] == "failure" and rec["failure_type"] == "ValueError"
    assert rec["field_id"] == "nope"


def test_stdio_disabled_still_works(monkeypatch, cap):
    monkeypatch.setenv("ACTPROOF_AUTH_MODE", "disabled")
    monkeypatch.setattr(m, "_get_request_headers", lambda: None)  # stdio: no headers

    @m.secured_tool("list_profiles")
    def fake():
        return {"ok": True}

    assert fake()["ok"]
    assert json.loads(cap[-1])["outcome"] == "success"


def test_http_mode_without_identity_fails_closed(monkeypatch, cap):
    monkeypatch.setenv("ACTPROOF_AUTH_MODE", "static_token")
    monkeypatch.setenv("ACTPROOF_STATIC_TOKEN", "secret")
    monkeypatch.setattr(m, "_get_request_headers", lambda: None)  # no request context

    @m.secured_tool("get_profile")
    def fake(act_id):
        return {"ran": True}

    with pytest.raises(m.ToolError):
        fake(act_id="op:x")
    rec = json.loads(cap[-1])
    assert rec["outcome"] == "failure" and rec["failure_type"] == "auth_unavailable"


def test_signature_preserved_for_schema():
    @m.secured_tool("get_field")
    def fake(act_id, field_id):
        return 1

    assert list(inspect.signature(fake).parameters) == ["act_id", "field_id"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
