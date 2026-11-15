### Implementation Summary

BL-16 mode 2, batch A: Stage P-ICS, Stage P0 (probe), Stage P1 — from
`plans/flight-control/plan.md`, "Revised 2026-11-15". Nothing from P2
onward. Branch rebased onto `fde7398e` at start (the agent worktree had
been created from a stale `origin/HEAD`); committed as three logical
steps on `worktree-agent-a315fa41ebe81b78a`.

### Files Changed

**Stage P-ICS**
- `aircraft-layer/dcs-export/Export.lua` — `push_ptt_state` now reads arg
  856 (`ARG_OPERATOR_PTT`) alongside 738, debounces on either value
  moving, sends `"ptt_op"` on the wire. `EXPORT_SCRIPT_VERSION` bumped to
  `2026-11-15` (then `2026-11-15b` for Stage P1's additive line).
- `aircraft-layer/src/schema/ptt.py` — `PttSample` gains `raw_operator`
  (default `0.0`, old-format tolerant); `intercom`/`radio` are now an OR
  across both raw values; new `_last_seat()` diagnostic, surfaced in
  `to_api_dict` as `"last_seat"`.
- `aircraft-layer/tests/test_ptt.py` — new truth-table/operator-only/
  both-moved/old-format tests; **one existing exact-dict-equality
  assertion updated** (`test_serves_the_raw_value_and_both_predicates`)
  to include the new `"last_seat"` key — required by the schema change
  the plan calls for, not an unrelated test edit.
- `aircraft-layer/tests/test_ptt_lua.py` (new) — `push_ptt_state`'s
  debounce-on-either-change run against a real Lua interpreter.

**Stage P0**
- `aircraft-layer/dcs-export/Export.probe-ai-pilot-wheel.lua` (new) —
  self-contained probe, waits for the park signal's rising edge, then
  runs P0-6 (park-sink trace + nudge), P0-1 (overlay closed/open), P0-2
  (one 0.7s held press per outer ring position in FLT), P0-3 (speed
  tap sequence), P0-4 (press-release-to-readback latency), P0-5 (centre
  ALT REF toggle), P0-7 (FLT→HVR speed criterion). Aborts and releases
  any open press the frame the stick unparks. Never presses short-right.

**Stage P1**
- `aircraft-layer/dcs-export/Export.lua` — `run_ai_pilot_wheel(t)` (every
  frame, beside `sight_servo_tick`): parses `list_indication(6)` into
  `mode_text`/`course_text`/`alt_text`/`alt_add_text`/`speed_text`
  (`parse_helperai_overlay_fields`, a second Lua-side implementation of
  the same algorithm `petrovich_indication.py`'s Python parser uses, not
  a reuse — the per-frame loop needs it without a round trip); detects
  the park-rising edge (arg 852/952, `ai_pilot_park_rising`); on rising,
  nudges altitude once if the AI's held value already equals the
  aircraft's actual altitude (`ai_pilot_should_nudge_altitude`, matched
  against the displayed R/B reference, `ai_pilot_actual_altitude_m`).
  `push_ai_pilot_wheel_state(t)` sends the status at 5 Hz, wire key
  `"apw_parked_active"`. **No shared `press(direction, duration)` helper**
  — the one press site (`ai_pilot_press_altitude_up_long_hold`) is
  hard-coded to `AI_WHEEL_UP`, per the plan's E-P6 note.
- `aircraft-layer/src/schema/ai_pilot_wheel.py` (new) — `AiPilotWheelState`,
  mirroring `sight_servo.py`'s shape exactly.
- `aircraft-layer/src/schema/__init__.py` — re-exports the new schema.
- `aircraft-layer/src/collector/cache.py` — `AiPilotWheelCache`.
- `aircraft-layer/src/collector/server.py` — routes `"apw_parked_active"`
  lines; `EXPECTED_EXPORT_VERSION` bumped to match.
- `aircraft-layer/src/collector/__main__.py` — wires the new cache into
  `CollectorServer`/`TelemetryAPIServer`.
