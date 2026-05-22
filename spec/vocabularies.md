# ActProof Events Controlled Vocabularies

**Version**: v1.5-rc1
**Status**: Pre-release candidate
**License**: Spec text is CC0. Schemas and test vectors are Apache-2.0.
**Maintainer**: actproof-events project

---

## Abstract

This document is the vocabulary reference for the ActProof Events catalogue. It governs the controlled vocabularies used by catalogue entry fields defined in `spec/schemas/act_catalogue_entry.v3.json`.

Two kinds of vocabulary appear in the catalogue. Closed vocabularies are enumerated directly in the JSON Schema. The schema file is the authoritative enumeration for these, and Section 2 explains what each value means. The `non_claims` vocabulary is open. The schema constrains only its shape, and this document is the governing authority for its naming rules and its recommended identifiers. Section 3 specifies that vocabulary.

---

## 1. Introduction

### 1.1 Scope

This document covers every controlled vocabulary referenced by a catalogue entry under the v3 entry schema: context types, submission stages, signature evidence labels, submission evidence labels, claim field types, and the `non_claims` identifier vocabulary. It does not cover manifest content, the receipt envelope, the hashing pipeline, or the on-chain note format. Those are specified in `spec/actproof-events.spec.md`.

### 1.2 Normative language

The key words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are used as defined in RFC 2119 and RFC 8174, and apply only when in capitals.

### 1.3 Two kinds of vocabulary

A closed vocabulary is enumerated in the JSON Schema as an `enum`. A value outside the enumeration fails schema validation. Adding a value to a closed vocabulary is a schema change and follows `schema_version_policy.md`. The schema file is authoritative for the set of values. The tables in Section 2 explain the meaning of each value and are kept consistent with the schema.

An open vocabulary is constrained only by shape. The schema fixes a string pattern, and any value matching the pattern passes validation. The `non_claims` array is the one open vocabulary in the v3 entry schema. This document, not the schema, is the governing authority for how `non_claims` identifiers are named and for the recommended set of identifiers. A new regulation can therefore introduce its own `non_claims` identifiers as catalogue data, with no schema change.

---

## 2. Closed vocabularies

The values in this section are enumerated in `spec/schemas/act_catalogue_entry.v3.json`. Where this document and the schema file appear to disagree, the schema file governs the set of permitted values and this document should be corrected.

### 2.1 Context types

Used by `regulated_context_profile.allowed_context_types` and `regulated_context_profile.default_context_type`. They constrain the receipt envelope `regulated_context.context_type` for receipts issued under an act type.

| Value | Meaning |
| --- | --- |
| `transaction_or_shipment` | The act records a discrete transaction or a shipment of goods or value. |
| `incident_lifecycle` | The act is one event in the lifecycle of an incident, such as detection, escalation, or resolution. |
| `regulatory_filing` | The act records a filing, notification, submission, or prepared filing package directed to a competent authority, a regulator, or another legally designated recipient. |
| `reporting_period` | The act covers a defined reporting period, such as a quarter or a financial year. |
| `assurance_handoff` | The act is a handoff of assurance from one party to another, such as from an external auditor to a board. |
| `release_or_publication` | The act is the release or publication of an artifact, such as a software release, a published mandate, or a board approval recorded for the entity. |

### 2.2 Submission stages

Used by `regulated_context_profile.allowed_submission_stages`. They constrain the receipt envelope `regulated_context.submission_stage`. The set declared on an act type SHOULD be coherent with its `allowed_context_types`: each stage belongs to one of the allowed context types. The table groups the stages by lifecycle family for readability. The schema enumeration is the authoritative set.

