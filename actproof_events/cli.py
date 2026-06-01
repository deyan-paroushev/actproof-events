# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""actproof_events.cli: the ``actproof-mapper`` command-line interface.

This exposes the experimental ActProof Mapper pipeline as a single console
command with subcommands, so that after an editable install::

    pip install -e .

a reviewer or collaborator can run::

    actproof-mapper run-all --example dora
    actproof-mapper source-dossier --bindings ... --sources ... --out ...

instead of invoking the step scripts by file path.

This is repo-local tooling, not a public packaged SDK. It is one entry point
with subcommands (rather than many entry points) so that the installed command
surface stays small while the mapper is experimental and its step contracts may
still change.

The subcommands simply dispatch to the step scripts under ``mapper/``. The
mapper is located relative to the repository, working both from a source
checkout and from an editable install.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


# Map each subcommand name to the step script that implements it.
_SUBCOMMANDS = {
    "source-dossier": "steps/step1_source_dossier.py",
    "source-fragments": "steps/step2_source_fragments.py",
    "legal-actions": "steps/step3_legal_actions.py",
    "mapped-fields": "steps/step4_mapped_fields.py",
    "evidence-labels": "steps/step5_evidence_labels.py",
    "interpretation-decisions": "steps/step6_interpretation_decisions.py",
    "traceability": "steps/step7_traceability_matrix.py",
    "assemble-profile": "steps/step8_profile_assembler.py",
    "run-all": "run_all.py",
}


def _find_mapper_dir() -> Path | None:
    """Locate the mapper/ directory.

    Works from a source checkout or an editable install by walking up from this
    file to the repository root and looking for a sibling ``mapper`` directory.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "mapper"
        if (candidate / "run_all.py").is_file():
            return candidate
    return None


def _print_usage() -> None:
    print("actproof-mapper - experimental ActProof Mapper CLI")
    print("")
    print("Usage:")
    print("  actproof-mapper <subcommand> [args...]")
    print("")
    print("Subcommands:")
    for name in _SUBCOMMANDS:
        print("  {}".format(name))
    print("")
    print("Each subcommand passes its remaining arguments straight to the step.")
    print("Run the worked DORA example end to end:")
    print("  actproof-mapper run-all --example dora")
    print("")
    print("Status: experimental, repo-local tooling. Not a public packaged SDK.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help", "help"):
        _print_usage()
        return 0

    sub = argv[0]
    if sub not in _SUBCOMMANDS:
        print("Unknown subcommand: {}".format(sub), file=sys.stderr)
        print("Run 'actproof-mapper --help' for the list.", file=sys.stderr)
        return 2

    mapper_dir = _find_mapper_dir()
    if mapper_dir is None:
        print("Could not locate the mapper/ directory. The CLI expects the "
              "mapper/ directory at the repository root (it is not bundled into "
              "the installed wheel).", file=sys.stderr)
        return 1

    script = mapper_dir / _SUBCOMMANDS[sub]
    if not script.is_file():
        print("Step script not found: {}".format(script), file=sys.stderr)
        return 1

    # Hand the remaining args to the step script as if it were called directly.
    sys.argv = [str(script)] + argv[1:]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:  # steps call sys.exit on failure; propagate the code
        return int(exc.code) if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
