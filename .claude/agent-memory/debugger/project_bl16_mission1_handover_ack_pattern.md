---
name: bl16-mission1-handover-ack-pattern
description: BL-16 flight channel -- a handover readback must wait for fd_acks the same way on both directions; take_controls had the ack gate, release_controls did not, and the asymmetry was the bug
metadata:
  type: project
---

Debug pass 2026-11-23 (`plans/flight-lift-vector/debug-2026-11-23.md`, problem 1): when BL-16
Stage 3 moved the handover onto the numbered `flight` channel, `take_controls` got the correct
"wait for `fd_acks`" treatment (`PendingTake`/`resolve_pending_take`), but `release_controls` kept
speaking its line (`config/rules/flight.lua`'s `i_have_controls` rule: `if r.acted then say(...)`)
the instant the request was *queued*, not once Lua had actually processed it -- `acted=True` is a
local belief-state decision, true a poll interval (and a round trip) before the real release lands.
The sortie report ("I have controls" -> seat change -> "you have controls" -> still held) is exactly
this window.

**When one of a pair of symmetric actions (take/release, arm/disarm, park/unpark) gets a
request/ack mechanism and its mirror doesn't, check whether the mirror needs the identical
treatment before assuming "it's simpler, so it doesn't need it."** The fix here was a direct copy
of the take-side shape: `pending_release_says` mirrors `pending_take_says`,
`flight_pending_release` mirrors `flight_pending_take`, both resolved by the *same*
`resolve_pending_take` function (no new logic needed, just reused on the second field). See
[[bl16-estimator-fabricated-zero-pattern]] for the other defect found the same pass.
