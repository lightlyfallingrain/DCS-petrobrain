---
name: 9k113-search-and-choose-look-scaling
description: Measured cost of the 9K113 sight's per-poll search-cycle sweeps (negligible) and of choose_look's pre-existing O(n^2), now fed a wider candidate window by sight_can_still_improve
metadata:
  type: project
---

From the performance review of `feature/9k113-narrow-search` (`78aebc04..5e917840`,
`plans/9k113-narrow-search/performance-review.md`).

## The four new per-poll search sweeps: non-issue, measured

`logger.py`'s `run_once` now unconditionally computes four sweep sequences every poll
(`sight_wide_search`/`sight_narrow_near_search`/`sight_narrow_far_search`/
`sight_out_of_regard_search`, via `_sight_in_regard_sweep`/`_sight_out_of_regard_sweep`), mirroring
the existing `search` sequence's own unconditional computation. **Measured 15.85-26.37 µs/poll**
across default/`full`/`left`/`ahead` scan-plan scenarios (body-layer's own `.venv`,
`search_pattern` step counts 21-63 depending on scenario) — 0.0026 % of the 1.0 Hz poll budget at
worst. Not worth caching per commanded sector: correctness would also require bucketing on
`ownship.alt_agl_m` (elevation depends continuously on altitude via `atan2(agl, range)`, which
changes every poll in flight), real complexity for microseconds.

## `choose_look` is O(n^2) over its candidate list — pre-existing, not touched by this plan, but now fed a wider window

`optic_policy.choose_look`'s `covered()` closure is O(k) per candidate it's called on, O(k²)
overall for `k = len(worth_looking)` (the contacts that passed `is_worth_a_look`). Unchanged by
this plan. **Measured directly** (synthetic `LookTarget`s): 18.75 µs @ k=5, 275 µs @ k=20, 1.75 ms
@ k=50, 6.74 ms @ k=100, 27.66 ms @ k=200 — confirms ~4× per doubling.

**What changed**: the new `sight_can_still_improve` predicate (replacing `can_still_improve` as
the candidate-filter predicate while `SIGHTING`) has **no lower bound** and an upper bound
(`SIGHT_NARROW_OPTIC`'s class/type threshold) substantially wider than `BINOCULAR_OPTIC`'s
(`class_range_mult` 13.75 vs. 3.50, `type_range_mult` 15.00 vs. 3.00 — structural optic-table
ratios, not object-specific). So `worth_looking` can legitimately admit more simultaneous
candidates during `SIGHTING` than the eye/binocular window ever did during `SCANNING`/`GLASSING`,
feeding `choose_look`'s pre-existing O(n²) a larger practical `k` than before.

**Verdict at today's scale: still negligible.** This project's largest **recorded** sortie is 55
total contacts ([[project_optic_policy_dict_copy_cost]]), and `worth_looking` is a filtered subset
of total contacts, never larger — worst case (every contact simultaneously qualifying) costs
~1.7 ms. It would take ~150-200 *simultaneous* in-regard, in-window candidates — a scale never
recorded, and one the sight's own ±60° regard cone makes geometrically unlikely to fill — before
this became noticeable against the 1 s budget.

**Why this is worth remembering rather than re-deriving**: any future change that widens a
`SIGHTING`-path candidate window (another optic, a wider regard, a relaxed threshold) should be
checked against `choose_look`'s O(n²) specifically, since it is the one place in this call chain
whose cost is quadratic rather than linear in candidate count. If it ever needs fixing: spatially
prune by azimuth bucket before the O(k²) pass, an Architect question, not a thing to improvise.

See [[project_body_layer_poll_loop_diagnosis]] for the 1.0 Hz budget this is measured against, and
[[project_optic_policy_dict_copy_cost]] for the sibling `optic_policy.decide` per-contact-dict-copy
measurement from the same lineage of reviews.
