### Performance Review

Batch reviewed: `feature/9k113-narrow-search`, `78aebc04..5e917840` (tip
`5e9178406c65d13b90097fd527851f4f300775ad`). Stages 1-4 plus the review's required fix and two
follow-up rounds (F4 wide-band-far-edge, binocular-sector-centre fix), built and merged as one
batch per `implementation.md`. Touches `body-layer/src/belief/optic_policy.py` and
`body-layer/src/logger.py`. Budget: the body-layer poll loop's own 1.0 Hz default
(`logger._DEFAULT_POLL_INTERVAL_S = 1.0`, confirmed against the running constant, not a docstring
— see [[project_body_layer_poll_loop_diagnosis]]), no hard real-time budget in this phase.

**Can-this-fail probes run before every timing below**, per this role's own standing rule: each
benchmark script asserts a case the code must get right (an out-of-regard remainder for a
straddling sector, none for `ahead`; `choose_look(empty)=None` / `choose_look(single)=that
target`) before any number is trusted. Both passed.

### Findings

#### New per-poll sweep sequences (`sight_wide_search`/`sight_narrow_near_search`/`sight_narrow_far_search`/`sight_out_of_regard_search`)

- **Location:** `logger.ConsolePerceptionRunner.run_once`'s `decide_optic(...)` call
  (`logger.py:656` area) — four new sweep builders (`_sight_in_regard_sweep` ×3,
  `_sight_out_of_regard_sweep` ×1) computed unconditionally every poll, mirroring the existing
  `search` sequence's own unconditional computation.
- **Risk:** rebuilt from scratch every poll rather than cached per commanded sector — flagged
  explicitly in the dispatch for measurement.
- **Measured** (`body-layer/.venv`, same interpreter/PYTHONPATH as the subproject's own commands,
  5000 calls/scenario, can-this-fail probe run first — see above):

  | scenario | steps built (wide+narrow_near+narrow_far+out_of_regard+search) | time/poll |
  |---|---|---|
  | default (no commanded sector) | 11+20+20+0+0 = 51 | 15.85 µs |
  | commanded `full` (worst case: all 4 legs populated) | 11+20+20+8+4 = 63 | 26.37 µs |
  | commanded `left` | 3+5+5+4+4 = 21 | 17.40 µs |
  | commanded `ahead` | 6+10+10+0+4 = 30 | 15.70 µs |

  Worst case (~26 µs/poll) is **0.0026 % of the 1.0 s poll budget**, and smaller still against the
  ~300 ms median *work* budget this subproject's own 2026-10-05 review measured for a realistic
  sortie poll (`group_salient_ids` alone, unrelated subsystem). A caching layer keyed on
  `commanded_sector` would also need to bucket on `ownship.alt_agl_m` to stay correct (elevation
  depends continuously on altitude via `atan2(agl, range)`, and altitude changes every poll in
  flight) — real complexity bought for microseconds.
- **Action:** MONITOR (effectively a non-issue; recording the number so a future reviewer does not
  re-derive it from scratch).
- **Mitigation:** none needed. If this is ever revisited, cache on `(commanded_sector,
  round(alt_agl_m, -2))` rather than sector alone, to preserve correctness.

#### `can_improve` threading into `is_worth_a_look`/`look_is_finished`

