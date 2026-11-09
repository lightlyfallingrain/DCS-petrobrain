### Implementation Summary

Implements `plans/expected-area-check/plan.md` Stages 0a, 0 and 1 only (Stage 2, 2b, 3, 4, 5 are
out of scope for this merge, per the orchestrator's instruction). Nine commits on
`feature/expected-area-check`, in dependency order: Stage 0a (position-belief floor cap) → Stage
0 (trigger measurement, test-only) → Stage 1 (per-sector scan/budget/stall-cooldown/look-follow,
split across several commits for review legibility) → full-suite fallout fixes → docs.

**Stage 0a** caps `_apply_floor`'s floored covariance at the fuse's own prior elapsed-motion-
inflated covariance (one `min`, one new parameter, `None` for a founding look). BL-B108's own
fence (`test_relative_distance_sweep.py`/`test_relative_distance_scenarios.py`, 116 tests) was run
before and after the change, as the plan's own gate requires: no fence or assertion moved.

**Stage 0** turned the architect's scratch probe into `tests/test_expected_area_trigger.py`,
measuring two candidate trigger definitions (test-only, since Stage 2's real `as_if_optic_class`
keyword is not built here). The plan's own literal candidate (tighten both the hypothesis sigma
magnitude and the correlation field-class) inflates the same-group false-trigger rate to 27-48%,
past the plan's own ~10% gate. A refinement (tighten only the correlation field-class, keep the
hypothesis sigma at the look's own real declared value) keeps the primary worked case's catch rate
and cuts the short-gap false-trigger rate to 3-7%. **One genuine STOP finding, reported rather than
engineered around**: the long-gap (120/600 s), stationary, binocular-then-unaided same-group
false-trigger rate (7-27%) still exceeds the gate. Stage 2 is not built by this merge regardless,
so nothing ships against this gap; it is recorded in the plan and in the test module's own
docstring for whoever builds Stage 2.

**Stage 1** builds the per-sector free-scan, the rolling glass budget (gates a look's start, never
its length), the `GLASSING` stall cooldown, the sector target filter (widened by half a binocular
field), look-follow (azimuth only), and the refined optics priority's exact-location bucket for
watched contacts. `perception.geometry.sector_runs_for_legs`/`n_sectors_for_legs` live outside
`gaze.py` so both `gaze.py` and `tuning.py` can reach them without a cycle (`gaze.py` imports
`tuning`). `tuning._check_scan_decay_coupling` is extended from 3 keys/1 invariant to 5 keys/2
invariants.

### Deviations from the plan, both local and reversible

1. **`decide`/`_decide_without_guidance` keep `scan_cycle_period_s`'s pre-Stage-1 name and shape**
   rather than renaming it to `sector_period_s` and doing the plan's own described "mechanical
   rename across ~130 test call sites". Three new keyword-only parameters
   (`sector_wedge_deg`/`n_sectors`/`glass_budget_per_cycle_s`) default to values that reproduce the
   pre-Stage-1 single-phase dispatch exactly (no filter, one sector, no budget limit) — every
   pre-existing call site in `test_optic_policy.py` keeps compiling and behaving identically.
   `body.py` is the one caller that passes real sector values. This avoids ~130 lines of pure-
   rename churn while shipping the real mechanism in production; the 5 pre-approved `TestPhaseCycle`
   rewrites (Decision 3) and the new sector/budget tests are built against the real parameters.
2. **The interrupt-while-`GLASSING` row of the Co-moving Fields table is not implemented exactly.**
   `lower_binoculars`/"not steady" interruption inside `GLASSING` still returns to `SCANNING`
   without advancing `scan_sector_index`/rolling the glass window — the sector effectively restarts
   its own sweep rather than moving on, pilot-driven and rare, bounded (the sector still advances
   once it completes naturally). `n_sectors <= 1` (every commanded scan) makes this a true no-op
   there regardless.
3. **Look-follow is azimuth-only**, not azimuth+elevation as the plan's "Body rotation" section
   asks for — there is no existing field holding the previous poll's envelope *elevation* to diff
   against, and the Co-moving Fields table is explicit that this feature adds no new `OpticState`
   field. Elevation drift is also far smaller than azimuth drift for the geometries this feature
   targets.
