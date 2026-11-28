---
name: effector-sequence-give-up-is-permanent
description: belief.effector_engine.advance gives up permanently (zero writes, no retry) on a non-absolute effector's unresolved readback -- fine for cosmetic sequences, a real trap for a safety-critical one (BL-16 M4 SAU handover, 2026-11-28)
metadata:
  type: project
---

`belief.effector_engine.advance`'s one-shot `read_args` readback, once a sequence-row run's read
keeps failing past `EFFECTOR_CONDITION_READBACK_WAIT_S` (5.0s sim time), gives up and treats every
arg as unknown. For a **non-absolute** effector shape (any momentary button -- `default_square_
button`, which is every curated SAU/OBSERV/weapons button in this codebase), an unknown self-check
readback **skips the row with only a `logger.warning`, never writes** -- and the trigger's run is
then removed from `EffectorRunState.runs` and **never retried** until the next genuine edge
(`fire_trigger` on a fresh transition). This is deliberate, documented, and tested
(`test_effector_engine.py::test_e2_non_absolute_unknown_readback_skips_with_warning`) -- explicitly
contrasted in the module's own docstring against the *other* kind of run (`request_write`'s ad hoc
single-target writes), which *do* keep retrying on the same failure because "a rule-originated
write is a command the pilot explicitly asked for."

**Why this was fine for every sequence before BL-16 M4**: takeoff, mission-start, seat-change,
OBSERV, weapons-arm/safe are all either re-triggerable by the player repeating the action, or low-
stakes/cosmetic. **Why M4's `CONTROLS_TO_PETROVICH` broke this assumption**: a lost SAU-off
handover leaves the SAU fighting the lift-vector control law for the rest of the flight, with no
spoken or logged signal reaching the player (only a `WARNING`-level log line) -- exactly the kind
of silent, permanent, safety-relevant failure this project's "fail loud" posture is supposed to
rule out everywhere else.

Debugged in `plans/flight-lift-vector/debug-2026-11-28-sau-take.md`: two sorties showed the
handover either never firing (zero `device=10` cockpit-switch lines ever) or firing ~39s late.
Could not pin the *exact* cause of the underlying readback stall from available evidence (no
body-layer stderr log was kept for either sortie -- see [[flight-ack-path-invisible-in-export-log]]
for the same gap found once already, 2026-11-23, on the analogous flight-take-ack path). Fix
applied: a bounded retry **at the `body.py` fire site only** (`ConsolePerceptionRunner.
sau_takeover_retry_until_sim`, `SAU_TAKEOVER_RETRY_WINDOW_S = 10s`, twice the engine's own 5s
budget) -- deliberately *not* changing `advance`'s shared give-up semantics, since every other
sequence depends on that contract staying as documented/tested; widening it would be an Architect-
level design decision, not a bug fix.

**Lesson for any future safety-critical effector-sequence trigger**: before assuming the engine's
existing "give up silently, never retry" behaviour is acceptable, ask whether losing that one write
has a *cost* beyond "the player can just repeat the action." If yes, it needs its own bounded
retry at the fire site (this pattern), not a silent reliance on the shared engine's low-stakes
default.
