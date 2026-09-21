### Implementation Summary

Implemented sub-slice **2A only** of the detection-cones slice 2 plan: per-optic per-tier
multipliers, per-op_class/per-type distinctiveness, the class-range clamp, and the
`clustering.py` acuity-floor fix. 2B/2C/2D (gaze, `ScanPlan`, scan-loop state,
`naked_eye_source.py` acquisition-set changes) were explicitly not touched, per scope.

### Files Changed

- `body-layer/src/perception/optics.py` — `Optic` loses `magnification`, gains
  `presence_range_mult`/`class_range_mult`/`type_range_mult`. `UNAIDED_OPTIC` = 1.0/1.0/1.0.
  `BINOCULAR_OPTIC` = 2.42/3.50/3.00 (BTR-60-derived, decisions doc). No longer imports from
  `visibility.py` (deleting `BINOCULAR_RANGE_MULTIPLIER` dissolved the circular import). 9K113
  wide/narrow multipliers (3.55/7.00/6.50, 5.81/13.75/15.00) are **not** added as named `Optic`
  instances — documented in the module docstring and referenced only where the clustering-floor
  derivation needs the narrow sight's 5.81, per the plan's explicit scope cut.
- `body-layer/src/perception/object_model.py` — `ObjectTypeProfile` gains
  `distinctiveness: float | None = None`. New `_OP_CLASS_DISTINCTIVENESS = {"OP_INFANTRY": 5.0}`,
  `_DEFAULT_DISTINCTIVENESS = 1.0`, and `distinctiveness_of(profile)` (per-type exception, else
  per-class default, else 1.0/"ordinary"). Both S-300 radar rows get `distinctiveness=2.6`
  (per-type exception, since `OP_LRSAM` also covers non-radar launchers).
- `body-layer/src/perception/visibility.py` — `_achieved_tier` now takes `optic: Optic` and
  `distinctiveness: float` instead of a flat `magnification`. Three thresholds, each chained
  through `min()` against the tier above it: `presence = size/LOWRES*presence_mult`,
  `class = min(presence, extent/MEDRES*class_mult*distinctiveness)`,
  `type = min(class, extent/HIRES*type_mult)`. The chained `min()`s make `type <= class <=
  presence` a structural guarantee, not a separately-checked clamp (plan step 4). The admission
  gate now uses `optic.presence_range_mult` (was `optic.magnification`). `BINOCULAR_RANGE_
  MULTIPLIER` deleted; `optics.py` imports collapsed to an ordinary top-level import (circular
  import gone).
- `body-layer/src/perception/clustering.py` — `cluster_candidates`/`_separable` take a new
  required `presence_range_mult: float` parameter, threaded into floor (A) instead of the
  hardcoded `BINOCULAR_RANGE_MULTIPLIER`. This is the fix for the latent defect the plan's "hard
  part 4" identifies: the old self-consistency proof for (A) only held while the active optic's
  presence multiplier was ≤ 4.0, and 9K113 narrow's 5.81 (not wired in this slice, but real)
  would have broken it.
- `body-layer/src/perception/naked_eye_source.py` — passes `UNAIDED_OPTIC.presence_range_mult`
  into `cluster_candidates` (the only optic `check_visibility` is called with today — no
  optic-selection mechanism exists until 2B).

### Tests Added

- `test_optics.py::test_binocular_optic_has_the_btr_60_derived_per_tier_multipliers` — pins the
  three BINOCULAR_OPTIC values.
- `test_object_model.py::test_ordinary_class_defaults_to_1` /
  `test_infantry_class_default_is_5` / `test_s300_radar_rows_carry_a_per_type_exception_not_the_
  class_default` / `test_per_type_exception_overrides_the_class_default` — `distinctiveness_of`'s
  resolution order (per-type exception, per-class default, global default).
