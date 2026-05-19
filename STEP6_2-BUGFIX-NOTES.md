# Bugfix for Quoruna Step 6.2: parallel fixes following ChatGPT's events review

The live STS mainnet mint goes through `anchoring/standards_engagement_builder.py`, not through the events test vector. So the same two bugs that ChatGPT identified in the events test vector also need fixing on the Quoruna side, or the live receipt would still carry the wrong maintainer name and the wrong specifications order.

## Files

### Modified

- `anchoring/standards_engagement_builder.py`:
  - `MAINTAINER_LEGAL_NAME`: "Advisa EOOD" -> "Deyan Paroushev". Issuer remains "Advisa EOOD" (correct, unchanged). The ORCID 0009-0003-8231-8265 ties the natural person to the legal entity.
  - `RELATED_SPECIFICATIONS`: reordered to lead with core specs (SCITT architecture, COSE Merkle Tree Proofs, RFC 8785, RFC 3161), then the two newer drafts (fassbender, hillier) at the end as related implementation context.

- `anchoring/evidence/standards_engagement/implementation_repository_state.txt`: clarified the header to distinguish "Issuer (legal entity): Advisa EOOD (UIC 206448172, Sofia, Bulgaria)" from "Maintainer (natural person): Deyan Paroushev (ORCID 0009-0003-8231-8265)".
- `anchoring/evidence/standards_engagement/working_group_charter_reference.txt`: same Issuer/Maintainer clarification.

## End-to-end verified

After installing the updated events wheel and reloading the Quoruna mint pipeline:

    maintainer_legal_name:   Deyan Paroushev
    maintainer_orcid:        0009-0003-8231-8265
    issuer_org_name:         Advisa EOOD
    issuer_authority_label:  open_source_maintainer
    related_specifications: leads with draft-ietf-scitt-architecture-22; ends with hillier draft
    catalogue.entry_hash:    sha256:41fcb384eb34851002de34df80fbe5844ae8f6a83f4ace8cb4952eb047d01cf5
    catalogue.source_package: actproof-events 1.4.0rc1
    evidence sizes:          4548 B + 5100 B (changed because of header clarification)
    pre-anchor manifest hash: sha256:4bdced7c7798bd38dc7432d1d1c00516d85f4236f4a8bc118c45245f16bb8290

The pre-anchor manifest hash will differ from this when you run with the current timestamp and a real catalogue_git_commit, but the canonical structure is identical.

## Pickup

Apply this zip on top of the previous Step 6.2 in your Quoruna working tree, then `pip install --force-reinstall` the new actproof-events wheel built from the bugfix events delivery, then run:

    python scripts/mint_standards_engagement_record.py --mode draft

The summary should show maintainer = "Deyan Paroushev". If it shows "Advisa EOOD", the install did not pick up the new builder; rerun the install.
