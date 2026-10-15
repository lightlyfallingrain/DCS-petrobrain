## Pass 2 — Stage 2, the §7 directional cone, and the optic-aware range cap

### Implementation Summary

Second and final implementation pass for `BL-B64`. Built on
`worktree-agent-9k113-stage2` (branched from `feature/9k113-sight` at
`118d4dc01841422541998cae3a944028ca7a4734`, HEAD matched exactly, no merge
needed). Two commits:

1. **Stage 2** — the sight becomes selectable (a new `OpticPhase.SIGHTING`,
   reachable only via `home_phase`, never as a bolted-on fourth phase), the
   1 s hand-movement exclusivity (`hands_busy_until_sim`), and violent
   manoeuvre forcing OBSERV off (`SIGHT_STEADY_RATE_LIMIT_DEG_S`).
2. **The §7 cone and the §12a optic-aware range cap**, built together —
   `plans/9k113-sight/performance-cone-gate.md` already cleared the cost
   question (0.02–0.11% of the tick, no bounding mechanism needed), so this
   pass built the pair plainly with no candidate cap or pre-filter.

### Design decisions beyond what the plan specified

The plan and direction document settle *what* OBSERV does at the policy
level (§6, §9, §13, §13a) but leave the exact internal shape of
`SIGHTING`'s own dwell/look cycle to the implementer, flagging
"simplification is expected" (direction §4). The shape chosen, and why:

- **`SIGHTING` plays the role `GLASSING` plays today — continuously, as the
  home phase — rather than as a separate sub-phase reached from it.** §9's
  framing ("the sight is the baseline, the naked eye is the interruption")
  reads most literally as: entering `SIGHTING` (via `_back_to_home`) is
  itself the "closer look" act, picking a target via the *same*
  `choose_look`/`is_worth_a_look`/`look_sweep` machinery `GLASSING` already
  uses, with `SIGHT_NARROW_OPTIC` as the look optic and `SIGHT_WIDE_OPTIC`
  as the idle-rest optic — mirroring `BINOCULAR_OPTIC`/`UNAIDED_OPTIC`'s
  own roles, just both folded into one phase instead of two. The brief
  naked-eye glance-away (direction §9's "quick glance around") is the
  *old* `SCANNING` phase, now reached from `SIGHTING` at a *dwell* boundary
  (`SIGHT_MAX_DWELL_S`) exactly as `GLASSING` is reached from `SCANNING` at
  a *scan* boundary today — `_start_glance_away`/`_back_to_home` are the
  two halves of that symmetry. This reuses the existing choose-target/
  sweep/commit-or-drop machinery almost entirely; the net new code is one
  function (`_decide_sighting`) plus the glance-away's few lines inside
  `decide`'s own `SCANNING` branch.
- **No autonomous wide/narrow switching logic beyond that resting/looking
  split.** §4's human example (wide-find, range, narrow-classify, wide
  again) is explicitly "not directly translatable to code" and
  simplification is authorised. `SIGHT_WIDE_OPTIC` is used exactly while
  idle (nothing worth a closer look); `SIGHT_NARROW_OPTIC` exactly while a
  look is in progress. There is no mid-look wide/narrow toggle. Flagging
  this because it is the single biggest simplification against the user's
  own worked example, and the one most likely to want revisiting after
  Stage 3's acceptance sortie.
- **A resolved look inside `SIGHTING` picks the next target immediately,
  without forcing a break.** Only `SIGHT_MAX_DWELL_S` (the whole dwell
  since entering the sight) forces the scheduled glance-away; `look_is_
  finished` firing on the *current* look just clears it and `_decide_
  sighting` falls through to `choose_look` again on the same poll's
  return. This is what makes the break "scheduled" rather than "whenever
  nothing is left to look at," per direction §9's own framing.