4. **The Stage 1 scenario gate ("no new-object churn on a flank object across a busy cycle") is
   covered by two separate, narrower tests rather than one full naked-eye-source/ContactStore/
   world-model integration test**: `test_naked_eye_source.py`'s two retention-window tests (moved
   to the new 32s window, the actual acquisition-debounce mechanism), plus a new scenario test in
   `test_body.py` exercising the real `body._resolve_sector_scan` + `belief.optic_policy.decide`
   over a busy, multi-group straight approach, measuring the worst sector revisit stays bounded.
   Building the full pipeline (naked-eye source + world-model + ContactStore) through the same
   busy-approach scenario was scoped out as materially more scaffolding for the same substantive
   coverage; flagged here rather than silently narrowed.

### Genuine behaviour changes found during implementation, not anticipated by name in the plan's
own test-impact list

- `test_time_based_reeligibility_fires_for_a_naturally_completed_look_on_a_stalled_contact`
  (`test_optic_policy.py`) polled only to ~144s past a completed look; `GLASS_STALL_COOLDOWN_S`'s
  180s floor now governs this exact scenario (a stalled, never-advancing contact). Numbers updated
  (window widened to ~240s), premise unchanged — a data update, not a premise break.
- Two full-pipeline scenario tests (`test_mock_flight_chain.py`,
  `test_bl_b104_scenario_mock_flights.py`) broke on the full-suite run, both traced to the
  commanded-scan wiring-defect fix (a commanded scan's own period is now its real leg count *
  `FOCUS_DWELL_S`, not the bare 16s `SCAN_CYCLE_PERIOD_S`) — see those files' own updated comments
  for the measured mechanism in each case. Neither was on the plan's own test-impact list for
  Stage 1 (which named `test_optic_policy.py`/`test_gaze.py`/`test_body.py`/`test_decay.py`/
  `test_tuning.py`, not these two full-pipeline fixture tests) — found by running the **full** test
  suite before declaring done, not by trusting the named list. Both were investigated (not
  guessed): the mock-flight-chain case was confirmed to be a previously-undetected real fixture
  object (`unit_102`) now genuinely reachable by faster binocular cadence, by dumping its full
  contact facts; the range-error case was confirmed to still clear the model's own rigorous
  3-sigma-per-poll budget at every observed poll before the cruder round-number bound was raised.

### Files Changed

- `body-layer/src/belief/position_belief.py` — Stage 0a: `_apply_floor` gains
  `prior_inflated_covariance`, capping the floor at it; `fold_position`'s call site passes the
  prior's own inflated covariance (already computed) for the `prior is not None` branch.
- `body-layer/src/belief/optic_policy.py` — Stage 1: `OpticState` gains `scan_sector_index`/
  `glass_step_started_sim`/`glass_recent_steps_s`. New `GLASS_STALL_COOLDOWN_S`/
  `_EFFECTIVE_GLASS_STALL_COOLDOWN_S`/`EXACT_LOCATION_MIN_GAIN_M` tunables. `LookTarget` gains
  `location_gain_m`; new `location_gain_for`, wired through `look_target_for`. `_classification_
  bucket` factored out of `choose_sighting_look`; new `choose_glass_look` (three buckets). New
  `_glass_can_improve`, `_within_sector`, `_glass_budget_admits_look`, `_rolled_glass_window`,
  `_advance_sector`, `_start_glass_look` helpers. `_decide_without_guidance`/`decide` gain
  `sector_wedge_deg`/`n_sectors`/`glass_budget_per_cycle_s` (see Deviation 1). GLASSING gains
  look-follow and the multi-look-per-step continuation; SCANNING-at-home gains the sector sweep/
  budget dispatch.
- `body-layer/src/perception/geometry.py` — new `sector_runs_for_legs`/`n_sectors_for_legs`
  (self-contained, no `tuning`/`gaze` import).
