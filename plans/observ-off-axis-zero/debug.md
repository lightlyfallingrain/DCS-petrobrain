### Debug Report

### Observed Issue
With the 9K113 OBSERV switch (arg 886) OFF, the ASP-17 mark was still seen moving. `docs/
acceptance/2026-10-24-sortie-feedback.md` F1, the user's own words: *"when observ is turned OFF,
either by Petrovich or by DCS AI or by player, then write 0 to both axis, but only once. Then stop
writing the axis values. We should only write axis values when observ is ON."*

### Hypothesis
`run_sight_servo` (`aircraft-layer/dcs-export/Export.lua`), the per-frame DCS-slave servo that
drives the AI slew axes (`CMD_AI_AZ`/`CMD_AI_ELEV` via `SetCommand`), early-returns on `not
observ_on` after resetting its own software state (`sight_goal_*`, `sight_setpoint_*`, etc.) — but
it never writes anything to the axes themselves on that path. `SetCommand`-driven axis values latch
at whatever was last written (confirmed independently by `aircraft-layer/research/2026-10-21-9k113-
slew-readback-probe-findings.md`: *"DCS feeds a bound analog axis every frame, so a centred stick
would write 0 to the axis every frame"* — i.e. the axis holds its last command when nothing keeps
writing it). So whatever the servo last wrote before OBSERV went off (a dither/wobble value, or a
live tracking correction) stays commanded indefinitely — the reported symptom.

### Evidence
- Read `run_sight_servo` (`dcs-export/Export.lua`, then lines ~1401–1474, now shifted by the fix):
  the `if not observ_on then ... return end` block resets only `sight_*` local state, with no call
  to `sight_point_quiet` anywhere in it.
- `sight_point_quiet` (then ~1157) is the *only* call site in the whole file for `CMD_AI_AZ`/
  `CMD_AI_ELEV` (confirmed by grep) — so nothing else could be re-asserting zero either; whatever
  was last written is simply never revisited once OBSERV goes off.
- Added a pure test (`sight_observ_transition`) and an end-to-end harness driving the real,
  unmodified `run_sight_servo` against a `GetDevice` mock, pre-fix: an "on" frame followed by an
  "off" frame produced zero `SetCommand` calls on the off frame — directly reproducing "the axis
  never gets zeroed" against the actual deployed logic, not just by inspection.

### Fix Applied
`aircraft-layer/dcs-export/Export.lua`:

1. New module-level state `sight_was_observ_on` (default `false`), reset in `LuaExportStop` alongside
   the rest of the `sight_*` block (a mission end/restart is not an observed OBSERV falling edge,
   same reasoning already written there for the rest of that state).
2. New pure helper `sight_observ_transition(observ_on, was_on)`, placed above `run_sight_servo` (and
   below everything it or `run_sight_servo` needs, per the file's existing "must stay below" Lua
   hoisting convention): returns `(write_zero, new_was_on)`. `write_zero` is true exactly on the
   on→off edge (`was_on and not observ_on`); false on every other combination, including an off frame
   with no prior on (first frame ever, OBSERV never switched on this mission, or just-reset-by-
   restart) and every off frame *after* the edge has already fired.
3. `run_sight_servo` calls this at the top of every frame (right after computing `observ_on`, before
   touching anything else), stores `new_was_on` back into `sight_was_observ_on`, and in the existing
   `if not observ_on then ... end` block — after the existing state reset, still before `return` —
   writes `sight_point_quiet(0.0, 0.0)` exactly when `observ_falling_edge` is true, and updates
   `sight_last_write_az_cmd`/`sight_last_write_el_cmd` to `0.0` so the next *on* frame's `"hold"` mode
   (which reads those as its own last-written baseline) does not resume from a stale non-zero value
   either.

0 is confirmed centre/neutral for both axes at this function's own convention: `write_az_cmd`/
`write_el_cmd` are both algebraically 0 when `write_az_deg`/`write_el_deg` are 0 (lines computing
`write_az_cmd = write_az_deg / 60.0` and the piecewise `write_el_cmd` branch — both pass through 0 at
0), consistent with the probe findings' own "a centred stick writes 0" statement.

Four transition cases named in the task, resolved:
- **First frame** (`sight_last_frame_t == nil`, unrelated to `sight_was_observ_on`): handled —
  `sight_was_observ_on` defaults to `false`, so an off first frame is "no prior on", not an edge.
