# ActProof profile governance v1

ActProof profile governance makes the review state of a profile explicit and hash-bound. It does not assert legal correctness, bank approval, supervisory approval, or compliance certification.

## Governance objects

- `review-records.json` — bounded review records such as `maintainer_reviewed`.
- `challenge-records.json` — public challenges and gap signals.
- `governance-status.json` — computed lifecycle state for one profile.

## Lifecycle states

- `candidate`
- `draft`
- `maintainer_reviewed`
- `pilot_ready`
- `deprecated`
- `superseded`
- `withdrawn`

ActProof 2.0.0 ships a maintainer-reviewed governance record for the DORA initial-notification profile. This is not external legal review and not bank SME approval.

## Bank boundary

A bank may use the governance record as part of a local POC and internal review process. The bank remains responsible for final legal/regulatory interpretation, factual incident investigation, internal control approval and regulatory submission.
