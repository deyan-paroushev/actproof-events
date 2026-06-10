# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Production-shaped source-dependency continuity worked example.

Run::

    python -m actproof_events demo dora-301-302-continuity

The demo is offline and local. It is production-shaped in the sense that the
objects in the continuity chain are typed statements, COSE-signed, locally
registered, receipted, and verified through the package's real code path:

    source atoms -> profile-dependency/v1 statement -> COSE receipt
       -> downstream binding -> continuity assessment

DORA is the worked example. The mechanism is general: a downstream artifact is
bound to a maintained source-dependency set, then later compared against the
current maintained source-dependency set. A mismatch returns NEEDS_REVIEW; it
never decides compliance or legal sufficiency.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from actproof_events.cose_signing import sign_statement, write_cose_artifact, write_dev_keypair
from actproof_events.scitt_profile import build_source_atom_statement, canonical_json_sha256
from actproof_events.scitt_registration import (
    compute_receipt_hash,
    init_local_log,
    register_signed_statement,
    verify_local_receipt,
)
from actproof_events.statement_profiles import (
    PROFILE_DEPENDENCY_STATEMENT_SCHEMA,
    PROFILE_DEPENDENCY_STATEMENT_TYPE,
    compute_profile_dependency_statement_hash,
)
from actproof_events.text_capture import compute_official_text_sha256

CATALOGUE_ACT = "op:eu.dora.ict_incident_notification_initial.v1"
CATALOGUE_ATOM = "src.eu.dora.32022R2554.art19.reporting_obligation"

PROFILE_ID = "eu.dora.major-ict-incident-reporting.profile"
ROOT_TYPE = "actproof.profile_dependency_root.v1"
CANONICALIZATION = "JCS / RFC 8785 compatible JSON (sort keys, compact separators)"
_RULE = "-" * 68

ART19_1_FIRST_SENTENCE = (
    "Financial entities shall report major ICT-related incidents to the relevant "
    "competent authority as referred to in Article 46 in accordance with paragraph 4 "
    "of this Article.\n"
)

REG302_ART1_1_A = (
    "Financial entities shall use the template laid down in Annex I to submit the "
    "initial notification, the intermediate report, and the final report referred to "
    "in Article 19(4) of Regulation (EU) 2022/2554 as follows:\n"
    "(a) financial entities that submit an initial notification shall complete the "
    "data fields of the template which correspond to the information to be provided "
    "in accordance with Article 2 of Commission Delegated Regulation (EU) 2025/301, "
    "and may, where they already have that information, complete those data fields "
    "the completion of which is not required for an initial notification but is "
    "required for an intermediate or final report.\n"
)

NON_CLAIMS = [
    "This demo does not determine legal compliance or legal sufficiency.",
    "The official legal source remains authoritative.",
    "NEEDS_REVIEW means the maintained source-dependency basis moved; it is not a non-compliance finding.",
    "Local COSE receipts in this demo are local transparency-pilot receipts, not external SCITT service receipts.",
]


def _short(h: str | None) -> str:
    if not h:
        return "(none)"
    body = h.split(":", 1)[1] if ":" in h else h
    return f"sha256:{body[:16]}..." if len(body) > 16 else h


def _verbatim_atom(atom_id: str, celex: str, eli: str, locator: str, text: str, dependency_role: str, dependency_status: str) -> dict[str, Any]:
    atom = {
        "atom_id": atom_id,
        "source_type": "eu_regulation",
        "source_role": "verbatim_official_text_excerpt",
        "locator": locator,
        "celex": celex,
        "eli": eli,
        "official_text_sha256": compute_official_text_sha256(text),
        "official_text_hash_basis": "verbatim official text excerpt; actproof normalisation v1",
        "text_excerpt": text,
        "dependency_role": dependency_role,
        "dependency_status": dependency_status,
    }
    atom["canonical_atom_json_sha256"] = canonical_json_sha256(atom)
    return atom


