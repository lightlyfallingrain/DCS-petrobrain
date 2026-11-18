### Performance Review

Batch: BL-16 mode 2 Stages P3+P4 (CBTM align/align-for-launch/break/break-away, launch-detection
recovery). Diff reviewed: `3107a662..6e0421e3` (branch `feature/bl16-p3p4-cbtm`), scoped to
`aircraft-layer/` and `body-layer/` per task (plans excluded). Touched files: `aircraft-layer/
dcs-export/Petrobrain/ai_pilot_wheel.lua`, `aircraft-layer/src/api/server.py`, `aircraft-layer/
src/collector/command_sender.py`, `aircraft-layer/src/schema/ai_pilot_wheel.py`,
`body-layer/src/belief/ai_pilot_wheel.py`, `body-layer/src/belief/crew_console.py`,
`body-layer/src/body.py`, `body-layer/src/rules/actions.py`, plus tests/config. Inputs: `plans/
flight-control/plan.md` Amendment 2026-11-18 + "Revised 2026-11-18 -- Stages P3+P4" section,
`plans/flight-control/implementation.md` newest sections, and this feature's own prior perf
reports (`perf-m1-m2.md`, `perf-batch-a.md`, `perf-takeover.md`, `perf-p2.md`) for the posture
this batch is judged against.

### Findings

#### `ai_pilot_cbtm_tick` runs at 5 Hz, not per frame -- confirmed, not a hot-path risk

- **Location:** `ai_pilot_wheel.lua:1158` (`ai_pilot_cbtm_tick`), called only from `update_ai_
  pilot_wheel_overlay` (`ai_pilot_wheel.lua:1540`), which `Export.lua`'s `LuaExportAfterNextFrame`
  calls only after `core.tick_due(t)` gates it to the existing 5 Hz export cadence
  (`Export.lua:419-442`). The per-frame function is `run_ai_pilot_wheel` (`Export.lua:417`,
  unconditional, ~140 fps) -- P3+P4's addition to it is one more `if ai_wheel_cbtm_pending_
  release_t ~= nil and t >= ...` deadline check (`ai_pilot_wheel.lua:1272-1283`), same O(1) shape
  and same established-closure-allocation pattern every other pending-release check in this file
  already has (`project_export_lua_per_frame_closures_are_established_pattern.md`).
- **Risk:** none. The task brief flagged `ai_pilot_cbtm_tick` alongside `run_ai_pilot_wheel` as a
  DCS-frame-budget concern, but the actual call graph puts the CBTM decision logic (mode-cycle
  retry, the five-action dispatch, the break-away gap) on the 5 Hz tick, matching the
  `helperai`-overlay-dependent steps this module already moved off the per-frame path for exactly
  this reason (`ai_pilot_wheel.lua:1432-1451`'s own docstring, "perf fix, `perf-batch-a.md`").
  Nothing in this diff moves it back.
- **Action:** none.

#### Body-layer per-poll additions (launch detection, recovery, CBTM send) -- same bounded cost
class the plan's own sibling plumbing was already cleared at

- **Location:** `body-layer/src/belief/ai_pilot_wheel.py` (`_parse_payload_station_counts`,
  `payload_count_dropped`, `capture_flight_snapshot`, `cbtm_apply_align`/`cbtm_apply_align_for_
  launch`, `seed_recovery_goal`, `decide_ai_pilot_wheel`'s three new steps) and `body.py`'s
  `_apply_ai_pilot_wheel_goal`, called once per poll (`_DEFAULT_POLL_INTERVAL_S = 1.0`,
  `body.py:2929`).
- **Risk:** none at realistic scale. Every new function is a `dataclasses.replace`, a handful of
  comparisons, or a loop over at most ~4 payload stations / ~4 goal params (`goal.pending_order`
  is bounded by the fixed `heading`/`altitude`/`speed` vocabulary) -- the same cost class `perf-
  m1-m2.md` already cleared for this plumbing's siblings (`Action: none`). No collection scales
  with contact count, world size, or sortie length; `_apply_ai_pilot_wheel_goal`'s CBTM send is a
  one-shot trigger, not a per-poll send.
- **Action:** none.

#### A second aircraft-layer GET riding every poll's ai-pilot-wheel refresh, unconditionally

- **Location:** `advance_parked_flight_state` (`body-layer/src/belief/ai_pilot_wheel.py:421-480`)
  now calls both `client.get_ai_pilot_wheel_latest()` and `client.get_payload_latest()` every
  single poll this function runs, regardless of `fc_mode`/`align_phase`/whether mode 2 or CBTM is
  in use at all this sortie -- the same unconditional-every-poll placement the ai-pilot-wheel read
  itself already has (needed to catch the park/unpark edge), now carrying a second, independent
  HTTP round trip for launch detection that only matters while `align_phase == "launch_aligned"`.
- **Risk:** low, and not worth gating now. This is one extra LAN HTTP GET at 1 Hz to an endpoint
  that already exists and is already read elsewhere in this codebase (`[[BL-B67]]`'s ATGM run) --
  far below any budget this project has, and squarely the "none" cost class `perf-m1-m2.md`
  already cleared for this exact shape of per-poll body-layer work. It is a credible *pattern* to
  watch, not a credible *cost*: each new mode-2 sub-feature so far has piggybacked one more
  unconditional read onto this same poll tick (`guidance_unit_state` readback, ai-pilot-wheel
  readback, now payload), and at 1 Hz that is cheap to keep doing indefinitely but is also the
  kind of accretion `project_export_lua_per_frame_push_functions.md` named on the Lua side at a
  faster cadence -- the same "read count keeps growing at this shape" trigger, translated to the
  per-poll tier.
- **Action:** MONITOR. No mitigation needed now (gating the payload read behind `align_phase in
  ("launch_aligned", "recovering")` would save one HTTP call per poll outside those two phases, at
  the cost of a state check this function does not otherwise need) -- revisit only if the per-poll
  read count on this path keeps growing at this shape, or a reported symptom (poll-loop lag,
  aircraft-layer saturation) ever shows up; neither has happened at 1 Hz with two small GETs today.

#### Wire/API surface additions (`cbtm_action`/`cbtm_seq`) -- request-triggered, not hot-path

- **Location:** `aircraft-layer/src/api/server.py`'s `cbtm_action`/`cbtm_seq` validation
  (`POST /command/ai_pilot_goal`), `command_sender.send_ai_pilot_goal`'s two new parameters, and
  `push_ai_pilot_wheel_state`'s two new wire fields (`apw_cbtm_status`/`apw_cbtm_seq`,
  `ai_pilot_wheel.lua:1681-1682`).
- **Risk:** none. The API/collector additions run once per voice command, not per poll or per
  frame. `push_ai_pilot_wheel_state` already builds one string via concatenation every 5 Hz tick
  for every other status field -- two more `text_or_null`/`fmt_num_or_null` calls is the same
  established per-field cost already paid for `apw_goal_progress`/`apw_goal_seq`, not a new
  allocation shape.
- **Action:** none.

### Verdict
APPROVED
