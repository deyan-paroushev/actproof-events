# DORA required-field binding notes

Version 1.8.0 binds the required fields in `op:eu.dora.ict_incident_notification_initial.v1` to source atoms drawn from four official-source instruments already pinned by the catalogue entry:

- Regulation (EU) 2022/2554, Article 19
- Commission Delegated Regulation (EU) 2025/301, Articles 1, 2 and 5
- Commission Implementing Regulation (EU) 2025/302, Annex I and Annex II
- Commission Delegated Regulation (EU) 2024/1772, Articles 1 to 8

The binding is intentionally modest. It does not claim full legal interpretation. It gives each required profile field a reviewable source basis and a derivation note, then records whether the mapping is direct, normalised, transformed, reconciled or modelled through the existing evidence-layer rubric.

## Required fields covered

The release validates that these 15 required fields have field-level derivations:

```text
entity_legal_identifier
entity_legal_name
financial_entity_type
submission_type
incident_reference_code
detection_datetime_utc
classification_datetime_utc
classification_criteria_triggered
affected_member_states
incident_discovery_method
business_continuity_plan_activated
initial_impact_description
primary_contact_name
primary_contact_email
competent_authority
```

Optional fields remain a future binding surface.
