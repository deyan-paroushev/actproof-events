# Transparency note

## DORA major ICT-related incident, initial notification

Act type: `op:eu.dora.ict_incident_notification_initial.v1`

This note is the human-readable companion to the profile's `generation` block.
The two give the same account, one in JSON and one in prose. The note exists so
that a reader who is not reading the profile JSON can still see what the profile
is built from, what the law requires, and where the author exercised judgement.
It hands the reader everything needed to check the profile against its sources
and reach an independent conclusion.

## 1. The source

The profile is built from four official EU legal instruments. Each is bound by
reference and by the SHA-256 hash of the artefact retrieved from the European
Union's official publication system. The artefact in every case is the Official
Journal PDF, the authentic published form of the act. The profile does not copy
any source text into the catalogue. It cites each instrument and pins its hash.
The artefacts were retrieved on 23 May 2026.

Anyone can re-fetch an instrument from the cited URL, hash the bytes, and confirm
the value below. A later mismatch means the instrument may have been amended, and
is the signal to revisit this profile.

**Regulation (EU) 2022/2554, the Digital Operational Resilience Act (DORA).**

- CELEX 32022R2554. ELI `http://data.europa.eu/eli/reg/2022/2554/oj`.
- Provisions relied on: Article 19.
- Artefact: Official Journal PDF.
- `sha256:85307f9e2a0409826dd0f54489645935816d16e929f0db4db3ef15badd11d38c`

**Commission Delegated Regulation (EU) 2025/301.** The regulatory technical
standards on the content of incident reports.

- CELEX 32025R0301. ELI `http://data.europa.eu/eli/reg_del/2025/301/oj`.
- Provisions relied on: Articles 1, 2 and 5.
- Artefact: Official Journal PDF.
- `sha256:47a209a9f73e228e85e1dad2934d917d5791629fc98add06fc6fda0acb872dbf`

**Commission Implementing Regulation (EU) 2025/302.** The implementing technical
standards giving the reporting templates.

- CELEX 32025R0302. ELI `http://data.europa.eu/eli/reg_impl/2025/302/oj`.
- Provisions relied on: Annex I and Annex II.
- Artefact: Official Journal PDF.
- `sha256:37ec431c7a11b8b30b39d1c1f0d95c39539d1c1e7236301ee3b06bb229ff009c`

**Commission Delegated Regulation (EU) 2024/1772.** The regulatory technical
standards on the classification of ICT-related incidents.

- CELEX 32024R1772. ELI `http://data.europa.eu/eli/reg_del/2024/1772/oj`.
- Provisions relied on: Articles 1 to 8.
- Artefact: Official Journal PDF.
- `sha256:416fb104161f8b3eb0aae2601060ab869b1672cfa8452d20798800301538ceab`

## 2. What the law requires

DORA, Regulation (EU) 2022/2554, is a Regulation, not a Directive. It applies
directly across the Union and has applied since 17 January 2025. Article 19
obliges a financial entity within its scope to report a major ICT-related
incident to its competent authority. Article 19(4) sets a three-stage sequence:
an initial notification, an intermediate report, and a final report. This
profile covers the initial notification only.

DORA itself does not set out the detail of what the initial notification must
contain. That is left to two supplementing instruments.

Commission Delegated Regulation (EU) 2025/301, the regulatory technical
standards, prescribes the content. Article 1 lists general information that
appears in all three reports: the type of submission, the financial entity's
name, LEI code and type, the entity that submits the report, the contact
persons, and others. Article 2 prescribes the information specific to the
initial notification: the incident reference code, the dates and times of
detection and of classification, a description of the incident, the
classification criteria relied on, the Member States impacted, how the incident
was discovered, whether a business continuity plan was activated, and related
items. Article 5 sets the time limits. The initial notification is due as early
as possible, and in any case within four hours of the incident being classified
as major and no later than 24 hours after the entity became aware of it.

Commission Implementing Regulation (EU) 2025/302, the implementing technical
standards, gives the official reporting template in Annex I and the data
glossary in Annex II. In that template the initial notification is the
general-information fields and the fields grouped under "Content of the initial
notification", numbered 2.1 to 2.10.

Whether an incident counts as major is determined under Commission Delegated
Regulation (EU) 2024/1772. Its Articles 1 to 7 set seven classification
criteria: clients, financial counterparts and transactions; reputational impact;
duration and service downtime; geographical spread; data losses; criticality of
services affected; and economic impact. Article 9 sets the materiality
thresholds for those criteria. Article 8 is the rule that determines, from the
criteria and their thresholds, when an incident is major. An initial
notification must state the criteria, under Articles 1 to 8, on which the entity
based its classification.

