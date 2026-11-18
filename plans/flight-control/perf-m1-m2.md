### Performance Review

Batch: BL-16 mode 1 Stages M1+M2 (raw-axis flight control). Diff reviewed: `0c206b37..6aa511c2`
(branch `feature/bl16-raw-axes`). Scope: `aircraft-layer/dcs-export/Petrobrain/flight_control.lua`
(new module, 1477 lines; `run_flight_control` runs every DCS frame from a new
`LuaExportBeforeNextFrame` callback, unconditionally, confirmed in `Export.lua`'s own diff —
`push_flight_control_state` is the only part gated to the existing 5 Hz tick inside
`LuaExportAfterNextFrame`), plus `body-layer/src/belief/flight_control.py` and
`body-layer/src/body.py:_apply_flight_control` (per-poll, human-paced, not per-frame).

Builds on the posture `perf-batch-a.md`/`perf-takeover.md`/`perf-p2.md` established for this
feature: per-frame `Export.lua` work is only what must be per-frame, a device read is not
duplicated across functions in the same tick, and a new per-frame closure/table-allocation shape
is judged against the file's own established baseline
(`project_export_lua_per_frame_closures_are_established_pattern.md`), not in isolation.

### Findings

#### `check_envelope` and `read_measured` independently read the same three DCS getters, every active frame

- **Location:** `flight_control.lua:856-882` (`check_envelope`) and `flight_control.lua:931-978`
  (`read_measured`), both called from `run_active_frame` (`flight_control.lua:1159,1169`) in
  sequence, every frame `fc_mode == "active"` and not paused. `check_envelope` calls
  `LoGetSelfData`, `LoGetIndicatedAirSpeed`, and `LoGetADIPitchBankYaw`. `read_measured` calls all
  three again (plus six more: `LoGetTrueAirSpeed`, `LoGetVerticalVelocity`,
  `LoGetAltitudeAboveGroundLevel`, `LoGetRadarAltimeter`, `LoGetAltitudeAboveSeaLevel`,
  `LoGetAngularVelocity`), each wrapped in its own `safe_call` closure.
- **Risk:** this is exactly the "redundant query" shape the project's own memory already names as
  the thing to watch for in this file (`project_flight_control_p1_perframe_indication_read.md`:
  "before approving a new per-frame … call, check whether an existing … caller already reads the
  same device/API this tick"), except here it is two functions in the *same new module*, not a
  second feature duplicating an older one. `LoGetSelfData`/`LoGetIndicatedAirSpeed`/
  `LoGetADIPitchBankYaw` each cross the Lua→DCS-engine boundary — the one per-call cost class this
  codebase has repeatedly flagged as real-but-unmeasured
  (`project_aircraft_layer_hotspots.md`) — and are paid twice per frame, unconditionally, for as
  long as mode 1 is `active` (potentially most of a sortie once the pilot delegates raw-axis
  flying). The duplication is pure waste: nothing about `check_envelope`'s read needs to be
  independent of `read_measured`'s.
- **Action:** NOW.
- **Mitigation:** call `read_measured()` once per active frame and have `check_envelope` take the
  resulting `measured` table (it only needs `ias_mps` and `bank_deg`, both already in it) instead
  of re-reading `LoGetSelfData`/`LoGetIndicatedAirSpeed`/`LoGetADIPitchBankYaw` itself. `check_
  envelope`'s own `self_data`-is-a-table check ("dead" cause) can be folded into `read_measured`
  (e.g. have it also return whether `LoGetSelfData` came back as a table) or left as a single
  extra `LoGetSelfData` call solely for that liveness check, which is one redundant call instead
  of three. A pure refactor, no change to behaviour, no architectural change — Implementer-level.

#### `law_update`'s per-frame full-state copy via generic `pairs()` iteration

- **Location:** `flight_control.lua:506-508` (`law_update`): `local next_state = {}; for k, v in
  pairs(state) do next_state[k] = v end`, then ~15 of the ~25 copied fields are individually
  overwritten. Runs every active frame (not gated), allocating one new ~25-key table per call.
  `write_outputs` (`flight_control.lua:892-922`) separately allocates a smaller (≤4-key)
  `new_last` table every active frame too.
- **Risk:** a genuine per-frame heap allocation, which root `CLAUDE.md`'s "No per-request
  allocations on hot paths" names directly and which matters here specifically because
  `Export.lua` runs on DCS's own render thread — cost here is cockpit stutter, not service
  latency (`project_aircraft_layer_hotspots.md`). That said, judged against this file's own
  established baseline rather than in isolation (per `project_export_lua_per_frame_closures_are_
  established_pattern.md`): `run_sight_servo` already allocates several `safe_call(function()...
  end)` closures and conditional `LoGetSelfData`/`LoGetADIPitchBankYaw` calls every frame with no
  reported stutter, and no live-DCS profiling tool exists anywhere in this repo to put a real
  number on either allocation's cost (same gap `project_export_lua_per_frame_push_functions.md`
  already names). A ~25-key table copy is larger than that baseline's small closures, but it is a
  pure-Lua table op, not a second engine-boundary crossing — the credibly-expensive part of a
  frame is the `LoGet*`/`GetDevice` calls, not Lua's own table allocator. The architecture reason
  for the copy-then-mutate shape is explicit and deliberate (`law_update` must stay pure, "never
  mutates `state` in place," so the toy-plant test suite can hold a pre-call reference and diff it
  against the post-call result) — changing that is a design-level call, not a local fix.
