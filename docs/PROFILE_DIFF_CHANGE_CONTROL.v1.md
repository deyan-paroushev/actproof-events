# Profile diff and change control v1

`actproof-events 1.9.1` adds profile-view diffing for controlled adopters.

The feature compares two exported `profile-view` JSON files and emits a change-control report. It is designed for bank, GRC, audit and integration teams that need to know what changed before pinning a new ActProof profile version.

## CLI

```bash
actproof-events diff-profile old.profile-view.json new.profile-view.json --out profile-diff.json
```

## What the report checks

- profile semantic hash changed
- profile artifact hash changed
- catalogue entry hash changed
- fields added
- fields removed
- fields changed
- source atom/source basis changed
- review status changed
- coverage changed

## Boundary

The diff report does not decide whether a change is legally material, compliant, safe for production use or accepted by a supervisor. It identifies review surfaces that require human change-control review.
