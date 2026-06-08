# COSE signing boundaries v1

The ActProof 2.7.0 COSE signing prototype deliberately separates four concepts that are often confused.

## Signed is not reviewed

A COSE signature proves that a key signed a statement hash. It does not prove that the statement was reviewed by a qualified maintainer, lawyer, auditor, bank SME or regulator.

## Signed is not SCITT-registered

2.7.0 produces a local COSE_Sign1 prototype. It does not submit the statement to a SCITT Transparency Service and it does not return a SCITT receipt.

## Signed is not legally correct

The official legal source remains the source of law. ActProof source atoms are source-bound evidence objects and profile-building elements. Signing a statement about an atom does not resolve legal interpretation.

## Signed is not compliance certification

A signed source-atom statement may help a relying party verify that a specific atom statement has not been altered. It does not certify that an institution is compliant, that a report is correct, or that a regulator will accept an output.

## Recommended use

Use 2.7.0 for development, inspection, research, reproducible examples, local verification demonstrations and preparation for a later SCITT registration pilot.

Do not use generated development keys or draft atom signatures as production trust artifacts.