In short, the profile models one regulatory deliverable: the initial
notification that a financial entity must submit to its competent authority,
within a fixed time window, when it classifies an ICT-related incident as major
under DORA Article 19(4).

## 3. The data model, and where judgement entered

The profile's claim schema follows the official template of Implementing
Regulation (EU) 2025/302, Annex I. Most fields are a direct transcription. The
type of submission, the entity name and LEI code, the incident reference code,
the detection and classification timestamps, the classification criteria, the
affected Member States, the discovery method, and the business continuity plan
indicator each correspond to a named field of the official template.

The profile was reconciled in May 2026 against the four hashed sources above.
The reconciliation checked the claim schema field by field against the official
text and made four corrections. They are recorded here in full.

The field `affected_functions_and_services` was a required field. The official
template places affected functional areas and business processes in the
intermediate report, field 3.27, not in the initial notification, and Article 2
of Regulation (EU) 2025/301 does not list it among the initial-notification
content. It was moved to optional. The required content of the profile now
matches the official initial-notification template. The field remains available,
because Article 2 sets the initial notification's content as a floor, "at least"
the listed items, and an entity may choose to report affected services early.

A field for the type of financial entity was missing. The official template
requires it, field 1.4, and Article 1(b) of Regulation (EU) 2025/301 makes it
mandatory in every report. A required field `financial_entity_type` was added.

The optional field for the preliminary estimated financial amount embedded the
euro in its name. The official template is currency-agnostic and carries a
separate "Reporting currency" field, 1.15. The field was renamed
`preliminary_estimated_financial_amount`, and an optional `reporting_currency`
field was added.

The profile's reliance statement previously described the incident as classified
"against the criteria of Article 8" of Regulation (EU) 2024/1772. Article 8 is
the rule that determines when an incident is major. The criteria themselves are
in Articles 1 to 7. The wording was corrected to classification "under Articles
1 to 8", which is how Article 2(d) of Regulation (EU) 2025/301 itself refers to
the classification basis.

Three further choices are deliberate, and are not transcriptions of the official
template. They are recorded here so a reader can see them plainly.

The field `initial_impact_description` corresponds to the official field 2.4,
"Description of the major ICT-related incident". The profile names it for the
impact it records. The field carries the description of the incident that the
law requires. The name reflects the receipt's purpose.

The field `competent_authority` is a required claim field. The official template
does not carry the competent authority as a data field, because the competent
authority is the recipient of the notification rather than content within it.
The profile records it because a receipt issued under this profile is a proof
that a named filing reached a named authority, and the authority must therefore
be named.

Several optional fields, `preliminary_estimated_clients_affected`,
`preliminary_estimated_financial_amount`, and `first_disruption_datetime_utc`,
carry information that the official template assigns to the intermediate report.
They are optional here so that an entity may record that information early if it
is already known. The "at least" floor of Article 2 permits this.

Two smaller choices. The field `classification_criteria_triggered` is an open
list of strings. The profile does not fix a closed value list. The criteria are
those of Articles 1 to 7 of Regulation (EU) 2024/1772, named in section 2 above.
All field identifiers are lower-case snake_case, and all timestamps are ISO 8601
in UTC, as recorded in the profile's `claim_field_types`.

How the profile was produced. The claim schema was drafted in earlier work, and
was then reconciled in May 2026, as set out above, against the four hashed
official sources, with ai-assisted analysis of the official text and the
corrections listed here applied. This account matches the profile's `generation`
block, which records the method, the reconciliation, and the eight-stage
authoring process the profile follows.

## 4. An open invitation

The four instruments in section 1 are pinned by hash and are public. The
plain-language account in section 2 and the record of judgement in section 3 are
complete. Nothing in this profile rests on trusting the author.

Anyone may re-fetch the cited sources, confirm the hashes, and read the official
text against the profile's claim schema, to judge whether the schema faithfully
represents what the law requires. Anyone may propose a correction, or contribute
a profile of their own. A contribution is assessed on one question: does its
claim schema match the official source it cites, where that source is pinned by
hash and independently fetchable. It is not assessed on who sent it. No special
standing, no paid tool, and no AI are needed to perform that check. The inputs
are all here.
