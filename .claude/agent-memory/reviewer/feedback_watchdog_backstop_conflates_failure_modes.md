---
name: watchdog-backstop-conflates-failure-modes
description: When reviewing a latch/watchdog state machine fed by external events, check whether the watchdog's stated "no END ever arrives" trigger actually has two causes (dead/gone vs. still alive and just running long) that need different handling -- and whether the plan's own prior research already flagged the deciding DCS behaviour as unverified.
metadata:
  type: feedback
---

Found reviewing `plans/emitter-visibility/plan.md` Stage B (`AC-B8`/`BL-B73`, 2026-10-15,
`feature/emitter-events` @ `f02ec43`). `EmitterTracker` (aircraft-layer collector) used
`FIRING_WATCHDOG_S=10.0` to bound a `START` with no `END` -- but the plan's own death-removal path
(`S_EVENT_DEAD`/`_CRASH`) already handles "unit destroyed mid-burst" immediately and independently.
The watchdog's only real job is the *other* cause of "no END yet": the unit is alive and still
firing, and the burst has simply run longer than the watchdog window -- exactly the sustained-AAA
scenario this feature exists to surface. A 10s watchdog silently ends a sighting mid-attack if DCS
does not retrigger `S_EVENT_SHOOTING_START` mid-burst, which the project's *own* prior research note
(`aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md`) had already
flagged as **not documented** -- and neither the Architect plan nor the Implementer re-surfaced that
open question at the point where the implementation came to depend on it.

**Why:** a watchdog's docstring tends to name only the scary failure mode (unit destroyed, event
lost) because that's the one everyone remembers to design for. The quiet failure mode -- "the normal
case just runs longer than the timeout" -- doesn't announce itself in the Co-moving Fields table or
the Risks section, because nobody writes "and also: don't let the timeout fire during ordinary
operation" as a risk, it reads as obviously implied. It isn't: the two causes share one mechanism and
one constant, and tuning the constant for one makes it wrong for the other unless the value is
checked against realistic sustained-duration numbers, not just "generously above any plausible single
burst" asserted in prose with no probe behind it.

**How to apply:** whenever reviewing a latch/watchdog/timeout state machine fed by external events
(DCS or otherwise), separate every path that sets "no event has arrived in time X" into its actual
causes, and ask whether each one has its own already-correct handling elsewhere (here: death removal)
that makes the watchdog's *only* remaining job the "still happening, just slow" case -- which is the
one a short timeout breaks. Then check whether the deciding fact (does the triggering event
retrigger/refresh during the ongoing condition, or fire once at onset) is actually known, by grepping
the project's own prior research notes before accepting "set generously above any plausible
duration" as settled. A documented-as-unverified DCS behaviour that an implementation has come to
depend on, with the dependency unflagged in the new plan/implementation, is a Required Fix, not an
optional note -- it's exactly the class of thing `CLAUDE.md`'s Investigator role exists to resolve
*before* a plan depends on it, and the gap here was that nobody re-ran that check at implementation
time even though the open question was on disk the whole time.

See also [[feedback_verify_state_not_the_account_of_it]] if present -- same family: the account (plan
Risks section) said the watchdog was a settled backstop; the state (the Lua handler's own one-shot
write to `PB_ACTIVE_FIRING_UNITS` on `SHOOTING_START` with no mid-burst refresh) said otherwise.
