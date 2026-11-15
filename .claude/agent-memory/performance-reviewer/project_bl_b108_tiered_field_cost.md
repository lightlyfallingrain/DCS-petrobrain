---
name: bl-b108-tiered-field-cost
description: BL-B108's correlated-noise field (estimation._tiered_field, _FIELD_FOURIER_K=256) costs 0.19-0.86 ms/air cluster depending on optic ladder depth -- unaided (the default optic) is the worst case, not an edge case. Linear per-cluster, no cache helps the per-call trig sum.
metadata:
  type: project
---

Measured 2026-11-01 on `feature/relative-distance-grouping` (`BL-B108`) @
`f8629e468e567d1129cc65292d6a4b5b886d9a4a`, body-layer venv, worktree source on `sys.path`. Full
report: `plans/relative-distance-grouping/performance-review.md`.

`perception.estimation._tiered_field` sums one `_field_value` (256-cosine RFF loop) call per
range-scale-ladder tier at or below the calling optic's own `k`. `UNAIDED_OPTIC` has the ladder's
largest `k` (1.0), so it is the **most** expensive case (4 tiers), not the cheapest -- and
`body-layer/CLAUDE.md`'s own invariant is that unaided is the *default* optic, not binoculars, so
the worst case is the common case, not a rare raised-binoculars moment.

Measured per-air-cluster cost (`perturbed_bearing_range`, one call per `_build_observation`, every
poll, for every currently-visible cluster, not just newly-admitted ones -- `emit_mode="every_poll"`
is the only mode the crew pipeline runs):

| optic | tiers | ms/cluster |
|---|---|---|
| unaided | 4 | 0.86 |
| binocular | 3 | 0.57 |
| sight_wide | 2 | 0.38 |
| sight_narrow | 1 | 0.19 |
| scope (outside ladder) | flat field | 0.22 |

Ground clusters pay 2x (`surface_range_estimate`'s cue A + cue B). Confirmed linear in cluster
count (n=10/50/200: 0.773/0.764/0.764 ms/cluster) -- the `functools.cache` on `_field_frequencies`
amortises only frequency-*table generation* (keyed on field_name/optic_class/length_scales/salt),
never the per-call trig evaluation, which depends on `coords` (true bearing/range) and is never
repeated across real clusters. The plan's own review round 1 raised "cache-key cardinality" as a
concern for this role to check -- that framing was slightly off-target: the cache was never meant
to amortise the per-call sum at all, only the one-time frequency derivation.

**At realistic "tens of contacts" scale this adds ~25-55 ms/poll** to a hot path that was
previously an O(1) table lookup (pre-`BL-B108`). Did not cross into NOW because: no hard real-time
budget exists yet for this phase (root `CLAUDE.md`), BL-11's own 1.000 s poll period has wide
headroom even over this, the poll's dominant cost is still elsewhere
(`describe_position`, [[project_bl11_measured_outcome]]), and `_FIELD_FOURIER_K=256` is itself a
deliberate, already-measured accuracy tradeoff (16-32 left per-optic realised variance 0.5-1.5x of
target) -- not an oversight to request down.

**How to apply:** re-check this specific path first if (a) a future feature raises typical
per-poll cluster counts well past "tens", or (b) Petrobrain Runtime sets a real per-poll budget --
this is the first new non-O(1) cost on this hot path and the one most likely to matter once a
budget exists. `_ladder_sorted()` (a 4-element sort, re-run fresh every `_tiered_field` call despite
the ladder being import-time-fixed for the process's life) is a candidate micro-optimisation but
measured as noise next to the 256-cosine sum itself -- not worth a change request alone.

Related: [[project_group_salience_hoist_residual]], [[project_belief_los_call_pattern]],
[[project_bl11_measured_outcome]], [[feedback_benchmarks_must_be_able_to_fail]].
