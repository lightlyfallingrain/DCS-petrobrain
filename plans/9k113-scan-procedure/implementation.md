# Implementation Summary — BL-B89 Stage 1 (9K113 sector scan)

Built exactly Stage 1 of `plans/9k113-scan-procedure/plan.md` (the sector scan). Stage 2
(pointing at a known place) is left designed, not built, per the plan's own scope.

## Files Changed

- `body-layer/src/perception/gaze.py` — added `SIGHT_SECTOR_WEDGE_DEG` (`left`/`right`/`full`
  only, the sight's own wider table), `SIGHT_AHEAD_LEGS` (the two alternating 40°-wide forward
  windows), and the new tunable `SIGHT_AHEAD_WINDOW_DWELL_S` (how long each "ahead" window is
  swept before alternating to the other — see "Deviation 1" below).
- `body-layer/src/belief/optic_policy.py`:
  - `SightSearchLeg` narrowed to `Literal["wide_near", "wide_far", "narrow_far_sweep"]`;
    `"binocular"` is no longer a value of this type at all (see "Deviation 2").
  - New `choose_sighting_look(targets)` — the priority-bucket wrapper around `choose_look`;
    `_decide_sighting` calls it in place of `choose_look`.
  - `_SEARCH_LEG_ORDER`/`_SEARCH_LEG_OPTIC`/`_next_search_leg` rewritten for the 3-leg cycle,
    no `has_out_of_regard` skip logic (no longer needed — `"binocular"` isn't in the order).
  - `_idle_sight_search` rewritten: on completing `narrow_far_sweep` (the cycle's last leg),
    routes to `_start_glance_away` (pre-setting `sight_search_leg` back to the cycle's first
    leg and `look_started_sim=None`) instead of restarting the lap — the mandatory per-lap
    pause, independent of `SIGHT_MAX_DWELL_S`.
  - `_enter_binocular_search` is now called only from `_decide_without_guidance`'s glance-away
    resume point (see "Deviation 2"), not from inside `_idle_sight_search`.
  - `_decide_sighting`/`_decide_without_guidance`/`decide` — three `sight_*_search` keyword
    params renamed (`sight_wide_near_search`/`sight_wide_far_search`/
    `sight_narrow_far_sweep_search`); `_decide_sighting` no longer accepts
    `sight_out_of_regard_search` at all (moved up to `_decide_without_guidance`, which already
    needed it for the glance-away branch).
  - `SIGHT_SEARCH_NEAR_M` lowered 2333.0 → 1500.0 (`lo` 1000.0 → 500.0); `SIGHT_SEARCH_MID_M`
    removed; new `SIGHT_SEARCH_WIDE_MID_M` (4000.0) and `SIGHT_SEARCH_WIDE_FAR_M` (8000.0,
    replacing the derived `_SIGHT_WIDE_SEARCH_FAR_M`) added. `SIGHT_SEARCH_FAR_M` unchanged.
- `body-layer/src/body.py`:
  - Removed the derived `_SIGHT_WIDE_SEARCH_FAR_M` constant entirely.
  - New `_sight_commanded_sector(scan_plan, ownship) -> tuple[float, float] | None` — resolves
    a commanded sector through the sight's own table (`SIGHT_SECTOR_WEDGE_DEG`/
    `SIGHT_AHEAD_LEGS`), a commanded single o'clock hour (`ScanPlan.commanded_legs`, exactly one
    entry) via `_gaze_for_clock_hour`, or `None` for free scan/a multi-leg `commanded_legs` (see
    "Deviation 3").
  - `_commanded_or_default_sector` takes `ownship` now (needed for the "ahead" time-based
    alternation) and delegates to `_sight_commanded_sector`.
  - `_sight_in_regard_sweep`/`_sight_out_of_regard_sweep` both read `_sight_commanded_sector`
    instead of `SECTOR_WEDGE_DEG` directly. `_search_sweep` (naked-eye/binocular) is untouched.
  - Poll-loop call site renamed to the three new leg keywords with the new band-edge table from
    the plan (`wide_near`: NEAR..WIDE_MID, `wide_far`: WIDE_MID..WIDE_FAR, `narrow_far_sweep`:
    WIDE_FAR..FAR).
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`); checked
  the rendered file, not just the source comments (per `body-layer/CLAUDE.md`'s "Tuning").
- `body-layer/tests/test_optic_policy.py` — `TestSearchCycle` replaced by `TestSightSearchLegs`
  (new leg names, the lap-completion→glance-away trigger, the binocular detour moved to the
  glance-away resume point); new `TestChooseSightingLook`; `TestSightStallCooldown`'s own
  `_decide` helper and leg-name assertions updated.
- `body-layer/tests/test_body.py` — `TestCommandedOrDefaultSector`/`TestSightInRegardSweep*`/
  `TestSightOutOfRegardSweep` updated for the new sector table and `ownship` parameter; new
  `TestSightSectorWedge`; `TestSightWideSearchFarM` (tested the now-removed derivation) replaced
  by `TestRunOncePassesTheThreeLegsOwnBandEdges`; new nose-up/1–2 km-band tests added to
  `TestSightInRegardSweepBoresightRelative` (see "Notable Discoveries").

## Tests Added

- `TestChooseSightingLook` (`test_optic_policy.py`) — a `class`-level target beats a
  `presence`-level one regardless of range; within one bucket `choose_look`'s own ordering is
  reproduced; empty input → `None`.
- `TestSightSearchLegs` (replaces `TestSearchCycle`) — the 3-leg cycle order and optics; a
  completed lap forces the glance-away (asserted via `phase → SCANNING` with
  `now_sim - phase_started_sim` far under `SIGHT_MAX_DWELL_S`, proving the *other* trigger
  fired); the cycle resumes a fresh `wide_near` pass after the pause; the out-of-regard
  binocular excursion is entered from the glance-away's own resume point, not mid-lap.
- `TestSightSectorWedge` (`test_body.py`) — `SIGHT_SECTOR_WEDGE_DEG`'s worked spans; the "ahead"
  alternation across two dwell periods; every named sector (+ `ahead`'s two windows) now fits
  inside the regard.
- `TestSightOutOfRegardSweep` extended — every named sector (`ahead`/`left`/`right`/`full`) now
  yields an empty out-of-regard sweep; a commanded o'clock hour outside ±60° (5 o'clock) yields
  a non-empty out-of-regard sweep and an empty in-regard one.
- `TestSightInRegardSweepBoresightRelative` extended — nose-up at 100/300/800 m AGL (5° and 10°);
  a mechanism test confirming `decide()` never stalls when `wide_near` is emptied by attitude;
  the 1–2 km AGL band (level and -8° nose-down) — see "Notable Discoveries" for what these
  measured.

## Deviations from the plan (flagged per the implementer's own instructions)

**1. `SIGHT_AHEAD_WINDOW_DWELL_S` is a new tunable the plan's own "Affected Modules" section did
not name.** The plan specifies `SIGHT_AHEAD_LEGS` as a fixed two-entry table but is silent on
*what drives the alternation* between the two windows. Re-reading the plan's own analogy
("the sight's own analogue of `_SECTOR_LEGS["ahead"]`'s naked-eye `(11, 12, 1)` cycling") pointed
at a time-based toggle, same spirit as the naked eye's own `gaze_at` mechanism — but the naked eye
cycles via `FOCUS_DWELL_S`/`command_t_sim`, a mechanism that lives in `ScanPlan`/`gaze_at`, not in
the sight's own search-leg stepping (`_idle_sight_search`, driven by `SEARCH_STEP_S` and
`look_started_sim`). Rather than reusing either of those (both answer a different question — see
`LOOK_SWEEP_SIGMA`'s own docstring, the module's standing rule against sharing a number between
two questions), I declared a new, independent tunable
(`perception.gaze.SIGHT_AHEAD_WINDOW_DWELL_S`, default 30.0 s, `lo=5.0, hi=120.0`,
`status="judgement"`) and toggle via `int(ownship.t_sim // SIGHT_AHEAD_WINDOW_DWELL_S) % 2`,
a pure function of sim time. This is a genuine design choice I made, not something the plan
specified — flagging it so the user/reviewer can retune or reject the mechanism once flown.

**2. The out-of-regard binocular excursion moved out of `_idle_sight_search` entirely, to the
glance-away's own resume point.** The plan states "the out-of-regard binocular excursion…does not
count toward a lap" and "is entered as its own, separately-triggered detour rather than a fourth
cycle leg", but does not say *where* that trigger lives. I considered keeping it inside
`_idle_sight_search` as a parallel check alongside the lap-boundary detection, but every variant I
traced either re-triggered the binocular excursion in a loop (since returning from it resets
`sight_search_leg` to the cycle's first leg, which would immediately re-satisfy "entry condition")
or double-fired the glance-away. Moving the trigger to
`_decide_without_guidance`'s existing `home_phase is SIGHTING` / glance-away-resume branch (right
where `elapsed >= SIGHT_GLANCE_AWAY_S` previously called `_back_to_home` unconditionally) resolves
this cleanly with a one-line change: if `sight_out_of_regard_search` is non-empty, detour into
`_enter_binocular_search` instead of `_back_to_home`; otherwise unchanged. This also has a side
effect worth flagging explicitly: **the sight's aim resets to dead-ahead `(0.0, 0.0)` on every
resume from the glance-away now**, including the lap-completion-triggered one — because
`_start_glance_away` (shared, unmodified, by both triggers) already nulls `look_azimuth_deg`/
`look_elevation_deg` on entry, and `_back_to_home`/`_enter_binocular_search` only default to
`(0.0, 0.0)` when the aim is `None`. This is **not a new regression** — it is the exact behaviour
the pre-existing `SIGHT_MAX_DWELL_S`-triggered glance-away already had; the lap-completion trigger
just reuses the same function and inherits it. Tests assert this explicitly (`(0.0, 0.0)` on
resume, not "last position") rather than silently assuming the old "stays at last position"
framing from `_enter_binocular_search`'s own (pre-existing) docstring, which only ever held when
binoculars were entered directly from mid-lap, not through a glance-away.

**3. A multi-leg `ScanPlan.commanded_legs` (a converted compass-absolute scan) is not handled by
`_sight_commanded_sector`** — falls through to the no-commanded-sector default, same as before
this function existed. The plan's own text names only the single-o'clock-hour case
("`ScanPlan.commanded_legs`, one int"); extending this to a multi-leg compass scan for the sight
specifically is unscoped here, same posture `_search_sweep`'s own docstring already states for the
binocular search ("still gated on `commanded_sector` alone, not `commanded_legs`").

## Notable Discoveries

- **At 1500 m AGL dead level, `wide_near` and `wide_far` are both genuinely empty** — the sight's
  own -15° down-regard limit cannot reach a near-band target from that altitude without nose-down
  pitch; only `narrow_far_sweep` reaches. -8° of nose-down recovers all three legs. This matches
  the explore notes' own residue ("the altitude at which a band empties moves with pitch") but in
  the *opposite* direction from the plan's own worked nose-up example — worth flying before
  trusting the 1–2 km band produces a useful lap at level flight.
- **At 800 m AGL with 10° of nose-up, `wide_near` empties too** — a direct consequence of this
  stage's own near-edge correction (2333 m → 1500 m): the near edge is now steep enough from
  800 m that even +10° of nose-up pitch correction leaves the required depression (-18.1°) past
  the mount's -15° limit. 100/300 m AGL and 800 m/5° all stay reachable. Neither case crashes or
  stalls the search cycle — `_idle_sight_search`'s existing leg-skip fallback handles an emptied
  leg by moving to the next nonempty one — but it means the "wide_near's near edge stays
  reachable" framing in the plan's own Tests section does not hold universally across the full
  50–800 m AGL × {5°, 10°} nose-up grid; it holds at every combination except 800 m/10°. Recorded
  precisely (not just "mostly reachable") so a reviewer can recheck the boundary rather than
  re-deriving it.
- **`_start_glance_away` already nulled the aim before this stage** — see Deviation 2. The
  pre-existing `SIGHT_MAX_DWELL_S`-triggered glance-away already reset to dead-ahead on resume;
  this was not previously exercised by a test that checked the *resumed* aim specifically (the
  existing tests checked the decision *during* the glance-away, which is `None`/not asserted, not
  the aim after `_back_to_home` runs). The new lap-completion trigger made this visible because my
  first draft of `TestSightSearchLegs` assumed "stays at last position" and failed against the
  real code — a case of my own test being wrong, not the implementation; corrected rather than
  the production code changed, since the "reset to dead ahead on any glance-away resume" behaviour
  predates this stage and reusing `_start_glance_away` unmodified is exactly what the plan asked
  for ("Both triggers call the same function").

## Checks

All run from `body-layer/`:

- `ruff format --check src tests tools`: pass
- `ruff check src tests tools`: pass
- `mypy src` (from inside `body-layer/`): pass — "Success: no issues found in 74 source files"
- `mypy tools` (from inside `body-layer/`): pass — "Success: no issues found in 10 source files"
- `pytest tests -q`: pass — 2587 passed, 4 xfailed (pre-existing xfails, untouched)

## Not built this round

- Stage 2 (pointing at a known place) — left designed per the plan, not built.
- The "quick position check" for a known, unmoved contact — the plan's own open Decision,
  recommended left as the stand-in ("simply don't re-look") until Stage 1 has flown.
- The wide-band split (1.5–4 / 4–8 km) and the narrow-far-sweep band (8–13.6 km) remain
  unconfirmed starting values past the 1.5 km near edge, per the plan's own open Decision.