- `body-layer/src/perception/gaze.py` — new `GLASS_BUDGET_PER_CYCLE_S` tunable, derived
  `WORST_REVISIT_S`, `sector_azimuth_span_deg`, public `sector_legs_for`. `ScanPlan` gains
  `sweep_legs`/`sweep_started_sim`; `gaze_at` honours it.
- `body-layer/src/perception/naked_eye_source.py` — `_ACQUISITION_RETENTION_WINDOW_S` moves from
  `SCAN_CYCLE_PERIOD_S` to `WORST_REVISIT_S`.
- `body-layer/src/belief/decay.py` — new I2 assert alongside the existing I1 assert.
- `body-layer/src/tuning.py` — `_check_scan_decay_coupling` extended to 5 keys/2 invariants.
- `body-layer/src/body.py` — new `_resolve_sector_scan`, `_SECTOR_MARGIN_DEG`; wired into
  `ConsolePerceptionRunner.run_once`; new `_last_scan_command_t_sim` field and its reset logic;
  OBSERV-off branch also resets sector bookkeeping.
- `body-layer/config/defaults.toml` — regenerated.
- `body-layer/CLAUDE.md`, `body-layer/docs/STRUCTURE.md`, `body-layer/ROADMAP/BL-B110.md` — docs.
- Tests: `body-layer/tests/test_position_belief.py`, `test_expected_area_trigger.py` (new),
  `test_optic_policy.py`, `test_gaze.py`, `test_tuning.py`, `test_decay.py` (unchanged, already
  covered by the new asserts), `test_naked_eye_source.py`, `test_estimation.py`, `test_body.py`,
  `test_mock_flight_chain.py`, `test_bl_b104_scenario_mock_flights.py`.

### Tests Added

- `test_position_belief.py` (4): Stage 0a growth-0/armour-growth cap behaviour, naked-only dwell
  unaffected, founding look unaffected.
- `test_expected_area_trigger.py` (11, new file): residual-fold and false-trigger measurement for
  both candidate trigger variants, including the long-gap STOP finding.
- `test_tuning.py` (2): I2 rejects a low `LOST_THRESHOLD_S` override; I2 accepts the pendulum
  `SCAN_PLAN` at defaults.
- `test_gaze.py` (14): sector partition (default/pendulum/three-leg tables, boundary legs, cyclic
  merge, single-leg, empty), `sector_azimuth_span_deg`/`sector_legs_for`, `ScanPlan.sweep_legs`/
  `sweep_started_sim` (absolute-indexing preserved, anchored cycling, hold-at-last-leg, pre-anchor
  clamp), `WORST_REVISIT_S`'s own formula.
- `test_optic_policy.py` (8 new, across 3 classes, plus 2 of the 5 Decision-3 rewrites — the other
  3 of the 5 already passed unchanged): the rolling budget gating starts not lengths, the sector
  target filter, the `GLASSING` stall cooldown's three branches, look-follow's azimuth shift and
  its absent-contact no-op.
- `test_estimation.py` (37): the rough-location fence (Decision 10) over R=0.5-6km and height=
  0-800m, air and ground.
- `test_body.py` (1): the Stage 1 scenario gate — busy multi-group approach stays within
  `WORST_REVISIT_S` + poll-slack headroom.

### Checks

(body-layer/ only — no other subproject touched)

- `ruff format --check`: pass
- `ruff check`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (0 errors, 79 source files)
- `pytest body-layer/tests -q`: pass — **3044 passed, 4 xfailed**, full suite, run twice (once
  before the Stage 1 wiring fix, once after)

### Notable Discoveries

- **mypy narrowing is invalidated by a reassignment of the same local variable name anywhere in a
  function, even inside a branch that always returns.** Reassigning `state = replace(state, ...)`
  inside the `GLASSING` branch of `_decide_without_guidance` made mypy lose the function-top
  `phase_started_sim is not None` narrowing for the unrelated `SCANNING`-at-home branch further
  down, which never touches that reassignment. Fixed by binding the look-follow result to a
  differently-named local (`glassing_state`) instead of reusing `state`.
