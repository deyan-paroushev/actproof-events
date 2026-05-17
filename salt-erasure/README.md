# Salt Erasure

**A cryptographic primitive for pseudonymized governance evidence with deferred unlinkability.**

Salt-erasure is a small standalone module that provides keyed pseudonymization of identifiers in audit trails, with a key-erasure operation that converts pseudonymous data into anonymized data per the European Data Protection Board's anonymization framework. The module is published under Apache License 2.0 and is intended to be drop-in usable in any system that needs to record verifiable governance evidence containing identifier references while preserving the option to make those references unlinkable at a later date.

This module is one of several substrates published under the ActProof Events project. It is independently consumable; nothing else in the ActProof Events repository is required for it to function. The module's primary integration target is governance receipt issuance, where receipts anchored to public ledgers must remain verifiable indefinitely but the personal data referenced in the receipts must comply with GDPR Article 5(1)(e) storage limitation.

## The tension this resolves

Governance evidence systems face a structural tension. The cryptographic anchor in a public ledger is permanent by design: that is the property that makes the evidence verifiable decades later by any party with internet access to a public Algorand, Bitcoin, or Ethereum node. The personal data referenced in the underlying manifest (director names, voter identifiers, employee references, beneficiary identifiers) is subject to data-protection law: under GDPR Article 5(1)(e), personal data may be retained no longer than necessary for the purposes for which it was processed. After the legitimate retention period expires, the personal data must be erased, blocked, or anonymized.

A system that simply stores plaintext identifiers in receipts cannot satisfy both requirements. Either the on-chain anchor must be invalidated (not possible on a permissionless chain) or the personal data must persist beyond the retention period (a GDPR violation).

Salt-erasure resolves the tension by interposing a keyed pseudonymization layer. Identifiers in the manifest are replaced with HMAC outputs computed under a secret salt held by the system operator. While the salt exists, an authorized party (the operator, an auditor with delegated access, a regulator under legal process) can verify links between candidate identifiers and pseudonyms by recomputing the HMAC. When the legitimate retention period expires, the salt is irreversibly erased. After erasure, no party including the original operator can recompute the HMAC, and the pseudonyms become structurally unlinkable to any identifier. The anchored receipt remains verifiable as a cryptographic artifact; the personal data has been anonymized per the EDPB framework; both regulatory and architectural requirements are satisfied.

## The cryptographic primitive

The module implements HMAC-SHA-256 keyed pseudonymization. For an identifier `id` (a string, encoded as UTF-8 bytes) and a salt `K` (a 32-byte secret), the pseudonym is:

```
pseudonym = HMAC-SHA-256(K, id)
```

The output is a 32-byte value, which the module represents internally as raw bytes and renders externally as hex or base64url depending on the consuming context.

The security properties are those of HMAC-SHA-256 under standard assumptions. Specifically:

- **Unforgeability**: Without `K`, no efficient algorithm can compute `pseudonym` for any `id` other than by trying every candidate against a known target pseudonym, which is bounded by the size of the identifier domain. For governance identifiers (employee numbers, director names, voter rolls), the identifier domain is typically small enough that brute-force enumeration is feasible while `K` exists. This is acceptable because authorized parties holding `K` are expected to be able to compute linkages.

- **Unlinkability after erasure**: Once `K` is irreversibly destroyed, no party can compute `HMAC-SHA-256(K, id)` for any `id`. Pseudonyms produced under `K` become indistinguishable from random 32-byte values to any party. The identifier domain enumeration attack is no longer applicable because the HMAC oracle is gone.

- **Salt independence**: Pseudonyms produced under different salts are computationally independent. An adversary who learns `K_1` (or its erasure does not occur in time) gains no information about pseudonyms produced under `K_2`. This is the property that enables salt rotation and selective erasure.

## Status

The v1.0 module is published under Apache License 2.0. The Python reference implementation is operationally tested. The CC0-licensed test vector corpus demonstrates the before-erasure linkability and after-erasure unlinkability properties through reproducible test cases. The module is suitable for integration with governance receipt issuance systems that require GDPR-compliant audit trails.

Deferred to future versions: a formal security analysis with externally-audited threat model, hardware security module (HSM) integration patterns for salt storage and erasure, cross-language reference implementations beyond Python, and integration with the ActProof Events compact note schema for pseudonymous on-chain references.

## Quick start

Installation. The v1.0 module is distributed as a single-file Python module (`salt_erasure.py`) and requires Python 3.10 or later with the standard library only (no external dependencies for the core primitive). Drop the file into your project's Python path, or vendor it into your own package. A polished pip-installable distribution under the package name `actproof-salt-erasure` (importable as `actproof_salt_erasure`) is planned for v1.1; when that ships, the import statement in the example below changes from `from salt_erasure import ...` to `from actproof_salt_erasure import ...` with no other code changes required.

