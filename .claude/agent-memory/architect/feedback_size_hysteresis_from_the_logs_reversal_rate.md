---
name: size-hysteresis-from-the-logs-reversal-rate
description: size a hysteresis band from the measured reversal rate, not the closing rate -- and if the signal genuinely reverses, a band alone is never sufficient and needs a minimum-interval guard beside it
metadata:
  type: feedback
---

**When a design needs hysteresis, pull both the median rate *and* the worst reversal out of the logs
before picking a band. The reversal rate is what sizes it, and the closing rate is the one you will
reach for by mistake.**

**Why:** planning the 2026-10-15 attack-run optic ladder, the obvious band (15% of the naked-eye
presence threshold, 350 m) looked ample until measured. From `dcs-belief-truth-*.jsonl`, the attack
target's own range series gave:

- median closing **−60 m/s**, not the ~17 m/s one 15-second slice of the feedback document implied
  — so the 350 m band is crossed in **under 6 s**;
- worst **opening** rate **+130 m/s** (the pilot flying past), which means **no band of any plausible
  width survives a reversal**.

So the conclusion flipped twice: the band needed widening (0.25), *and* a band alone was shown
insufficient, requiring a minimum-interval guard beside it. Neither was derivable without the logs,
and the per-slice figure already written in the feedback document was off by 4x against the run's own
median.

**How to apply:** for any threshold crossed by a moving signal, compute three numbers from real data
— median rate, worst rate in the intended direction, worst rate in the *reverse* direction. If the
reverse direction is non-trivial, plan for two guards (band + minimum dwell), and say in the plan
that a band alone was considered and rejected. Also look for a **free third guard**: here, the
already-required "go silent while the cockpit mask blocks the target" rule removed the fly-past case
at its root before any band or timer was consulted, because a fly-past *is* a mask event.

Sibling: [[find-n-in-the-repo-before-accepting-a-sizing-argument]] — same discipline, applied to a
count rather than a rate. Both say the same thing: the number is usually already on disk.
