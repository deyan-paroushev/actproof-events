# ActProof Events

ActProof Events is an open standard for turning a regulated act into a receipt that a third party can verify without trusting the issuer or any intermediary.

**Project site: [actproof.org](https://actproof.org).** The site explains the full ActProof stack and the reasoning behind it. ActProof Events is the standard layer, the companion `actproof` library is the receipt substrate, and applications consume both. Start there for the architecture and the why. This README is the reference for the catalogue itself.

When an organization reports a regulated act, the report is a claim. A DORA incident notification, an EUDR due diligence statement, a NIS2 management body approval are all such reports. Whoever relies on one of them today trusts the issuer who wrote it, and the platform that carried it. ActProof Events removes both points of trust. The act becomes a receipt that is cryptographically anchored to a public ledger and bound to the official text of the regulation it claims to satisfy. Correctness becomes something you check, not something you are asked to believe.

This repository holds the standard, the schemas, the catalogue of act profiles, and the conformance test vectors. The companion package `actproof` holds the substrate that mints, anchors, and verifies the receipts themselves.


## Profile-view export

`actproof-events` can export a rich public JSON projection from a canonical catalogue entry. The catalogue entry remains the canonical object; the exported profile view is the renderable projection used by websites, APIs, MCP servers, audit packs and compliance interfaces.

CLI:

```bash
actproof-events export-profile-view \
  op:eu.dora.ict_incident_notification_initial.v1 \
  --out dora.profile-view.json \
  --validate
```

Python:

```python
from actproof_events.exports import build_profile_view

view = build_profile_view("op:eu.dora.ict_incident_notification_initial.v1")
```

The projection declares `profile_view_schema: actproof.profile_view.v1`, carries package-version provenance, includes coverage metrics, and contains two explicit hashes: `profile_semantic_hash` for version-independent profile reproducibility and `profile_artifact_hash` for release-specific artifact traceability. `profile_view_hash` remains as a backward-compatible alias for the semantic hash. See `docs/PROFILE_VIEW_EXPORT.md`.

## How verification works

A regulated act has three things a relying party needs to be sure of. ActProof Events answers each one separately.

**Provenance.** Every act profile cites the official sources it draws from by stable identifier, and pins the SHA-256 hash of each one. A reader can fetch the same official document, hash it, and confirm the profile was built against the published law and not a paraphrase of it. This is mechanical. No judgement is involved.

**Schema conformance.** Every catalogue entry ships with conformance test vectors. An implementation runs the vectors and gets a deterministic pass or fail. Two independent implementations that both pass produce byte-identical receipts. This is mechanical too.

**Faithfulness.** Whether a profile's data model honestly reflects what the regulation requires is a question of judgement, and judgement cannot be hashed. ActProof Events does not hide this. Every source-bound profile ships a transparency note that records, in plain language, what the law requires, how the profile's fields map to it, and every interpretive decision that was made. The note is open. Anyone can read it and disagree.

The standard's position is simple. Check us, do not trust us. Provenance and conformance are checkable by machine. Faithfulness is checkable by a human reading an open transparency note against the open text of the law. Nothing relies on trusting this project.

## What this package ships

`actproof-events` is a Python package with no required runtime dependencies. Installing it gives a consuming application the following, as bundled data:

- **The act-profile catalogue.** JSON catalogue entries, one per regulated act, each describing the act's claim fields, evidence requirements, and source bindings.
- **The JSON Schemas** that define the structure of a catalogue entry, so a consumer can validate the entries it loads.
- **The conformance test vectors**, one companion file per catalogue entry, released CC0 so any implementation can use them as a shared conformance suite with no licensing friction.
- **The specification text**, together with the vocabularies, the schema versioning policy, and the catalogue loader contract, bundled so an installed copy carries the standard it implements.

The package exposes a small, typed API for locating this data:

```python
from actproof_events import (
    get_catalogue_path,
    get_schema_path,
    get_profile_view_schema_path,
    get_spec_path,
    list_catalogue_entries,
    __version__,
    __spec_version__,
)

# Every authoritative catalogue entry, as a sorted list of Path objects.
# Deprecated entries and test-vector files are excluded by default.
for entry_path in list_catalogue_entries():
    print(entry_path.name)

# The bundled JSON Schema for catalogue entries.
schema_path = get_schema_path("act_profile.v3")

# The bundled JSON Schema for exported profile views.
profile_view_schema_path = get_profile_view_schema_path()

# The bundled specification text.
spec_path = get_spec_path()

# The catalogue directory, if you would rather walk it yourself.
catalogue_dir = get_catalogue_path()
```

`__version__` is the package version. `__spec_version__` records which revision of the specification the installed package embodies. The companion documents are reachable the same way, through `get_vocabularies_path`, `get_schema_version_policy_path`, and `get_contract_path`.

## Install

```
pip install actproof-events
```

For full JSON Schema validation of catalogue entries, install the optional extra:

```
pip install "actproof-events[schema-validation]"
```

The extra pulls in `jsonschema`. The base package needs only the standard library.

## The catalogue

The catalogue is federated. It uses two namespaces.

The canonical namespace `op:` is curated by this project. An entry earns a place in it by citing a stable regulatory or organizational basis, by being structurally clear enough to reduce to mechanical constraints, and by being broadly applicable. Canonical entries go through the review described in `CONTRIBUTING_ACTS.md`.

The third-party namespace `x.<reverse-dns>:` is permissionless. Any organization that controls a DNS domain may publish its own entries by serving them under `.well-known/actproof-events/acts/` on that domain. No pull request and no coordination with this project are needed. Verifiers resolve third-party identifiers at verification time. Third-party publication is the architectural default, not a downgrade.

The catalogue currently spans EU regulatory acts (DORA, EUDR, NIS2), a civil-society mandate settlement, and the project's own software-release and standards-engagement acts.

The DORA ICT-incident initial-notification profile, `op:eu.dora.ict_incident_notification_initial.v1`, is the reference profile. It has been authored end to end under the source-binding process. It pins the SHA-256 of every official EU instrument it draws from, Regulation (EU) 2022/2554 together with its delegated and implementing acts, and it ships a transparency note recording every interpretive decision. It is the worked example the rest of the catalogue is being brought up to. Each entry declares its maturity in a `profile_status` block: the DORA profile is `candidate`, and the profiles that predate the source-binding process are `draft` and do not yet carry source bindings.

Superseded entries are kept under `_deprecated/` subdirectories. They remain in the tree so historical receipts can still be resolved, and they are excluded from the authoritative API by default.

## Two packages

ActProof Events is published as two Python packages, both Apache-2.0, with a clean split of responsibility.

`actproof-events`, this package, is the standard. It is the specification, the schemas, the act-profile catalogue, and the conformance vectors. It has no runtime dependencies and ships no anchoring code. It is the thing a verifier reads to know what a correct receipt looks like.

`actproof` is the substrate. It mints receipts, canonicalizes them, anchors them to the public ledger, and verifies them. It depends on `actproof-events` for the catalogue and schemas.

Splitting them keeps the standard light enough to be a dependency of anything, and lets the catalogue version independently of the anchoring code.

## Repository layout

```
spec/                        the specification text, schemas, and version policy
catalogue/acts/              the act-profile catalogue, organized by jurisdiction
actproof_events/             the installable Python package
scripts/                     test-vector generation and catalogue validation
mapper/                      experimental: source-PDF-to-profile mapping pipeline
salt-erasure/                the salt-erasure module for redactable evidence
docs/releases/               per-release notes
CONTRIBUTING_ACTS.md         how to propose a catalogue entry
CATALOGUE_LOADER_CONTRACT.md the contract a catalogue loader must honor
```

## ActProof Mapper (experimental)

`mapper/` contains a controlled, inspectable process that takes the official
source PDFs and produces a profile, recording every step: source verification,
fragments, legal actions, mapped fields, evidence labels, interpretation
decisions, and the traceability matrix that binds them. It is the worked,
runnable form of the source-to-profile mapping behind the DORA example.

It is experimental, not part of the published package, and not on PyPI. Run the
worked example with `python mapper/run_all.py --example dora`; Step 1 verifies
the four official DORA source PDFs against their pinned hashes. See
`mapper/README.md`.

For a nicer local experience, an editable install exposes the pipeline as a
console command (repo-local tooling, not a public package):

```
pip install -e .
actproof-mapper run-all --example dora
```

`actproof-mapper --help` lists the per-step subcommands.

## Specification

The specification text lives at `spec/actproof-events.spec.md`. It defines the catalogue entry schema, the manifest and envelope formats, the RFC 8785 canonicalization pipeline, the on-chain note format, and the verifier conformance test vector format.

ActProof Events is architecturally aligned with the IETF SCITT architecture. A COSE wire-format bridge is planned for a later iteration of the specification. Until it ships, ActProof Events implementations emit JSON-canonical receipts and are not yet SCITT-compatible at the wire level.

## Contributing

Catalogue contributions are welcome from regulators, industry associations, standards bodies, downstream implementers, and individual experts. A contribution is judged on its source binding, not on who submits it. `CONTRIBUTING_ACTS.md` describes the process for both namespaces, including the staged authoring process for a source-bound profile.

Contributions to the specification text, the reference code, and the test infrastructure follow the standard GitHub pull-request flow.

## License

ActProof Events combines two licenses, and the distributed package carries the full text of both, `LICENSE` and `LICENSES/CC0-1.0.txt`.

The Python package code, the JSON schemas, and the catalogue entries are licensed under Apache-2.0.

The specification text is dedicated to the public domain under CC0-1.0, so it can be implemented and re-published without restriction.

The conformance test vectors are released under CC0-1.0, so any implementation, open or proprietary, can use them as a shared conformance suite.

## Maintainer

ActProof Events is maintained by Deyan Paroushev at Advisa EOOD, Sofia.

- Repository: https://github.com/deyan-paroushev/actproof-events
- Specification: https://github.com/deyan-paroushev/actproof-events/blob/main/spec/actproof-events.spec.md
- Issues: https://github.com/deyan-paroushev/actproof-events/issues
