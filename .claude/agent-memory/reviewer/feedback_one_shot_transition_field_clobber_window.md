---
name: feedback_one_shot_transition_field_clobber_window
description: A single-slot one-shot wire field (flight_control_transition et al.) written by both a system decision (decide_flight_control) and a player action (take_controls/release_controls) in the same poll silently drops whichever write loses — check this whenever a fix adds a second writer to an existing one-shot field.
metadata:
  type: feedback
---

`body-layer`'s `CrewConsole.flight_control_transition` (and the sibling one-shot fields —
`flight_control_goal_transition`, `ai_pilot_goal_transition`) is a single Python attribute, not a
queue: whatever is in it when `_apply_flight_control` next runs is sent, and anything written to
it in between is simply gone. `body.py`'s own per-poll order is advance → apply (send/clear) →
drain (`decide_flight_control`, may queue a new one-shot) → ... → `_poll_transcripts` (player
commands, later in the *same* poll). That means a write from `decide_flight_control` and a write
from a player command dispatched later in the same poll land on the same field with no priority
rule — last write wins, first write never reaches the wire.

**Found in `plans/flight-control/review-handover-ack.md` (2026-11-20, BL-16 mode 1 handover-ack
fix, commit `5487ff0f`).** Fix (b) made `drain_flight_control` queue a self-generated `"release"`
on the ack-timeout (`TAKING → PILOT`) specifically so Lua is told to stop flying when belief gives
up. That queue write is a *new* writer added to an existing field whose only prior writers were
player-triggered (`take_controls`/`release_controls`). A player "take" or "release" transcript
processed later in that same poll silently discards the system's own release — reproduced by
calling `drain_flight_control` then `take_controls` back-to-back on the same `CrewConsole` and
watching `flight_control_transition` flip from `"release"` to `"take"` with no wire send of the
first in between. The debug report's own docstring claimed the fix closed this gap
unconditionally ("so belief and the aircraft never disagree about who flies for long") — true only
when nothing else writes the field first, which the fix never checked for.

**Why reading the diff alone doesn't catch this**: every new test for fix (b)/(c) exercised
`drain_flight_control` or `release_controls` in isolation. The gap only appears when you put two
writers of the *same* one-shot field on the same poll's timeline and ask which one survives —
mutation/reproduction, not reading the two test classes next to each other.

**How to apply**: whenever a fix adds a *new* writer to an existing one-shot/single-slot field
(any `*_transition` attribute in `crew_console.py`, or an analogous pattern elsewhere), ask who
else writes that same field and in what order within one poll. If a player-triggered write and a
system-decision write can land in the same poll, write (or demand) a test that calls both in the
sequence the poll loop actually uses and asserts the field still holds the one that must reach the
wire — don't accept "it's queued" as proof it's sent.

See also [[feedback_release_path_must_clear_what_a_take_path_assumes_is_none]] (a related
take/release-path state-leak class in the same module) and
[[feedback_lua_named_mutations_are_cheap_to_reproduce_directly]] (the general habit of reproducing
a Lua/belief-state claim rather than reading it).
