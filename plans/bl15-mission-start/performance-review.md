### Performance Review

Batch reviewed: BL-15 Stage 1 batch, `feature/bl15-mission-start`, diff base `eab86662` to tip
`ea5f77fc` (all three implementation batches covered by Reviewer's `review.md` Batch 1/Batch 2,
plus the Batch 3 required-fix commits — the whole currently-executed set, per the "one pass per
batch actually executed together" rule). Stage 4 (live acceptance) is not code and carries no
runtime cost.

**Scope calibration**: this is runtime polling in `body-layer/src/logger.py`'s poll loops, which
is Petrobrain Runtime territory in spirit but still pre-hard-real-time per root `CLAUDE.md`
("No hard real-time budget in this phase — that constraint starts once Petrobrain Runtime work
begins"). The applicable constraints here are "no per-request allocations on hot paths," "prefer
batching," and "offload heavy work asynchronously" — not a latency SLA. Single-player, LAN-only
(one aircraft-layer collector, one body-layer process).

**Measured, not assumed**: actual poll rate is `_DEFAULT_POLL_INTERVAL_S = 1.0` (confirmed by
reading `logger.py:1434` and the graph node recording the project's own correction of a stale
5 Hz claim — `Export.lua`'s *producer* rate, never this consumer's). Per poll, `run_once()`
already issues ~6-7 synchronous `GET` calls via `AircraftLayerClient` before this feature:
`get_telemetry_latest` (once), `HybridPerceptionSource.poll` (`get_petrovich_indication_latest`,
`get_world_objects_latest`), `NakedEyePerceptionSource.poll` (`get_world_objects_latest` again,
`get_unit_velocity_latest`, `get_firing_latest`, `get_line_of_sight_latest`). `_check_for_new_
mission` adds exactly one more (`get_mission_start_latest`) at the top of the loop, before any
of those.

### Findings

#### Extra HTTP GET per poll (`_check_for_new_mission` → `get_mission_start_latest`)
- **Location:** `body-layer/src/logger.py:_check_for_new_mission` (called from both
  `_run_console_poll_loop` and `_run_crew_text_poll_loop`, once per poll, before `run_once()`).
- **Risk:** none credible at this scale. This is an 8th synchronous GET added to a poll cycle
  that already makes 6-7, at a measured 1 Hz, on a LAN against a single collector. Each call is
  a `urllib.request.urlopen(url, timeout=2.0)` — no connection pooling anywhere in
  `AircraftLayerClient` (every `get_*`/`post_*` method opens and tears down its own connection),
  but that is the pre-existing shape of *every* call this client makes, not something this
  feature introduced. Adding one more call of the same shape is a ~14% increase on an
  already-established per-poll pattern, not a new cost class. The server side
  (`_handle_mission_start_latest` → `MissionStartCache.latest()`) is an O(1) dict read, matching
  every other `/latest` endpoint.
- **Action:** MONITOR.
- **Mitigation (not required now):** if the per-poll GET count on this seam ever becomes a
  concern (e.g. if a future feature pushes the poll rate up, or adds several more `/latest`
  calls), the fix is connection reuse (`urllib3`/`requests.Session`, or a persistent
  `http.client.HTTPConnection` wrapped by `AircraftLayerClient`) applied once across *all*
  `get_*` methods, not a one-off special case for this endpoint. Out of scope for this review —
  it would be a pre-existing-debt fix, not something this diff caused or should carry alone.

#### Timeout behaviour on a slow/unreachable collector
- **Location:** `AircraftLayerClient._get_json` (`timeout_s=2.0` default), called synchronously
  inside the poll loop's single `try` block.
- **Risk:** a slow or hung collector response to `GET /mission_start/latest` can block the poll
  thread for up to 2 s before `AircraftLayerError` is raised and caught
  (`_check_for_new_mission`'s own `except AircraftLayerError: ... return False`). This stalls the
  *entire* poll cycle (perception, belief, speech) for that iteration, same as a slow response on
  any of the 6-7 pre-existing calls already in `run_once()`. This is an identical risk to one that
  already exists for every other endpoint this client polls — not a new or worsened failure mode,
  and the degrade path (log-and-continue, retry next poll) is the same posture used everywhere
  else in these poll loops (`post_look_direction`'s own try/except is the cited precedent in the
  implementer's own docstring).
- **Action:** MONITOR (pre-existing architectural property, not introduced by this feature).
- **Mitigation:** none proposed here. A real fix (async I/O, or a watchdog that skips a poll
  rather than blocking on it) is a cross-cutting change to the whole poll-loop architecture, not
  something to bolt onto one endpoint — would need an Architect pass if the user decides this
  synchronous-serial-GET design needs to change before Petrobrain Runtime's hard-real-time phase.

#### Per-poll cost when nothing changed
- **Location:** `_check_for_new_mission`, unchanged-sequence path (`logger.py:1895-1896`).
- **Risk:** none. One GET (already counted above), one dict `.get("sequence")`, one `isinstance`
  check, one int comparison, early return. No allocation, no iteration over any collection sized
  by mission state. This is the steady-state path (every poll except the rare one where a restart
  actually happened) and it is as cheap as this mechanism can be made.
- **Action:** MONITOR (no action needed; noted only for completeness).

#### One-off reset/switch costs (sqlite open, `_build_sources`, log re-roll)
- **Location:** `_reset_mission_state` (five `reset_for_new_mission()` calls, all `self.__init__()`
  re-invocations or direct attribute clears — no full-dataset iteration, since the datasets being
  cleared are the belief store's own in-memory dicts/lists, reset to empty rather than iterated),
  `_maybe_switch_theatre` (opens a new `sqlite3.Connection`, runs `load_only_region` to validate
  the built region, calls `_build_sources`, closes the old connection only after the new one is
  live), `_reroll_run_logs` (closes two open file handles, constructs three fresh writer objects,
  rebuilds one stale closure).
- **Risk:** none at this project's stated scale. These only run when `_check_for_new_mission`
  detects an actual sequence change — a genuine DCS mission (re)start, which happens at most a
  handful of times per sortie (the pilot restarting the mission, or flying back-to-back missions
  in one process lifetime), not per poll. The sqlite open/`_build_sources`/log-reopen work is
  exactly the same one-off cost `main()` already pays once at process startup; this feature just
  makes that cost pay again on a detected restart instead of requiring a process relaunch. All of
  it runs synchronously on the poll thread (the same thread-affinity constraint `sqlite3.
  Connection` already imposes, documented in both the plan and `logger.py`'s own module
  docstring), so it does block that one poll iteration for its duration — but this is a rare event
  with no pilot-facing latency budget attached to it in this phase (no hard real-time constraint
  yet), and the plan's own degrade path (loud refusal rather than silently running against the
  wrong theatre) is explicitly correctness-over-latency by the user's own stated preference
  ("on error loud refusal is better," 2026-10-19).
- **Action:** MONITOR. Acceptable as implemented; nothing here crosses into "must fix now."

#### `MissionStartCache`/aircraft-layer side
- **Location:** `aircraft-layer/src/collector/mission_start_receiver.py` (loopback UDP, one
  datagram per `onSimulationStart`), `MissionStartCache.push`/`.latest` (latest-of-one, O(1)).
- **Risk:** none. One-shot push per mission start (no per-frame Lua-side polling, unlike the F10
  commands channel's drained queue), matching the plan's own stated design. No full-dataset
  iteration, no redundant querying, no allocation on a per-frame path.
- **Action:** MONITOR (no action needed).

### Verdict

APPROVED — MONITOR

No hot-path allocation, full-dataset iteration, redundant querying, or poor batching found in
this batch. The one new per-poll cost (an 8th synchronous GET at 1 Hz) is proportionate to the
existing poll-loop design and not a new cost class; the one-off reset/switch costs are correctly
gated on a rare event and match the project's own precedent (`main()`'s own startup cost paid
again on detected restart, not a fresh mechanism). The two MONITOR items (no connection pooling
across all `get_*` methods; synchronous-serial-GET poll loop can stall a full cycle on a slow
collector) are pre-existing properties of `AircraftLayerClient`/the poll-loop architecture that
this feature inherits rather than introduces or worsens — worth remembering if the poll rate or
per-poll call count grows further, or once Petrobrain Runtime's hard-real-time phase begins, but
not a required change for this batch.
