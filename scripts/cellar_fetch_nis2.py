#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
cellar_fetch_nis2.py, v1.3-nis2. Build-time source fetcher for the
actproof-events NIS2 significant-incident notification profile.

This is the DORA cellar_fetch.py v1.3, re-pointed at the two instruments the
NIS2 Article 23 early-warning profile is built from. The fetch, hash, and
binding logic are unchanged. Only the INSTRUMENTS list differs.

Why only two instruments
------------------------
DORA's initial notification draws on four instruments because its required
field surface is dispersed across a base Regulation, two RTS, and one ITS.
NIS2 Article 23 is structurally leaner at the early-warning stage:

  1. Directive (EU) 2022/2555, Article 23. The reporting obligation itself,
     including the early-warning content surface in Article 23(4)(a): the two
     judgement flags (suspected unlawful or malicious cause; possible
     cross-border impact) on top of the identity and timing minimum.
  2. Commission Implementing Regulation (EU) 2024/2690, Articles 3 to 14.
     The exhaustive "significant incident" thresholds for Article 23(3): the
     horizontal cases in Article 3 and the entity-type-specific cases in
     Articles 5 to 14. This is the NIS2 analogue of DORA's classification RTS
     2024/1772.

Two facts that the profile records honestly, not the fetcher:

  - NIS2 is a Directive. The operative early-warning FORM is the national CSIRT
    portal of the Member State of establishment, not an EU-level template. There
    is no harmonised EU field template equivalent to DORA's ITS 2025/302 Annex.
    The profile binds to the EU instruments and flags national transposition as
    the site where operative divergence enters. That is a finding, not a gap.
  - Financial entities are carved out of NIS2 incident reporting by the lex
    specialis rule (DORA applies instead). The profile's issuer scope is the
    essential or important entity, and the DORA/NIS2 overlap is analysed at the
    group and shared-incident level, not as "every bank files both".

Network notes
-------------
Identical to the DORA fetcher. Reaches publications.europa.eu and
eur-lex.europa.eu. Run in an environment with open outbound network. It will
NOT run inside a sandbox whose egress is restricted to a package-registry
allowlist.

Usage
-----
    python cellar_fetch_nis2.py --out ./build/nis2-sources
    python cellar_fetch_nis2.py --out ./build/nis2-sources --dry-run
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

# The instruments the NIS2 early-warning profile is built from.
# relied_on lists the articles the profile actually draws on. One
# source_binding entry is emitted per relied_on item. Entries for the same
# CELEX share that CELEX's single artefact hash.
INSTRUMENTS = [
    {
        "celex": "32022L2555",
        "eli_uri": "http://data.europa.eu/eli/dir/2022/2555/oj",
        "authority": "European Parliament and Council of the European Union",
        "short": "NIS2 Directive",
        "relied_on": [{"article": "23"}],
    },
    {
        "celex": "32024R2690",
        "eli_uri": "http://data.europa.eu/eli/reg_impl/2024/2690/oj",
        "authority": "European Commission",
        "short": "CIR, significant-incident thresholds and technical requirements",
        "relied_on": [{"article": "3"}, {"article": "4"}],
    },
]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) actproof-events-cellar-fetch/1.3-nis2"
)


def cellar_pdf_url(celex: str) -> str:
    return f"https://publications.europa.eu/resource/celex/{celex}"


def eurlex_pdf_url(celex: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:{celex}"


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
    return data[:5] == b"%PDF-"


def http_get(url: str, headers: dict, timeout: int, user_agent: str) -> bytes:
    request_headers = {"User-Agent": user_agent}
    request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_official_pdf(
    celex: str, timeout: int, user_agent: str
) -> tuple[bytes, str, str]:
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
        entry.update(relied)
        entries.append(entry)
    return entries


def run(out_dir: Path, timeout: int, user_agent: str, dry_run: bool) -> int:
    print("cellar_fetch v1.3-nis2. actproof-events build-time source fetcher.")
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
        "generator": "actproof-events cellar_fetch_nis2.py v1.3-nis2",
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
    print("  1. Article 23(4)(a) of 32022L2555. Confirm the early-warning content")
    print("     surface: the two judgement flags (suspected unlawful/malicious;")
    print("     possible cross-border impact) plus the identity and timing minimum.")
    print("  2. Article 3 of 32024R2690. Take the horizontal significant-incident")
    print("     cases verbatim; these are the classification criteria for the")
    print("     significance assessment that gates the obligation.")
    print("  3. Articles 5 to 14 of 32024R2690. Note the entity-type-specific")
    print("     significance cases; these add to source dispersion only for the")
    print("     digital-infrastructure entity types the CIR enumerates.")
    print("  4. Article 23(4) and (6) of 32022L2555. Check the confidentiality")
    print("     treatment (security and commercial interests, confidentiality of")
    print("     the information provided) to confirm the disclosure tiers.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and hash the official EU PDFs behind the NIS2 act profile.",
    )
    parser.add_argument(
        "--out", default="./build/nis2-sources",
        help="output directory, default ./build/nis2-sources",
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
