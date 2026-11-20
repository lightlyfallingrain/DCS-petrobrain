---
name: deferred-readback-mechanism
description: how to defer a rule's say() output until an async ack without touching rule files, body-layer flight-desired-state BL-16
metadata:
  type: feedback
---

When a plan asks for "wait for an external ack before speaking" over an existing synchronous
rule-dispatch path (`rules/engine.py`'s `run_rule` -> `CrewConsole.handle_command`), the generic
mechanism is: stage the already-computed lines on a one-shot `CrewConsole` field at dispatch
time, and let the later code that actually performs the async send (here, `body.py`'s
`_apply_flight_requests`/`_apply_ai_pilot_wheel_goal`) claim and pair that staged text with
whatever id/seq it mints for the send. A FIFO queue of `(id, lines, sent_at)` resolved once per
poll against the ack feed, in strict id order (never arrival order), is enough to also get
"two commands in one breath, readback in the order spoken" for free.

**Why not touch the rule files**: the readback text is already fully and correctly computed at
dispatch time (mode-aware, via whatever dispatch-time state the action read) — only *when* it is
spoken needs to change. Rule authors never need to know the deferral exists.

**The dangerous edge, not obvious from the plan text**: not every one-shot field that a dispatch
sets corresponds to an actual async send this stage. If some command categories still go out on
an older/parallel channel with no ack at all (here: mode-2 HVRT/CBTM, not yet dual-written onto
the new numbered channel), staging their readback too means it is *never* spoken — nothing will
ever claim it. The "should this defer" check must be scoped exactly to the one-shot fields that
the current stage's wire-send code actually reads, not to "every flight-category dispatch."
Existing differential tests that still pass unchanged after the change are the cheapest proof
this boundary was drawn correctly (if CBTM's readback had been swept into deferral, its
pre-existing `assert lines == ["Aligning."]` test would have still passed — `handle_command`'s
*return value* is unaffected by whether the lines were printed or staged, which hid the bug; had
to check `pending_flight_readback_lines` explicitly to catch it).

**Second edge**: a staged-but-never-sent request (the wire send gets skipped this poll for an
unrelated reason, e.g. a mode flip discarding the transition) must be drained with an explicit
"speak unable now" at that same discard site, or the staged text leaks into the next, unrelated
dispatch's own staging field.

See `plans/flight-desired-state/implementation.md`, "Stage 3b" for the full writeup.
