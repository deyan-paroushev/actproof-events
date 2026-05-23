#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
cellar_fetch.py, v1.3. Build-time source fetcher for actproof-events.

Purpose
-------
Fetch the official EU legal instruments a regulatory act profile is built
from, hash the retrieved artefact with SHA-256, and emit a source_bindings
fragment ready to drop into an actproof-events act profile.

This is a build-time tool. It runs once, when a profile is built or rebuilt.
It is not called at runtime, not by the lodge form, and not by the verifier.
The hash it captures is pinned into the profile. A receipt is verified later
against that pinned hash, with no live EU call in the trust path.

What is witnessed, and why this changed from v1.2
-------------------------------------------------
v1.2 tried to retrieve the Formex XML through the CELLAR notice API. In
practice that request returns HTTP 406, and the official EUR-Lex retrieval
guide confirms that obtaining the Formex content is a multi-step traversal:
a document notice, then a manifestation RDF document, then a content stream.
That chain is fragile to automate and not worth its cost here.

v1.3 witnesses the Official Journal PDF instead. The electronic Official
Journal is the authentic published form of EU law. A published OJ PDF is
fixed, it does not change after publication, and it is retrievable in a
single request. It carries the full Annex template and glossary in their
canonical layout, which is what the later AI extraction step reads. Hashing
the OJ PDF is a sound and defensible source binding.

How it is fetched
-----------------
Per instrument the tool tries two documented endpoints in order and uses the
first that returns a real PDF:

  1. CELLAR content negotiation:
     GET https://publications.europa.eu/resource/celex/<CELEX>
     with Accept: application/pdf and Accept-Language: eng
  2. EUR-Lex direct PDF endpoint:
     GET https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:<CELEX>

Each response is checked to be a real PDF before it is accepted. The binding
records which URL the artefact actually came from, so the retrieval is
reproducible.

The source binding is source-agnostic
-------------------------------------
The actproof-events standard binds a profile to an official source artefact,
its stable identifier, and its hash. It does not assume the EU. source_type
"eurlex" identifies the EU adapter. A United States profile would carry a
different source_type fetched by a different adapter.

What it does, and does not do
-----------------------------
Does. Resolve each CELEX to its official OJ PDF, download it, compute the
SHA-256, record the ELI URI and a retrieval timestamp, write the artefacts
to disk, and emit source-bindings.json.

Does not. Parse the regulation into a schema. The translation from the legal
text to the claim_schema is an AI extraction step, recorded in the profile's
generation block as ai_assisted_profile_from_authoritative_sources, and
reviewed before release. This tool sources and hashes.

Network notes
-------------
The fetch reaches publications.europa.eu and eur-lex.europa.eu. Run it in an
environment with open outbound network. A browser-like User-Agent is set,
since some EU endpoints reject default agents. It will not run inside a
sandbox whose egress is restricted to a package-registry allowlist.

Reproducibility and staleness
-----------------------------
retrieved_at records when this run captured the bytes. A published OJ PDF is
fixed, so a later re-run should reproduce the same hash. A mismatch is a
signal to check whether the instrument was amended, not a tool failure.

Usage
-----
    python cellar_fetch.py --out ./build/dora-sources
    python cellar_fetch.py --out ./build/dora-sources --dry-run

Outputs, written under --out
----------------------------
    artefacts/<celex>.pdf       one per instrument, the hashed artefact
    source-bindings.json        the fragment for the act profile
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# The instruments the DORA initial-notification profile is built from.
# relied_on lists the articles and annexes the profile actually draws on.
# One source_binding entry is emitted per relied_on item. Entries for the
# same CELEX share that CELEX's single artefact hash.
INSTRUMENTS = [
    {
        "celex": "32022R2554",
        "eli_uri": "http://data.europa.eu/eli/reg/2022/2554/oj",
        "authority": "European Parliament and Council of the European Union",
        "short": "DORA",
        "relied_on": [{"article": "19"}],
    },
    {
        "celex": "32025R0301",
        "eli_uri": "http://data.europa.eu/eli/reg_del/2025/301/oj",
        "authority": "European Commission",
        "short": "RTS, incident reporting content and time limits",
        "relied_on": [{"article": "1"}, {"article": "2"}, {"article": "5"}],
    },
    {
        "celex": "32025R0302",
        "eli_uri": "http://data.europa.eu/eli/reg_impl/2025/302/oj",
        "authority": "European Commission",
        "short": "ITS, incident reporting templates",
        "relied_on": [{"annex": "I"}, {"annex": "II"}],
    },
    {
        "celex": "32024R1772",
        "eli_uri": "http://data.europa.eu/eli/reg_del/2024/1772/oj",
        "authority": "European Commission",
        "short": "RTS, incident classification criteria",
        "relied_on": [{"article": "8"}],
    },
]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) actproof-events-cellar-fetch/1.3"
)


def cellar_pdf_url(celex: str) -> str:
    return f"https://publications.europa.eu/resource/celex/{celex}"


