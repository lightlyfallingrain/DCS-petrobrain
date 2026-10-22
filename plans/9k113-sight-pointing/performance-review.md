### Performance Review

Scope: BL-B80 v2, Stages 1–4/3b (one batch — the whole v2 rewrite that superseded v1's
position-command model, plus its three review-fix commits), diff `main...816250c8`. This replaces
the v1 review below, which assessed a different mechanism (`run_sight_pointing`,
`write_sight_target`/`advance_sight_aim`) that no longer exists on this branch.

Hot paths examined:

- `Export.lua`'s `run_sight_servo` (per-frame DCS-slave servo, runs every frame ahead of the 5 Hz
  export throttle — confirmed at the `LuaExportAfterNextFrame` call site, `Export.lua:1683`) and
  `push_sight_servo_state` (5 Hz, gated behind `last_export_t`, `Export.lua:1698`).
- Body-layer's per-poll chain: `logger.run_once` → `advance_sight_head` (`belief/sight_head.py`) →
  `select_sight_goal` → `attack_run.seen_world_direction`/`_seen_world_offset`, and the new
  `look_contact` resolution inside `run_once` (`logger.py:822-825`).
- `aircraft-layer`'s new `/command/sight_target` POST handler and `SightServoCache`/
  `GET /sight_servo/latest` (both ~1–5 Hz from the body-layer poll loop or external pollers, not
  per-frame).

No hard real-time budget applies in this phase (root `CLAUDE.md`). Findings are about whether this
stage's new work follows the codebase's own established cost pattern for `LuaExportAfterNextFrame`
and the poll loop, since both already carry several per-frame/per-poll helpers of the same shape.

### Findings

#### `run_sight_servo`'s per-frame closures and trig (Export.lua)
- **Location:** `Export.lua:1266` `run_sight_servo`, called every frame from
  `LuaExportAfterNextFrame` (line 1683) regardless of the 5 Hz export throttle.
- **Risk:** This is a heavier per-frame function than the v1 model it replaced. Steady state
  (`align_on`, a live goal, mark valid — the `"closed"` branch) it makes 4 `safe_call(function()
  ... end)` closures per frame (OBSERV read, align-lamp read, the two mark-argument reads at
  566/555), plus `LoGetSelfData`/`LoGetADIPitchBankYaw` each wrapped in `safe_call` inside the
  `have_goal` branch, plus one `math.sin`/`math.cos` pair every frame for the dither wobble
  (unconditional — computed even when `sight_mode == "hold"` overwrites most of the result) —
  roughly 6-8 short-lived closures/frame versus v1's 4, at the same ~157–160 fps the probes
  measured.
- **Action:** MONITOR, same reasoning as v1's equivalent finding. `push_ptt_state`,
  `push_spu8_state`, `push_cockpit_switch_state`, and `push_slew_trace` already run every frame in
  `LuaExportAfterNextFrame` with their own `safe_call(function() ... end)` closures; this function
  is more closures than the position-command model it replaced, but is the same *kind* of cost this
  file already tolerates at this frame rate, not a new category of per-frame work (no new
  per-frame table/array allocation found — `run_sight_servo` reads into locals and module-level
  state only). The dither `sin`/`cos` calls are cheap floating-point ops, not allocations. No fix
  requested now. If a future frame-time complaint arises, this function's closure count is now the
  single largest contributor in the file and should be the first one profiled, not folded into the
  "look at all of them collectively" note v1 left — it has grown enough since v1 to deserve being
  named first.

#### Redundant device-0/device-`DEV_I9K113` lookups within one frame
- **Location:** `run_sight_servo` calls `GetDevice(0)` three times per frame in the steady-state
  `"closed"` path (OBSERV, align lamp, then once each for the two mark arguments), in addition to
  the device-0 lookups `push_cockpit_switch_state` and `push_slew_trace` already make earlier in
  the same `LuaExportAfterNextFrame` frame; `sight_point_quiet` separately looks up
  `GetDevice(DEV_I9K113)` once per write.
- **Risk:** Purely redundant engine-side handle lookups, not allocations.
- **Action:** LATER — unchanged from v1's verdict on the same pattern, now with one more call site.
  Not credible as a budget risk this phase; worth a single pass across all of
  `LuaExportAfterNextFrame`'s per-frame helpers together if/when Petrobrain Runtime's real-time
  budget phase begins, not piecemeal per stage.

