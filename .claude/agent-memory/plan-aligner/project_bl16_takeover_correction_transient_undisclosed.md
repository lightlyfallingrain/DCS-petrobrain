---
name: bl16-takeover-correction-transient-undisclosed
description: a two-phase correction can bound an overshoot without disclosing it as expected -- check a convergence fix's own measured numbers for the magnitude it still lets through, not just whether it converges
metadata:
  type: project
---

BL-16's revised Stage P1 (2026-11-16, "takeover after the Batch A flights") fixed ED's AI-pilot
park-sink bug with a closed-loop altitude correction. The rehearsal probe found a wild barometric
target (+740 m) on takeover; a single hold straight to the handover altitude would let the aircraft
climb the whole time it takes to bring the target down. The pilot's own fix, taken verbatim into
the plan as a two-phase correction (phase 1: hold toward live current MSL to stop the climb early;
phase 2: hold toward the fixed handover snapshot to finish the job), **bounds** the climb but does
not eliminate it — the probe's own numbers show the aircraft still climbed ~130–140 m above the
handover altitude (920 → 1050 m) before phase 2 brought it back down.

The plan presented phase 1 as *the fix* for the climb, correctly citing the single-hold case as
worse, without separately stating the bounded case's own residual number as an expected, disclosed
transient. The task's explicit check ("nothing should climb/dive harder than the bug itself would")
caught it: ED's bug sinks the aircraft; the fix's fallback path (which the plan's own data shows is
the common path, not rare — the quick path only works when the wild target's AGL-equivalent is
under 700 m, and both measured instances of the bug put it above that) visibly climbs it instead,
by a comparable magnitude, as a side effect of curing the sink.

Mitigating factor noted but not treated as sufficient: the pilot designed this two-phase workaround
himself from having watched the climb during his own manual testing that day, so the mechanism
isn't invented without his exposure to it — but a test card and risks list that don't name the
transient as *expected* leave it readable as a regression on the next sortie, by someone (possibly
the pilot himself, weeks later) who doesn't have today's probe log in mind.

**How to apply**: when a plan's own fix for an overshoot/transient cites measured numbers to argue
the fix is needed, check whether those same numbers also bound how much of the original problem
the fix *still lets through* — a mechanism that reduces an overshoot from "unbounded/worse" to "a
measured, still-nontrivial amount" needs that residual amount stated as expected behaviour on the
test card and in Risks, not left implicit in the probe log that motivated the fix. This is the same
shape as [[project_scan_reshape_ahead_latency_vs_decay_revisit]] (a plan computing one number and
treating it as the complete answer to a different, related worry) and
[[project_bl_b110_fifth_pass_allowance_floor_plateau]] (a fence doing less than its own wording
below a breakpoint) — generalizes to: a mitigation's own measured residual is itself a finding, not
just confirmation the mitigation works.
