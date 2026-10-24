### Performance Review

Scope: BL-B90 Stage 4 ("readback by need"), batch = this one stage, reviewed before DoD.
Address: branch `feature/effector-sequences-stage4`, tip `2b742cf3` (checked out detached —
HEAD had diverged from local `main`, tree was clean). Diff reviewed: `c231efda..2b742cf3`.

No per-request/per-frame budget applies yet (Petrobrain Runtime has not started); the relevant
bar is the project's standing hot-path rules — no per-frame allocation on the Lua side, prefer
batching/precomputation, offload blocking work. Verified by reading `Export.lua`,
`arg_read_broker.py`, `effector_engine.py`, `aircraft_client.py`, `logger.py`'s poll block —
no live DCS run (per task scope).

### Findings

#### Per-frame switch reads removed (the stage's own headline claim)
- **Location:** `aircraft-layer/dcs-export/Export.lua` — `push_cockpit_switch_state` is fully
  deleted (only comments reference the old name now, grep-confirmed: no function definition, no
  call site). `push_watched_args_state` (3 `get_argument_value` reads for the shipped
  `{886,898,960}` set) is called from inside the existing 5 Hz export throttle
  (`if t - last_export_t < EXPORT_INTERVAL_S then return end`, `Export.lua:1873-1876`, call site
  at line 1974, *after* the throttle check and after the telemetry send succeeds), not from the
  per-frame `LuaExportAfterNextFrame` body directly.
- **Risk:** none — this is the claim holding up. Before: 9 reads + 9 `GetDevice(0)` calls + 9
  closures every frame (~125 fps measured) = ~1,125 reads/s. After: 0 per frame, 3 reads per 5 Hz
  tick = 15 reads/s continuous (~75× fewer, matches plan S4.8 exactly), plus the change-gate
  (`watched_args_changed`) before any JSON encode or socket send — a send happens only when a
  watched value actually moved or on forced resend (reconnect/first connect).
- **Action:** none needed. Confirmed, not just claimed.

#### Synchronous one-shot read on the aircraft-layer HTTP worker thread
- **Location:** `aircraft-layer/src/collector/arg_read_broker.py` `ArgReadBroker.read`, called
  from `POST /query/read_args`.
- **Risk:** blocks the calling HTTP worker thread for up to `ARG_READ_TIMEOUT_S` (0.25 s) while
  waiting on a `threading.Event`. The server is `ThreadingHTTPServer` (confirmed,
  `aircraft-layer/src/api/server.py`), so this does **not** serialize other endpoints
  (`/telemetry/latest`, etc.) behind a stalled read — each connection gets its own thread, and
  the wait holds no lock (the lock is only taken to mint/release the slot, never across the
  `event.wait`). `MAX_OUTSTANDING_READS = 8` bounds how many such threads can be parked at once;
  a 9th is refused immediately (`ArgReadBrokerBusy`), not queued. A stalled Export.lua therefore
  costs at most 8 parked worker threads for at most 0.25 s each, never an unbounded pile-up.
- **Action:** MONITOR. The bound is real and the design note in the module docstring already
  states the reasoning (sync-at-collector vs. async-ticket latency tradeoff). Nothing to fix now.

#### Synchronous `read_args` inside `effector_engine.advance` (poll-loop thread)
- **Location:** `body-layer/src/belief/effector_engine.py:314-333`, one `client.read_args(...)`
  call per running cursor whose `snapshot is None` (run start, or right after a `WaitRow`),
  inside the `for trigger in order` loop — so N concurrently-running triggers needing a fresh
  snapshot in the same poll cost up to N sequential blocking calls in that one `advance()` call.
- **Risk:** worst case (Export stalled, every shipped trigger fires in the same poll) is N ×
  0.25 s added to that poll's wall time on the ~1 Hz poll-loop thread. Currently 5 trigger files
  ship (`takeoff`, `observ-on`, `observ-off`, `weapons-arm`, `weapons-safe`); the plan's own risk
  section (S4.10) already states "up to 7 in one poll if every trigger fires at once, which no
  shipped flow does" — consistent with what's actually shipped, not an inflated claim. A failed
  read holds only that trigger (`break`, not a retry-forever loop) — other triggers in the same
  `advance()` call still progress. On repeated failure it resolves to `snapshot = {}` after
  `EFFECTOR_CONDITION_READBACK_WAIT_S`, so it cannot stall a trigger indefinitely, only delay it
  by that bound. This is a real, already-documented and already-bounded risk, not newly found
  here.
- **Action:** MONITOR, not NOW. It is bounded, rare (requires simultaneous trigger fires, which
  no shipped sequence causes), and already named in the plan with the correct order of magnitude.
  If a future sequence set grows to where simultaneous fires become routine (e.g. a scripted
  macro firing several triggers at once, `BL-B95`), revisit whether reads should be deduplicated
  across cursors sharing overlapping `read_args` sets in one `advance()` call — not needed today.

#### Per-poll `GET /watched_args/latest` + confirmation/resend bookkeeping
- **Location:** `body-layer/src/logger.py`, `_run_crew_text_poll_loop`'s poll block
  (`~line 3650-3710`): one `aircraft_client.get_watched_args_latest()` HTTP call per poll,
  `watch_id_for`/`watch_args_due` comparisons, and a conditional `set_watch_args` resend.
- **Risk:** none beyond the existing pattern. `desired_watch_id`/`desired_watch_args` are
  computed once before the poll loop starts (`logger.py:3465-3468`), not recomputed per poll.
  The added HTTP GET is one more call at the same ~1 Hz cadence this poll loop already makes for
  `telemetry`/`world_objects`/`petrovich_indication` — no new allocation pattern, no busy
  polling, and the resend itself is gated to at most once every `WATCH_ARGS_RESEND_S` (2.0 s) via
  `watch_args_due`, a pure function with no side effect of its own.
- **Action:** none needed.

#### `aircraft_client.read_args`'s own reply re-validation
- **Location:** `body-layer/src/aircraft_client.py:327-366` — regex/type/membership checks over
  every key in the reply, bounded to ≤ 64 entries.
- **Risk:** none at realistic scale. This runs once per one-shot read (run start / wait row), not
  per poll and not per frame — at most a handful of calls per trigger fire, bounded to ≤ 64
  entries each. The security plan review required this validation; it costs a small bounded loop
  on an already-infrequent path, not a hot one.
- **Action:** none needed.

### Verdict
APPROVED
