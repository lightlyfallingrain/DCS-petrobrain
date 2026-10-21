### Performance Review

Batch reviewed: `feature/9k113-effectors`, Stages 1-4 + review-fix + Stage 4b, built back to back
as one batch, tip `da1812f62de4a28ed016d52f1b37bbd5fe11cda7`. Touches `aircraft-layer/dcs-export/
Export.lua` (per-frame export hook), `aircraft-layer/src/{schema/cockpit_switch.py,collector/*,
api/server.py}`, `body-layer/src/{belief/sight_effector.py,sight_trace_writer.py,logger.py,
aircraft_client.py}`. No hard real-time budget in this phase (Petrobrain Runtime has not started);
body-layer's own budget is the existing 1.0 Hz poll loop (`logger._DEFAULT_POLL_INTERVAL_S`), and
the aircraft-layer side runs inside DCS's own per-frame export callback, which has no documented
project budget but is the one place "never block the sim frame" actually applies.

### Findings

#### `push_cockpit_switch_state` — 8 unconditional per-frame reads, every frame, no flag gate

- **Location:** `Export.lua`'s `push_cockpit_switch_state`, called from `LuaExportAfterNextFrame`
  unconditionally (only short-circuits on `client == nil`) — 8 `safe_call(function() ... end)`
  closures, each a fresh closure allocation + `pcall` + `GetDevice(0):get_argument_value(...)`,
  every single DCS frame for as long as a collector connection is up.
- **Risk:** this is the one place in the diff that runs on DCS's own frame budget rather than
  body-layer's 1 Hz poll, so it is the correct hot path to scrutinize. It is not a new pattern —
  `push_ptt_state` (1 read) and `push_spu8_state` (3 reads) already do exactly this shape,
  unconditionally, every frame, and that shape has shipped for two prior features without a
  reported frame-time problem. This diff triples the read count on top of that (ptt 1 + spu8 3 +
  cockpit_switch 8 = 12 unconditional `GetDevice(0)` calls + closure allocs per frame), and nothing
  in the diff caches the `GetDevice(0)` handle across these three functions — each of the 12 calls
  does its own fresh `GetDevice(0)` lookup. `get_argument_value` on an already-open device is a
  cheap table/array read inside DCS's own device model, not a scan or allocation on DCS's side;
  the real per-frame cost added here is Lua-side (12 closure objects + 12 `pcall` frames vs. 4
  before this diff), not engine-side.
- **Action:** MONITOR, not NOW. No measurement tool for DCS's own frame budget exists in this
  repo (there's no way to profile `LuaExportAfterNextFrame` without a live DCS session, and the
  existing two-feature precedent at this shape has not been flagged as a problem), so "trivial"
  here is an informed judgement call, not a measured number — stated plainly rather than quoted as
  one. The qualitative case for MONITOR: 12 small closures + 12 `pcall`s is well inside what Lua's
  frame-rate-class interpreters handle routinely (this is the same order of magnitude as a handful
  of table lookups), and DCS's own per-frame budget is milliseconds, not microseconds. The real
  reason this is not NOW is that the pattern this diff extends was never NOW either.
- **Mitigation (if ever revisited, not required now):** cache one `local device0 = GetDevice(0)`
  per `LuaExportAfterNextFrame` call and pass it into `push_ptt_state`/`push_spu8_state`/
  `push_cockpit_switch_state`, collapsing 12 `GetDevice(0)` lookups into 1. Cheap to do, but there
  is no evidence it is needed yet — flagging so a future reviewer adding a *fourth* such function
  does not have to re-derive this, and so the threshold for actually doing it ("this function count
  keeps growing linearly with every effector feature") is visible in one place rather than
  rediscovered each time.

#### `push_slew_trace` — per-frame log line, but correctly flag-gated and buffered

- **Location:** `Export.lua`'s `push_slew_trace`, also called unconditionally from
  `LuaExportAfterNextFrame`, but its body returns immediately when `SLEW_DEBUG` is `false`
  (checked once at load, default off) — a true no-op in the default case, same shape `DEBUG` itself
  already uses. When on, it only logs while OBSERV is on (plus a 5 s tail), and buffers 25 lines
  before a disk flush rather than flushing every frame.
- **Risk:** none at default. When enabled for a sortie's hand-slew segment, this is the deliberate,
  user-requested tradeoff ("put logging in so the slew loop can be adjusted from data") — a
  temporary diagnostic tool, not a shipped always-on cost.
- **Action:** none required. Correctly scoped: off by default, gated separately from `DEBUG` so
  turning on ordinary debug logging doesn't silently also turn on a per-frame file write, and
  buffered rather than flushed per line.

#### body-layer poll loop — one new GET + up to one new POST per poll, same shape as existing `/latest` polling

- **Location:** `_run_crew_text_poll_loop`'s new wiring: `refresh_cockpit_switch_readback` calls
  `aircraft_client.get_cockpit_switch_state_latest()` (`GET /cockpit_switch/latest`)
  unconditionally every poll; `advance_power_up` issues one `write_cockpit_switch` POST per poll
  while the 4-switch sequence is in progress (bounded: at most 4 POSTs total per takeoff, one per
  poll, never per-contact or per-frame); `write_observ`/`write_weapon_safety` fire at most once per
  accepted command.
- **Risk:** this is a real additional network round-trip per poll, but it follows the exact shape
  every other `get_*_latest()` call on `AircraftLayerClient` already has (`get_line_of_sight_
  latest`, `get_petrovich_wheel_latest`, etc.) — one more single-slot cache read at 1 Hz, on a
  background poll thread (not the main/UI thread), well inside a 1 Hz budget with no hard
  real-time requirement in this phase. Not a new risk category; one more instance of an
  already-accepted pattern.
- **Action:** none required.

#### `SightTraceWriter.write_poll` — one dict + `json.dumps` per poll, opt-in only

- **Location:** `sight_trace_writer.py`'s `write_poll`, called every poll from `_run_crew_text_
  poll_loop` only when `--slew-trace PATH` is passed (defaults off, `parser.error`s without
  `--crew-text`).
- **Risk:** negligible — one small dict, one `json.dumps`, buffered 5 polls before a flush,
  identical shape to `DetectionTraceWriter` which this role has already reviewed and approved at
  this scale. Not on any hot path by default.
- **Action:** none required.

#### Collector cache / API additions (`CockpitSwitchCache`, `POST /command/cockpit_switch`)

- **Location:** `aircraft-layer/src/collector/cache.py`'s `CockpitSwitchCache`, `api/server.py`'s
  new GET/POST handlers.
- **Risk:** none — single-slot "latest of one" cache, identical shape to `Spu8Cache`/
  `PttCache`/`MissionStartCache` already in this file; the POST handler does O(1) shape validation
  (two `isinstance` checks, one finite-number check) with no allow-list lookup, so no per-request
  iteration over anything.
- **Action:** none required.

### Verdict

APPROVED — MONITOR
