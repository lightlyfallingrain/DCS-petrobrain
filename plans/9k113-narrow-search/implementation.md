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
