### Implementation Summary

Implements `plans/9k113-narrow-search/plan.md` **as amended by Amendment 2** (which overrides
the plan body wherever they disagree, per the plan's own header). Built as one batch (Stages
1-4), one commit on the detached HEAD.

What shipped, in the amended shape:

- **Stage 1** -- the idle sight, every resume path, and the guidance-override-during-glance-away
  path all now carry a real aim inside the sight's own field of regard. Closes F5.
- **Stage 2** -- `_split_sector_by_regard`/`_commanded_or_default_sector` (geometry), and
  `search_pattern` gains `center_azimuth_deg`/`max_half_width_deg`. **Both the new split-sector
  call sites and the existing, previously-unsplit binocular search (`_search_sweep`) now use the
  commanded sector's own centre** -- Amendment 2 point 1 reversed the original plan's "leave
  `_search_sweep` exactly as it is" decision after the user said "fix the binocular search
  sector."
- **Stage 3** -- the search cycle, in Amendment 2's shape: **`wide` (brief orientation, near
  band) -> `narrow_near` (2.3-5.6 km) -> `narrow_far` (5.6-13.6 km) -> `binocular` (out-of-regard
  remainder, if any) -> `wide` ...**, not the original plan's two-leg `wide -> narrow -> binocular`
  cycle. Narrow now covers both bands; wide is confined to the near band only, as orientation.
