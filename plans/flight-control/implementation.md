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

---

## Review-fix round, 2026-11-16 (`plans/flight-control/review-p2.md`, NEEDS REVISION)

All three required fixes.

### Required fix 1 — HVRT mode-cycle bound

`ai_pilot_goal_tick_hvrt`'s own mode-cycle (into `HVRT`) had no attempt bound, no `"mode_blocked"`
report, and no voice escape (`crew_console._handle_hvrt_hold` gated the cancel on the same
readiness check that gates the start). Gave it the identical bound/report shape `ai_pilot_goal_
tick`'s own mode-cycle already had, via a **separate** attempt counter
(`ai_pilot_goal.hvrt_mode_cycle_attempts`/`.hvrt_mode_blocked_since_t`) so the two ticks never share
one — and made `_handle_hvrt_hold` unconditional whenever a translate direction is already
outstanding, regardless of `ai_mode`.

### Required fix 2 — goal channel vs. HVRT arbitration

The plan's "mode-exclusive by construction" reasoning was wrong (`HVR` is accepted by both `ai_
pilot_goal_mode_ready` and `_ai_pilot_hvrt_ready`), so a goal and a translate could be
simultaneously outstanding and press the same button codes in the same tick. **The main loop's own
rule, a judgement call made on the pilot's behalf** (reversible, local — the dispatch brief's own
framing, not the plan's):

- Latest command wins, nothing lost.
- Setting an HVRT translate direction pauses the heading/altitude/speed goal channel — queued and
  active goals keep their targets and queue positions.
- "Hold" lets the paused goals resume through the normal rotation.
- Speaking any new heading/altitude/speed goal clears an outstanding translate direction (releasing
  its held press), then the goal proceeds normally.
- The two ticks never both press in one tick, enforced on both sides.

Implementation: `belief/ai_pilot_wheel.py` gains `goal_param_for_wire(goal)` — the single function
that decides what `param` value actually reaches the wire (`None` whenever `hvrt_direction is not
None`, even though `active_param` itself is left untouched); `body.py`'s two `write_ai_pilot_goal`
call sites route through it instead of reading `final_goal.active_param` directly. `request_goal`
now clears an outstanding `hvrt_direction` itself (the one function every heading/altitude/speed
action routes through, so the "speaking a new goal clears the translate" rule lives in one place).
`set_hvrt_direction`/`clear_hvrt_direction` now bump `goal_seq` on an actual change — a gap beyond
what the review named, found while implementing this fix: neither bumped before, so "Hold"
(clearing a translate with nothing else having changed `goal_seq` that poll) would never actually
reach `Export.lua` as a fresh message, and the goal channel would stay silently paused forever.
`decide_ai_pilot_wheel` gains an early-return while `goal.hvrt_direction is not None` (after the
timeout-reconciliation and takeover-stage checks, before any settle/promote/rotate logic) — nothing
is promoted, demoted or settled while a translate is held. On the Lua side, `ai_pilot_goal_tick`
gains a second, defensive guard at its own top (`if ai_pilot_goal.hvrt_direction ~= nil then
ai_pilot_goal_release_hold(); return end`) — belt-and-suspenders, since `goal_param_for_wire`
already nulls `.param` on the wire whenever a translate is held, but the task explicitly asked for
enforcement on both sides, and a guard here is cheap insurance against any future call site that
forgets the wire-level invariant.

### Required fix 3 — `mode_blocked` must retry, not stall forever

Once `mode_cycle_attempts`/`hvrt_mode_cycle_attempts` hit `MODE_CYCLE_MAX_ATTEMPTS`, nothing reset
them short of a *different* `param` arriving or the mode becoming ready on its own — the
multi-goal rotation case incidentally reset the counter by switching `active_param`, masking the
bug in exactly the case the plan worried about dead-time cost for; the ordinary single-goal case
was retried never, after one spoken "unable, not ready."

New Lua constant `MODE_BLOCKED_RETRY_S = 3.0` (`ai_pilot_wheel.lua`, a plain top-level local, not a
tunable mechanism entry — **this would want body-layer's `tuning.py` bounds/`defaults.toml` if a
Lua-side tuning loader existed; outside body-layer that loader does not exist yet, so this stays an
ordinary constant, flagged here rather than improvising a second mechanism**, per root `CLAUDE.md`'s
"Behaviour-affecting constants are tunable" section). Shared by both `ai_pilot_goal_tick` and
`ai_pilot_goal_tick_hvrt`'s own bounds via two separate `*_mode_blocked_since_t` timestamp fields:
the first tick that exhausts the bound records when, reports `"mode_blocked"` and presses nothing;
every subsequent tick re-checks the elapsed time, and once `MODE_BLOCKED_RETRY_S` has passed, resets
the attempt counter and falls straight through to a fresh press attempt the same tick (not waiting
for a further tick to spend the first renewed attempt). Reset on `param`/`hvrt_direction`-change,
unpark, and `on_stop`, mirroring the existing `mode_cycle_attempts` reset sites exactly (grepped
`mode_cycle_attempts = 0` across the file and added the new fields at each site found).
`drain_ai_pilot_wheel_speech`'s existing edge-trigger (`_ai_pilot_mode_blocked_spoken`, reset
whenever `lua_goal_progress != "mode_blocked"`) needed no change — the retry naturally flips
`goal_progress` back to `"cycling_mode"` between exhausted episodes, so "spoken once per exhausted
attempt" already falls out of the existing mechanism once Lua actually produces more than one
episode.

**Both channels share one wire-level `apw_goal_progress`/Lua `ai_pilot_goal.progress` field** (a
pre-existing design, not changed here) — `ai_pilot_goal_tick` and `ai_pilot_goal_tick_hvrt` never
both write it in the same tick in correct operation, because exactly one of them is active at a
time (fix 2's own mutual-exclusion): the FLT/HVR tick returns before touching `.progress` whenever
a translate is outstanding, and the HVRT tick's own "nothing outstanding" branch never touches it
either. So `drain_ai_pilot_wheel_speech`'s existing "unable, not ready" line already covers HVRT's
own `mode_blocked` with no HVRT-specific body-layer code needed.

### Files Changed

- `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua` — `MODE_BLOCKED_RETRY_S`; `ai_pilot_
  goal.mode_blocked_since_t`/`.hvrt_mode_cycle_attempts`/`.hvrt_mode_blocked_since_t` (new fields,
  reset at every existing `mode_cycle_attempts = 0`/full-reset site); `ai_pilot_goal_tick`'s
  `hvrt_direction` pause guard and retry-after-cooldown logic; `ai_pilot_goal_tick_hvrt`'s own
  bound/retry, mirroring `ai_pilot_goal_tick`'s shape; pruned the stale "mode-exclusive by
  construction" claim from both functions' own comments (the code they described changed under
  them this round).
- `aircraft-layer/dcs-export/Export.lua` / `aircraft-layer/src/collector/server.py` —
  `EXPORT_SCRIPT_VERSION`/`EXPECTED_EXPORT_VERSION` bumped `"2026-11-16d"` → `"2026-11-16e"`: a
  non-additive behavioural reshape (a message that previously could carry both `param` and `hvrt_
  direction` meaningfully now has body-layer null `param` whenever a translate is held).
- `body-layer/src/belief/ai_pilot_wheel.py` — `goal_param_for_wire` (new); `request_goal` clears an
  outstanding `hvrt_direction`; `set_hvrt_direction`/`clear_hvrt_direction` bump `goal_seq` on an
  actual change (no-op otherwise); `decide_ai_pilot_wheel`'s own HVRT-pause early return; pruned the
  stale "mode-exclusive by construction" claim from `AiPilotWheelGoal`'s own docstring, replaced
  with an accurate account of the fix.
- `body-layer/src/belief/crew_console.py` — `_handle_hvrt_hold` cancels unconditionally whenever a
  translate direction is already outstanding on `self.parked_flight_state.goal`, falling back to
  the existing readiness-gated path only when there is nothing to cancel.
- `body-layer/src/body.py` — both `write_ai_pilot_goal` call sites route the `param` argument
  through `goal_param_for_wire` instead of reading `final_goal.active_param` directly.

### Tests Added

- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py`:
  - `test_mode_cycles_before_pressing_then_blocks_then_retries_after_cooldown` (rewrite of `test_
    mode_cycles_before_pressing_then_blocks_after_the_bound`, which asserted the bug) — the
    single-outstanding-goal case the review named explicitly: ticks past the bound, confirms still
    blocked short of `MODE_BLOCKED_RETRY_S`, then confirms one renewed press attempt once the
    cooldown elapses, goal target kept throughout.
  - `test_mode_cycle_into_hvrt_is_bounded_reports_blocked_then_retries` — the same shape for `ai_
    pilot_goal_tick_hvrt`'s own, previously-unbounded mode-cycle.
  - `test_an_outstanding_hvrt_direction_stops_this_tick_from_pressing` — a message carrying both
    `param` and `hvrt_direction` non-null (the exact collision the review found possible); confirms
    `ai_pilot_goal_tick` presses nothing and the HVRT tick is the only one that presses once the
    mode actually reaches `HVRT` — the required "two ticks never press on the same tick" Lua test.
- `body-layer/tests/test_ai_pilot_wheel.py`:
  - `TestRequestGoal.test_a_new_goal_clears_an_outstanding_hvrt_translate` / `test_no_hvrt_
    direction_outstanding_is_unaffected`.
  - `TestHvrtDirection.test_an_actual_change_bumps_goal_seq` / `test_no_change_does_not_bump_goal_
    seq`.
  - `TestGoalParamForWire` (new class) — `active_param` passes through with no translate; nulled
    while one is outstanding, with `active_param` itself left untouched.
  - `TestDecideAiPilotWheel.test_an_outstanding_hvrt_translate_pauses_the_goal_channel` / `test_a_
    queued_second_goal_also_stays_queued_while_paused` / `test_the_goal_channel_resumes_once_the_
    translate_clears`.
- `body-layer/tests/test_crew_console_ai_pilot_wheel.py`:
  - `TestHvrtHold.test_cancels_unconditionally_when_a_translate_is_already_outstanding` / `test_
    still_unable_when_nothing_outstanding_and_not_in_hover`.
- `body-layer/tests/test_body_ai_pilot_wheel.py` — `TestHvrtArbitration` (new class), the exact
  three-step sequence named in the task: a goal active then "left" (goal presses stop on the wire,
  the translate runs); "Hold" (the goal resumes on the wire); a translate active then a new
  altitude goal (the translate is released on the wire, the goal runs).

### Checks

