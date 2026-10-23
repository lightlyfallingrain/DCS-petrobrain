### Performance Review

Batch: `feature/switch-reference-values`, tip `8fd8fc38b8500b0ded9744c9708a6e163a95e5be`
(diff against `27c19054`). Covers the `values`/`helper_args` enrichment to the effector registry
generator/renderers, and the `mission-start`/`mission-start-in-air` trigger follow-on in
`logger.py`'s crew poll loop (pending flags, `t_sim` baseline `!=` check, the wall-clock bounded
fallback `MISSION_START_RESOLVE_FALLBACK_S`).

No hard real-time budget applies in this phase (Petrobrain Runtime work has not started); the
relevant target is simply "no added per-poll cost on the 1 Hz-default crew poll loop" and
"offline tools stay offline."

### Findings

#### Offline tools (generator + two renderers) — confirmed not hot path

- **Location:** `body-layer/tools/generate_effector_registry.py`,
  `tools/render_switch_reference.py`, `tools/render_triggers.py`.
- **Risk:** none. Grepped `body-layer/src` for imports of all three module names — zero hits.
  `CLAUDE.md`'s own text calls them "dev tools, not run at body-layer startup," run manually on
  the Windows DCS machine (generator, Stage 0) or by a human/CI regenerating a `.md` file. The
  bulk of this diff (717 lines in `effectors-raw/mi-24p.toml`, 1357 in `switch-reference.md`) is
  generated data, touched zero times at runtime.
- **Action:** none needed. Confirmed, not assumed.

#### `EffectorTrigger`/`TRIGGER_INFO` merge in `effector_sequences.py`

- **Location:** module-level `TRIGGER_INFO: Final[Mapping[...]]` dict literal and
  `KNOWN_TRIGGERS: Final[frozenset[str]] = frozenset(t.value for t in EffectorTrigger)`.
- **Risk:** none. Both built once at import time (7 enum members, 7 dict entries) — not
  per-poll, not per-request. `effector_engine.py`'s own `EffectorTrigger` definition was deleted
  in favour of a re-export (`__all__ = ["EffectorTrigger"]`); this removes a class body at import
  time and adds nothing at runtime.
- **Action:** none.

#### Mission-start resolution added to `_run_crew_text_poll_loop`

- **Location:** `logger.py`, inside the per-poll block, directly after
  `crew_console.sight_ready = is_sight_ready` and before the `TAKEOFF` edge check.
- **Steady-state cost (the overwhelming majority of polls, when no mission-start resolution is
  pending):** one `or` of two already-resident `bool` fields
  (`runner.pending_mission_start_fire or runner.pending_mission_start_in_air_check`), both
  `False`. No allocation, no branch taken beyond that, no I/O. This is the entire added cost on
  every ordinary poll once a mission has stabilised.
- **Cost while a mission-start window is actually resolving** (armed by `_check_for_new_mission`
  on a genuine DCS mission (re)start — i.e. once per mission start/restart, not once per poll in
  steady state): one float comparison (`last_ownship_state.t_sim != baseline`), one
  `time.monotonic()` call, and conditionally a call to the already-existing `fire_effector_trigger`
  (same function the pre-existing `TAKEOFF` path already calls on every real takeoff). No new
  HTTP call, no new per-poll allocation (`fire_effector_trigger`'s own cost is unchanged from
  before this diff — it is reused, not added), no blocking. `logger.warning(...)` only executes on
  the pathological fallback path (restart lands at `t_sim≈0` *and* the first fresh sample
  coincides exactly with the baseline) — by the plan's own account, self-healing and not
  reachable by any shipped sequence file this cut.
- **Duration of the resolving window:** normally resolves on the very next poll (well under a
  second, per the plan's "Notable Discoveries"); bounded above by
  `MISSION_START_RESOLVE_FALLBACK_S` (default 30 s, range 5–120 s) specifically so a pathological
  coincidence cannot hold the window open indefinitely. The existing fast-poll-interval test
  (`test_stale_telemetry_at_mission_restart_does_not_decide_airborne`) exercises ~20 polls of the
  resolving branch at a 0.01 s interval without issue — i.e. the branch's own per-poll cost was
  already measured by the implementer's test suite to not matter at a far tighter interval than
  production's 1.0 s default.
- **Why wall-clock, not a poll count, and why that's the right instrument:** matches the already-
  known project fact (memory: `project_poll_loop_has_no_5hz_spec.md`) that the crew poll loop has
  no fixed-rate spec — it's a 1.0 s fixed-delay sleep-after-work loop, and test harnesses run it at
  a different interval entirely. A poll-count threshold would couple the fallback's real-world
  timing to `--poll-interval-s`, which is exactly the trap this fix's own "why wall-clock" section
  documents having hit and avoided.
- **Action:** none required. Monitor only in the sense that any future change to
  `MISSION_START_RESOLVE_FALLBACK_S`'s bounds, or a change making `t_sim` itself non-stable across
  cache reads (flagged by the implementer's own "Notable Discoveries"), should re-check this
  reasoning — not a present risk.

#### Pre-existing poll-loop HTTP shape — not touched, not worsened

- Checked against known pre-existing risk (memory: `project_body_layer_poll_loop_serial_unpooled_gets.md`,
  "6-8 serial, unpooled HTTP GETs per 1Hz poll cycle") and the gated-HTTP-call-ordering lesson
  (`feedback_gated_http_call_before_the_gate.md`, an unconditional-before-flag-check GET). Neither
  pattern recurs here: the new code reads/writes only in-process runner fields and calls
  `time.monotonic()`; it introduces no HTTP call of its own, gated or otherwise. `logger.py`'s diff
  for this batch adds zero new client calls (confirmed by reading the full diff, not just
  grepping for `.get(`/`.post(`).
- **Action:** none. Named here so this batch's review doesn't need re-deriving that this
  pre-existing shape exists and isn't this diff's concern.

### Verdict
APPROVED
