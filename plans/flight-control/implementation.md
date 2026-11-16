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

---

## Revision 2026-11-16 — takeover and stabilisation (replaces Batch A's Stage P1)

Implements `plans/flight-control/plan.md`, "Revised 2026-11-16 — takeover after the Batch A
flights" → "Revised Stage P1 — takeover and stabilisation" and its "Amended 2026-11-16"
sub-section, in full. Worktree started at `993be9a5` (after a mid-task tip correction from
58330556 to 993be9a5 — docs-only `main` merge; `git merge --ff-only` from a clean, ancestor HEAD,
no conflict).

### Files Changed

- `aircraft-layer/dcs-export/Export.lua` — the whole takeover/correction state machine, replacing
  Batch A's one-shot nudge outright (plan point 8):
  - **Detection (point 1)**: `ai_pilot_park_rising(prev_parked, stick_park_arg)` dropped its
    `pedals_park_arg` parameter — arg 952 is no longer read for detection (it is arg 852's own
    mirror, not a second park sensor), kept only as a diagnostic value on the status push.
  - **Handover snapshot (amendment point 1)**: on the rising edge, `LoGetAltitudeAboveSeaLevel()`
    is read and stored as `ai_pilot_takeover.handover_altitude_m` in the same frame — this, not
    the first post-open read, is the correction goal throughout.
  - **Toggle + open (points 2/3)**: `AI_PILOT_REFERENCE_TOGGLE_DELAY_S` (0.5 s) after the rising
    edge, a same-frame blind centre tap (menu closed) then an immediate menu-open tap, both via
    one shared `ai_pilot_tap30(cmd)` helper (see "Local-count ceiling" below for why one helper,
    not two). The command menu's keep-open/reopen check (`MODE_READ_SETTLE_S` = 1.0 s settle
    window on an all-`nil` overlay read) runs every 5 Hz tick for as long as the belief
    `ai_pilot_takeover.menu_open` is true, independent of the takeover sequence's own stage.
  - **Correction decision (amendment point 5)**: `ai_pilot_decide_correction`, run once the first
    post-open overlay read lands. `"none"` if the held altitude is already within
    `AI_PILOT_ALT_TOLERANCE_M` of the handover snapshot. Otherwise: **quick path** (eligibility
    `ai_pilot_quick_path_eligible(agl_m)`, `AI_PILOT_QUICK_PATH_MAX_AGL_M` = 700.0 m) issues a
    `SHORT_PULSE_S` (0.15 s) centre pulse, reads the reference one tick later
    (`ai_pilot_takeover.correction_substage == "quick_read1"`); if it now reads `"R"`, a second
    pulse (`"quick_read2"`). **Superseded by the 2026-11-16 review fix below**: the second pulse's
    resolution is re-checked against tolerance rather than trusted outright. If it still reads
    `"B"` after the first pulse, falls back to the **two-phase hold**
    (`ai_pilot_begin_hold_phase`): phase 1 chases the aircraft's own live altitude (re-read every
    tick via `ai_pilot_actual_altitude_m` against whichever reference is currently displayed) to
    stop the climb, phase 2 (entered once phase 1 releases or is skipped) chases the fixed
    handover snapshot. Either phase is skipped outright if already within tolerance.
    `ai_pilot_check_hold_convergence` releases the instant the held value reads within tolerance
    of that phase's own target.
  - **Press shapes**: `ai_pilot_correction_direction(held_m, target_m)` (pure, replaces
    `ai_pilot_should_nudge_altitude` outright per plan point 8) returns `AI_WHEEL_UP`/`AI_WHEEL_
    DOWN`/`nil`; `ai_pilot_open_hold(cmd, t)` opens a hold in the decided direction and arms
    `AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S` (60 s) as a safety ceiling on the same shared
    per-frame deadline slot (`ai_wheel_pending_release_t`/`ai_wheel_pending_cmd`) the quick-path
    pulses also use — one slot is enough since at most one timed press is ever open at a time.
    Never a generic `press(direction, duration)` entry point (point 9/E-P6): `ai_pilot_open_hold`'s
    `cmd` is restricted to the two altitude directions by its one caller, and no path can reach
    `AI_WHEEL_LEFT`/`AI_WHEEL_RIGHT` (removed, see below) or `WHEEL_RIGHT`.
  - **Unpark (point 6)**: `run_ai_pilot_wheel`'s unpark branch releases any open press the same
    frame, closes the command menu if this sequence opened it, and drops every takeover field
    (`ai_pilot_takeover` table reset wholesale) — nothing resumes on the next park.
  - **Status push (point 7)**: `push_ai_pilot_wheel_state` gained `apw_arg852`/`apw_arg952`
    (raw diagnostic park-arg readings) and `apw_takeover_stage`/`apw_correction_path`.
  - `EXPORT_SCRIPT_VERSION` bumped `"2026-11-15b"` → `"2026-11-16"` — non-additive (`apw_
    last_press`'s own vocabulary changed; a collector built against the old shape would
    misinterpret it), per this file's own version-bump convention, not just because fields were
    added.
