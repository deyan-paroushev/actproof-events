#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
pack_sources.py. Bundle build/dora-sources/ into one zip for transfer.

build/dora-sources/ holds the four Official Journal PDFs and
source-bindings.json produced by cellar_fetch.py. That directory is
gitignored, so it is not in the repo and not in any zip downloaded from
GitHub. This tool packs it into a single file you can download from the
Codespace file explorer and upload for Step 3.

Pure standard library. No executable bit needed, you invoke it with python.
No zip binary needed, it uses Python's zipfile.

Usage
-----
Run it from the repo root:

    python pack_sources.py

Output
------
    build/dora-sources.zip

That path is inside build/, which is gitignored, so this does not touch git.
Then, in the Codespace file explorer, right-click build/dora-sources.zip and
choose Download. Upload that zip here.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def main() -> int:
    src = Path("build/dora-sources")
    out = Path("build/dora-sources.zip")

    if not src.is_dir():
        print(f"ERROR: {src} not found.")
        print("Run this from the repo root, after scripts/cellar_fetch.py has run.")
        return 1

    files = sorted(p for p in src.rglob("*") if p.is_file())
    if not files:
        print(f"ERROR: {src} is empty. Nothing to pack.")
        return 1

    print(f"Packing {len(files)} file(s) from {src}:")
    total = 0
    for f in files:
        size = f.stat().st_size
        total += size
        print(f"  {f}  ({size:,} bytes)")

    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for f in files:
            archive.write(f, f.relative_to(src.parent))

    print()
    print(f"Wrote {out}  ({out.stat().st_size:,} bytes packed, {total:,} bytes raw)")
    print()
    print("To get it onto your machine:")
    print("  in the Codespace file explorer, right-click build/dora-sources.zip")
    print("  and choose Download. Then upload that zip here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