- **Arg read failing** (`observe` not a number): already treated as OFF by the pre-existing
  `type(observe) == "number"` check, exactly like every other `not observ_on` path in this function
  (the full state reset already fires on a failed read today, with or without this fix). This fix
  does not change that posture — a failed read after a genuine ON state will fire the one-time zero
  write, same as a real OFF, which is the safe direction to fail toward. Not expanded further:
  distinguishing "failed read" from "genuine OFF" would be new scope, not required by the F1
  specification, and no evidence of flaky reads was found in the research notes.
- **Mission restart**: `LuaExportStop` now resets `sight_was_observ_on = false`, so the next
  mission's first off frame (if OBSERV starts off) is correctly "no prior on", not a replayed edge
  from the sortie that just ended.
- **OBSERV toggled off→on→off quickly**: each genuine edge writes exactly once; verified by the
  `test_rapid_off_on_off_each_edge_writes_once` tests (both the pure-decision and the end-to-end
  version) with an off→on→off→on→off sequence.

No other writer of `CMD_AI_AZ`/`CMD_AI_ELEV` exists in the file (confirmed by grep), so this is the
only path that needed the fix.

**`EXPORT_SCRIPT_VERSION` bump**: not needed. No JSON wire message, field, or schema changes — this
is purely internal servo logic inside `run_sight_servo`; nothing body-layer-visible changed shape.

### Verification
- `aircraft-layer/tests/test_sight_servo_lua.py`: added `TestSightObservTransition` (4 parametrized
  cases + one 5-frame rapid-toggle sequence) against the pure `sight_observ_transition`, and
  `TestRunSightServoObservOffWrites` (6 cases) driving the real, unmodified `run_sight_servo`
  end-to-end against a minimal `GetDevice`/`SetCommand` mock — covering: first frame off (no write),
  on→off (one zero write), off frame after the edge (no second write), rapid off→on→off→on→off (one
  write per genuine edge), a failed arg read after on (one zero write, same as genuine off), and a
  restart-simulated fresh-off start (no write).
- Confirmed each test actually depends on the fix, not just passes incidentally: reverted
  `sight_observ_transition` to two deliberately wrong versions (`return false, not observ_on` —
  "write every off frame"; `return false, observ_on` — "never write") and reran — 9 and 6 tests
  failed respectively, across both the pure and end-to-end classes. Restored and diffed byte-for-byte
  against the pre-mutation copy before committing (`diff` reported no difference).
- `21/21` tests in `test_sight_servo_lua.py` pass against the real fix; full suite `619/619` passes
  (`PYTHONPATH=src pytest -q`, 76.5s).
- `ruff format --check` clean after one `ruff format` pass on the new test code (two files
  reformatted: the edited test file's own line-wrapping, not the fix). `ruff check` clean (the one
  reported finding, `EXE001` on `research/2026-10-06-unit-id-join-reduce.py`, is pre-existing and
  unrelated to this change). `mypy src --strict`-config clean (28 source files, no issues). `luac5.1
  -p` parses clean. The `GETGLOBAL` scan (`aircraft-layer/CLAUDE.md`'s own-helper-leak check) shows
  no own-helper name among the globals read by the chunk — `sight_observ_transition` is correctly
  declared above `run_sight_servo`, its only caller.

**UNVERIFIED until flight** (no live DCS available to this agent):
- That `GetDevice(DEV_I9K113):SetCommand(dev, CMD_AI_AZ/CMD_AI_ELEV, 0.0)` actually centres the real
  ASP-17 mark in DCS, rather than merely stopping further AI-axis motion from whatever raw position
  the gimbal happens to be holding when the command is issued. The probe findings this fix leans on
  (`aircraft-layer/research/2026-10-21-9k113-slew-readback-probe-findings.md`) describe a centred
  *stick* writing 0, not that writing 0 to the AI command axis drives the gimbal itself back to
  mechanical centre — those may or may not be the same claim for this airframe's slew mechanism.
- That no other in-flight DCS-side process (e.g. DCS's own AI-axis damping, or an un-researched
  default-return-to-centre behaviour) interacts with a one-time zero write differently than with a
  sustained one.
- Whether the one-time write, rather than a sustained zero-every-off-frame write, is visually
  indistinguishable from "stopped" to the pilot once OBSERV goes off — the specification asked for
  exactly one write, which is what is implemented, but only a sortie confirms the mark visibly stops
  rather than drifting from whatever non-zero position it was at when OBSERV flipped off (before this
  fix, the *axis command* was the stale value, not necessarily the mark's visual position at the
  instant of the edge).
