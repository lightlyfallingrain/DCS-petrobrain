---
name: dcs-driven-los-cost-revision
description: X-B29 batched-LOS revision (2026-10-05) — per-call batch size is the real constraint, the Lua snippet must stay a fixed literal, and offline LOS agreement became an explicit non-goal
metadata:
  type: project
---

Four non-obvious things settled while revising `plans/dcs-driven-los/plan.md` on 2026-10-05.

**1. For anything riding the DCS mission bridge, budget the SINGLE CALL, not the duty cycle.**
The elevation probe throttled to one call per 250 ms and the user still felt a stutter, because one
2601-point call is 24 ms however far apart the calls are. Spreading calls bounds duty cycle only.
**Why:** DCS's own thread runs the payload, so a 24 ms call is 1.5 dropped frames at 60 fps. **How to
apply:** every bridge-call design needs a per-call item cap as a literal constant, plus the
`bridge_call_ms` self-measurement the velocity hook already established. Reject in-flight adaptive
caps — coverage that depends on unlogged history is unexplainable in a debrief.

**2. A Hook script's `dostring_in` snippet is a FIXED STRING LITERAL — this constrains architecture,
not just security.** `petrobrain-mission-telemetry-hook.lua`'s docstring: never built from network
input, mission data or any runtime value. **Why:** it means the collector cannot push a unit list, a
cap, or a priority order into the snippet. **How to apply:** any filtering, ordering or truncation for
a bridge feed has to be written *inside* the Lua literal, with its constants baked in — if a design
has the Python side choosing what to ask about, it is wrong on arrival.

**3. Don't take a research note's "comfortably above what we need" at face value — check the project's
own logs for the population figure.** The probe note concluded ~130 rays comfortably covers a 10 km
bubble; `research/2026-09-29-bridge-call-cost-at-scale.md` Finding 1 records a sortie carrying
**565–568 units**. The bubble subset is still unmeasured, and is derivable *with no flight* from
`dcs-detection-trace.jsonl` (rows per `t_sim` minus `GateOutcome.PLAYER_BUBBLE` rows = the 10 km
population). **How to apply:** when a cost argument rests on "N is more than we need", find the
measurement of N before accepting it; there is often one already on disk.

**4. Round-robin across polls is dead on arrival whenever a staleness bound already exists.** A 64-cap
over a 300-unit bubble at 1 Hz gives each unit a verdict every 5 s, against `LOS_MAX_AGE_S = 3.0` —
the join would discard four fifths of what the round-robin produced. **How to apply:** before proposing
"spread the work across ticks", multiply the split factor by the cadence and compare against the
consumer's own max-age constant. Truncate-and-degrade usually wins, especially when absence already
maps to a safe tri-state fallback.

**5. Aimed probes beat sweep differentials, and the repo had three aimed results already.** The
dispatch brief framed "`isVisible` sees buildings" as demonstrated (2 of 40 urban pairs). But Finding
12 fired 52 rays through 52 located buildings with zero blocked, Finding 16/19 showed SEGMENT hitting
three named buildings where `isVisible` returned clear at identical endpoints, and the new flight's own
aimed test was 6/6 clear. 2-vs-0 at n=40 is the same non-result as the earlier 1-vs-0 that note itself
called noise. **How to apply:** a sweep differential whose "control" baseline is computed by *our* coarser
sampling can be an artifact of the baseline, not a finding about the call under test. Prefer the aimed
test, and prefer designs that are correct under both hypotheses so the question stops being a gate.

See also [[provenance-confidence-pattern]], [[investigator-gating-pattern]].
