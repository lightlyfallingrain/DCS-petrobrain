---
name: bl16-mode1-batch-comoving-precedent-check
description: cbtm_break_entry_heading_deg flagged by implementer as missing a Co-moving row; checked against cbtm_action_sent precedent (never tabled either) before deciding not to require one
metadata:
  type: project
---

Reviewing BL-16's mode-1 batch (break turn/break away/rotor envelope/VRS, `plans/flight-control/
plan.md` Decisions 27-32), the implementer flagged (Departure 2) that Decision 32's new state
(`ParkedFlightState.cbtm_break_entry_heading_deg`) has no row in any Co-moving Fields table.

On its own this looked like exactly the shape of two prior required fixes on this same plan
([[bl16-comoving-table-missed-amendment]], [[bl16-comoving-table-rising-edge-still-missed]]) — but
both of those concerned the mode-2 **takeover** table, which carries an explicit "grep every write
site before merging" instruction and was unrelated to this field. [[comoving-table-scope-is-
participation-not-mere-membership]] says to check precedent and the table's own scope before
demanding a row.

Checking: `cbtm_action_sent` (the field `cbtm_break_entry_heading_deg` is co-moving with — same
functions, same capture/clear/read shape) was itself introduced in the P3+P4 batch and never given
a table row, and no prior review round flagged that. That is a real precedent for how this specific
field class (Python-side CBTM one-shot state bridging `ParkedFlightState`/`FlightControlState` at
one transition, as opposed to the Lua-side law state the mode-1 batch's own Decision 27 table does
track) is treated in this plan. Requiring a row for the new field without ever having required one
for the existing field it mirrors would be an inconsistent bar. Downgraded to an optional
refinement (a one-line note in the plan's prose, not necessarily a table row) rather than a
required fix.

**How to apply**: when an implementer self-flags a missing table row, don't default to requiring
it just because a same-named-table omission was a required fix elsewhere in the same plan — check
whether an *analogous existing field* (same shape, same functions) was already exempted by
precedent, and if so, apply the same bar consistently rather than ratcheting the requirement up
for the newer field only.