- `aircraft-layer/src/collector/server.py` — `EXPECTED_EXPORT_VERSION` bumped to match, same
  commit.
- `aircraft-layer/src/schema/ai_pilot_wheel.py` — `AiPilotWheelState` gained `arg_852`/`arg_952`
  (`float | None`, validated as number-or-null) and `takeover_stage`/`correction_path`
  (`str | None`); all four optional on the wire (missing → `None`), so an older `Export.lua`'s
  line still parses.
- `body-layer/src/belief/ai_pilot_wheel.py` — `ParkedFlightState` gained `raw_arg_852`/
  `raw_arg_952`/`takeover_stage`/`correction_path` as read-only diagnostic mirrors (plan point 7:
  "and any body-layer consumer that mirrors the wire"); `advance_parked_flight_state` parses them
  via a new `_as_optional_float` (JSON numbers, not numeric strings — `bool` excluded explicitly
  since `isinstance(True, int)` is true in Python). Pruned the module's own stale comment
  reference to `AI_PILOT_NUDGE_EPSILON_M` (renamed in `Export.lua`) while touching this file, per
  "Prune the comment you are standing next to."
- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py` — rewritten. Removed: the pedals-alone-triggers
  rising-edge test (952 is no longer read for detection) and every test of
  `ai_pilot_should_nudge_altitude`/the old one-shot-nudge integration scenario (both gone from
  production, per plan point 8). Added: `ai_pilot_correction_direction`/`ai_pilot_quick_path_
  eligible` pure-function tests, and a `TestTakeoverSequence` class exercising the full state
  machine end to end against the `GetDevice` mock (detect → toggle → open → each of the three
  correction paths → unpark), mirroring the takeover rehearsal probe's own steps but against
  production code.
- `aircraft-layer/tests/test_ai_pilot_wheel_api.py` — `AiPilotWheelState` construction sites and
  expected `to_api_dict()`/endpoint-response dicts extended with the four new fields; added a
  parse-error test for a non-number `apw_arg852`.
- `body-layer/tests/test_ai_pilot_wheel.py` — added a test confirming the four new fields parse
  through when present and default to `None` when absent from an older-shaped line, plus a
  `bool`-is-not-a-number regression test for `_as_optional_float`.

### Tests Added

- `TestAiPilotCorrectionDirection` (4 tests) — within tolerance → `nil`; above tolerance, held
  above/below target → `AI_WHEEL_DOWN`/`AI_WHEEL_UP`; a missing reading on either side → `nil`.
- `TestAiPilotQuickPathEligible` (3 tests) — below/at-or-above `AI_PILOT_QUICK_PATH_MAX_AGL_M`;
  unreadable AGL.
- `TestAiPilotParkRising` — updated for the dropped `pedals_park_arg` parameter; a `nil` reading
  is not parked (the old pedals-alone test removed, since pedals alone can no longer trigger
  anything).
- `TestTakeoverSequence` (7 tests): detect→toggle→open resolving to `"none"`; the two-phase hold
  end to end (phase 1 against live altitude, phase 2 against the handover snapshot, both via
  convergence-driven release); phase 1 skipped when already within tolerance of live altitude
  (still needing phase 2); the quick path succeeding (two pulses, never opens `AI_WHEEL_UP`/
  `DOWN`); the quick path falling back to the hold when the first pulse is refused; the menu
  keep-open reopening only after the settle window elapses, not on the first stale tick;
  unpark releasing an open hold, closing the menu, and dropping all state immediately, with a
  stale post-unpark read confirmed to no-op.
- `test_to_api_dict_carries_every_field`/`test_serves_the_latest_sample` (aircraft-layer) and
  `test_the_takeover_diagnostic_fields_are_parsed_through`/`test_a_boolean_arg_value_is_never_
  treated_as_a_number` (body-layer) — the four new fields round-trip correctly and a malformed
  `bool` on `apw_arg852` is never silently read back as `1.0`/`0.0`.

### Checks

**aircraft-layer/**
- `luac5.1 -p aircraft-layer/dcs-export/Export.lua`: pass
- `ruff format --check src tests`: pass (79 files)
- `ruff check src tests`: pass
- `mypy src` (from inside `aircraft-layer/`): pass, 27 source files
- `pytest tests -q`: pass, 765 passed

**body-layer/**
- `ruff format --check src tests`: pass (204 files)
- `ruff check src tests`: pass
- `mypy src` (from inside `body-layer/`): pass, 83 source files
- `pytest tests -q`: pass, 3284 passed, 4 xfailed (pre-existing, unrelated)

### Notable Discoveries

- **`Export.lua`'s main chunk hit Lua 5.1's hard 200-live-local ceiling** (`luac5.1 -p`: "main
  function has more than 200 local variables") once this revision's dozen-odd new takeover/
  correction fields were added as separate module-level locals (the file was already at 193 top-
  level locals before this change). Resolved by: (1) grouping the new takeover/correction state
  into **one** table local, `ai_pilot_takeover` — a deliberate, flagged departure from this file's
  own documented "individual locals, no `apw` table" convention (every field initialised in one
  place, so there is no forward-reference/hoisting risk, the concern that convention was guarding
  against); (2) merging `ai_pilot_open_hold_up`/`ai_pilot_open_hold_down` into one `ai_pilot_
  open_hold(cmd, t)` and `ai_pilot_toggle_reference_blind`/`ai_pilot_toggle_menu` into one
  `ai_pilot_tap30(cmd)`, both restricted-use, not the forbidden generic `press(direction,
  duration)` shape; (3) inlining the two-call-site centre-pulse press instead of its own function;
  (4) removing the now-genuinely-dead `LONG_PRESS_HOLD_S` constant (its one user, the old one-shot
  nudge function, was removed by this same revision) and the unused, reserved-for-a-later-stage
  `AI_WHEEL_LEFT`/`AI_WHEEL_RIGHT` declarations (a later stage that needs heading left/right
  declares them when it does). Final count: exactly 200. **This is a real constraint on every
  future stage of this plan (P2–P6)** — any new module-level local in `Export.lua` from here on
  should budget against it, not assume headroom.
- **Three of the new Lua constants** (`AI_PILOT_REFERENCE_TOGGLE_DELAY_S`, `MODE_READ_SETTLE_S`,
  `SHORT_PULSE_S`, `AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S`, `AI_PILOT_QUICK_PATH_MAX_AGL_M` —
  five, not three) are behaviour-affecting by the root `CLAUDE.md` test (a different value changes
  what Petrovich does: whether/when he presses, which correction path he takes) but have no
  tuning mechanism available in `Export.lua`. Declared as ordinary named locals with explanatory
  comments, per root `CLAUDE.md`'s own instruction for outside body-layer; flagged here rather
  than improvising a second loader.
- **A floating-point exact-equality trap in my own Lua integration tests**, not production code:
  `0.8 + 0.15` does not reliably equal the literal `0.95` in Lua's double-precision arithmetic, so
  a test driving the per-frame deadline-release check with `run_ai_pilot_wheel(0.95)` sometimes
  missed the release by one ULP. Fixed by calling one tick later (`0.96`) rather than on the exact
  nominal deadline — realistic anyway, since production is driven by DCS's own frame clock, never
  landing exactly on a computed deadline.
- **One Implementer decision not explicitly in the plan**: whether the quick path's second pulse
  (`"quick_read2"`) re-verifies tolerance before resolving. The phrase "then go on to step 6's
  checks" cited in an earlier version of this note as the plan's own wording was in fact from the
  main loop's dispatch brief, not `plan.md` — grepped and not found there; the plan is silent on
  this point. Implemented at the time with no tolerance re-check, matching the probe's own measured
  evidence that a second baro switch recalculates a correct target. **Fixed in the 2026-11-16
  review round** (below): the second pulse now re-checks tolerance and falls through to the
  two-phase hold if still wrong, the same shape the first pulse's own refusal already used.
- **Phase 1's hold-release comparison reuses `ai_pilot_actual_altitude_m`** (compare held against
  whichever reference the overlay currently displays) rather than hard-coding MSL, even though the
  reference is expected to stay `"B"` throughout a hold (the quick path, the only path that ever
  touches the reference, always resolves back to `"B"` before falling through to a hold). Not
  defended by an assertion that the reference is `"B"` — if it is ever something else mid-hold,
  phase 2's comparison against the handover snapshot (always MSL) would silently mix units. No
  case has been observed; flagged as the same posture as the plan's own "the AI always starts on
  radar" residual risk, not re-opened as a question.

---

## Review-fix round, 2026-11-16 (`plans/flight-control/review-takeover.md`, NEEDS REVISION)

Both required fixes, plus the main loop's own timing decision (not a review requirement).

### Files Changed

- `aircraft-layer/dcs-export/Export.lua`:
  - **Required fix 1**: `update_ai_pilot_wheel_overlay`'s `correction_substage == "quick_read2"`
    branch now re-checks the held altitude against `ai_pilot_takeover.handover_altitude_m` within
    `AI_PILOT_ALT_TOLERANCE_M` before resolving. Within tolerance → unchanged (`stage = nil`,
    `correction_path` stays `"quick"`). Outside tolerance → `correction_path = "hold"`, falls
    through to `ai_pilot_begin_hold_phase`, the same shape `quick_read1`'s own refusal already
    used. A missing reading is treated as "nothing to correct" (`ai_pilot_correction_direction`'s
    own stated convention, already used by `ai_pilot_decide_correction`'s first check), not a new
    rule invented for this branch.
  - **Main-loop timing decision (not a review requirement)**: restored the ~0.5 s gap the rehearsal
    probe actually flew between the blind centre tap and the menu-open tap (centre at +0.5 s, menu
    at +1.0 s after takeover), replacing the same-frame fall-through. New constant
    `AI_PILOT_MENU_OPEN_DELAY_S` (0.5) lives as a field on the existing `ai_pilot_takeover` table,
    not a new top-level local — the file is already at Lua 5.1's 200-live-local ceiling with zero
    headroom (review, Optional Refinements), and a table field costs no main-chunk local. New state
    field `ai_pilot_takeover.menu_open_at_t` (the deadline), cleared on unpark alongside the other
    sequence fields.
  - **Optional refinement, applied** (trivial, no local cost): `ai_pilot_check_hold_convergence`'s
    phase1→phase2 transition now calls `ai_pilot_begin_hold_phase(t, held)` instead of duplicating
    its dir2-computation/open-hold/`last_press` logic — `held` is within tolerance of live altitude
    at that point, so `begin_hold_phase`'s own `dir1` resolves to `nil` and it falls straight to
    phase 2 (or resolves), the same outcome the duplicated code produced. Verified by reading both
    paths side by side, not by a behavioural test (review found no difference between the two
    copies; this changes nothing about what either path does, only removes the second copy).
- `plans/flight-control/plan.md` — **Required fix 2**: the Co-moving Fields table extended with
  `correction_substage`'s transitions and every `correction_path` write (the review's own grep
  re-run, ten write sites, all now covered — see the table's own note for the exact command and
  count).
- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py`:
  - `TestTakeoverSequence`'s existing scripts updated for the new menu-open gap: every scenario
    that drove the sequence past "opening_menu" now issues a second `run_ai_pilot_wheel` call at
    the menu-open deadline (+1.0 s from takeover) before checking `menu_open`/`stage`/press counts,
    and every subsequent relative timestamp in those scripts shifted by the same 0.5 s so ordering
    relative to the sequence (not to the wall clock) is unchanged. `test_menu_reopens_after_the_
    settle_window` is untouched — it drives the keep-open check directly, bypassing the takeover
    sequence's own stage machine, so the gap does not reach it.
  - New `test_quick_path_falls_back_to_hold_when_pulse2_still_wrong` — the second pulse resolves
    but the readback is still outside tolerance of the handover snapshot; asserts `correction_path
    == "hold"`, a phase1 hold opens (never a `quick_read2`-resolves-to-`"none"` false positive),
    and no third pulse is ever issued.

