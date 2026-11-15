---
name: inherited-trigger-check
description: When a goal inherits stages moved from a closed entry, check the trigger/precondition they assume was actually built; harness gate cells overstate same-group traffic vs flight (object continuity <600 s)
metadata:
  type: feedback
---

When a roadmap entry carries stages "moved" from another entry, check that everything those stages
assume upstream actually shipped. BL-B111 (2026-11-10) inherited Stage 4 text saying "Stage 2's
trigger now opens a check", while BL-B110's Stage 2 had been closed unbuilt (it would have fired on
only 5–15 points on honest numbers). Taken literally, the look would have been built and almost
never used.

**Why:** moved design text keeps its old premises, and nothing re-reads them until a plan is
written. The goal check is the cheapest point to catch that.

**How to apply:** for each moved stage, ask what event starts it, and whether that event exists on
`main` now. Also: body-layer's harness measures same-group re-sightings through the gate, but in
flight a same group within `OBJECT_ID_MEMORY_S` (~600 s) resolves through object continuity. So
gate-path traffic in flight is mostly new groups plus long-gap re-sightings, and a broad "is this
the same group?" trigger costs less in flight than the harness suggests. Unconfirmed by the user as
of writing; see `plans/expected-area-look/alignment.md` Q1. Related: [[user-confirmed-dcs-facts]].
