# Field-level source binding

`actproof-events` 1.8.0 introduces field-level source binding for the required fields in the DORA initial-notification profile.

The canonical object remains the catalogue entry. The field-level binding layer is a reviewable read layer that explains where a profile field came from, which official-source units it depends on, and where interpretation entered.

## Data model

The 1.8.0 source-binding layer has two files:

```text
source_bindings/eu/dora/ict_incident_notification_initial.v1.source_atoms.json
source_bindings/eu/dora/ict_incident_notification_initial.v1.field_derivations.json
```

A source atom is the smallest reviewable source unit ActProof binds to. It may be an article, paragraph, annex section, template field, glossary entry, classification rule or threshold rule.

A field derivation maps one profile field to one or more source atoms and records the derivation type, mapping confidence, interpretive load, derivation note and field-specific non-claims.

## Public API

```python
from actproof_events.source_binding import explain_field_source

explanation = explain_field_source(
    "op:eu.dora.ict_incident_notification_initial.v1",
    "classification_criteria_triggered",
)
```

## CLI

```bash
actproof-events validate-source-bindings \
  op:eu.dora.ict_incident_notification_initial.v1

actproof-events explain-field \
  op:eu.dora.ict_incident_notification_initial.v1 \
  classification_criteria_triggered
```

## 1.8.0 release gate

The DORA profile has 27 fields, 15 of which are required. Version 1.8.0 binds all 15 required fields at field level and leaves the 12 optional fields marked as act-level fallback.

Expected coverage:

```text
required template-field coverage: 15/15 = 100.0%; release-gated field coverage: 15/27 = 55.6%
total field-level coverage:    15/27 = 55.6%
```

## Boundary

Field-level source binding does not certify legal compliance, determine supervisory findings or replace legal advice. It makes the profile's source basis inspectable, reproducible and challengeable.