- **Location:** `_decide_sighting`'s candidate filter (`worth_looking = [... is_worth_a_look(...,
  can_improve=sight_can_still_improve) ...]`) and its `look_is_finished(..., can_improve=
  sight_can_still_improve)` continuation check.
- **Risk:** a per-target predicate added to an existing per-target filter could turn an O(n) pass
  into something costlier if the predicate itself were expensive or newly uncached.
- **Checked:** `sight_can_still_improve` and the pre-existing `can_still_improve` both bottom out
  in `profile_for`, which is `@cache`d (`perception/object_model.py:557`, measured 0.93 → 0.04
  µs/call in the 2026-10-05 review) — so the new predicate is the same O(1)-per-call shape as the
  one it replaces. No new O(n²) is introduced by this threading; the candidate-filter list
  comprehension stays O(n) in contact count, same as before.
- **Action:** none (verified non-issue, not merely assumed).

#### `sight_can_still_improve`'s wider, one-sided admission window feeds a pre-existing O(n²) (`choose_look`)

- **Location:** `choose_look` (`optic_policy.py`, **unchanged by this diff**) is called on
  `worth_looking` once per poll while `SIGHTING`; its `covered()` closure is O(k) per candidate,
  O(k²) overall for `k = len(worth_looking)`.
- **Risk:** `sight_can_still_improve` has **no lower bound** (deliberately, per its own docstring —
  nothing dwells in parallel during `SIGHTING` to make a close look wasted the way the naked eye
  does during `GLASSING`) and its upper bound is `SIGHT_NARROW_OPTIC`'s own class/type threshold,
  which is substantially wider than `BINOCULAR_OPTIC`'s (`class_range_mult` 13.75 vs. 3.50,
  `type_range_mult` 15.00 vs. 3.00 — both structural properties of the optic table, not
  object-specific). So `worth_looking` can legitimately admit more simultaneous candidates during
  `SIGHTING` than the eye/binocular window ever did during `SCANNING`, and `choose_look` is
  unchanged, pre-existing O(n²) code that this diff did not touch but does feed more.
- **Measured** (`choose_look` directly, synthetic `LookTarget`s spread across the sight's own
  regard/range envelope, can-this-fail probe run first):

  | k (candidates in `worth_looking`) | time/call |
  |---|---|
  | 5 | 18.75 µs |
  | 10 | 70.74 µs |
  | 20 | 275.22 µs |
  | 50 | 1.75 ms |
  | 100 | 6.74 ms |
  | 200 | 27.66 ms |

  Confirms O(n²) (≈4× per doubling). At this project's own largest **recorded** sortie scale (55
  total contacts, [[project_optic_policy_dict_copy_cost]]) — and `worth_looking` is a filtered
  subset of total contacts, never larger — the pathological case of every contact simultaneously
  qualifying costs ~1.7 ms, trivial against the 1 s budget. It would take roughly 150-200
  *simultaneous* in-regard, in-window candidates (a scale this project has never recorded, and
  which the sight's own ±60° regard cone makes geometrically unlikely to fill with that many
  distinct contacts at once) before this cost became noticeable against the budget.
- **Action:** MONITOR, not NOW. This diff does not introduce the O(n²) (pre-existing, untouched)
  and does not make it fail today; it does make the pre-existing shape more reachable by widening
  the window that feeds it, so it is the first thing to look at if a future dense-target scenario
  (a large multi-vehicle convoy held in regard during a long `SIGHTING` dwell) ever makes `decide`
  show up in a poll-loop profile.
- **Mitigation (if ever needed):** `choose_look`'s own candidate-coverage check could be spatially
  pruned (bucket by azimuth before the O(k²) pass) rather than reworked wholesale — an Architect
  question if it is ever reached, not a change to make speculatively now.

#### Search-leg cycle advance (`_next_search_leg`/`_idle_sight_search`'s `first_nonempty_leg`)

- **Location:** `optic_policy._idle_sight_search`, the `first_nonempty_leg` inner loop.
- **Risk:** a cycle-advance mechanism that could loop unboundedly if every leg were perpetually
  empty.
- **Checked:** bounded at `len(_SEARCH_LEG_ORDER)` (4) iterations by construction, falls back to
  `_idle_sight_rest` (O(1), holds last aim) if every leg is empty — the plan's own "never reached
  in production" note for that fallback is consistent with `_commanded_or_default_sector` always
  yielding a non-empty in-regard span. O(1) per poll regardless of contact count.
- **Action:** none (verified bounded, not assumed).

#### Redundant geometry recomputation (`_commanded_or_default_sector`/`_split_sector_by_regard`)

- **Location:** `logger._sight_in_regard_sweep` (called 3× per poll — wide, narrow_near,
  narrow_far) and `_sight_out_of_regard_sweep` (1× per poll) each independently recompute the
  commanded-or-default sector and its regard split, rather than sharing one computation.
- **Risk:** none at current scale — each call is pure arithmetic over ~6 floats (no DCS/world-model
  dependency, confirmed from the functions' own docstrings), already included in the ≤26 µs/poll
  total measured above.
- **Action:** none. Not worth deduplicating for sub-microsecond savings; noted only so a future
  reader does not mistake the 4× repetition for an oversight.

### Comparison against `body-layer/research/2026-10-05-performance-review.md`

That review's one `optic_policy`-adjacent finding (`_look_targets` building a `LookTarget` per
contact every poll, MONITOR, same shape as `optic_policy.decide`'s own 0.08/0.45/1.46 ms at
55/300/1000 contacts) is unaffected by this diff — `_look_targets` itself is untouched. This
diff's own additions (the four sweep sequences, the `can_improve` predicate swap) stay inside that
same MONITOR-not-NOW posture: real, measured, linear-or-better in the dimension that matters, and
orders of magnitude under the budget at every scale this project has actually recorded.

### Second-order note for `BL-B66`

Per the plan's own "Second-order effect": once `BL-B66` gives `advance_sight_aim` a real,
non-identity slew duration, the per-poll cost shape here is unaffected (slew timing is a belief
concept living in `OpticState`/`OpticDecision`, not an additional per-poll computation) — flagging
only so a future performance pass on `BL-B66` does not need to re-derive this diff's own baseline.

### Verdict

APPROVED — MONITOR

---

## Batch 2

Batch reviewed: `feature/9k113-narrow-search`, the feature's own non-merge commits between
`5e917840` and tip `8cb3c52759bafdc6f6a020e605462b1e3131b346` — `bb6364b0` (elevation regard
filter on the idle search cycle), `451c5c45` (BL-B85 stall cooldown + `attempted_at_level`/
`pending_attempted_at_level` dicts, and the `_start_glance_away` commit-on-progress fix),
`49f92738` (F5: boresight-relative conversion via `heading_relative_to_body_relative`/
`body_relative_direction`), `9cba4943` (BL-B85 review required fix), `135e2414` (import-crash
floor + realistic-case test). Two merge commits in this range (`cce0b57a`, `88ac4200`) pull in
unrelated work from `main` (landmark-words, taking-fire-visible-shooter, speech-tilde,
voice-latency-instrumentation, etc.) — confirmed those merges touch no file this batch's commits
touch (`optic_policy.py`/`logger.py`/`perception/geometry.py`), so `git diff 5e917840..8cb3c527`
restricted to those three files is the actual batch diff, with no merge noise; verified against
each commit's own `git show --stat`. Budget: same as Batch 1, the body-layer poll loop's 1.0 Hz
default, no hard real-time budget in this phase.

**Can-this-fail probes run before every timing below**: `heading_relative_to_body_relative`
reduces to identity at zero attitude and is pitch-sensitive at non-zero pitch;
`look_target_for` is pitch-sensitive the same way; `dict(...)` copy semantics are real (mutating
the copy does not touch the original); and the end-to-end sweep benchmark asserts nose-down at
1000 m AGL recovers more wide-leg steps than level flight (the batch's own stated behaviour
change) before any `us/poll` number is trusted. All passed.

### Findings

#### `heading_relative_to_body_relative` / `_to_body_relative_steps`, called per sweep step per poll

- **Location:** `logger._to_body_relative_steps`, called once per raw step from
  `_search_sweep`/`_sight_in_regard_sweep`/`_sight_out_of_regard_sweep`, all three called
  unconditionally every poll from `run_once`'s `decide_optic(...)` wiring (same call sites Batch 1
  reviewed).
- **Risk:** replaces what was previously a near-free pass-through (`_sight_in_regard_sweep`
  returning `search_pattern`'s own steps directly) with a real vector rotation
  (`body_relative_direction`, two `GeoPosition`/`BodyRelativeDirection` dataclass allocations and
  several trig calls) per step, plus — for the three in-regard legs only — an additional
  `within_field_of_regard` bound check per step for the elevation-regard filter.
- **Measured** (`body-layer/.venv`, same interpreter/PYTHONPATH as Batch 1, 5000 calls/scenario,
  can-this-fail probe run first):

  | `heading_relative_to_body_relative` alone | |
  |---|---|
  | per call | 3.49 µs |
  | 51 steps (default) | 175.2 µs (rotation only, no regard filter) |
  | 63 steps (commanded `full`, worst raw step count) | 217.9 µs (rotation only) |

  End-to-end (the real `_sight_in_regard_sweep`/`_sight_out_of_regard_sweep`/`_search_sweep`
  functions, rotation **and** regard filter together, against production near/far-edge
  constants):

  | scenario | steps (wide+narrow_near+narrow_far+out_of_regard+search) | time/poll |
  |---|---|---|
  | default, level, 120 m AGL | 51 (11+20+20+0+0) | 204.5 µs |
  | default, 1000 m AGL, 5° pitch/-10° bank | 34 (7+14+13+0+0) | 423.6 µs |
  | commanded `full`, 1000 m AGL, pitch/bank | 58 (7+14+13+16+8) | **495.8 µs (measured worst case)** |
  | commanded `full`, level, 120 m AGL (nothing filtered, raw step count) | 63 (11+20+20+8+4) | 275.2 µs |
  | commanded `left`, 1000 m AGL, pitch/bank | 33 (3+9+5+8+8) | 182.2 µs |
  | commanded `ahead`, 1000 m AGL, pitch/bank | 26 (5+5+8+0+8) | 238.0 µs |

  An order of magnitude over Batch 1's pre-diff figure (15.85–26.37 µs/poll, pure `atan2`
  geometry with no rotation or filter) — expected, since every step now does a real 3-axis
  rotation instead of being returned as-is. Worst measured, **495.8 µs/poll, is still 0.0496 % of
  the 1.0 s poll budget** — three orders of magnitude under budget, and the step counts here are
  hard-bounded by `search_pattern`'s own step-centring (never grows with contact count or sortie
  length).
- **Action:** MONITOR (recording the re-measured number now that this diff is in, so a future
  reviewer does not have to re-derive it; non-issue at this scale).
- **Mitigation:** none needed.

#### `look_target_for` → `body_relative_direction`, called per target per poll

- **Location:** `logger._look_targets`, building one `LookTarget` per tracked contact every poll
  (unchanged call frequency from the 2026-10-05 review's own finding on this function — this
  batch changes what each call computes, not how often it is called).
- **Risk:** replaces the old `bearing_deg` + hand-rolled `asin` elevation (cheap, two trig calls)
  with a full `body_relative_direction` rotation (same cost shape as the sweep-step conversion
  above) — a real per-call cost increase, at a call frequency that already scales with total
  contact count.
- **Measured** (5000 calls/scenario for the per-call figure, 500 calls/scenario for the
  per-contact-count figure, can-this-fail probe run first):

  | | |
  |---|---|
  | `body_relative_direction` alone | 1.64 µs/call |
  | `look_target_for` (full, incl. the rotation) | 3.38 µs/call |
  | 55 contacts (this project's largest **recorded** sortie) | 223.7 µs/poll (4.07 µs/contact) |
  | 200 contacts | 819.3 µs/poll (4.10 µs/contact) |

  Confirms linear in contact count (4.07 vs. 4.10 µs/contact, flat as expected for a per-item
  O(1) operation). At 200 contacts — well beyond anything recorded — **0.082 % of the 1.0 s poll
  budget**. The 2026-10-05 review already flagged `_look_targets` itself as a MONITOR-not-NOW
  per-poll cost at this shape (0.08/0.45/1.46 ms at 55/300/1000 contacts, via `optic_policy.
  decide()`'s overall cost, not this function in isolation) — this batch's own per-call cost
  (~4.1 µs) is consistent with, not a new order of magnitude beyond, that existing posture.
- **Action:** MONITOR, same posture as the pre-existing `_look_targets` finding this extends — not
  a new risk category, a real but still negligible cost increase to an already-reviewed hot path.
- **Mitigation:** none needed at today's scale. If contact counts ever grow materially (a
  long-running campaign-style process, per `project_optic_policy_dict_copy_cost`'s own revisit
  condition), re-measure `look_target_for` specifically rather than assuming the old
  `bearing_deg`/`asin` figure still applies — it no longer does.

#### BL-B85's `attempted_at_level`/`pending_attempted_at_level` dicts — same no-pruning shape as the pre-existing range/time twins

- **Location:** `OpticState.attempted_at_level`/`pending_attempted_at_level`, populated and
  `dict(...)`-copied at every site `attempted_at_range_m`/`pending_attempted_at_range_m` already
  are (both `GLASSING` and `SIGHTING` commit sites, every interruption-drop site).
- **Risk:** two more per-contact dicts added to a state object that is already known to grow
  without pruning for the process lifetime (flagged independently by Security for memory, and by
  this role for runtime cost — `project_optic_policy_dict_copy_cost` memory). This batch does not
  introduce the no-pruning pattern; it adds two more dicts following the exact same pattern.
- **Checked, not assumed:** confirmed by `grep` that no call site ever removes a key from any of
  the five per-contact dicts (`attempted_at_range_m`/`attempted_at_time_sim`/`attempted_at_level`/
  the two `pending_*` twins) — every site either adds via `[contact_id] =` or resets the whole
  `pending_*` dict to `{}` on commit/drop, consistent with the pre-existing finding.
- **Measured** (isolated `dict(...)` copy cost for all five dicts together, 2000 calls/scenario):

  | contacts | 5-dict copy |
  |---|---|
  | 55 (largest recorded) | 1.58 µs |
  | 300 | 6.14 µs |
  | 1000 | 19.32 µs |

  Roughly 2× the three-dict figure the existing memory recorded in isolation, as expected for 5
  dicts vs. 3 — trivial at any of these scales (worst case 0.0019 % of the poll budget for the
  copies alone). The existing memory's own larger figures (0.084/0.447/1.46 ms at 55/300/1000
  contacts) measure `optic_policy.decide()`'s *entire* call, not the dict copies in isolation —
  this batch does not change that shape, since the two new dicts add the same O(1)-per-key copy
  cost the other three already pay.
- **Action:** MONITOR, same disposition the existing memory already recorded for the three-dict
  shape — this doubles the dict count but not the growth *pattern*, and the existing "revisit only
  if session length or contact-count assumptions change materially" condition already covers it.
  Not a new finding; recorded so a future reviewer does not mistake the added dicts for an
  unreviewed risk.
- **Mitigation:** none needed now. Memory accumulation, not CPU cost, is the actual limiting factor
  here and is already Security's territory, not this role's — restated so the boundary is explicit
  rather than silently assumed.

#### `_start_glance_away`'s new `current_level_by_id` dict comprehension over `targets`

- **Location:** `optic_policy._start_glance_away`'s new `{target.contact_id: target.current_level
  for target in targets}` — `targets` is every tracked contact's `LookTarget` (built fresh every
  poll by `_look_targets`, same list `_decide_sighting` itself receives), not a filtered subset.
- **Risk:** an O(total contact count) dict build looked, on first read, like it could be a new
  per-poll cost riding on top of the already-reviewed `_look_targets` cost.
- **Checked:** `_start_glance_away` only runs when `now_sim - dwell_started_sim >=
  SIGHT_MAX_DWELL_S` fires (`_decide_sighting`'s dwell-boundary check) — `SIGHT_MAX_DWELL_S` is a
  `tuning.real` bounded `lo=5.0, hi=120.0` (default 30.0), so this path executes **at most once
  every 5 seconds**, never once per poll. Even at 1000 contacts (an already-flagged
  beyond-anything-recorded scale), a dict comprehension of 1000 items is on the order of tens of
  microseconds — negligible against a 5-30 s firing interval, let alone the 1 s poll budget.
- **Action:** none (verified bounded by the dwell-boundary gate, not assumed from the function's
  own name).

#### `is_worth_a_look`'s `stall_cooldown_s` branch

- **Location:** `is_worth_a_look`'s new `stall_cooldown_s`/`attempted_at_level` comparison,
  inside the existing per-target candidate-filter list comprehension in `_decide_sighting`.
- **Risk:** a new branch added to an already-hot per-target predicate.
- **Checked:** two `dict.get()` lookups and an equality check — O(1), same shape as the
  pre-existing `attempted_at_time_sim.get(...)` lookup it sits beside. No new O(n) or O(n²)
  introduced; the candidate-filter list comprehension stays O(n) in contact count, same as Batch
  1 found for `can_improve`'s own threading.
- **Action:** none (verified non-issue, not merely assumed).

### Comparison against Batch 1 and the project's standing memory

This batch's two real additions — the boresight-relative rotation (sweep steps and look
targets) and the BL-B85 level-tracking dicts — both ride on call sites Batch 1 and the
2026-10-05 review already measured and approved (MONITOR) at this shape. Neither changes the
*order* of cost (both stay linear in their respective counts: steps per poll, contacts per poll,
contacts in the never-pruned dicts); both increase the *constant* by roughly 3-10× over the
pre-diff baseline, and both land one to three orders of magnitude under the 1.0 Hz poll budget at
every scale this project has recorded or is likely to record before Petrobrain Runtime's own
harder budget phase begins.

### Verdict

APPROVED — MONITOR