#### `look_contact` resolution: list allocation + linear scan, once per poll
- **Location:** `logger.py:822-825` (`run_once`):
  ```python
  look_contact = next(
      (contact for contact in self.store.contacts if contact.id == self.optic_state.look_contact_id),
      None,
  )
  ```
  `ContactStore.contacts` (`belief/contacts.py:930`) is `list(self._contacts.values())` — a fresh
  list built from the backing dict on every access, even though `ContactStore` already holds
  contacts in a dict keyed by id and a direct `self.store._contacts.get(id)` would be O(1) with no
  allocation.
- **Risk:** One list allocation + one O(n) scan per poll, n = live contact count. At this project's
  realistic scale (a single-aircraft engagement, contact counts in the tens) this is not a
  measurable cost at 1–5 Hz, and it is not new: `belief/tools.py:189`, `belief/tools.py:597/892/935`,
  and `belief/utterance.py:204` already do the identical `for c in store.contacts: if c.id == ...`
  scan — `ContactStore` exposes no `get_by_id`, so every caller in this codebase resolves a contact
  by id this way today. This is this project's established convention, not a pattern this stage
  introduced.
- **Action:** MONITOR. Not credible as NOW at current contact counts, and fixing it only at this
  one call site while five others keep the same pattern would not remove the cost class, only
  relocate it. If `ContactStore` ever grows a `get_by_id`/dict-keyed accessor (worth doing once
  contact counts or poll rate materially increase — body-layer's hard real-time budget only starts
  with Petrobrain Runtime), it should replace all six call sites in one pass, not just this one.

#### `advance_sight_head`/`select_sight_goal`/`seen_world_direction`: per-poll arithmetic
- **Location:** `belief/sight_head.py` (`advance_sight_head`, `select_sight_goal`,
  `_step_toward`, `_world_to_body`, `_clamp_gimbal`), `belief/attack_run.py`
  (`_seen_world_offset`, `seen_world_direction`), `perception/geometry.py`
  (`world_direction_from_body`, new). All called at most once per poll from `run_once`
  (`logger.py:134`), never in a loop over contacts or percepts.
- **Risk:** None credible. Each call is a fixed number of trig/arithmetic operations and one or two
  `dataclasses.replace()` calls on an already-frozen dataclass — the same cost class as every other
  `OpticState`/`GuidanceUnitState` update already in this codebase at the same ~1–5 Hz rate. No
  per-poll collection iteration, no string building, no I/O.
- **Action:** MONITOR (included for completeness, not because it is a risk).

#### `/command/sight_target` and `SightServoCache`/`/sight_servo/latest` (aircraft-layer)
- **Location:** `aircraft-layer/src/api/server.py` (`_handle_command_sight_target`,
  `_handle_sight_servo_latest`), `collector/cache.py` (`SightServoCache`, "latest of one" shape).
- **Risk:** None credible. `SightServoCache` is the same single-slot `latest()`/`push()` shape as
  `CockpitSwitchCache`, called at 5 Hz from `Export.lua`'s own push and at whatever rate a client
  polls `/sight_servo/latest` (no polling loop reads this at frame rate; nothing in this diff adds
  a caller faster than the existing 1–5 Hz poll pattern). `_handle_command_sight_target`'s field
  validation is a fixed handful of bounds checks per POST, same shape as `/command/cockpit_switch`.
- **Action:** MONITOR (included for completeness).

#### `write_sight_target` / `AircraftLayerClient` blocking HTTP writes
- **Note:** v1's "`write_sight_target` blocking HTTP write in the poll loop" finding does not
  carry forward — that write-path (`sight_effector.write_sight_target` →
  `AircraftLayerClient.write_sight_target`) belonged to the superseded position-command model and
  is gone from this diff (confirmed: `git diff main...HEAD -- body-layer/src/logger.py` shows no
  changes to `logger.py` since the Stage-1–4 review tip `a3a16eab`, and `sight_effector.py`'s
  surviving functions are the az/elev raw↔deg conversions, not a network write). The v2 model
  instead pushes the goal from `Export.lua`'s own per-frame servo state outward (`push_sight_servo_
  state`, `GET /sight_servo/latest`); body-layer never blocks on a synchronous sight-target POST in
  this version. No equivalent finding needed.

### Verdict
APPROVED — MONITOR

---

## v1 (superseded — position-command model)

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