- `aircraft-layer/src/api/server.py` — `GET /ai_pilot_wheel/latest`.
- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py` (new) — the pure Lua
  functions (overlay parse, park-rising, altitude-nudge) run against a
  real interpreter and checked against the overlay research note's own
  observed text shapes.
- `body-layer/src/belief/ai_pilot_wheel.py` (new) — `ParkedFlightState`
  (Stage P1's own fields, plus P2-P4's `goal`/`align_phase`/
  `pre_align_snapshot` declared now per the plan's own instruction) and
  `advance_parked_flight_state`. New tunable `AI_PILOT_ALTITUDE_
  TOLERANCE_M` (20.0, `agreed-guess`).
- `body-layer/src/aircraft_client.py` — `get_ai_pilot_wheel_latest`.
- `body-layer/src/body.py` — `ConsolePerceptionRunner.parked_flight_state`
  field; advanced in the poll loop beside `guidance_unit_state`'s own
  refresh, inside a `try`/`except AircraftLayerError`.
- `body-layer/config/defaults.toml` — regenerated.
- `body-layer/tests/test_ai_pilot_wheel.py` (new) — `advance_parked_
  flight_state` against a real loopback `AircraftLayerClient`, per the
  project's stated "no mocked urllib" test convention.
- `body-layer/tests/test_aircraft_client.py` — `get_ai_pilot_wheel_latest`
  round-trip + unreachable-host tests.
- `body-layer/tests/test_body.py` — **`FakeConsoleAircraftClient` gained
  `get_ai_pilot_wheel_latest`** (returns `self.ai_pilot_wheel_state`,
  default `None`) — required because the poll loop now calls it
  unconditionally; 21 "real poll loop" tests failed without this fix on
  the first full-suite run, caught and fixed in this same batch.
- `plans/flight-control/plan.md` — added the Implementer's grep result
  (one construction site, no `apw.` Lua table assignments — individual
  named locals used instead, documented inline why) just below the
  Co-moving Fields table, per the plan's own instruction.

### Tests Added

- `aircraft-layer/tests/test_ptt.py` — old-format line parses, `ptt_op`
  type validation, intercom truth table across both seats, operator-only
  opens capture, both-seats-same-frame, `_last_seat` naming.
- `aircraft-layer/tests/test_ptt_lua.py` — debounce on pilot-only/
  operator-only/both/neither moving, first-frame-always-sends, a wobble
  within epsilon not resending.
- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py` — overlay parse
  (FLT/baro-reference/childless-block/nested-block/HVRT text shapes),
  park-rising edge (unparked/crossing/already-parked/pedals-alone/nil),
  altitude-nudge (equal/within-tolerance/real-difference/missing-reading),
  `ai_pilot_parse_altitude_text`, `ai_pilot_actual_altitude_m`.
- `body-layer/tests/test_ai_pilot_wheel.py` — sample parses into state,
  no-sample-yet leaves state unchanged, unparked/empty fields round-trip
  as `None`, a non-numeric overlay field degrades to `None` not an error,
  later-stage fields (`goal`/`align_phase`) carried through unchanged.
- `body-layer/tests/test_aircraft_client.py` — `get_ai_pilot_wheel_latest`
  parses, raises on unreachable host.

### Checks