### Tests Added

- `test_quick_path_falls_back_to_hold_when_pulse2_still_wrong` (`test_ai_pilot_wheel_lua.py`) — the
  fallback this round's required fix 1 adds, mirrored on `test_quick_path_falls_back_to_hold_when_
  still_baro`'s own shape for the first pulse's refusal.

### Checks

**aircraft-layer/**
- `luac5.1 -p aircraft-layer/dcs-export/Export.lua`: pass
- `ruff format --check src tests`: pass (79 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (from inside `aircraft-layer/`): pass, no issues (27 source files)
- `pytest tests -q`: **766 passed** (765 + 1 new test; `TestTakeoverSequence`'s 8 tests, including
  the new one, confirmed by name in unfiltered `-v` output, not a `-k` run)

**body-layer/**
- `ruff format --check src tests`: pass (204 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (from inside `body-layer/`): pass, no issues (83 source files)
- `PYTHONPATH=src:../world-model/src pytest tests -q`: **3284 passed, 4 xfailed** (pre-existing,
  matches the prior round — no body-layer source change this round)

A counterfactual was run on required fix 1's own new test before trusting it: reverted the
`quick_read2` tolerance check to its pre-fix shape (unconditional `stage = nil`), re-ran
`test_quick_path_falls_back_to_hold_when_pulse2_still_wrong` alone, confirmed it failed for the
stated reason (`path` read back `"quick"` instead of `"hold"`), restored the fix, confirmed the
file's `sha256` matched the pre-mutation value exactly before running the full suite again.

### Notable Discoveries

- **The review's cited plan quote ("then go on to step 6's checks") does not exist in `plan.md`
  and never did** — it was the main loop's own dispatch-brief wording, misattributed to the plan in
  the prior `implementation.md` entry. Corrected in that entry rather than left standing, per the
  task's own instruction, so nothing downstream cites the plan for a sentence the plan never
  contained.

---

### Implementation Summary — Stage P2a/P2b (2026-11-16)

Built BL-16 mode 2's goal channel (Stage P2a: heading/altitude/speed goals, the rotation mechanism)
and HVRT translate (Stage P2b: translate hold/redirect/clear/timeout, the 2 m step) end to end
across all three subprojects — body-layer actions/rotation/dispatch, the aircraft-layer wire
(`POST /command/ai_pilot_goal`) and `Export.lua`'s per-tick press loop, and the audio-adapter
vocabulary/slot parsers that reach `crew_console.handle_command`. Seven commits, one per logical
layer, on `worktree-agent-a4c6aa4bfde4b4705r2`.

### Files Changed

**body-layer — the goal-channel core (`belief/ai_pilot_wheel.py`)**
- `AiPilotWheelGoal` (new dataclass): `heading_target_deg`/`altitude_target_m`/
  `altitude_target_ref`/`speed_target_kmh`/`active_param`/`active_since_sim`/`pending_order`/
  `goal_seq`/`hvrt_direction`.
- `request_goal`/`_with_target`/`_has_target`/`_target_field` — the queue-vs-preempt rule
  (queue at the back with no target yet; replace in place, bumping `goal_seq` only if active).
- `set_parked_heading`/`set_parked_altitude`/`set_parked_speed`/`set_hvrt_direction`/
  `clear_hvrt_direction` — the five actions; `set_parked_altitude` returns the achieved
  reference (`resolve_altitude_reference`, the 700 m radar cap) for the readback.
- `nearest_speed_step`/`step_speed`/`altitude_ref_from_letter` — small pure helpers the
  readback and `crew_console` handlers both need.
- `decide_ai_pilot_wheel` — the one "when": promotes the queue front when idle, rotates the
  active parameter after `AI_PILOT_GOAL_SLICE_S`, clears a settled parameter, reconciles an
  HVRT safety-timeout release, and never promotes while `takeover_stage is not None`.
- `ParkedFlightState` gains `goal: AiPilotWheelGoal | None` (was `Any`) and `lua_goal_progress`/
  `lua_goal_seq` (read-only mirrors of `Export.lua`'s own goal-tick report).
- New tunables: `AI_PILOT_GOAL_SLICE_S` (3.0), `AI_PILOT_HEADING_TOLERANCE_DEG` (5.0),
  `AI_PILOT_SPEED_STEPS_KMH` (corrected to the measured 120/150/200/250, dropping the unmeasured
  160), `AI_PILOT_ALTITUDE_RADAR_CAP_AGL_M` (700.0, a third duplication of the same physical
  limit — see that constant's own comment). `AI_PILOT_SPEED_MAX_SENTINEL_KMH` is a plain
  protocol constant, not a tunable (root `CLAUDE.md`'s own test: a different value would not
  change what Petrovich does).

**aircraft-layer — the wire and Export.lua**
- `src/collector/command_sender.py` — `CommandSender.send_ai_pilot_goal` (plain `json.dumps`,
  not `_format_fixed_point`: no near-zero-exponent risk on this channel).
- `src/api/server.py` — `POST /command/ai_pilot_goal` (shape validation, bounds on every
  numeric field, closed vocabularies for `param`/`altitude_target_ref`/`hvrt_direction`/
  `hvrt_step`).
- `src/schema/ai_pilot_wheel.py` — `AiPilotWheelState` gains `goal_progress`/`goal_seq`
  (defaulted, so the one pre-existing construction site in the test file did not need updating
  for the dataclass itself; its `to_api_dict` assertion did, additively).
- `dcs-export/Petrobrain/ai_pilot_wheel.lua` — `handle_ai_pilot_goal_command`; the per-5 Hz-tick
  dispatcher (`ai_pilot_goal_tick`, mode-cycle-then-press bounded by `MODE_CYCLE_MAX_ATTEMPTS`);
  dedicated heading (`AI_WHEEL_LEFT`/`_RIGHT`, long hold)/altitude (reuses `ai_pilot_correction_
  direction`, plus its own reference-toggle pulse) hold-and-poll loops on a **separate**
  pending-release pair from the takeover correction's own; a speed tap loop (short, inner-ring,
  same buttons as altitude's long-hold outer ring); the HVRT translate hold/redirect/clear/
  timeout loop (`ai_pilot_goal_tick_hvrt`); `hvrt_step`'s one-shot tap, deduplicated by comparing
  the incoming `goal_seq` against the stored one. `on_stop`/the unpark branch release and reset
  the new state proactively (same `AC-B13` gap class, closed before it recurs).
- `dcs-export/Petrobrain/commands.lua` — registers `ai_pilot_goal`, guarded on `ai_pilot_wheel ~=
  nil` like every other handler-owning module.
- Local count: 37 → 60 (`grep -cE '^local ' ai_pilot_wheel.lua`, before/after) — at AC-B12's own
  "~60" target, not over it, 30% of the 200 hard ceiling.

**body-layer — crew_console dispatch and the body.py glue**
- `belief/crew_console.py` — handlers for `level_flight`/`turn_heading`/`turn_heading_relative`/
  `set_speed`/`speed_step`/`set_altitude`/`altitude_step`/`hold_altitude`/`level_off` and
  `hvrt_translate_left`/`_right`/`_forward`/`_back`/`hvrt_hold`/`hvrt_step_up`/`_down`; each sets
  one of four new one-shot transition fields (`ai_pilot_goal_transition`/`ai_pilot_level_flight_
  transition`/`ai_pilot_hvrt_transition`/`ai_pilot_hvrt_step_transition`) for `body.py` to apply,
  matching `observ_transition`'s own division of labour. `parked_flight_state` is a new
  read-only state param, refreshed every poll. `drain_ai_pilot_wheel_speech` speaks "Unable, not
  ready." once per exhausted mode-cycle attempt (edge-triggered on `lua_goal_progress ==
  "mode_blocked"`). New `render_unable("NOT_READY")` reason (`belief/speech.py`), the pilot's own
  exact words.
- `src/body.py` — `_apply_ai_pilot_wheel_goal`: applies the four transitions to `ParkedFlightState.
  goal`, runs `decide_ai_pilot_wheel` (deriving `settled_param`/`hvrt_released_timeout` from
  `lua_goal_progress`), and sends `write_ai_pilot_goal` on a `goal_seq` change — the same
  "send on change" posture `write_sight_target`'s call site already has. `hvrt_step` always sends
  with a freshly-bumped `goal_seq` (its own one-shot-trigger contract). Unparking drops the goal
  and the send cursor (E-P10). New `ConsolePerceptionRunner.ai_pilot_goal_last_sent_seq` field.
- `src/aircraft_client.py` — `write_ai_pilot_goal` (raise-on-failure, mirrors `write_sight_
  target`); `hvrt_step` param added in the same commit `command_sender.py` gained it.

**audio-adapter — the voice vocabulary**
- `src/vocabulary.py` — 16 new tokens, all voice-only (no F10 menu involvement in BL-16 at all).
  New slot parsers: `parse_heading_deg` (digit-by-digit or an 8-point compass word via
  `SECTOR_WORD_DEGREES`, no 5° checksum — the AI wheel's own hold has none), `parse_turn_
  relative`, `parse_speed_value` ("max" or digits, **immediate-token-only** so "speed up" can
  never misresolve as a numeric request), `parse_speed_step_direction`, `parse_altitude_value`
  (optional trailing `radar`/`barometric`), `parse_altitude_step`. `_read_digits_after`
  generalises `parse_bearing`'s own digit-concatenation convention to any anchor word.
- `src/command_matcher.py` — one verb-anchored branch per new slotted token, ordered before the
  generic phrase table like every existing one. `_HVRT_BARE_WORD_TOKENS` + an exact
  single-word check, ahead of every fuzzy branch (see Notable Discoveries).

### Tests Added

- `body-layer/tests/test_ai_pilot_wheel.py` — `TestRequestGoal`/`TestSetParkedHeading`/
  `TestNearestSpeedStep`/`TestSetParkedSpeed`/`TestStepSpeed`/`TestResolveAltitudeReference`/
  `TestSetParkedAltitude`/`TestHvrtDirection`/`TestDecideAiPilotWheel`/`TestAltitudeRefFromLetter`/
  `TestAiPilotGoalRequest`/`TestAiPilotWheelGoalChannelFields` (the latter in
  `aircraft-layer/tests/test_ai_pilot_wheel_api.py`) — every pure function and the rotation
  mechanism's promote/demote/preempt/settle/takeover-gate sequences.
- `aircraft-layer/tests/test_ai_pilot_goal.py` — `send_ai_pilot_goal` wire format (incl.
  `hvrt_step`) and the `POST /command/ai_pilot_goal` endpoint's validation/bounds/503/500 paths.
- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py` — new `TestAiPilotGoalModeReady`/
  `TestAiPilotGoalHeadingDirection`/`TestAiPilotGoalAltitudeRefMismatch`/
  `TestAiPilotGoalSpeedTapDirection`/`TestAiPilotGoalHvrtDirectionCmd` (pure decisions) and
  `TestAiPilotGoalTick`/`TestHandleAiPilotGoalCommand`/`TestHandleAiPilotGoalCommandHvrtStep`/
  `TestAiPilotGoalTickHvrt` (integration, against a real Lua interpreter) — mode-cycle-then-press,
  the `mode_blocked` bound, the altitude reference toggle, speed taps, HVRT hold/redirect/
  timeout, and `hvrt_step`'s one-shot-per-`goal_seq` behaviour. Extended the existing
  `TestOnStop` with the new goal/HVRT release paths.
