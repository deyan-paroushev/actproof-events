# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""Local COSE_Sign1 prototype for ActProof source-atom statements.

This module implements the 2.7.0 local signing prototype for the
``actproof/source-atom/v1`` statement profile introduced in 2.6.0. It produces
and verifies a compact COSE_Sign1-shaped CBOR object using Ed25519 / COSE EdDSA
(alg -8). It intentionally does not register statements with SCITT and does not
produce COSE receipts.

The signature proves only that a key signed the canonical hash commitment for a
specific source-atom statement. It does not prove legal correctness, external
review, SCITT transparency-service registration, regulatory acceptance or
compliance.
"""
from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from actproof_events import __version__
from actproof_events.scitt_profile import (
    CANONICALIZATION,
    COSE_TYP,
    HASH_ALGORITHM,
    SCITT_SOURCE_ATOM_STATEMENT_TYPE,
    compute_statement_hash,
    load_json,
    validate_source_atom_statement,
)
from actproof_events.statement_profiles import (
    compute_statement_hash_for_type,
    validate_statement,
)

_INSTALL_HINT = (
    "COSE signing requires the optional extra. Install it with:\n"
    '    pip install "actproof-events[cose-signing]"'
)


def _require_crypto():
    """Import the cryptography primitives lazily.

    Keeps the base package import-safe with zero runtime dependencies: importing
    this module never requires cryptography; only sign/verify/keygen calls do,
    and they fail with a clear install hint if the extra is absent.
    """
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey,
        )
    except ImportError as exc:  # pragma: no cover - exercised via message
        raise ImportError(_INSTALL_HINT) from exc
    return InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey

COSE_SOURCE_ATOM_SIGNING_SCHEMA = "actproof.cose_source_atom_sign1.v1"
COSE_SOURCE_ATOM_VERIFICATION_SCHEMA = "actproof.cose_source_atom_verification.v1"
COSE_SIGN1_TAG = 18
COSE_HEADER_ALG = 1
COSE_HEADER_KID = 4
COSE_HEADER_TYP = 16  # RFC 9596 COSE typ header parameter
COSE_ALG_EDDSA = -8
PAYLOAD_FORMAT = "actproof.statement_hash.utf8.v1"
COSE_STATUS_SIGNED_LOCAL = "signed_local_cose_sign1_prototype"
SCITT_REGISTRATION_STATUS = "not_registered"
SCITT_RECEIPT_STATUS = "no_receipt_in_2_7_0"

NON_CLAIMS = [
    "COSE signature verification proves only that the statement hash was signed by the supplied key.",
    "The signature does not prove legal correctness, compliance certification, bank approval or supervisory approval.",
    "The signed statement is not registered with a SCITT Transparency Service in 2.7.0.",
    "No SCITT receipt is produced or verified in 2.7.0.",
    "Draft atom statements should not be treated as reviewed public trust artifacts.",
]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Minimal deterministic CBOR implementation for the COSE structures we emit.
# This avoids adding a mandatory runtime dependency and keeps the prototype
# inspectable. It supports ints, bytes, text, arrays, maps and tag 18.
# ---------------------------------------------------------------------------

def _enc_len(major: int, n: int) -> bytes:
    if n < 0:
        raise ValueError("CBOR length cannot be negative")
    prefix = major << 5
    if n < 24:
        return bytes([prefix | n])
    if n < 256:
        return bytes([prefix | 24, n])
    if n < 65536:
        return bytes([prefix | 25]) + n.to_bytes(2, "big")
    if n < 4294967296:
        return bytes([prefix | 26]) + n.to_bytes(4, "big")
    return bytes([prefix | 27]) + n.to_bytes(8, "big")


def cbor_encode(value: Any) -> bytes:
    if isinstance(value, bool):
        return b"\xf5" if value else b"\xf4"
    if value is None:
        return b"\xf6"
    if isinstance(value, int):
        if value >= 0:
            return _enc_len(0, value)
        return _enc_len(1, -1 - value)
    if isinstance(value, bytes):
        return _enc_len(2, len(value)) + value
    if isinstance(value, str):
        data = value.encode("utf-8")
        return _enc_len(3, len(data)) + data
    if isinstance(value, (list, tuple)):
        return _enc_len(4, len(value)) + b"".join(cbor_encode(x) for x in value)
    if isinstance(value, dict):
        # COSE maps use integer/text keys. Deterministic order by encoded key.
        items = sorted(value.items(), key=lambda kv: cbor_encode(kv[0]))
        return _enc_len(5, len(items)) + b"".join(cbor_encode(k) + cbor_encode(v) for k, v in items)
    if isinstance(value, CBORTag):
        return cbor_encode_tag(value.tag, value.value)
    raise TypeError(f"unsupported CBOR value: {type(value)!r}")


@dataclass(frozen=True)
class CBORTag:
    tag: int
    value: Any


def cbor_encode_tag(tag: int, value: Any) -> bytes:
    return _enc_len(6, tag) + cbor_encode(value)


class _CBORDecoder:
    def __init__(self, data: bytes):
        self.data = data
        self.i = 0

    def _read(self, n: int) -> bytes:
        if self.i + n > len(self.data):
            raise ValueError("truncated CBOR")
        out = self.data[self.i : self.i + n]
        self.i += n
        return out

    def _arg(self, ai: int) -> int:
        if ai < 24:
            return ai
        if ai == 24:
            return self._read(1)[0]
        if ai == 25:
            return int.from_bytes(self._read(2), "big")
        if ai == 26:
            return int.from_bytes(self._read(4), "big")
        if ai == 27:
            return int.from_bytes(self._read(8), "big")
        raise ValueError("indefinite-length CBOR is not supported")

    def decode(self) -> Any:
        b = self._read(1)[0]
        major, ai = b >> 5, b & 0x1F
        n = self._arg(ai) if major in {0, 1, 2, 3, 4, 5, 6} else ai
        if major == 0:
            return n
        if major == 1:
            return -1 - n
        if major == 2:
            return self._read(n)
        if major == 3:
            return self._read(n).decode("utf-8")
        if major == 4:
            return [self.decode() for _ in range(n)]
        if major == 5:
            return {self.decode(): self.decode() for _ in range(n)}
        if major == 6:
            return CBORTag(n, self.decode())
        if major == 7:
            if n == 20:
                return False
            if n == 21:
                return True
            if n == 22:
                return None
        raise ValueError("unsupported CBOR simple/float value")


def cbor_decode(data: bytes) -> Any:
    dec = _CBORDecoder(data)
    value = dec.decode()
    if dec.i != len(data):
        raise ValueError("trailing bytes after CBOR object")
    return value


# ---------------------------------------------------------------------------
# Key handling
# ---------------------------------------------------------------------------

def generate_ed25519_keypair() -> tuple[bytes, bytes]:
    _InvalidSignature, serialization, Ed25519PrivateKey, _Pub = _require_crypto()
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def write_dev_keypair(out_dir: str | Path, *, kid: str = "actproof-dev-ed25519-001") -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    priv, pub = generate_ed25519_keypair()
    priv_path = out / "source-atom.dev.private-key.pem"
    pub_path = out / "source-atom.dev.public-key.pem"
    meta_path = out / "source-atom.dev-key.metadata.json"
    priv_path.write_bytes(priv)
    pub_path.write_bytes(pub)
    meta = {
        "schema": "actproof.cose_dev_keypair_metadata.v1",
        "kid": kid,
        "algorithm": "Ed25519 / COSE EdDSA (-8)",
        "purpose": "development-only local COSE signing prototype for actproof/source-atom/v1 statements",
        "warning": "Do not use this generated keypair for production trust artifacts.",
        "private_key_path": str(priv_path),
        "public_key_path": str(pub_path),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def load_private_key(path: str | Path):
    _InvalidSignature, serialization, Ed25519PrivateKey, _Pub = _require_crypto()
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("2.7.0 prototype supports Ed25519 private keys only")
    return key


def load_public_key(path: str | Path):
    _InvalidSignature, serialization, _Priv, Ed25519PublicKey = _require_crypto()
    key = serialization.load_pem_public_key(Path(path).read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("2.7.0 prototype supports Ed25519 public keys only")
    return key


def _kid_bytes(kid: str) -> bytes:
    return kid.encode("utf-8")


def _payload_for_statement(statement: dict[str, Any]) -> bytes:
    """Return the detached COSE payload for any supported statement type."""
    errors = validate_statement(statement)
    if errors:
        raise ValueError("invalid statement: " + "; ".join(errors))
    stored = statement.get("statement_hash")
    recomputed = compute_statement_hash_for_type(statement)
    if stored != recomputed:
        raise ValueError(f"statement_hash mismatch: stored {stored}, recomputed {recomputed}")
    return str(stored).encode("utf-8")


def _protected_header(kid: str | None = None, *, cose_typ: str = COSE_TYP) -> dict[Any, Any]:
    # kid is kept unprotected so relying parties can inspect it without parsing
    # protected bstr. Protected headers bind alg and typ to the signature.
    return {
        COSE_HEADER_ALG: COSE_ALG_EDDSA,
        COSE_HEADER_TYP: cose_typ,
    }


def _unprotected_header(kid: str, *, profile: str = "actproof.cose_statement_sign1.v1") -> dict[Any, Any]:
    return {
        COSE_HEADER_KID: _kid_bytes(kid),
        "actproof-profile": profile,
        "payload-format": PAYLOAD_FORMAT,
        "scitt-registration-status": SCITT_REGISTRATION_STATUS,
    }


def _sig_structure(protected_bstr: bytes, payload: bytes, external_aad: bytes = b"") -> bytes:
    return cbor_encode(["Signature1", protected_bstr, external_aad, payload])


def sign_statement(
    statement: dict[str, Any],
    *,
    private_key_path: str | Path,
    kid: str = "actproof-dev-ed25519-001",
    cose_typ: str | None = None,
) -> dict[str, Any]:
    """Sign any supported ActProof statement profile.

    The COSE payload is the UTF-8 ``statement_hash`` string. The verifier must
    supply the statement JSON and recompute the hash before verifying the
    signature. This keeps the object small while preserving a deterministic
    commitment to the statement content.
    """
    payload = _payload_for_statement(statement)
    typ = cose_typ or str(statement.get("statement_type") or COSE_TYP)
    protected = _protected_header(cose_typ=typ)
    protected_bstr = cbor_encode(protected)
    profile = "actproof.cose_source_atom_sign1.v1" if statement.get("statement_type") == SCITT_SOURCE_ATOM_STATEMENT_TYPE else "actproof.cose_statement_sign1.v1"
    unprotected = _unprotected_header(kid, profile=profile)
    to_sign = _sig_structure(protected_bstr, payload)
    key = load_private_key(private_key_path)
    signature = key.sign(to_sign)
    cose_obj = CBORTag(COSE_SIGN1_TAG, [protected_bstr, unprotected, payload, signature])
    cose_bytes = cbor_encode(cose_obj)
    return {
        "schema": COSE_SOURCE_ATOM_SIGNING_SCHEMA if statement.get("statement_type") == SCITT_SOURCE_ATOM_STATEMENT_TYPE else "actproof.cose_statement_sign1.v1",
        "statement_type": statement.get("statement_type"),
        "statement_hash": statement.get("statement_hash"),
        "statement_subject": statement.get("subject", {}),
        "cose_status": COSE_STATUS_SIGNED_LOCAL,
        "cose_sign1_tag": COSE_SIGN1_TAG,
        "cose_alg": "Ed25519 / COSE EdDSA (-8)",
        "cose_typ": typ,
        "kid": kid,
        "payload_format": PAYLOAD_FORMAT,
        "payload_sha256": sha256_bytes(payload),
        "signature_sha256": sha256_bytes(signature),
        "cose_sha256": sha256_bytes(cose_bytes),
        "cose_base64url": base64.urlsafe_b64encode(cose_bytes).decode("ascii").rstrip("="),
        "scitt_registration_status": SCITT_REGISTRATION_STATUS,
        "scitt_receipt_status": SCITT_RECEIPT_STATUS,
        "package": {"name": "actproof-events", "version": __version__},
        "non_claims": list(NON_CLAIMS),
    }


def sign_source_atom_statement(
    statement: dict[str, Any],
    *,
    private_key_path: str | Path,
    kid: str = "actproof-dev-ed25519-001",
) -> dict[str, Any]:
    """Sign a source-atom statement and return COSE bytes + metadata."""
    return sign_statement(statement, private_key_path=private_key_path, kid=kid, cose_typ=COSE_TYP)

def write_cose_artifact(signing_result: dict[str, Any], out_path: str | Path) -> None:
    b64 = signing_result.get("cose_base64url")
    if not isinstance(b64, str):
        raise ValueError("signing_result missing cose_base64url")
    padding = "=" * (-len(b64) % 4)
    data = base64.urlsafe_b64decode(b64 + padding)
    Path(out_path).write_bytes(data)


def write_json(value: Any, path: str | Path, *, compact: bool = False) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=False, separators=(",", ":") if compact else None, indent=None if compact else 2) + "\n",
        encoding="utf-8",
    )


def load_cose_sign1(path: str | Path) -> dict[str, Any]:
    data = Path(path).read_bytes()
    decoded = cbor_decode(data)
    if not isinstance(decoded, CBORTag) or decoded.tag != COSE_SIGN1_TAG:
        raise ValueError("COSE object must be tag 18 / COSE_Sign1")
    value = decoded.value
    if not (isinstance(value, list) and len(value) == 4):
        raise ValueError("COSE_Sign1 value must be a 4-item array")
    protected_bstr, unprotected, payload, signature = value
    if not isinstance(protected_bstr, bytes) or not isinstance(unprotected, dict) or not isinstance(payload, bytes) or not isinstance(signature, bytes):
        raise ValueError("invalid COSE_Sign1 structure")
    protected = cbor_decode(protected_bstr)
    if not isinstance(protected, dict):
        raise ValueError("protected header must decode to a map")
    return {
        "cose_bytes": data,
        "protected_bstr": protected_bstr,
        "protected": protected,
        "unprotected": unprotected,
        "payload": payload,
        "signature": signature,
    }


def verify_cose_statement(
    cose_path: str | Path,
    *,
    public_key_path: str | Path,
    statement: dict[str, Any],
    expected_cose_typ: str | None = None,
) -> dict[str, Any]:
    """Verify a local COSE_Sign1 prototype against any supported statement JSON."""
    result_base: dict[str, Any] = {
        "schema": COSE_SOURCE_ATOM_VERIFICATION_SCHEMA if statement.get("statement_type") == SCITT_SOURCE_ATOM_STATEMENT_TYPE else "actproof.cose_statement_verification.v1",
        "statement_type": statement.get("statement_type"),
        "statement_hash": statement.get("statement_hash"),
        "cose_typ": None,
        "signature_valid": False,
        "statement_hash_matches": False,
        "payload_matches_statement_hash": False,
        "scitt_registration_status": SCITT_REGISTRATION_STATUS,
        "receipt_present": False,
        "trust_boundary": "local COSE_Sign1 signature verification only; no external SCITT transparency-service receipt in this release",
        "non_claims": list(NON_CLAIMS),
    }
    statement_errors = validate_statement(statement)
    if statement_errors:
        result_base.update({"ok": False, "reason": "invalid_statement", "errors": statement_errors})
        return result_base
    recomputed = compute_statement_hash_for_type(statement)
    result_base["statement_hash_matches"] = recomputed == statement.get("statement_hash")
    if not result_base["statement_hash_matches"]:
        result_base.update({"ok": False, "reason": "statement_hash_mismatch", "recomputed_statement_hash": recomputed})
        return result_base

    try:
        cose = load_cose_sign1(cose_path)
    except Exception as exc:
        result_base.update({"ok": False, "reason": "invalid_cose", "error": str(exc)})
        return result_base

    protected = cose["protected"]
    result_base["cose_typ"] = protected.get(COSE_HEADER_TYP)
    result_base["kid"] = (cose["unprotected"].get(COSE_HEADER_KID) or b"").decode("utf-8", errors="replace")
    result_base["payload_sha256"] = sha256_bytes(cose["payload"])
    result_base["cose_sha256"] = sha256_bytes(cose["cose_bytes"])

    expected_payload = str(statement.get("statement_hash")).encode("utf-8")
    payload_ok = cose["payload"] == expected_payload
    result_base["payload_matches_statement_hash"] = payload_ok
    if protected.get(COSE_HEADER_ALG) != COSE_ALG_EDDSA:
        result_base.update({"ok": False, "reason": "unsupported_alg", "alg": protected.get(COSE_HEADER_ALG)})
        return result_base
    if expected_cose_typ is not None and protected.get(COSE_HEADER_TYP) != expected_cose_typ:
        result_base.update({"ok": False, "reason": "unexpected_cose_typ", "typ": protected.get(COSE_HEADER_TYP)})
        return result_base
    if not payload_ok:
        result_base.update({"ok": False, "reason": "payload_statement_hash_mismatch"})
        return result_base

    to_verify = _sig_structure(cose["protected_bstr"], cose["payload"])
    InvalidSignature, _ser, _Priv, _Pub = _require_crypto()
    key = load_public_key(public_key_path)
    try:
        key.verify(cose["signature"], to_verify)
        result_base["signature_valid"] = True
        result_base.update({"ok": True, "reason": "signature_valid_local_only"})
    except InvalidSignature:
        result_base.update({"ok": False, "reason": "invalid_signature"})
    return result_base


def verify_cose_source_atom_statement(
    cose_path: str | Path,
    *,
    public_key_path: str | Path,
    statement: dict[str, Any],
) -> dict[str, Any]:
    """Verify a local COSE_Sign1 prototype against a source-atom statement JSON."""
    return verify_cose_statement(cose_path, public_key_path=public_key_path, statement=statement, expected_cose_typ=COSE_TYP)
