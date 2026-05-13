# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Advisa EOOD (UIC 206448172, Sofia, Bulgaria)
"""
salt_erasure: HMAC-SHA-256 keyed pseudonymization with cryptographic erasure.

A small standalone module implementing keyed pseudonymization of identifiers
in audit trails, with a key-erasure operation that converts pseudonymous data
into anonymized data per the European Data Protection Board's anonymization
framework.

Part of the OpenProof Events project. See README.md for full documentation,
security model, integration guidance, and limitations.

Quick example:

    from salt_erasure import SaltErasure, generate_salt

    salt = generate_salt()
    pseudonymizer = SaltErasure(salt=salt, salt_id="board-2026-06-16")

    pseudonym_a = pseudonymizer.pseudonymize("director_id_001")
    assert pseudonymizer.verify_link("director_id_001", pseudonym_a)

    pseudonymizer.erase()
    # pseudonymize() and verify_link() now raise SaltErasedError
"""
from __future__ import annotations

import ctypes
import hashlib
import hmac
import secrets
from typing import Final


__version__: Final[str] = "1.0.0"

__all__ = [
    "SALT_LENGTH_BYTES",
    "PSEUDONYM_LENGTH_BYTES",
    "SaltErasure",
    "SaltManager",
    "SaltErasedError",
    "UnknownSaltError",
    "generate_salt",
    "is_well_formed_pseudonym",
]


# Cryptographic parameters.
# 32-byte salt is the recommended HMAC-SHA-256 key length per RFC 2104.
# 32-byte pseudonym is the SHA-256 digest length.
SALT_LENGTH_BYTES: Final[int] = 32
PSEUDONYM_LENGTH_BYTES: Final[int] = 32


class SaltErasedError(Exception):
    """Raised when an operation is attempted on a SaltErasure instance whose
    salt has been erased."""


class UnknownSaltError(Exception):
    """Raised when a SaltManager is asked to operate on a salt identifier that
    has not been registered."""


def generate_salt() -> bytes:
    """Generate a fresh 32-byte salt from the OS cryptographic random source.

    Uses secrets.token_bytes, which delegates to os.urandom on Unix and
    BCryptGenRandom on Windows. Suitable for cryptographic key material.

    Returns:
        32 random bytes suitable for use as an HMAC-SHA-256 salt.
    """
    return secrets.token_bytes(SALT_LENGTH_BYTES)


def is_well_formed_pseudonym(value: object) -> bool:
    """Check that a value has the shape of an HMAC-SHA-256 pseudonym.

    Args:
        value: The candidate pseudonym to check.

    Returns:
        True if value is a bytes or bytearray of exactly 32 bytes,
        False otherwise.
    """
    return isinstance(value, (bytes, bytearray)) and len(value) == PSEUDONYM_LENGTH_BYTES


def _zero_bytes(buf: bytearray) -> None:
    """Best-effort overwrite of a bytearray buffer with zero bytes.

    Uses ctypes.memset against a buffer view where the platform supports it,
    falling back to a Python loop otherwise. Python's garbage collector may
    still retain copies of the original buffer briefly; for HSM-grade erasure
    semantics, consult the README's Security Model section.

    Args:
        buf: The bytearray to overwrite in place.
    """
    n = len(buf)
    if n == 0:
        return
    try:
        # Create a ctypes array view over the bytearray's underlying memory and
        # memset it to zero. The view shares memory with buf, so the memset
        # affects buf directly without copying.
        view = (ctypes.c_char * n).from_buffer(buf)
        ctypes.memset(view, 0, n)
    except (TypeError, ValueError):
        # Fall back to a pure-Python loop on platforms or interpreters where
        # ctypes-based memset cannot be applied to a bytearray.
        for i in range(n):
            buf[i] = 0


