#!/usr/bin/env python3
"""
compute_test_vectors.py

Generate OpenProof Events test vector files from raw manifest inputs.

A test vector binds a catalogue entry to a concrete example manifest and the
deterministic outputs any conforming verifier should produce: the canonical
manifest bytes, the manifest hash, the envelope, the envelope hash, and the
ARC-2 JCS note bytes that get anchored on-chain.

Usage:
    python scripts/compute_test_vectors.py \\
        <catalogue_entry.json> \\
        <manifest_input.json> \\
        <output_test_vectors.json>

The script is a pure function over its inputs. Given the same catalogue entry
and the same manifest input, it always produces the same test vector file
modulo metadata (test_vector_id derived from filename). All hash outputs are
byte-identical across runs and across machines.

Dependencies:
    pip install jcs
"""

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

try:
    import jcs
except ImportError:
    print(
        "Error: 'jcs' package required (RFC 8785 canonicalization). "
        "Install with: pip install jcs",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------- primitive helpers ----------

def sha256_hex(data: bytes) -> str:
    """Return the SHA-256 hex digest of the given bytes."""
    return hashlib.sha256(data).hexdigest()


def b64(data: bytes) -> str:
    """Standard base64 encoding (with padding) for transport in JSON."""
    return base64.b64encode(data).decode("ascii")


def b64url_no_pad(data: bytes) -> str:
    """Base64url encoding without padding, per the ARC-2 JCS note format."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def canonical(obj) -> bytes:
    """Return the RFC 8785 JCS-canonical UTF-8 bytes of a JSON-compatible object."""
    return jcs.canonicalize(obj)


# ---------- validation ----------

def validate_manifest(manifest: dict, catalogue: dict) -> list[str]:
    """
    Validate a raw manifest against a catalogue entry.

    Returns a list of error messages (empty list = manifest is valid for this entry).
    """
    errors: list[str] = []

    if manifest.get("act_type_id") != catalogue["act_type_id"]:
        errors.append(
            f"manifest act_type_id ({manifest.get('act_type_id')!r}) does not "
            f"match catalogue ({catalogue['act_type_id']!r})"
        )

    if manifest.get("catalogue_entry_version") != catalogue["version"]:
        errors.append(
            f"manifest catalogue_entry_version ({manifest.get('catalogue_entry_version')}) "
            f"does not match catalogue version ({catalogue['version']})"
        )

    claim_fields = manifest.get("claim_fields") or {}
    for required in catalogue["required_claim_fields"]:
        if required not in claim_fields:
            errors.append(f"required claim field missing: {required!r}")

    evidence_labels = {e.get("label") for e in (manifest.get("evidence") or [])}
    for required in catalogue["required_evidence_labels"]:
        if required not in evidence_labels:
            errors.append(f"required evidence label missing: {required!r}")

    return errors


# ---------- composition ----------

def compose_envelope(
    *,
    manifest_hash_hex: str,
    merkle_root_hex: str,
    act_type_id: str,
    catalogue_entry_version: int,
) -> dict:
    """
    Compose the envelope that wraps the manifest hash for on-chain anchoring.

    The envelope is hashed separately and its hash is also included in the
    ARC-2 note. This allows a verifier to confirm both the manifest binding
    and the envelope binding independently from the on-chain commitment.
    """
    return {
        "schema": "actproof.attestation_envelope.v1",
        "envelope_version": 1,
        "act_type_id": act_type_id,
        "catalogue_entry_version": catalogue_entry_version,
        "manifest_hash": manifest_hash_hex,
        "merkle_root": merkle_root_hex,
    }


def compose_arc2_note_inner(
    *,
    merkle_root_hex: str,
    envelope_hash_hex: str,
    act_type_id: str,
) -> dict:
    """
    Compose the inner JSON object of the ARC-2 JCS note in disclosed mode.

    Field meanings:
      r : merkle root (base64url no padding of merkle_root bytes)
      m : number of leaves in the merkle tree (1 for v2.0 single-leaf)
      t : type discriminator ("a" = attestation)
      q : Quoruna protocol version
      e : envelope hash (base64url no padding of envelope_hash bytes)
      s : act_type_id, present only in disclosed mode
    """
    return {
        "r": b64url_no_pad(bytes.fromhex(merkle_root_hex)),
        "m": 1,
        "t": "a",
        "q": "1",
        "e": b64url_no_pad(bytes.fromhex(envelope_hash_hex)),
        "s": act_type_id,
    }


# ---------- test vector assembly ----------

def compute_test_vector(
    *,
    catalogue: dict,
    raw_manifest: dict,
    test_vector_id: str,
) -> dict:
    """
    Produce a complete test vector from a catalogue entry and a raw manifest.

    Raises ValueError if the manifest fails validation against the catalogue.
    """
    errors = validate_manifest(raw_manifest, catalogue)
    if errors:
        raise ValueError(
            "Manifest validation failed:\n  - " + "\n  - ".join(errors)
        )

    # 1. Canonicalize and hash the manifest
    manifest_canonical = canonical(raw_manifest)
    manifest_hash_hex = sha256_hex(manifest_canonical)

    # 2. Merkle root for v2.0 single-leaf tree equals the manifest hash
    merkle_root_hex = manifest_hash_hex

    # 3. Compose, canonicalize, and hash the envelope
    envelope = compose_envelope(
        manifest_hash_hex=manifest_hash_hex,
        merkle_root_hex=merkle_root_hex,
        act_type_id=catalogue["act_type_id"],
        catalogue_entry_version=catalogue["version"],
    )
    envelope_canonical = canonical(envelope)
    envelope_hash_hex = sha256_hex(envelope_canonical)

    # 4. Compose and canonicalize the ARC-2 JCS note (disclosed mode)
    note_inner = compose_arc2_note_inner(
        merkle_root_hex=merkle_root_hex,
        envelope_hash_hex=envelope_hash_hex,
        act_type_id=catalogue["act_type_id"],
    )
    note_inner_canonical = canonical(note_inner)
    note_prefix = b"quoruna/v1:"
    note_full = note_prefix + note_inner_canonical

    return {
        "schema": "actproof.test_vector.v1",
        "test_vector_id": test_vector_id,
        "catalogue_act_type_id": catalogue["act_type_id"],
        "catalogue_entry_version": catalogue["version"],
        "raw_manifest": raw_manifest,
        "manifest_canonical_b64": b64(manifest_canonical),
        "manifest_canonical_byte_length": len(manifest_canonical),
        "manifest_hash_hex": manifest_hash_hex,
        "merkle_root_hex": merkle_root_hex,
        "envelope": envelope,
        "envelope_canonical_b64": b64(envelope_canonical),
        "envelope_canonical_byte_length": len(envelope_canonical),
        "envelope_hash_hex": envelope_hash_hex,
        "arc2_note": {
            "mode": "disclosed",
            "prefix": "quoruna/v1:",
            "inner_canonical_b64": b64(note_inner_canonical),
            "full_note_b64": b64(note_full),
            "full_note_byte_length": len(note_full),
            "field_meanings": {
                "r": "base64url-no-padding of merkle_root bytes",
                "m": "number of leaves in the merkle tree",
                "t": "type discriminator ('a' = attestation)",
                "q": "Quoruna protocol version",
                "e": "base64url-no-padding of envelope_hash bytes",
                "s": "act_type_id (disclosed mode only)",
            },
        },
        "reference_anchor": {
            "network": "algorand-testnet",
            "status": "placeholder",
            "txid": None,
            "round": None,
            "anchored_at": None,
            "anchoring_address": None,
            "verify_url_template": "https://testnet.allo.info/tx/{txid}",
            "instructions": (
                "Decode arc2_note.full_note_b64 to raw bytes. "
                "Anchor those bytes as the transaction note from any funded "
                "Algorand testnet account. After confirmation, populate "
                "txid, round, anchored_at, and anchoring_address."
            ),
        },
        "expected_verifier_output": "PASS",
        "verifier_checklist": [
            "Recompute manifest_hash_hex by canonicalizing raw_manifest with RFC 8785 JCS and applying SHA-256",
            "Confirm merkle_root_hex equals manifest_hash_hex (single-leaf tree convention for v2.0)",
            "Recompute envelope_hash_hex by canonicalizing envelope with RFC 8785 JCS and applying SHA-256",
            "Recompose arc2_note.full_note_b64 by concatenating the prefix bytes with the canonical note inner bytes",
            "Once reference_anchor.txid is populated, fetch the on-chain note and confirm byte-identical match",
        ],
    }


# ---------- entrypoint ----------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compute OpenProof Events test vectors from a catalogue entry and "
            "a manifest input. Deterministic: same inputs always produce the "
            "same hashes."
        )
    )
    parser.add_argument("catalogue_entry", help="Path to catalogue entry JSON file")
    parser.add_argument("manifest_input", help="Path to raw manifest JSON file (the test input)")
    parser.add_argument("output", help="Path to write the test vector JSON file")
    parser.add_argument(
        "--test-vector-id",
        help="Test vector identifier (default: derived from manifest_input filename)",
    )
    args = parser.parse_args()

    catalogue = json.loads(Path(args.catalogue_entry).read_text())
    raw_manifest = json.loads(Path(args.manifest_input).read_text())

    test_vector_id = args.test_vector_id or Path(args.manifest_input).stem

    test_vector = compute_test_vector(
        catalogue=catalogue,
        raw_manifest=raw_manifest,
        test_vector_id=test_vector_id,
    )

    Path(args.output).write_text(
        json.dumps(test_vector, indent=2, ensure_ascii=False) + "\n"
    )

    print(f"Test vector written to: {args.output}", file=sys.stderr)
    print(f"  catalogue:            {catalogue['act_type_id']}", file=sys.stderr)
    print(f"  manifest_hash:        {test_vector['manifest_hash_hex']}", file=sys.stderr)
    print(f"  envelope_hash:        {test_vector['envelope_hash_hex']}", file=sys.stderr)
    print(f"  note byte length:     {test_vector['arc2_note']['full_note_byte_length']}", file=sys.stderr)


if __name__ == "__main__":
    main()
