# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Module entry point for ``python -m actproof_events``.

Currently exposes one public subcommand:

    python -m actproof_events quickstart

which runs an end-to-end, offline demonstration: build a source-atom
statement, sign it, register it into a local transparency log, mint and
verify the receipt, then run a continuity check against a real later
regulatory event. See ``actproof_events.quickstart``.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("usage: python -m actproof_events <command> [options]")
        print()
        print("commands:")
        print("  quickstart                      Run the offline end-to-end demonstration.")
        print("  demo dora-301-302-continuity    Run the DORA 301 -> 302 continuity demo.")
        print()
        print("Run 'python -m actproof_events <command> --help' for command options.")
        return 0 if (argv and argv[0] in ("-h", "--help", "help")) else 2

    command, rest = argv[0], argv[1:]
    if command == "quickstart":
        try:
            from actproof_events.quickstart import main as quickstart_main
        except ModuleNotFoundError:
            print(
                "quickstart is not available in this build. Run the worked demo instead:\n"
                "  python -m actproof_events demo dora-301-302-continuity"
            )
            return 2
        return quickstart_main(rest)

    if command == "demo":
        if not rest or rest[0] in ("-h", "--help", "help"):
            print("usage: python -m actproof_events demo <name> [options]")
            print()
            print("demos:")
            print("  dora-301-302-continuity   Source-dependency continuity (Article 19 + 301 + 302).")
            return 0 if (rest and rest[0] in ("-h", "--help", "help")) else 2
        name, demo_rest = rest[0], rest[1:]
        if name == "dora-301-302-continuity":
            from actproof_events.dora_continuity_demo import main as demo_main

            return demo_main(demo_rest)
        print(f"unknown demo: {name!r}")
        print("run 'python -m actproof_events demo --help' for available demos.")
        return 2

    print(f"unknown command: {command!r}")
    print("run 'python -m actproof_events --help' for available commands.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
