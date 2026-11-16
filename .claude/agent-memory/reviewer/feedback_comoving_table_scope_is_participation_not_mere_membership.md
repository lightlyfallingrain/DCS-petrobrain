---
name: comoving-table-scope-is-participation-not-mere-membership
description: a new dataclass field does not automatically need a row in a plan's Co-moving Fields table -- the table tracks fields that participate in a multi-write state machine, not every field the dataclass happens to carry
metadata:
  type: feedback
---

[[bl16-comoving-table-missed-amendment]] and [[bl16-comoving-table-rising-edge-still-missed]]
both found real uncovered write sites in BL-16's "Co-moving Fields" table (`plans/flight-control/
plan.md`) for fields that *are* part of the align/recovery/mode-cycle/takeover state machine
(`correction_path`, `correction_substage`, `takeover_stage`). Reviewing `feature/seat-change-
triggers`, which adds `ParkedFlightState.player_seat`, I checked whether this new field also
needed a table row and concluded no: the table's own scope (its header: "an align/recovery
sub-state-machine with fields written externally ... and internally") is about fields with
*multiple* writers or that participate in a transition the table exists to keep consistent.
`player_seat` has exactly one writer (`advance_parked_flight_state`, a straight feed mirror) and
one reader (a trigger-firing comparison, not a second write), the same shape as several existing
`ParkedFlightState` fields already excluded from that table (`ai_mode`, `held_heading`,
`raw_arg_852`, `takeover_stage`'s own sibling diagnostic mirrors). Those earlier misses were real
because the fields in question *did* participate in the state machine and the table's own grep
instruction was simply never run; this is a different question -- whether the field belongs in the
table's scope at all -- and answering "no" without running the grep is not the same failure mode.

**How to apply**: before treating a dataclass-field addition as needing a Co-moving Fields (or any
similar write-site ledger) entry, check what the table's own stated scope is (read its header
sentence, not just its row shape) and whether the new field has more than one writer or
participates in the tracked transition -- a simple feed-mirror field with one writer and only
*consuming* readers is not automatically in scope just because it lives on the same dataclass as
fields that are. State the reasoning in the review rather than silently assuming either "every new
field needs a row" or "this table doesn't apply to me" -- both are the kind of unstated premise
this project's "read every X, so Y claim as two claims" habit exists to catch.
