### Performance Review

First code-level pass on the batch built so far on `feature/bl16-lift-vector-law` (BL-16 mode 1
lift-vector law LV-0..LV-2, plus mode-2 fixes BL-B139/BL-B140). Tip reviewed: `bbddd80b` (checked
out on branch `bl16-perf` in this worktree, the assigned worktree's own HEAD having been on
unrelated `worktree-agent-ac0171644a5ca50c7` BL-B67 work — not an ancestor of `bbddd80b`, so a fresh
checkout was taken instead of a fast-forward). No hard real-time budget applies yet (Petrobrain
Runtime has not started); the bars are the standing ones: no needless per-frame allocation, no
redundant query, work gated to the frequency it actually needs. Only a plan-time review
(`perf-plan-review.md`, CONCERNS) existed before this pass — this is the first review against the
actual code.

`Export.lua`'s `LuaExportBeforeNextFrame` runs `flight_control.lua`'s `run_flight_control` and
`flight_desired.lua`'s `tick` unconditionally every DCS frame (~140 Hz), so everything in
`flight_control.lua`/`flight_desired.lua` is judged at that rate. `flight_profile.lua` is static
per-aircraft config with no per-frame function at all — not a hotspot. `ai_pilot_wheel.lua`'s
mode-2 goal logic (including the new wake-kick, BL-B139) runs at the existing 5 Hz goal tick, not
per frame. The body-layer side (`belief/ai_pilot_wheel.py`, `body.py`'s `_apply_ai_pilot_wheel_goal`
/`_apply_flight_requests`) runs at body-layer's own ~5 Hz poll cadence, two orders of magnitude
below the Lua frame rate, and every addition there is a handful of scalar fields/one extra
fire-and-forget HTTP call — no loop over a dataset, no redundant per-poll query beyond what
pre-existed.

### Findings

#### Both `perf-plan-review.md` NOW items were fixed exactly as requested

- **Location:** `flight_control.lua`, `read_estimator_raw` (L2266-2356) and the estimator ring
  buffers (`est_ring_new`/`est_ring_push`/`est_ring_slope`/`est_ring_mean`, L1967-2117).
- **Risk:** none remaining — checked against what the plan review asked for, not re-derived from
  scratch. (1) The unselected velocity source (`"position"` when `"vector"` is active, or vice
  versa) is now read and fed into its ring **only** `if FLIGHT_TRACE_ENABLED` (L2318, L2426-2486)
  — the common case (flag off, `velocity_source == "vector"`) does one velocity computation per
  frame, not two, as requested. (2) The least-squares rings are fixed-size preallocated arrays
  (`EST_RING_CAPACITY`, allocated once in `est_ring_new`, never a per-frame `table.insert`) with
  incremental running sums (`sum_t`/`sum_t2`/`sum_v`/`sum_tv`) updated O(1) amortized per push —
  confirmed by reading `est_ring_push`'s own add-newest/evict-oldest loop, and by
  `test_flight_control_estimator.py`'s dedicated 3-simulated-hour-at-30 Hz test exercising the
  periodic rebase (`EST_RING_REBASE_INTERVAL_S`) that keeps the cancellation error bounded over a
  long session rather than only "small at today's sortie lengths."
- **Action:** none — noted so this review records the fix was verified, not assumed.

#### Estimator runs every frame in every mode, as the plan always intended — gating confirmed correct

- **Location:** `run_flight_control` (L3156-3185): `est_due(fc_est, t, flight_profile_active)` is
  checked **before** `read_estimator_raw` is called (L3176-3177) — an off-due frame (most of them,
  ~140 Hz against `law_hz`'s 30) costs only `est_due`'s own two comparisons, no `LoGet*` call built
  or thrown away.
- **Risk:** this is the plan's own accepted MONITOR item (a permanent per-frame-pair floor added
  to every sortie, including ones where mode 1 never engages) — not newly introduced, and the gate
  that keeps the floor to "cheap check most frames, real read only at 30 Hz" is in place and
  correct. `law_update` itself is further deferred one frame whenever the estimator step also ran
  (`estimator_due_this_frame`, L3368-3369 → `run_active_frame`'s own L3074-3082 reasoning), and
  `test_flight_control_lua.py`'s scheduling test confirms zero collisions between the two over a
  simulated second at the real frame rate.
- **Action:** MONITOR, unchanged from the plan review — carried forward, not re-opened.

#### Flag-gated per-frame trace writes with `flush()` at up to ~30 Hz while the debug flag is on

- **Location:** `flight_trace_log` (L2242-2255), called from `run_flight_control` only
  `if ran and FLIGHT_TRACE_ENABLED` (L3180), i.e. at most once per estimator step (~30 Hz, not
  ~140 Hz) and only while `aircraft_layer_flight_debug.flag` is present. Every trace-only read
  (`LoGetAccelerationUnits`, AoA/AoSS, wind, the unselected velocity source, the six raw rotor/
  engine args) is itself gated behind the same `FLIGHT_TRACE_ENABLED` check, confirmed inside
  `read_estimator_raw` (L2318-2354) — the gate is checked before the reads are built, not just
  before the file write, exactly as the plan review's MONITOR item asked to confirm.
- **Risk:** low and explicitly accepted by root `CLAUDE.md`'s testing-aid framing (a debug trace
  file is allowed to be less than perfectly efficient), but `flight_trace_file:flush()` runs on
  every call while the flag is on, i.e. up to ~30 Hz of fsync-class I/O for the life of a debug
  sortie — this is the one place in the batch doing synchronous I/O inside the Export frame
  callback, on DCS's own thread, at a non-trivial rate. The flag is off by default and this is a
  deliberate debugging aid flown only on calibration sorties, so it is not a production cost.