| Stage | Family | Meaning |
| --- | --- | --- |
| `pre_submission_evidence_pack` | Preparation | An evidence pack assembled before any submission. |
| `evidence_pack_prepared` | Preparation | An evidence pack that has been prepared and finalised. |
| `prepared` | Preparation | The act has been prepared and is ready for its next lifecycle step. |
| `early_warning` | Filing or incident | An initial alerting notification issued ahead of a fuller report. |
| `initial_notification` | Filing or incident | The first formal notification of an incident or matter to its recipient. |
| `intermediate_report` | Filing or incident | An interim report following an initial notification. |
| `progress_report` | Filing or incident | A status update issued between defined milestones. |
| `reclassification_to_non_major` | Filing or incident | A notification that a previously notified matter is reclassified as no longer major. |
| `final_report` | Filing or incident | The concluding report in a reporting sequence. |
| `submitted` | Submission | The act has been submitted to its recipient. |
| `submission_acknowledged` | Submission | The recipient has acknowledged receipt of the submission. |
| `pre_publication` | Publication | The act is prepared but not yet published. |
| `published` | Publication | The act has been published. |
| `assurance_engagement_complete` | Assurance | An assurance engagement underlying the act has been completed. |
| `assurance_handoff_complete` | Assurance | An assurance handoff has been completed. |
| `restated` | Revision | A previously issued act has been restated with corrected content. |
| `superseded` | Revision | The act has been replaced by a later act of the same type. |
| `withdrawn` | Revision | The act has been withdrawn by its issuer. |

### 2.3 Signature evidence labels

Used by `signature_policy.supports`. Each label names an externally produced signature or attestation artifact that an act type recognises alongside the platform `issuer_record`. The companion field `signature_policy.minimum` sets the floor of what must be present at commit time and takes the values `issuer_record`, `external_signature`, or `either`. `issuer_record` is an evidence record of the issuer commit action. It is not an Advanced or Qualified Electronic Signature under Regulation (EU) 910/2014 (eIDAS).

| Value | Meaning |
| --- | --- |
| `external_qes_pdf` | A PDF carrying a Qualified Electronic Signature under eIDAS. |
| `external_qes_artifact` | A Qualified Electronic Signature artifact in a form other than PDF, such as a detached or XML signature. |
| `external_aes_certificate` | An Advanced Electronic Signature with a supporting certificate under eIDAS. |
| `signed_board_minutes` | Board minutes or a resolution signed by the relevant officers. |
| `third_party_signing_service_certificate` | A certificate issued by a third-party signing service. |
| `internal_attestation_record` | An attestation record produced within the issuer's own systems. Not an eIDAS signature. |
| `gpg_signed_release` | A release signed with a GnuPG or OpenPGP key. |
| `sigstore_cosign_signature` | A Sigstore cosign signature. |
| `in_toto_statement_v1` | An in-toto attestation Statement, version 1. Recognised for software release act types. Not an eIDAS signature. |
| `slsa_provenance_v1_attestation` | A SLSA Provenance version 1 attestation. Recognised for software release act types. Not an eIDAS signature. |

### 2.4 Submission evidence labels

Used by `submission_evidence_policy.supports`. Each label names an artifact that evidences submission or transmission of an act to its recipient. These labels are distinct from the signature evidence labels in Section 2.3. A submission acknowledgement is evidence that a filing reached its recipient. It is not a signature over the filing's content.

| Value | Meaning |
| --- | --- |
| `secure_electronic_channel_acknowledgement` | An acknowledgement returned by a secure electronic channel confirming receipt. |
| `authority_submission_reference` | A reference or identifier assigned by the receiving authority on submission, such as a case reference or a filing number. |
| `authority_receipt_acknowledgement` | An acknowledgement from the authority confirming the filing was received. |
| `portal_submission_confirmation` | A confirmation produced by a submission portal. |
| `registered_delivery_confirmation` | A confirmation of registered delivery, by registered post or registered electronic delivery. |
| `email_delivery_receipt` | A delivery or read receipt for a submission sent by email. |
| `api_submission_response` | A response returned by an API submission endpoint. |

### 2.5 Claim field types

Used by the `claim_field_types` map. Each value declares the primitive data type of a claim field, so a catalogue-driven consumer can render the input control, parse the submitted value, and serialise the manifest with no hardcoded per-act-type knowledge.

