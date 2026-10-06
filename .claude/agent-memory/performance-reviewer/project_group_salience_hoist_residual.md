---
name: group-salience-hoist-residual
description: BL-11 Stage 2's hoist measures 5.1x not 8.1x; the missing 1.6x is angular_separation_rad rebuilding observer-relative vectors per pair.
metadata:
  type: project
---

`group_salient_ids`'s hoisted pair loop measures **5.1×** over the pre-Stage-2 baseline, not the
`2026-10-05-performance-review.md` finding 1's **8.1×**, and the ratio **saturates at 5.1× from
~2,500 pairs upward** — still 5.1× at 169 k pairs, nearly double a sortie's ~96 k.

**Why:** `clustering.angular_separation_rad` recomputes `a - observer` and `b - observer` on
every pair. The observer-relative difference vector is a *per-candidate* quantity, so Stage 2
hoisted four of five and left the fifth inside the O(n²) loop. Carrying those vectors in the
`_resolvable_terms` pass (keeping `atan2(|cross|, dot)` verbatim, output bit-identical) gives a
further **1.6×**, total **8.0× at 58 k pairs** — i.e. exactly the note's figure. Inlining
`_cohesive_from_terms` instead buys only 1.1×; the function call per pair is *not* the cost.

**Why the per-pair unit cost reconciles anyway:** the note's 215 ms at ~96 k pairs is 2.24
µs/pair; a dense-band 134.2 ms at 58,311 pairs is 2.30 µs/pair. The absolute baseline is the
same measurement; only the pair count differed. So the implementer's O(*resolvable*²) reasoning
was right about absolute cost and **wrong about the ratio** — the ratio does not scale with pair
count, and a flight will come back at 5×, not 8×.

**And the residual does not matter, which is the other half of the lesson.** The full-poll harness
put `group_salient_ids` at **1.1 ms median / 5.5 ms max** in situ, because the real in-bubble
candidate count is **median 232 at 440 objects** (min 32, max 434) — the player bubble sheds most
of the field, and every finding-1 figure had assumed 440. The declined 1.6× would save ~0.4 ms of
a 12.6 ms poll. So the *claim* was worth correcting and the *code* was not.

**How to apply:** when a prototype's speedup is quoted against a shipped implementation, measure
the shipped one — a prototype that inlines is not the code that ships. When a ratio is claimed to
"rise with scale", check it at a scale above the one in question; this one plateaus. And before
asking for a micro-optimisation, get the in-situ number: a 1.6× on a term that is 1.1 ms is a
finding to record, not a change to request.

Related: [[project_divides_between_and_group_tick_multiplicity]],
[[project_group_reporting_cohesion_scale]].
