#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Advisa EOOD (Sofia, Bulgaria)
# SPDX-License-Identifier: Apache-2.0
"""
ActProof Mapper - interpretation link model (shared)
=====================================================

WHY THIS EXISTS (in plain words)
--------------------------------
An interpretation link connects a profile field (or evidence label) to an
interpretation decision that governs it. The hard question a commons must
answer is not "is there a link?" but:

    "Who proposed this reading, and has a human affirmed it?"

The law was written by humans. An AI can PROPOSE a reading, but the FINAL call
on interpretation rests with a human maintainer. Different AIs, and different
maintainers, may read the same provision differently. Accuracy in this commons
comes from attributed plurality plus human convergence - not from trusting any
single interpreter.

So an interpretation link is not a single value. It holds:

  - proposals[]   one or more attributed proposals (which AI or which human
                  proposed this, when, citing which decision, and why)
  - affirmation   the human record: proposed | affirmed | overruled, by whom,
                  when, which proposal was chosen, and a note
  - discussion_ref  OPTIONAL, host-neutral pointer to where the deliberation
                  happened (a GitHub discussion today, something else tomorrow).
                  The link is meaningful WITHOUT it; the commons must not depend
                  on any single host.
  - vote_ref      RESERVED, unused for now: the slot for a future mechanism
                  (e.g. a Quoruna vote) that resolves a contested link.

Today a link typically holds one AI proposal and an affirmation status of
"proposed". That is the honest degenerate case of the full model: the slot is
designed for many, and currently holds one. When a second maintainer later runs
a different model, their reading appends to proposals[]; the structure for
choosing between them is already present.

This module defines the record shape in ONE place so step 4 (field links) and
step 6 (decision register) stay consistent.
"""

from __future__ import annotations


# Affirmation lifecycle. A link is one of these.
AFFIRMATION_PROPOSED = "proposed"     # an AI or human proposed it; no human has affirmed
AFFIRMATION_AFFIRMED = "affirmed"     # a human maintainer affirmed the chosen proposal
AFFIRMATION_OVERRULED = "overruled"   # a human maintainer overruled all proposals

KNOWN_AFFIRMATION_STATUS = {
    AFFIRMATION_PROPOSED,
    AFFIRMATION_AFFIRMED,
    AFFIRMATION_OVERRULED,
}


def make_proposal(proposed_by, chosen_decision, rationale=None, proposed_at=None):
    """Build one attributed proposal.

    proposed_by: model name + version (e.g. "GPT-5.5") or a human handle.
    chosen_decision: the interpretation_decision id this proposal points to.
    rationale: why this reading was proposed.
    proposed_at: ISO date/time the proposal was made.
    """
    return {
        "proposed_by": proposed_by,
        "proposed_at": proposed_at,
        "chosen_decision": chosen_decision,
        "rationale": rationale,
    }


def make_interpretation_link(proposals=None, affirmation=None,
                             discussion_ref=None, vote_ref=None):
    """Build a full interpretation-link record.

    proposals: list of make_proposal(...) records (may hold just one today).
    affirmation: an affirmation block (see make_affirmation); defaults to
                 a 'proposed' status with no human sign-off yet.
    discussion_ref: OPTIONAL host-neutral pointer to the deliberation venue.
    vote_ref: RESERVED, unused; a future vote mechanism may populate it.
    """
    proposals = list(proposals or [])
    if affirmation is None:
        affirmation = make_affirmation(status=AFFIRMATION_PROPOSED)
    return {
        "proposals": proposals,
        "affirmation": affirmation,
        "discussion_ref": discussion_ref,
        "vote_ref": vote_ref,
    }


def make_affirmation(status=AFFIRMATION_PROPOSED, affirmed_by=None,
                     affirmed_at=None, chosen_proposal=None, note=None):
    """Build the human affirmation block.

    status: proposed | affirmed | overruled.
    affirmed_by: the human maintainer who took the final call (handle).
    affirmed_at: ISO date/time of the affirmation.
    chosen_proposal: index or proposed_by of the proposal that was affirmed.
    note: the maintainer's reason for affirming or overruling.
    """
    return {
        "status": status,
        "affirmed_by": affirmed_by,
        "affirmed_at": affirmed_at,
        "chosen_proposal": chosen_proposal,
        "note": note,
    }


def link_from_legacy(decision_ids, proposed_by, proposed_at=None, rationale=None):
    """Adapter: turn a legacy flat list of decision ids into proposal records.

    The earlier model recorded interpretation_decisions as a bare list of ids
    with no attribution. This wraps each into an attributed proposal with the
    affirmation defaulting to 'proposed', so existing examples migrate cleanly
    into the multi-proposal shape without claiming a human affirmed anything.
    """
    proposals = [
        make_proposal(proposed_by=proposed_by, chosen_decision=did,
                      rationale=rationale, proposed_at=proposed_at)
        for did in (decision_ids or [])
    ]
    return make_interpretation_link(proposals=proposals)


def affirmation_status(link):
    """Read the affirmation status of a link, defaulting to 'proposed'."""
    if not isinstance(link, dict):
        return AFFIRMATION_PROPOSED
    aff = link.get("affirmation") or {}
    return aff.get("status", AFFIRMATION_PROPOSED)
