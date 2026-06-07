# Bank Overlay Impact Review v1

`actproof-events 2.2.0` introduces an offline change-control report that compares a changed ActProof profile-view against a bank-owned overlay.

The purpose is narrow: when a bank has reviewed internal mappings against one ActProof profile hash, and a later ActProof profile changes, the library identifies which bank-local mapping decisions, missing-required-field decisions and review assumptions require re-review.

It does **not** migrate overlays automatically, approve mappings, decide legal materiality, certify compliance or determine supervisory acceptance.

## Command

```bash
actproof-events diff-overlay-impact \
  bank-overlay.json \
  old.profile-view.json \
  new.profile-view.json \
  --out overlay-impact-report.json
```

## Impact statuses

- `no_profile_change` - semantic profile hash did not change.
- `no_overlay_impact` - profile changed but no direct overlay decision was affected; retain an audit record.
- `review_required` - one or more overlay decisions should be reviewed before carry-forward.
- `blocking_review_required` - a removed accepted mapping, new required field, or similar blocking change requires bank action before carry-forward.

## Conservative rule

If a mapped field, source basis, required status or review status changes, the bank overlay requires review. When uncertain, the library asks for review rather than declaring a change safe.
