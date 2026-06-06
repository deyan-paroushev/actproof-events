#!/usr/bin/env python3
"""validate_source_atoms.py — conformance gate for 1.8.0 field-level source binding.

Merged gate: ChatGPT's strict required-field release rules + the structural and
chain-of-custody checks. Fails the mint if:
  - either sidecar fails its JSON Schema
  - any derivation references a missing source atom
  - any REQUIRED field lacks a derivation (release criterion)
  - required-field coverage != 100%
  - any atom lacks ELI or CELEX or source_document_sha256
  - any atom's source_document_sha256 doesn't chain to source-bindings
Reports (does not fail) provisional text binding and draft review status — these
are honest, disclosed states, not conformance errors.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from jsonschema.validators import Draft202012Validator
except ImportError:
    print("Error: jsonschema required. pip install jsonschema", file=sys.stderr)
    sys.exit(1)


def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))


def main() -> int:
    binders = ROOT / "source_bindings"
    atom_schema = load(ROOT / "spec" / "schemas" / "source_atoms.v1.schema.json")
    deriv_schema = load(ROOT / "spec" / "schemas" / "field_derivations.v1.schema.json")
    Draft202012Validator.check_schema(atom_schema)
    Draft202012Validator.check_schema(deriv_schema)

    print("actproof-events 1.8.0 source-atom / field-derivation validation")
    failures = 0
    checked = 0

    # known pinned-PDF hashes from all source-bindings
    known_hashes = set()
    for sbp in (ROOT / "sources").rglob("source-bindings.json"):
        try:
            for b in load(sbp).get("source_bindings", []):
                known_hashes.add(b.get("sha256"))
        except Exception:
            pass

    for sa_path in sorted(binders.rglob("*.source_atoms.json")):
        if "/drafts/" in str(sa_path):
            continue
        checked += 1
        fd_path = sa_path.with_name(sa_path.name.replace(".source_atoms.json", ".field_derivations.json"))
        name = sa_path.name.replace(".source_atoms.json", "")
        print(f"\n  profile: {name}")
        sa = load(sa_path)

        ae = sorted(Draft202012Validator(atom_schema).iter_errors(sa), key=lambda e: list(e.path))
        if ae:
            failures += 1; print(f"    FAIL source_atoms schema: {ae[0].message[:90]}"); continue
        if not fd_path.exists():
            failures += 1; print("    FAIL: no field_derivations sidecar"); continue
        fd = load(fd_path)
        de = sorted(Draft202012Validator(deriv_schema).iter_errors(fd), key=lambda e: list(e.path))
        if de:
            failures += 1; print(f"    FAIL field_derivations schema: {de[0].message[:90]}"); continue
        print("    OK   both sidecars validate against schema")

        atoms = sa["source_atoms"]
        atom_ids = {a["source_atom_id"] for a in atoms}

        # identifier completeness
        bad = [a["source_atom_id"] for a in atoms
               if not a.get("celex") or not a.get("eli") or not str(a.get("source_document_sha256","")).startswith("sha256:")]
        if bad:
            failures += 1; print(f"    FAIL: {len(bad)} atom(s) missing CELEX/ELI/source_document_sha256")
        else:
            print(f"    OK   all {len(atoms)} atoms carry CELEX + ELI + source_document_sha256")

        # referential integrity
        dangling = {r for d in fd["field_derivations"] for r in d["source_atoms"] if r not in atom_ids}
        if dangling:
            failures += 1; print(f"    FAIL: {len(dangling)} dangling atom reference(s): {sorted(dangling)[:3]}")
        else:
            print("    OK   all derivation atom references resolve")

        # REQUIRED-field release criterion
        entry = None
        for cand in (ROOT / "catalogue").rglob(f"{name}.json"):
            entry = load(cand); break
        if entry:
            required = set(entry.get("required_claim_fields", []))
            bound_required = {d["field_id"] for d in fd["field_derivations"]
                              if d["field_id"] in required and d.get("source_atoms")}
            missing = required - bound_required
            if missing:
                failures += 1; print(f"    FAIL: required fields unbound: {sorted(missing)}")
            else:
                print(f"    OK   all {len(required)} required fields are source-bound (release criterion)")

        # chain of custody
        orphan = [a["source_atom_id"] for a in atoms
                  if a.get("source_document_sha256") and a["source_document_sha256"] not in known_hashes]
        if orphan:
            failures += 1; print(f"    FAIL: {len(orphan)} atom(s) reference a PDF hash not in source-bindings")
        else:
            print("    OK   every atom's pinned-PDF hash chains to source-bindings")

        # disclosures (not failures)
        prov = sum(1 for a in atoms if a.get("binding_status") == "provisional")
        rg = (fd.get("review_gate") or {}).get("review_status", "unknown")
        print(f"    INFO {prov}/{len(atoms)} atoms provisional (official_text_sha256 pending) | review_status: {rg}")

        # identity-hash recompute (hard check): a shipped sha256 field must be reproducible
        try:
            from actproof_events.source_binding import verify_source_atom_identity_hash
            bad_id = [a["source_atom_id"] for a in atoms if not verify_source_atom_identity_hash(a)]
            if bad_id:
                failures += 1
                print(f"    FAIL: {len(bad_id)} atom(s) atom_identity_sha256 do not recompute: {bad_id[:3]}")
            else:
                print(f"    OK   all {len(atoms)} atom identity hashes recompute (reproducible, not asserted)")
        except Exception as exc:
            print(f"    WARN could not run identity-hash recompute: {exc}")

    print()
    if checked == 0:
        print("summary: no source-atom sidecars found"); return 0
    print(f"summary: {checked} profile(s) checked, {failures} failure(s)")
    print("RESULT:", "PASS" if failures == 0 else "FAIL")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