| Value | Meaning |
| --- | --- |
| `string` | A short single-line value. |
| `text` | A long multi-line value. |
| `boolean` | True or false. |
| `integer` | A whole number. |
| `number` | A decimal number. |
| `date` | An ISO 8601 calendar date, `YYYY-MM-DD`. |
| `datetime` | An ISO 8601 timestamp in UTC. |
| `email` | An email address. |
| `string_list` | An ordered list of strings, that is a multi-value field. |

A consumer that encounters a claim field absent from an entry's `claim_field_types` map SHOULD treat that field as `string`.

---

## 3. The non_claims vocabulary

### 3.1 Purpose

`non_claims` is an optional array on `reliance_context`. It enumerates, in machine-readable form, the inferences that a verifier MUST NOT draw from a receipt issued under an act type. It exists so that a catalogue entry can state the limits of a receipt as structured data, not only as prose, and so that those limits can be rendered consistently on receipts and verification pages.

### 3.2 What a receipt proves

The `non_claims` identifiers carve out what lies beyond the proof a receipt actually carries, so the baseline matters. A receipt under this substrate proves that a named issuer committed to a specific manifest, comprising the claim fields and the evidence hashes, at a specific time, that the committed content is integrity-protected by the canonical hashing pipeline, and, when anchored, that the commitment is recorded on a public ledger so that any third party can verify it independently without trusting the issuer or any intermediary platform.

A receipt does not, by itself, prove that the issuer's substantive claims are factually correct, that any authority accepted or approved the act, that the issuer is compliant with any regulation, or that legal liability has been allocated, admitted, or transferred. Identifiers in `non_claims` make such limits explicit and specific for a given act type.

### 3.3 Shape constraint

The JSON Schema constrains each `non_claims` value to the pattern:

```
^[a-z0-9]+(?:_[a-z0-9]+)*$
```

A value is one or more segments of lowercase letters and digits, joined by single underscores. There is no leading or trailing underscore, and no consecutive underscores. A value matching this pattern passes schema validation. The remainder of this section is the naming guidance that this document, not the schema, governs.

### 3.4 Naming rules

A `non_claims` identifier SHOULD be structured as `does_not_<verb>_<object>`.

It SHOULD begin with `does_not_`, so the identifier reads as a negation.

The `<verb>` segment SHOULD name the kind of inference that is being excluded. The recommended verbs and their sense are:

| Verb | Excluded inference |
| --- | --- |
| `prove` | that something has been demonstrated to be the case |
| `establish` | that something has been settled or made certain |
| `confirm` | that something has been independently corroborated |
| `imply` | that something follows by suggestion or association |
| `constitute` | that the receipt itself amounts to the thing named |
| `replace` | that a separate obligation or instrument is satisfied |
| `discharge` | that a continuing duty has been fully met |
| `exhaust` | that no further steps in a sequence remain |
| `transfer` | that a right, duty, or liability has moved between parties |
| `create` | that a new obligation or entitlement has arisen |
| `confer` | that a status, membership, or authority has been granted |
| `predetermine` | that the outcome of a later process has been fixed |

The `<object>` segment names the specific inference and SHOULD be precise enough to be unambiguous. Entry-specific identifiers MAY be long.

Where an identifier refers to a legal instrument, the instrument name SHOULD be lowercased into snake_case. Punctuation, parentheses, slashes, and spaces become underscores, and year and number become underscore-separated digit segments. For example, "Directive (EU) 2022/2555" becomes `directive_eu_2022_2555`, and "Regulation (EU) 2016/679" becomes `regulation_eu_2016_679`.

### 3.5 Recommended core identifiers

The following identifiers are generic and reusable across act types. A catalogue entry SHOULD use a core identifier verbatim where one fits, rather than coining a near-duplicate.