def eurlex_pdf_url(celex: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:{celex}"


# Each strategy: a name, a URL builder, and any extra request headers.
# They are tried in order; the first that returns a real PDF wins.
STRATEGIES = [
    {
        "name": "cellar-content-negotiation",
        "url": cellar_pdf_url,
        "headers": {"Accept": "application/pdf", "Accept-Language": "eng"},
    },
    {
        "name": "eurlex-direct-pdf",
        "url": eurlex_pdf_url,
        "headers": {"Accept": "application/pdf"},
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_prefixed(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def is_pdf(data: bytes) -> bool:
    """A real PDF starts with the %PDF- signature."""
    return data[:5] == b"%PDF-"


def http_get(url: str, headers: dict, timeout: int, user_agent: str) -> bytes:
    """GET url, return the body bytes. Raises on any network or HTTP error."""
    request_headers = {"User-Agent": user_agent}
    request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_official_pdf(
    celex: str, timeout: int, user_agent: str
) -> tuple[bytes, str, str]:
    """Fetch the OJ PDF for a CELEX, trying each strategy in order.

    Returns (pdf_bytes, source_url, strategy_name). Raises RuntimeError with
    every strategy's failure reason if none of them yields a real PDF.
    """
    failures = []
    for strategy in STRATEGIES:
        url = strategy["url"](celex)
        try:
            data = http_get(url, strategy["headers"], timeout, user_agent)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            failures.append(f"  {strategy['name']}: {exc}  ({url})")
            continue
        if not is_pdf(data):
            failures.append(
                f"  {strategy['name']}: response was not a PDF, "
                f"{len(data)} bytes  ({url})"
            )
            continue
        return data, url, strategy["name"]

    raise RuntimeError(
        f"every strategy failed for {celex}:\n" + "\n".join(failures)
    )


def relied_on_label(item: dict) -> str:
    if "article" in item:
        return f"Article {item['article']}"
    if "annex" in item:
        return f"Annex {item['annex']}"
    return "(unspecified)"


def bindings_for(
    instrument: dict, retrieved_at: str, digest: str, source_url: str, method: str
) -> list[dict]:
    """Expand one instrument into its source_binding entries, one per relied_on."""
    entries = []
    for relied in instrument["relied_on"]:
        entry = {
            "source_type": "eurlex",
            "celex": instrument["celex"],
            "eli_uri": instrument["eli_uri"],
            "authority": instrument["authority"],
            "artifact_type": "oj_pdf",
            "format": "application/pdf",
            "retrieved_at": retrieved_at,
            "retrieved_from": {"url": source_url, "method": method},
            "sha256": digest,
        }
        entry.update(relied)  # adds "article" or "annex"
        entries.append(entry)
    return entries


def run(out_dir: Path, timeout: int, user_agent: str, dry_run: bool) -> int:
    print("cellar_fetch v1.3. actproof-events build-time source fetcher.")
    print(f"Mode: {'dry-run, nothing downloaded or written' if dry_run else 'fetch'}")
    print("Artefact witnessed and hashed: the official Official Journal PDF.")
    print()

    artefact_dir = out_dir / "artefacts"
    all_bindings: list[dict] = []

    for instrument in INSTRUMENTS:
        celex = instrument["celex"]
        relied = ", ".join(relied_on_label(i) for i in instrument["relied_on"])
        print(f"  {celex}  {instrument['short']}")
        print(f"    relied on: {relied}")

        if dry_run:
            for strategy in STRATEGIES:
                print(f"    would try [{strategy['name']}]: {strategy['url'](celex)}")
            print(f"    would write: {artefact_dir / (celex + '.pdf')}")
            print()
            continue

        try:
            data, source_url, method = fetch_official_pdf(celex, timeout, user_agent)
        except RuntimeError as exc:
            print()
            print(f"ERROR. Could not retrieve a PDF for {celex}.")
            print(str(exc))
            print("  Run this tool in an environment with open outbound network.")
            return 1

        retrieved_at = now_iso()
        digest = sha256_prefixed(data)
        artefact_dir.mkdir(parents=True, exist_ok=True)
        (artefact_dir / f"{celex}.pdf").write_bytes(data)
        print(f"    retrieved: {len(data)} bytes via [{method}]")
        print(f"    source:    {source_url}")
        print(f"    {digest}")
        all_bindings.extend(
            bindings_for(instrument, retrieved_at, digest, source_url, method)
        )
        print()

    if dry_run:
        print("Dry-run complete. Re-run without --dry-run to fetch and write.")
        return 0

    fragment = {
        "generated_at": now_iso(),
        "generator": "actproof-events cellar_fetch.py v1.3",
        "note": (
            "Build-time source bindings. Each entry pins the SHA-256 of the "
            "Official Journal PDF retrieved for its CELEX. Verification checks "
            "a receipt against these pinned hashes, with no live EU call. "
            "source_type 'eurlex' is the EU adapter; the binding shape is "
            "source-agnostic."
        ),
        "source_bindings": all_bindings,
    }
    out_path = out_dir / "source-bindings.json"
    out_path.write_text(json.dumps(fragment, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"  {len(all_bindings)} source_binding entries across {len(INSTRUMENTS)} instruments.")
    print()
    print("Reconciliation checklist for Step 3, read from the fetched PDFs:")
    print("  1. Annex II of 32025R0302. Confirm the field names and value lists")
    print("     for the DORA profile's claim fields.")
    print("  2. Article 8 of 32024R1772. Take the complete classification-criteria")
    print("     enumeration and the a-to-g letter mapping verbatim.")
    print("  3. Article 2 of 32025R0301. Confirm the required initial-notification")
    print("     content matches the profile's required fields.")
    print("  4. Annex II and 32024R1772. Check whether classification records and")
    print("     detection records are article-grounded, to confirm the two")
    print("     evidence labels on the DORA profile.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and hash the official EU PDFs behind the DORA act profile.",
    )
    parser.add_argument(
        "--out", default="./build/dora-sources",
        help="output directory, default ./build/dora-sources",
    )
    parser.add_argument(
        "--timeout", type=int, default=60,
        help="per-request timeout in seconds, default 60",
    )
    parser.add_argument(
        "--user-agent", default=DEFAULT_USER_AGENT,
        help="User-Agent header for the requests",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="resolve and print the plan without downloading or writing",
    )
    args = parser.parse_args(argv)
    return run(Path(args.out), args.timeout, args.user_agent, args.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
