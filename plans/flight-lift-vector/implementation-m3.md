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