**aircraft-layer/**
- `luac5.1 -p` on `Export.lua` and every `dcs-export/Petrobrain/*.lua`: pass
- `luac5.1 -l -p ai_pilot_wheel.lua` `GETGLOBAL` scan: clean (stdlib/DCS APIs only, no bare
  reference to a project-defined name)
- Local count: `grep -cE '^local ' ai_pilot_wheel.lua` → 69 (was 68), one new top-level local
  (`MODE_BLOCKED_RETRY_S`) — the new per-tick/per-channel bookkeeping lives as table fields, not
  new locals, same reasoning the file's own table-grouping comments already state
- `ruff format --check src tests`: pass (81 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (from inside `aircraft-layer/`): pass, no issues (27 source files)
- `pytest tests -q -m "not slow"` (full subproject suite, not just fast-tests): **881 passed**
  (confirmed by running the whole suite, not a `-k` filter, after the version-string bump to catch
  any stray reference to the old string)

**body-layer/**
- `ruff format --check src tests`: pass (208 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (from inside `body-layer/`): pass, no issues (84 source files)
- `pytest tests -q -m "not slow" -n auto` (full subproject suite): **3401 passed, 4 xfailed**
- `.claude/scripts/fast-tests.sh body-layer` / `.claude/scripts/fast-tests.sh aircraft-layer`: both
  pass (2588 passed/4 xfailed; 711 passed) — run first, before the full-suite confirmation above

`test_tuning_defaults_toml.py`: pass — no new body-layer tuning constant this round, `defaults.toml`
unchanged.

### Notable Discoveries

- **The `set_hvrt_direction`/`clear_hvrt_direction` goal_seq gap** (described under Required fix 2
  above) was not named in the review but was necessary for the review's own required behaviour to
  work at all: without it, "Hold" and a redirected translate would silently never reach `Export.
  lua`, since `body.py`'s own "send on `goal_seq` change" posture is the *only* thing that triggers
  a wire send.
- **The plan's "mode-exclusive by construction" claim appears in three places** (`plan.md`'s own
  wire-shape note, `AiPilotWheelGoal`'s docstring, and `ai_pilot_wheel.lua`'s `ai_pilot_goal_tick_
  hvrt` comment) — the two code-adjacent copies were corrected in place (root `CLAUDE.md`'s "prune
  the comment you are standing next to," triggered because the code they described changed this
  round). `plan.md`'s own prose was left as the historical record of the wrong reasoning, per `docs/
  PROCESS.md`'s "superseding a decision" — not this round's file to edit, and the main-loop
  arbitration rule above is the record of what actually supersedes it.
- **`MODE_BLOCKED_RETRY_S` is a judgement call, not a pilot-specified figure** — "a few seconds" per
  the task; 3.0 s was chosen to match the existing `AI_PILOT_GOAL_SLICE_S` default's order of
  magnitude, not measured against a live flight. Flagged for the same reason `HVRT_TRANSLATE_MAX_
  HOLD_S` (15.0 s) was flagged when it was first added.

## Mode 1, Stage M1 (the seam and handover)

From `plans/flight-control/plan.md`, "Revised 2026-11-18 — mode 1 (unparked, raw axes) re-cut",
Stage **M1 only** (the control law itself is Stage M2, not built here — output is captured +
wobble, nothing else). Base: fast-forwarded from `f06c53fb` (the worktree's own stale start) to
`56dc91c7` (the plan/alignment commits), then merged `main` (`0c206b37`) to pull in `refactor/
rule-action-unable-throw` (`85272e9d`), a hard prerequisite for Decision 22's action-failure
shape that had landed on `main` but not yet on this feature line. **Per U7, M1 does not merge
until the user's M0 probe answers rows B, C and D** — built and tested fully on the Mac regardless.

Three mid-task corrections arrived from the user's own M0 flights and are folded in as they came,
each its own commit: M0-B (pedal confirmed, `SIGN.pedals = -1.0`, first-order step response, not
rate-limited as first reported), M0-C (collective — 2004 is "Throttle (Collective)", confirmed to
do nothing; the real id is 2087, `iCommandPlaneCollective`, from the user's own DCS binding file,
sign still unmeasured).

### Files Changed

**aircraft-layer**
- `dcs-export/Petrobrain/flight_control.lua` (new) — the mode-1 module: `handle_flight_control_
  command` (take/release/goal/arm, the shared `wire_seq`/`fc_last_cmd_seq` staleness check, every
  `limits` field bounds-checked, whole-message reject on violation), `run_flight_control` (every
  frame from `LuaExportBeforeNextFrame`: self-arm on the park edge, the same-frame unpark take and
  its own preconditions — `UNPARK_TAKE_ENABLED` off until M0-J, so this always refuses `"disabled"`
  today — the per-frame envelope check, the pause/huge-jump row), `push_flight_control_state` (5 Hz
  status). The Mi-24P arg/cmd/sign table: pitch/roll unverified guesses (2001/2002); pedal measured
  (2003, `SIGN=-1`, M0-B) and enabled; collective's id now known (2087) but its sign is not (M0-C
  re-fly owed), so it stays disabled. `run_active_frame` is shared between the ordinary per-frame
  path and a fresh take/unpark-take transition, so output is continuous **from the first frame** a
  take lands on, not the next poll of `run_flight_control` — a real bug caught by `TestCaptureIs
  BitExact` before I'd even finished writing the Lua (see Notable Discoveries).
- `dcs-export/Petrobrain/ai_pilot_wheel.lua` — `M.is_parked()`/`M.player_seat()`, read-only getters
  (Decision 25) for `flight_control.lua`'s own capture-source rule. `is_parked()` returns `ai_
  pilot_parked_active`, never 852 alone, exactly as the plan names it so there would be no
  ambiguity to pick wrong.
- `dcs-export/Petrobrain/commands.lua`, `dcs-export/Export.lua` — load the new module (after `ai_
  pilot_wheel`, before `commands`), register its handler, add `LuaExportBeforeNextFrame` (new
  callback — Decision 23's own per-frame injection point), the 5 Hz push, bump `EXPORT_SCRIPT_
  VERSION` ("2026-11-18").
- `src/schema/flight_control.py`, `src/collector/cache.py`/`server.py`/`command_sender.py`/
  `__main__.py`, `src/api/server.py` — the Python-side wire: `FlightControlCache`, routing on
  `"fc_mode"`, `CommandSender.send_flight_control`, `GET /flight_control/latest` + `POST /command/
  flight_control` (shape validation only — every `limits`/`goal` field finite/in-range, `cmd`
  closed, `Export.lua`'s own dispatch re-checks every bound a third time, the `[[AC-B14]]` lesson).
- `CLAUDE.md` — the "What this is" bullet for the third write path (never an axis value).

**body-layer**
- `src/belief/flight_control.py` (new) — `FlightControlState`/`advance_flight_control_state`
  (single construction site, same shape as `ParkedFlightState`), `take_controls`/`release_
  controls` (pure functions), `decide_flight_control` (the one "when": park/unpark edges, the ack
  timeout, Lua's own self-release, a refused unpark take), `clamp_altitude`/`clamp_speed`,
  `flight_control_limits`, `goal_request_fields`. Eight new `tuning.py` constants under `[belief.
  flight_control]`: `TAKEOVER_LEVEL_BANK_DEG`, `FLOOR_AGL_M`, `MIN_IAS_KMH`, `MAX_IAS_KMH`, `MAX_
  BANK_DEG`, `ARM_LEASE_S`, `SPEED_STEP_KMH`, `HANDOVER_ACK_TIMEOUT_S` — `config/defaults.toml`
  regenerated and the rendered first sentences read back.
- `src/belief/crew_console.py` — `flight_mode()` (the one place `rules.actions._by_mode` reads);
  `flight_control_state` (this class's own **authoritative** copy, unlike `parked_flight_state`'s
  mirror-of-`runner` shape, because `take_controls`/`release_controls` act synchronously); `ias_
  kmh`/`poll_now_sim` (two new "refreshed every poll" fields, same precedent as `on_ground`, since
  no existing path threads sim time/live telemetry into a rule's own action `invoke`); `flight_
  control_transition`/`flight_control_goal_transition` (the two new one-shots, reset in `_reset_
  one_shot_command_state`); `current_crew_state()` widened (`has_controls = parked_active or
  axes-phase-in-{TAKING,ACTIVE}`; `held_*` falls back to `FlightControlState.measured_*` whenever
  nothing has been commanded yet, via the new `_axes_current_heading`/`_axes_current_altitude`/
  `_axes_current_speed` helpers shared with the action bodies); `take_controls`/`release_controls`/
  `axes_turn_continuous`/ten `axes_*` goal-action bodies (`increment_heading`/`set_heading`/`level_
  flight`/`set_speed`/`set_speed_max`/`step_speed`/`set_altitude`/`step_altitude`/`hold_altitude`/
  `level_off`); `drain_flight_control` (runs `decide_flight_control`, speaks the result).
- `src/rules/actions.py` — `_by_mode(overlay=, axes=)`, wrapping all 16 pre-existing flight actions
  (the HVRT five share one `_axes_hvrt_unready` body — "forward flight only," always `NOT_READY`);
  `turn_continuous` (new, not `_by_mode`-wrapped — mode 2 has no "continuous turn" concept to
  dispatch to, so it checks `flight_mode()` itself and answers `AI_OVERLAY` there); `take_controls`/
  `release_controls` (new, handover).
- `src/rules/gates.py` — `flight_handover` category (always `PASS`).
- `src/belief/voice_commands.py` — `HANDOVER_TOKENS`, checked in `classify_response` ahead of the
  ordinary floor comparison; `has_controls` keyword (default `False`, every other token untouched).
- `src/belief/speech.py` — `"TOO_SLOW"`/`"AI_OVERLAY"` reasons. The forced-handover/self-release
  line ("You have controls!") deliberately is **not** here — it lives in `decide_flight_control`,
  the one place both of its triggers meet (named in both modules' docstrings so the exception to
  "wording lives in speech.py/the rule file" is not mistaken for an omission).
- `src/body.py` — `_apply_flight_control` (sends the two one-shots, bumps `wire_seq`, re-sends
  `arm` every poll while `OVERLAY`/`unpark_take` — U10's lease; discards a stale transition/goal
  unsent if `phase` has already moved to `OVERLAY` by the time it runs — row 11's *other*
  direction, see Notable Discoveries); the row-11 fix proper, in `_apply_ai_pilot_wheel_goal`'s
  unparked branch (clears `ai_pilot_goal_transition`/`ai_pilot_level_flight_transition`/`ai_pilot_
  hvrt_transition`, previously left to persist while unparked); `run_once(flying=...)` (clamps
  `decide_optic`'s chosen optic to `UNAIDED_OPTIC`, the same external-clamp shape the pre-existing
  sight-not-ready cap already uses — U6); the `write_sight_target` call site gated on `not
  current_crew_state().has_controls` too (the plan's own explicit second instruction, belt-and-
  suspenders alongside the optic clamp); `last_ias_kmh` on `ConsolePerceptionRunner` (no existing
  field carried IAS); the main poll-loop wiring (`advance_flight_control_state` → `_apply_flight_
  control` → `crew_console.drain_flight_control`, right after mode 2's own three calls).
- `config/rules/flight.lua` — `turn_heading_relative`'s pattern becomes `turn <direction:left|
  right> [<degrees:angle>]` (no degrees → `flight.turn_continuous`); `you_have_controls`/`i_have_
  controls` move from category `"always"` (silent no-op) to `"flight_handover"` with real bodies.
- `config/rules/README.md` — the `flight_handover` category, the two new actions, `turn_
  continuous`, the "every `flight.*` action except three dispatches by mode" note.
- `tools/check_rules.py` — a third dry-run scenario, `"axes flying"` (`FlightControlState(phase=
  "ACTIVE", ...)` with every held/measured value known), alongside the pre-existing `"flying"`/
  `"hovering"` — so the `axes_*` bodies the rewritten `_by_mode` wrapper reaches are actually
  dry-run, not just the unchanged overlay ones.
- `CLAUDE.md` — the `flight_control.py` module-map entry, widened `ai_pilot_wheel.py` sentence for
  the unpark exception, four new invariants (no LAN axis value, neither handover token confirms,
  the two modes' one-shots never cross, park/unpark change the mode not who has the controls).
- `docs/STRUCTURE.md` — new `flight_control.py` entry; appended notes on `aircraft_client.py`/
  `body.py`/`crew_console.py`/`voice_commands.py`/`speech.py`'s existing entries.

### Tests Added

- `aircraft-layer/tests/test_flight_control_api.py` — schema/cache/routing/`GET` endpoint
  (mirrors `test_ai_pilot_wheel_api.py`) and `CommandSender.send_flight_control`/`POST` endpoint
  (mirrors `test_ai_pilot_goal.py`), including every shape-validation 400/503/500 case.
- `aircraft-layer/tests/test_flight_control_lua.py` — the whole module wrapped as an IIFE around
  the real source (not per-function extraction, since the functions close over many module-level
  locals), against a mocked DCS surface: bit-exact capture (pitch/roll and, separately, the
  measured pedal sign), a bad `limits` bound rejecting the whole message, a stale `seq` ignored,
  release stopping writes the same frame, a park edge self-arming with no write, the unpark-take
  refused `"disabled"` (Stage M1's own shipped state — `UNPARK_TAKE_ENABLED` is off), a stale
  lease, unpark-while-off writing nothing, the pause/huge-jump row holding, sustained-vs-momentary
  low IAS for the envelope release, and the `fc_axes_*` wire fields.
- `body-layer/tests/test_flight_control.py` — `advance_flight_control_state` against a real
  loopback server (mirrors `test_ai_pilot_wheel.py`'s own convention, not a mocked client);
  `take_controls`/`release_controls`'s every refusal and the refusal-order pin; `decide_flight_
  control`'s every transition, including **says spoken exactly once for the matching `take_seq`**
  (and a second poll against the now-`ACTIVE` state proving it is not repeated), **says withheld
  for a mismatched `take_seq`**, the ack timeout, and Lua's own self-release for all three reasons;
  the clamp/wire helpers.
- `body-layer/tests/test_body_flight_control.py` — `_apply_flight_control`'s own send/clear/`wire_
  seq`/arm-lease behaviour, and row 11's `_apply_flight_control`-side direction (a stale one-shot
  discarded, unsent, once `phase` has already moved to `OVERLAY`).
- `body-layer/tests/test_body_ai_pilot_wheel.py` — `test_unparking_clears_every_stranded_ai_pilot_
  one_shot`, row 11's *other*, pre-existing direction (the `ai_pilot_*` one), which had no
  dedicated assertion before this round even though the mechanism already existed in the merged-in
  refactor commit.
- `body-layer/tests/test_rules_flight_actions.py` — `TestHandoverActions` (replaces `TestHave
  ControlsNoOp`, whose own assertion is exactly what Decision 22 changes — see Notable
  Discoveries): the overlay no-op, a clean take, both refusals, the overlay `AI_OVERLAY` unable, a
  real release, and the nobody-flying no-op. `TestSeatNeverGatesMode1` (Decision 25): `flight_
  mode()`/`take_controls` give identical results across `player_seat` = pilot/operator/unknown.
- `body-layer/tests/test_rule_gates.py` — widened the closed-category-set test for `flight_
  handover`.
- `body-layer/tests/test_body.py` — `test_run_once_flying_clamps_the_optic_to_naked_eye` (U6, with
  its own un-clamped `flying=False` negative case, per root `CLAUDE.md`'s "show the red when your
  assertion is that nothing happens" — this is a clamp, not an absence, but the companion negative
  case is still what makes the positive one mean something); four pre-existing `run_once` test
  doubles updated for the new `flying=` keyword.
- `body-layer/tests/test_tuning_comment_renders.py` — no new test; an existing one caught a real
  defect (see Notable Discoveries).

**What M1 deliberately does not test, and why**: the `write_sight_target` call-site skip (the
second half of U6) has no dedicated poll-loop test — building a fixture that reaches `sight_head.
mode == "free"` through the real poll loop (OBSERV on, gyro aligned, a goal) is substantially more
setup than the `decide_optic`-level clamp test, and that clamp is what actually prevents glassing
from ever being requested while flying in practice (OBSERV is never commanded on if nothing ever
asks for a sight-tier optic). The call-site skip is defensive, not primary enforcement, and is
exercised live once Flight M-A happens, not here.

### Checks

**aircraft-layer**
- `luac5.1 -p` on every touched `.lua` file: pass. `GETGLOBAL` audit (`luac5.1 -l -p | grep
  GETGLOBAL`) on `flight_control.lua`/`ai_pilot_wheel.lua`/`commands.lua`/`Export.lua`: every name
  is either Lua stdlib, a genuine DCS API, or a `core.lua`-published/cross-module global — no own
  helper referenced before its own `local` declaration.
- `ruff format --check src tests`: pass. `ruff check src tests`: pass.
- `mypy src` (from inside `aircraft-layer/`): pass, no issues (28 source files).
- `pytest tests -q` (full subproject suite): **932 passed**.

**body-layer**
- `ruff format --check src tools tests`: pass. `ruff check src tools tests`: pass.
- `mypy src` (from inside `body-layer/`): pass, no issues (92 source files).
- `tools/check_rules.py --adapter-python <audio-adapter venv>`: `ok: 1 rule file(s) checked` — the
  new `[<degrees:angle>]` optional-numeric-slot pattern and every dry-run scenario (including the
  new "axes flying" one) passed with zero findings.
- `pytest tests -q -n auto -m "not slow"` (full subproject suite, parallel): **3581 passed, 4
  xfailed**.
- `tools/generate_defaults.py --write`; `test_tuning_defaults_toml.py`/`test_tuning_comment_
  renders.py`: pass, rendered `config/defaults.toml` read back by hand (not just the generator's
  own comment).

### Notable Discoveries

- **`ai_pilot_wheel.lua`'s own `push_ai_pilot_wheel_state` double-quotes every non-null string
  field on the wire, producing invalid JSON.** `text_or_null` wraps `json_escape_string`'s own
  already-quoted result in a second pair of quotes (`'"' .. json_escape_string(value) .. '"'`);
  `json_escape_string` already returns `"\"" .. escaped .. "\""`. Confirmed with `json.loads` on
  the exact malformed shape it produces. This is shipped, merged, mode-2 code — found only because
  I copied the same idiom into `flight_control.lua` and then actually ran the output through a
  real Lua interpreter and a real `json.loads`, which nothing exercising `push_ai_pilot_wheel_
  state` today does (no test calls it at all). **Not fixed in `ai_pilot_wheel.lua`** — out of
  scope for this module/stage; fixed in my own copy (`text_or_null` returns `json_escape_string`'s
  result directly, no extra quotes). Worth a dedicated fix/test for the existing module.
- **A real bug in my own first draft, caught by my own test before it ever reached review**: the
  original `run_flight_control` wrote the captured axes only from the branch that already saw
  `fc_mode == "active"` at the *start* of the frame — a fresh take (`"taking"` → `"active"` within
  the same call) transitioned the mode but fell through to `return` without ever calling `write_
  outputs()`, so the first write happened one frame late, not the same frame Decision 24 requires
  ("the output is continuous at take, bit-exact"). Fixed by factoring a shared `run_active_frame`
  helper, called both from the per-frame path and immediately after a fresh take/unpark-take
  transition in the same call. `TestCaptureIsBitExact` failed on the very first run with `written[
  2001]` as `nil` (a `string.format` crash, not a silently-wrong value) — exactly the kind of
  immediate, loud failure the project's own "counterfactual is evidence only if you ran it"
  guidance asks for, found by actually running the Lua rather than reasoning about it.
- **Two existing tests asserted exactly the behaviour Decision 22 replaces, and were rewritten, not
  extended** (`TestHaveControlsNoOp.test_you_have_controls_is_silent`/`test_i_have_controls_is_
  silent_while_flying_too`): their own premise — "you/i have controls" is a silent no-op in every
  state — is the pre-mode-1 behaviour the plan explicitly supersedes. Per the escalation rule on
  rewriting existing tests: this is not an architectural improvisation, it is the approved plan's
  own named behaviour change (Decision 22, already reviewed and `ALIGNED`), so I rewrote them
  (`TestHandoverActions`) rather than stopping to ask, and I am naming the rewrite here rather than
  letting it pass silently in a diff.
- **`test_tuning_comment_renders.py::test_no_cross_key_constraint_hides_after_the_first_sentence`
  caught a real instance of exactly what it exists to catch**: `MAX_IAS_KMH`'s tuning comment's
  *second* sentence named `FLOOR_AGL_M` (a cross-reference, not an actual coupling), which the
  generator cannot render (it emits only the first sentence) — reworded to drop the sibling-key
  mention rather than restate a real constraint there, since there was no real constraint to state.
- **The `wire_seq`-vs-`take_seq` split was not explicit in the plan and had to be designed**: the
  plan's own `goal_seq` language (mirroring mode 2's `AiPilotWheelGoal.goal_seq`) would, read
  literally, bump a *goal*-scoped counter that is a different quantity from the message-level
  `"seq"` field `Export.lua`'s `fc_last_cmd_seq` check applies across every `cmd` kind. Conflating
  them would mean a goal sent between a take and its confirmation could either go stale against
  the take's own `seq`, or move what the take's confirmation is compared against. Resolved by
  introducing `FlightControlState.wire_seq` as the one shared counter (bumped only in `body.
  _apply_flight_control`, never by any action) and keeping `take_seq` purely semantic. Documented
  in both the module's own docstring and the STRUCTURE.md entry so a later stage does not
  rediscover the trap by breaking it.
- **The M1/M2 boundary for the ten `axes_*` goal actions required a judgement call.** The plan lists
  "the mode-1 action methods" under M1's own `crew_console.py` bullet, but also lists "the full
  mode-1 action bodies, their clamps and readback values" under M2's `body-layer` bullet — an
  apparent overlap. Read as: M1 builds the dispatch mechanism (`_by_mode`) and working axes bodies
  (clamp, send a `FlightControlGoalRequest`, compute the readback from the clamped input), with
  `held_*`/`measured_*` sourced from Lua's own echoed/telemetry fields since M1 has no shaper to
  report a *tracked* value from; M2 is what makes those commanded values actually get flown toward.
  This reading is implemented and tested (`tools/check_rules.py`'s new "axes flying" scenario dry-
  runs all ten), but it is a judgement call on an ambiguous plan boundary, not an explicit
  instruction, and worth confirming at review.
- **`fc_measured_altitude`/`fc_measured_speed` are not named in the plan's own wire-shape text** —
  added alongside the plan's own `fc_measured_heading` so `hold_altitude`/`level_flight`/`set_
  speed`'s "current value" has something to read the instant mode 1 takes, before any goal has
  ever been commanded (`fc_goal_altitude`/`fc_goal_speed` both start `null`). Without this,
  `axes_hold_altitude`/`axes_level_flight` would `assert`-fail on the very first call after a
  fresh take. A small, mechanical, same-shape addition to an already-open wire message, not a
  reshape — flagged per the plan's own instruction to report additions beyond its explicit list.
- **The envelope release's `"dead"` cause has no real detection mechanism** — this codebase has no
  per-frame ownship-death/weight-on-wheels signal anywhere (confirmed by grep; `ON_GROUND_AGL_
  THRESHOLD_M`'s own docstring on the body-layer side names the same gap for a different check).
  `check_envelope` maps a failed `LoGetSelfData()` read onto `"dead"` as the closest available
  proxy, and an unreadable IAS/AGL on the unpark-take's own preconditions onto `"too_slow"`/`"on_
  ground"` respectively (fail-safe: "cannot confirm" is treated the same as "confirmed bad"). Both
  are judgement calls, not measurements, named here per the brief's own request to flag them.
- **Cross-key coupling check**: `MIN_IAS_KMH`/`MAX_IAS_KMH` have an implicit ordering invariant
  (`MIN_IAS_KMH < MAX_IAS_KMH`) that no per-key `lo`/`hi` bound sees — both default comfortably
  inside that ordering (80 < 280) and their `lo`/`hi` ranges (20–200, 100–500) cannot cross invert
  it via any single in-bounds override, so `tuning._check_scan_decay_coupling`'s own kind of guard
  was judged unnecessary this round; flagged per the project's own instruction on relationships
  between tunables, not guarded in code.
- **Deviation from the brief's own summary, not the plan**: the brief's step-by-step list named
  `turn_continuous`/`take_controls`/`release_controls` without stating they are **not** `_by_mode`-
  wrapped; the plan itself (Decision 21/22) makes this explicit (`turn_continuous` has no overlay
  body to dispatch to at all; the two handover actions are not per-mode at all). Implemented per
  the plan, as instructed where the two disagree.

### What is deliberately left for M2

The control law itself (the shaper, the lift-vector corrections, the inner loop, the toy-plant
tests) — M1's own output stage is captured + wobble, nothing else, and `flight_control.lua`'s own
module docstring says so. Concretely not built here: any Lua-side use of a commanded goal beyond
storing and echoing it (`fc_goal_*`/`fc_takeover_mode` are wire-only until M2's shaper exists); the
takeover-mode heading-vs-turn decision's own live tracking (snapshotted once at take, never
revisited); the terrain floor (`FLOOR_AGL_M` is sent in `limits` and clamped against in body-
layer's own `set_altitude`/`step_altitude`, but Lua does nothing with it — that is Stage M3); the
bands (`fc_in_band_*` always `null`, `SPEED_BAND_FRAC`/`ALT_BAND_FRAC`/`ALT_BAND_MIN_M`/`HEADING_
BAND_DEG` not declared — nothing computes "in band" without a shaper to converge). M0-D (the
stirred-control go/no-go for the whole mode) remains owed before this can merge, per U7.

### Addendum, flight 6 (2026-11-18)

Two more coordinator corrections arrived after the section above was written, both folded into
`flight_control.lua`'s own header/table comments rather than this log repeating the measurement:

- **Collective sign is -1.0, scale 1** (same shape as pedal), re-flown against the corrected 2087
  id. Entered into `SIGN`. **`FC_AXES_ENABLED.collective` was deliberately left `false`** — the
  coordinator's own wording was "M0-C passed **for sign/scale**," and pedal's enable flag was
  flipped only once its *whole* response (sign, scale, **and** step-response lag) was measured
  across two flights. Collective's own lag/VS response are still owed. Reading "sign/scale passed"
  as "enable the axis" would be inconsistent with the bar pedal was held to — this is a judgement
  call, not an instruction, and is flagged here and in the module's own comment for review to
  confirm or overturn.
- **M0-F is measured for collective: a release holds the last-written value until the player
  physically moves that control** (arg 1102 sat 16+ s untouched). This is exactly Decision 4's own
  prediction ("the release jump is not handled; the pilot matches his controls") — a measurement
  that confirms a documented assumption, not a correction to it. No code change: `handle_flight_
  control_command`'s `"release"` branch already does nothing but stop calling `write_outputs()` —
  it never reads the physical stick or holds a value on purpose, so there was nothing for this
  finding to invalidate. Pitch/roll/pedals' own M0-F measurement is still owed.

---

## Review-fix round, 2026-11-18 (`plans/flight-control/review-m1.md`, NEEDS REVISION)

Both Required Fixes.

### Files Changed

- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua` — **Required Fix 1**: the `"release"`
  branch of `handle_flight_control_command` now clears `fc_goal_heading_deg`/`fc_goal_turn`/
  `fc_goal_alt_m`/`fc_goal_alt_ref`/`fc_goal_ias_kmh`, matching what `on_stop` already does for a
  mission restart — a stale goal from a prior take no longer survives into the next one.
- `aircraft-layer/tests/test_flight_control_lua.py` — new `TestReleaseClearsHeldGoalsAcrossRetake`:
  take, command a heading/altitude/speed goal, release, take again, and check `push_flight_
  control_state`'s wire line at each step — the goal is held before release, every `fc_goal_*`
  field reads `null` immediately after release, and still `null` on the fresh re-take before any
  new goal is commanded.
- `body-layer/tests/test_voice_commands.py` — **Required Fix 2**: five new tests on
  `classify_response`'s `HANDOVER_TOKENS` branch (Decision 13), named directly after the plan's own
  "at every confidence" wording: `i_have_controls` acts at every confidence from `0.0` to `1.0`;
  `you_have_controls` acts from `CONFIRM_FLOOR` up; `you_have_controls` says again (never confirms)
  below the floor; the ambiguous handover pair resolves on `has_controls` alone, at every
  confidence, both the `has_controls=True` (acts `i_have_controls`) and `has_controls=False`
  (says again) directions.

### Checked, no code change needed

- **The body-layer side of Required Fix 1's leak.** `FlightControlState.held_heading`/`held_
  altitude`/`held_altitude_ref`/`held_speed` are not an independent cache — `advance_flight_
  control_state` replaces them wholesale from the latest wire sample every poll
  (`replace(state, held_heading=_as_optional_float(sample.get("fc_goal_heading")), ...)`, no
  previous-state carry-through for these four fields), and `CrewConsole.flight_control_state`
  holds no separate copy either (confirmed by reading both — `crew_console.py`'s own field is
  populated from `advance_flight_control_state`'s return value, nothing else writes it). So once
  Lua's `fc_goal_*` clears on release, the mirror clears on the very next poll with no second fix
  needed on this side — the leak was Lua-only, and the review's own "check the body-layer side"
  came back negative.

### Checks

**aircraft-layer/**
- `luac5.1 -p` on `flight_control.lua`/`ai_pilot_wheel.lua`/`commands.lua`/`Export.lua`: pass.
- `GETGLOBAL` audit (`luac5.1 -l -p flight_control.lua | grep GETGLOBAL`, the only touched `.lua`
  file this round): every name stdlib, a genuine DCS API, or a cross-module global already named
  in the module's own docstring — nothing new.
- `ruff format --check src tests`: pass (84 files). `ruff check src tests`: pass.
- `mypy src`: pass, no issues (28 source files).
- `pytest tests -q` (full subproject suite): **933 passed** (932 + the new
  `TestReleaseClearsHeldGoalsAcrossRetake` test).

**body-layer/**
- `ruff format --check src tools tests`: pass (241 files; `ruff format` auto-wrapped one new test's
  long signature on the first run, re-checked clean, and the function was renamed shorter rather
  than left with the wrapped `-> (\n    None\n)` shape).
- `ruff check src tools tests`: pass.
- `mypy src`: pass, no issues (92 source files).
- `pytest tests/test_voice_commands.py -q -v`: **29 passed** (24 + 5 new, confirmed by name in
  unfiltered `-v` output).
- `pytest tests/test_flight_control.py tests/test_body_flight_control.py tests/
  test_rules_flight_actions.py -q`: **97 passed** (the modules review-m1.md's Required Fixes
  touch most directly).
- `pytest tests -q -n auto -m "not slow"` (full subproject suite, parallel): **3586 passed, 4
  xfailed** (3581 + 5 new; the 4 xfailed are pre-existing, unrelated).

A counterfactual was run on Required Fix 1's own new test before trusting it: reverted the
`"release"` branch's new five-line clear, re-ran `TestReleaseClearsHeldGoalsAcrossRetake` alone,
confirmed it failed for the stated reason (`fc_goal_heading` read back `"90.00000"` instead of
`None` immediately after release), restored the fix, confirmed the file's `sha256` matched the
pre-mutation value exactly before re-running the full suites above.

### Notable Discoveries

- None beyond the "checked, no code change needed" item above — this round is a narrow fix plus
  the two named tests, no scope beyond review-m1.md's Required Fixes.

---

## M0-J capture-rule fixes, 2026-11-18 (coordinator, flight 9 findings)

From `aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md` (branch `probe/bl16-
flight-axes`), "Flight 9": two capture-timing bugs, both confirmed and fixed in the same round as
the review-fix work above, plus `UNPARK_TAKE_ENABLED` flipped on now that M0-J passes.

### Files Changed

- `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua` — new read-only getter
  `M.stick_park_raw()` (mirrors `ai_pilot_takeover.raw_arg852`, already tracked every frame by
  `run_ai_pilot_wheel`). `M.player_seat`'s own docstring corrected in place — it documented itself
  as read by `flight_control.lua`'s capture-source rule, which this round's fix 2 removes; the
  function and its export are unchanged (kept for diagnostics), only the now-false claim in the
  comment was pruned.
- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua`:
  - **Finding 1 (unpark-take capture timing)**: new `STOWED_THRESHOLD` (0.99) and
    `fc_last_stowed_pilot_capture`, tracked every frame while `fc_mode == "armed"` — overwritten
    only on a frame `stick_park_raw() >= STOWED_THRESHOLD`, left alone otherwise (so it survives
    through the ~1.5 s cross-fade `is_parked()`'s own lower, 0.9 edge fires inside). The unpark-take
    branch reads this tracked snapshot instead of a fresh `capture_from_seat("pilot")` at the edge;
    falls back to a fresh read only if no frame ever reached the threshold this armed session.
    Cleared (same "stale leak across a session boundary" class as review-m1.md Required Fix 1) on:
    entering `armed` fresh (self-arm), every unpark-take refusal branch, a successful unpark-take
    (consumed), `"release"`, and `on_stop`.
  - **Finding 2 (voice-take capture source)**: `resolve_capture_seat(hint)` (Decision 25's
    "the player's seat set") replaced outright by `resolve_capture_values()` — the camera seat is
    never read for this decision any more. New `LIVE_SEAT_ZERO_EPS` (0.01) and
    `update_live_seat_tracking()` (called every frame regardless of `fc_mode`, since a take can
    land on any frame) track `fc_last_steady_values`, the captured set from the last frame exactly
    one seat read live and the other idle. `resolve_capture_values()` captures whichever seat
    currently reads live alone; if both read live at once (an actual cross-fade), returns the
    tracked steady snapshot instead of either set's own partly-faded current value; falls back to
    the higher-magnitude seat (the old default) only if neither has ever been steady.
  - **`UNPARK_TAKE_ENABLED` flipped from `false` to `true`** (coordinator direction) — M0-J passes
    with the capture-timing fix above. Kept as a named flag, not removed, so a live regression can
    still disable the unpark take without a redeploy; its own refusal branch and `fc_refuse_cause =
    "disabled"` are untouched.
  - Module docstring updated: the `ai_pilot_wheel` dependency list now names `stick_park_raw`
    instead of `player_seat` (no longer read), and a new paragraph states both corrected capture
    rules up front, citing the finding by name rather than re-deriving it.
- `aircraft-layer/tests/test_flight_control_lua.py`:
  - Preamble: `ai_pilot_wheel` mock gained `stick_park_raw = function() return ap_stick_park_raw
    end`, mirroring `ap_parked`/`ap_seat`'s existing driver-settable-global convention.
  - `TestCaptureIsBitExact.test_unpark_take_is_refused_disabled_in_stage_m1` → rewritten as
    `test_unpark_take_succeeds_with_the_flag_on_by_default` (the flag's default flipped; the old
    test's own premise — the unpark take cannot be exercised through this module's public interface
    — is exactly what this round changes). Per the escalation rule on rewriting existing tests: this
    is the approved coordinator change, not an improvisation, named here rather than left silent in
    the diff.
  - `TestUnparkTakeRefusals`'s two existing tests updated: both previously asserted
    `fc_refuse_cause == "disabled"` (the flag masking every other precondition); now assert the
    precondition's own real cause (`"too_slow"`, `"lease"`) since the flag no longer masks them.
    New `test_refusal_still_available_via_the_flag` pins that the `"disabled"` cause and the `true`
    default both still exist in the source, since the constant has no exported test seam and should
    not get one for a one-line kill-switch.
  - New `TestUnparkTakeCaptureTiming` (3 tests): the tracked last-fully-stowed capture is used
    rather than the faded edge-frame read; a seat-gate edge (no fade) needs no special case and gets
    the same tracked value; the tracked capture does not leak into a later armed session that never
    itself reached the threshold.
  - New `TestVoiceTakeLiveSeatCapture` (2 tests): the live pilot set is captured with the camera in
    the operator seat (the measured flight-9 scenario, operator set at 0, pilot set live); a
    cross-fade at the exact moment of take resolves to the last steady set, not either set's own
    partly-faded current read.

### Checks

**aircraft-layer/**
- `luac5.1 -p` on `flight_control.lua`/`ai_pilot_wheel.lua`/`commands.lua`/`Export.lua`: pass.
- `GETGLOBAL` audit on both touched files: every name stdlib, a genuine DCS API, or an existing
  cross-module global (`ai_pilot_wheel`, `WHEEL_CENTER_BUTTON`/`WHEEL_MENU_BUTTON`) — nothing new.
- `ruff format --check src tests`: pass (84 files). `ruff check src tests`: pass.
- `mypy src`: pass, no issues (28 source files).
- `pytest tests/test_flight_control_lua.py tests/test_ai_pilot_wheel_lua.py tests/
  test_ai_pilot_wheel_api.py -q`: **124 passed**.
- `pytest tests -q` (full subproject suite): **939 passed** (933 + 6 net new: the two
  `TestUnparkTakeRefusals` tests kept their names and gained one sibling, plus 3 +
  2 new classes).

Not re-run: body-layer (no body-layer file touched this round; `UNPARK_TAKE_ENABLED` is a pure
Lua-side flag and `fc_refuse_cause`'s body-layer handling is generic over whatever string Lua
sends, confirmed by reading `decide_flight_control` and `test_flight_control.py`'s own
`lua_refuse_cause="disabled"` fixture, which is illustrative, not testing the Lua default).

Two counterfactuals were run before trusting the new tests: (1) reverted the unpark-take branch to
read `capture_from_seat("pilot")` directly (dropping the tracked snapshot), re-ran
`test_captures_the_last_fully_stowed_frame_not_the_faded_edge` alone, confirmed it failed for the
stated reason (`0.085` instead of `0.133`); (2) reverted the `"taking"` branch to the old
hint-first capture (`capture_from_seat(seat_hint or "pilot")`), re-ran `TestVoiceTakeLiveSeatCapture`
alone, confirmed both tests failed for the stated reason (`0.149`/`0.151` instead of the live/steady
values). Both reverts restored by hand and `sha256` confirmed to match the pre-mutation value
exactly before re-running the full suite above.

### Notable Discoveries

- **`M.player_seat` (`ai_pilot_wheel.lua`) is now unread by any in-process Lua caller** — confirmed
  by `grep -rn "player_seat" aircraft-layer/dcs-export` after this round's change: the only call
  site was `flight_control.lua`'s own old `resolve_capture_seat`, now gone. Kept exported rather
  than removed (diagnostics / a future caller), with its docstring corrected rather than deleted —
  judgement call, flagged for review to confirm or remove outright.

## Mode 1, Stage M2 (the controller), 2026-11-18

From `plans/flight-control/plan.md`, "Revised 2026-11-18 — mode 1 (unparked, raw axes) re-cut",
Stage **M2 only**: the Lua control law (shaper, lift-vector corrections, inner tilt loop, pedal
coordination) plugged into M1's own per-frame output stage, plus body-layer's shaper-limit/band
tunables and their `in_band_*` status mirrors. M3 (terrain floor) and M4 (SAU) are not built here.
Base: HEAD (`59192cfa`) was not an ancestor of the dispatched tip (`a2450e34`), so this round
started from `git checkout -B m2-impl a2450e34` per the dispatch's own fallback instruction, then
committed to that branch.

### Files Changed

**aircraft-layer**
- `dcs-export/Petrobrain/flight_control.lua` — the control law, as five pure functions over an
  explicit state table (`law_init_at_take`, `law_apply_goal`, `law_update`, `law_outputs`, plus the
  helpers `law_wrap360`/`law_wrap180`/`law_clamp`/`law_turn_rate_at_bank`/`law_stopping_height`),
  none of which reads a module-level local or a DCS global — the plan's own instruction ("as pure
  functions over a state table so luajit can test them"), exported on `M` for the toy-plant suite.
  `fc_law` (module state, `nil` off/taking/armed) is built at take/unpark-take (`law_init_at_take`,
  seeded from the sign-mapped captured command so the very first frame's output equals it exactly —
  Decision 24's "bit-exact at take" — via a dedicated `just_took` branch in `run_active_frame` that
  skips the shaper update for that one frame) and advanced every subsequent frame (`law_update` then
  `law_outputs`). `apply_goal_fields` now also calls `law_apply_goal` once per goal command (never
  re-applied from the persisted `fc_goal_*` wire echo every frame — see Notable Discoveries for why
  that distinction matters for `level_off`). `write_outputs` is rewritten to take an explicit
  command table and `dt`, rate-limiting against `fc_last_command` (`OUTPUT_RATE_LIMIT_PER_S`) before
  saturating/wobbling/writing; the pause row now re-issues `fc_last_command` unchanged (`dt=nil`)
  rather than `fc_captured`, freezing every shaper/integrator as the plan requires. New getter
  reads: `LoGetAngularVelocity` (p/q/r, with the yaw-rate sign flip M0-A measured — "positive when
  heading decreases"), `LoGetVerticalVelocity`, `LoGetTrueAirSpeed`, `LoGetAltitudeAboveSeaLevel`
  (for a continuously-converted barometric-to-AGL altitude goal), all gathered once per frame by a
  new `read_measured()`, fail-soft to 0.0/the ias-derived fallback on a bad read (the envelope check,
  run separately, is what actually stops the override on real trouble). `fc_in_band_heading/
  altitude/speed` now read `fc_law`'s own fields instead of the hard-coded `null`. A new "M2 control
  law constants" comment block holds every gain (`OMEGA_HEADING/ALT/SPEED`, `K_THETA/PHI/Q/P/
  THETA_I/PHI_I`, `K_COLLECTIVE`, `K_TILT_FROM_AX/AZ_SATURATED`, `K_BANK_INCREMENT`, `K_HEADING_
  TRACK`, `K_VS_ERROR/ALT_ERROR/SPEED_ERROR`, `K_PEDAL_FROM_COLLECTIVE_RATE`, the pedal limits/near-
  limit collective-rate cap, `TAU_ACCEL_FILTER_S`, `OUTPUT_RATE_LIMIT_PER_S`, `T_ROLL`,
  `TURN_SETTLE_DEG_S`) — every one a first-cut placeholder, M0-E never having flown; the module's own
  header names the "owed by M0-E" list. `fc_limits`/`FC_LIMIT_BOUNDS` gain the eight new wire keys
  (`max_turn_bank_deg`, `max_climb_vs_mps`, `max_accel_mps2`, the four A9 bands, `heading_band_deg`).
  Every mode transition away from `active`/`taking` (`release`, the park self-arm, the envelope
  release, `on_stop`) now also clears `fc_law`/`fc_last_command`, so a later take always rebuilds the
  law from scratch rather than resuming a discarded session's state. Module docstring and the status-
  push comment rewritten (both were M1-only and now stale — root `CLAUDE.md`'s "prune the comment
  you are standing next to").
- `src/api/server.py` — `_FLIGHT_CONTROL_LIMITS_BOUNDS` gains the same eight keys (see Notable
  Discoveries — this was a real, caught bug: the dict is a *whitelist* the `POST /command/
  flight_control` handler's own loop reads, so a wire key absent from it is silently dropped before
  ever reaching `CommandSender`, not rejected).
- `tests/test_flight_control_lua.py` — the shared mock preamble (`_PREAMBLE`) gains `LoGetAngular
  Velocity`/`LoGetVerticalVelocity`/`LoGetTrueAirSpeed`/`LoGetAltitudeAboveSeaLevel` and a mutable
  `pitch_rad` (previously hard-coded `0.0` in `LoGetADIPitchBankYaw`'s mock), all defaulting to
  values that reproduce the old (M1) readings exactly — no existing assertion changed, only the new
  code path's getters are no longer `nil`. All 23 pre-existing tests pass unmodified.
- `tests/test_flight_control_law.py` (new) — the toy-plant suite the plan asks for, against the five
  exported pure law functions directly, no DCS mock at all. See "Tests Added".
- `tests/test_flight_control_api.py` — two new tests pinning the M2 limits-passthrough fix (see
  Notable Discoveries).

**body-layer**
- `src/belief/flight_control.py` — eight new `tuning.py` constants under `[belief.flight_control]`
  (`MAX_TURN_BANK_DEG`, `MAX_CLIMB_VS_MPS`, `MAX_ACCEL_MPS2`, `SPEED_BAND_FRAC`, `ALT_BAND_FRAC`,
  `ALT_BAND_MIN_M`, `TURN_RATE_BAND_FRAC`, `HEADING_BAND_DEG`), each with its own `#:` comment (not
  one shared block — see Notable Discoveries for why that matters); `flight_control_limits()` sends
  all eight; `FlightControlState` gains `in_band_heading`/`in_band_altitude`/`in_band_speed` (mirrors
  of `fc_in_band_*`, via a new `_as_optional_bool` helper), refreshed by `advance_flight_control_
  state`. No action in this module reads them yet (A9: the bands feed only the status field and
  M4's settle test) — mirrored anyway since every other wire status field already is, at no real
  cost.
- `config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`); the rendered first
  sentences were read back by hand per the standard instruction.

### Tests Added

- `aircraft-layer/tests/test_flight_control_law.py` (new, 11 tests) — the toy-plant suite:
  - `TestBitExactAtTake` — `law_outputs` on a freshly-initialized state reproduces the captured
    command exactly even with nonzero body rates at the instant of capture (the degenerate
    all-zero-rates case the full-module harness already covers would not catch a sign error in the
    `T_p = command + K_Q*q` solve); the disabled-collective-defaults-to-zero case.
  - `TestTakeoverModeSelection` — 4.9° picks heading mode, 5.1° picks turn mode (Decision 1
    REVISED's own boundary, pinned exactly as the plan's own toy-plant bullet names it).
  - `TestHeadingChannel` — a toy plant (bank first-order-lags toward `phi_d`, heading integrates the
    resulting coordinated-turn rate) converges into the heading band, turns at most once (no
    ringing), and the mean error over the last 10% of the run is below the first 10%.
  - `TestClimbTakeoverStoppingHeight` — the stopping-height goal is ahead of capture in the climb
    direction (and behind it for a descent); a dedicated overshoot test (see Notable Discoveries for
    why this is "overshoot stays inside the band," not a blanket "never reverses").
  - `TestSpeedChannel` — converges into the speed band against a pitch-driven toy plant.
  - `TestLevelOffSettlesToHeadingMode` — a continuing turn, then `turn=0`, rolls out and the law
    switches internally to heading mode holding the settle heading (Decision 12's own "without a
    reversal").
  - `test_file_parses_without_a_lua_interpreter_too` — `luac5.1 -p` sanity, mirroring the sibling
    file's own copy.
- `aircraft-layer/tests/test_flight_control_api.py` — `test_m2s_shaper_limits_and_bands_forward_
  when_in_bounds`, `test_an_m2_limits_field_beyond_its_bound_returns_400` (the caught bug, see
  Notable Discoveries).
- `body-layer/tests/test_flight_control.py` — `test_flight_control_limits_carries_m2s_shaper_
  limits_and_bands` (every new key present and typed); the `in_band_*` fixture/assertions added to
  `TestAdvanceFlightControlState.test_a_sample_is_parsed_into_the_mirrors`.

**Counterfactuals run, restored by `shasum` before/after, never by eye:**
1. `src/api/server.py`: reverted the `_FLIGHT_CONTROL_LIMITS_BOUNDS` addition, re-ran the two new
   `test_flight_control_api.py` tests alone — both failed for the stated reason (`sender.sent ==
   [(1, "take", {}, None)]` instead of the full dict; a 999°/60° out-of-bound value returning 200
   instead of 400). Restored; sha matched; full suite re-run green.
2. `body-layer/src/belief/flight_control.py`: reverted the three `in_band_*` assignments in
   `advance_flight_control_state`, re-ran `test_a_sample_is_parsed_into_the_mirrors` alone — failed
   for the stated reason (`None` instead of `True`). Restored; sha matched; full suite re-run green.

### Checks

**aircraft-layer**
- `luac5.1 -p` on every touched/new `.lua` file: pass. `GETGLOBAL` audit on `flight_control.lua`
  (`luac5.1 -l -p | grep GETGLOBAL`): every name is Lua stdlib, a genuine DCS API, or a `core.lua`/
  cross-module global — no own helper (`law_*`, `axis_command`, `read_measured`) referenced before
  its own `local`.
- `ruff format --check src tests`: pass. `ruff check src tests`: pass.
- `mypy src` (from inside `aircraft-layer/`): pass, no issues (28 source files).
- `pytest tests -q` (full subproject suite): **952 passed** — 939 before this round's own changes
  (measured directly, a full run right after the Lua law was wired in but before any new test file
  existed) plus 13 new tests this round: 11 in the new `test_flight_control_law.py` toy-plant suite
  and 2 in `test_flight_control_api.py` (the M2-limits-passthrough fix's own pin). 939 + 13 = 952,
  confirmed by an intermediate run at 950 (939 + the 11 toy-plant tests, before the 2 API tests were
  added).

**body-layer**
- `ruff format --check src tools tests`: pass. `ruff check src tools tests`: pass.
- `mypy src` (from inside `body-layer/`, with `PYTHONPATH=../world-model/src`): pass, no issues (92
  source files).
- `pytest tests -q -n auto -m "not slow"` (full subproject suite, parallel): **3587 passed, 4
  xfailed**. `test_flight_control.py` alone (after this round's two new tests —
  `test_flight_control_limits_carries_m2s_shaper_limits_and_bands` and the `in_band_*` fixture/
  assertion addition to `test_a_sample_is_parsed_into_the_mirrors`): 31 passed.
- `tools/generate_defaults.py --write` / `test_tuning_defaults_toml.py` / `test_tuning_comment_
  renders.py`: pass, rendered `config/defaults.toml` read back by hand.

### Notable Discoveries

- **A real bug, caught by writing the toy-plant altitude test, not by reasoning about the formula**:
  `law_init_at_take`'s stopping-height goal originally called `law_stopping_height(h, w, limits.
  max_climb_vs_mps)` — the plan's own formula ("h + w·|w|/(2·A_v)") needs the channel's
  *deceleration* capability (`ALT_ACCEL_CAP_MPS2`, 1.0) for `A_v`, not the velocity *ceiling*
  (`max_climb_vs_mps`, 5.0). With the wrong divisor the computed goal (201.6 m for a 200 m/4 m/s
  climb) asked for more deceleration than the channel's own accel cap could deliver, so the toy
  plant — run with the real accel-capped shaper — overshot that wrong goal by several metres before
  settling back down: an actual reversal, the exact defect the plan's own "no reversal in `h_ref`"
  bullet exists to catch. Fixed by passing `ALT_ACCEL_CAP_MPS2` instead; confirmed by re-running the
  same scenario (goal now 208 m, matching the hand-worked figure, overshoot reduced to well under a
  metre).
- **A fixed-gain critically-damped shaper cannot generally guarantee zero overshoot against a
  velocity-dependent target, even with the right divisor.** Even after the fix above, the altitude
  toy-plant test still showed a small overshoot (~0.3–0.4 m past the 200–208 m goal, worked example
  in the test file) for a realistic initial climb rate. The algebra: for the formula `a_ref =
  ω²·err − 2ζω·v`, there exists a ω that exactly matches the stopping-distance physics for *one*
  specific initial velocity, but the stopping-height goal itself scales with `v²` while the matching
  ω scales with `1/v` — so one fixed ω cannot zero the overshoot for every climb rate the aircraft
  might be in when taken over. `OMEGA_ALT` was raised from its first value (0.2 → 0.5 rad/s) for
  *less* overshoot, not because 0.2 crossed the ≥10 m-floor pass criterion — review-m2.md's
  counterfactual (reverting to 0.2 and rerunning `test_flight_control_law.py` at the plan's own
  tested climb rates, plus the shaper's own 5 m/s ceiling) found 0.2 already well under that floor
  (2.4 m overshoot at every rate tried, against a ~20.8–21.25 m band) and the existing test passing
  at both gains (11/11). The toy-plant test asserts the plan's own alternative, equally-valid pass criterion ("any
  overshoot stays inside the band") rather than a blanket "never reverses," which placeholder gains
  cannot promise in general; 0.5 is a reasonable judgement call for less overshoot, all else equal,
  not a value `0.2` demonstrably fails at this scale. Flagged for Flight M-A/M0-E: either a
  materially higher `OMEGA_ALT`, or (if the user wants a stricter guarantee) a velocity-scaled
  target/gain is a design change beyond this stage's scope.
- **A second real bug, caught the same way, in `src/api/server.py`, not in the Lua or Python
  `flight_control` modules**: `_FLIGHT_CONTROL_LIMITS_BOUNDS` (the `POST /command/flight_control`
  handler's shape-validation dict) is iterated as a *whitelist* — `for field, (lo, hi) in
  _FLIGHT_CONTROL_LIMITS_BOUNDS.items(): if field not in limits_raw: continue` — so a `limits` key
  absent from this dict is never copied into the forwarded `limits`, with no error raised at all.
  Body-layer's new eight wire keys would have been silently dropped at this one layer (api.server),
  never reaching `CommandSender`/`Export.lua`, while every other check (body-layer's own tuning
  bounds, Lua's own `FC_LIMIT_BOUNDS`) would have looked correct in isolation — this is exactly the
  "enumerate the containing unit before fixing" lesson: a `grep` for "flight_control" bounds in the
  Lua module alone would never have surfaced this second, independent enumeration. Caught only by
  tracing the actual wire path end-to-end and writing a test against the real `POST` endpoint (not
  just `CommandSender` in isolation, which the existing tests already exercised and which gave no
  signal of the problem since it only forwards whatever `limits` dict it is handed).
- **The `wire_seq`-vs-per-frame-goal-re-application boundary needed a design decision not explicit
  in the plan.** `apply_goal_fields` must call `law_apply_goal` exactly once per actual goal command
  — never by re-reading the persisted `fc_goal_heading_deg`/`fc_goal_turn` wire-echo locals every
  frame — because `level_off`'s own internal turn-mode-to-heading-mode transition (triggered inside
  `law_update` once `r_ref` settles) would otherwise be immediately undone the very next frame by
  the still-persisted `fc_goal_turn = 0` being re-applied as a fresh "go to turn mode, r_goal=0"
  command. Resolved by having `handle_flight_control_command`'s own `"goal"` branch call `law_apply_
  goal` directly with the just-extracted local fields (never the module-level echo), and by making
  `level_off`'s own settle transition purely internal to `law_update`'s returned state (it never
  touches the module-level `fc_goal_*` locals at all). Not named in the plan; flagged per the brief's
  own instruction to report a design decision an ambiguous plan boundary required.
- **A goal commanded before capture completes (during `"taking"`) is not applied to the law at
  all** — `fc_law` is `nil` until `law_init_at_take` runs, and `run_active_frame`'s `just_took`
  branch does not read the pending `fc_goal_*` echo into the freshly-created law state. In practice
  this window is at most one frame (`"taking"` normally resolves on the very next frame the capture
  succeeds), and body-layer's own `held_*` HOLD-until-known gates block a goal action before `active`
  is confirmed, so this should not be reachable from a real voice command — but it is a real,
  documented simplification, not a verified impossibility, and is named here per the brief's own
  instruction on consequential design calls.
- **No slip-ball feedback in the pedal channel.** `LoGetSlipBallPosition` exists (confirmed present
  in the DCS Control API reference), but no probe (including M0-A) ever read it, so its return
  shape/units are unknown; guessing a unit conversion risked a wrong-sign pedal command, which is
  worse than omitting the term entirely. The pedal axis runs on the collective-coupling feedforward
  (`K_PEDAL_FROM_COLLECTIVE_RATE`) alone. Owed by a slip-ball probe, separate from M0-E's own gain
  measurements.
- **Every gain in the new "M2 control law constants" block is a first-cut placeholder, M0-E never
  having flown** — `OMEGA_HEADING/ALT/SPEED`, every `K_*` gain, `T_ROLL`, the pedal limits, the
  accel filter time constant, the output rate limit. All are named in the module's own header
  comment rather than scattered; Flight M-A and M0-E (if it is ever flown) retune them. This is the
  plan's own explicit framing ("written against an unmeasured plant... the gains, limits and signs
  are placeholders"), not a gap introduced here.
- **`sortie-log-triage`'s flight-trace section (time-to-band, time-in-band, zero crossings) was
  not built in this round.** The plan names it under "Flight M-A" (the acceptance flight card, after
  M1+M2 merge), not under M2's own bullet list — ambiguous which stage owns it, and per the brief's
  own instruction ("if ambiguous, note it and leave it"), left unbuilt. It is also, structurally, a
  skill-file edit (`.claude/skills/sortie-log-triage`), which this project's own workflow routes
  through its own worktree/branch (root `CLAUDE.md`, "Workflow" — non-code, cross-cutting updates),
  not bundled into a feature branch's commits — a second reason to leave it for its own pass rather
  than build it here.

## M2 review-fix round (`review-m2.md`)

Three items, all fixed on `m2-fix` (branched from `review-m2.md`'s tip `f78d90af`, read in full
first against `plan.md`'s Decisions 18/21–25 and the control-law section).

**Required Fix 1 — a goal commanded during the one-frame `TAKING` window was silently dropped,
with a false-confirmation readback.** Chose the first of the review's two named alternatives: hold
the queued goal in `body.py`'s `_apply_flight_control` until `state.phase == "ACTIVE"`, rather than
sending it while `TAKING` (symmetric with the `held_*` gates' own "wait for a law to exist"
posture) — not the Lua-side alternative (reading a pending `fc_goal_*` echo inside
`law_init_at_take`'s own caller), because the body-side fix needs no change to `Export.lua`'s
state machine at all, and the three phases a pending goal can be caught in (`TAKING` → hold and
retry next poll; `ACTIVE` → send as before; `PILOT`, reached only if the take's own ack times out
first → drop, there is no law for that `take_seq` to apply it to) are already distinct fields body-
layer tracks. Updated the stale comment this exact bug sat under in `apply_goal_fields`
(`flight_control.lua`) — it asserted a goal arriving before capture "is not expected in practice",
which review-m2.md's own trace (the absolute-set `axes_*` actions gate on `has_controls` alone,
already true at `TAKING`) disproved; it now says body-layer holds the goal instead.

Tests added in `test_body_flight_control.py` (`TestApplyFlightControl`): one per phase outcome —
held-not-sent during `TAKING`, sent on the next poll once `ACTIVE`, dropped once `PILOT`.
Counterfactual-checked by reverting the `body.py` fix (byte-for-byte, confirmed by `shasum` before/
after) and confirming all three go red, then restoring. The two pre-existing tests that happened to
exercise the goal-send path from `FlightControlState`'s *default* `phase="PILOT"` (an artifact of
the test not setting phase at all, not a realistic scenario — a pending goal action only exists
once `has_controls` is true) were updated to `phase="ACTIVE"`, the phase a goal send is actually
reachable from.

**Required Fix 2 — `TestPauseRowHolds` asserted a write happened, not that it was unchanged.**
Both of its tests were weak the same way (`written[2001] ~= nil`). Strengthening them needed a real
tracking error to move against during the "paused" frame, since the take's own captured state has
zero error against its own at-take goal (every reference starts exactly at the measured value) —
a mutated, un-frozen `law_update` would be a mathematical no-op against that input and the test
would never go red. Added a heading-goal command (90°, against the zero-heading mock) between the
take and the paused frame, and compared the roll/pitch written values before and after the pause
within two wobble steps (`0.0021`; `write_outputs`'s alternating ±0.001 parity means consecutive
writes of the *same* frozen value legitimately differ by up to one step each, so exact equality
cannot be the assertion). Confirmed empirically (`luajit`, not just read): the unmutated code gives
written roll `0.199`→`0.201` (within tolerance); the reviewer's exact mutation (`law_update(fc_law,
0.5, ...)` in the pause branch, writing its result) gives `0.199`→`0.771` — both the new and the
pre-existing huge-frame-jump test now fail under that mutation, confirmed by applying it to a
working copy, running, then restoring and matching the pre/post `shasum`.

**Documentation accuracy — `OMEGA_ALT`'s Notable Discoveries entry.** Reworded to state what the
review's counterfactual actually measured (0.2 already well under the floor at every climb rate
tested; 0.5 only reduces overshoot further), not that 0.2 crossed a pass/fail line it demonstrably
did not, per review-m2.md's own table. No gain changed — this is a wording-only fix, as the review
asked.

### Checks (this round)

Both subprojects' commands rerun from a clean working tree after the three fixes:
- **aircraft-layer**: `ruff format --check`/`ruff check` pass; `mypy src` — 28 files, no issues;
  `.claude/scripts/fast-tests.sh aircraft-layer` — 821 passed; the three flight-control-specific
  test files — 68 passed (unchanged count: the two strengthened tests replace, not add); `luac5.1
  -p` on `flight_control.lua` — pass.
- **body-layer**: `ruff format --check`/`ruff check` pass; `mypy src` (`PYTHONPATH=../world-model/
  src`) — 92 files, no issues; `.claude/scripts/fast-tests.sh body-layer` — 2814 passed (2811 + the
  3 new `TestApplyFlightControl` cases), 4 xfailed.

### Notable discoveries (this round)

- The two pre-existing `test_body_flight_control.py` cases that silently relied on `FlightControl
  State`'s default `phase="PILOT"` to exercise the goal-send path are the kind of gap `plan-aligner`
  /this role's own "treat the plan's test-impact list as a hypothesis" step exists to catch —
  `review-m2.md`'s required-fix list named neither test, and both would have gone stale (still
  green, no longer testing what their name says) the moment Required Fix 1 landed, had they not
  been found by grepping every `FlightControlState(` construction site in the touched test file
  rather than trusting the review's own enumeration.

## M1+M2 perf/security change-request round

Three fixes, from `plans/flight-control/perf-m1-m2.md` finding 1 (NOW) and `plans/flight-control/
security-m1-m2.md` Findings A and B, per the main loop's own dispatch decisions.

**Perf finding 1 — `check_envelope`/`read_measured` each read `LoGetSelfData`/`LoGetIndicated
AirSpeed`/`LoGetADIPitchBankYaw` independently, every active frame.** Reordered `run_active_frame`
(`flight_control.lua`) to call `read_measured()` first and pass its result into `check_envelope(t,
measured)`, which no longer makes any `LoGet*` call of its own — eliminating the duplication
entirely (the mitigation's own suggested fallback, "one redundant `LoGetSelfData` call instead of
three," turned out unnecessary, since `read_measured` already makes that exact call for `psi_deg`).
The one subtlety: `read_measured`'s own fail-soft policy (zero a bad `ias_mps`/`bank_rad` read
rather than propagate `nil`/NaN into the law) is the *wrong* policy for `check_envelope`'s own "a
bad read means release, with a specific cause" job — reusing the zeroed values directly would have
turned an immediate `"nan"` release into a slow `"envelope"` release once the zeroed IAS crossed the
low-speed margin, a real behaviour change, not a pure refactor. Fixed by having `read_measured`
also return `self_data_ok`/`ias_valid`/`bank_valid` — captured *before* the fail-soft zeroing —
which `check_envelope` checks instead of re-reading. `bank_deg` itself needed no separate flag
(NaN propagates through `math.deg` unchanged, so an invalid `bank_rad` already leaves `bank_deg`
NaN rather than zeroed) but `bank_valid` is still needed to distinguish that from a `LoGetADIPitch
BankYaw` call that returned nothing at all (`type(bank_rad) ~= "number"`), which NaN-propagation
alone cannot tell apart from a valid zero. All 23 pre-existing `test_flight_control_lua.py` cases
pass unchanged, confirming the refactor is behaviour-preserving.

**Security Finding A — `fc_last_cmd_seq` desyncs permanently across a body-layer restart; fixed
now (main-loop decision, per the dispatch: "it is a functional bug, not only an attack").** Chose
option (b) from security-m1-m2.md's own two recommendations — body-layer reconciles its own
`wire_seq` against Lua's echoed counter — over option (a) (bounding how far a single message may
advance `fc_last_cmd_seq` in `Export.lua`), because (b) is the one that actually fixes the much
more probable self-inflicted trigger (an ordinary body-layer restart mid-session) as well as the
LAN-reachable one, and needs no new Lua-side policy call about "how big a jump is implausible" (a
genuine body-layer restart after a long sortie could legitimately need to jump by dozens).

**Did *not* reuse `ai_pilot_wheel.lua`'s `goal_seq ~= ai_pilot_goal.goal_seq` ("different", not
"greater") shape the dispatch pointed at as the existing precedent** — read it first
(`ai_pilot_wheel.lua:1322`) and it does not fit here: that check is a one-shot *trigger* dedup for
a single field (`hvrt_step`) layered *on top of* the channel's own already-monotonic `goal_seq`
staleness gate, not a replacement for monotonic ordering. `flight_control`'s own `seq` gate
(`handle_flight_control_command`) is that staleness gate itself, guarding four different command
kinds over a loopback UDP socket where out-of-order delivery is a real, named case this codebase
already defends against (`test_a_stale_seq_is_ignored`). Switching it from "greater than" to
"different from" would accept a genuinely stale, reordered duplicate as if it were new — the exact
failure mode the gate exists to prevent — so the mode-2 precedent's *shape* does not transfer, only
its *reasoning* ("let body-layer's own counter track Lua's, rather than inventing a second
mechanism") does, which is what the reconciliation approach below actually borrows.

Mechanism: `Export.lua`'s `push_flight_control_state` now echoes `fc_last_cmd_seq` itself (new wire
field, additive — an older collector/body-layer simply never reads it, same "null means nothing new"
posture every other optional field here has), deliberately *not* reset by `on_stop` (matching the
field's own existing "never reset" comment one line below). `schema.flight_control.FlightControl
State` carries it through (`last_cmd_seq`) to `GET /flight_control/latest`. `belief.flight_control.
FlightControlState` mirrors it as `lua_last_cmd_seq` (a plain `advance_flight_control_state` mirror,
nothing special there). The actual reconciliation lives in `body._apply_flight_control`, run
unconditionally at the top before any send this poll: `if state.lua_last_cmd_seq is not None and
state.lua_last_cmd_seq > state.wire_seq: wire_seq = lua_last_cmd_seq`. This only ever *raises*
`wire_seq`, never lowers it, so it cannot reintroduce acceptance of a genuine duplicate/stale resend
within the same body-layer session — the one property Finding A's own requirement named explicitly.

Tested end to end in both languages per the dispatch instruction: `test_flight_control_lua.py`'s new
`TestLastCmdSeqEchoSurvivesOnStop` (Lua, real interpreter) sends `seq=47`, confirms the echo, calls
`on_stop()`, confirms the echo survives it unchanged, then confirms a reconciled `seq=48` is
accepted. `test_body_flight_control.py`'s new `test_a_body_layer_restart_reconciles_wire_seq_
above_lua_last_cmd_seq` seeds `FlightControlState(wire_seq=0, lua_last_cmd_seq=47)` (a fresh
process's default `wire_seq` against a mid-sortie-high Lua counter) and asserts the actual send
lands at `seq=48`; `test_reconciliation_never_lowers_wire_seq_below_its_own_history` seeds the
opposite case (`wire_seq=10, lua_last_cmd_seq=3`, modelling the mirror lagging one poll behind
this process's own last send) and asserts the send still lands at `11`, not `4`. Both new body-layer
tests counterfactual-checked by reverting the reconciliation block in `body.py` (byte-for-byte,
`shasum`-matched before/after) — the restart test goes red (`seq == 1`, not `48`) for exactly the
stated reason; restored and reran clean. The Lua test counterfactual-checked the other direction:
temporarily made `on_stop` reset `fc_last_cmd_seq` (the behaviour this fix and `on_stop`'s own
pre-existing comment both forbid) and confirmed the echo assertion goes red, then restored
(`shasum`-matched).

**Security Finding B — `arm_lease_s` shared the generic 60 s sanity ceiling, letting any accepted
message widen U10's 3 s escape-hatch margin by 20x.** Gave it its own ceiling at both layers that
check it independently (`Export.lua`'s `FC_LIMIT_BOUNDS.arm_lease_s`, the HTTP layer's `_FLIGHT_
CONTROL_LIMITS_BOUNDS["arm_lease_s"]`): **10.0 s**, chosen as roughly 3x the 3 s default — enough
headroom that a deliberately slower lease (e.g. for a laggier LAN) is still representable without
a code change, while capping the worst case at a third of the old ceiling and nowhere near the
60 s every other limit still shares. body-layer's own `tuning.py` declaration for the same
constant (`ARM_LEASE_S`, `belief/flight_control.py`) had its `hi` bound lowered from 30.0 to match
10.0 — not because body-layer's own tunable range needs to be that tight for ordinary flying, but
because a user-configured value between 10.0 and the old 30.0 would now be silently rejected
*whole-message* at the wire layer (the `AC-B14` posture: an out-of-bounds limit rejects everything,
not just that field) rather than applied, which is a worse failure than simply narrowing the
tunable range to match. Regenerated `config/defaults.toml` with `tools/generate_defaults.py
--write` and read the rendered output directly (not the source comment) per this project's own
"the generator emits only the first sentence" caveat: confirmed it now reads `range: 0.5 .. 10.0`
for `ARM_LEASE_S`. `test_tuning_defaults_toml.py`'s own staleness check passes against the
regenerated file. No existing test asserted the old `60.0`/`30.0` ceilings directly (grepped both
subprojects' test suites for `arm_lease_s`/`ARM_LEASE_S`); every existing Lua/HTTP test already
uses `arm_lease_s` values of 1.0–3.0, well inside the new ceiling, so none needed updating.

**Cross-key coupling check (per this role's own standing instruction to flag one even if not
guarded):** `ARM_LEASE_S` has no asserted relationship with any other tuning key in `tuning.
_check_scan_decay_coupling` or elsewhere — it is read only by `flight_control_limits()` and sent
as one independent `limits` field. Not adding a new coupling check here; flagging only because the
value *is* now coupled, outside the tuning system, to two other hard-coded ceilings (`Export.lua`'s
`FC_LIMIT_BOUNDS.arm_lease_s`, the HTTP layer's own bound) that `generate_defaults.py` cannot see
and does not check against — a future change to any one of the three needs a human (or a future
`invariant-check`-style grep) to keep the other two in step; this round kept all three at 10.0 by
hand, verified by grep.

### Comment pruning (per "Prune the comment you are standing next to")

Two comments pruned, both in `flight_control.lua`, right beside code this round touched:

- `check_envelope`'s docstring previously only explained the `"nan"`/`"dead"` cause split; it now
  also states why it takes `measured` rather than reading `LoGet*` itself (the fail-soft-vs-release
  policy mismatch) — an addition, not a deletion, since the original "why the two causes exist"
  sentences were still load-bearing and kept verbatim.
- `read_measured`'s docstring gained one new paragraph (the `self_data_ok`/`ias_valid`/`bank_valid`
  rationale) with nothing removed — its existing "every reader fails soft... the envelope check,
  run separately, is what actually stops the override on real trouble" sentence turned out to be
  exactly the load-bearing context the new paragraph needed to point back at, so it stayed.

No comment was found stale enough to delete outright in either touched file this round — both
functions' existing docstrings were accurate statements of *why*, not *what*, and remained true
after the edits; only `check_envelope`'s call site (`run_active_frame`) changed shape, and it
carries no comment of its own to prune.

### Checks (this round)

- **aircraft-layer**: `ruff format --check` — 85 files already formatted; `ruff check` — all
  checks passed; `mypy src` — 28 files, no issues; `luac5.1 -p` on `Export.lua`, `flight_control.
  lua`, `core.lua`, `ai_pilot_wheel.lua` — all pass; full `tests/` — 953 passed (was 821 pre-round
  per the prior round's own count — this round's new/changed tests are `test_flight_control_lua.py`
  (+1, `TestLastCmdSeqEchoSurvivesOnStop`) and `test_flight_control_api.py` (field additions to
  existing assertions, no new test count); the jump from 821 to 953 reflects this subproject's test
  suite having grown across intervening rounds not covered by this implementation.md entry, not a
  miscount here — confirmed by `-v` name listing that every flight-control test file's own count
  matches what this entry states (24 in `test_flight_control_lua.py`, 34 in `test_flight_control_
  api.py`).
- **body-layer**: `ruff format --check` → 2 files needed reformatting (`body.py`, `test_body_
  flight_control.py`, both whitespace-only from the new code/tests) — reformatted with `ruff
  format`, then `ruff format --check` passes; `ruff check` — all checks passed; `mypy src` — 92
  files, no issues; `test_tuning_defaults_toml.py` — passes against the regenerated `config/
  defaults.toml`; targeted run (`test_flight_control.py` + `test_body_flight_control.py` +
  `test_tuning_defaults_toml.py`, `-m "not slow"`) — 45 passed (13 in `test_body_flight_control.py`,
  up from 11 pre-round: the 2 new reconciliation tests). The full `body-layer/tests/` suite was
  started but not completed in this round (it runs ~3+ minutes serially in this environment and the
  targeted run plus the full `aircraft-layer` suite already cover every touched module and its
  direct test files with no regressions) — flagged here rather than silently claimed; DoD's own
  `--full` pass is the authoritative run for this subproject.

### Notable discoveries (this round)

- `read_measured` already made the exact `LoGetSelfData` call `check_envelope` needed for its
  `"dead"` cause — the perf finding's own mitigation text assumed one redundant call would remain
  ("one redundant call instead of three"); reading both functions side by side first showed the
  duplication could be eliminated completely, not just reduced by two of three.
- The dispatch pointed at `ai_pilot_wheel.lua`'s `goal_seq ~= ai_pilot_goal.goal_seq` shape as "the
  existing shape to reuse where it fits" — it did not fit, and the 15 minutes spent reading that
  call site first (rather than assuming the pointer was correct and copying the shape) is what
  caught that before it became a wire-ordering regression. Worth recording because the dispatch
  text itself invited exactly that copy.
- `arm_lease_s`'s new 10.0 s ceiling is now a value asserted identically in three places
  (`Export.lua`, `aircraft-layer/src/api/server.py`, `body-layer`'s `tuning.py` `hi` bound) with no
  single mechanical check tying them together — `test_export_lua_constants_parity.py` exists for a
  *different* pair of constants (the `watched_args`/`read_args` size bound) and does not cover this
  one. Not fixed in this round (out of the dispatch's stated scope), but worth a backlog item if
  this project wants `invariant-check`-style coverage for "the same safety-margin ceiling, declared
  in three languages/layers, stays in step" more generally — `arm_lease_s` is the first instance of
  that specific shape in this codebase.

## Mode 2, Stages P3+P4 (CBTM align/align-for-launch/break/break-away, recovery), 2026-11-19

Implements `plans/flight-control/plan.md`, "Revised 2026-11-18 -- Stages P3+P4 ready to build",
narrowed by its own "Amendment 2026-11-18 (main loop, after the plan check)" to **mode 2 only** --
mode-1 break turn/break away (`BREAK_TURN_BANK_DEG`/`turn_bank_override_deg`) is explicitly
withdrawn from this batch and not built here; mode 1 answers "unable" to all four new commands
instead (permanently for align/align-for-launch, temporarily for break/break-away).

### Files Changed

**aircraft-layer:**
- `src/schema/ai_pilot_wheel.py` -- `AiPilotWheelState.cbtm_status`/`cbtm_seq`, optional fields,
  same "an older Export.lua still parses cleanly" posture as every other Stage addition on this
  schema.
- `src/collector/command_sender.py` -- `CommandSender.send_ai_pilot_goal` gains `cbtm_action`/
  `cbtm_seq`, new sibling one-shot fields on the same wire message `hvrt_step` already travels on.
- `src/api/server.py` -- `POST /command/ai_pilot_goal` validates the two new fields (closed
  vocabulary for `cbtm_action`, the same `goal_seq` bound reused for `cbtm_seq`) and forwards them.
- `dcs-export/Petrobrain/ai_pilot_wheel.lua` -- the CBTM one-shot channel: `LONG_PRESS_HOLD_S`/
  `BREAK_AWAY_GAP_S` constants; the `ai_pilot_cbtm` state table and `AI_PILOT_CBTM_PRESS_CMD` press
  map; a **third** pending-release pair (`ai_wheel_cbtm_pending_cmd`/`_release_t`), mirroring the
  existing two (takeover, goal channel) rather than sharing either; `ai_pilot_cbtm_mode_ready`/
  `ai_pilot_cbtm_finish`/`ai_pilot_cbtm_tick` (mode-cycle-then-press dispatcher, same bounded-retry
  shape the goal channel's own mode-cycle already has); a CBTM-pause guard added to the top of
  `ai_pilot_goal_tick`/`ai_pilot_goal_tick_hvrt` (mirrors the existing HVRT-pause guard); `handle_
  ai_pilot_goal_command` parses `cbtm_action`/`cbtm_seq` and starts a fresh run on a distinct seq,
  releasing whatever press the previous run left open; `run_ai_pilot_wheel` gains the third
  release-deadline check (decides gap-vs-finish for `break_away`'s two presses) and releases/resets
  the channel on unpark; `on_stop` releases/resets it too (same `AC-B13`-class proactive-close
  reasoning the goal channel's own reset already has); `push_ai_pilot_wheel_state` sends
  `apw_cbtm_status`/`apw_cbtm_seq`.

**body-layer:**
- `src/belief/ai_pilot_wheel.py` -- `AlignPhase`/`CbtmAction` type aliases; `FlightSnapshot`
  (the typed replacement for the old `Any`-typed `pre_align_snapshot` stub); `ParkedFlightState`
  gains `lua_cbtm_status`/`lua_cbtm_seq` (Lua mirrors), `cbtm_action_sent` (this side's own record
  of the last CBTM trigger, not a Lua mirror), `payload_station_counts_last_seen`; `advance_parked_
  flight_state` also reads `GET /payload/latest` each poll (launch detection) and mirrors the two
  new CBTM status fields; `payload_count_dropped`, `capture_flight_snapshot`, `cbtm_apply_align`,
  `cbtm_apply_align_for_launch` (Fix 1's own re-entry branch), `seed_recovery_goal` (Decision 26's
  priority seeding, renamed from a private `_seed_recovery` once `body.py` needed to call it too);
  `decide_ai_pilot_wheel` gains `payload_count_dropped`/`agl_m`/`ias_kmh` parameters and three new
  steps (F-P7 break-wins, the three recovery triggers, recovery's own end condition), plus a guard
  suppressing the slice-timer rotation while `"recovering"`.
- `src/belief/crew_console.py` -- `ai_pilot_cbtm_transition` one-shot field (reset alongside the
  other `ai_pilot_*` ones); `level_flight()` now reports `leveling_off` (true while aborting a
  `"launch_aligned"` run) so the rule can choose its own readback; `level_off()`'s docstring
  corrected (F-P8 settled it as "stop turn" only, in every `align_phase` -- the stale "Stage P4's
  own addition, not built here" sentence this docstring carried was pruned); four new actions
  (`cbtm_align`/`cbtm_align_for_launch`/`cbtm_break`/`cbtm_break_away`), each a trivial one-shot
  setter -- the actual `align_phase`/wire-send mechanics live in `body.py`.
- `src/body.py` -- imports the five new `belief.ai_pilot_wheel` names; `_apply_ai_pilot_wheel_goal`
  gains a `previous_payload_counts` parameter (default `None`, so every pre-existing call site in
  the test suite keeps working unchanged) and now: applies F-P6 (a fresh heading/altitude/speed
  command ends `"aligning"`/`"launch_aligned"`, never `"recovering"`) before dispatching the goal
  request; applies the `level_flight` abort (Q0 -- heading frozen at current, then straight into
  `seed_recovery_goal`'s own targets while `"launch_aligned"`, or a plain end while `"aligning"`);
  applies `cbtm_align`/`cbtm_align_for_launch` directly (the "external (voice, ...)" writer the plan
  names) and leaves the two breaks' own align/goal mutation to `decide_ai_pilot_wheel` (keyed off
  the newly-written `cbtm_action_sent`); computes `agl_m`/`ias_kmh`/`payload_count_dropped` for the
  `decide_ai_pilot_wheel` call; sends the CBTM wire message as its own one-shot trigger (`cbtm_seq`,
  its own distinct sequence space, bumped from `runner.ai_pilot_cbtm_last_sent_seq`) whenever `ai_
  pilot_cbtm_transition` is set, reusing (not bumping) the last-sent ordinary `goal_seq` on that same
  message -- safe, since `Export.lua` only dedupes the FLT/HVR goal fields on a *change* to `.param`,
  never on `goal_seq` moving, so an unchanged `goal_seq` carrying unchanged `param`/targets is a
  no-op for that half of the message; the main poll loop captures `previous_payload_counts` before
  `advance_parked_flight_state` overwrites it, so the launch-detection comparison has something to
  compare against.
- `src/rules/actions.py` -- `_cbtm_align`/`_cbtm_align_for_launch`/`_cbtm_break`/`_cbtm_break_away`
  wrapper functions; `_axes_cbtm_align_unready` (`AI_OVERLAY`, permanent, E-P20) and `_axes_cbtm_
  break_unready` (`NOT_READY`, temporary until the mode-1 batch); four new `_by_mode`-wrapped
  `Action`s registered in `FLIGHT_ACTIONS`.
- `config/rules/flight.lua` -- `level_flight`'s own pattern widened to `"level <form:flight|off>"`
  (F-P8: "level off" is a second wording for the same command, never a second meaning on `level_
  off`), its handler now branches on `r.leveling_off`; four new rules (`cbtm_align`/`cbtm_align_for_
  launch`/`cbtm_break`/`cbtm_break_away`), category `"flight_control"` (has-controls only, same as
  the HVRT rules), readbacks the user's own words verbatim.
- `config/defaults.toml` -- regenerated (`tools/generate_defaults.py --write`) for the two new
  tunables below; rendered output read directly, not the source comment, per this project's own
  "the generator emits only the first sentence" caveat.

### Behaviour constants

| Constant | Default | Where | Why |
|---|---|---|---|
| `AI_PILOT_RECOVER_AGL_DROP_M` | 40.0 | body-layer `tuning.py` | the Q-P3-2 relative floor |
| `AI_PILOT_RECOVER_IAS_CEILING_KMH` | 280.0 | body-layer `tuning.py` | the absolute overspeed ceiling |
| `LONG_PRESS_HOLD_S` | 0.7 | `Export.lua` constants block | the CBTM long-press duration |
| `BREAK_AWAY_GAP_S` | 2.0 | `Export.lua` constants block | the gap between `break_away`'s two presses |

### Tests Added

- `body-layer/tests/test_ai_pilot_wheel.py` -- `TestPayloadCountDropped` (no-previous/drop/rise-
  while-another-drops/new-station/no-change, matching the plan's own test-strategy list verbatim),
  `TestCaptureFlightSnapshot` (prefers an outstanding goal target over the held value, falls back to
  held values, `None` when a parameter has neither, `None` when AGL is unknown), `TestCbtmApplyAlign`,
  `TestCbtmApplyAlignForLaunch` (Fix 1's own re-entry case, from both `"recovering"` and
  `"launch_aligned"`), `TestSeedRecoveryGoal` (altitude active/speed queued; a previously-active
  heading is re-queued, not dropped), `TestDecideAiPilotWheelCbtm` (the break-wins heading-drop for
  both an active and a queued heading goal; an `"align"` trigger does *not* run the break logic;
  each of the three recovery triggers independently and two firing at once still enters `"recovering"`
  exactly once; recovery promotes strictly on `settled_param`, confirmed by holding `now_sim` well
  past `AI_PILOT_GOAL_SLICE_S` and showing altitude stays active regardless; recovery ends once both
  parameters have cleared; a fresh `request_goal` call for one recovering parameter during recovery
  leaves the other's own target untouched -- Q6/the table's own row, exercised at the level `set_
  parked_altitude`/`set_parked_heading` actually call through).
- `body-layer/tests/test_rules_flight_actions.py` -- `test_shipped_rule_files_load_with_zero_
  failures`'s enumerated rule-id set extended with the four new ids (pre-existing test, necessarily
  updated -- it asserts the exact shipped set by name).
- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py` -- `TestOnStop.test_open_cbtm_press_is_released`
  (new); the three existing `TestOnStop` tests, plus the four harness-builder functions shared by
  `TestTakeoverSequence`/`TestSeatGate`/`TestAiPilotGoalTick`/`TestHandleAiPilotGoalCommand`/
  `TestAiPilotGoalTickHvrt`/`TestPushAiPilotWheelStateJson`, all needed their fake preamble state
  extended with `ai_pilot_cbtm`/the third pending-release pair (and, for the one harness that calls
  `update_ai_pilot_wheel_overlay`, `AI_PILOT_CBTM_PRESS_CMD` plus the three new functions) -- these
  are pre-existing tests whose *inline hand-mirrored* module state (this file's own stated
  convention, not an extraction) no longer matched what the real, now-modified functions read and
  wrote; none of their own assertions changed except where noted.
- `aircraft-layer/tests/test_ai_pilot_goal.py`/`test_ai_pilot_wheel_api.py` -- the `_RecordingCommand
  Sender` double and every `sender.sent == [...]`/`to_api_dict()` assertion updated for the two new
  trailing fields; mechanical, no assertion's *meaning* changed.

### Checks

- **aircraft-layer**: `ruff format --check` -- 85 files; `ruff check` -- all checks passed;
  `mypy src` -- 28 files, no issues; `luac5.1 -p` on `ai_pilot_wheel.lua` -- pass; the bytecode
  global-safety check (`luac5.1 -l -p ... | grep GETGLOBAL`) -- every name is a genuine DCS API,
  stdlib, or an existing cross-module helper, none of this round's own new names; full `tests/` --
  961 passed.
- **body-layer**: `ruff format --check` -- 227 files; `ruff check` -- all checks passed; `mypy src`
  -- 92 files, no issues (`mypy src tests` surfaces ~330 pre-existing errors across unrelated test
  files from a `replace(ParkedFlightState(), **dict[str, object])` helper pattern that predates this
  round and from several other files entirely outside this round's diff -- not this subproject's
  own `mypy` command, which is `src`-only, so not fixed here); targeted run (`test_ai_pilot_wheel.py`
  + `test_body_ai_pilot_wheel.py` + `test_crew_console_ai_pilot_wheel.py` + `test_flight_control.py`
  + `test_body_flight_control.py` + `test_rules_flight_actions.py` + `test_voice_commands.py` +
  `test_tuning_defaults_toml.py` + `test_rule_gates.py`, `-m "not slow"`) -- 249 passed; `tests
  --collect-only` over the whole suite (the smoke check) -- 3649 collected, no import errors.
  The full suite was not run in this round (no `.venv` in this worktree to drive `fast-tests.sh`,
  and the full suite is DoD's own job per root `CLAUDE.md`'s "Tests" note) -- flagged here rather
  than silently claimed.

### Notable discoveries and deliberate simplifications (flagged, not hidden)

- **`decide_ai_pilot_wheel`'s F-P7 break-wins check reads `state.cbtm_action_sent` (this side's own
  record of the last trigger), not the plan's literal "`lua_cbtm_status` not yet `"idle"` for this
  `cbtm_seq`" condition.** The simpler check runs every poll `cbtm_action_sent` names a break and is
  idempotent (nothing left to drop/clear after the first poll it fires), so it is safe, but it does
  not reproduce the plan's own nuance of only acting while Lua specifically reports the break still
  in flight. Re-entering `"aligning"`/`"launch_aligned"` after a break correctly stops triggering it,
  since a later `cbtm_align`/`cbtm_align_for_launch` overwrites `cbtm_action_sent` to a non-break
  value as part of the same dispatch.
- **`seed_recovery_goal` re-queues a previously-active heading goal rather than the plan's own
  wording ("altitude becomes active, speed queued") implying heading is untouched.** Reasoned
  through in this round's own docstring: while `"aligning"`/`"launch_aligned"`, Lua's CBTM-pause
  guard means no heading press is actually in flight regardless of what `active_param` says, so this
  is defensive (preventing an orphaned target with no queue slot) rather than a behaviour the user
  asked for or that should ever actually matter live.
- **`cbtm_align()`'s action unconditionally restarts a plain alignment from any prior `align_phase`
  (including mid-recovery)** -- not explicitly specified by the plan (which only states Fix 1's
  re-entry rule for `cbtm_align_for_launch`); read as the natural counterpart, flagged for the
  Reviewer to confirm against the user's own intent if this matters.
- **The `level_flight` abort's "first level at current, then start recovery" (Q0) is implemented as
  heading frozen at the current held value plus altitude/speed jumping straight to `seed_recovery_
  goal`'s own pre-align targets**, not as a literal two-step freeze-then-climb sequence -- the
  "level at current" wording is read as describing the aircraft's own transient physical state at
  the moment recovery starts (wherever it currently is), not a distinct goal step this code needs to
  model, since the very next decide-call already drives toward the recovery targets regardless.
- **No live DCS flight test was possible or attempted this round** (no Windows box in this
  environment) -- every check above is static/unit-level; the plan's own "Flight test steps" section
  remains the acceptance gate for this batch and needs a real sortie before the mode-1 batch begins.

## Review-fix round (2026-11-19) -- review-p3p4.md's two Required Fixes

Both of `review-p3p4.md`'s Required Fixes were missing-test gaps, not behavioural defects (its own
verdict); no production code was planned to change, and none did except one test-only correction
below. Fast-forwarded from `59192cfa` to the reviewed tip `d5eaee9b`, then committed on this round's
own branch (not `feature/bl16-p3p4-cbtm` directly, per the dispatch's worktree instructions).

**Required Fix 1** -- `body-layer/tests/test_body_ai_pilot_wheel.py` gains four new classes
(`TestCbtmTransitions`, `TestFlightCommandEndsAlignment`, `TestLevelFlightAbortRecovery`,
`TestRecoveryTriggerWiring`), covering exactly the four bullets the review named: each `cbtm_*`
one-shot transition landing on `align_phase`/`cbtm_action_sent` with a correctly-bumped `cbtm_seq`
wire send; F-P6 (a fresh heading/altitude/speed command ending `"aligning"`/`"launch_aligned"` and
still flying, while `"recovering"` is untouched); the F-P8/Q0 `level_flight` abort reaching
`"recovering"` seeded from the snapshot with heading frozen at the *current held* value, and the
`"aligning"` case's plain end with nothing to recover; and `agl_m`/`ias_kmh`/`payload_count_dropped`
actually reaching `decide_ai_pilot_wheel` from `runner.last_ownship_state.alt_agl_m`/`runner.
last_ias_kmh`/a live `previous_payload_counts` comparison, not just the pure function's own direct
arguments.

**A pre-existing behaviour surfaced while writing these, not a defect in this round's own code**:
every CBTM-transition call through `_apply_ai_pilot_wheel_goal` also sends one ordinary ("null"
param, `goal_seq=0`) goal message on the first poll of an activation with no goal yet -- `goal` is
written back onto `runner.parked_flight_state` unconditionally before `final_goal` is computed, so
a fresh `AiPilotWheelGoal()` (`goal_seq=0`) differs from `runner.ai_pilot_goal_last_sent_seq`'s
initial `None` and triggers one harmless extra send, self-correcting on the very next poll once
`ai_pilot_goal_last_sent_seq` is set. Confirmed by hand against the real code (not assumed from
reading it) before writing the tests around it -- the module docstring and a `_cbtm_send` helper
(filters `client.ai_pilot_goal_calls` down to the one entry whose `cbtm_action` is not `None`) say
so, rather than asserting a brittle single-call count that this behaviour would otherwise break.
Flagged here per this round's own dispatch instruction ("if a test exposes a real bug, fix it
minimally and say so") -- judged **not** a bug worth fixing: it is a one-poll, no-op-on-Lua message
(every field `None`/unchanged), not a behaviour regression, and fixing it would be a change to
`_apply_ai_pilot_wheel_goal`'s own existing send logic outside this round's stated scope (test
coverage only, no behaviour change expected).

**Required Fix 2** -- `body-layer/tests/test_rules_flight_actions.py` gains `TestCbtmActions`,
dispatching all four `cbtm_*` rules through `_dispatching_console`/`handle_command` against the
real shipped `flight.lua`: each rule's overlay-mode readback ("Aligning.", "Aligning for launch.",
"Breaking left."/"Breaking right.", "Breaking away.") and `ai_pilot_cbtm_transition` value; the
coarse `"flight_control"` gate's "not flying" `unable` taking priority over either mode body; and
both mode-1 "unable" reasons (`cbtm_align`/`cbtm_align_for_launch` -> permanent `AI_OVERLAY`,
`cbtm_break`/`cbtm_break_away` -> temporary `NOT_READY`), mirroring `TestHandoverActions`/
`TestSeatNeverGatesMode1`'s own shape (`console.flight_control_state = replace(..., phase="ACTIVE")`
to reach `flight_mode() == "axes"`).

### Checks (this round)

- **body-layer**: `ruff format --check` -- 1 file needed reformatting on the first pass
  (`test_body_ai_pilot_wheel.py`, a line-length wrap in a new test, whitespace-only) --
  reformatted with `ruff format`, then `ruff format --check` passes (227 files); `ruff check` --
  all checks passed; `mypy src` -- 92 files, no issues (this round added no `src/` changes, so this
  is an unchanged-green confirmation, not a new result); targeted run (the same nine-file set
  `review-p3p4.md` itself used, `-m "not slow"`) -- **275 passed** (up from 249: 29 in `test_body_
  ai_pilot_wheel.py`, up from 9 -- the 20 new Stage-P3+P4-composition tests; 69 in `test_rules_
  flight_actions.py`, up from 59 -- the 10 new `TestCbtmActions` tests); `tests --collect-only`
  over the whole suite (smoke) -- 3675 collected (up from 3649 by exactly the 26 new test functions),
  no import errors. No `.venv` in this worktree either (same as the previous round) -- every command
  above ran against `/Users/sg/Code/DCS-petrobrain/body-layer/.venv`'s binaries with this worktree's
  `body-layer` as CWD, per the dispatch instruction; the full suite remains DoD's own job.
- **aircraft-layer**: untouched this round -- no files under `aircraft-layer/` changed, so its own
  checks were not re-run (review-p3p4.md's own pass already covers the tip this round built on).

### DoD fix round (`dod-p3p4.md`, test-only, no production change)

Two of `dod-p3p4.md`'s required fixes, both test doubles/literals, not `src/` changes:

1. `tests/test_body.py`'s `FakeConsoleAircraftClient` gained `get_payload_latest`, returning
   `None` -- the same "not an error, no sample yet" default every other `get_*_latest` method on
   that fake already uses (`ai_pilot_wheel_state`/`flight_control_state`/`sight_servo_state`/
   `spu8_state`). `advance_parked_flight_state` calls this unconditionally every poll (this
   batch's launch-detection read); the fake had no such method, so the real poll loop's own
   `except Exception` was swallowing an `AttributeError` before any of that function's `replace()`
   calls ran -- the three `test_body.py` failures DoD found. Grepped every other `class Fake.*
   Client` in `tests/` (`test_body.py`'s other `FakeAircraftClient`, `FakeSpeechInputClient`;
   `test_crew_console.py`'s `FakeSpeechClient`; `test_detection_trace.py`/`test_emission_pipeline.
   py`/`test_hybrid_source.py`/`test_naked_eye_source.py`/`test_player_bubble.py`'s own
   `FakeAircraftClient`s) -- none of the others are driven through `_run_crew_text_poll_loop`
   (confirmed: none of them define `get_ai_pilot_wheel_latest`/`get_flight_control_latest` either,
   and none call that function), so none needed the same fix.
2. `tests/test_aircraft_client.py::test_write_ai_pilot_goal_posts_to_command_endpoint`'s expected
   payload dict gained `"cbtm_action": None, "cbtm_seq": None` -- `AircraftLayerClient.write_
   ai_pilot_goal`'s two new trailing optional params (this batch's own CBTM one-shot wire fields,
   always included in the POSTed dict) weren't reflected in this pre-existing test's literal.

**Checks**: `body-layer` -- `ruff format --check .` (2 pre-existing files would reformat,
`research/2026-10-05-security-audit.md`/`research/2026-11-17-lupa-sandbox.md`, both untouched by
this fix and already noted in `review-p3p4.md`'s re-review); `ruff check .` -- all checks passed;
`mypy src` -- 92 files, no issues; full suite `pytest -n auto -q` -- **3671 passed, 4 xfailed, 0
failed** (up from 3667 passed/4 failed before this round's two fixes). `aircraft-layer` untouched,
not re-run.

## Mode 1 batch (break turn, break away, rotor envelope, VRS, rates as goals), 2026-11-19

Implements `plans/flight-control/plan.md`, "Revised 2026-11-19 -- mode-1 batch: break turn, break
away, the rotor envelope, rates as goals" (Decisions 27-31) plus the "Main-loop amendment
2026-11-19 (after the plan check)" (Decision 32, the `ROTOR_RPM_ARG_SCALE_MAX_PCT` naming). Branch
`feature/bl16-mode1-break`, fast-forwarded onto `12c439a8` (the plan + main-loop amendment commits)
before any implementation.

**Plan-vs-codebase check (step 1b) found both kinds of mismatch the role's own instructions warn
about, before writing a line:**

- **Phantom tests.** The plan's "F-M1's removal ripples through the test/doc surface" section
  names two tests to delete (`test_flight_control_lua.py`'s "self-releases at 41 deg of
  bank"/"clamps `phi_d` to `max_bank_deg`") and a `max_bank_deg` parity assertion in `test_export_
  lua_constants_parity.py`. **None of the three exist** -- grepped both files for `max_bank_deg`/
  `bank`/`ENV_BANK`/`release` and found no such tests in either; `test_export_lua_constants_
  parity.py` does not reference `flight_control` at all. Nothing was deleted; a new positive test
  (`TestEnvelopeRelease::test_sustained_high_bank_never_releases`) was added instead, confirming
  the removal's own wiring rather than inverting tests that were never there.
- **No missing-file surprises this time** -- `grep`ing `MAX_BANK_DEG`/`max_bank_deg` across both
  subprojects' `src/`/`tests/` before editing found every real call site (`belief/flight_control.
  py`, `aircraft-layer/src/api/server.py`, `dcs-export/Petrobrain/flight_control.lua`,
  `aircraft-layer/tests/test_flight_control_law.py`'s own `_LIMITS` fixture), so none were missed.

### Files Changed

**body-layer:**
- `src/belief/flight_control.py` -- `MAX_BANK_DEG` removed (F-M1, "remove the 30 degree limit");
  five new `tuning.real` constants (`ROTOR_RPM_FLOOR_PCT`, `RETREATING_BLADE_STALL_IAS_KMH`,
  `BREAK_MAX_HEIGHT_LOSS_M`, `VRS_IAS_THRESHOLD_KMH`, `VRS_MAX_DESCENT_MPS`), all `status=
  "agreed-guess"` (the tuning-status enum has no `"user"` literal -- mypy caught this; every one
  of these is the user's own stated number, closest existing status is `"agreed-guess"`, same as
  `TAKEOVER_LEVEL_BANK_DEG`'s own precedent for a user-answered-but-unmeasured value); `Flight
  ControlGoalRequest.turn_rate_deg_s: float | None`; `flight_control_limits()` drops `max_bank_deg`
  and adds the five new wire keys; `goal_request_fields()` carries `turn_rate_deg_s` when set.
- `src/belief/ai_pilot_wheel.py` -- `ParkedFlightState.cbtm_break_entry_heading_deg: float | None`
  (Decision 32's own capture); `cbtm_break_target_heading_deg(action, entry_heading_deg)`, a pure
  helper (entry -90/+90/-180 for left/right/away).
- `src/body.py` -- `_apply_ai_pilot_wheel_goal` captures `state.held_heading` into `cbtm_break_
  entry_heading_deg` the instant a break `cbtm_transition` fires (before anything else that poll
  can move it), carries it through unchanged otherwise, and clears it on unpark alongside `cbtm_
  action_sent` (same leak class that field's own docstring already names).
- `src/belief/crew_console.py` -- `axes_break_turn(sign, rate_deg_s)`/`axes_break_away(rate_deg_s)`
  replace the two mode-1 `_axes_cbtm_break_unready` call sites' real bodies; `drain_flight_control`
  gains Decision 32's own seeding (an `OVERLAY` -> `ACTIVE` transition with a break active seeds
  `flight_control_goal_transition` from `cbtm_break_target_heading_deg`).
- `src/rules/actions.py` -- `_axes_break_turn`/`_axes_break_away` replace `_axes_cbtm_break_
  unready`; `cbtm_break`/`cbtm_break_away`'s `Action.params` each gain a trailing `rate_deg_s`
  (`lo=1, hi=90`, required, mode 2's own bodies ignore it).
- `config/rules/flight.lua` -- `BREAK_TURN_RATE_DEG_S = 40` (F-M2: the rate lives in the rule, not
  Python), passed as the new trailing arg to both `flight.cbtm_break`/`cbtm_break_away` calls.
- `config/defaults.toml` -- regenerated (`tools/generate_defaults.py --write`); the five new keys
  render, `MAX_BANK_DEG` is gone.

**aircraft-layer:**
- `dcs-export/Petrobrain/flight_control.lua` -- `ENV_BANK_MARGIN_DEG` and `check_envelope`'s bank
  branch deleted (IAS alone governs release now); `max_bank_deg` dropped from `fc_limits`/`FC_
  LIMIT_BOUNDS`, the five new keys added to both; the mode-1 batch's own constants block (rotor/
  stall margins and rate caps, `K_BREAK_PEDAL_BIAS`, the rotor-RPM seam constants); `read_rotor_
  rpm_pct()` (ships `"dummy"`, flips to `"arg_proxy"` later), called once per frame in `read_
  measured()`; `law_apply_goal`'s `turn`/`heading_deg` branches both set/clear `rate_override_deg_
  s`/`break_entry_h_m` (Decision 27); `law_update`'s heading-mode branch reads the override for its
  own rate/accel ceiling, the altitude shaper gains Decision 29's break floor and Decision 31's VRS
  cap, step 3 widens `collective_saturated` to `collective_limited` (Decision 30) and step 5 adds
  the break's pedal bias; settling (`in_band_heading` going true) clears the override (B3); `phi_d`'s
  clamp against `max_bank_deg` is gone (F-M1); `law_init_at_take` seeds both new fields `nil` (B5).
  `M.read_rotor_rpm_pct` exported alongside the law functions, for `TestReadRotorRpmPct`'s own
  direct call.
- `src/api/server.py` -- `_FLIGHT_CONTROL_LIMITS_BOUNDS` drops `max_bank_deg`, adds the five new
  keys (generous sanity bounds, matched key-for-key to `Export.lua`'s own `FC_LIMIT_BOUNDS`);
  `_FLIGHT_CONTROL_GOAL_BOUNDS` gains `turn_rate_deg_s: (-90.0, 90.0)`.

### Departures from the plan, and why

1. **`axes_break_turn`/`axes_break_away` answer `NOT_READY` on an unknown current heading, rather
   than the plan's own `assert current is not None` pattern (copied verbatim from `axes_increment_
   heading`).** `cbtm_break`/`cbtm_break_away`'s rule category is the plain `"flight_control"`
   (shared with mode 2's own no-refusal body), not `"flight_control_heading"`'s hold-until-known
   gate `increment_heading` relies on for the same `assert` to be safe -- so a break commanded in
   the one-poll gap right after a take, before `fc_measured_heading` has ever been reported, is
   genuinely reachable and would otherwise crash. Local and reversible (one method body each); not
   escalated. Flagging for Architect/Reviewer: the alternative -- moving `cbtm_break`/`cbtm_break_
   away` to a `"_heading"`-holding category -- would also hold mode 2's own no-refusal body for a
   beat, a cross-mode behaviour change the plan never asked for, which is why this round did not
   take that path instead.
2. **Decision 32's exact mechanism is the Implementer's own design, not literally specified.** The
   amendment says "the take path seeds `heading_goal` from it" without naming where "it" (the
   break's own numeric target) comes from, since body-layer never tracked one for mode 2's break
   (ED computes it internally) -- added `cbtm_break_entry_heading_deg`, captured from `held_
   heading` at the press, and seed only `heading_deg` (not `turn_rate_deg_s` -- the amendment names
   no rate for this case, and `None` means "ordinary rate," a reasonable reading of "seeds the
   heading goal" literally). Flagged for review since this is new state, not in the plan's own
   Co-moving Fields table.
3. **The plan's own worked bank figures (150 km/h/40 deg/s -> ~71 deg; 220 km/h -> ~76 deg) do not
   hold against the actual shaper**, measured via the toy-plant suite: 150 km/h settles around ~43
   deg, 220 km/h around ~54 deg. Root cause, worked out while writing `TestBreakTurnChannel`: the
   heading-mode branch's critically-damped shaper (`OMEGA_HEADING = 0.3`, an explicitly unmeasured
   placeholder) peaks at roughly `E*omega/e` for a step error `E`, independent of the rate ceiling
   once that ceiling exceeds the natural peak -- raising `turn_rate_deg_s`'s ceiling does not by
   itself drive the rate up *to* it for a 90 deg error. Part of the bank reached above that
   kinematic prediction comes from `phi_i`'s own now-unclamped growth (the plan's own named Risk:
   "Integrator windup in `phi_i`... deliberately not fixed this batch"). Not fixed here -- `OMEGA_
   HEADING` is a first-cut gain the plan itself says is "owed by M0-E," and retuning the shaper is
   an Architect-level call, not an Implementer one. Tests assert the qualitative claim (steeper
   than an ordinary turn, converges, settling clears the override) rather than the specific figure.
   **Flagging prominently for Flight M-A**: as shipped, a break will not visibly reach the 60-80
   deg bank the plan's own text promises the pilot.

### Tests Added

- `aircraft-layer/tests/test_flight_control_law.py` -- `TestBreakTurnChannel` (3, qualitative bank/
  settle/mirror-symmetry, see Departure 3 above), `TestRateOverrideClearing` (3: set-on-heading-
  with-rate, cleared-by-ordinary-heading, cleared-by-continuous-turn -- B1/B2), `TestBreakHeight
  Floor` (2: floor holds while active, released on settle -- Decision 29), `TestRotorEnvelopeGuards`
  (4: RPM-floor caps a rise/leaves a fall untouched, stall-margin caps a rise, clear-of-both rises
  freely -- Decision 30), `TestVrsDescentCap` (2: capped below threshold, uncapped at cruise --
  Decision 31). `_LIMITS`/`_measured()` fixtures extended with the five new limits keys, `floor_
  agl_m` (newly read by `law_update` this batch), and `rotor_rpm_pct` (defaulted well clear of the
  floor so no pre-existing scenario trips a guard it isn't testing).
- `aircraft-layer/tests/test_flight_control_lua.py` -- `TestEnvelopeRelease::test_sustained_high_
  bank_never_releases` (F-M1's own positive confirmation); `TestReadRotorRpmPct` (3: dummy value,
  arg-proxy scaling, arg-proxy fail-soft-to-dummy) via a new `_run(..., rotor_rpm_source=...)`
  parameter that patches the module source's `ROTOR_RPM_SOURCE` default for this one test class.
- `body-layer/tests/test_flight_control.py` -- `TestWireHelpers` additions (`turn_rate_deg_s` on
  the wire only when set; `max_bank_deg` absent, the five new limits present);
  `TestDrainFlightControlSeedsTheBreakTarget` (4: seeds on an OVERLAY->ACTIVE break take, no-op
  with no break/no entry heading, unaffected by an ordinary TAKING->ACTIVE take -- Decision 32).
- `body-layer/tests/test_ai_pilot_wheel.py` -- `TestCbtmBreakTargetHeadingDeg` (4, including a
  wrap-through-zero case).
- `body-layer/tests/test_body_ai_pilot_wheel.py` -- `TestCbtmTransitions` gains the entry-heading
  capture (break captures, align does not) and `TestApplyAiPilotWheelGoal` gains the unpark-clears-
  it case.
- `body-layer/tests/test_rules_flight_actions.py` -- `TestCbtmActions`'s two mode-1 `NOT_READY`
  tests rewritten (the stub they covered is gone): `test_mode_1_break_not_ready_without_a_known_
  heading`/`..._away_...` (the new guard from Departure 1) plus three new tests flying the real
  break (`test_mode_1_break_left/right/away_flies_the_real_break`) asserting the dispatched
  `FlightControlGoalRequest`.

### Checks

**body-layer** (fresh `.venv` built for this worktree -- none existed; `pyproj`/`numpy`/`lupa==2.8`/
`mypy`/`ruff`/`pytest` installed per `pyproject.toml`'s own declared versions):
- `ruff format --check src tests` -- pass (227 files).
- `ruff check src tests` -- pass.
- `mypy src` -- pass, 92 files.
- `tools/check_rules.py config/rules` -- `ok: 1 rule file(s) checked`; wording/dry-run steps
  skipped with a warning (`audio-adapter/.venv` not built in this worktree, pre-existing, not
  something this round's changes can affect) -- `luac5.1 -p config/rules/flight.lua` passes
  separately as a syntax backstop.
- `tests/test_tuning_defaults_toml.py`/`test_tuning_comment_renders.py` -- pass (the second caught
  a real bug: `BREAK_MAX_HEIGHT_LOSS_M`'s `FLOOR_AGL_M` cross-reference lived in its comment's
  *second* sentence, which the generator never renders -- fixed by restating it in the first).
- Full suite, `pytest tests -q` (no xdist in this fresh venv) -- **3687 passed, 4 xfailed, 0
  failed**.
- `.claude/scripts/fast-tests.sh body-layer` -- smoke clean; the targeted run surfaced one
  deterministic, order-dependent failure, `test_main_print_tuning_works_without_aircraft_layer_
  url`, **not reproducible** standalone, within its own file, combined with `test_flight_control.
  py`, or under the full suite's own (alphabetical) order -- only under this script's specific
  targeted-selection order for this diff. Root cause, traced through `tuning.py`: `Resolution.
  defaulted`/`applied` are populated incrementally as each tuning-declaring module is first
  imported, reading `os.environ["PETROBRAIN_TUNING"]` *at that import instant* (`tuning.py`'s own
  documented "constants bind by value at import" design) -- some test file earlier in this
  specific combined run's import order sets that env var (directly or via a fixture that outlives
  its own test) to a file that supplies every key, so by the time this test's own `monkeypatch.
  delenv` runs, the global `defaulted` set is already permanently empty for the rest of the
  process. Pre-existing architecture (documented in `tuning.py`'s own module docstring and `body-
  layer/CLAUDE.md`'s "Tuning" section), not touched by anything in this diff, and not reproducible
  under the full suite's own order -- flagged for the Reviewer/DoD rather than chased further here
  (root `CLAUDE.md`: the full suite, not `fast-tests.sh`'s targeted heuristic, is the authoritative
  gate). Not refuted the DoD's full-suite pass above, which is clean.

**aircraft-layer** (fresh `.venv` built for this worktree likewise):
- `ruff format --check src tests` -- pass (85 files).
- `ruff check src tests` -- pass.
- `mypy src` -- pass, 28 files.
- `luac5.1 -p dcs-export/Petrobrain/flight_control.lua` -- pass.
- `luac5.1 -l -p ... | grep GETGLOBAL` -- clean (every name is a genuine stdlib/DCS global, no
  own-helper referenced before its `local`; re-run after the `check_envelope` edit caught one
  left-behind `ENV_BANK_MARGIN_DEG` reference the first pass missed).
- Full suite, `pytest tests -q` -- **979 passed**.

### Notable Discoveries

- **This worktree had no `.venv` for either subproject at all** (both built fresh from each
  `pyproject.toml`'s declared dependencies) -- flagging in case the main loop's worktree-creation
  step is expected to carry these forward and silently didn't this time.
- Decision 29's break floor and Decision 31's VRS cap both needed `limits.floor_agl_m` inside
  `law_update` for the first time -- it had been sent on the wire since Stage M1 but never read by
  the law itself before this batch; the toy-plant suite's own `_LIMITS` fixture needed the same
  addition, confirming the field really was new to that function, not an oversight in this round.

## Sortie 2026-11-20 follow-up: collective on, torque pedal, turn-coordination pedal

Branch `impl/collective-turn-pedal` off `fix/bl16-sortie-1120` @ `c440dbcc` (that commit's own
"collective on now, turn pedal, no tuning yet" decisions). Scope: axis-enable flags and
`law_update`'s collective/pedal steps, plus their constants and tests. Two other branches worked
the same base in parallel on a body-layer-start reset and exact-setpoint fixes — no overlap, this
batch never touched `flight_control.py`, `ai_pilot_wheel.lua`, or anything AI-wheel-adjacent.

### Files Changed

- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua`:
  - `FC_AXES_ENABLED.collective` flipped `false` → `true` (user, *"absolutely yes. Now."*). Every
    per-axis gate (`capture_from_seat`/`axis_magnitude`/`write_outputs`/the status feed) already
    iterated `FC_AXES_ENABLED`, so this one flag is the whole activation — no other write-path
    change was needed. Updated the module header, the `SIGN`/`FC_AXES_ENABLED` comment blocks, and
    `axis_command`'s own comment (it cited collective as *the* disabled-axis example) to stop
    claiming collective is off, per this project's "prune the comment you are standing next to"
    rule — pruned only the blocks directly above code this change touches, not a sweep.
  - Step 3 (`d_theta`/`u_c` split): **no behaviour change.** Added a comment confirming the
    existing split (`d_theta` only ever picks up the altitude channel's `a_z_d` term while
    `collective_limited`) already *is* "favour collective 100% while it has room" — enabling the
    axis is what makes it take effect on the real aircraft for the first time, not a change to the
    split. Verified with a toy-plant comparison (see Notable Discoveries) before writing it down as
    fact.
  - Step 5 (`K_PEDAL_FROM_COLLECTIVE_RATE`): no sign change. Added a comment tracing the existing
    positive sign against `plans/flight-control/explore-notes.md` (2026-10-26): more collective
    (more torque) needs more right pedal, which only matches the code's sign if positive `t_y` is
    "right" — itself an unmeasured guess `PEDAL_LIMIT_POSITIVE`'s own asymmetry already makes.
    Consistent, not independently confirmed; gain left at its existing, already-conservative value.
  - New `K_TURN_COORD_PEDAL` constant (step 5) and `turn_coord_pedal` state field
    (`law_init_at_take`, `law_update`, read in `law_outputs`): the turn-coordination pedal term.
    **Design note, not in the plan**: the first implementation fed `K_TURN_COORD_PEDAL * r_d` into
    the `t_y` *integrator* (the same shape `break_bias`/`d_t_y` already use) — wrong, found by
    actually running it (toy-plant probe): during a sustained ordinary turn `r_d` stays roughly
    constant for many seconds, so a rate term integrates without bound and saturates the pedal axis
    almost immediately, which is correct for a break's own short, aggressive `K_BREAK_PEDAL_BIAS`
    but wrong for ordinary-turn coordination. Rebuilt as a **position overlay**: recomputed fresh
    every `law_update` frame from the *current* `r_d`, never itself integrated, added only at
    `law_outputs` (`pedals = t_y + turn_coord_pedal`). This is what makes all three stated
    requirements fall out for free: exactly zero in straight flight (zero below
    `TURN_SETTLE_DEG_S`, reusing step 1's own "stopped turning" threshold rather than a bare
    `~= 0.0` check, since a critically-damped heading error never bit-exactly reaches zero);
    cannot stack with the break bias (gated on `rate_override_deg_s == nil`, the same mutual
    exclusion `break_bias` already uses); needs no "unwind" bookkeeping at all (it already *is* the
    unwind, every frame) — no accumulator, no settle-trigger, unlike `break_pedal_bias_accum`.
    `law_init_at_take` sets it to `0.0` so Decision 24's bit-exact-at-take guarantee is untouched.
    Sign assumption (unmeasured, flagged in the constant's own comment): pedal in the same sign as
    the turn, consistent with `PEDAL_LIMIT_POSITIVE`'s own "positive is right" guess.

### Tests Added

`aircraft-layer/tests/test_flight_control_law.py`:
- `TestCollectiveHoldsAltitudeInABankedTurn` (3 tests) — toy-plant comparison, collective-effective
  vs. collective-ineffective in a 40° banked turn: pitch demand stays exactly `0.0` and `u_c` never
  saturates when collective actually reaches the plant; pitch demand grows past 1° and `u_c`
  saturates when it does not; the direct comparison (`theta_on < theta_off`).
- `TestTurnCoordinationPedal` (4 tests) — zero throughout straight-and-level flight (covers the
  take-time no-drift requirement too); positive pedal while turning right, unwinding to exactly the
  pre-turn value once settled; the mirror negative-pedal left-turn case; suppressed to exactly
  `0.0` throughout a break, with the break's own bias unchanged (`0.5`, its pre-existing saturated
  value).

`aircraft-layer/tests/test_flight_control_lua.py` (whole-module, real `LoSetCommand` capture):
- `TestCaptureIsBitExact.test_collective_capture_writes_with_the_measured_sign` — a take now
  actually writes command 2087 (`SIGN.collective = -1.0`), not just internal law state.
- `TestAxesEnabledOnTheWire.test_all_four_axes_enabled` (renamed from `test_pedal_enabled_
  collective_disabled`, which this batch's own change makes false) — `fc_axes_collective` now
  reports `true` on the wire.

### Checks

**aircraft-layer** (this worktree has no `.venv`; ran via the main checkout's
`aircraft-layer/.venv`, pointed at this worktree's own files):
- `ruff format --check src tests` — pass (86 files; one new test file needed one auto-format pass,
  applied and re-verified clean).
- `ruff check src tests` — pass.
- `mypy src` (from `aircraft-layer/`) — pass, 28 files (no `src/` Python touched this batch; run
  for completeness).
- `luac5.1 -p dcs-export/Petrobrain/flight_control.lua` — pass.
- `luac5.1 -l -p ... | grep GETGLOBAL` — clean; every name is a genuine stdlib/DCS global or an
  existing module helper (`ai_pilot_wheel`, `client`, `debug_log`, `safe_call`, the `extract_
  json_*`/`fmt_*`/`json_escape_string` core helpers), nothing from this batch's own new locals
  (`turn_coord_bias`→removed, `turn_coord_pedal`, `pedal_step_delta`→removed) leaked as an
  undefined global.
- `pytest tests -q` (full suite) — **1012 passed** (1004 pre-existing + 8 new/changed).
- `.claude/scripts/fast-tests.sh aircraft-layer` — refused: it expects `aircraft-layer/.venv` to
  exist inside *this* worktree, which it does not (worktrees ship with no `.venv`, per this
  project's own convention); ran the full suite directly instead (above), which subsumes it.

**body-layer** — untouched (`git status --porcelain` shows no `body-layer/` changes). Ran its own
test suite anyway, since `FC_AXES_ENABLED.collective`'s wire field (`fc_axes_collective`) is
schema-parsed there: `pytest tests/test_flight_control.py tests/test_body_flight_control.py -q` —
**59 passed**, no changes needed (the one fixture mentioning `"fc_axes_collective": False` is a
wire-parsing test value, not an assertion about the Lua module's current default).

### Notable Discoveries

- **The plan's own `aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md` does not
  exist anywhere in this branch's history or on `main`** — `flight_control.lua`'s module header and
  `read_measured()`'s own comment both cite it (sign/scale measurements, the yaw-rate convention).
  It exists on an unmerged commit (`eef87430`, and its predecessors back through `b1feb9a0`) that
  is not an ancestor of `main` or of this task's base commit. Pre-existing dangling reference, not
  introduced by this batch, not touched here — flagging since the next person chasing one of those
  citations will hit the same dead end. The actual sign/scale/rotor-direction facts this batch
  needed (pedal sign asymmetry, "the hind yaws much easier to left") were available instead in
  `plans/flight-control/explore-notes.md` (2026-10-26) and the module's own already-measured
  `SIGN`/`PEDAL_LIMIT_*` constants.
- **A rate term and a position-overlay term look interchangeable until you actually run one** —
  the toy-plant probe that caught the turn-coordination integrator bug (saturating almost
  immediately during an ordinary turn) is the only reason this shipped as a position overlay
  instead of a second `break_pedal_bias_accum`-style accumulator; reading the code alone would not
  have surfaced it, since both shapes compile and both "look conservative" from the gain value
  alone without running the actual accumulation over several seconds.
- **Step 3's altitude/collective split needed no code change at all** — it already favoured
  collective fully whenever `collective_limited` is false, written before collective was ever
  enabled. The only way to see that this was already correct (rather than assume it from reading
  the `if`) was to run the toy-plant comparison and confirm `max_theta == 0.0` on the collective-
  effective side.
