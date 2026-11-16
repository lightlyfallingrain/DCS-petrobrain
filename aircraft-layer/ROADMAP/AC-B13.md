# AC-B13 — `LuaExportStop` does not release an open AI-pilot-wheel press

- [x] **AC-B13 — Release any open AI-pilot-wheel press and clear the takeover state in
  `LuaExportStop`, the same way that function already resets every sibling per-session state —
  done as part of `[[AC-B12]]`, DoD-PASSED 2026-11-16, merged to `main` as `e9ae92c4`.** #status/done
  #needs-flight Filed 2026-11-16 from BL-16's takeover-revision security analysis
  (`plans/flight-control/security-takeover.md`, "Risk Communication: `LuaExportStop` does not release
  an open AI-pilot-wheel press"; verdict APPROVED, this finding non-blocking).

  **The finding.** `LuaExportStop` (mission end, restart, DCS exit) resets the search wheel's own
  `pending_release_t`, the `sight_*` and `watched_*` state and `mission_start_model_t`, but not
  `ai_wheel_pending_release_t`, `ai_wheel_pending_cmd`, or the `ai_pilot_takeover` table (including
  `correction_hold_cmd`). If the export environment stops while a correction hold is open, the last
  `performClickableAction(30, cmd, 1)` is never released by this path.

  **Why it is low/low.** Pre-existing since BL-16 Batch A, when the only hold was the ≤0.7 s
  one-shot nudge; BL-16's takeover revision widened the window to the 60 s correction-hold ceiling.
  `LuaExportStop` fires only when the aircraft the press was acting on is also discarded; no
  single-player case is known where the export environment stops and the same aircraft stays
  player-controlled.

  **Fix (security's own recommendation):** about three lines in `LuaExportStop` mirroring the
  existing `pending_release_t = nil` reset — release any open AI-wheel press, then clear the
  pending-press fields and the takeover state. Add a test in the existing Lua harness.

  **Scheduling (main loop, 2026-11-16):** not held against BL-16's merge. **Pick it up in
  `[[AC-B12]]`**, which reorganises `Export.lua`'s start/stop code into modules anyway, so the reset
  lands in the AI-pilot-wheel module's own stop hook.

  **Done, 2026-11-16.** `ai_pilot_wheel.lua`'s new `on_stop()` releases any open
  `ai_wheel_pending_cmd` press (`performClickableAction(cmd, 0)`, unconditional and hardcoded to
  the release value) then clears it and every `ai_pilot_takeover` field, mirroring
  `pending_release_t`'s own reset shape elsewhere in the split. Two passing Lua unit tests
  (`test_ai_pilot_wheel_lua.py::TestOnStop`): an open press releases and every field clears; no
  open press means no spurious release but the fields still clear. Security re-verified: the
  release value is hardcoded to `0`, never a variable, so this path can only release what this
  module's own logic already set, never press anything. Reviewer confirmed the state-relocation
  map against the original file line-by-line — no field dropped. `[[BL-B117]]` (the parked flag
  and overlay text fields, a second, adjacent gap the same security analysis did not find) stays
  its own open item, deliberately not folded in here.

  **`#needs-flight`** — the Lua unit test is the primary proof; the live cross-check (restart the
  mission mid-correction-hold, confirm no cockpit control stays pressed) is this milestone's prize
  block, carried on `[[AC-B12]]`'s own card:
  https://claude.ai/artifact/5Q1za4baC6VNYaRoScNuyc. **Branch to fly: `main`.**