def _summary_atom(atom_id: str, celex: str, eli: str, summary: str, dependency_role: str, dependency_status: str) -> dict[str, Any]:
    descriptor = f"SUMMARY DESCRIPTOR (not verbatim official text).\n{summary}\n"
    atom = {
        "atom_id": atom_id,
        "source_type": "eu_regulation",
        "source_role": "summary_descriptor",
        "celex": celex,
        "eli": eli,
        "summary_text_sha256": compute_official_text_sha256(descriptor),
        "summary_text_hash_basis": "sha256 over a SUMMARY DESCRIPTOR, NOT the verbatim official text",
        "summary": summary,
        "note": "Descriptor-level dependency used for demo scope control; not an official-text atom.",
        "dependency_role": dependency_role,
        "dependency_status": dependency_status,
    }
    atom["canonical_atom_json_sha256"] = canonical_json_sha256(atom)
    return atom


def _dependency_root_envelope(atoms: list[dict[str, Any]]) -> dict[str, Any]:
    basis = sorted(
        [
            {
                "atom_id": a["atom_id"],
                "dependency_role": a.get("dependency_role", "unspecified"),
                "dependency_status": a.get("dependency_status", "required"),
                "source_role": a.get("source_role"),
                "canonical_atom_json_sha256": a["canonical_atom_json_sha256"],
                "official_text_sha256": a.get("official_text_sha256"),
                "summary_text_sha256": a.get("summary_text_sha256"),
            }
            for a in atoms
        ],
        key=lambda x: x["atom_id"],
    )
    return {
        "root_type": ROOT_TYPE,
        "hash_algorithm": "SHA-256",
        "canonicalization": CANONICALIZATION,
        "profile_id": PROFILE_ID,
        "dependency_basis": basis,
    }


def _profile_dependency_statement(profile_version: str, policy: str, atoms: list[dict[str, Any]]) -> dict[str, Any]:
    envelope = _dependency_root_envelope(atoms)
    dependency_root = canonical_json_sha256(envelope)
    statement: dict[str, Any] = {
        "schema": PROFILE_DEPENDENCY_STATEMENT_SCHEMA,
        "statement_type": PROFILE_DEPENDENCY_STATEMENT_TYPE,
        "profile_id": PROFILE_ID,
        "profile_version": profile_version,
        "profile_policy": policy,
        "expected_dependencies": [a["atom_id"] for a in atoms],
        "dependency_root": dependency_root,
        "dependency_root_envelope": envelope,
        "receipt_status": "eligible_for_local_cose_receipt",
        "non_claims": list(NON_CLAIMS),
    }
    h = compute_profile_dependency_statement_hash(statement)
    statement["statement_hash"] = h
    statement["profile_dependency_statement_hash"] = h  # compatibility/detail field
    return statement