- **Stage 4, Part A only** -- `sight_look_optic` (least-capable-optic-that-suffices for an actual
  look, wide vs. narrow). **Part B (attack-run guidance's sight-wide-over-binoculars preference)
  is explicitly not built** -- Amendment 2 point 3 defers it to `BL-B66` (real slew time), so the
  preference and its quick-look exception land together. No code for it exists in this commit.

### Files Changed

- `body-layer/src/belief/optic_policy.py`
  - Three new tunables: `SIGHT_SEARCH_NEAR_M` (2333.0), `SIGHT_SEARCH_MID_M` (5647.0, new),
    `SIGHT_SEARCH_FAR_M` (13556.0) -- band edges for the sight's own search cycle.
  - `search_pattern` gains `center_azimuth_deg: float = 0.0` and `max_half_width_deg: float =
    MAX_SEARCH_SECTOR_HALF_WIDTH_DEG`, both true no-ops for every pre-existing call.
  - `OpticState` gains `look_optic: Optic = SIGHT_NARROW_OPTIC` (which sight setting the current
    look uses) and `sight_search_leg: SightSearchLeg = "wide"` (which leg of the idle cycle is
    current); new module-level `SightSearchLeg` type alias (`Literal["wide", "narrow_near",
    "narrow_far", "binocular"]` -- four names, not the original plan's three, because Amendment 2
    split narrow into near/far).
  - New `sight_look_optic(target) -> Optic` (Stage 4 Part A).
  - New `_SEARCH_LEG_ORDER`/`_SEARCH_LEG_OPTIC`/`_next_search_leg`/`_enter_binocular_search`/
    `_idle_sight_rest`/`_idle_sight_search` -- the search-cycle mechanism, driving `_decide_
    sighting`'s idle branch.
  - `_back_to_home`: `home_phase is SIGHTING` branch carries `look_azimuth_deg`/`look_elevation_
    deg` forward (or defaults to `(0.0, 0.0)` if never set) instead of nulling them -- this *is*
    "stays at last position," and closes the resume-from-interruption/resume-from-search paths.
  - `_decide_sighting`: mid-look continuation and look-start both read/set `state.look_optic`
    (via `sight_look_optic`) instead of hardcoding `SIGHT_NARROW_OPTIC`; idle branch (`chosen is
    None`) now calls `_idle_sight_search` instead of resting with no aim; signature gains the four
    `sight_*_search` keyword sequences, threaded through `_decide_without_guidance`/`decide`.
  - `_apply_guidance`: down-cap condition extended from `home_phase is not SIGHTING` to
    `home_phase is not SIGHTING or decision.look_azimuth_deg is None` -- Stage 1's fourth path
    (glance-away's own bare `UNAIDED_OPTIC` decision has no aim even while `home_phase is
    SIGHTING`).
- `body-layer/src/logger.py`
  - Imports: `SIGHT_SEARCH_NEAR_M`/`SIGHT_SEARCH_MID_M`/`SIGHT_SEARCH_FAR_M` from
    `belief.optic_policy`; `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC` from `perception.optics`.
  - `_search_sweep`: now passes `center_azimuth_deg=center_deg` (previously discarded the centre
    it unpacked from `SECTOR_WEDGE_DEG`) -- fixes the pre-existing dead-ahead-sweep defect for
    `left`/`right`/`full`, per Amendment 2 point 1.
  - New `_split_sector_by_regard`, `_commanded_or_default_sector`, `_sight_in_regard_sweep`,
    `_sight_out_of_regard_sweep` -- the Stage 2/3 geometry, as given in the plan, **with one fix**
    (see Notable Discoveries: the out-span clamping bug).
  - `run_once`'s `decide_optic(...)` call gains `sight_wide_search`/`sight_narrow_near_search`/
    `sight_narrow_far_search`/`sight_out_of_regard_search`, computed fresh every poll the same way
    `search` already is.
- `body-layer/config/defaults.toml` -- regenerated (`tools/generate_defaults.py --write`) for the
  three new tunables. Rendered lines checked directly (not just the source `#:` comment) --
  `SIGHT_SEARCH_FAR_M`'s first-sentence comment originally began with a backtick-wrapped name
  (`` `SIGHT_NARROW_OPTIC`'s own presence reach... ``), which the generator's `.strip("*`")` trim
  stripped asymmetrically (only the leading backtick, since the sentence's own end is a period,
  not a backtick) -- rendered as `` SIGHT_NARROW_OPTIC`'s own presence reach... `` with a stray
  trailing backtick and no matching leading one. Fixed by rewording the sentence to not open with
  a backtick ("The sight narrow setting's own presence reach...").
- `body-layer/tests/test_optic_policy.py` -- see Tests Added/Rewritten below.
- `body-layer/tests/test_logger.py` -- see Tests Added below.

### Tests Rewritten (and why)

All in `test_optic_policy.py`. Every one of these previously pinned a now-superseded behaviour;
none were rewritten without a reason tied to Stage 1 or Stage 4 Part A landing.

- `test_idle_sighting_rests_wide_with_nothing_worth_looking_at` -> renamed `test_idle_sighting_
  rests_with_an_aim_inside_regard_with_nothing_worth_looking_at`. Was the pinned F5 bug itself
  (asserted `decision.look_azimuth_deg is None`); now asserts the invariant generally (non-`None`,
  `within_field_of_regard`), exactly the plan's own "Test impact, pinned bug" note anticipated.
- `test_the_security_agents_own_reproduction_is_rejected` -- also asserted `decision.look_azimuth_
  deg is None` for the rejected-target case; with Stage 3's active default search the idle branch
  never has a `None` aim at all, so this is narrowed to "the rejected target is not the source of
  the committed aim" (`decision.look_azimuth_deg is not None` and `!= 85.0`).
- `test_a_worthwhile_target_is_picked_immediately_no_scan_boundary`,
  `test_the_look_continues_on_the_next_poll`,
  `test_a_resolved_look_commits_and_immediately_picks_the_next_target`,
  `test_the_glance_away_returns_to_sighting_after_its_own_duration`,
  `test_a_target_just_inside_the_azimuth_limit_is_still_picked`,
  `test_a_target_at_minus_14_degrees_elevation_is_still_picked`,
  `test_a_target_at_plus_19_degrees_elevation_is_still_picked`,
  `test_an_in_regard_target_is_still_picked_when_an_out_of_regard_one_exists`,
  `test_observ_still_on_through_sighting_is_unaffected` -- all asserted `decision.optic is
  SIGHT_NARROW_OPTIC` for `_target()`'s default range (1000 m, "presence" level). Measured
  (`tier_ranges` for a T-72): `SIGHT_WIDE_OPTIC`'s own presence->class threshold is 3500 m, well
  above 1000 m, so `sight_look_optic` now picks `SIGHT_WIDE_OPTIC` for every one of these -- the
  plan's own "Test impact, range-sensitive" note. All nine changed to `SIGHT_WIDE_OPTIC`.

**No existing test pinned the binocular dead-ahead-sweep defect** Amendment 2 point 1 names
(`_search_sweep`/`search_pattern` had no test coverage in `test_logger.py` at all before this
task -- confirmed by `grep` before writing anything). So there was nothing to rewrite there;
fresh tests cover both the fixed behaviour and the pre-existing `ahead`-is-unaffected case
(`test_search_sweep_is_centred_on_the_commanded_sectors_own_centre`,
`test_search_sweep_ahead_is_unchanged_by_the_centre_fix`).

### Tests Added

`test_optic_policy.py`:
- `TestSearchPattern::test_center_azimuth_deg_shifts_every_step_by_exactly_that_amount`,
  `::test_max_half_width_deg_overrides_the_binocular_cap` -- Stage 2's two new `search_pattern`
  parameters, in isolation.
- `TestSightingDwellCycle::test_the_default_search_starts_at_the_wide_legs_first_step` -- the
  default sweep's first step, computed by calling `search_pattern` directly in the test (not
  hand-derived), per the plan's own instruction.
- `TestSightLookOptic` (new class) -- `sight_look_optic` exercised directly: a close presence
  target picks wide; a presence target beyond wide's own class threshold picks narrow; a `"class"`
  target is judged against the *type* threshold, not class. Direct, not through `_decide_sighting`,
  because of a gap found while writing an integration-level version of this test -- see Notable
  Discoveries.
- `TestIdleAimInvariant` (new class) -- the plan's required Stage 1 test, across all four named
  transitions: idle rest, resume-from-interruption (`lower_binoculars` mid-glance-away), resume-
  from-search (a binocular excursion's pattern running out, asserting the resumed aim is the
  sight's own last position, not reset), and a guidance override arriving during the glance-away.
- `TestSearchCycle` (new class) -- the four-leg cycle itself, driven with small synthetic
  sequences: `wide -> narrow_near -> narrow_far -> wide -> ...` with no out-of-regard remainder
  (never enters `SEARCHING`), and the full cycle including the binocular excursion (phase
  transition, both its own steps, and the "stays at last position" resume) when one exists.

`test_logger.py`:
- `test_search_sweep_is_empty_for_a_free_scan`,
  `test_search_sweep_is_centred_on_the_commanded_sectors_own_centre`,
  `test_search_sweep_ahead_is_unchanged_by_the_centre_fix` -- the Amendment 2 fix.
- `TestSplitSectorByRegard` -- `ahead`/`left`/`right`/`full` against the plan's own worked
  example, plus `test_a_span_entirely_outside_regard_has_no_in_span` (the edge case that found
  the out-span clamping defect, see Notable Discoveries).
- `TestCommandedOrDefaultSector`, `TestSightInRegardSweep`, `TestSightOutOfRegardSweep` -- the
  priority rule, and that the computed sweeps stay inside their own sub-spans.

### Checks

(body-layer/ is the only subproject touched)

- `ruff format --check src tests`: pass (2 files needed `ruff format` after editing; both
  reformatted and re-verified clean)
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass, no issues in 68 source files
- `pytest body-layer/tests -q`: pass -- 2267 passed, 4 xfailed (pre-existing, unrelated to this
  change)
- `pytest body-layer/tests/test_tuning_defaults_toml.py -q`: pass (defaults.toml staleness gate)

### Notable Discoveries

1. **`sight_look_optic`'s narrow branch is effectively unreachable through `_decide_sighting`'s own
   live trigger path today.** `_decide_sighting` only ever considers a target that passes `is_
   worth_a_look`/`can_still_improve`, which is gated by `improvement_window_m` -- a window built
   from the **naked eye's and binoculars'** own thresholds, not the sight's. For every object this
   codebase profiles, `SIGHT_WIDE_OPTIC`'s own class/type threshold is higher than `BINOCULAR_
   OPTIC`'s for the same tier (`class_range_mult` 7.00 vs. 3.50, `type_range_mult` 6.50 vs. 3.00
   -- both ratios are a structural property of the optic table, not specific to T-72), so a target
   just inside the trigger window is, by construction, always inside wide's own reach too. A live
   sight look therefore always resolves to `SIGHT_WIDE_OPTIC` in practice, never `SIGHT_NARROW_
   OPTIC`, until something widens the trigger window itself to the sight's own improvement window
   (an `improvement_window_m`-equivalent built from `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC` rather
   than the eye/binocular pair). **Not fixed here** -- Stage 4 Part A's own scope is "which optic
   serves an already-chosen target," not "what triggers choosing one," and widening the trigger
   is a judgement call (which window should gate a *sight* look?) the plan does not make. Flagging
   for a follow-up backlog item. The function itself is correct and tested directly
   (`TestSightLookOptic`); the gap is in what currently calls it.

   **Superseded 2026-10-20, by the review's required fix** (`plans/9k113-narrow-search/review.md`):
   `_decide_sighting`'s candidate filter and its `look_is_finished` continuation check now both
   take an injectable `can_improve` predicate, defaulting to `can_still_improve` (the eye/binocular
   window, unchanged for every other caller) but overridden to the new `sight_can_still_improve`
   (an upper-bound check against `SIGHT_NARROW_OPTIC`'s own class/type threshold, no lower bound)
   at both of `_decide_sighting`'s call sites. A live sight look can now reach `SIGHT_NARROW_OPTIC`
   -- see `TestNarrowReachableAtRange` in `test_optic_policy.py`, which asserts both that a far
   target is picked and that the resulting look survives past the poll that started it.
2. **`_split_sector_by_regard`'s out-of-regard clamping had a latent defect**, found by testing an
   edge case beyond the four named `RelativeSector`s (a span entirely outside the regard on one
   side, e.g. centre 90°, half-width 10°, regard 60°). The given formula fixed the out-span's near
   edge at the regard boundary unconditionally (`lo = regard_half_deg`), which for a span that
   never reached the boundary in the first place manufactured an out-span wider than the original
   sector (stretching from the boundary rather than from the sector's own edge) -- here, `(80,
   20)` i.e. the range [60,100], when the real out-of-regard content is only [80,100]. Fixed by
   clamping to whichever is tighter (`lo = max(span_low, regard_half_deg)`, and symmetrically
   `hi = min(span_high, -regard_half_deg)` for the low-side branch) -- verified this is a true
   no-op for all four named sectors (`ahead`/`left`/`right`/`full`), which is why the plan's own
   worked example never exposed it: every one of them straddles or contains azimuth 0, so neither
   branch is ever asked to clamp a span that was already entirely on the far side. Not reachable
   from any production call site today (`_commanded_or_default_sector` only ever produces one of
   the four named sectors or the regard-width default); fixed anyway since it is pure, cheap, and
   the function is general-purpose geometry, not sector-specific.
3. **Amendment 2's wide/narrow band assignment, as built**: `wide` sweeps `[NEAR_M, MID_M]`
   (2.3-5.6 km, same band as `narrow_near`, just at wide's coarser resolution) -- "wide is only
   for orientation and close range" read as "wide shares the near band with narrow, not a
   separate one," since the plan's own three tunables (`NEAR_M`/`MID_M`/`FAR_M`) give only two
   band edges to place three legs against, and "keep the band edges as the existing tunables"
   rules out inventing a fourth. If this reading is wrong, the fix is confined to `logger.py`'s
   `sight_wide_search=_sight_in_regard_sweep(...)` call (one `near_m`/`far_m` pair).

---

### Required fix round (`plans/9k113-narrow-search/review.md`)

The review's one required fix: the "worth a look" gate admitting a contact to `_decide_sighting`'s
candidate list was bound to the naked-eye/binocular pair (`improvement_window_m`), not the sight's
own reach, so a contact beyond binocular's own reach never became a sight candidate at all and
narrow was never triggered live (Notable Discovery 1 above, now superseded).

**Shape, as recommended by the review:**

- `sight_can_still_improve(target) -> bool` (`optic_policy.py`, beside `sight_look_optic`) -- a
  single upper-bound check against `SIGHT_NARROW_OPTIC`'s own class/type threshold, **no lower
  bound** (unlike `improvement_window_m`'s two-sided window -- while `SIGHTING` nothing dwells in
  parallel to resolve a close contact for free, so there is no equivalent exclusion).
- `is_worth_a_look` and `look_is_finished` both gained an injectable `can_improve: Callable[
  [LookTarget], bool] = can_still_improve` keyword, a true no-op for every pre-existing caller.
- `_decide_sighting`'s **two** call sites both pass `can_improve=sight_can_still_improve`: the
  candidate filter (`worth_looking`) and the `look_is_finished` continuation check. The second
  call site is not optional -- without it, a newly-admitted far contact is picked on the poll it
  starts and then found already outside the eye/binocular window on the very next poll, ending the
  look (and committing `attempted_at_range_m` as if it had resolved something) one poll after it
  began -- silently reintroducing the exact defect the fix closes. Confirmed by mutation: removing
  either call site's threading independently (checksum-verified restore after each) makes the new
  survival test (and, for the candidate-filter removal, the pick test too) fail for exactly that
  reason.
- `_decide_without_guidance`'s `SCANNING`-at-home call sites (the plain `is_worth_a_look`/`look_is_
  finished` calls, untouched) are left exactly as they were -- the OBSERV-off path is provably
  unchanged, since neither received the new keyword.

**Files changed this round**: `body-layer/src/belief/optic_policy.py` (the predicate, the two
keyword parameters, the two call sites); `body-layer/tests/test_optic_policy.py` (`TestSightCan
StillImprove`, `TestFarSightCandidateIsAdmittedAndSurvives`, and `TestSightLookOptic`'s class
docstring updated -- the "narrow is unreachable" claim it made is no longer true); this file
(Notable Discovery 1 marked superseded above). No tunables added, no `defaults.toml` change.

**Tests added**:
- `TestSightCanStillImprove` -- the predicate in isolation: a target beyond binocular's own class
  threshold but within narrow's can still improve; one beyond narrow's own reach cannot; no lower
  bound (a very close target still can); an already-`type`-level target cannot; a `"class"`-level
  target is judged against narrow's own type threshold, not class.
- `TestFarSightCandidateIsAdmittedAndSurvives` -- the review's required test: a 5000 m T-72
  presence-level target (beyond `BINOCULAR_OPTIC`'s 1750 m class threshold and `SIGHT_WIDE_OPTIC`'s
  3500 m, within `SIGHT_NARROW_OPTIC`'s 6875 m) is picked for a sight look with `decision.optic is
  SIGHT_NARROW_OPTIC`, and the look survives a second poll (`state.look_contact_id` unchanged)
  rather than being ended by `look_is_finished` one poll after it started.

**Checks (this round)**: `ruff format --check src tests`: pass (after one reformat of the two
touched files). `ruff check src tests`: pass. `mypy src`: pass, no issues in 68 source files.
`pytest tests -q`: 2273 passed, 4 xfailed, 0 failed (two separate flaky failures observed across
two runs -- `test_connection_reporter_says_disconnected_once_then_connected_once` and
`test_check_for_new_mission_keeps_the_traceback_for_a_non_connection_failure` -- both from the
task's own known-flake list, both pass alone on rerun, neither touches `optic_policy.py` or this
change's call paths).

---

### F4 follow-up: the wide sweep's far edge is wide's own reach, not the old shared near-band edge

Source: `docs/acceptance/2026-10-20-sortie-feedback.md`, "F4 -- wide sweep band" (user: *"it makes
sense to use it up to where it can bring information, be it detection or classification. At greater
distances it cannot, narrow can."*). This supersedes Notable Discovery 3 above: the wide leg had
been sharing `[SIGHT_SEARCH_NEAR_M, SIGHT_SEARCH_MID_M]` (2.3-5.6 km) with `narrow_near`, i.e. wide's
far edge was binoculars' own boundary rather than wide's own.

**Fix, as flagged in Notable Discovery 3**: confined to `logger.py`'s `sight_wide_search=` call's
`far_m` argument, which now reads a new derived constant, `_SIGHT_WIDE_SEARCH_FAR_M`, instead of
`SIGHT_SEARCH_MID_M`.

**No new tunable.** Per the task's own preference, this is derived from existing calibration rather
than guessed: `SIGHT_SEARCH_NEAR_M` is already the reference vehicle's (T-72, 7 m) unaided presence
reach, and `SIGHT_SEARCH_FAR_M`'s own comment already establishes the pattern of scaling that same
base by an optic's `presence_range_mult` to get that optic's own presence reach for the same vehicle
(`2333 * 5.81` for narrow). This applies the identical scaling to `SIGHT_WIDE_OPTIC`'s own
multiplier: `SIGHT_SEARCH_NEAR_M * SIGHT_WIDE_OPTIC.presence_range_mult = 2_333.0 * 3.55 =
8_282.15 m` (**~8.28 km**), clamped by `min()` against `PLAYER_BUBBLE_RADIUS_M` (10 km, the tighter
of the two caps that could apply -- `SIGHT_WIDE_OPTIC.range_cap_m` is the looser 20 km). The clamp
does not bind today (8.28 km < 10 km) but is applied anyway since a retuned `SIGHT_SEARCH_NEAR_M`
could push the derived value past it. No `tuning.py` declaration, no `defaults.toml` regeneration --
the value is a pure function of an already-tunable constant plus fixed optic calibration, not an
independent judgement call.

**"The farther of detection and classification reach" needs no separate class-threshold
computation.** `tier_ranges`' chained `min()`s make a class threshold never exceed its own optic's
presence threshold, structurally, for any object profile or optic (`class_threshold_m = min(
presence_threshold_m, ...)`), so the presence reach alone already is the larger of the two --
verified in `TestSightWideSearchFarM::test_presence_reach_is_already_the_farther_of_presence_and_
class` rather than assumed.

**Files changed this round**: `body-layer/src/logger.py` (the new `_SIGHT_WIDE_SEARCH_FAR_M`
constant beside `_SEARCH_BAND_M`; the `sight_wide_search=` call's `far_m` argument; the adjoining
comment pruned of its now-stale "wide orientation pass over the near band" wording per the
"prune the comment you are standing next to" rule -- 1 comment block updated, same file);
`body-layer/tests/test_logger.py` (new tests, below); this file.

**Tests added** (`TestSightWideSearchFarM`, `tests/test_logger.py`):
- `test_matches_the_reference_vehicles_presence_reach_through_wide` -- the constant equals
  `SIGHT_SEARCH_NEAR_M * SIGHT_WIDE_OPTIC.presence_range_mult`.
- `test_reaches_further_than_the_old_shared_near_band_boundary` -- greater than `SIGHT_SEARCH_MID_M`.
- `test_stays_inside_the_player_bubble` -- less than `PLAYER_BUBBLE_RADIUS_M` (the clamp's own
  headroom today).
- `test_presence_reach_is_already_the_farther_of_presence_and_class` -- falsifies the derivation's
  own structural claim directly against `tier_ranges`/`profile_for("T-72")`, rather than assuming it.
- `test_wide_sweep_reaches_a_shallower_elevation_than_the_old_boundary` -- `_sight_in_regard_sweep`
  itself produces a shallower (further-reaching) elevation with the new far edge than with the old
  one, same near edge and altitude. Its own docstring flags that this does **not** prove `run_once`
  passes the new constant at its call site -- that is the next test's job.
- `test_run_once_passes_the_wide_legs_own_far_edge` -- the one test that actually pins the call-site
  wiring: monkeypatches `logger._sight_in_regard_sweep` to spy on the `far_m` passed for the
  `optic=SIGHT_WIDE_OPTIC` call inside a real `ConsolePerceptionRunner.run_once()`, and asserts it
  is `_SIGHT_WIDE_SEARCH_FAR_M`. Needs no `SIGHTING`-dwell state set up: `sight_wide_search` is
  computed fresh every poll regardless of sight phase, mirroring `search`'s own unconditional
  computation (both are plumbed into `decide_optic(...)` unconditionally even when nothing reads
  them that poll), so a default runner's very first poll already exercises the call.

**Mutation-checked**, not merely written (`shasum` before/after, restored by overwrite rather than by
eye): reverted the `sight_wide_search=` call's `far_m` argument from `_SIGHT_WIDE_SEARCH_FAR_M` back
to `SIGHT_SEARCH_MID_M` (the pre-fix code) and reran `TestSightWideSearchFarM` -- exactly one test
went red, `test_run_once_passes_the_wide_legs_own_far_edge`, for exactly the stated reason
(`assert [5647.0] == [8282.15]`); the other five stayed green, confirming they test the constant and
the sweep function in isolation rather than the call site. The first attempt at this class (before
the wiring test existed) was itself a near-miss worth recording: four of the five constant/function
tests all passed against the *reverted* call site too, which is exactly the "test passes for the
wrong reason" trap -- none of them actually exercised `run_once`, so none could have caught the
one-line regression the task was about. Restored by overwrite from a saved copy, `shasum`-verified
identical to the pre-mutation file.

**Checks (this round)**: `ruff format --check src tests`: pass. `ruff check src tests`: pass.
`cd body-layer && .venv/bin/mypy src`: pass, no issues in 68 source files. `pytest tests -q`: 2280
passed, 4 xfailed, 0 failed, no flakes observed this run (none of the task's known-flake tests
needed a rerun).

**Derived wide band edge: ~8.28 km** (`8_282.15` m exactly, for the reference vehicle), up from the
old shared 5.6 km -- inside the 10 km player bubble, so it is wide's genuine reach rather than a
value the bubble cuts short.

### Security required fix: idle sight search never enforced elevation field of regard

`plans/9k113-narrow-search/security-review.md`, Part 2 Required Fix 1 (verdict NEEDS FIXES).
Confirmed by direct calculation before touching anything, reproducing the review's own table
(`math.degrees(math.atan2(alt, 2333.0))`): the idle search cycle's `wide`/`narrow_near` legs
command an elevation 8.2 deg past the sight's own `regard_elevation_down_deg=-15.0` at 1000 m AGL
-- an ordinary cruise/orbit altitude, not an edge case -- because `belief.optic_policy.
search_pattern`'s elevation is pure range/altitude geometry (`atan2`) with no awareness of this
optic's own field of regard; only its azimuth was ever capped (`max_half_width_deg`).

**Fix, applying the project's own established "reject, not clamp" pattern** (`look_sweep` already
does this for the sight's look-sweep path; `.claude/agent-memory/implementer/
feedback_declared_bound_check_at_selection_not_at_consumer.md`): `logger._sight_in_regard_sweep`
now filters `search_pattern`'s returned steps through `within_field_of_regard(optic, azimuth,
elevation)` before returning them, dropping any step the optic cannot physically reach rather than
clamping it to the boundary. This is the one producer every caller of the three in-regard legs
(`run_once`'s `sight_wide_search=`/`sight_narrow_near_search=`/`sight_narrow_far_search=`) reads
from, so filtering here protects all three without a second check anywhere else. A leg that
filters down to empty composes with the existing leg-advance/`_idle_sight_rest` fallback
unchanged -- `_idle_sight_search`'s `first_nonempty_leg` already treats an empty leg as "advance to
the next one," and confirmed by test (`test_a_multi_poll_cycle_never_commits_an_out_of_regard_aim`,
both altitudes) that the fallback itself never yields an out-of-regard aim, since it only ever
holds the last (already-validated) position or `(0.0, 0.0)`.

**The out-of-regard binocular sweep (`logger._sight_out_of_regard_sweep`) needs no equivalent
fix.** It calls `search_pattern` with `BINOCULAR_OPTIC`, whose `regard_azimuth_half_deg`/
`regard_elevation_up_deg`/`regard_elevation_down_deg` are all `None` (confirmed by reading
`BINOCULAR_OPTIC`'s declaration in `perception/optics.py` -- it is built with no `regard_*`
keyword at all) -- binoculars genuinely have no field of regard (a head-aimed instrument, not a
gimballed sight), so `within_field_of_regard` would be a true no-op there by the same convention
every other binocular caller already relies on. Left unchanged rather than adding a no-op filter.

**Tests added** (`TestSightInRegardSweepElevation`, `tests/test_logger.py`, inserted directly after
the existing `TestSightInRegardSweep`): the review's own required-test shape, built against the
real production near/far-edge wiring (`SIGHT_SEARCH_NEAR_M`/`_SIGHT_WIDE_SEARCH_FAR_M`/
`SIGHT_SEARCH_MID_M`/`SIGHT_SEARCH_FAR_M`), not a synthetic stand-in:

- `test_wide_leg_at_1000m_agl_stays_within_regard`, `test_narrow_near_leg_at_1000m_agl_stays_
  within_regard`, `test_narrow_far_leg_at_1000m_agl_stays_within_regard` -- each of the three
  in-regard legs, at 1000 m AGL, every returned step satisfies `within_field_of_regard` for its own
  optic; each also asserts the leg is non-empty (the filter must not silently empty every leg).
- `test_the_unfiltered_geometry_really_does_reach_past_the_down_limit` -- calls `search_pattern`
  directly (the function `_sight_in_regard_sweep` wraps), pinning that the underlying hazard this
  fix guards against is real production geometry, not a hypothetical; documents what the fix above
  is for, for a future reader.
- `test_a_multi_poll_cycle_never_commits_an_out_of_regard_aim` (parametrized `120.0`/`1000.0` m
  AGL) -- the review's own explicitly-named gap: the **existing** `within_field_of_regard`
  invariant tests (`TestSightingDwellCycle`'s idle-aim test, `TestIdleAimInvariant`) pass no
  `sight_*_search` sequences at all, which falls straight through to `_idle_sight_rest` and never
  calls `search_pattern`. This test instead builds the three real legs the way `run_once` builds
  them and drives `decide()` through 12 polls (more than one full `wide -> narrow_near ->
  narrow_far` cycle), checking the **committed** `(azimuth, elevation)` on each `OpticDecision`,
  not just the raw pattern list. 120 m AGL (this feature's own existing test default) pins that the
  fix is a true no-op at the altitude every other test in this module already uses; 1000 m AGL is
  the altitude the security review measured as failing unfiltered.

**Mutation-checked, not merely written** (`shasum` before/after, restored by overwrite): changed
`_sight_in_regard_sweep`'s `return [step for step in steps if within_field_of_regard(...)]` to a
bare `return steps` (the pre-fix shape) and reran `TestSightInRegardSweepElevation` -- three of the
six tests went red for exactly the stated reason: `test_wide_leg_at_1000m_agl_stays_within_regard`,
`test_narrow_near_leg_at_1000m_agl_stays_within_regard`, and the 1000 m parametrization of
`test_a_multi_poll_cycle_never_commits_an_out_of_regard_aim` (the failure shows
`look_elevation_deg=-23.20155444616394` on `SIGHT_WIDE_OPTIC`'s `-54.5` deg azimuth step -- the
review's own `-23.2 deg` figure at 1000 m AGL, reproduced exactly). `test_narrow_far_leg_at_
1000m_agl_stays_within_regard` and the 120 m parametrization stayed green under the mutation, which
is expected and not a gap: `narrow_far`'s near edge is `SIGHT_SEARCH_MID_M` (a shallower depression
than the shared `SIGHT_SEARCH_NEAR_M` edge the defect lives at), and 120 m AGL is comfortably under
the ~625 m threshold for any leg -- both are genuine negative cases, not blind spots. Restored by
overwrite, `shasum`-verified byte-identical to the pre-mutation file.

**Checks (this round)**: `ruff format --check src tests`: pass (one reformat applied to the new
test class before the check). `ruff check src tests`: pass. `cd body-layer && .venv/bin/mypy src`:
pass, no issues in 68 source files. `pytest tests -q`: 2286 passed, 4 xfailed, 0 failed. One
known-flake test needed a rerun in the full-suite pass (`test_connection_reporter_reannounces_
after_a_recovery_and_a_second_drop`, a timing flake named in the dispatch brief) -- confirmed by
running it alone immediately after, which passed; unrelated to this change (it never touches
`logger._sight_in_regard_sweep`/`optic_policy.search_pattern`/`within_field_of_regard`).

**What the pilot will notice**: high up, the idle sweep's closest-range elevation band drops out --
above roughly 625 m AGL the sight cannot physically look that steeply down to cover the near edge
of its own search band, so those steps are simply skipped (confirmed: at 1000 m AGL the wide leg's
near elevation band, -23.2 deg, is dropped in full while its far band, -6.9 deg, is swept normally
-- 11 of 22 steps), rather than the gunsight being pointed at an elevation the mount cannot
mechanically hold.

### BL-B85: a timer bound so the sight cannot indefinitely re-grant one stuck contact

`docs/acceptance/2026-10-20-sortie-feedback.md` F4 overruled Reviewer/Security's non-blocking
disposition of `BL-B85` -- *"BL-B85 is required for 9K113, we can't just indefinately look at one
thing. Needs a timer value or the like that forces moving on"* -- so this round builds it into the
feature rather than leaving it filed. `body-layer/ROADMAP/BL-B85.md` has the entry's own account;
this is the decision log.

**Started from the dispatch brief's own framing**: extend `is_worth_a_look`'s existing per-contact
retry bookkeeping (`attempted_at_range_m`/`attempted_at_time_sim`, `RETRY_RANGE_FRACTION`'s
range-based re-eligibility and `OPTIC_RETRY_INTERVAL_S`'s time-based one, from the 2026-09-26
fixes) with a longer, sight-only cooldown applied when a contact's classification level has not
moved since its last committed attempt. Added `OpticState.attempted_at_level`/`pending_attempted_
at_level` (the exact `attempted_at_range_m`/`pending_attempted_at_range_m` pattern, one `dict[str,
str]` twin, populated and committed at every site the range twin already is -- both `GLASSING`'s
and `SIGHTING`'s look-start and natural-end-commit sites, and every `pending_attempted_at_range_m=
{}` interruption-drop site, so the two dicts never fall out of step regardless of which phase last
attempted a contact). Added `is_worth_a_look`'s new `stall_cooldown_s: float | None = None`
parameter -- `None` for every pre-existing caller (`GLASSING`'s own call never passes it, a true
no-op), and `_decide_sighting`'s candidate filter passes the new `SIGHT_STALL_COOLDOWN_S` tunable.
When passed and the contact's level matches what was recorded at the last commit, the longer
cooldown governs the time-based branch in place of `OPTIC_RETRY_INTERVAL_S`; `RETRY_RANGE_
FRACTION`'s range-based escape is untouched either way.

**That alone did not fix the reproduction -- a second, deeper defect had to be found first.**
Wrote the 900 s/three-contact reproduction from `plans/9k113-narrow-search/review.md` as a test
(three close T-72 contacts, 50/80/120 m, held at `presence` forever, driven through `decide()` with
real single-step `wide`/`narrow_near`/`narrow_far` search sequences) before trusting the fix above,
per the dispatch brief's own instruction to reproduce the starvation first. It still measured 88%
busy with the `stall_cooldown_s` plumbing in place -- `attempted_at_range_m`/`attempted_at_level`
were staying *empty* the entire run, so the new cooldown branch was never even being reached.

Traced it to `_decide_sighting`'s own dispatch order: it checks the scheduled whole-dwell break
(`now_sim - dwell_started_sim >= SIGHT_MAX_DWELL_S`, entering `_start_glance_away`) **before**
checking whether the current look reached its own natural end (`look_is_finished`, which uses the
same `SIGHT_MAX_DWELL_S` as that look's own per-look ceiling when nothing can resolve it sooner).
For a contact that never advances, `can_improve` never flips false, so a look only ever ends via
that shared `SIGHT_MAX_DWELL_S` ceiling -- and because a fresh look always starts on the very poll
the dwell (re)enters `SIGHTING` (no scan boundary to wait for), the look's own clock and the
dwell's own clock start within a poll of each other every single cycle, so the scheduled-break
check wins the race every time. `_start_glance_away` was dropping the pending marks the same way a
genuine interruption does (`"the look did not reach its own natural end"` -- true by construction,
never false for a stuck contact), so `attempted_at_range_m`/`attempted_at_time_sim`/`attempted_at_
level` never recorded anything for it at all: the whole retry/cooldown mechanism this round set out
to extend was structurally unreachable for exactly the contact it needed to govern. Fixed:
`_start_glance_away` now commits pending marks into the committed maps exactly as the natural-end
path in `_decide_sighting` does, rather than discarding them -- a dwell boundary reached while a
look is still running is not evidence the look delivered nothing; it ran the sight's full allotted
time, which is what "committed" already means on the ordinary natural-end path two branches below.

**Both halves measured as necessary, independently, by mutation** (`shasum` before/after each,
restored by overwrite and confirmed byte-identical):
- Reverting only the `_start_glance_away` commit (back to dropping pending marks), with the
  `stall_cooldown_s` plumbing left in place: reproduction measures 88% busy -- unchanged from the
  pre-fix figure, confirming the commit fix is the one that actually lets any bookkeeping happen.
- Reverting only the `stall_cooldown_s` argument at `_decide_sighting`'s candidate filter (so
  `is_worth_a_look` falls back to the short `OPTIC_RETRY_INTERVAL_S`, 64 s), with the commit fix
  left in place: reproduction *also* measures 88% busy -- three contacts' own busy phases (30 s
  each, 90 s total) outlast the 64 s short interval, so a contact is re-eligible again before the
  others have even had their turn and no idle gap ever opens. `SIGHT_STALL_COOLDOWN_S` (132 s, ~two
  search-cycle laps) is long enough to open that gap; this is why the default is roughly double the
  three-contact busy-phase length, not an arbitrary round number.
- With both fixes: 58% busy, every leg (`wide`/`narrow_near`/`narrow_far`) visited, every contact
  re-looked four times over the 600 s run.

**`SIGHT_STALL_COOLDOWN_S`** (`belief/optic_policy.py`, `tuning.real`, default 132.0, `lo=30.0`,
`hi=400.0`, `status="judgement"`): the rendered `config/defaults.toml` line was checked, not just
the source comment -- the first draft used blank-`#:`-line paragraph breaks the same way `SIGHT_
SEARCH_NEAR_M`'s shared-intro-then-bullet comment does, which (per the generator's own documented
behaviour, `_comment_block_above` stopping upward traversal at the first blank `#:` line) renders
only the *paragraph nearest the assignment*, not the first paragraph of the whole block -- the
rendered line came out as an unrelated mid-reasoning sentence the first two times. Rewritten as one
contiguous `#:` block (the `GUIDANCE_OPTIC_MIN_INTERVAL_S`/`HANDS_BUSY_DURATION_S` pattern) with a
clean, period-free first sentence and the user's own verbatim quote moved to a later sentence (a
quote containing its own sentence-ending period would otherwise truncate the rendered line
mid-quote) -- confirmed by reading `config/defaults.toml` after each attempt, not the diff.

**Does the same bound protect `GLASSING`?** No, by construction, not by oversight -- only `_decide_
sighting`'s own candidate filter passes `stall_cooldown_s`; `GLASSING`'s call to `is_worth_a_look`
does not, so a contact stuck under binoculars keeps the pre-existing `OPTIC_RETRY_INTERVAL_S`
behaviour unchanged. `OpticState.attempted_at_level`/`pending_attempted_at_level` *are* populated
symmetrically for both phases (so the data exists regardless of which phase last attempted a
contact), but only the sight's own call site opts into treating it as a cooldown gate. Extending
the cooldown to `GLASSING` would be a `GLASSING` behaviour change beyond what F4 asked for (the
9K113, not binoculars); noted in `BL-B85.md` as a backlog item rather than built here.

**Tests added** (`TestSightStallCooldown`, `tests/test_optic_policy.py`, after `TestSearchCycle`):
- `test_a_stalled_contact_is_not_retried_before_the_sight_cooldown` / `test_a_stalled_contact_is_
  retried_once_the_sight_cooldown_elapses` -- the surgical unit tests directly on `is_worth_a_look`,
  pinning the boundary at exactly `SIGHT_STALL_COOLDOWN_S`.
- `test_glassing_keeps_the_pre_existing_short_interval` -- `GLASSING`'s own call (no `stall_
  cooldown_s` passed) is unaffected; uses 1_700 m (the existing GLASSING-window convention this
  module's other tests already use), not the close ranges the sight-specific tests use, since
  `can_still_improve`'s own lower bound excludes anything that close regardless of this feature.
- `test_progress_since_the_last_attempt_keeps_the_fast_retry` -- a contact whose level *did* move
  since the last commit is not penalised by the longer cooldown.
- `test_three_contacts_stuck_at_presence_still_let_the_search_cycle_run` -- the full 600 s/
  three-contact reproduction and fix, described above.

**Checks (this round)**: `ruff format --check src tests`: pass. `ruff check src tests`: pass.
`cd body-layer && mypy src`: pass, no issues in 68 source files. `pytest tests -q`: 2323 passed, 4
xfailed, 0 failed. One known-flake test needed a rerun in the full-suite pass
(`test_check_for_new_mission_keeps_the_traceback_for_a_non_connection_failure`, a timing flake
named in the dispatch brief) -- confirmed by running `test_mission_start_reset.py` alone
immediately after, which passed in full; unrelated to this change (it never touches `optic_
policy.py`). `tools/generate_defaults.py` (no `--write`): confirmed `config/defaults.toml` already
current after the final edit.

**Notable discovery, relevant to future sight/dwell work**: `SIGHT_MAX_DWELL_S` plays two distinct
roles today -- the whole-dwell scheduled-break clock (`_decide_sighting`'s own top check) and the
per-look natural-end ceiling (`look_is_finished`'s `max_dwell_s` parameter) -- and sharing one
constant between them is what made the scheduled break win the race against the natural-end check
on *every* cycle for a look that needs its full ceiling, not just occasionally. This round's fix
(committing on the scheduled break, same as the natural end) resolves the one consequence BL-B85
named, but the underlying race (two clocks, one constant, resolved by code order rather than by
which one is conceptually "supposed" to fire first) is still there for any future caller that reads
one of these events as meaning something the other doesn't. Not a cited constant-coupling in the
tuning-bounds sense (nothing here is a `lo`/`hi` violation), so it would not be caught by the
cross-key coupling check `tuning.py`'s docstring warns about -- flagging it here instead.

### F5: the regard check is boresight-relative (pitch/bank), not altitude-only

`docs/acceptance/2026-10-20-sortie-feedback.md` F5, settled *"OK"* for sequencing on 2026-10-20: the
9K113's `regard_*` limits (`optics.py`'s `regard_azimuth_half_deg=60.0`/`regard_elevation_up_deg=
20.0`/`regard_elevation_down_deg=-15.0`) are relative to the airframe's own boresight, not to the
ground -- *"nose low position at high altitude would allow a near scan... it is not about distance,
but angles relative to boresight"*; *"the limits are the mechanical rotation limits around aircraft
axis. When aircraft rotates, so do the coordinate axis."* `_sight_in_regard_sweep`'s elevation fix
(`bb6364b0`) rejected steps correctly against `within_field_of_regard`, but `search_pattern`'s own
steps are heading/horizon-relative, computed from `atan2(altitude_agl_m, range_m)` alone -- level-
flight geometry with no notion of pitch or bank -- so the regard filter was testing a ground-
anchored number as if it were a body-relative one. Built as one commit, on the detached HEAD, per
the dispatch brief's sequencing instruction ("gets a simple boresight-relative limit check... then
merges once DoD passes").

**Fix, kept deliberately simple per the user's own instruction** (*"let's not build anything too
fancy yet, since the effectors will anyhow be a priority soon and then DCS will limit the 9K113 to
its actual limits"*): no slew model, no new tunables, no `OpticState` change. One new pure function,
`perception.geometry.heading_relative_to_body_relative`, reusing `body_relative_direction` (the same
conversion `perception.visibility.check_visibility` already uses for live detections) rather than
re-deriving its pitch/bank rotation a second time -- it builds a unit-range synthetic target from
the heading-relative `(azimuth, elevation)` pair, rotates it back out to world coordinates with the
same `heading_true_deg` that will be handed to `body_relative_direction`, so the yaw cancels exactly
and only the pitch/bank rotation `body_relative_direction` already implements is left to apply.
Verified algebraically (the inverse-yaw construction is the exact matrix inverse of `body_relative_
direction`'s own step 1) and by an explicit heading-invariance test (`test_heading_relative_to_body_
relative_cancels_heading_exactly`, non-zero pitch/bank, two different headings, identical result).

`logger.py`'s three sweep generators (`_search_sweep`, `_sight_in_regard_sweep`,
`_sight_out_of_regard_sweep`) each now convert `search_pattern`'s raw steps through a shared
`_to_body_relative_steps(steps, ownship)` helper before returning them -- `_sight_in_regard_sweep`
converts *before* filtering through `within_field_of_regard`, so the gate and the aim it ultimately
commits are now the same body-relative numbers; `_search_sweep`/`_sight_out_of_regard_sweep` have no
regard filter to fix (binoculars are not bounded), but convert anyway so the binocular aim frame
agrees with every other optic's, per the brief: *"Binoculars have no regard, so the conversion
matters there only for pointing the right way."*

**`look_target_for` had the identical bug, for real contacts, not just search steps -- found while
confirming the brief's "if not, fix the same way" clause, not assumed from the function's own
docstring.** Its docstring already claimed "body-relative azimuth... the same frame `within_optic_
fov` tests in," but the body computed `azimuth = true_bearing - heading_true_deg` and `elevation =
asin(height_delta / slant_m)` -- heading-relative and level-flight-only, exactly `search_pattern`'s
own defect, just hiding behind a docstring that asserted the opposite of what the code did. Since
`_decide_sighting`'s candidate filter (`within_field_of_regard(SIGHT_WIDE_OPTIC, target.azimuth_deg,
target.elevation_deg)`) reads this value directly, a real contact's regard eligibility was wrong by
exactly the same pitch/bank error as a search step's, silently, since `bb6364b0`. Fixed by replacing
the manual azimuth/elevation derivation with a `body_relative_direction` call (dropping the now-
unused `bearing_deg` import) and adding keyword-only `pitch_deg`/`bank_deg` parameters, both
defaulting to `0.0` -- a true no-op for every pre-existing call site (five in `tests/test_optic_
policy.py`), mirroring `OwnshipState`'s own default convention. `logger._look_targets` is the one
caller with a real ownship to hand, and now passes `ownship.pitch_deg`/`ownship.bank_deg`.
Mathematically equivalent to the old formula at `pitch_deg=bank_deg=0.0` (verified: `asin(height_
delta/slant_m) == atan2(height_delta, horizontal_range)` for a non-negative horizontal range, which
is exactly what `body_relative_direction`'s own elevation reduces to when pitch/bank are both zero),
so every pre-existing `look_target_for` test still passes unchanged.

**Reacquire after nose-down, and the BL-B85 stall cooldown -- checked, not just asserted.** A
contact rejected as a candidate because pitch currently puts it out of regard is never selected, so
it is never written into `pending_attempted_at_range_m`/`attempted_at_level` -- a look that never
started cannot have "ended," and `SIGHT_STALL_COOLDOWN_S` only ever reads those dicts
(`is_worth_a_look`'s own `attempted_at is None` branch returns `True` unconditionally). Since every
`sight_*_search` sequence and every `LookTarget` is recomputed fresh from the current `ownship` every
poll (`logger.run_once`'s own per-poll wiring, unchanged by this fix), a leg or a contact that empties
out under one attitude is re-evaluated under the next poll's attitude with no carried state at all --
reacquisition is a consequence of the existing per-poll-recompute architecture, not new code. Pinned
by two tests (`TestFieldOfRegardEnforcement`): a target held out of regard for ten consecutive polls
is never marked attempted in any of the three dicts, and the same target is picked on the very next
poll once its elevation moves back inside the envelope -- no cooldown, because nothing was ever
recorded to cool down from.

**Files Changed**

- `body-layer/src/perception/geometry.py` -- new `heading_relative_to_body_relative`.
- `body-layer/src/logger.py` -- new `_to_body_relative_steps`; `_search_sweep`/`_sight_in_regard_
  sweep`/`_sight_out_of_regard_sweep` each convert through it; `_sight_in_regard_sweep`'s and
  `_sight_out_of_regard_sweep`'s docstrings rewritten -- the old "~625 m AGL" figure was a
  level-flight-only artifact of the altitude-only model this fix replaces, so it is now stated as
  a boresight-relative claim with no altitude number attached (the number itself now lives, dated,
  in `BL-B86.md`, alongside the note below that it was never a general threshold).
- `body-layer/src/belief/optic_policy.py` -- `look_target_for` gains `pitch_deg`/`bank_deg` (both
  default `0.0`); now calls `body_relative_direction` instead of deriving azimuth/elevation by hand;
  `bearing_deg` import dropped (no longer used anywhere in this file).
- `body-layer/ROADMAP/BL-B86.md` -- dated note: its measured altitude figures are level-flight-only;
  the "idle search goes fully static" window moves with pitch, not with AGL alone.

**Tests Added**

- `test_geometry.py`: five tests on `heading_relative_to_body_relative` -- identity at zero attitude,
  heading-invariance (non-zero pitch/bank, two headings), nose-down reducing a 1000 m AGL/2333 m
  depression from −23.2° to −13.2°, nose-up pushing a −10° step to −20°, and a bank-30 test
  reproducing `body_relative_direction`'s own azimuth/elevation bank-mixing numbers through the new
  function.
- `test_logger.py` (`TestSightInRegardSweepBoresightRelative`): the same nose-down/nose-up/bank
  scenarios through the real production call chain (`search_pattern` + `_to_body_relative_steps` +
  `within_field_of_regard`), a level-flight-is-a-true-no-op pin, an end-to-end `_sight_in_regard_
  sweep` comparative test (more in-regard steps with nose down than level, same near/far edges), and
  one `_search_sweep`/one `_sight_out_of_regard_sweep` test confirming a banked aim differs from a
  level one.
- `test_optic_policy.py` (`TestLookTargetGeometry`): `test_elevation_accounts_for_pitch` (reproduces
  `test_geometry.py`'s own pitched-nose-is-dead-ahead case through `look_target_for`) and `test_
  elevation_and_azimuth_account_for_bank` (reproduces its bank-rotates-elevation-into-azimuth case).
- `test_optic_policy.py` (`TestFieldOfRegardEnforcement`): `test_a_target_repeatedly_out_of_regard_
  is_never_marked_attempted` and `test_the_same_target_is_picked_immediately_once_back_in_regard` --
  the reacquire-after-nose-down/BL-B85 interaction above.

**Mutation-checked, both sites, by hand (not via a mutation-testing tool)**: temporarily hard-coded
`pitch_deg=0.0` inside `heading_relative_to_body_relative`'s own call to `body_relative_direction`
-- five tests went red (the two nose-up/nose-down `test_geometry.py` tests and three `test_logger.py`
tests downstream of them), restored, confirmed by `shasum` before/after. Separately hard-coded
`pitch_deg=0.0, bank_deg=0.0` inside `look_target_for`'s own call -- both of its new tests went red,
restored, confirmed by `shasum` before/after. Full suite green both before and after each restore.

**Checks**: `ruff format --check src tests`: pass. `ruff check src tests`: pass. `cd body-layer &&
mypy src`: pass, no issues in 68 source files. `pytest tests -q`: 2339 passed, 4 xfailed, 0 failed,
no rerun needed (none of the three named flaky tests failed in this run).

**Notable discovery**: `look_target_for`'s own docstring already claimed "body-relative azimuth,"
which is exactly why this was not caught by reading the docstring alone during earlier rounds --
the comment said the output already had the property this round adds. The dispatch brief's own
"confirm, don't assume" instruction for `LookTarget` is what caught it; a plain read of the
docstring would have reported it as already correct.