```python
from salt_erasure import SaltErasure, generate_salt, SaltErasedError

# Generate a fresh 32-byte salt
salt = generate_salt()

# Create a pseudonymizer bound to this salt
pseudonymizer = SaltErasure(salt=salt, salt_id="board-meeting-2026-06-16")

# Pseudonymize identifiers
director_a_pseudonym = pseudonymizer.pseudonymize("director_id_001")
director_b_pseudonym = pseudonymizer.pseudonymize("director_id_002")

# While the salt exists, verify links
assert pseudonymizer.verify_link("director_id_001", director_a_pseudonym) is True
assert pseudonymizer.verify_link("director_id_002", director_a_pseudonym) is False

# When the retention period expires, erase the salt
pseudonymizer.erase()

# After erasure, no operations are possible
try:
    pseudonymizer.pseudonymize("director_id_001")
except SaltErasedError:
    pass

# The pseudonyms remain valid as cryptographic artifacts but are no longer
# linkable to any identifier
print(director_a_pseudonym.hex())
```

## API reference

The module exposes the following public surface.

### `SaltErasure`

A pseudonymizer bound to a single salt. Construct with a 32-byte salt and a human-readable salt identifier (used in audit logs and serialised receipts to identify which salt-cohort the pseudonym belongs to).

- `pseudonymize(identifier: str) -> bytes`: Returns the 32-byte HMAC-SHA-256 pseudonym for the given identifier. Raises `SaltErasedError` if the salt has been erased.
- `verify_link(identifier: str, pseudonym: bytes) -> bool`: Returns True if the given identifier hashes to the given pseudonym under this salt, False otherwise. Raises `SaltErasedError` if the salt has been erased. Uses constant-time comparison to prevent timing side channels.
- `erase() -> None`: Irreversibly destroys the salt in memory. After this call, all operations on this instance raise `SaltErasedError`. The salt bytes are overwritten with zeros, and the internal reference is replaced with a sentinel. The Python garbage collector may retain the original bytes object briefly; for HSM-grade erasure, consult the section on persistent storage below.
- `salt_id: str`: The human-readable identifier for this salt cohort. Read-only.
- `is_erased: bool`: True if the salt has been erased, False otherwise.

### `SaltManager`

Manages multiple salts indexed by identifier, supporting salt rotation and selective erasure.

- `register(salt_id: str, salt: bytes) -> None`: Registers a new salt under the given identifier.
- `pseudonymize(salt_id: str, identifier: str) -> bytes`: Pseudonymizes the identifier using the named salt.
- `verify_link(salt_id: str, identifier: str, pseudonym: bytes) -> bool`: Verifies linkage using the named salt.
- `erase(salt_id: str) -> None`: Erases the named salt while leaving other salts in the manager untouched.
- `list_active_salt_ids() -> list[str]`: Returns the identifiers of salts not yet erased.

### Module-level utilities

- `generate_salt() -> bytes`: Returns 32 random bytes from the operating system's cryptographic random source (`secrets.token_bytes`).
- `is_well_formed_pseudonym(value: bytes) -> bool`: Returns True if the value is a 32-byte sequence (the expected shape of HMAC-SHA-256 output).

### Exceptions

- `SaltErasedError`: Raised when an operation is attempted on a `SaltErasure` instance whose salt has been erased.
- `UnknownSaltError`: Raised when a `SaltManager` is asked to operate on a salt identifier that has not been registered.

## Security model

The module's security guarantees rest on three assumptions.

**Assumption 1: HMAC-SHA-256 is secure.** This is a standard cryptographic assumption supported by extensive analysis. SHA-256 is a NIST-approved hash function with no known practical preimage or collision attacks. HMAC under SHA-256 is a pseudorandom function under the assumption that SHA-256 is a pseudorandom function.

**Assumption 2: The salt remains secret while it exists.** If the salt is leaked or copied by an unauthorized party before erasure, that party can compute linkages indefinitely, including after the operator's own erasure operation completes. The module provides no protection against salt theft. Operators must protect the salt through standard secret-management infrastructure: hardware security modules, encrypted storage at rest, access controls, audit logging of salt access.

**Assumption 3: Erasure is irreversible.** When `erase()` is called, the salt is overwritten in memory. For pure-memory deployments (transient processes), this provides reasonable erasure semantics, though Python's garbage collector may briefly retain copies depending on memory pressure. For persistent deployments where the salt was at any point written to durable storage, additional erasure steps are required: secure delete of the storage file, cryptographic shredding of the disk sectors, decommissioning of the HSM slot. The module does not implement persistent-storage erasure; integrators are responsible for ensuring that their salt-storage path supports irreversible erasure.

The module's threat model excludes the following attacks, which require system-level defenses:

- Memory dumps before erasure (mitigated by HSMs and memory protection)
- Side-channel attacks during pseudonymization (mitigated by constant-time HMAC implementations and physical security)
- Compromise of the random source for salt generation (mitigated by trusted OS cryptographic random sources)
- Coercion of the operator to retain or recreate the salt (mitigated by independent technical controls and split-key escrow)
- Reconstruction of identifiers from other sources beyond the pseudonyms (the EDPB anonymization standard explicitly requires that identifiers cannot be reasonably reconstructed from other available data; this requires data-management controls beyond cryptographic erasure alone)

## Limitations and integration notes

This module provides one cryptographic primitive. It is not by itself a GDPR-compliance solution. Operators integrating this module into governance evidence systems must additionally:

Establish a retention policy that defines when each salt cohort should be erased. The retention period is determined by the lawful basis for processing under GDPR Article 6 and the storage limitation principle under Article 5(1)(e). For most governance evidence, retention periods of seven to fifteen years are common, aligned with corporate record-keeping requirements and statutory limitation periods. The erasure event should be recorded in an immutable audit log so that future auditors can verify that erasure occurred at the policy-mandated time.

Ensure that no other data source allows reconstruction of identifiers from the pseudonyms. The EDPB anonymization framework requires that anonymization is robust against "all the means reasonably likely to be used to identify the natural person". If the same identifier appears in plaintext in another database, in operational logs, in backup archives, or in third-party reports, the pseudonymization in receipts does not anonymize the natural person. Operators must conduct a holistic data inventory and ensure that the salt-erasure event is accompanied by erasure or anonymization of all other identifier copies.

Document the salt-management architecture as part of the system's data-protection impact assessment under GDPR Article 35. The DPIA should describe where salts are generated, how they are stored, who has access, what the rotation schedule is, how erasure is triggered, and what the audit-trail evidence is for erasure events.

Consider salt rotation as a defense-in-depth measure even before retention-period expiry. Rotating salts on a regular schedule (annually, per fiscal period, per major business event) limits the blast radius of any single salt compromise. The `SaltManager` API supports rotation by maintaining multiple active salts simultaneously.

## EDPB anonymization framework

The European Data Protection Board, the body of supervisory authorities responsible for consistent GDPR interpretation across the European Economic Area, has issued guidance on anonymization techniques. The relevant authoritative documents at the time of writing include the Article 29 Working Party Opinion 05/2014 on Anonymisation Techniques (which the EDPB has endorsed as continuing guidance) and subsequent EDPB Guidelines on related topics. Implementers should consult the most recent EDPB publications for current authoritative guidance.

The substantive framework these documents establish is that data is "anonymized" (and therefore no longer personal data subject to GDPR) when the data subject is not identifiable, considering all the means reasonably likely to be used to identify the person. Pseudonymized data with a remaining key (such as the salt) does not meet this standard; it remains personal data subject to GDPR. Pseudonymized data after irreversible key erasure may meet the standard, provided that the cryptographic erasure is genuinely irreversible and that no other reasonably-available data source enables identifier reconstruction.

This module is designed to be used as one component of an anonymization architecture that meets this framework. The cryptographic erasure of the salt is necessary but not sufficient. Operators must combine it with the data-management practices described in the previous section to claim anonymization under the EDPB framework.

## Relationship to ActProof Events receipts

In the ActProof Events substrate, governance receipts may carry identifier references in the eligibility set, the action set, the tally output, the result, and the attachments. When these references include personal data, the salt-erasure module provides the recommended pseudonymization layer.

The typical integration pattern is to pseudonymize all identifier fields before computing the manifest hash. The manifest then contains pseudonyms rather than plaintext identifiers. The salt identifier (`salt_id`) is recorded in a non-anchored side-channel (the operator's internal records, the receipt's metadata in the operator-side database) so that authorized parties can determine which salt cohort applies to verification operations. The salt itself is held by the operator under appropriate access controls. When the retention period expires, the operator erases the salt, the linkage between pseudonyms and identifiers becomes unrecoverable, and the on-chain anchor remains as a verifiable but anonymized cryptographic artifact.

A future revision of the ActProof Events compact note schema may add an optional `salt_id` field to disclosed-mode notes, allowing receipts to declare which salt cohort their pseudonyms belong to. This is currently a documented schema gap for v1.4 amendment.

## License

This module is licensed under Apache License 2.0. See `LICENSE` for the full text.

The conformance test vectors in `test_vectors.json` are licensed under Creative Commons Zero v1.0 Universal (CC0-1.0). The CC0 license is chosen to allow any implementation in any language to import the test vectors into its conformance suite without attribution friction.

## Contributing

The module is small by design. Pull requests addressing the following areas are welcome:

- Reference implementations in additional languages (TypeScript, Rust, Go) that pass the CC0 test vector corpus
- Integration documentation for specific HSM vendors and KMS services
- Threat model elaborations grounded in concrete deployment scenarios
- Translations of this README into other languages

Pull requests proposing to expand the cryptographic primitive itself (alternative HMAC functions, alternative pseudonymization constructions) should open a GitHub Discussion first to align on whether the addition belongs in this module or in a separate companion module under the ActProof Events organization.

For security disclosures specific to this module, see the security disclosure section of the main ActProof Events repository's CONTRIBUTING_ACTS.md document.

## Maintainers

This module is currently maintained by Advisa EOOD (UIC 206448172, Sofia, Bulgaria), the company behind the Quoruna decision-recording product and the maintainer of the ActProof Events substrate. Long-term governance of the salt-erasure module is expected to transition to a multi-organization maintainer team as the ActProof Events substrate matures.

## Contact

For technical questions, open a GitHub issue against the ActProof Events repository with the `salt-erasure` label. For collaboration inquiries or research partnership proposals, contact `deyan@advisa.tech`.