| Identifier | Meaning |
| --- | --- |
| `does_not_prove_regulator_acceptance` | The receipt does not prove that a regulator or competent authority accepted, approved, or agreed with the act. |
| `does_not_prove_regulatory_compliance` | The receipt does not prove that the issuer is in compliance with the cited regulation. It proves only that the named act was performed and committed. |
| `does_not_establish_the_truth_of_the_issuer_claims` | The receipt proves that the issuer committed to the stated claims with integrity at the stated time. It does not independently establish that those claims are factually correct. |
| `does_not_transfer_legal_liability` | The receipt does not transfer, allocate, or limit legal liability between any parties. |
| `does_not_constitute_an_admission_of_liability` | The receipt does not constitute an admission of fault, breach, or liability by the issuer. |
| `does_not_constitute_legal_advice` | The receipt and its catalogue entry do not constitute legal advice. |
| `does_not_replace_obligations_under_other_instruments` | The receipt does not replace or satisfy notification, filing, or disclosure obligations arising under instruments other than the one cited. |
| `does_not_predetermine_the_outcome_of_any_review` | The receipt does not predetermine the outcome of any supervisory, audit, judicial, or other review. |
| `does_not_imply_endorsement_by_a_third_party` | The receipt does not imply endorsement, certification, or approval by any third party, including any standards body, auditor, or authority. |

### 3.6 Entry-specific identifiers

Most act types also need identifiers that name limits specific to their regulation or governance context. These are catalogue data. They are authored on the entry and require no schema change.

The DORA initial notification entry, `op:eu.dora.ict_incident_notification_initial.v1`, declares entry-specific identifiers including `does_not_replace_the_separate_notification_obligation_under_directive_eu_2022_2555_nis2`, `does_not_constitute_the_final_legal_classification_of_the_incident`, and `does_not_exhaust_the_intermediate_and_final_reporting_obligations_under_dora_article_19_4`.

The standards engagement record entry, `op:actproof.standards_engagement_record.v1`, declares entry-specific identifiers including `does_not_prove_admission_to_the_working_group`, `does_not_prove_acceptance_of_any_contribution_by_the_working_group`, and `does_not_imply_endorsement_by_the_standards_developing_organisation_or_its_officers`.

An entry-specific identifier follows the same naming rules as Section 3.4.

### 3.7 Consistency with reliance_statement

Where an entry declares both `non_claims` and `reliance_statement`, the two MUST be consistent. `reliance_statement` is the human-readable prose. `non_claims` is the machine-readable enumeration of the same limits. An entry SHOULD state, in its `reliance_statement`, that the `non_claims` array is the authoritative enumeration of what the receipt does not prove. Each identifier in `non_claims` SHOULD have a human-readable counterpart in the `reliance_statement` or be rendered on the receipt and verification surfaces.

---

## 4. Governance and change process

### 4.1 Closed vocabularies

A value in any closed vocabulary in Section 2 is added by amending `spec/schemas/act_catalogue_entry.v3.json`. Adding a value to an `enum` is an additive change: entries authored before the addition remain valid. Such a change follows `schema_version_policy.md` and MUST be accompanied by a new row in the relevant table of this document.

### 4.2 The non_claims vocabulary

An entry-specific `non_claims` identifier is added with the catalogue entry that uses it. It is catalogue data and requires no schema change and no change to this document.

A genuinely new generic identifier, one that is reusable across act types, SHOULD be proposed as an addition to the recommended core list in Section 3.5, so that the core list stays curated and entries converge on shared identifiers rather than coining near-duplicates.

### 4.3 Proposing changes

Changes to this document are proposed as pull requests against the actproof-events repository. A change to a closed vocabulary references the corresponding schema change. A change to the `non_claims` core list explains the inference the new identifier excludes and why an existing core identifier does not already cover it. Catalogue authoring conventions are described in `CONTRIBUTING_ACTS.md`, and the loader behaviour that consumes these vocabularies is described in `CATALOGUE_LOADER_CONTRACT.md`.
