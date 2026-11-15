### Review Summary

Reviewed BL-16 mode 2, batch A (Stage P-ICS, Stage P0 probe, Stage P1) on
`feature/flight-control`, diff `fde7398e..c0be1771` (21 files), against
`plans/flight-control/plan.md` ("Revised 2026-11-15"), `implementation.md`'s own
four stated deviations, `alignment.md`'s E-P1/E-P6/E-P10, and root/subproject
`CLAUDE.md`.

**Worktree note**: this agent's worktree started at `0fa6c92f` (stale `origin/HEAD`,
not an ancestor of the task's tip). Moved with `git switch -C
worktree-agent-a167d1f2c47f63d89 c0be1771`, confirmed `HEAD` == `c0be1771`, tree
clean, before doing anything else.

**Full read**: every changed file in the diff was read; Export.lua and the probe
script read in full around every new function; both `.venv`s built fresh and all
four commands (`ruff format --check`, `ruff check`, `mypy --strict`, `pytest`) run
in this worktree for both `aircraft-layer` and `body-layer`, plus `luac5.1 -p`/`-l -p`
GETGLOBAL checks on both Lua files and a re-run of `tools/generate_defaults.py`
against the committed `config/defaults.toml`. Two mutation checks performed directly
(see below) rather than trusting the stated test coverage on read alone.

**Structural checks confirmed by grep + mutation, not just reading:**

- **E-P6** (`HDG LOS`/short-right must never be pressed by code): grepped every
  `performClickableAction(30, ...)` / `press(...)` call site in both `Export.lua`
  and the new probe script. `AI_WHEEL_RIGHT`/`WHEEL_RIGHT` (cmd 3002) is declared in
  both files but is only ever opened as a **long hold** (`open_long_hold(WHEEL_RIGHT, t)`
  in the probe's P0-2 row; not called at all yet in production `Export.lua`, which
  only presses `AI_WHEEL_UP`). No call site pairs `3002` with a short/pulse duration
  anywhere. Holds. One caveat below (Optional) about the probe's own generic `press(cmd,
  value)` helper.
- **E-P10** (unpark releases every open press, same frame, drops state, nothing
  resumes on next park): read `run_ai_pilot_wheel`'s `not now_parked` branch directly
  (`Export.lua:2183-2197`) — it fires a release `performClickableAction(..., 0)` and
  clears `ai_wheel_pending_release_t`/`cmd` and every overlay-text field the same
  frame the park signal reads below threshold, and `run_ai_pilot_wheel(t)` is called
  unconditionally every frame (`LuaExportAfterNextFrame`, line ~2589), not gated by
  the 5 Hz export throttle. Holds by construction. Not covered by an automated test
  (see Optional below) — verified by direct code read only, consistent with this
  layer's documented "no automated test for the live Export.lua path" convention.
- **Co-moving-fields construction site** (`ParkedFlightState(`): grepped `src/` and
  `tests/` — exactly one production construction site
  (`belief/ai_pilot_wheel.py:104`, inside `advance_parked_flight_state`), matching the
  plan's own stated grep result. **Mutated it**: removed the `goal=state.goal,
  align_phase=state.align_phase, pre_align_snapshot=state.pre_align_snapshot` carry-
  forward kwargs and reran `test_ai_pilot_wheel.py` —
  `test_later_stage_fields_are_carried_through_unchanged` failed immediately
  (`'none' == 'aligning'` mismatch), confirming the pinning test is load-bearing, not
  vacuous. Restored afterward; `git status --porcelain` on that file is clean.
- **P-ICS OR semantics / old-format tolerance**: `PttSample.intercom`/`radio` are a
  genuine OR across `raw`/`raw_operator`; `from_dict`'s `raw_operator` defaults to
  `0.0` so an old-format line without `"ptt_op"` still parses; `push_ptt_state`'s
  debounce fires on either value moving (verified by reading the Lua and by the
  dedicated `test_ptt_lua.py` harness, which runs the real function through a Lua
  interpreter). `audio-adapter/src/ptt_source.py` and `_handle_ptt_state` (SPU-8 gate)
  are untouched — confirmed by diff.
- **EXPORT_SCRIPT_VERSION / EXPECTED_EXPORT_VERSION pair**: both read `"2026-11-15b"`,
  matching.
- **`defaults.toml` is not stale**: reran `tools/generate_defaults.py` — "up to date",
  no diff against the committed file.
- **Scope**: grepped for every P2+ symbol (`set_parked_heading`, `set_parked_altitude`,
  `set_parked_speed`, `cbtm_align`, `cbtm_align_for_launch`, `recover_to_level`,
  `goal_seq`, `AI_PILOT_SPEED_STEPS_KMH`, `BREAK_AWAY_GAP_S`,
  `HVRT_TRANSLATE_MAX_HOLD_S`) in production `Export.lua`/`belief/ai_pilot_wheel.py` —
  none present outside docstrings/plan cross-references. Nothing from P2 onward is
  built.

### Required Fixes

1. **No aircraft-layer-side test exists for the new `AiPilotWheelState`
   schema/`AiPilotWheelCache`/collector-routing/`GET /ai_pilot_wheel/latest`
   endpoint.** `grep -rln "AiPilotWheel" aircraft-layer/tests/` matches only
   `test_ai_pilot_wheel_lua.py` (the Lua pure-function tests). Every sibling
   per-frame feed this stage explicitly mirrors has a matching Python-side test
   file: `test_sight_servo_api.py` (schema parse/validation errors, cache
   keep-latest, `TestCollectorRouting` — routes ahead of the telemetry
   fallthrough, a malformed line is dropped not raised, no-cache-configured drops
   silently — and the real `GET /sight_servo/latest` endpoint via a live
   `TelemetryAPIServer`), `test_payload_api.py`, and `test_ptt.py`'s own
   `TestPttSample`/`TestPttCache`/`TestCollectorRouting`/`TestPttEndpoint` classes.
   None of this exists for `AiPilotWheelState`/`AiPilotWheelCache`: no test proves
   `AiPilotWheelState.from_dict` rejects a missing `apw_parked_active`, a non-bool
   value, or a non-string/non-null optional field; no test proves the collector's
   new `"apw_parked_active" in data` branch (`collector/server.py:529-544`) routes
   ahead of the telemetry fallthrough or drops a malformed line instead of raising;
   no test proves `GET /ai_pilot_wheel/latest` answers `null` before the first
   sample and the full dict after, through a real `TelemetryAPIServer`. The
   body-layer-side tests (`test_ai_pilot_wheel.py`, `test_aircraft_client.py`) only
   exercise a hand-built dict served by a bare `http.server` handler — they never
   touch `AiPilotWheelState` or the collector at all, so they cannot catch a defect
   in either. `mypy --strict` catches type mismatches but not a wrong routing order,
   a wrong drop-vs-raise decision, or a wrong `None`-before-first-sample posture.
   Add `test_ai_pilot_wheel_api.py` mirroring `test_sight_servo_api.py`'s structure
   (schema/cache/`TestCollectorRouting`/endpoint classes) before this stage is
   considered covered.

### Optional Refinements

- **The probe script's own `press(cmd, value)` (`Export.probe-ai-pilot-wheel.lua:170`)
  is a generic combinator**, exactly the shape the plan's own Implementer note (and
  Finding 2 of the plan-check alignment pass) says to avoid in production code,
  because it is "one typo from pressing" `short-right`. In this probe it is in fact
  never called with `(WHEEL_RIGHT, <short>)` — verified by grep across every call
  site — and the script's own header documents the E-P6 constraint and the
  "skipped: would need short-right, forbidden" fallback language, even though no row
  currently needs it. Not a required fix (a probe script, not production, not voice-
  reachable, and the plan's own invariant is about production Lua), but worth a
  one-line note if this probe's shape is ever copied forward into a production
  stage: the generic `press` helper itself is the thing to not carry into
  `Export.lua`'s real P2-P4 work, not just its current callers.
- **`run_ai_pilot_wheel`'s own integration behaviour (the unpark-releases-and-clears
  branch, E-P10) has no automated test** — only its pure sub-functions
  (`parse_helperai_overlay_fields`, `ai_pilot_park_rising`,
  `ai_pilot_should_nudge_altitude`, etc.) are extracted and run against a real Lua
  interpreter. This matches `aircraft-layer/CLAUDE.md`'s documented convention
  ("`Export.lua` and the live Export.lua↔collector↔API path have no automated
  test... validated manually against a running mission") and the plan's own Stage
  P1 test list, which only asks for the pure functions above — so this is not a
  required fix, just flagged so Flight P1's test card is understood as the actual
  verification of E-P10 in production, not a redundant check.
- **`AI_PILOT_ALTITUDE_TOLERANCE_M` (body-layer tunable, 20.0) and
  `AI_PILOT_NUDGE_EPSILON_M` (Export.lua local, 20.0) are duplicated, not read from
  one source** — Deviation 3 in `implementation.md`. Acceptable for this batch: the
  Architecture decision explicitly keeps all per-frame press timing in Lua until
  Stage P2 wires a goal channel through, no channel exists yet to carry the
  body-layer value into `Export.lua`, and both declarations cross-reference each
  other in their own comments so the duplication is visible rather than silent.
  Flag for Stage P2 to resolve into one source of truth, as the implementer's own
  note already says.
- **`run_ai_pilot_wheel`'s `get_helperai_indication()`/`list_indication(6)` call and
  its `parse_helperai_overlay_fields` recursive-descent parse run every DCS frame
  while parked, unthrottled** (`Export.lua:2199-2208`, called from
  `LuaExportAfterNextFrame` ahead of the 5 Hz `last_export_t` gate, same placement
  as `sight_servo_tick`). This is a second read+parse of the same underlying
  `list_indication(6)` dump the existing 5 Hz `push_petrovich_indication` path
  already does each export tick — `implementation.md`'s own "Notable Discoveries"
  flags this as the plan's own stated risk, not a new finding, but it is now real,
  shipped code rather than a plan description. Hand to performance-reviewer: is a
  per-DCS-frame (not per-5Hz-tick) string-split/recursive-table-build over a
  variable-length text dump, while parked, an acceptable per-frame cost on the
  Lua side, or does it want its own throttle (e.g. only re-parse every N frames, or
  only when the raw string has changed)?

### Items to hand to performance-reviewer / security

- **Performance**: the unthrottled per-frame `list_indication(6)` parse noted above
  (`run_ai_pilot_wheel`, Export.lua) — a second full parse of the same raw dump the
  5 Hz telemetry path already parses, now running every render frame rather than at
  5 Hz, for the duration of every parked flight segment.
- **Security**: nothing new surfaced. The new write path
  (`GetDevice(30):performClickableAction(AI_WHEEL_UP, ...)`) reuses the existing
  device-30 write mechanism BL-6's search wheel already established; no new network
  surface, no new external input parsing beyond the existing `list_indication`
  text-parsing pattern this layer already uses elsewhere.

### Verdict

CHANGES REQUIRED — one required fix (Required Fix 1, missing aircraft-layer-side
test coverage for the new schema/cache/collector-routing/endpoint). Everything else
checked (E-P1, E-P6, E-P10, P-ICS OR semantics, scope boundary, tuning render,
construction-site count, version pair) holds under direct verification, not just
reading.

### Review Confidence

Full read of every changed file; mechanical checks (ruff/mypy/pytest/luac) run
directly in this worktree for both touched subprojects, not taken from the
implementer's report; two mutation checks performed (construction-site
carry-forward, confirmed via test failure/restore) rather than accepted on read
alone.