**aircraft-layer/**
- `ruff format`: pass (3 files auto-reformatted on first run, re-checked clean)
- `ruff check`: pass
- `mypy --strict` (`cd aircraft-layer && .venv/bin/mypy src`): pass, no issues (27 source files)
- `pytest`: 733 passed
- `luac5.1 -p` on both new/modified Lua files: pass
- `luac5.1 -l -p` GETGLOBAL check on both files: only genuine DCS/stdlib
  globals, no accidental-local bug

**body-layer/**
- `ruff format`: pass (1 file auto-reformatted, re-checked clean)
- `ruff check`: pass
- `mypy --strict` (`cd body-layer && .venv/bin/mypy src`): pass, no issues (83 source files)
- `pytest`: 3281 passed, 4 xfailed (pre-existing, unrelated)

Both subprojects' `.venv` did not exist in this fresh agent worktree and
were created (`python3 -m venv .venv` + `pip install pytest mypy ruff`
plus `pip install -e .` for body-layer's `pyproj`/`numpy`).

### Notable Discoveries

- **The agent worktree was created from a stale `origin/HEAD`, not the
  task's stated tip.** Per the dispatching instructions, moved the branch
  to `fde7398e` with `git switch -C` before any work — confirmed HEAD
  matched and the tree was clean first.
- **`FakeConsoleAircraftClient`'s missing method was caught by running
  the full suite, not by the targeted new tests.** The 21 failures were
  all pre-existing tests exercising "the real poll loop" through
  `body.py`'s `_run_crew_text_poll_loop`, which now calls `advance_
  parked_flight_state` unconditionally whenever a real ownship state
  exists — exactly the scope-widening the role's "verify state, not the
  account of it" guidance warns about. Fixed in the same batch rather
  than filed as a follow-up.
- **The plan's Co-moving Fields table's `apw.mode`/`apw.press` notation
  is conceptual, not literal Lua syntax.** This implementation uses
  individual named locals (`ai_pilot_parked_active`, `ai_pilot_mode_text`,
  …) rather than a single `apw` table, for the same "a local referenced
  above its own declaration compiles as a global" reason `push_ptt_state`
  was once broken by (project memory: `feedback_export_lua_new_helper_
  can_make_an_earlier_function_stale`) — assembling one table from several
  values computed at different points in the frame would risk exactly
  that. Noted in the plan itself so P2-P4 don't read the table's notation
  as a literal requirement.
- **`AI_PILOT_ALTITUDE_TOLERANCE_M` (body-layer tunable) and
  `AI_PILOT_NUDGE_EPSILON_M` (Export.lua local) are the same number (20.0)
  held in two places, not one.** The plan's own Stage P1 instruction says
  to declare the tunable now "since P1's nudge-if-equal uses it," but no
  goal-message channel exists yet to actually carry a body-layer value
  into `Export.lua` (the Architecture decision keeps all per-frame press
  timing in Lua until Stage P2). Flagging this explicitly per the
  "lo/hi must be AST literals... if you must duplicate a value, name its
  source in a comment" guidance — both declarations cross-reference each
  other in their own comments, but Stage P2 should resolve which one is
  authoritative once a real channel exists, rather than leaving both to
  drift independently.
- **`AiPilotWheelState.held_altitude_ref`/`ParkedFlightState.held_
  altitude_ref` round-trip `None` for "reference unknown this frame"**,
  distinct from the string `"R"`/`"B"` — no third value invented for
  "overlay not populated" vs. "overlay populated but blank," since the
  Lua-side parser already collapses both to `None` (the same "absence
  only" convention `parse_helperai_overlay_fields`'s childless-block case
  uses).
- **`list_indication(HELPERAI_DEVICE_ID)`'s dual meaning (Petrovich's own
  detection text vs. the AI-pilot overlay while parked) is read twice per
  frame while parked**: once by the existing 5 Hz `push_petrovich_
  indication` path (unchanged, still pushes whatever is there) and once by
  `run_ai_pilot_wheel`'s own `get_helperai_indication()` call, every
  frame. Both calls hit the same underlying DCS function; this is the
  plan's own stated Risk ("a new flattening on the same raw dump"), not a
  new finding — recorded here only because the two call sites are now
  real code, not a plan description.

### Perf fix (`plans/flight-control/perf-batch-a.md`, NEEDS MITIGATION)

Implemented the mitigation exactly as specified. `run_ai_pilot_wheel(t)`
(still called every frame) now keeps only: the open-press release-deadline
check, park-signal edge detection (`stick_park`/`pedals_park` arg reads),
and the unpark branch (clears overlay fields, drops any open press, and
now also clears the new `ai_pilot_pending_nudge` flag — E-P10 extended to
cover the deferred nudge, not just the open press). On a rising edge it
only sets `ai_pilot_pending_nudge = true`; it no longer reads or parses
`list_indication(HELPERAI_DEVICE_ID)` itself.

A new function, `update_ai_pilot_wheel_overlay(raw, t)`, carries the
overlay parse and the altitude-nudge decision that used to live in
`run_ai_pilot_wheel`. It is called from the 5 Hz export block in
`LuaExportAfterNextFrame`, which now reads `list_indication
(HELPERAI_DEVICE_ID)` exactly **once** per tick into a local
(`helperai_raw`) — the same read the existing `encode_petrovich_
indication_line` consumer further down the function now reuses instead
of calling `get_helperai_indication()` a second time, closing the "same
dump read twice" finding directly above. `update_ai_pilot_wheel_overlay`
no-ops while unparked or before a dump exists; while parked, it refreshes
the five overlay text fields every tick and, if a nudge is armed,
resolves it from that tick's freshly-parsed `alt_text`/`alt_add_text`
(deferring the one-shot nudge by at most one 5 Hz tick, ≤ 200 ms, per the
perf report's own accepted slack) and clears the flag whether or not it
fired.

No wire-format change (same `apw_*` fields, same semantics, same
cadence for `push_ai_pilot_wheel_state`) — `EXPORT_SCRIPT_VERSION`/
`EXPECTED_EXPORT_VERSION` left at `"2026-11-15b"`, not bumped, since the
version-bump convention is keyed to the wire format a collector parses,
which did not change.

Left the perf report's P2 MONITOR item as a comment at the 5 Hz call
site (`update_ai_pilot_wheel_overlay`'s own docstring) rather than code:
P2's readback-release check should default to riding this same 5 Hz tick
rather than reintroducing a per-frame `list_indication(6)` read, unless a
live P2 test shows 5 Hz is not fast enough for that goal's tolerance.

Added two Lua integration tests (`test_ai_pilot_wheel_lua.py`,
`TestNudgeDrivenFromCachedParse`) against a `GetDevice` mock, following
`test_sight_servo_lua.py`'s own established pattern for this: one proves
the press only fires once `update_ai_pilot_wheel_overlay` resolves the
armed flag (not on the rising frame, not on a second tick after it has
already fired once), the other proves unparking before the next tick
clears the armed flag so a stale parse never fires a nudge for a park
that already ended. Verified both are load-bearing, not tautological, by
mutation: removed the unpark branch's new `ai_pilot_pending_nudge = false`
line, confirmed `test_unpark_before_the_next_tick_clears_the_pending_
nudge` failed for the stated reason (`pending_after_unpark` read back
`"true"`), restored the line, confirmed the file's checksum matched the
pre-mutation value exactly (not just "tests pass again").