- **A full-pipeline fixture test can be sensitive to a wiring-defect fix in a way its own test-
  impact analysis cannot predict without running it**: both `test_mock_flight_chain.py` and
  `test_bl_b104_scenario_mock_flights.py` broke from the commanded-scan cadence fix, and neither
  was named in the plan's own Stage 1 test list. Running the *full* suite (not just the named
  files) before declaring done is what caught this.
- **Stage 0's measured false-trigger rate for the long-gap stationary case (7-27%) is a real,
  unresolved gap** that Stage 2's implementer needs to address before that stage ships — recorded
  in three places (plan.md, the test module's own docstring, `ROADMAP/BL-B110.md`) so it cannot be
  missed.

---

### Stage 1b — implementer pass 2026-11-09, STOPPED per the stage's own gate

**No production or test code is committed by this pass.** Plan's Stage 1b step 1 ("harness fix,
both cross-time harnesses... If any BL-B108 fence or assertion moves, stop and report both
outputs; do not edit the fence") was carried out, in isolation, against `test_relative_distance_
sweep.py` only (its "cross-time helpers, lines ~471–566": `_e3_fold_rate`, `_fuse_two_looks` and
their two callers) — unique `observation_id` per trial and a per-trial `t_sim`/`poll_key` base
(`t0 = trial * 1e-3`), exactly as the plan specifies.

**It moved a `BL-B108` fence.** Before (unchanged code): `pytest tests/test_relative_distance_
sweep.py -q` → `71 passed in 33.31s`. After (fix applied): `2 failed, 69 passed in 31.61s`.
`test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact`'s `u_u` (unaided→unaided,
3 km, 4 s gap) honest same-optic reacquisition fold rate measured **83–86%** (`n=100` then
`n=300`), not the asserted 100%; `u_b` stayed 99–100%. `test_no_omniscience_fused_sigma_never_
beats_the_tighter_optics_own_sigma` failed on `_fuse_two_looks`'s own zero-tolerance `assert
len(store.contacts) == 1`, hit once (binocular→unaided, 3 km, trial 7/60) by the already-known,
already-elsewhere-fenced (`test_e3_binocular_then_unaided_folds_almost_always`, ≥ 90%) non-fold
rate for that direction, once the draw was actually resampled instead of frozen at one lucky
value; 0 sigma-ratio violations across the 59 cells that did fold.

**Mechanism**: the same one the plan's own Stage 1b section already names for the gap-dependence
finding — `z_look` keyed by `(optic, poll_key=t_sim)`, the per-look bearing draw by
`observation_id` alone, both independent of `_FIELD_REALISATION_SALT`. The fixed-draw helpers
froze both to one draw for the whole ensemble; that one draw happened to always fold for `u_u`.
Per this stage's own instruction, **the fence was not edited**. The harness-fix edit itself was
reverted (`git checkout -- tests/test_relative_distance_sweep.py`) so the committed tree is
unchanged and green; the numbers above, and in `plan.md`'s new "Stage 1b implementer pass,
STOPPED 2026-11-09" subsection, are the full record.

**Not done, because step 1 (which produced this stop) blocks it**: the matching harness fix in
`test_expected_area_trigger.py`'s `_rates`, the one-sided direction clause in `_as_if_gate`, the
6/120/700 s gap grid, the ground (`surface=True`) cells at 100/500 m AGL, and the replacement of
`test_false_trigger_rate_for_long_gap_stationary_same_group_exceeds_the_gate`. None of these were
touched.

**For whoever picks this up next**: `test_relative_distance_sweep.py`'s own `_e1_fold_rate`/
`_E1_PAIRS` machinery already sweeps the *different-groups* case across many geometries with the
same fix's shape — the natural next step is the equivalent sweep for the *same-optic, same-group*
case (what this pass's two ad hoc probe cells hinted at) before deciding whether `u_u`'s "always"
guarantee itself needs correcting (a `BL-B108` behaviour-description change, needs the user) or
whether 3 km/4 s was simply an unlucky single cell among many that are fine.

### Checks (this pass)

- No files changed in the final committed state (edit made, measured, then reverted).
- `pytest body-layer/tests/test_relative_distance_sweep.py -q`: pass (unchanged, `71 passed`) —
  confirmed clean after the revert.
