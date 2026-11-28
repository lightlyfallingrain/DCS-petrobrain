# BL-16 lift-vector law, M3 (terrain floor and look-ahead) — Implementation Summary

Built per `plans/flight-lift-vector/plan.md`'s "M3 amendment (2026-11-28)" in full (sections
A–F, the Implementation plan's four stages, the Tuning constants table, the Co-moving Fields
table), against the "Answered 2026-11-28" block (U18 yes, U19 ~100 km/h, U20 10 m/s, U21 yes,
U22 "every climb trades speed") — not the plan's own earlier recommendations. Cross-checked
`plan-aligner`'s "M3 terrain floor — plan check" (`alignment.md`): all three findings (the Risks
bullet, card row 11, and the missing Tests-list item for U22's ordinary-climb case) were already
backfilled into `plan.md` by the tip commit (`ca0bcb50`) before this build started — confirmed by
grep, not assumed.

## Files Changed

**aircraft-layer (the law and the data path):**

- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua` — `fc_limits.floor_agl_m` 40 → 50;
  `max_climb_vs_mps` removed from `fc_limits`/`FC_LIMIT_BOUNDS`. New module state `fc_terrain`
  (outside `fc_law`, like the estimator) + `parse_terrain_relay` (parses the lease's `terrain`
  field). New pure helper `law_terrain_w_floor` (section B). `law_apply_goal`: a new `alt_m`
  clears `terrain_return`. `law_init_at_take`: `terrain_return`/`terrain_binding` seeded `false`,
  `dbg_terrain_w_floor` seeded `nil`. `law_update`: derives `f_eff` (F_eff); floors `alt_goal_agl`
  beneath it; the break floor now uses `f_eff` (replacing the removed `profile.break_floor_agl_m`);
  computes `terrain_c`/`goal_asl`/`w_floor` and combines it with the ordinary shaper's own
  acceleration demand (whichever asks for more climb/less descent wins, approached at the accel
  cap — never a step); `terrain_ease_down_mps` caps the return once `terrain_return` is set (the
  step the floor stops binding) until altitude is back in band; the power governor
  (`w_ref_lead_max_mps`, gated on **last frame's own** `dbg_shortfall`/saturated `u_c` — this
  frame's shortfall is not known yet, the usual feedback-only posture) replaces the removed
  `max_climb_vs_mps` clamp; the speed absorber (`shortfall > 0` → `v_ref`/`dv_ref` yield toward
  `speed_give_floor_kmh`, same shortfall `theta_speed_give` already reads, no terrain-only
  branch — U22). `read_measured`: `asl_valid` (ASL genuinely read this frame, not the AGL
  fallback), `pos_x`/`pos_z`/`pos_valid` (world position, for the projection). `run_active_frame`:
  projects `fc_terrain` into `measured.terrain` (`{d, T}` pairs) against the CURRENT position/
  heading, gated on `asl_valid`/`pos_valid`/`terrain_max_age_s`. `handle_flight_lease_command`:
  parses the `terrain` field via the new raw-string extractor. `on_stop`: resets `fc_terrain`.
  Unpark seed clamp removed (`build_take_seed`'s old `seed.alt_m < fc_limits.floor_agl_m` branch)
  — a carried mode-2 height flies exactly as given (E10). Status line gains `fc_floor_eff_m`,
  `fc_terrain_n`, `fc_terrain_age_s`, `fc_terrain_w_floor`, `fc_terrain_binding`,
  `fc_speed_giving`; the flight trace gains `v_ref`/`h_ref`/`w_ref`/`terrain_return`/
  `dbg_terrain_w_floor`.
- `aircraft-layer/dcs-export/Petrobrain/flight_profile.lua` — removed `break_floor_agl_m`; added
  `terrain_lead_s`, `terrain_tau_min_s`, `terrain_min_speed_mps`, `terrain_max_age_s`,
  `terrain_lookahead_enabled`, `w_ref_lead_max_mps`, `speed_give_floor_kmh`,
  `terrain_ease_down_mps`.
- `aircraft-layer/dcs-export/Petrobrain/core.lua` — new `extract_json_raw_string_field` (the
  `terrain` field's own characters — `.`, `,`, `;`, `|`, `-` — are outside `extract_json_string_
  field`'s `[%w_]+` pattern), exported as `_G`, same convention as its siblings.
- `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` — new `terrain_points` op on the
  existing 7797 listener: `MAX_TERRAIN_POINTS` (32), `SET_TERRAIN_TEMPLATE` (66 `%d` conversions),
  `_applyTerrainPoints`, a `land.getHeight`-only evaluation loop in `LOS_CODE` (fail-closed, empty
  token on a failed/non-finite height), `pollInbound` drains the new op, `sendPayload`/
  `pollAndSend` carry a second `"\2"`-delimited sub-wire and `"terrain"` envelope key (the probes
  sub-wire keeps its own `"\1"` delimiter unchanged).
- `aircraft-layer/src/schema/line_of_sight.py` — `MAX_TERRAIN_POINTS`, `TerrainAnswers` (mirrors
  `ProbeAnswers`; non-finite height → `None`, never `0.0`), `LineOfSightSnapshot.terrain`/
  `terrain_raw`.
- `aircraft-layer/src/collector/line_of_sight_receiver.py` — reads the envelope's `"terrain"` key.
- `aircraft-layer/src/collector/command_sender.py` — `LookDirectionSender.send_terrain_points`;
  `CommandSender.send_flight_lease` gains a `terrain: str | None = None` parameter, sent as a
  third JSON field alongside `epoch`/`limits` (`Export.lua`'s own regex-based field extraction
  scans the whole message text, so nesting position doesn't matter).
- `aircraft-layer/src/api/server.py` — `POST /command/terrain_points` (mirrors `/command/
  probe_points`); `_FLIGHT_CONTROL_LIMITS_BOUNDS`'s `max_climb_vs_mps` entry removed;
  `/command/flight_lease` validates an optional `terrain` field on its own (length/pattern) — a
  bad one drops terrain only, never the lease or its `limits` (the existing whole-message-reject
  posture is deliberately not extended to this field).

**body-layer (the composer and the floor itself):**

- `body-layer/src/belief/flight_control.py` — `FLOOR_AGL_M` 40.0 → 50.0 (status `agreed-guess`,
  the user's own number — kept the project's existing status vocabulary rather than the plan
  table's own shorthand "user", which is not one of `tuning.Status`'s literal values).
  `MAX_CLIMB_VS_MPS` removed (constant and its `flight_control_limits()` wire entry). `clamp_
  altitude`'s AGL floor removed — only `>= 0` now.
- `body-layer/src/belief/terrain_ahead.py` — **new**: `compose_terrain_grid` (pure geometry,
  coarsens past `MAX_TERRAIN_POINTS` rather than truncating), `build_terrain_relay` (joins by
  index, drops non-finite/missing heights, age-gates on `TERRAIN_RELAY_MAX_AGE_S`), the four `[belief.terrain_ahead]` tuning constants.
- `body-layer/src/aircraft_client.py` — `post_terrain_points`; `write_flight_lease` gains a
  `terrain: str = ""` parameter.
- `body-layer/src/body.py` — `ConsolePerceptionRunner._terrain_sent`/`_terrain_seq` (a small ring
  of recently-sent grids, since the aircraft layer's answer lags by at least one poll — `_terrain_
  sent` is a `dict[int, TerrainGrid]`, pruned to `_TERRAIN_SENT_KEEP` (8) entries); `_reset_
  mission_state` resets `_terrain_seq` explicitly (`_terrain_sent`'s own `default_factory` field
  is already reassigned by the `self.__init__()` re-invocation there). New `_compose_and_relay_
  terrain` (composes/sends every poll, reads back the answer, joins and encodes it — every
  failure degrades to `""`, never raises); called from `_apply_flight_requests` right before the
  lease send, in every mode (never suppressed by the `overlay` branch — the lease itself is
  unconditional, matching F's "mode 2 untouched" by the floor/look-ahead rather than by the data
  path, which stays warm throughout).
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`); the
  rendered text was read and two source docstrings reworded after the render showed a joined-
  without-a-space artifact (`generate_defaults._join_comment_lines`'s own "no space inside a
  backtick span that crosses a line break" rule, triggered by a code-formula backtick opened on
  one `#:` line and closed on the next, not a dotted identifier).