- **Action:** MONITOR (unchanged from the plan review's own posture on this point) — worth
  revisiting only if a calibration sortie with the flag on ever shows visible frame-time cost; not
  worth buffering/batching the writes pre-emptively for a debug-only path.

#### Pre-existing per-frame `GetDevice(0)` read growth (update_live_seat_tracking, push_* functions) — unchanged by this batch

- **Location:** `update_live_seat_tracking` (6 uncached `GetDevice(0)` reads, unconditional every
  frame regardless of `fc_mode`) and `Export.lua`'s `push_ptt_state`/`push_spu8_state`/
  `push_cockpit_switch_state` family. Already tracked in agent memory
  (`project_export_lua_per_frame_push_functions`, `project_bl16_m1_m2_redundant_envelope_measured_
  reads`, `project_bl16_mode1_rotor_rpm_seam_dormant_arg_proxy`) from prior batches on this same
  file.
- **Risk:** this batch does not add a new per-frame `GetDevice(0)`/`LoGet*` reader beyond the
  estimator's own bounded set (already covered above), and does not touch `update_live_seat_
  tracking` or the `push_*` family. The "fourth such function" re-open threshold from
  `project_export_lua_per_frame_push_functions` is not crossed by this batch.
  `ROTOR_RPM_SOURCE`/`ENGINE_RPM_SOURCE` remain `"dummy"` as of this diff (the `arg_proxy` branch
  stays dormant, per the existing memory's own note to re-check only when it flips).
- **Action:** none from this batch — the existing MONITOR carries forward unchanged, re-stated here
  only so this review shows it was checked against the current diff rather than assumed stable.

#### Body-layer mode-2 additions (BL-B139 wake-kick, BL-B140 speed-step fix) — bounded, poll-rate, no new concern

- **Location:** `body.py`'s `_apply_ai_pilot_wheel_goal` (new `wake` bool, read once per poll and
  threaded through three existing send calls, L3836-3935 of the diff) and `_apply_flight_requests`
  (replaces `_apply_flight_control` with the same per-poll, one-send-per-transition shape, no new
  loop). `belief/ai_pilot_wheel.py`'s `nearest_speed_step` fix (BL-B140) is a one-character
  comparison-operator change (`>=` → `>`), and `ai_pilot_wheel.lua`'s wake-kick functions
  (`ai_pilot_wake_kick_direction_hold`/`_tap`, L1047-1130) are a handful of scalar field
  comparisons called from `ai_pilot_goal_tick`/`ai_pilot_goal_tick_altitude`/`_speed`, themselves
  gated to the existing 5 Hz goal tick (`ai_pilot_goal_tick`'s own doc comment, confirmed by its
  call site in `run_ai_pilot_wheel`) — not the ~140 Hz Export frame.
- **Risk:** none credible. Single-aircraft, fixed small field counts, no iteration over a
  dataset, no redundant query beyond the one `wake` read this batch adds (explicitly computed once
  per poll and reused by every send that needs it, per its own comment at L3836-3842 — the
  opposite of the "gated HTTP call before the gate" shape this role has flagged elsewhere).
- **Action:** none.

### Verdict
APPROVED — MONITOR

Both NOW items from the plan-time review were implemented exactly as requested (unselected
velocity source trace-gated; ring buffers fixed-size with incremental least-squares sums, verified
by a dedicated long-session test). The remaining MONITOR items (estimator-every-mode floor,
flag-gated trace `flush()` rate, the pre-existing `GetDevice(0)` read growth) are all accepted,
unchanged, and none crosses into NOW at this batch's scale — single aircraft, bounded field counts,
no datasets, no scaling risk. Nothing here blocks Reviewer/Security/DoD for this batch.
