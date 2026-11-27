### Performance Review

Batch reviewed: `26bfa514` (BL-B141 single command-seq counter; BL-B117 AI-wheel `on_stop`
reset) + `03b67fcb` (BL-16 M4 SAU channel handover trigger + `step-delay-s` override). Video
game add-on context: Petrobrain is a hobby add-on for the DCS World flight-simulation game;
nothing in this batch controls real hardware. Target: body-layer's per-poll path has no hard
real-time budget yet (that starts once Petrobrain Runtime work is formally scoped), but the poll
loop is still expected not to stall visibly or compound debt — "no per-request allocations on hot
paths" / "offload heavy work asynchronously" from the role brief, applied proportionately to a
small, mostly one-shot batch.

### Findings

#### `_next_command_seq` (body.py, BL-B141)
- **Location:** `_next_command_seq` (renamed from `_next_flight_seq`), called from
  `_apply_ai_pilot_wheel_goal` (goal "set", `hvrt_step`, CBTM one-shot) and `_apply_flight_requests`.
- **Risk:** none credible. It is a plain `runner.command_seq += 1; return runner.command_seq` —
  O(1), no allocation, no I/O. Widening it from one channel to three channels does not change its
  cost shape, only which call sites share the same counter. Python ints are unbounded so no
  overflow concern over a long session.
- **Action:** MONITOR (no action needed; noted only because the diff touches every call site that
  mints a wire `seq`).

#### `controls_to_petrovich_edge` (flight_authority.py, BL-16 M4)
- **Location:** `controls_to_petrovich_edge(prev, new)`, called once per poll from the crew-text
  poll loop in `body.py`, alongside the pre-existing `controls_to_player_edge` call.
- **Risk:** none credible. A two-field string comparison (`prev.fd_mode != "m1" and new.fd_mode ==
  "m1"`), same shape and same call frequency as the existing twin it sits beside. No new
  allocation, no new per-poll state.
- **Action:** MONITOR (no action needed).

#### `step-delay-s: 0` burst on `controls-to-petrovich`/`controls-to-player` (effector_engine.py +
sequence files)
- **Location:** `effector_engine.advance`'s per-row loop, `SequenceFile.step_delay_s` now `0.0`
  for both `controls-to-petrovich.md` and `controls-to-player.md` (4 `SwitchRow`s each).
  `advance`'s due-time check is `if now_sim < cursor.next_due_sim: break`; with `step_delay_s =
  0.0`, `next_due_sim == now_sim` after a successful write, so the strict `<` does **not** break
  — the loop falls through to the next row in the **same** `advance()` call, same poll. Each
  `SwitchRow` that is not already at target ends in a synchronous `client.write_cockpit_switch`
  call — a real LAN HTTP round trip to the aircraft layer (`AircraftLayerClient`), not an
  in-process call.
- **Risk:** this is a genuine, if small, widening of per-poll blocking I/O: up to 4 sequential
  synchronous HTTP writes (plus the one cached `read_args` snapshot at run start, not re-read per
  row — `assumed_writes` lets later rows see earlier same-poll writes without a re-read, so this
  is not a redundant-query problem) land inside one poll's processing, where the previous
  (pre-batch) default spacing (`EFFECTOR_SEQUENCE_STEP_DELAY_S = 1.0s`) guaranteed at most one
  write per trigger per poll. If the aircraft-layer round trip is slow (LAN hiccup, Windows-side
  contention), this poll's wall time grows by roughly 4x a single write's latency instead of 1x,
  stacked on whatever else that poll does (perception, belief, speech drain). Two things bound the
  blast radius: (a) this only fires on the `controls-to-player`/`controls-to-petrovich` triggers,
  both one-shot mode-transition edges, never a steady per-poll cost; (b) `body.py`'s own
  `_wait_for_next_tick` already treats an over-budget poll as tick debt rather than a hang — a slow
  poll here delays the *next* tick, it does not block or crash the loop. This is also exactly what
  was asked for ("for the SAU channel on/off changes, do not wait between them, just turn all on
  right away ... this case is an exception," user direction 2026-11-28) — a deliberate, scoped
  trade of a slightly longer one-shot poll for atomic-feeling handover, not an oversight.
- **Action:** MONITOR. Not NOW: the burst is bounded (4 writes, 2 triggers, both edge-fired not
  per-poll), explicitly user-directed, and the existing tick-debt mechanism already absorbs an
  occasional over-budget poll without cascading. Worth re-checking only if (a) a future sequence
  file reuses `step-delay-s: 0` with a much longer row count, or (b) a flown sortie's own slew/
  effector trace shows a visible stall on a mode-1 take — neither observed yet, so no mitigation
  is proposed now.
- **Mitigation (if ever needed):** cap how many writes a zero-delay trigger may fire in one poll
  (same shape as the existing "one write per trigger per poll" cap `next_due_sim` normally
  enforces, just re-added as an explicit row-count guard for the zero-delay case), or move the
  burst off the poll thread the way `SpeechWorker` already offloads speech pushes. Escalate to
  Architect before building either — both are an architectural change to the engine's per-poll
  contract, not a local fix.

#### AI-wheel `on_stop()` field reset (`ai_pilot_wheel.lua`, BL-B117)
- **Location:** `Export.lua`'s `ai_pilot_wheel.lua` `on_stop()`, which now also clears
  `ai_pilot_parked_active` and six overlay text fields.
- **Risk:** none. Runs once at mission stop, not per-frame — seven extra field assignments on a
  function that already runs at this frequency. Not a hot path by any measure.
- **Action:** MONITOR (no action needed).

### Memory/graph check
`python3 .claude/scripts/memory-search.py` found no prior performance-reviewer memory on
`effector_engine`'s per-poll burst behaviour, the SAU triggers, or the command-seq counter — this
finding (the zero-delay same-poll fall-through) is new and saved to agent memory below.
`.claude/scripts/gq.sh` was not queried further since the relevant design (the tick-debt poll
loop, the engine's "one write per trigger per poll" cap) is already documented in
`body-layer/CLAUDE.md`'s own module-map entries, read directly.

### Verdict
APPROVED — MONITOR
