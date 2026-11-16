### Implementation Summary

Split `aircraft-layer/dcs-export/Export.lua` (3,200 lines, 200 top-level locals) into a short
`dofile` loader plus eight module files under the new `aircraft-layer/dcs-export/Petrobrain/`
directory (plan's U2), with no behaviour change except AC-B13's one approved fix (release any open
AI-pilot-wheel press and clear the takeover state in the stop hook). Mapped to the plan's stages:

- **Stage 1-4 (module cut + wiring):** built in one pass rather than incrementally per the plan's
  stage order (`core`/`commands` skeleton first, then move modules one at a time) — the cross-module
  design (see "Decisions" below) had to be settled before any one module could be written correctly,
  so staging the *commits* after the fact (one per logical group) was more useful than staging the
  *build*. Every module parses clean (`luac5.1 -p`), passes the local-order check, and is well under
  the 200-local ceiling.
- **Stage 5 (test file paths):** all seven affected `test_*_lua.py` files updated; the two
  glob-based tests widened per U2.
- **Stage 6 (AC-B13's own test):** added to `test_ai_pilot_wheel_lua.py` — extracts the real
  `on_stop`, asserts the release call fires and every takeover field clears. Counterfactual-checked:
  removing the release call from `ai_pilot_wheel.lua` made the test fail for the stated reason,
  restored by checksum (`shasum` before/after matched).
- **Stage 7 (WORKFLOW.md):** deploy step updated to copy the whole `Petrobrain/` folder alongside
  `Export.lua`; U1's "version check is the whole check" stated explicitly.
- **Stage 8 (live check flight):** not performed — this is the user's own live acceptance step, per
  the plan's Verification section. Not claimed as done.

### Files Changed

- `aircraft-layer/dcs-export/Export.lua` — reduced to the loader: `load_module` (dofile +
  pcall-guard + publish each module's table as a bare global), `core.init(EXPORT_SCRIPT_VERSION)`,
  and the four composed `LuaExport*` callbacks dispatching into every module in the exact original
  per-frame/5 Hz order. `EXPORT_SCRIPT_VERSION` stays here, unbumped (no wire-format change). Full
  historical bump-comment block kept intact (restored after an initial over-aggressive trim — see
  "Notable Discoveries").
- `aircraft-layer/dcs-export/Petrobrain/core.lua` (new) — shared infra: `require("socket.core")`,
  the collector TCP connection (`client`, a bare global per the "no textual change to moved bodies"
  constraint), the 5 Hz gate (`tick_due`), connect/reconnect (`ensure_connected`/`on_start`/
  `on_stop`), debug logging, JSON helpers, `extract_json_*`, `WHEEL_MENU_BUTTON`/
  `WHEEL_CENTER_BUTTON`. Every cross-module helper is declared `local function`/`local NAME = value`
  (so the test harness's extraction regex finds it) and separately published to `_G` right before
  `return M`.
- `aircraft-layer/dcs-export/Petrobrain/telemetry.lua` (new) — ownship line + `LoGetWorldObjects`
  feed + loadout feed. `send_ownship(t)` returns `true` only once the line has gone out — the gate
  the loader uses for every downstream push this tick, replacing the single-file version's one
  shared early `return`. `send_world_objects(t)` is a separate entry point, called by the loader
  *after* `effectors.push_watched_args_state`/`telemetry.push_payload_state`, preserving the
  original send order exactly (world-objects last, so its own possible send failure never
  retroactively un-sends what already went out this tick).
- `aircraft-layer/dcs-export/Petrobrain/petrovich.lua` (new) — HelperAI classification feed +
  AI-Wheel search effector (BL-6). Reads `WHEEL_MENU_BUTTON`/`WHEEL_CENTER_BUTTON` from `core`.
  `handle_petrovich_search_command` normalized to `(data, t)`.
- `aircraft-layer/dcs-export/Petrobrain/sight.lua` (new) — the whole 9K113 sight/servo subsystem.
  Largest module by a wide margin (confirmed, see "Notable Discoveries"). `handle_sight_target_
  command` normalized to `(data, t)`.
- `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua` (new) — BL-16's AI-pilot takeover.
  **AC-B13's fix lives in `on_stop`**: releases any open `ai_wheel_pending_cmd` press, then clears
  it and every `ai_pilot_takeover` field. Deliberately does not touch `ai_pilot_parked_active` or
  the overlay text fields (BL-B117, filed separately, left alone).
- `aircraft-layer/dcs-export/Petrobrain/effectors.lua` (new) — `watch_args`/`read_args` +
  unrestricted `cockpit_switch`. `handle_cockpit_switch_command` normalized to `(data, t)`.
  `force_resend()` is the new entry point the loader calls on a fresh (re)connect, replacing the
  two inline `watched_force_send = true` call sites.
- `aircraft-layer/dcs-export/Petrobrain/ptt_ics.lua` (new) — PTT, SPU-8 panel, mission-start
  co-pilot ICS write. `on_mission_start_tick(t)` does its own `LoGetSelfData` check rather than
  depending on `telemetry.send_ownship`'s field-completeness gate — matches the original's exact
  dependency (self_data non-nil only), confirmed by re-reading the original call order.
- `aircraft-layer/dcs-export/Petrobrain/commands.lua` (new) — inbound UDP listener only, loaded
  last. Dispatch table built directly from the other modules' handler functions (all now uniform
  `(data, t)`), no adapter closures.
- `aircraft-layer/WORKFLOW.md` — deploy step copies the whole `Petrobrain/` folder alongside
  `Export.lua`; states U1 (version check is the whole deployment-staleness check, no per-module
  stamp) and the `win-mac-sync` mirror note (that folder is gitignored/local, so no file to create
  here — documentation only).
- `aircraft-layer/tests/test_ptt_lua.py`, `test_payload_lua.py`, `test_ai_pilot_wheel_lua.py`,
  `test_sight_servo_lua.py`, `test_watched_args_lua.py`, `test_export_lua_constants_parity.py`,
  `test_exponent_float_fix.py` — every `_extract_lua_function`/`_extract_lua_constant`/
  `_lua_constant` call site now takes/resolves a `path: Path` pointing at the function's new home
  file. Two files (`test_ptt_lua.py`, `test_payload_lua.py`) needed exactly two paths, matching the
  plan's own prediction; `test_ai_pilot_wheel_lua.py` needed a per-name split for
  `WHEEL_CENTER_BUTTON`/`WHEEL_MENU_BUTTON` (core.lua) vs. everything else (ai_pilot_wheel.lua).
- `aircraft-layer/tests/test_dcs_export_lua_syntax.py`, `test_dcs_export_lua_local_order.py` — glob
  widened from `*.lua` to `**/*.lua` (U2), no other change.
- `.claude/agent-memory/implementer/project_export_lua_split_test_harness_dictates_global_local_boundary.md`
  (new) — the test-harness-regex constraint on the global/local design, and the exact-order-tracing
  lesson.

### Tests Added

- `TestOnStop::test_open_hold_press_is_released_and_every_field_cleared` — AC-B13's own test (plan
  Stage 6): extracts the real `ai_pilot_wheel.lua` `on_stop`, presets an open `AI_WHEEL_DOWN` hold,
  asserts the release call fires with value `0` and every `ai_pilot_takeover` field is `nil`/`false`
  afterward. Counterfactual-verified: removing the release call made this fail for the stated
  reason (`press_log` empty instead of `"3005:0"`), then restored by checksum.
- `TestOnStop::test_no_open_press_releases_nothing_but_still_clears_state` — no stale press
  (`ai_wheel_pending_cmd` already `nil`) → no spurious release call, but every takeover field still
  clears.

### Checks

(aircraft-layer/ — the only subproject touched; nothing in `body-layer/` or `world-model/` changed)

- `luac5.1 -p` on `Export.lua` and all 8 new `Petrobrain/*.lua` files: pass
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `cd aircraft-layer && .venv/bin/mypy src`: pass (27 source files, no issues)
- `pytest tests -q`: 792 passed (0 skipped, 0 failed) — confirmed the 139 Lua-interpreter-backed
  tests across the 7 affected files ran (not skipped) by running them with `-v` and grepping for
  `SKIPPED`/`FAILED`/`ERROR` (none found), per this project's "never report done from a filtered run"
  convention.
- `test_dcs_export_lua_local_order.py::test_no_local_read_as_global` passes for all 8 new module
  files and the loader — the mechanical proof that the global/local cross-module design has no
  leaked ordering bugs.
- Per-module `grep -cE '^local ' <file>` headroom check — see "Notable Discoveries", sight.lua
  exceeds the plan's own ~60 soft target.

### Decisions Made

- **Cross-module channel, two tiers.** (1) Pure per-frame helpers that existing function bodies
  call by a bare name (`safe_call`, `debug_log`, `json_escape_string`, `encode_scalar`,
  `fmt_num_or_null`, `extract_json_*`, `WHEEL_MENU_BUTTON`/`WHEEL_CENTER_BUTTON`, and `client` itself)
  are declared in `core.lua` and published as bare globals via `_G.NAME = NAME` — required both by
  the "dofile chunks share no locals" mechanism and by the Lua test harness's `local function NAME(`
  extraction regex (see new agent-memory file). (2) Each module's own *entry points* (the functions
  the loader or `commands.lua` calls across the module boundary) are collected into that module's
  returned table and the table itself is published as a bare global of the module's name by the
  loader's `load_module`, so `commands.lua`'s dispatch table and the loader's composed callbacks can
  write `petrovich.handle_petrovich_search_command`, etc.
- **`core.ensure_connected`/`core.on_start` return `(connected, fresh)` rather than calling
  `effectors.force_resend()` from inside `core`.** Keeps `core.lua` ignorant of `effectors` entirely;
  the loader (which already holds every module reference) is the one place that wires "fresh connect
  → force a full watched-args resend" — matches this split's own "every dependency explicit and
  visible in the loader" principle better than having `core` reach into a module loaded after it.
- **Converted every `function M.xxx(...)` to `local function xxx(...) + M.xxx = xxx`.** Originally
  wrote stop/start hooks as direct table-method definitions; AC-B13's required test (Stage 6) needs
  to extract `on_stop` with the same regex every other test uses, which only matches `local
  function NAME(`. Applied uniformly across all eight files rather than only where a test currently
  needs it, so a future test can extract any entry point the same way.
- **`ptt_ics.on_mission_start_tick` re-reads `LoGetSelfData` independently rather than depending on
  `telemetry.send_ownship`'s own gate.** Confirmed from the original file that the mission-start ICS
  logic only ever depended on `self_data` being non-nil, never on the ownship line's field-
  completeness or send success (it ran *before* the field-completeness check in the original). A
  second cheap `safe_call(LoGetSelfData)` per 5 Hz tick, not a new pattern — `run_sight_servo` and
  others already call it independently too.
- **`admit_read` lives in `effectors.lua` but is called from `commands.lua`** (`effectors.
  admit_read(reads_this_frame)`), since the per-frame read cap it guards is effectors' own constant
  (`MAX_READS_PER_FRAME`) even though its one caller (`poll_command_socket`) is in `commands.lua`.
  Exposed via the module table like any other cross-module entry point.
- **`ACTIVITY_LOG_LIMIT` duplicated** (as a tiny unrelated diagnostic constant) in both `Export.lua`
  (for `LuaExportActivityNextEvent`'s own counter) and `telemetry.lua` (for `send_ownship`'s send
  counter) rather than shared through `core` — matches this project's own accepted "a hand-sync
  burden for one incidental number is not worth the coupling" pattern (e.g. the `GIMBAL_*`
  constants' own comment).
- **Did not bump `EXPORT_SCRIPT_VERSION`.** Neither the module split nor AC-B13's fix changes the
  wire format or any field's meaning — nothing for a collector to misread.

### Could Not Do / Left Alone

- **Stage 8, the live check flight** — not performed. This is explicitly the user's own acceptance
  step (root `CLAUDE.md`: "Do not claim anything works live"). `WORKFLOW.md`'s deploy steps are
  updated and ready for it.
- **BL-B117** (the parked flag / overlay text fields not reset on stop) — left alone as instructed;
  it is its own filed backlog item, not part of this scope.
- **Part 2 ("read only what is needed")** — not built, per the plan's own scope.

### Notable Discoveries

- **`sight.lua` exceeds the plan's own ~60-top-level-local soft target**: `grep -cE '^local '
  Petrobrain/sight.lua` → 84 (and every other module comfortably under: core 29, telemetry 10,
  petrovich 14, ai_pilot_wheel 37, effectors 20, ptt_ics 24, commands 10, loader 14). The actual Lua
  5.1 200-per-chunk ceiling this split exists to relieve is not at risk — `luac5.1 -p` passes with
  wide headroom (84 vs. 200) — but the plan's stated target ("no module above ~60... generous
  headroom") is a soft guideline the plan itself anticipated might not hold for this one module
  ("the largest module by a wide margin"). Not restructured further: splitting the 9K113 subsystem
  into two files would depart from the plan's own decided module cut, which is outside this
  implementer's authority to change unilaterally. Flagging for Reviewer/the user rather than
  resolving silently.
- **An initial draft of the `EXPORT_SCRIPT_VERSION` comment block over-trimmed the dated
  version-bump history** (11 dated entries from 2026-10-05 through 2026-11-16) while rewriting the
  surrounding prose for the loader. Caught and restored verbatim before committing — per this
  project's own rule, a dated provenance line is never pruned, only superseded. No functional
  impact (caught pre-commit), noted here because it is exactly the failure mode the rule exists to
  prevent and is worth a future reader knowing was checked.
- **The plan's own illustrative `LuaExportAfterNextFrame` composition snippet groups `telemetry`'s
  ownship+world-objects send as one call, ahead of `watched_args`/`payload`/the Petrovich feeds** —
  but the real file's order is ownship → watched_args → payload → world_objects → Petrovich
  (indication, then wheel), with world_objects able to null `client` on a failed send. Following the
  snippet literally would have let a world-objects send failure retroactively suppress watched_args/
  payload pushes that, in the original, had already gone out before world_objects was ever polled.
  Resolved by splitting `telemetry`'s entry point into `send_ownship` + `send_world_objects` and
  calling them in the file's real original order (see "Decisions" above) — the plan's own disclaimer
  ("Illustrative only... the order must not change") governs here.
- **Comments pruned**: 4 "must stay below `safe_call`/`fmt_num_or_null`" ordering notes in
  `sight.lua` (on `push_slew_trace` and `run_sight_servo`) had their mentions of `safe_call`/
  `fmt_num_or_null` removed — those names are now bare globals with no file-order sensitivity at
  all, so the claim "must stay below" them is false post-split. The rest of each comment (ordering
  relative to genuinely still-local same-file constants/functions) was kept, since that constraint
  is still real.
