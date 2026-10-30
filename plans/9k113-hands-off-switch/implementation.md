### Implementation Summary

Added a hands-off switch for the 9K113 sight servo, so the pilot can hand-slew the sight onto
ground targets at known depression angles to calibrate `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL`
without Petrovich's per-frame servo write fighting the input. User's own words, 2026-10-30: *"I
can point the 9K113 by hand - Petrovich *must not* write axis values then."*

This task had no Architect-produced `plan.md` — it was dispatched directly as a small, fully
scoped change (branch `feature/9k113-hands-off-switch`). This file is the implementation record
in its place, and is what the code comments below cite (there is no `plan.md` in this directory).

**Flag**: `Saved Games\DCS\Scripts\aircraft_layer_sight_hands_off.flag`, checked once at load,
same pattern as the existing `SLEW_DEBUG`/`aircraft_layer_slew_debug.flag` block.

### Files Changed
- `aircraft-layer/dcs-export/Export.lua`:
  - New `SIGHT_HANDS_OFF` load-time flag (declared right after the `SLEW_DEBUG` block), plus a
    one-line `debug_log` announcement when active.
  - **The write-blocking gate lives inside `sight_point_quiet`** (`if SIGHT_HANDS_OFF then return
    end`, before the `GetDevice(DEV_I9K113)`/`SetCommand` calls) — confirmed by `grep` that this
    is the *only* place in the file that calls `SetCommand` on `CMD_AI_AZ`/`CMD_AI_ELEV`, so
    gating here blocks every current caller (the per-frame correction and the OBSERV
    falling-edge zero write, both inside `run_sight_servo`) and any future one, by construction,
    rather than by remembering to repeat the check at each call site.
  - **`run_sight_servo` itself is deliberately *not* gated.** It already sits at Lua 5.1's
    60-upvalue-per-closure ceiling — confirmed live: adding a single `if SIGHT_HANDS_OFF then
    return end` inside it pushed `luac5.1 -p` to report "function at line 1581 has more than 60
    upvalues" and fail the syntax check outright. Reverted; see "Notable Discoveries" below.
  - New small function **`sight_servo_tick(t)`**, declared right after `run_sight_servo` (so it
    can call it, per the file's "local must be declared above its use" rule) — the single
    per-frame entry point `LuaExportAfterNextFrame` now calls instead of `run_sight_servo`
    directly. When `SIGHT_HANDS_OFF` is set it sets `sight_mode = "hands_off"` and returns
    without calling `run_sight_servo` at all (so the goal/mark/stall tracking that feeds the
    writes is skipped too, not just the writes themselves); otherwise it calls `run_sight_servo`
    unchanged. This keeps the hands-off check off `run_sight_servo`'s upvalue budget entirely.
  - `push_slew_trace` (the per-frame SLEW_DEBUG trace) is untouched and confirmed independent —
    it reads device args/mark values directly via `GetDevice(0)`, never through any `sight_*`
    module-level variable or `SIGHT_HANDS_OFF`, so it keeps logging raw 555/566 and gimbal args
    every frame regardless of the hands-off flag.
  - Updated the `push_sight_servo_state` doc comment's mode-string list (five → six, `hands_off`
    added) since it's directly adjacent to the new `sight_servo_tick` function this change added.
- `aircraft-layer/src/schema/sight_servo.py` — updated the module docstring's mode-string count
  (five → six) for the same reason. No enum/validation exists on either side (`mode` is passed
  through verbatim, confirmed by reading the file) — nothing to add there, just the stale prose.
- `aircraft-layer/tests/test_sight_servo_lua.py`:
  - Fixed a latent bug in `_extract_lua_function` (see "Notable Discoveries").
  - `_run_field_park_sequence` gained `hands_off: bool = False`, routing every frame through the
    real, extracted `sight_servo_tick` (not `run_sight_servo` directly, and not a Python-level
    mirror of what the flag should do).
  - New `_run_sight_point_quiet` helper + `TestSightPointQuietHandsOffGuard` — calls the real
    `sight_point_quiet` directly, bypassing `sight_servo_tick`/`run_sight_servo` entirely, because
    `sight_servo_tick`'s own early return means `sight_point_quiet` is never actually reached
    while hands-off inside `TestRunSightServoHandsOff` below. Without this class, `sight_point_
    quiet`'s own guard would have zero test coverage despite being the gate the plan asked for at
    "the single write site".
  - New `TestRunSightServoHandsOff` (4 tests): closed-mode-with-a-goal, hold mode, and an OBSERV
    on→off edge, each asserting no write and `mode == "hands_off"` while the flag is set, plus one
    confirming unchanged behaviour (writes occur, mode is the ordinary value) while it is unset.

### Tests Added
- `TestSightPointQuietHandsOffGuard::test_hands_off_blocks_the_write` / `test_unset_writes_both_axes`
  — the write-blocking gate itself, in isolation from `sight_servo_tick`.
- `TestRunSightServoHandsOff::test_hands_off_blocks_write_in_closed_mode_with_a_goal`
- `TestRunSightServoHandsOff::test_hands_off_blocks_write_in_hold_mode`
- `TestRunSightServoHandsOff::test_hands_off_blocks_the_observ_falling_edge_zero_write`
- `TestRunSightServoHandsOff::test_hands_off_unset_leaves_behaviour_unchanged`

