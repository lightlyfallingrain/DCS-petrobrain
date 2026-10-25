---
name: 9k113-search-and-choose-look-scaling
description: Measured cost of the 9K113 sight's per-poll search-cycle sweeps (negligible, both pre- and post-boresight-rotation) and of choose_look's pre-existing O(n^2), now fed a wider candidate window by sight_can_still_improve
metadata:
  type: project
---

From the performance review of `feature/9k113-narrow-search`, two batches:
`78aebc04..5e917840` and the feature's own non-merge commits `5e917840..8cb3c527`
(`plans/9k113-narrow-search/performance-review.md`, "Batch 2" — two merge commits inside that
range pull in unrelated `main` work and are excluded, confirmed by `git show --stat` on each
non-merge commit that none of them touch `optic_policy.py`/`logger.py`/`perception/geometry.py`).

**Batch 2 superseded the µs/poll figures below with ~10× higher ones — still negligible, but do
not quote the Batch 1 numbers as current.** Batch 2 added a real vector rotation
(`perception.geometry.body_relative_direction`, via the new `heading_relative_to_body_relative`)
to every sweep step and every per-contact `look_target_for` call, replacing what was previously
pure `atan2` arithmetic or a cheap `bearing_deg`+`asin` pair (F5, boresight-relative regard
check — `docs/acceptance/2026-10-20-sortie-feedback.md`). Re-measured end-to-end, real production
functions, `body-layer/.venv`:

| what | Batch 1 (pre-rotation) | Batch 2 (post-rotation + regard filter) |
|---|---|---|
| sweep sequences, worst case | ~26.37 µs/poll | **495.8 µs/poll** (measured worst case across scenarios) |
| `look_target_for`, per contact | not separately measured | 4.07-4.10 µs/contact (223.7 µs @ 55, 819.3 µs @ 200) |

Both stay 2-3 orders of magnitude under the 1.0 Hz poll budget (worst case 0.0496 %). The order
of cost is unchanged (linear in step count / contact count, both hard-bounded quantities); only
the constant moved. If a future change adds *another* rotation or per-step cost on top of this
one, re-measure rather than assuming headroom from the Batch 1 figures — the ceiling has already
moved once.

**BL-B85's `attempted_at_level`/`pending_attempted_at_level`** (Batch 2) extend
`OpticState`'s per-contact dicts from three to five, same no-pruning pattern as
[[project_optic_policy_dict_copy_cost]] — isolated 5-dict `dict(...)` copy cost measured at
1.58/6.14/19.32 µs for 55/300/1000 contacts (roughly 2× the 3-dict figure, as expected). Same
MONITOR disposition as the dicts it extends: memory growth, not per-poll CPU cost, is the actual
long-run concern, and that is Security's territory.

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

## `choose_sighting_look` (BL-B89 Stage 1, `9k113-scan-procedure`) only shrinks `choose_look`'s own k, never grows it

New wrapper buckets `targets` by `current_level` ("class" before "presence") in O(n), then runs
`choose_look`'s O(k²) on only the highest-priority non-empty bucket — `k` is always a subset of
the same `targets` passed in, so this call is cheaper than or equal to calling `choose_look`
directly on the full list, at every split. Measured (`body-layer/.venv`, synthetic `LookTarget`s,
`plans/9k113-scan-procedure/performance-review.md`):

| n | class fraction | `choose_look` | `choose_sighting_look` |
|---|---|---|---|
| 55 (largest recorded sortie) | 0.5 | 962 µs | 241 µs |
| 200 | 0.5 | 12.74 ms | 3.24 ms |
| 200 | 0.9 (worst case, one bucket absorbs nearly everything) | 12.59 ms | 10.25 ms |

Worst case (skewed bucket) converges toward `choose_look`'s own cost, never exceeds it — so this
wrapper inherits `choose_look`'s existing MONITOR disposition rather than adding a new one. No
re-measurement needed unless `choose_look` itself is changed.