- **`lower_binoculars` generalises past "am I home" into "is there an
  active look to drop."** `SCANNING`-at-home never has `look_contact_id`
  set while it is the current phase (only `GLASSING`/`SEARCHING` do), so
  this distinction is unreachable, and therefore a no-op in effect, for
  every OBSERV-off caller — but `SIGHTING`-at-home *can* have an active
  look (it is its own "closer look"), so a player command must still be
  able to drop that look back to idle without touching `home_phase`. Found
  by writing the test for "lowering while sighting is home" and discovering
  the naive `state.phase is state.home_phase -> no-op` check silently
  failed to drop an in-progress look — see Notable Discoveries.
- **The player-bubble cone and the sight's own pointing direction are the
  same `actual_aim_*` fields §15a already split**, never belief's desired
  aim — `logger._apply_active_gaze` builds the `SightCone` from the exact
  same `updated_state.actual_aim_azimuth_deg`/`elevation_deg` it builds the
  `Gaze`/`ScanPlan` from, in the same function, so the two can never drift
  apart (there is no second conversion point that could read a different
  value). The cone is `None` whenever idle-wide (no committed aim) — this
  is not a special case, it falls out of `actual_aim_*` being cleared
  whenever `decision.look_azimuth_deg is None`, which idle-`SIGHTING`'s
  `OpticDecision(optic=SIGHT_WIDE_OPTIC)` (no azimuth) already produces.
- **`Optic.range_cap_m` is reused for both the visibility gate's sanity
  bound and the cone's own depth**, rather than two separate numbers. Both
  answer "how far can this optic's reach plausibly extend," and direction
  §7 fixed both at 20 km for both sight settings — giving them independent
  numbers that happen to start equal would be the kind of coincidental
  agreement this project's own conventions (e.g. `PLAYER_BUBBLE_RADIUS_M`
  vs. `NAKED_EYE_RANGE_CAP_M`) treat as a trap, not a shortcut. `Optic.
  range_cap_m` is `None` (not a literal `10_000.0`) on `UNAIDED_OPTIC`/
  `BINOCULAR_OPTIC`, so `optics.py` never has to duplicate `visibility.
  NAKED_EYE_RANGE_CAP_M`'s value — `check_visibility`/`tier_ranges` resolve
  the `None` default themselves, which is also what keeps `optics.py` free
  of any import from `visibility.py` (the circular import slice 2A
  deliberately dissolved).
- **The cone's angular test is azimuth-only, not a true (azimuth+
  elevation) separation.** This matches the plan's own §12b cost
  arithmetic (`(fov/360) * π * (20² - 10²)`, purely azimuthal) and
  `association.FORWARD_HEMISPHERE_HALF_WIDTH_DEG`'s own precedent in the
  same module, rather than `within_optic_fov`'s great-circle test. The
  bubble itself has no elevation term either (it is a flat-range circle),
  so an elevation-aware cone would be inconsistent with the filter it
  extends.

### Files Changed

- `src/perception/optics.py` — `Optic` gains `range_cap_m: float | None =
  None`. `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC` set it to `20_000.0`
  (direction §7's cone depth, deliberately the same figure as the cone but
  not aliased to it — see Design decisions above).
- `src/perception/visibility.py` — `tier_ranges`/`check_visibility` both
  resolve `optic.range_cap_m if optic.range_cap_m is not None else
  NAKED_EYE_RANGE_CAP_M` in place of the hardcoded `NAKED_EYE_RANGE_CAP_M`
  constant, kept in sync by construction (both read the same optic).
- `src/perception/association.py` — new `SightCone` dataclass
  (`azimuth_deg`/`half_angle_deg`/`depth_m`, body-relative). `filter_
  player_bubble` gains `sight_cone: SightCone | None = None`: a candidate
  beyond `PLAYER_BUBBLE_RADIUS_M` but inside the cone's wedge and depth
  survives. `None` is a true no-op — the branch only runs for a candidate
  that already failed the radius test.
