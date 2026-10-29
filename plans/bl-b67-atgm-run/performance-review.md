### Performance Review

Batch A (Stage 0 probe files + Stages 1-4), `feature/bl-b67-atgm-run` @ `f2c8c25c`. No hard
real-time budget applies yet (Petrobrain Runtime phase has not started) — the relevant bar is the
project's standing hot-path rules: no per-request allocation, no full-dataset iteration, prefer
precomputation/batching, never block the main thread. Scope checked:
`git diff main...f2c8c25c -- body-layer aircraft-layer` (Stage 5+ own-weapon channel is not in
this diff — confirmed by `git diff --stat`, so its previously-flagged "one extra `GET
/firing/latest` per poll" risk does not apply to this batch).

### Findings

#### `atgm_run.decide` and its call sites in `body.py`'s 1 Hz poll loop
- **Location:** `belief/atgm_run.py::decide` and its construction/threading in `body.py`
  (`AtgmRunState` dataclass replace, `sight_lock_contact_id`, `vertical`, `guidance_floor`
  derivation).
- **Risk:** None credible. Every new per-poll operation is O(1): dataclass construction/`replace`,
  a handful of scalar comparisons, dict lookups into two small fixed-size family tables. No loop
  over contacts, stations, or history. This is the same shape as the existing `attack_run.decide`
  it was modelled on.
- **Action:** MONITOR (only in the sense that Stage 5-7 wiring, not this batch, adds the one real
  per-poll I/O cost the plan's own Risks section already names and accepts — an extra
  `GET /firing/latest`; re-check when that stage lands).

#### `aim_unit_direction` — nearest-cluster-member aim (`naked_eye_source.py::_build_observation`)
- **Location:** `NakedEyePerceptionSource._build_observation`, new block computing
  `member_directions` (dict comprehension over `cluster.members`) and `min(...)` over the same.
- **Risk:** This is a bounded query, not a full-dataset scan — it iterates only the current
  candidate's cluster (typically single digits of members), and only when gated by
  `live_los_clear is True` and a sight-tier optic, i.e. the same rare, already-narrow condition
  `relative_direction`'s own centroid math runs under. No allocation scales with contact count or
  theatre size; it scales with cluster size, which this project's own convention already treats as
  small and bounded (group/cluster membership, not a world-object scan). Not a credible risk at any
  realistic scale.
- **Action:** MONITOR. If a future cluster-size cap is ever removed or clusters are allowed to grow
  large (dozens of members), this `O(cluster)` work (plus the two `body_relative_direction` calls
  per member) would be the thing to revisit — flagging the assumption, not the code.

#### `callouts.py`'s `hold_routine` gate
- **Location:** `CalloutScheduler.tick`, the event-candidate loop and the group-disclosure loop.
- **Risk:** None. Each adds one O(1) boolean check per already-iterated candidate/group; no new
  iteration, no new allocation, default `False` is a true no-op for every existing caller (byte-
  identical behaviour, confirmed by the implementer's own no-op claim and the test suite).
- **Action:** MONITOR (no action; included for completeness since it touches a per-poll loop that
  scales with live contacts).

#### `Export.lua`'s `push_payload_state` (5 Hz export tick, not per-frame)
- **Location:** `dcs-export/Export.lua::push_payload_state`, called from
  `LuaExportAfterNextFrame` at the same throttled cadence as `push_watched_args_state` —
  confirmed from the diff this sits *after* the existing `EXPORT_INTERVAL_S` throttle check, not
  in the unthrottled per-frame body.
- **Risk:** It builds the station-list JSON fragment and the change-gate signature string on
  *every* 5 Hz tick, even when nothing changed — only the socket `send` is gated on the signature
  comparison. This is table/string allocation on a hot-ish path, but: (a) it is capped at ≤8
  stations (the plan's own stated cap), so the work is O(1) in practice, not O(n) over anything
  that grows; (b) it is the same allocate-then-compare-then-maybe-send shape
  `push_watched_args_state` already uses in this file, so it is not a new pattern, just a second
  instance of an accepted one; (c) 5 Hz on a handful of short string concatenations is far below
  any DCS frame-time concern, and this is explicitly pre-Runtime (no hard real-time budget yet).
  Not a credible risk.
- **Action:** MONITOR. Not worth gating the table/string build on the signature too (computing the
  signature cheaply *requires* touching each station anyway, so there is nothing cheaper to
  precompute here without restructuring `LoGetPayloadInfo`'s own per-poll read, which DCS itself
  requires).

#### Aircraft-layer payload cache/API (`collector/cache.py`, `src/api/server.py`)
- **Location:** `PayloadCache`, `GET /payload/latest`.
- **Risk:** None — "latest of one" cache, same shape as the pre-existing `PttCache`/sight-servo
  caches. O(1) read and write, no polling loop added beyond the existing collector/API pattern.
- **Action:** MONITOR (no action).

### Verdict
APPROVED
