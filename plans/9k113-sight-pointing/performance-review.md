### Performance Review

Scope: BL-B80 Stages 1–3 (one batch), diff `edc8dd73..157b78b1`. Hot paths examined: Export.lua's
new `run_sight_pointing` (per-frame, gated only on OBSERV, runs ahead of the 5 Hz export throttle —
confirmed at `LuaExportAfterNextFrame` call site, line ~1400) and body-layer's `write_sight_target`
path in the ~1–5 Hz poll loop (`logger.py`, `sight_effector.py`, `aircraft_client.py`,
`optic_policy.advance_sight_aim`).

No hard real-time budget applies in this phase (root `CLAUDE.md`). Findings below are about
whether the new per-frame work follows this codebase's own established cost pattern for
`LuaExportAfterNextFrame`, since that function already runs several other per-frame helpers.

### Findings

#### `run_sight_pointing`'s per-frame closures (Export.lua)
- **Location:** `Export.lua:run_sight_pointing` (new), called every frame from
  `LuaExportAfterNextFrame` regardless of the 5 Hz export throttle.
- **Risk:** Lua's `safe_call(function() ... end)` allocates a new closure every call. Steady state
  (OBSERV on, no detector fire) this function makes 4 such calls per frame: the OBSERV read, the
  device lookup inside `sight_point_quiet`, and the az/elev readback reads for the detector. At a
  plausible ~60–150 fps that is ~240–600 short-lived closures/sec added on top of what this file
  already allocates per frame.
- **Action:** MONITOR. This is not a new pattern this stage introduces — `push_ptt_state`,
  `push_spu8_state`, `push_cockpit_switch_state`, and `push_slew_trace` already run every frame in
  the same function, each with their own `safe_call(function() ... end)` closures (30
  `safe_call(function` sites total in the file after this change). `run_sight_pointing` is
  consistent with, not materially worse than, the existing per-frame cost this file already
  tolerates, and no per-frame table/array allocation was found (the rate limiter and detector use
  only locals and module-level state, no new tables per frame). No fix requested now; if a future
  frame-time complaint arises, these per-frame `safe_call` closures across the whole file are the
  first thing to look at collectively, not this stage's addition in isolation.

#### Redundant `GetDevice(0)` lookups within one frame
- **Location:** `run_sight_pointing` calls `GetDevice(0):get_argument_value(...)` twice (OBSERV,
  then az/elev reads) in addition to the device-0 lookups `push_cockpit_switch_state` and
  `push_slew_trace` already make earlier in the same `LuaExportAfterNextFrame` frame.
- **Risk:** Purely redundant work — the same device handle could be fetched once per frame and
  passed to each function instead of re-resolved by each. `GetDevice` is understood to be a cheap
  engine-side handle lookup (not an allocation), and this redundancy pre-exists this stage (every
  per-frame function in this file already does its own `GetDevice(0)` call), so this stage adds to
  an existing pattern rather than creating a new one.
- **Action:** LATER. Not credible as a budget risk at current scale (DCS frame budget concerns are
  out of scope this phase per `CLAUDE.md`), and fixing it piecemeal for one function while the rest
  of the file keeps the same pattern would just split the redundancy rather than remove it. Worth
  doing as one pass across all of `LuaExportAfterNextFrame`'s per-frame helpers together if/when
  Petrobrain Runtime's real-time budget phase begins — not this plan's job to pre-empt.

#### `write_sight_target` blocking HTTP write in the poll loop
- **Location:** `logger.py`'s `_run_crew_text_poll_loop`, new block calling
  `belief.sight_effector.write_sight_target` → `AircraftLayerClient.write_sight_target` →
  `_post_json` every poll while `home_phase is SIGHTING` (idle included, per the plan).
- **Risk:** A synchronous HTTP POST inside the poll loop thread could stall the poll cadence if the
  aircraft-layer collector is slow or unreachable.
- **Action:** MONITOR, not NOW. This is the same synchronous `_post_json` pattern already used by
  `write_cockpit_switch`, `post_look_direction`, and `push_text_line` in the same poll loop — not a
  new blocking surface this plan introduces. It is wrapped in `try`/`except AircraftLayerError`
  that logs and continues (does not crash or wedge the loop), matching the existing posture for
  every other write in this loop. Frequency is ~1–5 Hz (poll rate), not per-frame, and body-layer's
  current phase has no hard real-time budget. No credible scenario in this review found where this
  differs in risk from the already-accepted `write_cockpit_switch` pattern.

#### Body-layer per-poll conversions and dataclass `replace()`
- **Location:** `sight_effector.sight_elevation_raw_to_deg`/`_deg_to_raw`,
  `in_gyro_alignment`, `refresh_readback`, `optic_policy.advance_sight_aim`.
- **Risk:** None credible — pure arithmetic and one `replace()` call per poll on an already-frozen
  dataclass, same cost as every other `GuidanceUnitState`/`OpticState` update already in this
  codebase at the same ~1–5 Hz rate.
- **Action:** MONITOR (no action — included for completeness, not because it is a risk).

### Verdict
APPROVED — MONITOR