- **Action:** MONITOR. Flag to Architect only if a live-flight symptom (stutter, missed frame,
  visible axis jitter) is ever reported while mode 1 is active for an extended period — at that
  point the cheap, non-architecture-breaking fix is to replace the generic `pairs()` copy with an
  explicit field-by-field return table (the same style `law_init_at_take` already uses for its own
  return value), which is still a new table and still pure, but skips hashing over every key twice
  (once to copy, once to overwrite) and makes the function's actual field set visible at the call
  site instead of implicit in the copy-then-overwrite pattern.

#### `update_live_seat_tracking` runs unconditionally every frame, `fc_mode` irrelevant, and widens the already-flagged `GetDevice(0)`-per-field pattern

- **Location:** `flight_control.lua:761-771` (`update_live_seat_tracking`), called from
  `run_flight_control` (`flight_control.lua:1204`) before any mode check — runs every single DCS
  frame regardless of `fc_mode`, including "off" (the common case for most of a sortie if mode 1
  is rarely engaged). It calls `axis_magnitude("pilot")` and `axis_magnitude("operator")`
  (`flight_control.lua:724-735`), each of which iterates `FC_AXES_ENABLED` via `pairs()` and calls
  `read_axis` → a fresh `safe_call(function() return GetDevice(0):get_argument_value(arg) end)`
  closure per enabled axis — currently 3 enabled axes (pitch/roll/pedals) × 2 seats = 6 fresh
  `GetDevice(0)` lookups and 6 closures, every frame, forever, whether or not mode 1 is ever used
  this sortie.
- **Risk:** this is the deliberate design the module's own docstring calls for (M0-J, flight 9: "a
  take can land on any frame," so the capture-source snapshot must already be current) — not a
  bug, and the per-axis cost is small and bounded (4 axes max, never scales with contact count or
  world size). But it is the concrete case the project's own standing memory
  (`project_export_lua_per_frame_push_functions.md`) named as the trigger to re-open that finding:
  *"if a fourth such function is added … re-open this finding rather than re-deriving it from
  scratch. The threshold … is: the read count keeps growing at this shape."* This module adds up
  to 6 more uncached `GetDevice(0)` lookups per frame on top of the 12 the three existing
  `push_*` functions already do unconditionally — the read count has grown again, at the same
  shape that memory predicted.
- **Action:** MONITOR (reopening the named threshold, not a new NOW-level finding on its own —
  the per-call cost is unmeasured and no symptom has been reported). **Recommended when next
  touched:** cache one `local device0 = GetDevice(0)` per `run_flight_control` call (or per
  `LuaExportBeforeNextFrame`/`AfterNextFrame` pair, covering `push_ptt_state`/`push_spu8_state`/
  `push_cockpit_switch_state` too) and thread it into `read_axis` instead of each call doing its
  own `GetDevice(0)` — collapses what is now 18+ per-frame `GetDevice(0)` calls across the file
  into one. Worth doing as one pass across the whole file rather than per-module, per that
  memory's own recommendation.

#### Body-layer side — per-poll, not per-frame; same bounded shape already cleared for this feature

- **Location:** `body-layer/src/belief/flight_control.py` (`advance_flight_control_state`,
  `take_controls`, `release_controls`, `decide_flight_control`) and `body-layer/src/body.py:3505`
  (`_apply_flight_control`), all called once per poll (human/crew-cognition cadence, not a
  frame-rate path).
- **Risk:** none. Every function is a single `dataclasses.replace` or a handful of comparisons —
  no loop over a collection, no per-poll allocation beyond one small dataclass construction, same
  cost class `perf-p2.md` already cleared for this feature's sibling (`ai_pilot_wheel`) goal
  plumbing. `_apply_flight_control` sends at most three small, fixed-shape HTTP writes per poll,
  gated on an actual state transition (`transition is not None` / `goal_request is not None`),
  never unconditionally.
- **Action:** none.

### Verdict
APPROVED — MONITOR
