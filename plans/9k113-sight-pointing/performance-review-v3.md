# Performance Review — BL-B80 v3 Stage 6 (9K113 sight edge-park)

Branch `feature/9k113-sight-edge-park`, tip `e1d9f985b7361630b584c0acca57f1167e6e50e1`
(fast-forwarded from `194e2200`, matches). Diff reviewed:
`9dfc3d2f32b4f012672c95fbda7d02ddcb3a19de..80714a98454c5b17d34e19f7b5ba7a7bd380604f`.

Budget context: no hard real-time budget applies yet (that starts with Petrobrain Runtime). The
relevant constraints here are the standing ones — no per-request allocation on hot paths, prefer
batching/precomputation, offload heavy work async. `Export.lua`'s `LuaExportAfterNextFrame` is a
true per-DCS-frame hot path (unthrottled, ahead of the file's own 5 Hz export gate), so it is
judged against that baseline rather than against a runtime SLO that does not exist yet.

### Findings

#### `run_sight_servo`'s new field-target/clip logic (every frame, when a goal is live)

- **Location:** `aircraft-layer/dcs-export/Export.lua`, `run_sight_servo` — new calls to
  `sight_clip_to_field_body_deg` (once/frame) and `sight_mark_is_clipped` (twice/frame, az+el),
  plus the feed-forward finite-difference branch.
- **Risk:** none credible. Both new functions are pure scalar arithmetic (`math.abs`/`math.min`,
  a subtraction and a compare) on top-level named functions, not per-frame closures — no table,
  array, or closure allocation added. The `m566`/`m555` `GetDevice(0)` reads these consume were
  already being made every frame by the pre-v3 `mark_valid` check this replaces; v3 reuses them
  rather than adding new device reads. This matches the existing project baseline recorded in
  memory (`project_export_lua_per_frame_closures_are_established_pattern.md`): no new per-frame
  table/array allocation, and `run_sight_servo` was already the single largest per-frame closure
  contributor in this file before this stage.
- **Action:** MONITOR (carried from existing baseline, not newly introduced by this stage).
- **Mitigation:** n/a — no measurable regression to fix. If Petrobrain Runtime's real-time budget
  phase begins, profile `run_sight_servo` first (per existing memory), not stage-by-stage.

#### `push_slew_trace`'s two new `GetDevice(0)` reads + `sight_mark_is_clipped` calls

- **Location:** `aircraft-layer/dcs-export/Export.lua`, `push_slew_trace` (moved below
  `sight_mark_is_clipped`/the new constants, same function, gained `m566`/`m555` reads and a
  `mark_clipped` computation).
- **Risk:** low. This function is a no-op unless `SLEW_DEBUG` is set — it is a calibration-flight
  debug probe, not code that runs in normal play. Even with the flag on, the added cost is two more
  `GetDevice(0):get_argument_value` calls (bringing this function's own device reads to four) and
  two cheap arithmetic calls — same shape as the existing `push_*_state` per-frame pattern already
  accepted in this file (`project_export_lua_per_frame_push_functions.md`), and gated off in the
  configuration that matters (normal sorties, where the file ships `SLEW_DEBUG` off).
- **Action:** MONITOR.
- **Mitigation:** n/a. If `SLEW_DEBUG` is ever made default-on or a fifth per-frame debug probe is
  added at this shape, re-open `project_export_lua_per_frame_push_functions.md`'s threshold
  ("fourth such function… re-open rather than re-derive") — not a concern at today's scope (debug
  tooling only).

#### `push_slew_trace`'s relocation (file-ordering fix, not a cost change)

- **Location:** same function, moved from just after `safe_call` to just after
  `sight_mark_is_clipped`/the new constants.
- **Risk:** none — this is a correctness fix (avoiding a `local`-referenced-before-declaration
  `GETGLOBAL` bug, per the file's own established hazard), not a performance-relevant change. Noted
  only because the diff is large; no call-frequency or allocation change results from the move
  itself.
- **Action:** N/A (not a performance finding).

#### New per-frame state variables (`sight_field_target_body_az/el_deg`, `sight_mark_clipped`, `sight_prev_field_target_body_az/el_deg`)

- **Location:** module-level `local`s in `Export.lua`, written every frame inside
  `run_sight_servo`.
- **Risk:** none. These are scalar top-level locals assigned by value every frame, exactly the
  same shape as the `sight_estimate_body_az/el_deg` locals they replace (removed 1:1 by the
  open-loop branch's deletion) — no net growth in persistent per-frame state, and no allocation
  (reassignment, not `table.insert`/new-table-per-frame).
- **Action:** APPROVED, no further note needed.

#### `push_sight_servo_state`'s two new fields (`field_target_azimuth_deg`/`field_target_elevation_deg`/`mark_clipped`)

- **Location:** `aircraft-layer/dcs-export/Export.lua`, `push_sight_servo_state`; schema change in
  `aircraft-layer/src/schema/sight_servo.py`.
- **Risk:** none at this stage's frequency. `push_sight_servo_state` runs at the file's own 5 Hz
  export throttle (confirmed: called after the `t - last_export_t < EXPORT_INTERVAL_S` gate, not
  from the unthrottled per-frame block above it), not every frame. Three extra fields in a status
  line sent 5 times/second is negligible regardless.
- **Action:** APPROVED.

### What was checked and ruled out

- **No new unconditional `GetDevice`/`get_argument_value` calls were added to the always-on,
  non-debug per-frame path.** The two reads `sight_mark_is_clipped` consumes inside
  `run_sight_servo` (`m566`/`m555`) are the same reads the pre-v3 `mark_valid` check already made;
  v3 reuses the existing values rather than re-fetching.
- **No new per-frame table, array, or closure allocation.** Grepped the diff for `{` literal
  construction and closure definitions inside `run_sight_servo`/`push_slew_trace` — both new pure
  functions (`sight_clip_to_field_body_deg`, `sight_mark_is_clipped`) are top-level named functions
  called with scalar arguments, returning scalars (multiple return values, not a table).
- **File I/O**: `push_slew_trace`'s buffered-write-then-periodic-flush pattern
  (`slew_log_buffer`/`SLEW_LOG_FLUSH_EVERY_N_LINES`) is unchanged by this stage — only the fields
  written into each buffered line changed, not the flush cadence or buffering mechanism. Flag-gated
  off by default, as before.
- **Branch count**: the `closed`/`homing` split and the shared stall detector are a few more
  conditionals than the old `closed`/`open` split, not a complexity class change — no loop or
  recursion was introduced.

### Verdict

APPROVED — MONITOR (inherited baseline, not a new condition from this stage)