**Tests:**

- `aircraft-layer/tests/test_line_of_sight_hook_lua.py` — mirrored every `SET_PROBES_TEMPLATE`
  test for `SET_TERRAIN_TEMPLATE`/the four-splice `LOS_CODE` prefix/the three-op coalescing guard.
- `aircraft-layer/tests/test_line_of_sight_schema.py`, `test_line_of_sight_receiver.py`,
  `test_line_of_sight_api.py`, `test_flight_control_api.py` — mirrored every `probes`/`probe_
  points` test for `terrain`/`terrain_points`, plus the lease's new `terrain` field (valid,
  malformed-drops-terrain-only, empty).
- `aircraft-layer/tests/test_flight_control_law.py` — fixtures (`_LIMITS`/`_PROFILE`) updated for
  the removed/added fields; two break-floor regression tests rewritten for the merged-floor
  mechanism (see "Notable Discoveries" below); two pedal-guard tests given a locally-overridden
  `alt_accel_cap_mps2` to restore a nominal rate the removed `max_climb_vs_mps` jump used to
  supply; three new test classes — `TestM3LookAheadHelperDirect` (direct `law_update` calls
  against `measured.terrain`: a ridge demands a climb, hover/below-min-speed disarms the whole
  grid (E8), points behind/below-the-goal/non-finite are dropped, a ridge above the goal bounds a
  descent, the kill switch degrades to no demand), `TestM3FloorDerivation` (`F_eff` itself, via
  `h_ref`'s own one-step-converged value), `TestM3TerrainClimbScenario` (the plan's own "A new
  terrain driver": a capped-authority point-mass plant, a ramp `g(x)`, a 1 Hz-refreshed grid
  re-projected every step — see "What this one scenario does not reach", below).
- `aircraft-layer/tests/test_flight_control_lua.py` — `flight_profile.ACTIVE` fixture gained the
  eight new fields; `_CORE_HELPERS` gained `extract_json_raw_string_field`.
- `body-layer/tests/test_terrain_ahead.py` — **new**: geometry (heading 0/90 with DELIBERATELY
  distinct step/half-width so an axis swap cannot pass on the defaults' coincidental equality,
  coarsening, the control point), relay encoding (finite/missing/non-finite/non-numeric heights,
  no-grid, stale-grid, all-missing).