- `body-layer/tests/test_crew_console_ai_pilot_wheel.py` (new file) — every handler's readback
  and transition value, the "unable, not ready" precondition paths, and the reset-at-top-of-
  dispatch convention.
- `body-layer/tests/test_body_ai_pilot_wheel.py` (new file) — `_apply_ai_pilot_wheel_goal`'s own
  composition: transition application, the settle/rotate/send sequence, `hvrt_step`'s bumped
  `goal_seq`, the unpark reset, and the no-ownship-sample-yet no-op.
- `audio-adapter/tests/test_bl16_stage_p2_vocabulary.py` (new file) — every new slot parser and
  `match_transcript` branch, plus the HVRT bare-word collision fix.
- `body-layer/tests/test_speech.py` — `render_unable("NOT_READY")`.

### Checks

**body-layer/**
- `ruff format --check src tests`: pass (206 files already formatted)
- `ruff check src tests`: pass except one **pre-existing, unrelated** `I001` finding in
  `tests/test_bl_b104_association_scenarios.py` (confirmed via `git log` — last touched
  `951a32e1`, not this round; not in this round's diff)
- `mypy src` (from inside `body-layer/`): pass, no issues (83 source files)
- `.claude/scripts/fast-tests.sh body-layer`: **2532 passed, 4 xfailed** (4 xfailed pre-existing)

**aircraft-layer/**
- `ruff format --check src tests`: pass (81 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (from inside `aircraft-layer/`): pass, no issues (27 source files)
- `luac5.1 -p` on every `dcs-export/*.lua` and `dcs-export/Petrobrain/*.lua`: pass
- `.claude/scripts/fast-tests.sh aircraft-layer`: **380 passed**

**audio-adapter/**
- `ruff format --check src tests`: pass (32 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (from inside `audio-adapter/`): pass, no issues (16 source files)
- `PYTHONPATH=src pytest tests -q` (full suite, not just fast-tests): **438 passed, 2 skipped**
  (the 2 skips are the pre-existing live-Piper/whisper-binary env-var gates)

### Notable Discoveries

- **Two internal plan inconsistencies, resolved rather than escalated (both local, reversible —
  Escalation Rules):**
  1. The vocabulary table names one token (`hvrt_translate`/`hvrt_step`) for several bare
     direction words, but the generic phrase match carries no information beyond the matched
     *token* once several phrases share one, and the plan's own "no slot parser needed" rules out
     adding one. Implemented as one enumerated token per word instead
     (`hvrt_translate_left`/`_right`/`_forward`/`_back`, `hvrt_step_up`/`_down`), the same shape
     `_RELATIVE_SCAN_TOKENS` already uses for bare direction words. Player-facing behaviour (the
     readback table) is unchanged; only the internal token space differs from the plan's literal
     wording.
  2. The "Amended 2026-11-15" vocabulary note says HVRT dispatch is gated on `ai_mode ==
     "HVRT"` exactly, treating anything else as unmatched; the later, more specific 2026-11-16
     decision says a bare direction word reaches from *hover* (`HVR`) too, cycling into HVRT
     automatically, and answers "unable, not ready" only outside hover entirely — which requires
     the command to be *heard and answered*, not silently dropped. Implemented the later decision
     (gate on `ai_mode in ("HVR", "HVRT")`, inside the handler, always returning a line) as
     authoritative over the earlier note, per this project's "a later decision supersedes an
     earlier one on the same topic" convention.
- **A real, measured matcher collision, found and fixed while wiring HVRT's bare words**: a bare
  "right" fuzzy-anchors onto `_POINT_VERBS`
  (`difflib.SequenceMatcher(None, "right", "sight").ratio() == 0.8`, above `VERB_FLOOR`) and
  resolves as `point`'s own `relative` slot (`RELATIVE_WORDS` already contains "left"/"right")
  before the generic phrase table — where `hvrt_translate_right` lives — is ever reached. Fixed
  by checking HVRT's seven bare single-word commands as an **exact**, whole-transcript match
  before any fuzzy branch runs, rather than narrowing `_POINT_VERBS`' own tolerance (which risked
  regressing its calibrated "look"/"sight" matching for an unrelated reason). This collision
  predates this round — any bare "right" said for an unrelated reason would already have
  misresolved to `point` — but was never surfaced because no existing token previously needed a
  bare "left"/"right" to resolve to anything else.
- **`hvrt_step` (the 2 m HVRT altitude tap) is named in Stage P2b's own task list
  ("`hvrt_hold`/`hvrt_step` actions") but absent from the plan's "wire shape" section**, which
  enumerates only `goal_seq`/`param`/`heading_target_deg`/`altitude_target_m`/`altitude_target_
  ref`/`speed_target_kmh`/`hvrt_direction`. Implemented as a one-shot field added to the existing
  `ai_pilot_goal` message (the smallest consistent extension) rather than a new op — acted on
  exactly once per distinct `goal_seq`, which `body.py`'s own call site is responsible for
  bumping on every send that carries one. Flagged for review rather than silently built as if the
  wire shape had always included it.
- **`level_off`'s own readback is not in the plan's Readbacks table at all** (the table lists
  `level_flight`/`turn_heading`/`turn_heading_relative`/`set_speed`/`speed_step`/`set_altitude`/
  `altitude_step`/`hold_altitude`/`hvrt_translate`/`hvrt_hold`/`hvrt_step`, but not `level_off`,
  even though the vocabulary table lists the token itself). Chose to reuse `turn_heading`'s own
  readback shape (the resolved heading, digit by digit: "Heading 1 2 0.") since `level_off`'s
  action *is* a heading goal (freeze at current) — a judgement call, not a plan requirement.
- **`held_speed` cannot currently distinguish "unknown" from "AI already at MAX"** — `_parse_
  float` (`advance_parked_flight_state`) returns `None` for the literal overlay string `"MAX"`,
  so `speed_step("down")` spoken while already at MAX currently reads as "unable, not ready"
  rather than stepping down from MAX. Documented on `step_speed`'s own docstring as a known gap,
  not fixed in this stage — the parse-time fix belongs with whichever stage first needs `held_
  speed` to tell the two apart for its own reasons.
- **Stage P0-rad (the 700 m radar cap probe) was not flown this round**, per the task's own
  instruction not to block on it — the "alt ... radar" row's quick-path behaviour in `Export.lua`
  (reusing the takeover correction's own measured pulse mechanism) is built as designed but
  remains provisional until that probe (or Flight P2a) confirms it against a target actually
  above the cap while already on radar.
- **Three constants now exist for the same 700 m radar-cap physical limit**: `Export.lua`'s own
  `AI_PILOT_QUICK_PATH_MAX_AGL_M`, body-layer's `AI_PILOT_ALTITUDE_TOLERANCE_M`-style duplication
  precedent, and the new `AI_PILOT_ALTITUDE_RADAR_CAP_AGL_M` (needed in body-layer because the
  readback must resolve the achieved reference at acceptance time, before any live AGL read could
  arrive). Flagged in both constants' own doc comments; not unified in this stage.
- **Flights P2a and P2b are the pilot's own** — nothing in this round claims live DCS behaviour;
  every check above is static (format/lint/type) or runs against a real Lua interpreter/loopback
  HTTP server, never a live DCS session.

### Merge: origin/main (seat gate) into feature/bl16-p2-voice-goals, 2026-11-16

`fix/ai-wheel-pilot-seat-gate` (main, `53104a49`/`964daf7f`) landed the operator-seat gate on
`ai_pilot_wheel.lua`'s *takeover* correction while this branch's own Stage P2a/P2b commits (goal
channel, HVRT translate) were in flight against the pre-gate file — both sides touched
`run_ai_pilot_wheel`'s park/unpark branch and `push_ai_pilot_wheel_state`. Merged `a55f7e97` with
`git merge --no-ff`, resolving by hand rather than taking either side whole.

**How the seat gate reaches the goal/HVRT loops, by construction, not by a second check:**
`run_ai_pilot_wheel` now computes `ai_pilot_parked_active` from
`in_operator_seat and stick_park or nil` (main's own change) — leaving the operator seat forces
`now_parked = false` exactly as a real unpark would, regardless of arg 852. Every P2a/P2b
per-tick loop (`ai_pilot_goal_tick`/`ai_pilot_goal_tick_hvrt`) is called only from
`update_ai_pilot_wheel_overlay`, which itself returns immediately `if not ai_pilot_parked_active`
— a guard Stage P1 already had and Stage P2a/P2b never needed to touch. So the seat gate covers
the goal channel and HVRT translate **without either tick function reading the seat itself**: the
one existing `ai_pilot_parked_active` check is the only gate either loop has ever had, and it is
now seat-aware for free.

**What the merge *did* need to add by hand, in `run_ai_pilot_wheel`'s "not now_parked" branch**:
the goal/HVRT release code (release any open `ai_wheel_goal_pending_cmd` hold and
`ai_pilot_goal.hvrt_hold_cmd` press, reset `ai_pilot_goal.*` to idle) runs **unconditionally**,
same as the takeover correction's own release — only the menu-close tap is gated on
`in_operator_seat` (main's own rule: a tap while in the pilot seat would land on the pilot's own
wheel). A held goal/HVRT press is a device-30 release, not a wheel-menu navigation, so there is no
"wrong wheel" risk in releasing it from either seat.

**Added**, since the coordinator's merge instruction asked for direct coverage rather than relying
on the above argument alone:
`test_ai_pilot_wheel_lua.py::TestSeatGate::test_goal_hold_releases_without_new_press_on_switch_to_pilot_seat`
— opens a heading-goal hold, switches `camera_fwd` to the pilot eye point mid-hold, and asserts the
held press releases, `ai_pilot_goal.progress` drops to `"idle"`, no menu tap fires, and nothing
presses again while the seat stays pilot. Verified red-then-green: reverting `run_ai_pilot_wheel`'s
`in_operator_seat and stick_park or nil` back to plain `stick_park` fails this test (and the three
pre-existing `TestSeatGate` tests) for the expected reason; restored byte-for-byte (checksum
matched before/after) and the suite is green again.

**`EXPORT_SCRIPT_VERSION`/`EXPECTED_EXPORT_VERSION` bumped `"2026-11-16c"` → `"2026-11-16d"`**
(this branch had not touched the version string; main's seat-gate fix owned `"...16c"`) — this
merge's own functional change (goal channel + HVRT now merged against the seat gate) is otherwise
invisible to the version-match staleness check. `test_export_lua_constants_parity.py` keeps the
two in sync.

**`body-layer/config/defaults.toml` regenerated**, not hand-merged, via
`tools/generate_defaults.py --write` — both branches' tunables (this branch's pre-existing
`AI_PILOT_HEADING_TOLERANCE_DEG` etc., main's new `[belief.altimeter_qnh_sync]` block) render
correctly from the already-clean-merged `.py` sources with no further action.

**Resolution shape for the other conflicted files** was mechanical once the above was understood:
`aircraft-layer/src/schema/ai_pilot_wheel.py` and both `aircraft-layer/tests/test_ai_pilot_wheel_*`
files each had two independent, non-overlapping field/test additions (this branch's
`goal_progress`/`goal_seq`, main's `seat`/`cam_fwd_m`) landing at the same insertion points —
combined by keeping both, with `seat`/`cam_fwd_m` ordered before the defaulted `goal_progress`/
`goal_seq` fields on `AiPilotWheelState` (a frozen, non-`kw_only` dataclass requires every
no-default field before any defaulted one; all construction call sites already use keyword args,
so no behavioural effect). `body-layer/src/body.py` and `body-layer/src/belief/crew_console.py`
each had one import-block conflict (this branch's `belief.ai_pilot_wheel` import vs. main's new
`belief.altimeter_qnh_sync` import) — kept both.