class SaltErasure:
    """A pseudonymizer bound to a single salt with explicit erasure semantics.

    Construct with a 32-byte salt and a human-readable salt identifier. Use
    pseudonymize() to convert identifiers to HMAC-SHA-256 pseudonyms. Use
    verify_link() to check whether a candidate identifier hashes to a given
    pseudonym under this salt. Use erase() to irreversibly destroy the salt;
    subsequent operations raise SaltErasedError.

    The salt_id field is a human-readable identifier for this salt cohort
    (for example, "board-meeting-2026-06-16" or "quarterly-cohort-2026Q2").
    It is intended to be recorded in audit logs and serialised receipts so
    that authorized parties can determine which salt cohort applies to
    verification operations.
    """

    __slots__ = ("_salt", "_salt_id", "_erased")

    def __init__(self, salt: bytes, salt_id: str) -> None:
        """Initialize with a 32-byte salt and a human-readable identifier.

        Args:
            salt: A 32-byte secret. Must be exactly SALT_LENGTH_BYTES long.
            salt_id: A non-empty human-readable identifier for this cohort.

        Raises:
            TypeError: If salt is not bytes or salt_id is not str.
            ValueError: If salt is not exactly 32 bytes or salt_id is empty.
        """
        if not isinstance(salt, (bytes, bytearray)):
            raise TypeError(
                f"salt must be bytes, got {type(salt).__name__}"
            )
        if not isinstance(salt_id, str):
            raise TypeError(
                f"salt_id must be str, got {type(salt_id).__name__}"
            )
        if len(salt) != SALT_LENGTH_BYTES:
            raise ValueError(
                f"salt must be exactly {SALT_LENGTH_BYTES} bytes, got {len(salt)}"
            )
        if not salt_id:
            raise ValueError("salt_id must be a non-empty string")

        # Store the salt as a bytearray so that erase() can overwrite it in
        # place. We copy the input rather than retaining a reference so that
        # the caller's view of their input buffer is not affected by erase().
        self._salt = bytearray(salt)
        self._salt_id = salt_id
        self._erased = False

    @property
    def salt_id(self) -> str:
        """The human-readable identifier for this salt cohort."""
        return self._salt_id

    @property
    def is_erased(self) -> bool:
        """True if the salt has been erased, False otherwise."""
        return self._erased

    def pseudonymize(self, identifier: str) -> bytes:
        """Compute the HMAC-SHA-256 pseudonym for an identifier.

        The identifier is UTF-8 encoded before hashing.

        Args:
            identifier: The identifier to pseudonymize.

        Returns:
            32-byte HMAC-SHA-256 output.

        Raises:
            SaltErasedError: If the salt has been erased.
            TypeError: If identifier is not a string.
        """
        if self._erased:
            raise SaltErasedError(
                f"Cannot pseudonymize: salt '{self._salt_id}' has been erased"
            )
        if not isinstance(identifier, str):
            raise TypeError(
                f"identifier must be str, got {type(identifier).__name__}"
            )
        return hmac.new(
            bytes(self._salt),
            identifier.encode("utf-8"),
            hashlib.sha256,
        ).digest()

    def verify_link(self, identifier: str, pseudonym: bytes) -> bool:
        """Check whether an identifier hashes to a given pseudonym under this salt.

        Uses hmac.compare_digest for constant-time comparison, preventing
        timing side channels from leaking information about partial matches.

        Args:
            identifier: The candidate identifier.
            pseudonym: The candidate pseudonym, expected to be 32 bytes.

        Returns:
            True if identifier hashes to pseudonym under this salt,
            False otherwise.

        Raises:
            SaltErasedError: If the salt has been erased.
            TypeError: If identifier is not a string or pseudonym is not bytes.
            ValueError: If pseudonym is not exactly 32 bytes.
        """
        if self._erased:
            raise SaltErasedError(
                f"Cannot verify_link: salt '{self._salt_id}' has been erased"
            )
        if not isinstance(identifier, str):
            raise TypeError(
                f"identifier must be str, got {type(identifier).__name__}"
            )
        if not isinstance(pseudonym, (bytes, bytearray)):
            raise TypeError(
                f"pseudonym must be bytes, got {type(pseudonym).__name__}"
            )
        if len(pseudonym) != PSEUDONYM_LENGTH_BYTES:
            raise ValueError(
                f"pseudonym must be exactly {PSEUDONYM_LENGTH_BYTES} bytes, "
                f"got {len(pseudonym)}"
            )
        computed = hmac.new(
            bytes(self._salt),
            identifier.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return hmac.compare_digest(computed, bytes(pseudonym))

    def erase(self) -> None:
        """Irreversibly destroy the salt.

        Overwrites the salt bytes with zeros via best-effort ctypes.memset
        and marks this instance as erased. Subsequent calls to pseudonymize()
        or verify_link() raise SaltErasedError.

        This operation is idempotent: calling erase() on an already-erased
        instance is a no-op and does not raise.

        Python's garbage collector may retain copies of the original salt
        bytes briefly. For HSM-grade erasure semantics, the salt must be
        held in an HSM rather than in process memory, and erasure must be
        triggered through the HSM's key-deletion API. This module implements
        the in-memory erasure semantics suitable for transient processes
        whose memory does not persist beyond the process lifetime.
        """
        if self._erased:
            return
        _zero_bytes(self._salt)
        self._erased = True

    def __repr__(self) -> str:
        status = "erased" if self._erased else "active"
        return f"SaltErasure(salt_id={self._salt_id!r}, status={status})"


class SaltManager:
    """A registry of multiple salts supporting salt rotation and selective erasure.

    Use register() to add salts under named identifiers, pseudonymize() and
    verify_link() to perform operations under a named salt, and erase() to
    irreversibly destroy a single named salt while leaving others intact.

    The manager does not persist salts across process lifetimes; in-memory
    state only. Operators integrating with persistent salt storage must wrap
    this class with their own load and save logic, ensuring that the storage
    layer supports irreversible erasure that mirrors erase() semantics here.
    """

    __slots__ = ("_salts",)

    def __init__(self) -> None:
        """Initialize an empty salt manager."""
        self._salts: dict[str, SaltErasure] = {}

    def register(self, salt_id: str, salt: bytes) -> None:
        """Register a salt under the given identifier.

        Args:
            salt_id: The identifier to use for this salt. Must not already
                     be registered (use a fresh identifier per rotation).
            salt: A 32-byte secret.

        Raises:
            TypeError: If salt_id is not str.
            ValueError: If salt_id is already registered, or if the
                        SaltErasure constructor rejects the salt.
        """
        if not isinstance(salt_id, str):
            raise TypeError(
                f"salt_id must be str, got {type(salt_id).__name__}"
            )
        if salt_id in self._salts:
            raise ValueError(
                f"salt_id '{salt_id}' is already registered. "
                f"Use a fresh identifier per salt cohort."
            )
        # SaltErasure constructor validates salt length, type, and salt_id.
        self._salts[salt_id] = SaltErasure(salt=salt, salt_id=salt_id)

    def pseudonymize(self, salt_id: str, identifier: str) -> bytes:
        """Pseudonymize an identifier using the named salt.

        Args:
            salt_id: The identifier of the salt cohort to use.
            identifier: The identifier to pseudonymize.

        Returns:
            32-byte HMAC-SHA-256 output.

        Raises:
            UnknownSaltError: If salt_id is not registered.
            SaltErasedError: If the named salt has been erased.
        """
        self._require_known(salt_id)
        return self._salts[salt_id].pseudonymize(identifier)

    def verify_link(self, salt_id: str, identifier: str, pseudonym: bytes) -> bool:
        """Verify linkage between an identifier and pseudonym under the named salt.

        Args:
            salt_id: The identifier of the salt cohort to use.
            identifier: The candidate identifier.
            pseudonym: The candidate pseudonym (32 bytes).

        Returns:
            True if identifier hashes to pseudonym under the named salt.

        Raises:
            UnknownSaltError: If salt_id is not registered.
            SaltErasedError: If the named salt has been erased.
        """
        self._require_known(salt_id)
        return self._salts[salt_id].verify_link(identifier, pseudonym)

    def erase(self, salt_id: str) -> None:
        """Erase the named salt while leaving other salts untouched.

        Idempotent: erasing an already-erased salt is a no-op.

        Args:
            salt_id: The identifier of the salt cohort to erase.

        Raises:
            UnknownSaltError: If salt_id is not registered.
        """
        self._require_known(salt_id)
        self._salts[salt_id].erase()

    def is_erased(self, salt_id: str) -> bool:
        """Check whether the named salt has been erased.

        Args:
            salt_id: The identifier of the salt cohort to check.

        Returns:
            True if the named salt has been erased, False if still active.

        Raises:
            UnknownSaltError: If salt_id is not registered.
        """
        self._require_known(salt_id)
        return self._salts[salt_id].is_erased

    def list_active_salt_ids(self) -> list[str]:
        """Return the identifiers of salts not yet erased.

        Returns:
            A list of salt identifiers for which is_erased is False.
            The order matches insertion order.
        """
        return [sid for sid, s in self._salts.items() if not s.is_erased]

    def list_all_salt_ids(self) -> list[str]:
        """Return all registered salt identifiers, including erased ones.

        Returns:
            A list of all registered salt identifiers. The order matches
            insertion order.
        """
        return list(self._salts.keys())

    def _require_known(self, salt_id: str) -> None:
        """Raise UnknownSaltError if salt_id is not registered."""
        if salt_id not in self._salts:
            raise UnknownSaltError(f"salt_id '{salt_id}' is not registered")

    def __repr__(self) -> str:
        active = len(self.list_active_salt_ids())
        total = len(self._salts)
        return f"SaltManager(active={active}, total={total})"