- `body-layer/tests/test_body_flight_control.py` — `_FakeRunner` gained `last_ownship_state =
  None` (takes `_compose_and_relay_terrain`'s own early-return path) and the two private terrain
  fields; one lease-call unpacking updated for the new 3-tuple shape.
- `body-layer/tests/test_flight_authority.py`, `test_flight_control.py` — four tests rewritten
  for the removed floor (see "Notable Discoveries").

## Checks

**aircraft-layer/**

- `ruff format src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (from inside `aircraft-layer/`): pass, 0 issues in 29 source files
- `luac5.1 -p` on every touched Lua file (`flight_control.lua`, `flight_profile.lua`, `core.lua`,
  `petrobrain-line-of-sight-hook.lua`): pass
- `pytest tests -q -n auto`: **1313 passed** (full suite, run twice — once mid-work after the Lua
  law changes, once at the end after the schema/API/Hook changes)

**body-layer/**

- `ruff format src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (from inside `body-layer/`): pass, 0 issues in 96 source files
- `test_tuning_defaults_toml.py` (the `defaults.toml` staleness check): pass
- `pytest tests -q -n auto`: **3927 passed, 4 xfailed** (full suite, run three times across the
  fix rounds below; the final run — the one this number reports — found zero new failures)

## Notable Discoveries

1. **The break-floor mechanism's test premise inverted under the merged floor.** `profile.
   break_floor_agl_m` (50.0, independent of `limits.floor_agl_m`) is removed — the break now
   shares `f_eff`, the SAME floor every other command uses. `TestLV2BreakFloorIsBreakOnly`'s old
   technique ("force `state.alt_goal_m = 0.0` directly to probe the break floor independent of the
   ordinary goal") now defeats itself: under M3, an explicit AGL goal of 0 is honoured exactly
   (U18 — "allow player to command any altitude and then accept it"), which pulls `f_eff` itself
   down to 0 too, so the break floor the test meant to isolate collapses along with it. Rewrote
   the probe to use a deep barometric goal instead (`f_eff` for barometric is always `limits.
   floor_agl_m`, never AGL-goal-dependent) — this is a genuine mechanism change, not a cosmetic
   fixture update, so I flagged it here rather than silently patching the number.
2. **The same test's own convergence rate halved**, independent of (1): the new power governor
   (`w_ref_lead_max_mps`, 2.0) bounds the descent to `measured.w_mps +- lead` once collective
   bottoms at -1 — in this file's STATIC `measured` table (never updated to reflect "what the
   aircraft achieved," unlike the plant-integration scenarios elsewhere in the same file), that
   bound is a fixed -2 m/s, half the OLD `max_climb_vs_mps` cap (5 m/s) the test's own step count
   was timed against. Needed 1200 steps (60 s), not 400, to actually reach the floor — confirmed
   by running it before changing the number, not assumed from the arithmetic alone.
3. **Removing the hard `max_climb_vs_mps` clamp removes an artificial one-step jump two
   near-pedal-limit-guard tests depended on.** `TestCollectiveRateCapNearPedalLimit`'s own
   scenario (`w_mps = -10`, well outside the old `[-5, 5]` clamp) used to get a free, large `w_ref`
   correction from the clamp itself on the very first `law_update` frame, which is what pushed the
   scenario's nominal collective rate (0.447, per the test's own prior comment) above the guard's
   0.3 threshold. Without the clamp, the SAME scenario's nominal rate is ~0.18 regardless of how
   negative `w_mps` is (measured by sweeping it) — the guard test could no longer exercise
   anything. Fixed with a LOCALLY-overridden (not shared-fixture) `PROFILE.alt_accel_cap_mps2 =
   10.0` inside each of the two drivers, isolating the guard from this unrelated accel-cap change.
4. **`decide_carried_value_speech`'s own carried-value-announcement mechanism needed no code
   change at all** — it already compares `clamp_altitude(new.alt_m, ref)` against `new.alt_m` and
   announces only on a difference; removing the floor from `clamp_altitude` makes it correctly
   stop firing for a low carried AGL height (E10's own "no jump at the unpark"), with zero lines
   touched in `flight_authority.py`. Only the two tests asserting the old floor-triggered
   announcement needed rewriting (one to assert no announcement, one for the single remaining
   clamp branch — a negative carried altitude).
5. **The `generate_defaults.py` comment-joiner's own documented backtick-span rule bit a plain
   code formula, not a dotted identifier** — `_join_comment_lines` inserts no space across a line
   break while a backtick span is open, by design, for a dotted-path name split across two `#:`
   lines (`` `perception.estimation. `` / `` BEARING_SIGMA_DEG` ``). My own docstring opened a
   backtick before `F_eff = min(this,` and closed it after `AGL goal)` on the next line, which the
   same rule (correctly, by its own stated contract) joined with no space, rendering `min(this,
   AGL goal)` as `min(this,AGL goal)` in `defaults.toml`. Caught by reading the RENDERED file, not
   the source — exactly the habit root `CLAUDE.md`'s Tuning section asks for ("three separate
   defects in X-T26 lived in the gap between the two"). Fixed by rewording the docstring to avoid
   breaking a code span across the line, not by touching the generator.
6. **`handle_flight_lease_command`'s own `limits` field is nested JSON (`{"limits": {...}}`) but
   parsed by a flat, structure-blind regex** — confirmed by reading `command_sender.send_flight_
   lease` (which really does send `limits` nested) alongside `extract_json_number_field`'s own
   regex (which matches `"key":value` anywhere in the raw text, never walking a parsed tree). This
   is why the new `terrain` field can ride alongside `limits` in the same JSON object and still be
   read correctly by a flat extractor — worth recording since it is easy to assume (wrongly) that
   Lua-side field extraction in this codebase respects JSON nesting.
7. **`ROTOR_RPM_SOURCE`/engine-RPM gating and the M3 power governor are independent, confirmed by
   reading, not re-derived here**: the governor reads `state.dbg_shortfall`/`state.u_c` (law-
   internal), never the RPM guards' own `rotor_rpm_warning_pct`/`spooled_rpm_pct` gating directly
   — a future change to either RPM source's calibration cannot silently change the governor's own
   behaviour, and vice versa.

## What the toy plants still cannot show (M3's own "What the plant cannot show" list)

Unchanged from the plan's own accounting, confirmed by this build rather than re-asserted: the
real DCS frame/datum (`x`/`z`, `land.getHeight` vs `LoGetAltitudeAboveSeaLevel` — card row 1's own
job); whether slowing down really buys climb rate in the real Mi-24P (no speed-dependent climb-
capability term exists in any toy plant here, M3 or pre-M3); real rotor-RPM/engine behaviour at
the power limit; radar AGL over forest vs bare ground; the real route's latency/jitter (~1-3 s,
user-accepted); transitional lift at low speed.

**`TestM3TerrainClimbScenario`'s own scope, disclosed in its class docstring rather than silently
narrowed**: one gentle upslope, not the full multi-ridge/ease-down-after-the-crest cycle (E3/Q4);
the explicit-lower-height case (E5, already covered without a plant by the direct `F_eff` tests);
hover-behind-a-ridge (E8, covered directly in `TestM3LookAheadHelperDirect` instead, which needs
no closed loop at all). The scenario's own gains (`plant_w_gain = 6.0`, deliberately capped well
below the pre-existing plants' 15.0, per finding 9) are a first cut to demonstrate the mechanism
(climbs early, before the ramp; recovers near the floor afterward), not a measurement — it shows a
real, nonzero sag below the floor during the climb (bounded generously in the assertion rather
than asserted away), which is exactly the kind of first-cut-gain gap the live card's own rows 1-6
exist to catch for real.

## Deviations from the plan, disclosed

- **`BL-16.md`/`BL-B138.md` roadmap entries not touched** — the orchestrating brief explicitly
  reserved roadmap status edits for the main loop; the plan's own Implementation plan item 4 named
  these two files, so noting the gap here rather than silently completing or silently dropping it.
- **The terrain-driver toy-plant test covers one scenario, not the plan's own full list** — see
  above; disclosed in the test file itself (same posture `implementation-lv3.md`'s own "Fix pass"
  accounting table set) as well as here.
- **`FLOOR_AGL_M`'s tuning `status`** is `agreed-guess`, not the plan table's own "user" — `tuning.
  Status` has no such literal; `agreed-guess` is this codebase's existing vocabulary for "the
  user's own stated number," already used by every sibling constant in the same module
  (`BREAK_MAX_HEIGHT_LOSS_M`, `VRS_IAS_THRESHOLD_KMH`, …).

## Fix pass (`review-m3.md`)

Branch `fix/bl16-flight-epoch-bound`, worktree at tip `6d789b38`. Addressed all three findings.

**Required fix 1 — the missing U22 toy-plant case.** `aircraft-layer/tests/test_flight_control_
law.py`, new `TestM3OrdinaryClimbTradesSpeedNoTerrain`: a direct, `collective_was_capped`-style
scenario (`TestLV2HeightGivesFirst`'s own technique — a real `shortfall` forced via the rotor-RPM-
warning guard against a large climb demand), on a PLAIN altitude command (no break set, so the
break-only `effective_shortfall` scaling never engages) with `measured.terrain` never assigned
anywhere in the scenario. Confirmed by running it against the actual law (not assumed from the
formula): `v_ref` settles at exactly `speed_give_floor_kmh` (27.777... m/s) while the measured
speed this phase is driven even lower (70 km/h), the strongest form of "never below it"; the
shortfall that produced it is 0.368 (clearly real); once RPM and measured speed both recover,
`v_ref` is climbing back (34.69 m/s after 60 s — `omega_speed` is deliberately slow, so this is a
trend assertion, not full convergence, same posture every other toy-plant test in this file takes
with a first-cut gain). This closes the exact gap plan-aligner's Finding 3 predicted and the
Reviewer confirmed was never built: a future regression narrowing the governor's lead back to 0 for
an ordinary (non-terrain) climb now fails this test.

**Optional 2a — ease-down cap, direct.** New `TestM3EaseDownCapDirect`: a single `law_update` call
with `state.w_ref` already far past the cap (-50 m/s) and `state.terrain_return` set directly (the
Co-moving field a real terrain-stop-binding transition would have set, so no multi-ridge closed
loop is needed) confirms the unconditional `max()` against `profile.terrain_ease_down_mps` (10.0,
U20) binds every step regardless of how `w_ref` got there (`-10.0`, measured). The contrasting case
(`terrain_return` false) shows the same steep `w_ref` is left essentially untouched (`-49.95`,
measured) — "ordinary descents you command keep no limit" from the plan's own section C text.

**Optional 2b — the `|h| < 1e5` magnitude bound.** `flight_control.lua`'s `parse_terrain_relay` now
rejects a height outside `|h| < 1e5` the same way it already rejected a non-finite one (one `and
math.abs(h) < 1e5` clause, section E's own text: "each height re-checked `h == h` and `|h| <
1e5`"). New `aircraft-layer/tests/test_flight_control_lua.py` class
`TestTerrainRelayMagnitudeBound`, run through the whole-module harness (`handle_flight_lease_
command` → `fc_terrain_n` on the status line, confirmed live: a grid of one in-range and two
out-of-range heights reports `fc_terrain_n = 1`; an all-out-of-range grid reports `0`).

**Checks**, run from this worktree (no local `.venv`, so the main checkout's `aircraft-layer/
.venv` was used; `luac5.1`/`luajit` from Homebrew):

- `ruff format --check`: pass (the two touched test files).
- `ruff check`: pass.
- `mypy src` (from inside `aircraft-layer/`): pass, 0 issues in 29 source files (no production
  source changed other than the Lua file, which mypy does not cover).
- `luac5.1 -p flight_control.lua`: pass.
- `pytest tests -q`: **1318 passed** (1313 (review's own baseline) + 5 new: 1 in
  `TestM3OrdinaryClimbTradesSpeedNoTerrain`, 2 in `TestM3EaseDownCapDirect`, 2 in
  `TestTerrainRelayMagnitudeBound`), zero regressions, identical count with and without `-m "not
  slow"` (this subproject has no `slow`-marked tests).

No `body-layer` file was touched by this fix pass, so its suite was not re-run.

## Fix pass 2 (review-m3.md "Re-review (fix pass)" required fix)

The re-review found that `TestM3OrdinaryClimbTradesSpeedNoTerrain`'s recovery half never actually
exercised U22's "returns to the commanded speed once the shortfall ends": `measured.h_m` was never
advanced during the 60 s recovery loop, so the altitude-error term driving the collective
(`k_alt_error * (h_ref - measured.h_m)`) grew without bound against a frozen sensor, kept the
collective saturated, and `shortfall` never genuinely returned to `0.0` — the old assertion
(`v_ref_recovered > v_ref_floor_phase + 5.0`) passed anyway through a per-frame statement-order
leak, not real recovery.

**Fix**, confirmed by running the driver under `luajit` (per-frame traces, not assumed from the
formula) before writing any assertion: both loops in `_run_scenario` now advance `measured.w_mps`
and `measured.h_m` from `state.w_ref` each step — the same "sensor reports the climb" technique
this file's own bank/heading toy-plant scenarios already use (e.g.
`TestOvershootPastTheStoppingHeightStaysInsideTheBand`'s `measured.h_m = measured.h_m +
measured.w_mps * dt`), rather than a new closed-loop plant. With this change, `shortfall` reaches
`0.0` almost immediately after the RPM/speed recovery (measured: 0.05 s into the 60 s window, well
inside the review's own "~1 s" estimate), though a second, genuine power-limited saturation
recurs partway through the climb (this test's 500 m AGL step is large relative to the toy
`PROFILE`'s `alt_accel_cap_mps2` of 1.0 — a real, not artifactual, overshoot-then-recover of the
law's own altitude shaper) before `shortfall` settles at exactly `0.0` by the end of the 60 s
window. `v_ref` reaches `60.362485510` m/s against a `speed_goal_mps` of `61.111111111` m/s by then
— within 1.0 m/s, nowhere near the old +5.0 m/s margin a broken resumption path would still clear.

**New/changed assertions**: `shortfall_recovered == 0.0` (the premise U22's wording and the
original test's own docstring both assumed but never checked), `speed_goal_mps` read back from the
scenario itself (rather than retyped as a literal, so a future change to the take seed cannot
silently decouple the assertion from what the scenario actually commands), and `v_ref_recovered`
within `1.0` m/s of `speed_goal_mps` (a real convergence check, replacing the old "`> floor + 5.0`"
trend-only assertion). The floor-phase assertions are unchanged and unaffected (confirmed: floor
phase values are bit-identical to the prior pass, since the altitude error during that 1 s phase is
too small to move `measured.h_m` meaningfully).

**Mutation check, re-run**: patched a local copy of `flight_control.lua` to gate the section-D
speed-give block behind `state.terrain_return` (required-fix-1's own mutant) and re-ran the
updated test against it — still fails, at the floor-phase assertion (`v_ref_floor_phase` resolves
to the commanded `61.111` m/s instead of the `27.778` m/s floor, since the mutant disables the
give entirely for a non-terrain climb). The mutant is caught by the pre-existing floor-phase
assertions, which this fix pass does not touch; the new recovery assertions were not the ones this
particular mutant was aimed at catching (required-fix-1's own regression target), so no additional
mutant was built for them beyond the convergence tolerance itself.

Docstring corrected: the class-level docstring now records this fix pass and why the recovery
half needed it; the method's own recovery comment no longer claims the old assertion was "not
asserted at full convergence, only... moving back up" as a deliberate design choice — it now
explains the convergence check and cites the measured gap to `speed_goal_mps`.

**Checks**, run from this worktree (no local `.venv`, so the main checkout's `aircraft-layer/
.venv` was used; `luajit`/`luac5.1` from Homebrew, confirmed present):

- `ruff format --check src tests`: pass.
- `ruff check src tests`: pass.
- `mypy src` (from inside `aircraft-layer/`): pass, 0 issues in 29 source files (no production
  source touched — only the test file).
- `pytest tests -q`: **1318 passed**, same count as fix pass 1 (no test added or removed, only one
  test's own body changed), zero regressions.
- `luac5.1 -p`: not re-run — no Lua file was touched by this fix pass.

Only `aircraft-layer/tests/test_flight_control_law.py` changed in this pass.

## R1 (2026-11-28) — speed-give delta, performance finding 1, security findings 1/2

Built per `plan.md`'s "## M3 revision R1 (2026-11-28)" in full — all three parts, one batch, per
the orchestrator's task. Target branch tip confirmed: `git rev-parse HEAD` matched the expected
`9d7ffdb2` exactly (already at tip, no merge needed — the worktree had been fast-forwarded to it
before this task started).

### R1-a — `speed_give_max_delta_kmh`

`flight_profile.lua` gains `speed_give_max_delta_kmh = 50.0` (loop value, beside the existing
`speed_give_floor_kmh`, same home — both are per-aircraft loop gains the law reads, not a `tuning.py`
constant: `speed_give_floor_kmh` already lived in `flight_profile.lua`, not `tuning.py`, so this
follows the existing split rather than starting a second one). `flight_control.lua`'s section-D
speed-give block (`law_update`, ~L1627) now computes
`v_floor_mps = max(state.speed_goal_mps - speed_give_max_delta_kmh/3.6, speed_give_floor_kmh/3.6)`
instead of the old bare `speed_give_floor_kmh/3.6` — the relative delta, floored by the absolute
100 km/h. `state.speed_goal_mps` (already read elsewhere in `law_update`, e.g. the speed-band
check) is what "commanded speed" means here, not `desired.ias_kmh` directly — consistent with the
rest of this block's own comment ("`speed_goal_mps`/`desired.ias_kmh` are never touched").

**Verified under `luajit` before asserting** (per the task's own instruction), using the existing
toy-plant driver in `TestM3OrdinaryClimbTradesSpeedNoTerrain`: with `speed_goal_mps` = 220 km/h and
measured speed dropped to 70 km/h during a forced shortfall, `v_ref` now settles at
`max(220-50, 100) = 170` km/h (47.222 m/s), not the old absolute 100 km/h floor — confirmed by
running the updated test and reading the printed Lua values before writing the assertion, not the
reverse.

**Tests updated/added** (`test_flight_control_law.py`,
`TestM3OrdinaryClimbTradesSpeedNoTerrain` — `_run_scenario` parameterised on `speed_kmh`/
`dropped_speed_kmh` rather than hard-coded 220/70, so the three worked cases share one driver):

- `test_ordinary_climb_with_no_terrain_data_trades_speed_toward_the_floor` — 220 → 170 (was
  220 → 100), plus a second assertion that the relative floor still sits above the absolute one.
- `test_absolute_floor_binds_below_the_relative_delta` (new) — 130 km/h commanded: the relative
  delta alone would give 80, but `max(130-50, 100) == 100` wins.
- `test_commanded_speed_at_or_below_the_absolute_floor_gives_none` (new) — 100 km/h commanded:
  `max(100-50, 100) == 100 ==` commanded speed, so `v_ref` cannot fall at all under the same forced
  shortfall that produces a real give at 220/130.

Both toy-plant PROFILE tables (`test_flight_control_law.py`'s `_PROFILE`,
`test_flight_control_lua.py`'s inline profile table) gained `speed_give_max_delta_kmh = 50.0`
beside the existing `speed_give_floor_kmh` entry — mirrors `flight_profile.lua`'s shipped default,
per this file's own earlier "mirror the shipped profile" convention for every other BL-16 M3
constant.

**Card and docs updated to the new wording** ("speed falls by at most ~50 km/h, not below 100"),
rows 4 and 11: `docs/acceptance/2026-11-28-bl16-m3-card.md` and its sibling `.html`.
`aircraft-layer/CLAUDE.md`'s M3 bullet (the only `CLAUDE.md` of the two that stated the speed-give
floor at all — `body-layer/CLAUDE.md` has no `speed_give_*` mention, grepped, confirmed) now states
the two-bound formula and cites the user's own words. No `tuning.py`/`defaults.toml` change: neither
constant lives there.

### R1-b — performance (`performance-m3.md` findings 1/2)

**Finding 1** (terrain projection allocating every DCS frame, read only at `law_hz`): gated the
`run_active_frame` projection block (builds `measured.terrain`) behind the SAME `law_due(t,
fc_law_last_update_t, flight_profile.ACTIVE)` test the law-update call below it already uses —
"project only when `law_due()` is true," the finding's second named mitigation, chosen over
reusing preallocated parallel arrays (the first) because it needed no change to `law_terrain_w_
floor`'s own `ipairs(terrain)` iteration or to the `{d, T}` pair shape every other consumer
(including the toy-plant tests, which feed `measured.terrain` directly) already assumes. Confirmed
no live test exercises this path through `run_active_frame` end-to-end (grepped
`test_flight_control_lua.py` for `run_active_frame`/`fc_terrain_n`/`measured.terrain`: the only
hits are `fc_terrain_n`, which reads `fc_terrain.points` directly and is untouched by this gate,
and a `run_active_frame` mention inside an unrelated comment) — every terrain-law test drives
`law_update` directly with `measured.terrain` set by the driver, so this gate is untested by the
existing suite and no new test was added for it (behaviour-preserving by construction: the result
is read only on the same frame it is computed, both before and after).

One edge case disclosed, not fixed: the law's own collision-defer path (`law_is_due and
estimator_due_this_frame and not fc_law_deferred_last_frame` → defer one frame) can still compute
a terrain projection that `law_update` does not consume that exact frame, since the gate checks
only `law_due`, not the full three-way defer condition. Strictly less work than before (unconditional
every frame) in every case, including this one, so not a regression; flagged for whoever next
touches this collision logic, if it is worth closing further.

**Finding 2** (duplicate `GET /line_of_sight/latest` fetch): added `ConsolePerceptionRunner.
_los_cache` (`tuple[float, dict[str, object] | None] | None`, keyed by the poll's own sim-time
stamp) and a new helper `_get_line_of_sight_cached(runner, aircraft_client, poll_stamp)` that both
`_resolve_expected_area_checks` (keyed by `ownship.t_sim`) and `_compose_and_relay_terrain` (keyed
by a new `now_sim` parameter, threaded through from `_apply_flight_requests`'s own `now_sim` =
`runner.last_t_sim`) now call instead of fetching independently. Both call sites pass the SAME
value for a given poll — `_resolve_expected_area_checks` runs inside `run_once`, which sets
`runner.last_t_sim = ownship.t_sim` immediately after; `_apply_flight_requests` is called later in
the same poll cycle with `runner.last_t_sim` (by then already that poll's value) as `now_sim` — so
the cache is a hit on the second call whenever both run in the same poll, and a plain miss
(re-fetch) otherwise, never a stale read. A failed fetch (`AircraftLayerError`) is cached as `None`
too, matching both call sites' pre-existing "degrade to no answer" behaviour exactly, and avoiding
a second failing request the same poll.

No test added for the cache-sharing itself (the finding was LATER/non-blocking, and the behaviour
each call site observes is unchanged — same JSON dict either way); the existing expected-area and
terrain-relay tests (`test_body.py`, `test_body_flight_control.py`) continue to exercise both
consumers' own logic against whatever `los`/`None` the fake client's `get_line_of_sight_latest`
returns, unaffected by whether the fetch happened once or twice internally.

**Caught by the existing mission-reset survivor test, not a new test of my own**:
`test_mission_start_reset.py::test_console_perception_runner_reset_preserves_declared_fields_and_resets_rest`
poisons every declared field, calls `reset_for_new_mission()`, and asserts every non-preserved
field is back at its constructor default — `_los_cache` (a plain `default=None`, `init=False`
field) is exactly the trap that module's own `_terrain_seq`/`_last_probe_seq` comments already
document (a `self.__init__()` re-invocation does not reassign a plain-default `init=False` field
per instance). Fixed with one explicit `self._los_cache = None` line in `reset_for_new_mission`,
right beside the `_terrain_seq` line documenting the same trap — otherwise a cached LOS snapshot
from the mission that just ended could be read as the new mission's own answer if the new
mission's sim-time stamp happened to coincide with the cached one's (restarts can produce
coincident `t_sim` values, per this project's own mission-start documentation). Full suite run
before and after this fix: 1 failure (this one) → 0.

### R1-c — security hardening (`security-m3.md` findings 1/2)

**Finding 1** (`x`/`z` had no magnitude bound, only `h` did): added the bound at both layers, using
`_TERRAIN_POINTS_COORD_ABS_MAX` (2,000,000, the same value the channel's other direction already
uses) rather than `h`'s own tighter `1e5` — the security review's own recommended value.

- `flight_control.lua`'s `parse_terrain_relay`: new local `TERRAIN_RELAY_COORD_ABS_MAX = 2000000`,
  checked alongside the existing `x == x`/`z == z` finiteness tests.
- `aircraft-layer/src/api/server.py`: new `_terrain_relay_passes_bounds(raw)` — parses the
  already-regex-matched string a second time (split on `|`, `;`, `,`) and rejects on any
  non-finite or out-of-bound `x`/`z`/`h`, called right after the existing shape regex/length check
  in the `flight_lease` handler. A failing bound drops `terrain` only (sets it to `None`), same
  "never the whole lease" posture the field already had for a malformed string.

**Finding 2** (point count unbounded in the relay, despite a comment claiming the `MAX_TERRAIN_
POINTS` bound): closed at both layers, truncating rather than rejecting outright, matching the
Hook's own `_applyTerrainPoints` precedent for the same cap.

- `flight_control.lua`'s `parse_terrain_relay`: new local `TERRAIN_RELAY_MAX_POINTS = 32`; the
  point-collection loop now `break`s once the cap is reached (the `seq`/received-time stamp from
  the entry still being scanned when the cap hit is still applied — only the point list is capped,
  never the whole parse rejected).
- `server.py`'s `_terrain_relay_passes_bounds`: counts `;`-separated entries before parsing any of
  them and rejects (rather than truncates) an over-count string outright — simpler than mirroring
  Lua's truncate-in-place, and consistent with this field's existing "reject the whole `terrain`
  field, never the lease" posture for every other malformed-input case at this layer (the
  truncate-not-reject choice was made in Lua specifically to match the Hook's own established
  pattern for the SAME cap on the request side; the collector layer had no such precedent to
  match, so it took the simpler of the two valid choices).

The misleading pre-existing comment on `_TERRAIN_RELAY_PATTERN` (claimed bounds the regex alone
never checked — the finding's own "doesn't match what the code checks" observation) was corrected
to describe what the regex actually bounds (shape only) versus what `_terrain_relay_passes_bounds`
now adds (count + magnitude), rather than left to mislead the next reader the same way.

**Tests added:**

- `test_flight_control_lua.py`, `TestTerrainRelayMagnitudeBound` (two new methods) —
  `test_out_of_range_xz_are_dropped_in_range_ones_kept` (a huge-but-finite `x` and a huge-but-finite
  `z`, each dropped, the in-range point kept) and
  `test_more_than_the_cap_points_are_truncated_not_carried_unbounded` (40 points sent, 32 survive).
- `test_flight_control_api.py`, `TestFlightLeaseCommandEndpoint` (three new methods) —
  `test_an_overlong_xz_decimal_literal_drops_terrain_only` (a 400-digit `x`, which the shape regex
  alone accepts), `test_more_than_the_cap_points_drops_terrain_only` (33 entries, over the cap), and
  `test_exactly_the_cap_points_still_forwards` (32 entries, the boundary case, still accepted —
  confirms the fix does not quietly tighten the real, documented limit).

### Non-obvious choices

- **`speed_give_max_delta_kmh` placed in `flight_profile.lua`, not `tuning.py`.** The plan's own
  Tuning-constants convention ("the numbers the user set and may configure... live in `tuning.py`";
  "loop values live in the profile") would suggest `tuning.py` for a number the user gave verbatim
  ("speed delta should typically not exceed 50 km/h"). But `speed_give_floor_kmh` — the sibling
  constant it is directly compared against in the same line of code, also user-originated (U19) —
  already lives in `flight_profile.lua`, and splitting the pair across two mechanisms for no
  functional reason would make the pair harder to read together, not easier to tune. Followed the
  existing placement rather than the general rule's letter; noted here per the root `CLAUDE.md`
  tuning-constants procedure's own instruction to say so when departing.
- **R1-b finding 1's chosen mitigation (gate on `law_due`) over the preallocated-array
  alternative.** The array alternative would have required `law_terrain_w_floor`'s `ipairs`
  iteration to become a bounded `for i = 1, n do` over a separate count field (the finding's own
  text), a second change to a function with its own existing tests, for a MONITOR-level finding
  that was explicitly "not blocking." The gate gets the same frame-rate reduction with a two-line
  change to the call site alone.
- **Server-side point-count enforcement rejects rather than truncates**, while Lua truncates — see
  R1-c above; both are legitimate, chose per-layer precedent rather than forcing one shape onto
  both.

## Checks (R1)

Run from this worktree (`aircraft-layer/.venv` and `body-layer/.venv` from the main checkout, per
this project's "agent worktrees have no local `.venv`" note; `luajit`/`luac5.1` from Homebrew).

**aircraft-layer:**

- `ruff format --check src tests`: pass (one file needed `ruff format` itself —
  `src/api/server.py`, a blank-line normalisation around the new helper — then re-checked clean).
- `ruff check src tests`: pass (after prefixing three newly-unused unpacked tuple elements with
  `_` in the two new R1-a test methods — `RUF059`).
- `mypy src` (from inside `aircraft-layer/`): pass, 0 issues in 29 source files.
- `pytest tests -q`: **1325 passed** (1318 before this pass + 7 new: 2 R1-a, 2 R1-c Lua, 3 R1-c
  Python).
- `luac5.1 -p` on every touched `.lua` file: pass.

**body-layer:**

- `ruff format --check src tests`: pass.
- `ruff check src tests`: pass.
- `mypy src` (from inside `body-layer/`): pass, 0 issues in 96 source files.
- `pytest tests -q`: first run caught a real regression — `test_mission_start_reset.py::
  test_console_perception_runner_reset_preserves_declared_fields_and_resets_rest` failed: the new
  `_los_cache` field (a plain `default=None`, `init=False` field) was not reset by
  `reset_for_new_mission()`, the same `self.__init__()`-does-not-reassign-a-plain-default-
  `init=False`-field trap that field's own siblings (`_terrain_seq`, `_last_probe_seq`) already
  document in that method. Fixed with one explicit `self._los_cache = None` line beside
  `_terrain_seq`'s own (see "Non-obvious choices" above). Second run: **3927 passed, 4 xfailed**
  (the 4 xfails are pre-existing and unrelated to this change).

No `tuning.py`/`defaults.toml` change in this pass (R1-a's constants are profile loop values, not
tuning constants; R1-b/R1-c touch no behaviour-affecting constant at all).