- `src/belief/optic_policy.py` — the bulk of the change:
  - Four new `tuning.real(...)` constants: `HANDS_BUSY_DURATION_S` (1.0,
    lo 0.1/hi 5.0), `SIGHT_STEADY_RATE_LIMIT_DEG_S` (30.0, lo 12.0/hi
    90.0 — `lo` pins the cross-key coupling with `STEADY_RATE_LIMIT_DEG_S`
    at the per-key level, see Cross-key couplings below),
    `SIGHT_MAX_DWELL_S` (30.0, lo 5.0/hi 120.0), `SIGHT_GLANCE_AWAY_S`
    (3.0, lo 1.0/hi 15.0). All `status="judgement"`.
  - `OpticPhase.SIGHTING` added.
  - `OpticState` gains `home_phase: OpticPhase = OpticPhase.SCANNING`,
    `hands_busy_until_sim: float | None = None`, `look_started_sim: float
    | None = None` (the per-look clock `SIGHTING` needs, distinct from
    `phase_started_sim`'s whole-dwell role there).
  - `OpticDecision` gains `suppressed: bool = False`.
  - `is_steady` gains `rate_limit_deg_s: float = STEADY_RATE_LIMIT_DEG_S`
    (keyword-only-by-convention, positional-compatible) so the sight's own
    threshold reuses the mechanism rather than duplicating it.
  - `look_is_finished` gains `started_sim`/`max_dwell_s` keyword
    parameters (defaulting to `state.phase_started_sim`/`MAX_LOOK_S`, i.e.
    `GLASSING`'s unchanged shape) so `SIGHTING` can pass its own per-look
    clock and dwell ceiling through the same function.
  - `_back_to_scanning` renamed `_back_to_home`: returns to `state.
    home_phase` (not hardcoded `SCANNING`) with a home-aware optic
    (`_HOME_OPTIC` dict: `SCANNING -> UNAIDED_OPTIC`, `SIGHTING ->
    SIGHT_WIDE_OPTIC`).
  - New `_start_glance_away` (enters the bounded naked-eye interruption
    from `SIGHTING`) and `_force_observ_off` (a violated `sight_steady`
    drops `home_phase` back to `SCANNING` entirely, then calls `_back_to_
    home`).
  - New `_decide_sighting` — `SIGHTING`'s own body; see Design decisions.
  - `lower_binoculars` generalised: `state.phase is state.home_phase` with
    no active look is a no-op (unchanged for OBSERV-off); with an active
    look (only reachable for `SIGHTING`), drops it back to idle without
    touching `home_phase`.
  - `decide`'s dispatch: hands-busy check (returns `OpticDecision(optic=
    UNAIDED_OPTIC, suppressed=True)`, no phase advance) right after the
    first-poll branch; `SIGHTING` dispatches to `_decide_sighting`; the
    `SCANNING` branch splits on `state.home_phase` into the glance-away
    sub-state (when `home_phase is SIGHTING`) or the original, untouched
    scanning-at-home body (when `home_phase is SCANNING`). The two
    pre-existing fresh-`OpticState(...)` construction sites (entering
    `SEARCHING`/`GLASSING`) now also carry `home_phase`/`hands_busy_
    until_sim` forward explicitly, alongside `actual_aim_*` — a no-op in
    value today (both branches only run when `home_phase is SCANNING`),
    but the rule is the same one Stage 1's review flagged as the real
    trap, so it is honoured here too rather than left implicit.
- `src/perception/naked_eye_source.py` — `NakedEyePerceptionSource` gains
  `sight_cone: SightCone | None = None` and `suppressed_until_sim: float |
  None = None`. `poll()` returns `[]` immediately while suppressed,
  without touching `_previously_seen_at`/`_acquired_at` (a deliberate
  pause, not a data gap). `filter_player_bubble` call threads `sight_cone`
  through.
- `src/logger.py` — `decide_optic` call in `run_once` passes `sight_steady
  =is_steady(list(self.attitude_history), rate_limit_deg_s=
  SIGHT_STEADY_RATE_LIMIT_DEG_S)` (a second call against the same
  history, the sight's own threshold). `_apply_active_gaze` builds
  `sight_cone` (from `optic.regard_azimuth_half_deg is not None` — a
  general "is this optic pointed/slewed" test, not a name check against
  the two sight optics — and the resolved *actual* aim) and `suppressed_
  until_sim` (from `optic_state.hands_busy_until_sim`), assigning both
  onto every `NakedEyePerceptionSource` alongside `scan_plan`/`optic`. The
  big `--crew-text` poll loop applies `crew_console.observ_transition`
  ("on"/"off") onto `runner.optic_state` (`home_phase` plus a fresh
  `hands_busy_until_sim`), consuming-and-clearing it, in the same lagged-
  one-poll slot `attack_run_transition` already uses.
- `src/belief/crew_console.py` — `observ_transition: Literal["on", "off"]
  | None = None` field (same one-shot-signal shape as `attack_run_
  transition`), reset at the top of every `handle_command` dispatch.
  `"observ_on"`/`"observ_off"` tokens added to `DISPATCHED_COMMAND_TOKENS`
  and dispatched to new `_handle_observ_on`/`_handle_observ_off` (readback
  `"Observ on."`/`"Observ off."`, unconditional).
- `config/defaults.toml` — regenerated via `tools/generate_defaults.py
  --write` for the four new tunables. Rendered output read directly (not
  the source comments): all four render with their own description,
  status and range line, correctly scoped under a new `[belief.
  optic_policy]` table. One cosmetic note, not a defect: because each
  constant's first English sentence contains a mid-sentence citation
  ending in a digit (e.g. "...Stage 2." / "...plan §13."), the generator's
  sentence-splitter (which deliberately never splits a period preceded by
  a digit, so "0.1" never splits) merges that citation with the sentence
  after it, so three of the four render two sentences' worth of text
  rather than one. Not corrupted or truncated — just longer than a single
  clause — and not something this entry's scope extends to fixing (the
  splitter regex is shared infrastructure).
- Tests — see below.

### Tests Added

46 new tests across six files (exact count: `git diff` shows +46/-0 `def
test_` lines, matching `1929 - 1883 = 46` precisely).

- `tests/test_optic_policy.py` (+22) — `TestObservOffIsBitIdentical` (3:
  `sight_steady`/`hands_busy_until_sim` defaults are true no-ops on the
  ordinary cycle); `TestObservOn` (2: commanding OBSERV on mid-`GLASSING`
  does not interrupt the look; the look's natural end hands back to
  `SIGHTING`, not `SCANNING`); `TestSightingDwellCycle` (7: idle rests
  wide, a target is picked with no scan-boundary gate, a look continues
  across polls, a resolved look picks the next target without forcing a
  break, the scheduled break fires regardless of what's worth looking at,
  the glance-away returns to sighting and resumes the look on the next
  poll, the glance-away holds naked-eye before its own duration elapses);
  `TestManoeuvreForcesObservOff` (2: an unsteady sight poll drops
  `home_phase` entirely and discards pending marks; the sight's own gate
  does not affect an ordinary binocular look); `TestHandsBusy` (3:
  suppressed while busy, not suppressed once elapsed, the constant is
  positive); `TestLowerBinocularsPreservesObserv` (4: idle-at-home no-op,
  an active look is dropped without leaving `home_phase`, mid-glance-away
  hands back to `SIGHTING` not `SCANNING`, dropping a sight look clears
  pending marks); `TestSightSteadyRateLimitIsHigherThanBinoculars` (1: the
  cross-key coupling, see below).
- `tests/test_association.py` (+6) — `SightCone` as a true no-op when
  `None`; admits inside its wedge and depth; rejects outside the wedge;
  rejects beyond its own depth; does not re-admit (or exclude) a candidate
  already inside the ordinary radius; azimuth is body-relative to
  ownship's own heading, not true bearing.
- `tests/test_visibility.py` (+5) — the narrow sight's 20 km cap admits a
  T-72B past the naked-eye's 10 km cap (the exact §12a scenario); the
  sight's own cap still rejects beyond 20 km; the naked eye is unaffected
  by the sight's cap existing; both sight optics carry the same 20 km
  figure; `tier_ranges`' presence threshold resolves each optic's own cap
  (a 100 m object exercises the cap binding for both the naked eye at 10
  km and the narrow sight at 20 km — an ordinary 7 m vehicle never reaches
  either cap, so it cannot distinguish them).
- `tests/test_crew_console.py` (+3) — "Observ on"/"Observ off" each signal
  the poll loop and speak; the signal resets at the top of the next
  dispatch (the same convention `attack_run_transition` already proves).
- `tests/test_naked_eye_source.py` (+5) — suppressed yields no
  observations; no longer suppressed once the duration elapses;
  suppression does not touch dedup state; the cone admits a candidate
  beyond the bubble end-to-end through the real `poll()` pipeline (optic
  FOV, gaze, and the optic-aware cap all included, not mocked); the same
  scenario with no cone is rejected by the ordinary radius test
  (demonstrating the cone is additive, not a relaxation).
- `tests/test_logger.py` (+5) — `_apply_active_gaze` builds a `SightCone`
  from the resolved actual aim; builds no cone for a non-sight optic
  (`regard_azimuth_half_deg is None`); builds no cone while idle-sighting
  (no committed aim); sets `suppressed_until_sim` from `OpticState.hands_
  busy_until_sim`; defaults to `None`.

### Checks

(body-layer/ only — the only subproject touched)

- `ruff format --check .`: fails only on the pre-existing out-of-scope
  `research/2026-10-05-security-audit.md`, same two lines the first pass
  already predicted (confirmed by diffing against a blanket `ruff format
  .` run and reverting that one file — see Notable Discoveries).
- `ruff check .`: pass.
- `mypy src`: pass (0 errors, 59 source files). `mypy src tests` reports
  150 pre-existing errors across 16 test files unrelated to this entry's
  diff (confirmed by running it before any of this pass's edits, via `git
  stash`) — the project's documented command is `mypy src`, not `mypy src
  tests`; noted so a future reader doesn't mistake that number for a
  regression.
- `pytest -q`: **1929 passed, 4 xfailed** (baseline 1883 passed, 4
  xfailed). 46 net new tests, 0 removed, 0 modified — every pre-existing
  test in every touched file passes unchanged, which is the direct
  evidence for the OBSERV-off bit-identical claim below.
- xfailed count unchanged (4 -> 4).

### Notable Discoveries

- **The naive `lower_binoculars` generalisation (`state.phase is state.
  home_phase -> no-op`) was wrong, and a test caught it before it shipped.**
  `SCANNING`-at-home never has `look_contact_id` set while it is the
  current phase, so for OBSERV-off this check is correct by construction.
  But `SIGHTING`-at-home *is* its own "closer look" (this pass's own
  design choice, see above), so the same check made dropping an
  in-progress sight look impossible — a real regression against the
  binocular case, where a player command always ends an active `GLASSING`
  look. Fixed by also checking `state.look_contact_id`, which costs
  nothing for OBSERV-off (that field is always `None` while `phase is
  SCANNING`).
- **`is_worth_a_look` excludes a contact already mid-look, and `_decide_
  sighting`'s first draft re-ran it every poll — which silently ended
  every look after exactly one poll.** `is_worth_a_look`'s own docstring
  says why: a contact in `pending_attempted_at_range_m` reads as "a look
  already in progress... not worth *starting a second* one." `GLASSING`
  never hits this because it steps through its sweep by index, never
  re-selecting. The first draft of `_decide_sighting` filtered through
  `is_worth_a_look`/`choose_look` unconditionally on every poll, which
  excluded the very contact it had just started looking at, read `chosen`
  as some other target (or `None`), and reset to idle-wide every second
  poll. Caught by `test_the_look_continues_on_the_next_poll`, which failed
  on the first run. Fixed by checking "is there already a look in
  progress" *before* re-running the target-selection machinery at all —
  the same ordering `GLASSING`'s own dispatch (`state.phase is GLASSING`
  short-circuits before `SCANNING`'s choose-look body ever runs) already
  uses, just not yet applied inside `SIGHTING`'s single phase.
- **`_back_to_home` rests idle for exactly one poll before `SIGHTING`
  picks a target, which is a real (if small) behavioural difference from
  what a first reading of "no scan boundary to wait for" suggests.**
  Returning home from the glance-away (or from `GLASSING`/`SEARCHING`)
  always produces the home phase's *idle* decision (`_HOME_OPTIC[home_
  phase]`) — it does not also run the target-picking logic inline. For
  `SCANNING`-at-home this is invisible (there is a whole `scan_cycle_
  period_s` to wait out anyway before a look can start). For `SIGHTING`
  it means the very next poll after a glance-away resolves is idle-wide,
  and the poll *after that* is the first one that can pick a target. One
  poll's latency at whatever rate `decide` is called — not loop-rate yet
  (that is `[[BL-B63]]`'s own stage) — so currently ~1 s at this project's
  existing 1 Hz poll. Worth knowing before Stage 3's sortie: a target
  appearing exactly as the sight returns from a glance will take one
  extra poll to be picked up, not zero.
- **A positive finding, not a defect: every pre-existing test in every
  touched file passed on the first run, with zero edits, after Stage 2's
  entire refactor landed.** This is the direct evidence for plan §13's
  "OBSERV off is bit-identical by construction" claim, verified by running
  the full suite (and this entry's own new `TestObservOffIsBitIdentical`
  class) rather than merely asserted from the design.

---

### Implementation Summary

`BL-B64` Stages 1 and 1b, plus direction §14 (`UNAIDED_OPTIC` FOV), implemented on
`worktree-agent-9k113-impl` (branched from `feature/9k113-sight` at
`08c512fe69d33472de67789679c03948be93753a`). Scope held to exactly the four items in
the task brief: the two sight optics as table entries (nothing selects them), the
per-optic position-sigma mechanism (`BL-B55`, folded in), the desired/actual aim field
split (§15a), and `UNAIDED_OPTIC.fov_half_angle_deg: None -> 90.0`. No cone, no
optic-aware range cap, no selection/`optic_policy` resting-phase change, no slew
controller — all deliberately out of scope per the brief.

### Files Changed

- `src/perception/optics.py` — `Optic` gains three field-of-regard fields
  (`regard_azimuth_half_deg`, `regard_elevation_up_deg`, `regard_elevation_down_deg`,
  all `float | None = None`, unread by anything yet). Added `SIGHT_WIDE_OPTIC`
  (3.55/7.00/6.50, FOV half-angle 5.75°, regard ±60°/+20°/−15°) and `SIGHT_NARROW_OPTIC`
  (5.81/13.75/15.00, FOV half-angle 3.0°, same regard). `UNAIDED_OPTIC.fov_half_angle_deg`
  changed `None -> 90.0`. Rewrote the module's stale "scope cut" paragraph and
  `within_optic_fov`'s docstring (the `is None` branch is now unreachable from this
  table but kept, with a comment, for a future peripheral-awareness pseudo-optic).
- `src/perception/estimation.py` — `naked_eye_sigma_m` renamed to `look_sigma_m`,
  gained a mandatory `optic: Optic` parameter. Added two tunable down-range scale
  constants (`SIGHT_WIDE_RANGE_SIGMA_SCALE` 0.5, `SIGHT_NARROW_RANGE_SIGMA_SCALE` 0.3,
  both `status="judgement"`) and two derived (non-tunable) cross-range scale dicts
  keyed by `optic.name`, computed from the FOV ratio against `BINOCULAR_OPTIC`. Both
  dicts default unmatched optics (`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`) to `1.0` —
  behaviour-preserving for every optic that existed before this entry.
- `src/perception/naked_eye_source.py` — threaded `self.optic` into the one
  `look_sigma_m` call site in `_build_observation`. That call already runs once per
  cluster, so "a group is ranged once with a shared draw" (direction §11) is a
  structural consequence of this one parameter, not a separate mechanism.
- `src/belief/optic_policy.py` — `OpticState` gains `actual_aim_azimuth_deg`/
  `actual_aim_elevation_deg` (both `float | None = None`). Added `advance_sight_aim(
  actual_az, actual_el, desired_az, desired_el, *, dt_s)`, whose body is `return
  (desired_az, desired_el)` — the perception-stage pass-through; `dt_s` is accepted and
  unused, reserved for `[[BL-B66]]`'s controller. Fixed the two branches of `decide()`
  that construct a fresh `OpticState(...)` (entering `SEARCHING`, entering `GLASSING`)
  to carry the two new fields forward explicitly — they are not part of `decide`'s own
  phase bookkeeping, so a phase transition must not reset them.
- `src/logger.py` — `_apply_active_gaze` is the one conversion point (plan §15a) where
  `OpticDecision`'s desired aim becomes the `ScanPlan`/`Gaze` perception treats as fact.
  It now takes `optic_state: OpticState | None` and `dt_s: float`, calls
  `advance_sight_aim` there, builds the `ScanPlan` from the *actual* result, and returns
  the updated `OpticState` (or `None` if nothing changed) for the caller to persist.
  When no look is commanded, actual aim is cleared to `None` too, mirroring
  `OpticState.look_azimuth_deg`'s own contract. `run_once` computes `dt_s` from the
  previous poll's `last_t_sim` and persists the returned state back onto
  `self.optic_state`.
- `src/perception/visibility.py`, `src/perception/detection_trace.py` — updated two
  comments that asserted `UNAIDED_OPTIC`'s FOV gate is a documented no-op; both are now
  live as of the `None -> 90.0` change. Also fixed `NAKED_EYE_RANGE_CAP_M`'s
  independently-stale docstring (claimed a 7 m vehicle reaches 9333 m from a threshold
  value that no longer exists; corrected to 2333 m from the current
  `LOWRES_ANGULAR_RADIUS_RAD = 0.003`) — touched while reading this file for the §14
  comment fix, as the brief invited.
- `src/belief/groups.py`, `src/belief/association_over_time.py` — updated two
  docstrings that claimed "the 9K113 does not exist in this code" / that
  `perception.estimation` is optic-blind. Both are now literally false; reworded to
  say the sight optics exist but nothing selects them, and binoculars remain
  deliberately unfixed (no sourced figure to assign them).
- `config/defaults.toml` — regenerated via `tools/generate_defaults.py --write` for
  the two new tunables above. Read the rendered output; both entries render cleanly
  with their own description, status and range.
- `tests/test_optics.py`, `tests/test_estimation.py`, `tests/test_optic_policy.py`,
  `tests/test_logger.py`, `tests/test_position_belief.py` — see below.

### Tests Added

- `test_unaided_optic_field_of_view_still_admits_anything_within_90_degrees` — an
  ordinary off-boresight candidate is unaffected by the `None -> 90.0` change.
- `test_unaided_optic_field_of_view_now_rejects_past_90_degrees_true_separation` — the
  one real behaviour change: a candidate whose true (azimuth+elevation) separation
  from the boresight exceeds 90° is now rejected, where `None` admitted it
  unconditionally. Moved from the now-false `TestBoresightElevation.test_the_unaided_
  eye_ignores_the_boresight_entirely` (see Notable Discoveries).
- `test_binocular_optic_gets_the_same_sigma_as_the_naked_eye` — pins that `BL-B55`'s
  fix is scoped to the two sight optics only; binoculars must produce the exact
  naked-eye sigma until a sourced figure exists for them.
- `test_sight_optics_get_a_smaller_down_range_sigma_than_the_naked_eye` — narrow <
  wide < naked eye, and pins both against the named tunable constants directly.
- `test_sight_cross_range_sigma_is_derived_from_the_fov_ratio` — narrow < binocular <
  wide, following from each optic's own sourced `fov_half_angle_deg`.
- `TestAdvanceSightAim` (3 tests) — the pass-through body, including the
  no-prior-actual case (first poll of a look), and that `dt_s` is accepted but inert.
- `TestOpticStateActualAimCarriesForward` (2 tests) — entering `GLASSING` and entering
  `SEARCHING` both preserve a pre-existing actual aim rather than resetting it to
  `None`, the correctness property the effector stage's controller will depend on.
- `test_apply_active_gaze_builds_the_scan_plan_from_actual_aim`,
  `test_apply_active_gaze_returns_the_updated_optic_state_with_actual_aim_set`,
  `test_apply_active_gaze_clears_actual_aim_when_no_look_is_commanded`,
  `test_apply_active_gaze_returns_none_when_optic_state_was_never_given` — the
  conversion point's four observable behaviours: builds from actual, persists actual
  onto the returned state, clears actual when nothing is commanded, and stays a true
  no-op (`None`) for every caller that passes no `optic_state` at all.

### Checks

(body-layer/ only — the only subproject touched)

- `ruff format --check .`: fails only on the pre-existing out-of-scope
  `research/2026-10-05-security-audit.md`, as the task brief predicted.
- `ruff check .`: pass
- `mypy src`: pass (0 errors, 59 source files)
- `pytest -q`: **1883 passed, 4 xfailed** (baseline 1870 passed, 4 xfailed). Counted
  precisely, not estimated: `git diff` shows 15 new `def test_` lines and 2 removed
  (one rename, one genuine removal — `test_the_unaided_eye_ignores_the_boresight_
  entirely`, which asserted something no longer true), net +13 — matching
  1883 - 1870 = 13 exactly.
- xfailed count unchanged (4 -> 4), as expected: nothing in this stage touches the
  mechanisms those four xfails cover.

### Notable Discoveries

- **The `None`-fov asymmetry the architect's plan predicted was real and already had
  a victim.** `test_optics.py`'s `TestBoresightElevation.test_the_unaided_eye_
  ignores_the_boresight_entirely` asserted `within_optic_fov(UNAIDED_OPTIC,
  boresight_azimuth_deg=0.0, azimuth_deg=80.0, elevation_deg=-40.0,
  boresight_elevation_deg=30.0)` is `True` — true separation for that pair is ~102°,
  past the new 90° half-angle, so the test now correctly asserts `False`. Moved to
  `test_optics.py` next to its companion case rather than left in place asserting
  something false, per the task's instruction to explain rather than quietly adjust.
  No other test in the full suite depended on the `None` behaviour — the rest of the
  suite's gaze/visibility fixtures stay well inside 90° true separation by
  construction, which is itself worth recording: a 90° *azimuth-only* bound
  (`FULL_GAZE`) was already in force everywhere upstream, so almost nothing in this
  codebase exercises geometry anywhere near the true-separation boundary.
- **`look_sigma_m`'s per-optic dicts needed a `BINOCULAR_OPTIC` reference, and that
  reference is read live off the optic object, not duplicated as a literal.** The
  cross-range scale is `optic.fov_half_angle_deg / BINOCULAR_OPTIC.fov_half_angle_deg`
  computed once at import time into `_SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC` — this
  means if `BINOCULAR_OPTIC.fov_half_angle_deg` or either sight optic's FOV is ever
  retuned, the sight's cross-range scale moves with it automatically rather than
  silently drifting out of sync with a hand-copied number.
- **`UNAIDED_OPTIC`'s own `fov_half_angle_deg` must never feed the sigma-scale
  formula**, even though it is now a real number. It represents a peripheral-vision
  envelope (direction §14), not pointing precision, so using it as the ratio's
  denominator or numerator would silently claim the naked eye's bearing precision
  changed when nothing about the crewman's pointing ability did. Both scale dicts are
  keyed by `optic.name` with a `1.0` default specifically so `UNAIDED_OPTIC` never
  needs to appear in either dict at all.
- **`decide()`'s two "fresh `OpticState(...)`" branches were a real, if currently
  harmless, trap.** Because `advance_sight_aim`'s body is `return desired`
  unconditionally this stage, the missing carry-forward on `actual_aim_*` would not
  have caused a visible defect today — the value gets overwritten with `desired`
  immediately after `decide()` returns, every poll. It would have become a real bug
  silently the day `[[BL-B66]]` replaces the body with a real controller that needs
  the *previous* poll's actual aim to converge from. Found by reading every
  `OpticState` construction site instead of trusting that `replace()`-style
  construction was used throughout (it mostly is, but not in the two branches that
  start a fresh `SEARCHING`/`GLASSING` phase) — exactly the "enumerate the containing
  unit" lesson from this role's own memory.
