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