**Counterfactuals actually run** (per-rule: a passing test on an assertion of absence is only
evidence if the break was executed): removed `sight_point_quiet`'s own guard —
`TestSightPointQuietHandsOffGuard::test_hands_off_blocks_the_write` went red for the stated
reason, the sibling test stayed green; restored (checksum-verified byte-identical before/after).
Separately, reduced `sight_servo_tick` to an unconditional `run_sight_servo(t)` call — all three
"blocks" tests in `TestRunSightServoHandsOff` went red (mode mismatch), the "unset" test stayed
green; restored (checksum-verified). Confirmed `TestRunSightServoHandsOff` alone, as originally
written with a Python-level mirror of the skip logic instead of calling the real
`sight_servo_tick`, would **not** have caught either break — that's why the harness was changed to
call the real extracted function (see Notable Discoveries).

### Checks
(aircraft-layer/ only — body-layer/ was read for the mode-string/schema question, per the task,
but not modified; no enum exists there to update)
- `luac5.1 -p dcs-export/Export.lua`: pass
- `ruff format --check`: pass (75 files already formatted)
- `ruff check`: pass (All checks passed!)
- `mypy src` (strict): pass (Success: no issues found in 26 source files)
- `pytest -q` (full suite, from `cd aircraft-layer`): 649 passed, 2 deselected. The 2 deselected
  (`test_collector_server_accept_errors.py`, `OSError: [Errno 98] Address already in use`) are a
  pre-existing, environment-only port-binding collision — this change never touches
  `collector/server.py` and does not use sockets; confirmed by running `tests/test_sight_servo_
  lua.py` plus the three other Export.lua-adjacent test files on their own (187 passed) and the
  full suite before any of this change's edits existed (same 2 failures, verified first as a
  baseline). No tools/venv of this layer's own exist in this worktree (gitignored, not created
  by the agent harness) — ran via `body-layer/.venv`'s `ruff`/`mypy`/`pytest` binaries with `cwd`
  set to this worktree's `aircraft-layer/` directory (per `.claude/agent-memory/implementer/
  feedback_worktree_no_venv.md`); `aircraft-layer/pyproject.toml` declares no dependencies of its
  own, so this borrows only the tool binaries, not any dependency resolution.

### Notable Discoveries
- **Lua 5.1's 60-upvalue-per-closure ceiling is real and `run_sight_servo` is already at it.**
  Confirmed live by `luac5.1 -p`: adding one more upvalue reference to that function (even a
  single `if SIGHT_HANDS_OFF then return end`) fails with "function at line 1581 has more than 60
  upvalues". This is why the hands-off check could not live inside `run_sight_servo` itself and
  had to move to a new wrapper function, `sight_servo_tick`, called from `LuaExportAfterNextFrame`
  instead. Worth flagging for any future change to that function: it has essentially zero upvalue
  headroom left, and the usual move of "just add one more `if` at the top" will fail the syntax
  check, not just misbehave at runtime.
- **`_extract_lua_function` (this test file's own helper, duplicated from `test_exponent_float_
  fix.py`) had a latent, previously-silent bug**: its depth counter matches the bare words
  `function`/`if`/`end` anywhere in the raw text, including inside `--` line comments. A comment
  reading "a mission end/restart..." several hundred lines past `run_sight_servo`'s real closing
  `end` happened to rebalance the count by coincidence for every extraction so far, so every
  existing test was (and still is, after the fix) passing against a chunk that was always longer
  than intended — confirmed by extracting `run_sight_servo` from the pre-change file: 379 lines,
  not its real ~230. Adding `sight_servo_tick` shifted that coincidental rebalancing point past
  the end of the file, which is what actually surfaced the bug (the harness's generated script
  failed to compile at all, "'end' expected ... near '<eof>'"). Fixed by skipping `--` line
  comments while counting (block comments `--[[ ]]` are not handled — this file's only one is the
  header before line 107, well before anything ever extracted). This fix is local to this test
  file's own copy of the helper (deliberately not shared with `test_exponent_float_fix.py`'s copy,
  per this file's own module docstring on why the two are duplicated rather than imported) — that
  other copy was not touched and was not in scope for this task, but may have the same latent
  issue if a future edit there adds or moves a function near a similarly-worded comment.
- **No schema enumerates `servo_mode`'s allowed strings on either side** of the aircraft-layer/
  body-layer boundary (checked both `aircraft-layer/src/schema/sight_servo.py` and body-layer's
  `sight_trace_writer.py`/`body.py` consumers) — only the schema module's own docstring listed the
  five strings in prose, now six. No enum validation exists to extend; `"hands_off"` passes
  through exactly like any other mode string already does.
- **Neither `DEBUG` nor `SLEW_DEBUG` logs its own activation at load** anywhere in `Export.lua`
  (confirmed by `grep` for "enabled" — zero hits) — the task's instruction to log one line "if
  that pattern exists for SLEW_DEBUG" has no existing pattern to mirror. Added the log line anyway
  (gated through the existing `debug_log`, itself gated on `DEBUG`) since it directly answers what
  the instruction asked for and is the one observable signal during an actual calibration flight
  that the flag took effect — flagged here as a judgment call rather than a silent deviation.
- **The slew-debug flag is not documented anywhere outside `Export.lua`'s own comments** —
  `grep -rl "aircraft_layer_slew_debug.flag"` across `aircraft-layer/` returns only `Export.lua`
  itself; `WORKFLOW.md` and `CLAUDE.md` don't mention it. The task's instruction to "mirror it"
  into user-facing docs has no existing location to mirror into, so no doc change was made —
  flagging this rather than inventing a new doc section unprompted.