- `test_visibility.py::test_tier_thresholds_never_invert` — property test, `type <= class <=
  presence` across every named profile in `object_model`'s two keyword tables × both shipped
  optics (plan step 4's mandated invariant test).
- `test_visibility.py::test_infantry_class_clamps_to_presence_at_every_optic` — the model's main
  evidence for decision 3: infantry's class threshold saturates to its own presence threshold at
  every optic (a range just inside presence still resolves `medres`, never `lowres`).
- `test_clustering.py::test_floor_would_have_broken_under_the_old_hardcoded_constant` — proves
  the clustering-floor defect directly: a pair admitted at the 9K113 narrow sight's real
  `presence_range_mult` (5.81) satisfies (A) when checked against that same multiplier, but fails
  (A) when checked against the old hardcoded `BINOCULAR_RANGE_MULTIPLIER` (4.0) — the exact
  mismatch the parameterisation fixes. Also confirms `cluster_candidates`, correctly
  parameterised, still resolves the pair as separate clusters.
- `test_visibility.py::test_binocular_presence_threshold_for_a_7m_object` — the new, correctly
  derived binocular presence threshold (5646.67 m for a 7 m object), replacing the ground-truth
  claim the xfail below documents as broken.

### Fixture/expected-value changes, with derivation

All derived from the model's own formulas (recomputed by hand and verified by running the
suite), not back-fit from observed output:

