"""Tests for 2.4.0 local API / internal service mode.

The API is an optional extra; tests that need the running app are skipped when
fastapi/httpx are not installed. The local-only posture guard is tested without
any optional dependency.
"""

import sys
import pytest

from actproof_events import __version__

ACT = "op:eu.dora.ict_incident_notification_initial.v1"


# --- posture guard: no optional dependency needed ----------------------------

def test_is_loopback_classification():
    from actproof_events.api import _is_loopback
    assert _is_loopback("127.0.0.1")
    assert _is_loopback("localhost")
    assert _is_loopback("::1")
    assert _is_loopback("127.0.5.9")
    assert not _is_loopback("0.0.0.0")
    assert not _is_loopback("10.0.0.5")
    assert not _is_loopback("192.168.1.10")


def test_main_refuses_non_loopback_without_flag(monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    from actproof_events import api
    monkeypatch.setattr(sys, "argv", ["actproof-api", "--host", "0.0.0.0"])
    with pytest.raises(SystemExit) as exc:
        api.main()
    assert "refusing to bind" in str(exc.value)


# --- endpoint behaviour: needs fastapi + httpx -------------------------------

def _client():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from actproof_events.api import app
    return TestClient(app)


def test_service_info_declares_no_egress_and_no_bank_data():
    c = _client()
    j = c.get("/v1/service-info").json()
    dp = j["deployment_posture"]
    assert dp["receives_bank_incident_data"] is False
    assert dp["receives_bank_overlay_or_governance_decisions"] is False
    assert dp["read_only"] is True
    assert "none" in dp["network_egress"].lower()
    # the bank-private features are explicitly declared as NOT exposed
    assert j["bank_private_features_not_exposed_over_http"]


def test_governance_status_endpoint_is_readonly_and_bounded():
    c = _client()
    r = c.get(f"/v1/profiles/{ACT}/governance-status")
    assert r.status_code == 200
    j = r.json()
    assert "lifecycle_state" in j
    assert j.get("boundary")  # boundary carried on the grounded answer


def test_sbom_endpoint_is_cyclonedx():
    c = _client()
    j = c.get("/v1/release/sbom").json()
    assert j["bomFormat"] == "CycloneDX"
    assert j["metadata"]["component"]["version"] == __version__


def test_release_manifest_endpoint_binds_profile_hash():
    c = _client()
    j = c.get("/v1/release/manifest").json()
    assert j["profile"]["profile_semantic_hash"].startswith("sha256:")


def test_unknown_profile_is_404_not_500():
    c = _client()
    assert c.get("/v1/profiles/op:nope.v1/governance-status").status_code == 404


def test_no_overlay_or_impact_route_exists():
    # the bank-private overlay/impact must NOT be reachable over HTTP, under ANY
    # of the route names a service might plausibly use. The overlay carries the
    # bank's internal review decisions and reviewer identities; under DORA Art.28
    # the bank must not be invited to transmit that to a network listener.
    c = _client()
    forbidden = (
        f"/v1/profiles/{ACT}/overlay", f"/v1/profiles/{ACT}/overlay-impact",
        "/v1/overlay", "/v1/overlay-impact",
        "/v1/overlays/init", "/v1/overlays/init-from-schema", "/v1/overlays/validate",
        "/v1/overlays/status", "/v1/overlays/report", "/v1/overlays/impact",
    )
    for path in forbidden:
        assert c.get(path).status_code == 404, path
        assert c.post(path, json={}).status_code in {404, 405}, path


def test_read_only_2x_views_are_present():
    c = _client()
    for p in ("lock", "source-atom-coverage", "completeness"):
        assert c.get(f"/v1/profiles/{ACT}/{p}").status_code == 200, p


def test_oversize_body_is_rejected():
    c = _client()
    r = c.post(f"/v1/profiles/{ACT}/compare-schema", json={"fields": ["x"]},
               headers={"content-length": str(600 * 1024)})
    assert r.status_code == 413


def test_service_info_declares_stateless_posture():
    c = _client()
    dp = c.get("/v1/service-info").json()["deployment_posture"]
    assert dp["stores_reports"] is False
    assert dp["requires_database"] is False
    assert dp["external_network_calls"] is False
    assert dp["body_limit_bytes"] > 0
