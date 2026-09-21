---
name: cones-slice2-design
description: Key structural decisions and traps found designing detection-cones slice 2 (gaze/scan/dwell) in body-layer
metadata:
  type: project
---

Detection-cones slice 2 (planned 2026-09-21, `plans/detection-cones-slice2/plan.md`) settled four
structural things worth not re-deriving:

**Gaze is a pure function of sim time, not a state machine.** `perception` must not import `belief`,
but gaze is driven by belief-level commands. Resolution: belief owns the *intent* (`PendingIntent` +
`AttentionArea.relative_sector`), `logger.py`'s runner reads it and hands perception a frozen
`ScanPlan`, and `gaze_at(t_sim, plan)` computes the cone. No state, so replay determinism is free
rather than managed.
**Why:** the obvious designs (state machine in perception, or gaze in belief) either violate the
module boundary or break replay.
**How to apply:** reuse this shape for any future perception behaviour driven by crew commands.

**Poll rate (1.0 s) vs `belief/decay.py`'s `OBSERVED_WINDOW_S = 5.0` is a genuine bound conflict.**
A scan cycle must be >=8 s to avoid aliasing sectors away at 1 Hz, but >5 s pushes every contact out
of "observed" certainty between visits. `OBSERVED_WINDOW_S` must be *derived* from the scan cycle
period once he scans (belief -> perception import is the allowed direction).
**Why:** the constant's 5.0 was chosen when Petrovich looked everywhere at once.
**How to apply:** any timing change in perception must be checked against decay.py's ladder
(`OBSERVED_WINDOW_S`, `POSITION_HALF_LIFE_S=30`, `LOST_THRESHOLD_S=120`) before the plan is final.

**`NAKED_EYE_MAX_NEW_PER_POLL = 3` is already an attention-bandwidth model** written before any
attention machinery existed. Do not add a second intake limiter without deciding whether it is the
same mechanism under another name.

**`clustering.py`'s floor (A) hardcoding `BINOCULAR_RANGE_MULTIPLIER` was flagged benign twice and
is not benign under per-tier optic multipliers.** The slackness proof holds iff the active optic's
presence multiplier <= 4.0 — true for unaided/binocular/9K113-wide, false for 9K113-narrow (5.81).
Fix is to pass the active presence multiplier in. Also `NAKED_EYE_RANGE_CAP_M = 10000.0`
contradicts the measured 18 km 9K113-narrow presence range; both are prerequisites the deferred
9K113 backlog item inherits.

**The attention gate is the optimisation, not a later perf pass** (user, 2026-09-21). Measured on
`~/cones-sortie.jsonl`: 350,913 candidate evaluations / 4,719 polls; 75.8% currently reach the
range gate. A 60-degree wedge keeps ~23% of those (~61k vs ~266k). So the gaze wedge goes FIRST in
the chain, ahead of the cockpit mask — cost of that ordering is that the trace stops reporting the
mask rejection rate, which is accepted because the mask is static and measurable offline.
**How to apply:** when a model change makes the system less omniscient, check whether it also makes
previously-too-expensive realism terms affordable — re-cost, don't carry forward old estimates.

**Attention bypass seam:** `salient_object_ids: frozenset[int]` on the source, empty by default,
filled later by an unbuilt attention-capture channel. Invariant: a bypass skips the *gaze gate
only* — never cockpit mask, range/size or terrain LOS. Salience redirects attention; it never
grants vision. Without that rule the bypass is a back door through no-omniscience.

**Naked eyesight is two channels** (user, 2026-09-21): narrow **focus** cone (scans within a
sector, 2 s per o'clock hour) + wide **peripheral** (poor acuity, excellent change detection,
event-driven). Peripheral is the principled answer to "what bypasses the attention gate" — it says
*why* rather than enumerating *what*. It does not destroy the wedge optimisation because it is
event-driven, not scan-driven.
**How to apply:** `Optic.peripheral: bool` (unaided True, binocular False) + the rule *a stimulus
bypasses the gaze gate only when the active optic has peripheral vision* makes the whole model
operative and testable with zero triggers wired — and gives binoculars a real cost (you lose change
detection) rather than a free acuity upgrade. Deferred: expectation suppression ("mind overrides
instinct" for expected changes) needs belief-side knowledge, wrong import direction.

**Scan-period arithmetic, settled:** 2 s per o'clock hour, sectors are 2 hours -> 4 s legs ->
`SCAN_CYCLE_PERIOD_S = 16`, `FOCUS_DWELL_S = 2`. Worst-case unobserved gap for a flank contact is
`CYCLE - FOCUS_DWELL = 14 s`. The bound is two-sided and both sides are real:
`CYCLE - FOCUS_DWELL < OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` (14 < x < 30) — the upper bound
exists because reaching 30 collapses `certainty_of`'s middle band entirely. Set
`OBSERVED_WINDOW_S = SCAN_CYCLE_PERIOD_S = 16`.

**`perception` cannot reuse `belief.attention.area_contains` for the gaze wedge** — different frame
(body-relative azimuth vs absolute bearing from an area centre) and no radius. Only the shortest-
angle helper is genuinely shared; it moves to `perception/geometry.py`. Not a duplication.

See also [[trig-fixed-point-proof]] — same lesson: re-verify a "provably slack/no-regression" claim
at the case the new design actually changes, not the case the old proof covered.
