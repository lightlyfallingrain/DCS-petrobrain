### Review Summary

Fix for `docs/acceptance/2026-10-24-sortie-feedback.md` F1: `run_sight_servo`'s AI slew axes
(`CMD_AI_AZ`/`CMD_AI_ELEV` via `SetCommand`) latched at whatever was last written when OBSERV went
off, because the pre-existing `if not observ_on then ... return end` path reset only software state,
never the axes. The fix adds a one-time zero write on the genuine on→off edge (`sight_observ_
transition`, a pure helper) and nothing on any other off frame, plus a `LuaExportStop` reset so a
mission restart can't replay a stale edge from the previous sortie.

Scope is tight: one file changed for the fix (`Export.lua`, +56/-3), one test file added, plus the
sortie-feedback doc and `debug.md` already in from the branch's earlier commits. No wire/schema
change, correctly judged not to need an `EXPORT_SCRIPT_VERSION` bump.

Verified independently (not just read):
- `git rev-parse HEAD` vs expected tip `aff9f5eb` — matched after fast-forward; tree clean throughout.
- Grepped every `CMD_AI_AZ`/`CMD_AI_ELEV`/`SetCommand` site in `Export.lua`: exactly two call sites —
  the new off-edge zero write and the pre-existing on-path write inside `if observ_on`. No other
  writer exists, so no sibling path was missed (the "parallel treatment" check in `reviewer.md` has
  nothing else to check here — this is a single mechanism, single call site).
- `LuaExportStart`/`LuaExportStop` read directly: `LuaExportStop` resets `sight_was_observ_on = false`
  alongside the rest of the `sight_*` block; `LuaExportStart` does not touch it (correct — a
  mid-mission reconnect must not fabricate a spurious edge).
- Confirmed `sight_last_write_az_cmd`/`sight_last_write_el_cmd` are the actual baseline `sight_mode ==
  "hold"` reads on a later on-frame (line ~1621/1633) — zeroing them on the edge is load-bearing, not
  cosmetic; without it, resuming OBSERV would hold from the stale pre-off value.
- **Ran the tests myself, didn't just read them pass.** `21/21` in `test_sight_servo_lua.py`,
  `619/619` full suite. Then mutated `sight_observ_transition`'s off-branch (`return was_on, false` →
  `return true, false`, i.e. "write on every off frame") and reran: 6 of 21 tests failed, confirming
  the suite actually depends on the fix rather than passing incidentally.
- `ruff format --check`, `ruff check`, `mypy --strict` (28 files), `luac5.5 -p` (no `luac5.1` in this
  worktree; syntax-only, same limitation the implementer's own `debug.md` notes they covered with the
  correct `luac5.1`) all clean. Re-ran the `GETGLOBAL`-equivalent own-helper-leak scan against
  `luac5.5`'s `GETTABUP`/`_ENV` opcode (5.5 has no `GETGLOBAL` instruction, so the exact `aircraft-
  layer/CLAUDE.md` recipe doesn't transfer byte-for-byte) — no own-helper name read as a global;
  `sight_observ_transition` is correctly declared above `run_sight_servo`, its only caller.
- Queried the knowledge graph and agent memory for OBSERV/9K113 slew context before concluding
  anything — nothing in either store contradicts the fix or the debug.md's "unverified until flight"
  list. The one related finding ("switch write animates over ~3 frames", `aircraft-layer/research/
  2026-10-17-9k113-effector-and-slew-probe-findings.md`) is about `performClickableAction`-driven
  cockpit toggle switches, a different write path from `SetCommand` on the continuous AI axis — it
  doesn't bear on this fix.

### Required Fixes

None.

### Optional Refinements

- **Failed OBSERV read (arg 886) is treated as a genuine off-transition, not held.** When `safe_call`
  can't read the argument, `type(observe) == "number"` is false and `observ_on` becomes `false` —
  exactly like every other `not observ_on` path in this function, pre-existing and unchanged by this
  fix in *that* sense. But this fix does add something new for that case: a failed read immediately
  after a genuine ON state now fires the one-time zero write (a visible snap to centre) that didn't
  exist before, since before this fix a failed read caused no axis write at all (the original bug,
  just silent instead of a glitch). The user's spec names three causes for the edge — Petrovich, DCS
  AI, player — and a telemetry read hiccup is none of them. `debug.md` names this explicitly and
  argues it's the safe direction to fail toward (commanding a stop rather than continuing to assert a
  stale value), and there's no evidence in `aircraft-layer/research/` of `get_argument_value` actually
  being flaky for this device. I agree failing toward a stop is the right default, and don't think
  this needs to block — but it is a new failure surface this fix introduces (a transient read glitch
  can now cause one visible recentre even though OBSERV never physically moved), and holding state on
  a failed read (treat it as "no sample this frame", skip the transition decision entirely, keep
  `sight_was_observ_on` as-is) would remove that surface entirely at no cost, since no real OBSERV
  edge is ever lost by waiting one frame for a working read. Worth doing if/when this path is touched
  again; not worth a round-trip now given no observed flakiness.
- `test_mission_restart_does_not_replay_stale_edge` doesn't actually exercise a *restart after a true
  ON state* (it starts the sequence straight from off, same as `test_first_frame_off_writes_nothing`)
  — it documents the restart scenario in its docstring/name but the assertion is identical to the
  first-frame test. A stronger version would run an on→(simulated `LuaExportStop` reset)→off sequence
  and show no write, which is the scenario the debug report actually names. Cosmetic; the real
  guarantee (the reset itself) is already read and confirmed correct above.

### Verdict
APPROVED

### Review Confidence
Full read.
