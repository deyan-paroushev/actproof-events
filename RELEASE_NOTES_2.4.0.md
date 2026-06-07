# actproof-events 2.4.0 — Local API / internal service mode

Extends the existing optional read-only REST API to surface the 2.x bank-control
layer, and hardens the local-only, no-egress posture. This is a "smart brakes"
release: it adds reach to the PUBLIC source-bound layer and deliberately refuses
to add reach to the bank-PRIVATE layer.

## What it does (all read-only GET, localhost-default, no egress)

- `GET /v1/service-info` — declares the deployment posture verifiably: loopback
  default, no egress, receives no bank incident data and no bank overlay or
  governance decisions, read-only, stateless (no DB, no report/evidence store),
  body-size limited.
- `GET /v1/profiles/{act_id}/governance-status` — published-profile governance.
- `GET /v1/profiles/{act_id}/lock` — profile lock (component hashes).
- `GET /v1/profiles/{act_id}/source-atom-coverage`
- `GET /v1/profiles/{act_id}/completeness`
- `GET /v1/release/sbom` — CycloneDX SBOM.
- `GET /v1/release/manifest` — release-assurance manifest.

## The boundary it holds — by design, not omission

The bank's OWN overlay and its impact report are NOT exposed over HTTP. They
carry the bank's internal review decisions and reviewer identities. Under DORA
Article 28 the bank is responsible for ensuring its providers do not create
uncontrolled data flows; an HTTP listener that accepts overlay JSON would invite
the bank to transmit sensitive internal governance data to an unauthenticated
endpoint. A body-size limit does not make that category of data safe to put on
the wire. The overlay and impact stay file-local via the CLI. A regression test
asserts that no overlay/impact route exists under any plausible path.

## Local-only hardening + resource guard

`actproof-api` defaults to `127.0.0.1` and refuses to bind a non-loopback host
unless `--allow-non-loopback` is passed, printing why. An app-wide middleware
rejects oversized request bodies (HTTP 413, 512 KiB cap) per OWASP API4
resource-consumption guidance. The service is stateless: no database, no report
or evidence storage, no external network calls.

## Honesty boundary

Read-only developer/internal face of the same source-bound facts. Not legal
advice, does not certify compliance, accepts no bank incident or governance
data. The API extra is optional: `pip install "actproof-events[api]"`.

Tests: 162 passing (11 for the local API; endpoint tests skip cleanly when
fastapi/httpx are absent).
