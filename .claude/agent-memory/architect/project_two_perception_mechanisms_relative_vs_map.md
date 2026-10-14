---
name: project_two_perception_mechanisms_relative_vs_map
description: Petrobrain has two distinct perception questions — "where is it on the map" (perturbed, biased, world-anchored) and "where is it relative to me right now" (exact while looked at) — and BEARING_SIGMA_DEG only models the first
metadata:
  type: project
---

**User direction, 2026-10-14**, `docs/acceptance/2026-10-14-attack-run-guidance-direction.md` §18,
first consumer `plans/attack-run/plan.md` Decisions 16/17.

| | question | error model | consumers |
|---|---|---|---|
| **world-anchored belief** (`PositionBelief`) | where is this unit *on the map* | `BEARING_SIGMA_DEG=3.0`, `RANGE_FRACTIONAL_SIGMA=0.17`, plus a per-object systematic bias at `SYSTEMATIC_BIAS_FRACTION=0.4` of single-look sigma that **never averages out** | reporting, grouping, memory, world-feature references |
| **ownship-relative observation** (new) | where is it *relative to me, right now* | exact at `RELATIVE_DIRECTION_SIGMA_DEG = 0.0`, a parameter so a value can be given later | attack-run guidance only (fenced) |

**Why:** `BEARING_SIGMA_DEG`'s own docstring says it models *"the crewman's own pointing
precision"* — i.e. **stating** a bearing. It is the right model for *"ground, two o'clock, two
kilometres"* and the wrong one for *"come left"* while watching the thing. Most world-position error
is *ownship's own* and cancels in a relative observation. The user's proof of independence is
pre-GPS: an Mi-24P crew can be badly lost and still guide a gun run exactly, because guidance never
passes through the map.

**How to apply.**

1. **Ask which question a consumer is really asking** before reaching for `Contact.position`. If it
   wants a relative quantity (alignment, *"break right"*, ATGM tracking), the world-anchored
   estimate charges it a describing-error it should not pay. If it wants a map claim (*"edge of the
   forest"*), the relative channel cannot answer it at all — *"use the better channel everywhere"*
   is the wrong generalisation and is the likely mistake. Filed as `BL-B62`.
2. **A relative datum must be bounded by the look, or it is a map read wearing a disguise.** In
   `BL-14`: set only for a cluster the detection gate admitted *this poll* with
   `live_los_clear is True`, and usable only within `ATTACK_RUN_RELATIVE_MAX_AGE_S`.
3. **Carry the offset, not the finished angles — this is measured, not taste.** The crew poll loop
   runs at 1.0 s (`logger.py:_DEFAULT_POLL_INTERVAL_S`). In a 45° bank turn at 220 km/h the heading
   rate is `g·tan45/V = 9.2°/s`, so an azimuth frozen at the observing poll is ~9° stale one poll
   later — nearly 2× the 5° lined-up band. Carry an ownship-frame offset and re-rotate against
   *current* attitude each poll; the residual is then ownship translation (~1.7° at 1 km worst case)
   plus target motion (~0.5°).
4. **The no-omniscience protection is structural, not informational, and say so.** A relative offset
   plus ownship's exact telemetry *is* convertible to a world position. The fences that do the work
   are (a) a grep test restricting the field to the projection plus one consumer, mirroring
   `test_belief_source_never_references_derived_world_position`, and (b) never writing it back into
   belief. The `live_los_clear` precedent (`plans/dcs-driven-los/plan.md`) is weaker than it looks
   here: its own words are *"only the yes/no fact of whether a ray was clear"*, and this datum
   carries true relative position. Claim the precedent for the *shape*, not for the strength.

**The one quantitative trap.** The world-anchored fallback's azimuth residual is **not** the
cross-range bias everyone quotes. From the same aspect it is 1.20° (1σ, scale-invariant). But the
**down-range** bias is 3.2× larger in metres (`0.4 · 0.17 · R`) and rotates into cross-range as the
aircraft circles, giving **3.89°** at every range — 78% of a 5° band at 1σ, over it at 2σ. A pylon
turn around a target group is exactly the case. Elevation residual is ~0.46° at 120 m above the
target and ~1.07° at 300 m — it scales with the depression angle and is not a constant.

See also [[project_last_alt_m_is_the_ownship_altitude]] (the vertical half's input, and the
world-model query this distinction removed).
