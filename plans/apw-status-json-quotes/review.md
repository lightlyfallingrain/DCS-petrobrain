### Review Summary

Reviewed `fix/apw-status-json-quotes` (HEAD `c7f2524e`, base main `797f53db`). Fast-forwarded
this worktree onto `c7f2524e` (13 intervening main commits were new to this worktree; the fix
itself is a 4-file, net +338/-1 line commit on top of them).

The bug: `push_ai_pilot_wheel_state`'s local `text_or_null` wrapped `core.lua`'s
`json_escape_string`'s return value — which is already the full quoted JSON literal
(`'"' .. escaped .. '"'`) — in a second pair of quotes, producing `""FLT""` for every non-nil
text field. `collector/server.py`'s `_handle_line` drops the whole line on `JSONDecodeError`
before any field-level routing, so one bad string field froze every field on the AI-pilot-wheel
status line, not just the broken ones.

The fix removes the redundant outer quoting in exactly one place, matches `json_escape_string`'s
actual contract (confirmed by reading `core.lua:176-183`, unchanged), and is exercised by every
other correct caller (`encode_scalar`, `telemetry.lua`'s `name` field) in the same way the fix now
uses it.

**Mutation-checked, not just read**: reverted the Lua fix to its pre-fix form in this worktree,
ran `TestPushAiPilotWheelStateJson` — all 4 new tests fail with exactly the described
`JSONDecodeError: Expecting ',' delimiter`, including `test_all_text_fields_nil_is_valid_json`
(because `apw_goal_progress` defaults to `"idle"`, a non-nil string). Restored the fix, same 4
tests pass, working tree clean afterward (no stray diff).

**Sweep verified independently, not trusted from the debug report**: grepped
`json_escape_string` across `aircraft-layer/dcs-export/` myself (5 call sites: `core.lua`'s own
`encode_scalar`, `telemetry.lua`'s `name` field, `Export.probe-pb15.lua`'s duplicated copy, and
the fixed site) and grepped for the `'"' .. ... .. '"'` double-quoting shape directly — the only
other hit is `sight.lua:889`'s `'"' .. tostring(sight_mode) .. '"'`, confirmed by reading every
`sight_mode = ` assignment site (all eight are fixed-enum literals: `off`/`caged`/`hold`/
`homing`/`closed`/`hands_off`) — never DCS-read text, so it cannot carry a character needing
escaping and is correctly out of scope for this fix. The three Hook scripts that do emit JSON
(`petrobrain-mission-start-hook.lua`, `-mission-telemetry-hook.lua`, `-firing-events-hook.lua`)
use DCS's own shipped `Scripts\JSON.lua` encoder, not hand-rolled quoting — not susceptible to
this bug class, confirmed by reading their `JSON:encode(...)` call sites.

**Mode-2 consequence checked against the actual code, not just the debug report's narrative**:
`AiPilotWheelCache.push`/`.latest()` (`collector/cache.py`) only ever records a successfully
parsed sample and never clears on a drop; `body-layer/src/belief/ai_pilot_wheel.py`'s
`advance_parked_flight_state` only short-circuits on `sample is None` (feed never sent a line this
session) and has no staleness/timestamp check — so a `None` is the only case it protects against,
not a stale-but-non-`None` sample. The practical effect matches the debug account: once any
string field goes non-nil (which, per the `apw_goal_progress` default, is essentially from the
first AI-mode poll), `ParkedFlightState` — including `parked_active` and `player_seat`, the two
fields `body-layer/CLAUDE.md` names as mode 2's own gating condition — freezes at its last validly
parsed value for the rest of the session, rather than going null or stale-flagged.

### Required Fixes

None.

### Optional Refinements

- None of substance. The fix is minimal, scoped to exactly the defective line, and does not touch
  `json_escape_string`'s contract or any other caller.

### Verification performed

- `ruff format --check` (aircraft-layer src tests): clean.
- `ruff check` (aircraft-layer src tests): clean.
- `cd aircraft-layer && mypy src`: `Success: no issues found in 27 source files`.
- `pytest` (aircraft-layer, full suite): 885 passed.
- `luac5.1 -p` on `ai_pilot_wheel.lua`: syntax OK.
- Mutation check (see above): new tests fail pre-fix with the exact described error, pass
  post-fix, tree restored clean.
- Independent re-sweep of `json_escape_string` callers and the `'"' .. ... .. '"'` shape: no
  second occurrence found, confirming the debug report's sweep.

### `#needs-flight`

Carried forward from `plans/apw-status-json-quotes/debug.md`, unchanged by this review: a live
sortie is needed to confirm `GET /ai_pilot_wheel/latest` now advances continuously (not just once)
while the AI pilot wheel overlay shows live mode/course/altitude/speed text, and that mode 2's
seat/parked gating tracks a live seat change rather than freezing at its first value. Test on
`main` once merged (or `fix/apw-status-json-quotes` before merge).

### Verdict
APPROVED

### Review Confidence
Full read — small, self-contained fix (4 files, net +338/-1 across debug.md + test + one-line Lua
change); diff read in full, fix mutation-tested, sweep re-verified independently rather than
trusted from the debug report.
