---
name: feedback-retry-window-magnitude-vs-flown-evidence
description: When a fix's bound was derived from the mechanism's own internal timeout rather than the flown evidence, check the bound against the evidence's own numbers before trusting the fix closes the bug
metadata:
  type: feedback
---

A bounded-retry/timeout fix can be mechanically correct (bounded, gated, no duplicate side
effects, well tested) and still not close the bug it was written for, if the chosen bound's
magnitude was derived from the *mechanism's own* internal timeout rather than from the actual
observed failure duration in the evidence that motivated the fix. These are independent axes —
"is the retry logic correct" and "is the retry window big enough to have covered what was
observed" — and a review that only checks the first looks complete while missing the second.

**Worked example (BL-16 M4 SAU-take debug fix, `plans/flight-lift-vector/debug-2026-11-28-sau-
take.md`, commit `15235ea7`).** The debugger found `effector_engine.advance` gives up
permanently on a non-absolute effector's readback after 5 s (`EFFECTOR_CONDITION_READBACK_WAIT_S`)
and added a `SAU_TAKEOVER_RETRY_WINDOW_S = 10.0` retry window at the fire site — "twice the
engine's own 5 s give-up budget." That derivation never referenced either flown sortie's own
timing. Re-reading the cited logs directly (not just the debug note's prose) found: sortie 1's
SAU-off write actually landed ~39 s after the take-edge (grepped `lv2-aircraft_layer_debug.log`
lines 2956-2965 directly); sortie 2 showed zero writes for the full ~46 s the flight trace logs
before recording stopped (read `lv3-aircraft_layer_flight_trace.log`'s own `t=` values end to
end). **Both numbers exceed the 10 s window** — replayed through the patched code, neither flown
case would actually recover inside the new retry window. The debug note's own "What a re-fly
should show" section stated the window "may still lose the handover on a long stall" as a residual
risk, without ever computing that the *only* two data points available both already exceed it.

**Why this is easy to miss**: the fix reads as complete — root cause found, test added that proves
the retry mechanism itself works, checks pass. The missing step is arithmetic, not logic: subtract
the edge timestamp from the write timestamp in the raw log, and compare that number to the chosen
constant. Nothing about reviewing "is this retry correct" surfaces it; only reviewing "does this
retry's *magnitude* match what was flown" does.

**How to apply**: whenever a plan/debug note proposes a timeout, retry window, or deadline sized
by reference to an *internal* mechanism constant (a sibling timeout, "twice X's own budget", a
round number) rather than by reference to the *external* evidence (the flown log, the bug report,
the measured latency) that motivated the fix, pull the actual duration out of that evidence
yourself before approving. If the evidence's own duration exceeds the chosen bound, say so as a
required fix (or at minimum a required disclosure to the user) even though the retry mechanism
itself is correct — approving a correct-but-undersized fix as if it closes the bug is the
failure mode, not the retry logic.
