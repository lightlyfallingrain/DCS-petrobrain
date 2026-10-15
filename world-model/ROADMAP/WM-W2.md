# WM-W2 — `feature/dcs-driven-los` — the mechanism works, its availability does not

- [~] **`feature/dcs-driven-los` ([[X-B29]]/[[X-B30]], Stages 1-3) — FLOWN 2026-10-05. The mechanism
  works; its *availability* does not, and that is the first real defect.** #status/in-progress #needs-flight Read from the logs
  rather than the cockpit, since a working LOS gate is invisible in flight
  (`aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md`).

  **What the flight proved.** 101,091 live verdicts, internally consistent
  (`live_los_clear = building_clear AND terrain_clear`, no contradictory rows), `los_skew_s` median
  0.16 s against a 3.0 s budget, and **no contact ever admitted on a `False` verdict**. The new
  capability fired: **9,861 rows across 118 distinct objects where terrain was clear and a building
  blocked** — including a `5p73 s-125 ln` launcher. Buildings have never occluded anything in this
  project before.

  **What it did not prove, and now blocks acceptance.** The feed is **intermittent**: 19% of polls
  carry zero verdicts, in **211 clustered outages** up to 20.7 s long, with the gap between
  verdict-bearing polls running to **60.9 s** at worst. So **only 23% of admitted contacts used a
  live verdict** — the other 77% silently fell back to the offline SRTM primitive with its 12 m
  tolerance, i.e. exactly the path the user has ruled obsolete for live use. Not truncation: only
  11 of 2,104 polls exceeded the 128-sightline cap, and the *missing* rows are the *nearer* ones.

  **`dcs.log` was not captured on this flight**, so the Hook's own `bridge_call_ms` /
  `units_in_wedge` / `sightlines_computed` counters — which exist to answer exactly this — were
  never read. **Capturing it is the single most valuable thing on the next sortie.** Clears when
  the feed is continuous and the fallback is the exception rather than the rule.

  Original entry follows. DoD PASSED on fixtures 2026-10-05,
  not yet merged, not yet flown.** Petrovich asks DCS directly whether terrain or a building blocks
  a sightline, cone-scoped to his gaze wedge, instead of approximating it from this subproject's
  SRTM grid; buildings occlude for the first time in this project. What a fixture cannot confirm, and
  what Stage 4's sortie must: whether the `atan2` heading convention inside the Hook script's
  `LOS_CODE` actually matches DCS's own Mission Scripting Engine convention (wrong would mean a
  silently mis-aimed wedge, not a wrong detection), whether a building actually occludes in the
  running game, whether the missed-AAA geometry now resolves without the 12 m tolerance, and whether
  the per-frame look-direction socket poll produces any felt stutter (no DCS-side Lua profiler
  exists to measure this offline). Acceptance card:
  `docs/acceptance/2026-10-05-dcs-driven-los-sortie.md`. Full record: `plans/dcs-driven-los/{plan.md,
  security-plan-review.md, implementation.md, review.md, security-deep-analysis.md, performance.md,
  dod-check.md}`; backlog entries `todo/backlog.md`'s [[X-B29]]/[[X-B30]].

## Decision, 2026-10-15 (user): observe, do not tune

**The residual no-verdict rate is accepted as-is for now**, and the attack-target LOS priority is
scheduled with `[[BL-B70]]` rather than pulled forward. The user's reasoning, which is the part
worth keeping because it decides when this becomes urgent again:

> *"This is highly dependent on density of targets in a given mission. If it's very dense then
> there's a lot of units to LOS and that is a real cost. If just a few units inside the player
> bubble then it's nearly free. A very dense scene is on the rare side, it may happen over large
> cities, but otherwise the scenarios typically are much sparser."*

So the cost is **a property of the mission, not of the code**, and tuning against the sparse case
would be tuning against the common case rather than the one that hurts. Coverage measured 77% on
2026-10-05 and 93–99% across the three 2026-10-15 sorties; the gate fails closed, so a miss costs
one tick of a contact treated as masked.

**What would reopen it**, concretely rather than as a feeling: the hook already puts
`units_in_wedge` and `sightlines_computed` on the wire side by side, and its own docstring states
the test — *"If `sightlines_computed < units_in_wedge` ever shows up in the log, the wedge is
wrong, not the budget."* A dense-city sortie is the scenario that would show it. **Read those two
numbers before changing `MAX_SIGHTLINES_PER_CALL` (128), the 90° wedge, or `LOS_MAX_AGE_S` (3.0)**
— all three were left deliberately unchanged pending exactly that measurement.
