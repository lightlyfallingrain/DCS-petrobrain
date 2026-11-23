---
name: project_bl16_release_ack_speech_untested_at_drain_site
description: BL-16 LV-0 debug pass (a2f462e0, 2026-11-23) fixed release_controls to defer "You have controls." behind fd_acks, mirroring take_controls -- but only the queuing half (_apply_flight_requests populating flight_pending_release) got a test; drain_flight_control's new resolution block that actually speaks the line was provably unguarded by any test (mutation: commented it out, full body-layer suite still passed 3785/3785).
metadata:
  type: project
---

Required fix in `plans/flight-lift-vector/review-debug-1123.md`: add a test calling
`CrewConsole.drain_flight_control` directly with a populated `flight_pending_release` and an
`acks` string that accepts/refuses/times out, asserting the spoken line and that the field
clears -- the same shape `TestResolvePendingTake` already has for the underlying decision
function, but nothing exercised it through the actual call site that speaks for a release.

**Pattern to watch for across this codebase**: a new "stage/defer behind an ack" mechanism tends
to get two halves tested unevenly -- the queuing/setup side (easy to assert against a fake
client/console state) gets a test quickly, but the later poll's resolution/speech side (needs a
pending state built up across two calls, with the right `acks` string) is the one that is
actually safety-critical and the one that gets skipped. This is the second time this exact
mechanism (`PendingTake`/`resolve_pending_take`, reused for take and now release) has had an
asymmetry bug between its two directions -- see [[feedback_verify_the_mechanism_a_comment_claims_not_just_the_behaviour]]
and the debugger's own `project_bl16_mission1_handover_ack_pattern.md`. When reviewing any future
extension of this mechanism (a third handover-like action, or another `PendingX` reuse), check
specifically whether the *resolution* call site -- not just the *queuing* call site -- has a
direct test.

**How this was found**: reading the diff and tracing the Lua write-path by hand did not surface
it -- the code is correct. Only mutating the new `if self.flight_pending_release is not None:`
block in `drain_flight_control` to `if False and ...` and running the full suite surfaced it (zero
failures). Reinforces `reviewer.md`'s "verify by mutation, per entry, not per set" -- this was a
single new conditional block, not an enumerated set, and it was still exactly the kind of thing a
set-level/diff-level read cannot catch.

Also noted, lower severity: the debugger's own report (`debug-2026-11-23.md`, "Checks run") named
`luac5.5 -p` as the Lua syntax check run, not `luac5.1` -- `aircraft-layer/CLAUDE.md` is explicit
that it must be 5.1 specifically (DCS's embedded version; a newer `luac` accepts syntax DCS
rejects). Re-running with the correct binary found no actual defect this time, but the debug
report's own account of what was verified was wrong. Worth checking which `luac` version a
debugging/implementation report actually used, not just whether it claims to have run one.
