---
name: project_callout_scheduling_stages
description: Callout-scheduling Slice A/B split mechanics, fixture-timing gotcha, and the plan-vs-mechanism defect found in the 2C transcript worked example.
metadata:
  type: project
---

Implemented `plans/callout-scheduling/plan.md` on `feature/callout-scheduling-and-aggregation`
(two commits: Slice A `bd7c150`, Slice B `a0b21df`). Baseline 842 passed/4 xfailed; final 858
passed/4 xfailed (842 + 10 Slice A + 6 Slice B).

**Building two revertible commits from one design pass.** I wrote the full design (scheduler +
grouping together) first to validate it end-to-end, then split for commit history: reverted
`speech.py` to git HEAD, hand-wrote a Slice-A-only `callouts.py` (no `group_candidates`, `tick()`
treats each event as its own singleton candidate, no import of `belief.speech`'s private
helpers), committed that with Slice-A-only tests, then restored the full versions from a
scratchpad backup and committed the diff. Backing up the full files before starting the split
(`cp` to the scratchpad dir) made the second half trivial — the full version is a strict superset
of the Slice-A version, so no re-derivation was needed.

**Fixture-timing gotcha for the 7→4 acceptance test.** Bunching all 7 candidate events at `t=0`
and polling forward only produced 2 spoken lines, not 4: the two closest-range candidates (BTR-70
and truck identifications, "very close") consumed the whole occupancy budget back-to-back before
the two infantry groups' shared `CALLOUT_MAX_AGE_S=10s` deadline (counted from `t=0`) arrived. This
is a real demonstration of the plan's own stated caveat ("do not expect aggregation alone to hit
two") but not proof grouping collapses 7→4 in isolation. Fix: stagger the founding events over
~18s of sim time (t=0, 4, 8, 12), matching how a real sortie actually produces detections — each
group then gets spoken well within its own deadline.

**Real plan defect found (the "fifth" one, per this task's own framing).** The plan's "Applied to
the sortie transcript" paragraph writes the 3-member infantry group as `"three infantry, ..."`, but
the mechanism it explicitly says to reuse (`speech._cardinality_phrase`, tightened to require every
member attended+exact before speaking a number) renders lo=3/hi=3 unattended identically to
lo=2/hi=2 unattended: `"a couple of infantry, ..."` (the `lo >= 2 and hi <= 3` branch covers both).
Implemented per the actually-reused mechanism, not the plan's prose; the acceptance test asserts
the real output and documents the mismatch in its own docstring rather than silently matching the
plan's worked example.

**Geometry trick for controllable clock/range in tests.** With `project_terrain_aware` monkeypatched
to an identity passthrough (existing convention in `test_crew_console.py`/`test_speech.py`), a
contact's enriched `relative_now` (clock/range) is driven entirely by its *founding observation's*
`ownship_at_observation.x/z` against a fixed `EnrichmentContext.ownship` at the origin — completely
independent of `derived_world_position` (which drives `Contact.last_position`, i.e. spatial-gate
matching). This lets a test give two contacts identical displayed clock/range while keeping them
gate-separate (far-apart `derived_world_position`), or vice versa. `bearing_deg(observer, target) =
atan2(delta_z, delta_x)`, so clock 12 = +x, clock 3 = +z, confirmed by running it rather than
assumed from the docstring.
