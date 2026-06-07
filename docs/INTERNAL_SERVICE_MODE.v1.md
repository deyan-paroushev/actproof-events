# Internal service mode (v1)

ActProof Events ships an optional, read-only REST API for internal use. It is
local-first and performs no network egress.

## Install and run

```
pip install "actproof-events[api]"
actproof-api --host 127.0.0.1 --port 8787
curl localhost:8787/v1/service-info
```

## What it exposes (read-only)

- `/v1/profiles...` — source-bound profile facts, fields, sources, evidence.
- `/v1/profiles/{act_id}/governance-status` — published profile governance.
- `/v1/release/sbom`, `/v1/release/manifest` — supply-chain assurance facts.
- `/v1/service-info` — the deployment posture, declared verifiably.

## What it deliberately does NOT expose

The bank overlay and overlay-impact report are CLI-only. They carry the bank's
internal review decisions and reviewer identities; they stay file-local and are
never sent over the API. The API receives no bank incident data.

## Network posture

The default bind is loopback (`127.0.0.1`). Binding a non-loopback address
requires `--allow-non-loopback` and is the operator's deliberate decision; place
the service behind your own gateway and authentication. The service has no
built-in auth because it is intended to run locally and serve only public,
source-bound facts.
