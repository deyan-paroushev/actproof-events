# COSE source-atom statement notes v1

ActProof source-atom statements are designed to be COSE-ready without adding a production signing dependency in 2.6.0.

The intended future COSE direction is:

```text
canonical atom statement JSON
→ hash commitment / hash envelope
→ COSE_Sign1 or equivalent signed statement
→ SCITT registration
→ COSE receipt
→ offline relying-party verification
```

2.6.0 records:

- `cose_typ: actproof/source-atom/v1`
- `payload_mode: hash_commitment`
- `cose_status: profile_defined_not_signed`
- `scitt_registration_status: not_registered`

This keeps the release honest. It defines the payload and verification contract before adding real signing and receipt verification.
