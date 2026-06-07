# actproof-events 2.2.0 — Bank Overlay Impact Review

This release adds profile-change impact reporting for bank-owned overlays.

## Added

- `actproof_events.overlay_impact`
- `build_overlay_impact_report(...)`
- `diff_overlay_impact_files(...)`
- `write_overlay_impact_report(...)`
- CLI command: `actproof-events diff-overlay-impact`
- Documentation: `docs/BANK_OVERLAY_IMPACT.v1.md`
- Tests: `tests/test_overlay_impact.py`

## Boundary

The impact report is descriptive and conservative. It does not migrate bank overlays, approve mappings, determine legal materiality, certify compliance or provide supervisory approval.
