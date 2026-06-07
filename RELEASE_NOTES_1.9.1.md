# actproof-events 1.9.1 — Profile diff and change control

This release adds a conservative change-control layer for exported profile-view JSON files.

## Added

- `actproof_events.profile_diff`
- `diff_profile_views(...)`
- `diff_profile_view_files(...)`
- CLI command:

```bash
actproof-events diff-profile old.profile-view.json new.profile-view.json --out profile-diff.json
```

## Detects

- field added / removed / changed
- source atom or source-basis changes
- review status changes
- coverage changes
- semantic hash changes
- catalogue hash changes

## Boundary

The report is a change-control aid. It does not approve a profile change, determine legal materiality, certify compliance, or replace bank/GRC/audit review.