def _continuity_state(
    artifact_root: str,
    current_root: str,
    old_atoms: list[dict[str, Any]],
    new_atoms: list[dict[str, Any]],
    replacements: list[dict[str, str]] | None = None,
):
    replacements = replacements or []
    old_ids = {a["atom_id"] for a in old_atoms}
    new_ids = {a["atom_id"] for a in new_atoms}
    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    if artifact_root == current_root:
        return "ALIGNED", added, removed, replacements
    if replacements:
        return "SUPERSEDED", added, removed, replacements
    return "NEEDS_REVIEW", added, removed, replacements


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _receipt_statement(statement: dict[str, Any], out: Path, log_path: Path, priv: Path, pub: Path, name: str, kid: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    signed = sign_statement(statement, private_key_path=priv, kid=kid)
    cose_path = out / f"{name}.cose-sign1.cbor"
    write_cose_artifact(signed, cose_path)
    receipt = register_signed_statement(log_path, cose_path=cose_path, statement=statement)
    recomputes = receipt["receipt_hash"] == compute_receipt_hash(receipt)
    verdict = verify_local_receipt(receipt, cose_path=cose_path, statement=statement, public_key_path=pub)
    if not (recomputes and verdict.get("ok")):
        raise RuntimeError(f"receipt failed verification for {name}: {verdict}")
    return cose_path, receipt, verdict


def _build_atoms() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    art19 = _verbatim_atom(
        "eu.dora.2022-2554.article-19-1.first-sentence",
        "32022R2554",
        "http://data.europa.eu/eli/reg/2022/2554/art_19",
        "Article 19(1), first subparagraph, first sentence",
        ART19_1_FIRST_SENTENCE,
        "base_obligation",
        "required",
    )
    atom301 = _summary_atom(
        "eu.dora.2025-301.major-incident-content-time-limits",
        "32025R0301",
        "http://data.europa.eu/eli/reg_del/2025/301/oj",
        "Specifies content and time limits for the initial notification, intermediate report and final report on major ICT-related incidents.",
        "content_and_time_limits",
        "required",
    )
    atom302_summary = _summary_atom(
        "eu.dora.2025-302.forms-templates-procedures",
        "32025R0302",
        "http://data.europa.eu/eli/reg_impl/2025/302/oj",
        "Lays down standard forms, templates and procedures for reporting major ICT-related incidents; binds to content in 2025/301 Articles 2 to 4.",
        "forms_templates_procedures",
        "required",
    )
    atom302_art1 = _verbatim_atom(
        "eu.dora.2025-302.article-1-1-a.initial-notification-template-fields",
        "32025R0302",
        "http://data.europa.eu/eli/reg_impl/2025/302/oj",
        "Article 1(1), opening sentence and point (a)",
        REG302_ART1_1_A,
        "initial_notification_template_field_completion_rule",
        "required",
    )
    return art19, atom301, atom302_summary, atom302_art1


def run(workdir: Path | None = None, verbose: bool = False) -> int:
    out = Path("actproof-demo-output") / "dora-301-302-continuity" if workdir is None else Path(workdir)
    out.mkdir(parents=True, exist_ok=True)

    def v(msg: str) -> None:
        if verbose:
            print(msg)

    v(_RULE)
    v("ActProof Events: source dependency continuity demo")
    v("Worked example: DORA 301 -> 302")
    v("Local pilot. No network, no external service, no data leaves this machine.")
    v(_RULE)

    art19, atom301, atom302_summary, atom302_art1 = _build_atoms()
    v("\n[1] Build source atoms")
    v(f"    Article 19(1) 1st sentence (verbatim): {_short(art19['official_text_sha256'])}")
    v(f"    2025/301 (summary descriptor)        : {atom301['source_role']}")
    v(f"    2025/302 instrument (summary)        : {atom302_summary['source_role']}")
    v(f"    2025/302 Art.1(1)(a) (verbatim)      : {_short(atom302_art1['official_text_sha256'])}")

    v1_atoms = [art19, atom301]
    v2_atoms = [art19, atom301, atom302_summary, atom302_art1]
    stmt_v1 = _profile_dependency_statement("v1", "Article 19(1) + 2025/301.", v1_atoms)
    stmt_v2 = _profile_dependency_statement(
        "v2", "2025/302 is a required implementation dependency for this reporting profile.", v2_atoms
    )
    v("\n[2] Build typed profile-dependency statements")
    v(f"    v1 dependency_root: {_short(stmt_v1['dependency_root'])}")
    v(f"    v2 dependency_root: {_short(stmt_v2['dependency_root'])}")

    keys = write_dev_keypair(out, kid="actproof-continuity-ed25519")
    priv = Path(keys.get("private_key_path", out / "source-atom.dev.private-key.pem"))
    pub = Path(keys.get("public_key_path", out / "source-atom.dev.public-key.pem"))
    log_path = out / "local-log.json"
    if log_path.exists():
        log_path.unlink()
    init_local_log(log_path, label="dora 301-302 continuity demo local pilot")

    v("\n[3] COSE-sign, register and verify profile-dependency statements")
    v1_cose, v1_receipt, v1_verdict = _receipt_statement(stmt_v1, out, log_path, priv, pub, "profile-dependency.v1", "actproof-continuity-ed25519")
    v2_cose, v2_receipt, v2_verdict = _receipt_statement(stmt_v2, out, log_path, priv, pub, "profile-dependency.v2", "actproof-continuity-ed25519")
    v(f"    v1 receipt verified: {v1_verdict.get('ok')} ({v1_verdict.get('reason')})")
    v(f"    v2 receipt verified: {v2_verdict.get('ok')} ({v2_verdict.get('reason')})")

    v("\n[4] Optional substrate check: COSE receipt over package catalogue source-atom statement")
    source_statement = build_source_atom_statement(CATALOGUE_ACT, CATALOGUE_ATOM)
    source_cose, source_receipt, source_verdict = _receipt_statement(source_statement, out, log_path, priv, pub, "source-atom", "actproof-continuity-ed25519")
    v(f"    source-atom receipt verified: {source_verdict.get('ok')} ({source_verdict.get('reason')})")

    artifact_body = {
        "artifact_id": "bank-x.dora.major-incident-reporting-form.v1",
        "artifact_kind": "example_internal_reporting_form",
        "relied_on_profile": PROFILE_ID,
        "relied_on_profile_version": "v1",
    }
    artifact = {
        "record_type": "actproof.demo.downstream_binding.v1",
        "binding_status": "not_a_receipt",
        "note": "Downstream binding record. It binds an example artifact to the receipted profile-dependency statement it relied on at build time.",
        "artifact": artifact_body,
        "artifact_sha256": canonical_json_sha256(artifact_body),
        "relied_on_dependency_root": stmt_v1["dependency_root"],
        "relied_on_profile_dependency_statement_hash": stmt_v1["statement_hash"],
        "relied_on_profile_dependency_receipt_hash": v1_receipt["receipt_hash"],
    }
    artifact["downstream_binding_record_hash"] = canonical_json_sha256(artifact)
    v("\n[5] Bind downstream artifact to the receipted v1 profile-dependency statement")
    v(f"    bound to v1 statement hash: {_short(stmt_v1['statement_hash'])}")
    v(f"    bound to v1 receipt hash  : {_short(v1_receipt['receipt_hash'])}")

    state, added, removed, replaced = _continuity_state(
        artifact["relied_on_dependency_root"], stmt_v2["dependency_root"], v1_atoms, v2_atoms
    )
    v("\n[6] Continuity check: bound root vs current receipted profile root")
    v(f"    artifact relied on root : {_short(artifact['relied_on_dependency_root'])}")
    v(f"    current profile root    : {_short(stmt_v2['dependency_root'])}")
    v(f"    result                  : {state}")
    if added:
        v(f"    added since binding     : {', '.join(added)}")

    _write_artifacts(
        out, v2_atoms, stmt_v1, stmt_v2, artifact, source_statement, source_receipt,
        v1_receipt, v2_receipt, state, added, removed, replaced
    )

    if verbose:
        print("\n" + _RULE)
    print("ActProof source-dependency continuity demo")
    print("Worked example: DORA 301 -> 302")
    print()
    print("Bound artifact:")
    print("  bank-x.dora.major-incident-reporting-form.v1")
    print()
    print("Bound source basis:")
    print("  DORA Article 19(1) + EU 2025/301")
    print()
    print("Current source basis:")
    print("  DORA Article 19(1) + EU 2025/301 + EU 2025/302")
    print()
    print("Result:")
    print(f"  {state}")
    print()
    print("Meaning:")
    print("  The artifact relied on an older receipted source-dependency statement.")
    print("  ActProof does not determine compliance or legal sufficiency.")
    print()
    print("Receipts:")
    print("  Verified local COSE receipts for profile-dependency v1 and v2 statements.")
    print("  Optional source-atom receipt also verified as substrate evidence.")
    print()
    print("Artifacts:")
    print(f"  {out.resolve()}")
    if not verbose:
        print("\nRun with --verbose to see hashes, receipt verification and object paths.")
    return 0


def _write_artifacts(
    out: Path,
    atoms: list[dict[str, Any]],
    stmt_v1: dict[str, Any],
    stmt_v2: dict[str, Any],
    artifact: dict[str, Any],
    source_statement: dict[str, Any],
    source_receipt: dict[str, Any],
    v1_receipt: dict[str, Any],
    v2_receipt: dict[str, Any],
    state: str,
    added: list[str],
    removed: list[str],
    replaced: list[dict[str, str]],
) -> None:
    for sub in ("source-atoms", "profiles", "statements", "downstream-binding", "receipts", "continuity"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    for a in atoms:
        _write_json(out / "source-atoms" / (a["atom_id"].replace(".", "-") + ".source-atom.json"), a)
    for v, stmt, receipt in (("v1", stmt_v1, v1_receipt), ("v2", stmt_v2, v2_receipt)):
        _write_json(out / "profiles" / f"dora-incident-reporting-profile.{v}.json", {
            "profile_id": PROFILE_ID,
            "profile_version": v,
            "expected_dependencies": stmt["expected_dependencies"],
            "dependency_root": stmt["dependency_root"],
            "profile_dependency_statement_hash": stmt["statement_hash"],
            "profile_dependency_receipt_hash": receipt["receipt_hash"],
        })
        _write_json(out / "statements" / f"profile-dependency-statement.{v}.json", stmt)
        _write_json(out / "receipts" / f"profile-dependency.{v}.receipt.json", receipt)
    _write_json(out / "downstream-binding" / "bank-x-reporting-form.binding.v1.json", artifact)
    _write_json(out / "source-atom.statement.json", source_statement)
    _write_json(out / "receipts" / "source-atom.receipt.json", source_receipt)

    assessment = {
        "schema": "actproof.demo.continuity_assessment.v1",
        "artifact_id": artifact["artifact"]["artifact_id"],
        "artifact_relied_on_root": artifact["relied_on_dependency_root"],
        "artifact_relied_on_statement_hash": artifact["relied_on_profile_dependency_statement_hash"],
        "artifact_relied_on_receipt_hash": artifact["relied_on_profile_dependency_receipt_hash"],
        "current_profile_root": stmt_v2["dependency_root"],
        "current_profile_statement_hash": stmt_v2["statement_hash"],
        "current_profile_receipt_hash": v2_receipt["receipt_hash"],
        "roots_match": artifact["relied_on_dependency_root"] == stmt_v2["dependency_root"],
        "continuity_state": state,
        "added_dependencies": added,
        "removed_dependencies": removed,
        "replacements": replaced,
        "legal_conclusion": "not_assessed",
        "meaning": "The artifact relied on an older receipted source-dependency statement. Current reliance needs review against the current receipted profile statement.",
        "boundary": "ActProof does not determine compliance or legal sufficiency.",
    }
    _write_json(out / "continuity" / "continuity-check.v1-to-v2.json", assessment)
    (out / "continuity" / "continuity-check.txt").write_text(
        "Result: %s\n\nThe downstream binding was created against the v1 receipted dependency root.\n"
        "The current v2 receipted dependency root adds EU 2025/302 dependencies.\n"
        "ActProof shows source-basis movement only; compliance is not assessed.\n" % state,
        encoding="utf-8",
    )
    _write_json(out / "manifest.json", {
        "schema": "actproof.demo.manifest.v1",
        "demo": "dora-301-302-continuity",
        "profile_id": PROFILE_ID,
        "continuity_state": state,
        "receipted_statements": [
            "profile-dependency-statement.v1.json",
            "profile-dependency-statement.v2.json",
            "source-atom.statement.json",
        ],
        "boundary": "Local reproducible worked example; not legal advice or production external SCITT registration.",
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m actproof_events demo dora-301-302-continuity")
    parser.add_argument("--out", default=None, help="Output directory for generated artifacts")
    parser.add_argument("--verbose", action="store_true", help="Print detailed hashes and receipt checks")
    args = parser.parse_args(argv)
    return run(workdir=Path(args.out) if args.out else None, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