- **Infantry can no longer produce a presence-only (`lowres`) observation at any optic** (its
  `distinctiveness=5.0` saturates class to presence by design — this is decision 3's point).
  Every test that relied on an Infantry candidate landing in a genuine lowres-only band was
  switched to a non-distinctive object (Ural truck or T-72B, `distinctiveness=1.0`) at a
  re-derived boundary range:
  - `test_visibility.py`: `test_infantry_just_inside/outside_lowres_tier_range_*` →
    `test_armored_vehicle_just_inside/outside_lowres_tier_range_*` (T-72B, 500–2333.33 m band).
  - `test_visibility.py::test_default_optic_is_naked_eye`'s `downgraded_tier_candidate` → T-72B
    at 2000 m (presence 2333.33 m, class 500 m) instead of Infantry at 300 m.
  - `test_naked_eye_source.py::test_lowres_range_candidate_reaches_presence_level` → Ural truck
    at 1000 m (class 428.57 m, presence 2000 m) instead of Infantry at 400 m.
  - `test_detection_trace.py::test_admission_records_achieved_tier` — Infantry at 250 m now
    resolves `medres` (class threshold 600 m, clamped to presence), not `lowres`; expected value
    updated in place (this test isn't about the tier value specifically, just the trace
    mechanism, so the object wasn't swapped).
  - `test_visibility.py::test_higher_magnification_optic_extends_the_range_threshold` — Infantry
    at 610 m under `BINOCULAR_OPTIC` now resolves `medres` (class clamps to presence, 1452 m),
    not `lowres`.
- **`test_vision_calibration.py`** — this suite is CONTAMINATED (detection-aid dots) per its own
  docstring; 2A moved two real, known quantities:
  - `test_computed_tier_matches_ground_truth`/`test_gate_admits_every_photographed_range` needed
    `optic=BINOCULAR_OPTIC` passed explicitly (the function's new default is `UNAIDED_OPTIC`, a
    much tighter gate, since the old default resolved to the flat `BINOCULAR_RANGE_MULTIPLIER`).
  - Two genuine regressions, both `pytest.xfail`ed (not silently re-fit, not deleted) with
    `_KNOWN_TIER_REGRESSIONS`/`_KNOWN_GATE_REGRESSIONS`: `C-8890m`/`C-6580m` (gate) — an 8 m
    object's binocular presence threshold is now `8/0.003*2.42 = 6453.33 m`, below both real
    photographed ranges, because `BINOCULAR_OPTIC.presence_range_mult` (2.42, BTR-60-derived) is
    lower than the old flat 4.0 that `LOWRES_ANGULAR_RADIUS_RAD` was itself derived against at
    this exact 8.89 km ground-truth point. `C-1000m` (tier) — same mechanism for
    `type_range_mult` (3.00 < 4.0): the row now resolves `medres` instead of the photographed
    `type_recognizable`. Every other row (`C-5040m` down to `C-503m`) still matches.
  - `test_visibility.py::test_armored_vehicle_is_visible_at_the_farthest_photographed_range` —
    same underlying regression, `xfail`ed with a full derivation in the reason string; a new
    passing test (`test_binocular_presence_threshold_for_a_7m_object`) pins the actual new
    threshold instead.
- **`test_calibration_cluster_merge_undercount.py`** — all four `cluster_candidates(...)` calls
  needed the new required `presence_range_mult` argument. Passed `BINOCULAR_OPTIC.presence_
  range_mult` (2.42), not `UNAIDED_OPTIC`'s 1.0: this fixture's own 9 km detection range is only
  physically plausible under an optic with binoculars' reach (a 7 m object's `UNAIDED_OPTIC`
  presence threshold is 2333 m — `check_visibility`'s real gate would never admit this candidate
  in the first place under naked eye). Using `UNAIDED_OPTIC` here made floor (A) bind at naked
  eye's own coarser resolution and merge the fixture's "resolves individually at 9 km" headline
  case — documented in the module's own docstring, not silently switched without explanation.

### Checks

(body-layer/ only — no other subproject touched)

- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (strict): pass, no issues in 38 source files
- `pytest -q`: pass — 778 passed, 4 xfailed (baseline was 774 passing; net +4 xfail are the
  documented, real known regressions above, not silently swallowed failures)

### Notable Discoveries

- **The plan's "vehicle rows must not move" framing (step 6) was too narrow.** It reads as being
  about decision 3 (distinctiveness) only — but decision 1 (per-tier multipliers) *by itself*
  moves ordinary-vehicle calibration rows too, because `BINOCULAR_OPTIC`'s new presence/type
  multipliers (2.42/3.00) are lower than the old flat 4.0 the `LOWRES`/`HIRES_ANGULAR_RADIUS_RAD`
  constants were themselves derived against at specific ground-truth points (8.89 km/6.58 km for
  presence, 1000 m for type). This is a real, unavoidable consequence of moving from one flat
  multiplier to three independently-measured ones — the decisions doc's own "known unmodelled
  residual" note covers it in spirit, but the plan's step 6 statement should be read as "the
  *distinctiveness clamp* doesn't move vehicle rows," not "vehicle rows are immune to 2A."
  Reported here rather than silently worked around; all three known-broken rows are `xfail`ed
  with full derivations, not hidden.
- **The clustering-floor test fixture (`test_calibration_cluster_merge_undercount.py`) implicitly
  assumed binocular-level detection range all along.** Its own 9 km scenario is not reachable
  under `UNAIDED_OPTIC`'s real presence threshold (2333 m for a 7 m object) — the fixture
  predates optic multipliers entirely and was written when the default was `BINOCULAR_OPTIC` at a
  flat 4.0. Passing the plan-literal "active optic" (`UNAIDED_OPTIC`, since that's what
  `naked_eye_source.py` actually uses today) breaks the fixture's own headline claim for a
  physically real reason (naked eye can't resolve 18.7 m spacing at 9 km — the floor fix doing
  exactly its job). Kept the fixture's original premise by passing `BINOCULAR_OPTIC.presence_
  range_mult` explicitly instead, documented in the module docstring rather than silently chosen.
- **Distinctiveness (decision 3) turned out to interact with far more of the existing test suite
  than the plan's own "Infantry" framing suggested.** Every existing test that placed an Infantry
  candidate in what used to be a presence-only band broke, because infantry's
  `distinctiveness=5.0` structurally eliminates that band at every optic (class always saturates
  to presence). This is correct/intended per decision 3, but the blast radius was wider than a
  quick read of the plan implies — five separate test functions across three files needed a
  different (non-distinctive) test object, not just a value tweak.

---

## 2A.5: intake cap counts groups, not objects (2026-09-21)

### Implementation Summary

Implemented sub-slice **2A.5 only**, on top of merged 2A. `NakedEyePerceptionSource.poll()` now
clusters every gate-surviving candidate before the simultaneous-detection cap is applied, instead
of capping individual objects ahead of clustering. Admitting a cluster admits all of its members at
once, so a dense group larger than the cap is reported whole in one poll. Acquisition state stays
keyed on `object_id` (clusters have no stable cross-poll identity). The `on_change` defect — a
capped-out object/cluster being marked "previously visible" and never retried — is fixed: a
capped-out group's members are now excluded from `_previously_visible_ids` until actually admitted,
so the backlog drains over subsequent polls. No gaze/`ScanPlan`/scan-loop/dwell code touched (2B/2C/
2D out of scope, per the task).

### Files Changed

- `body-layer/src/perception/naked_eye_source.py` — `poll()` reordered: gate → cluster all
  survivors → cap clusters → emit. `NAKED_EYE_MAX_NEW_PER_POLL` renamed
  `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` (value unchanged, 3). New shared static
  `_select_capped_clusters(clusters, known_ids)`: finds clusters with ≥1 member not in `known_ids`,
  sorts nearest-first by each cluster's nearest member's own range, takes the first
  `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL`. `_acquire_on_change` and `_acquire_every_poll` now take/
  return `Cluster`s: `_acquire_on_change` computes `steady_ids = currently_visible_ids &
  _previously_visible_ids` and sets the new state to `steady_ids | admitted_ids` — this is the
  concrete fix (a capped-out cluster's not-yet-previously-visible members are excluded from both
  terms, so they stay eligible next poll). `_acquire_every_poll` mirrors this against `_acquired_ids`
  and emits every cluster whose members are now *all* in the acquired set. Module docstring points
  3-5 rewritten to describe the new order and the cap's new unit.
- `body-layer/src/perception/detection_trace.py` — one docstring reference to the renamed constant
  updated.
- `body-layer/tests/test_naked_eye_source.py` — see Tests Added below.
- `body-layer/CLAUDE.md` — the `naked_eye_source.py` and `detection_trace.py` Structure entries'
  descriptions of the old "Stage 2 scoping decision" (cap runs ahead of clustering, per-object)
  updated to describe 2A.5's actual behaviour; these were the only two references to the renamed
  constant outside code/tests.

### Tests Added

- `test_a_dense_group_larger_than_the_cap_admits_whole_in_one_poll` — the headline case: ten
  co-located, single-link-chained Infantry (10 m down-range spacing, confirmed by running the
  scenario to merge into one cluster, not assumed from the 20 m pairwise-merge case already in the
  suite) produce one `Observation`. Also asserts, via `DetectionTraceCollector`, that all ten
  `object_id`s individually reached `GateOutcome.ADMITTED` before clustering — the no-omniscience-
  leak check the task asked for.
- `test_a_capped_out_group_is_retried_and_the_backlog_drains_over_polls` — **replaces**
  `test_candidates_dropped_by_the_cap_are_not_retried_next_poll` per explicit user approval
  (2026-09-21). Reuses the existing 5-singleton-group fixture (`_CAP_TEST_RANGES_M`, cap=3).
  Expected counts derived from the model, not observed: poll 1 admits the 3 nearest (5 eligible,
  cap 3); poll 2 (same snapshot) — the 2 remaining groups are still eligible (their members were
  excluded from `_previously_visible_ids` last poll) and both fit under the cap, so both are
  admitted (`5 - 3 = 2`); poll 3 — nothing eligible, true steady state, `[]`. Docstring states what
  the test replaces and why, per the task's rewrite instructions.
- `test_continuity_survives_a_cluster_whose_membership_grows_between_polls` — object-keyed
  acquisition state check: a 3-member cluster emits `Observation` A; a 4th member joins on the next
  poll (still one cluster, confirmed by running the scenario); the grown cluster's
  `continues_observation_id` resolves to A via majority object-id overlap (3 of 4 members vote for
  A), which a per-cluster-id scheme could not do since no cluster id survives poll to poll.
- `test_more_new_candidates_than_the_cap_emits_only_the_cap_nearest_first` — unchanged assertions
  (renamed constant only); already exercises "angularly separated singleton groups are still capped
  at N groups per poll" since each of its 5 candidates is its own group under this fixture's
  geometry, so a separate test for that scenario would have been a near-duplicate.

Also fixed a now-stale comment in `test_a_cluster_splitting_gives_the_majority_child_continuity`
(`test_naked_eye_source.py`): its 4 candidates are one cluster, so under 2A.5 the cap never
throttles that scenario at all (a group is admitted whole regardless of member count) — the old
comment's "only 3 of 4 acquired" claim, true under the pre-2A.5 per-object cap, no longer describes
what the code does. The test's own assertions were unaffected (still `len(first) == 1`); only the
comment was wrong.

### Checks (body-layer/)

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass (`cd body-layer && mypy src`, per the CWD-only config-discovery note)
- `pytest tests -q`: pass — **780 passed, 4 xfailed** (baseline 778 passed / 4 xfailed; net +2 new
  tests, since the rewritten pinned test replaces one 1-for-1 and two new tests were added)

### Notable Discoveries

- **The plan's own affected-modules note ("Not touched: `clustering.py`") held exactly as stated.**
  `cluster_candidates`'s existing signature (a `Sequence[ClusterCandidate]` plus observer/presence-
  multiplier) already accepted "all gate survivors" just as readily as "the capped subset" — the
  reorder in `poll()` needed zero changes to `clustering.py` itself, confirming the plan's claim
  that this slice's whole cost sits on the calling side.
- **One existing test's own *comment* (not its assertions) went stale**, in
  `test_a_cluster_splitting_gives_the_majority_child_continuity`: its 4-candidate merged-cluster
  fixture happened to exercise exactly the case where per-object throttling and per-group throttling
  produce the same `len(first) == 1` result, but for different reasons (per-object: 3 of 4
  acquired, capped; per-group: 1 cluster admitted whole, cap never binds). The plan's own test-impact
  list didn't name this file, and a grep for the renamed constant caught it — worth flagging since
  it's exactly the "silent, not loud" class of miss the role instructions warn about: the assertions
  still passed, only the explanation was wrong.
- **`_select_capped_clusters`'s nearest-first ordering uses each cluster's *nearest member's own
  individually-computed range*, not a recomputed centroid distance.** `ClusterCandidate.range_m` is
  already the slant range `check_visibility` derived per-candidate before clustering ever runs, so
  reusing it avoids a second geometry computation and keeps "nearest-first" tied to the same range
  figure the pre-2A.5 code sorted on (just now taken as a per-cluster minimum instead of a per-object
  value). Not specified by the plan at this level of detail; recorded here as the design call.

#### Cost verification (plan step 6d)

Clustering now runs over every gate survivor rather than over at most the cap's worth. Verified
rather than assumed: `visible` is the same population either way — the 2026-09-21 trace measured
**17,487 admissions over 4,719 polls, ~3.7 per poll** — because clustering was always fed
gate-survivors; the cap merely truncated the list first. The union-find pair loop is therefore on
the order of a dozen comparisons per poll, and moving the cap after it changes which entries are
*emitted*, not how many are *compared*. Under `emit_mode="every_poll"` — what `--console` and
`--crew-text` actually run — clustering already covered essentially all visible candidates, so this
is a real ordering change only for `on_change`.

## 2B: gaze as a filter (2026-09-21)

Implemented in an isolated worktree (agent trial, `AGENTS.md` "Where work happens") on top of
`1e1f3f0` (tip of `feature/cones-2b-gaze-filter`, itself `main` + nothing). Scope: 2B only — no 2C
scan loop, no 2D dwell.

### Implementation Summary

- New `perception/gaze.py`: `Gaze` (frozen `center_azimuth_deg`/`half_width_deg`/`label`),
  `FULL_GAZE`, `within_gaze`, `gaze_for` (the peripheral-bypass rule), `gaze_from_relative_sector`,
  plus `RelativeSector`/`RELATIVE_SECTORS`/`_RELATIVE_SECTOR_WEDGE_DEG` moved down from
  `belief/attention.py` (hard part 5/8's setup) — `belief/attention.py` now re-imports them.
- `perception/geometry.py` gains `angular_delta_deg` (moved from `belief/attention.py`'s private
  `_angular_delta_deg`), imported by both `belief/attention.py` (`area_contains`) and
  `perception/gaze.py` (`within_gaze`) — the one piece genuinely shared between the two wedge tests
  (hard part 5).
- `perception/optics.py`: `Optic.boresight_azimuth_deg` deleted; `within_optic_fov` now takes the
  boresight as a call-time parameter. New `Optic.peripheral: bool` (default `True` so every existing
  synthetic test `Optic(...)` keeps constructing unchanged); `UNAIDED_OPTIC.peripheral=True`,
  `BINOCULAR_OPTIC.peripheral=False`.
- `perception/visibility.py`: `check_visibility` gains `gaze: Gaze | None = None`, evaluated first
  in the gate chain (ahead of the cockpit mask); `within_optic_fov`'s boresight is
  `gaze.center_azimuth_deg` when a gaze is active, else `0.0` (unchanged from the old pinned
  default) — an optic is pointed by the head, not the airframe.
- `perception/detection_trace.py`: new `GateOutcome.GAZE`, with a docstring note that a
  rear-hemisphere candidate now records `GAZE` instead of `COCKPIT_MASK` once a real gaze
  restriction is active, and why that attribution shift is accepted rather than "fixed" by
  reordering back (hard part 3).
- `perception/naked_eye_source.py`: `NakedEyePerceptionSource` gains `gaze: Gaze | None = None` and
  `peripheral_stimulus_ids: frozenset[int] = frozenset()`; each candidate's effective gaze is
  resolved through `gaze_for(candidate.object_id, self.gaze, self.peripheral_stimulus_ids,
  UNAIDED_OPTIC)` before `check_visibility` — `UNAIDED_OPTIC` hardcoded since this channel has no
  optic-selection mechanism yet (2D's job).
- `logger.py`: new `_active_gaze(tasks)` (the most recently created still-`pending` `scan_area` task
  carrying a `relative_sector`, resolved to a `Gaze` via `gaze_from_relative_sector`, or `None`) and
  `_apply_active_gaze(sources, tasks)` (assigns it onto whichever `sources` entry is a
  `NakedEyePerceptionSource`, a no-op for anything else). `ConsolePerceptionRunner.run_once` calls
  `_apply_active_gaze` every poll, after reprojecting relative areas and before polling sources.
- `todo/todo.md`: closed "Scan commands should drive naked-eye perception" with a note pointing at
  this slice and clarifying that dwell/tier-varies-with-time is still 2C/2D's job.

### Deliberate deviation from the plan's literal Implementation Plan step 9 wording

Step 9 says "Default stays `FULL_GAZE`… so both are no-ops." Hard part 3 also states "2B's default
is `FULL_GAZE` (±90°), which by construction rejects nothing the cockpit mask would not." **That
second claim does not hold**: `FULL_GAZE`'s half-width is 90° (reusing `RelativeSector.full`'s own
existing wedge), while the cockpit mask's `rear_cutoff_deg` is 130° (`cockpit_mask.py`) — a
candidate between 90° and 130° off the nose that the mask would admit would be silently rejected by
a `FULL_GAZE` default, which is not a no-op in the real cockpit envelope (only on fixtures that
happen not to place a candidate in that 40° band).

Implemented instead so the **regression gate is exact rather than approximate**: `check_visibility`'s
`gaze` parameter default is `None` (skip the gate entirely), `NakedEyePerceptionSource.gaze` field
default is `None`, and `logger.py`'s `_active_gaze` returns `None` (not `FULL_GAZE`) when no scan
command is pending. `FULL_GAZE` still exists exactly as specified (a named forward-hemisphere
constant, matching `RelativeSector.full`), but is reserved for an explicit "full" scan command
rather than being silently assigned as the always-on default. `test_visibility.py`'s
`test_default_gaze_is_none_and_does_not_narrow_the_cockpit_envelope` proves the distinction matters:
a candidate at 100° azimuth is admitted under the real default (`gaze=None`) and would *not* be
under a `FULL_GAZE` default. Flagged per the role instructions' "if you find yourself changing an
expected value, stop and report it" — this isn't a changed test expectation, it's a design choice
that resolves an internal inconsistency in the plan's own two statements about the same default,
in favor of the one that is this slice's own defining, named acceptance property
("2B must be behaviour-preserving by construction... with no command issued, the trace is identical
to the previous slice").

### Files Changed

- `src/perception/gaze.py` (new) — see above.
- `src/perception/geometry.py` — `angular_delta_deg` added.
- `src/perception/optics.py` — boresight moved off `Optic`, `peripheral` field added.
- `src/perception/visibility.py` — gaze gate (first in chain), boresight-from-gaze wiring.
- `src/perception/detection_trace.py` — `GateOutcome.GAZE`.
- `src/perception/naked_eye_source.py` — `gaze`/`peripheral_stimulus_ids` fields, per-candidate
  `gaze_for` resolution.
- `src/belief/attention.py` — re-imports `RelativeSector`/`_RELATIVE_SECTOR_WEDGE_DEG`/
  `angular_delta_deg` from `perception`, instead of defining them.
- `src/logger.py` — `_active_gaze`, `_apply_active_gaze`, wired into `ConsolePerceptionRunner.
  run_once`.
- `tests/test_gaze.py` (new) — unit tests for `Gaze`/`within_gaze`/`gaze_for`/
  `gaze_from_relative_sector`.
- `tests/test_optics.py` — `within_optic_fov` call sites updated for the new boresight parameter
  (mandated by the plan, not an incidental rewrite); two new `Optic.peripheral` tests.
- `tests/test_visibility.py` — gaze gate ordering/rejection/admission tests, the bypass invariant,
  the boresight-follows-gaze test, the default-is-None regression test.
- `tests/test_naked_eye_source.py` — gaze filtering, default-is-None, peripheral-bypass tests.
- `tests/test_logger.py` — `_active_gaze`/`_apply_active_gaze` unit tests plus one `run_once`
  integration test wiring a pending scan task onto a real `NakedEyePerceptionSource`.
- `todo/todo.md` — closed the "Scan commands should drive naked-eye perception" item.

### Tests Added

- `test_gaze.py` (13 tests) — `Gaze`/`FULL_GAZE` shape, `within_gaze` boundary + a genuinely
  non-axis-aligned angle (37°/42°) + a 180°-seam wraparound case, `gaze_for`'s bypass rule under
  both optics plus a synthetic non-peripheral optic, `gaze_from_relative_sector` parametrized over
  all four sectors.
- `test_optics.py` — `test_unaided_optic_has_peripheral_vision`,
  `test_binocular_optic_has_no_peripheral_vision`.
- `test_visibility.py` — gate-order/rejection/admission (`left` gaze), `GAZE` fires ahead of
  `COCKPIT_MASK` in the trace, the `gaze=None` default does not narrow the cockpit envelope (the
  test that pins the deviation above), the bypass invariant (rear-cutoff candidate still rejected
  with `gaze=None`), boresight-follows-gaze for a narrow synthetic optic.
- `test_naked_eye_source.py` — a narrow gaze filters an off-axis candidate, the default (`gaze`
  unset) does not filter, a peripheral-stimulus id bypasses a narrow gaze.
- `test_logger.py` — `_active_gaze` (none pending / resolves a pending relative-sector task /
  ignores a cancelled task / picks the most recently created pending task),
  `_apply_active_gaze` (sets gaze only on `NakedEyePerceptionSource` instances / clears it when
  nothing is pending), and one `run_once` integration test proving a pending `scan_area` task
  actually reaches a real `NakedEyePerceptionSource.gaze` through the poll loop.

### Checks (body-layer/)

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (`cd body-layer && mypy src`): pass, 39 source files, no issues
- `pytest tests -q`: pass — **810 passed, 4 xfailed** (baseline 780 passed / 4 xfailed; net +30 new
  tests, no existing expectation changed, xfailed count unchanged)

### Notable Discoveries

- **The plan's own two statements about 2B's default gaze conflict with each other** — see the
  "Deliberate deviation" section above. Worth a plan correction before 2C, since 2C's own docs
  ("Free scan covers 9-3 (210°) while the cockpit mask admits 8-4 (260°)") already correctly treat
  the mask's real envelope as wider than any single gaze wedge; only the 2B default-gaze claim was
  inconsistent with that.
- **`Optic.peripheral` defaulting to `True`** (rather than a required field) was a deliberate,
  minimal-footprint choice: `test_visibility.py` constructs three synthetic `Optic(...)` instances
  (`_MASK_ONLY_OPTIC` and two `narrow_optic`s) with no `peripheral` argument; making the field
  required would have forced touching those construction sites for a property irrelevant to what
  they test. Only `BINOCULAR_OPTIC` sets it explicitly `False`.
- **`_active_gaze` deliberately never reads the store's re-projected `AttentionArea`** — it reads
  `PendingIntent.area.relative_sector` directly and looks that up in `gaze.
  gaze_from_relative_sector`'s own body-relative wedge table, sidestepping `belief/tasks.py`'s
  documented `task.area` staleness caveat entirely (a relative sector's *direction* never goes
  stale, only its absolute world-bearing projection does, and this function never needs the
  latter). Not spelled out at this level of detail in the plan; recorded here as the design call.
- **Worktree-isolation trial (`AGENTS.md` "Where work happens", rule 2)**: ran cleanly end to end.
  No `git` conflicts, `body-layer/.venv` created ad hoc in the worktree (mirrors the standing
  pattern from earlier milestones — no dependency tooling existed before M1 either). The one
  friction point: this environment's Bash tool refuses heredoc/`>>` redirection from a
  worktree-isolated agent ("too complex to verify it stays inside the worktree") — worked around by
  using the `Edit` tool for every test-file append instead of shell heredocs. Worth knowing for the
  next isolated-implementer run: plan on `Edit`/`Write`, not `cat >>`, for appending large test
  blocks.
