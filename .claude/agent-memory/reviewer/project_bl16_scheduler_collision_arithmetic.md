---
name: bl16-scheduler-collision-arithmetic
description: How to check whether two independently-scheduled LAW_HZ-style periodic steps can collide on one DCS frame, without trusting a fixed-rate test loop
metadata:
  type: project
---

BL-16's lift-vector law (`plans/flight-lift-vector/`) gates expensive per-step work
(`law_update`, the estimator's `LoGet*` reads) to a shared `profile.law_hz` period instead of
running every DCS frame, with a "defer once on collision, then force through" rule so the law is
never starved under a coarse caller step. Reviewed LV-1's fix round (`review-lv1-fixes.md`,
2026-11-24): the implementer's own `TestLawHzScheduling` test only proves zero collisions at a
perfectly regular, fixed 140 Hz loop — it says nothing about whether the *force-through* branch
(which deliberately does not re-check the estimator's own due flag) can land on the same frame as
the estimator at a realistic jittery frame rate.

**The check that actually answers it: compare one frame's worst-case `dt` against the shared
period, not just run the existing test.** At the stated 40–200 Hz floor, one frame step is at most
`1/40 = 25 ms`; the shared period here is `1/law_hz ≈ 33.3 ms`. Since `25 ms < 33.3 ms`, the
estimator (or the law) cannot become due again within a single ordinary frame immediately after it
last fired — so the force-through branch, which only risks a real collision when the *other*
schedule also re-fires on that exact forced frame, is arithmetically unreachable within the stated
envelope. It only becomes reachable if two *consecutive* frames both exceed the shared period
(sustained sub-30 fps), which is below the stated floor and would need a live frame-time log to
rule out rather than an argument.

**How to apply:** any future stage of this law (LV-2/LV-3) or any other `*_due`/periodic-scheduler
pair in this codebase that adds a "collision defer, then force" rule needs this same
period-vs-worst-case-frame-time arithmetic, not just a fixed-rate scheduling test, before accepting
"never the same frame" as proven at the real DCS rate. If the shared period and the frame-rate
floor are ever close enough that a single frame could plausibly exceed the period (e.g. a lower
`law_hz` or a true sub-40fps DCS target), flag it as a required fix rather than an optional note.
