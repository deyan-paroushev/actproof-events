#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
ActProof Mapper - Run All
==========================

WHAT THIS DOES (in plain words)
-------------------------------
This runs the whole journey in one command: an official source, through eight
controlled steps, to a finished ActProof profile JSON.

    PDF sources
      -> [1] source dossier       verify the PDFs by hash
      -> [2] source fragments     name the pieces of law a human selected
      -> [3] legal actions        who must do what, to whom, by when
      -> [4] mapped fields        derive each profile field, with its basis
      -> [5] evidence labels      supporting records (never overclaimed)
      -> [6] interpretation       record every judgement, open to challenge
      -> [7] traceability matrix  bind it all into one inspectable table
      -> [8] profile assembler    emit the final profile + full mapping package

Each step reads the previous step's output plus, where relevant, a
human-authored "selection" file (the review gate). Each step writes its own
outputs and a check log. If any step fails its structural checks, the run
stops there and tells you which step and why.

The point is transparency: you can run this, read every intermediate file, and
see exactly how a public rule became machine-readable JSON - and challenge any
step.

USAGE
-----
    python run_all.py --example dora
    python run_all.py --inputs <dir> --sources <dir> --out <dir>

With --example dora it uses examples/dora/inputs and examples/dora/sources and
writes to examples/dora/outputs.

The run succeeds even if the source PDFs are absent (Step 1 reports them as
"missing"). It stops only on an actual structural failure in a step.
"""

import argparse
import os
import subprocess
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = os.path.join(HERE, "steps")


def run_step(label, script, args, strict=False):
    """Run one step as a subprocess. Returns the exit code.

    When strict is True, the step is told (via ACTPROOF_STRICT) to exit with
    code 2 if it produced warnings, so the runner can stop on warnings.
    """
    cmd = [sys.executable, os.path.join(STEPS, script)] + args
    print("\n" + "=" * 60)
    print("STEP: {}".format(label))
    print("=" * 60)
    env = dict(os.environ)
    if strict:
        env["ACTPROOF_STRICT"] = "1"
    result = subprocess.run(cmd, env=env)
    return result.returncode


def main():
    ap = argparse.ArgumentParser(description="Run the full ActProof Mapper pipeline.")
    ap.add_argument("--example", help="Named example (e.g. 'dora'). Sets inputs/sources/out automatically.")
    ap.add_argument("--inputs", help="Directory of human-authored input/selection files.")
    ap.add_argument("--sources", help="Directory of source PDF files.")
    ap.add_argument("--out", help="Output directory for all step outputs.")
    ap.add_argument("--stop-on-warning", action="store_true",
                    help="Treat a step's warnings as a stop condition (default: continue).")
    args = ap.parse_args()

    if args.example:
        base = os.path.join(HERE, "examples", args.example)
        inputs = args.inputs or os.path.join(base, "inputs")
        sources = args.sources or os.path.join(base, "sources")
        out = args.out or os.path.join(base, "outputs")
    else:
        if not (args.inputs and args.sources and args.out):
            ap.error("Without --example you must give --inputs, --sources and --out.")
        inputs, sources, out = args.inputs, args.sources, args.out

    os.makedirs(out, exist_ok=True)

    def i(name):  # input file path
        return os.path.join(inputs, name)

    def o(name):  # output file path
        return os.path.join(out, name)

    # The pipeline, in order. Each tuple: (label, script, args).
    pipeline = [
        ("1 - Source dossier", "step1_source_dossier.py", [
            "--bindings", i("source-bindings.json"),
            "--sources", sources,
            "--out", out]),
        ("2 - Source fragments", "step2_source_fragments.py", [
            "--dossier", o("source-dossier.json"),
            "--provisions", i("selected-provisions.json"),
            "--out", out]),
        ("3 - Legal actions", "step3_legal_actions.py", [
            "--fragments", o("source-fragments.json"),
            "--actions", i("selected-legal-actions.json"),
            "--out", out]),
        ("4 - Mapped fields", "step4_mapped_fields.py", [
            "--actions", o("legal-actions.json"),
            "--profile", i("profile-draft.json"),
            "--derivations", i("selected-field-derivations.json"),
            "--out", out]),
        ("5 - Evidence labels", "step5_evidence_labels.py", [
            "--actions", o("legal-actions.json"),
            "--fields", o("mapped-fields.json"),
            "--evidence", i("selected-evidence-labels.json"),
            "--out", out]),
        ("6 - Interpretation decisions", "step6_interpretation_decisions.py", [
            "--fields", o("mapped-fields.json"),
            "--evidence", o("evidence-labels.json"),
            "--decisions", i("selected-interpretation-decisions.json"),
            "--out", out]),
        ("7 - Traceability matrix", "step7_traceability_matrix.py", [
            "--fragments", o("source-fragments.json"),
            "--actions", o("legal-actions.json"),
            "--fields", o("mapped-fields.json"),
            "--evidence", o("evidence-labels.json"),
            "--decisions", o("interpretation-decisions.json"),
            "--out", out]),
        ("8 - Profile assembler", "step8_profile_assembler.py", [
            "--dossier", o("source-dossier.json"),
            "--fragments", o("source-fragments.json"),
            "--actions", o("legal-actions.json"),
            "--fields", o("mapped-fields.json"),
            "--evidence", o("evidence-labels.json"),
            "--decisions", o("interpretation-decisions.json"),
            "--traceability", o("traceability.json"),
            "--out", out]),
    ]

    for label, script, step_args in pipeline:
        code = run_step(label, script, step_args, strict=args.stop_on_warning)
        if code == 2:
            print("\n" + "!" * 60)
            print("PIPELINE STOPPED at step: {}".format(label))
            print("Strict mode (--stop-on-warning): this step produced warnings.")
            print("Read the step's check log in: {}".format(out))
            print("!" * 60)
            sys.exit(2)
        if code != 0:
            print("\n" + "!" * 60)
            print("PIPELINE STOPPED at step: {}".format(label))
            print("This step reported a structural failure (exit code {}).".format(code))
            print("Read the step's check log in: {}".format(out))
            print("!" * 60)
            sys.exit(1)

    # Success summary.
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print("The journey from source to profile is done.")
    print("")
    print("Final artefacts in {}:".format(out))
    print("  - actproof-profile.json   the finished operational profile")
    print("  - mapping-package.json    the complete evidence record")
    print("  - traceability.json/.md/.csv   how each field maps to its source")
    print("  - one register + check log per step")
    print("")
    print("What this proves: the profile is reproducible from the recorded steps.")
    print("What this does NOT prove: legal correctness, completeness or compliance.")


if __name__ == "__main__":
    main()
