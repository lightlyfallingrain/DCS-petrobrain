### Debug Report

### Observed Issue

The AI-overlay status push from `Export.lua` (`aircraft-layer/dcs-export/Petrobrain/
ai_pilot_wheel.lua`'s `push_ai_pilot_wheel_state`) produces invalid JSON whenever any
text field on the line is non-`nil`. `aircraft-layer/src/collector/server.py`'s
`_handle_line` runs `json.loads` on every received line and drops the whole line on
`JSONDecodeError` (`logger.warning("dropping malformed (non-JSON) line: %r", line)`).
`docs/acceptance/2026-11-16-bl16-batch-a-feedback.md` shows every `apw_*_text` field
as `null` in body-layer's view while the AI pilot wheel was actively flying — the
flight symptom this defect explains.

### Hypothesis

Confirmed as given in the Implementer's note, with one correction: the bug is not
limited to the five `apw_*_text` fields named in the flight evidence — it fires on
**every** string field `push_ai_pilot_wheel_state` sends through its local
`text_or_null` helper, which also includes `apw_takeover_stage`, `apw_correction_path`,
`apw_seat`, and `apw_goal_progress` (whose code default, `"idle"`, is itself a non-nil
string — so the line is malformed essentially from the first poll onward, not only
once the overlay shows text).

Root cause: `aircraft-layer/dcs-export/Petrobrain/core.lua`'s `json_escape_string(s)`
(line 180) already returns the **full quoted JSON literal** (`'"' .. escaped .. '"'`),
not just the escaped inner body. `text_or_null` (line ~1371, pre-fix) wrapped that
already-quoted result in a second pair of quotes:

```lua
return '"' .. json_escape_string(value) .. '"'
```

producing `""FLT""` for `value = "FLT"` — not a JSON string, two adjacent tokens
(`""` then garbage), which `json.loads` rejects as "Expecting ',' delimiter".

### Evidence

Extracted `push_ai_pilot_wheel_state` plus `core.lua`'s `fmt_num_or_null`/
`json_escape_string` and ran them standalone under `luajit` against a fake
`client:send` capturing the sent line (same extraction technique
`aircraft-layer/tests/test_ai_pilot_wheel_lua.py` already uses elsewhere in this file).

Pre-fix, with only `ai_pilot_mode_text = "FLT"` set and every other text field at its
code default:

```
{"t":123.456,"apw_parked_active":false,"apw_mode_text":""FLT"","apw_course_text":null,
 ...,"apw_goal_progress":""idle"",...}
```

`json.loads` on that line: `JSONDecodeError: Expecting ',' delimiter: line 1 column 58
(char 57)`. Confirms both the exact mechanism and that the default `"idle"`
`apw_goal_progress` value is independently broken, not only the five `_text` fields.

### Fix Applied

`aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`, `push_ai_pilot_wheel_state`'s
`text_or_null`: removed the redundant outer pair of quotes, since `json_escape_string`
already returns the quoted literal:

```lua
local function text_or_null(value)
    if value == nil then
        return "null"
    end
    return json_escape_string(value)
end
```

`json_escape_string`'s own contract (escape backslash/quote/newline, return a quoted
literal) is unchanged — this fix only removes a caller's incorrect re-wrapping of that
contract's output, not the contract itself.

**Sweep of every other `json_escape_string`/hand-built-JSON caller for the same
double-quoting shape** (`grep -rn "json_escape_string" aircraft-layer/dcs-export/`,
plus a manual read of every hand-rolled JSON line in `Petrobrain/*.lua`, the probe
file that duplicates these helpers, and every Hook script):

- `core.lua`'s `encode_scalar` (string branch) — calls `json_escape_string` directly,
  no extra wrapping. Correct.
- `telemetry.lua` (`name` field, world-objects line) — calls `json_escape_string`
  directly. Correct.
- `Export.probe-pb15.lua` (a probe, not deployed pipeline code) — its own duplicated
  `json_escape_string`/`encode_scalar`, used the same correct way as `core.lua`'s.
  Correct; not touched (probes are out of scope for a pipeline fix, and this one has
  no bug).
- `sight.lua`'s `push_sight_servo_state` builds `'"' .. tostring(sight_mode) .. '"'`
  by hand, bypassing `json_escape_string` entirely. **Not the same bug** — `sight_mode`
  is drawn only from a fixed internal enum (`off|caged|hold|homing|closed|hands_off`,
  per that function's own docstring), never DCS-read-back or arbitrary text, so it can
  never contain a character that needs escaping. Confirmed by reading every assignment
  site; left unchanged (no live defect, and this is a bug fix, not a style pass — see
  root `CLAUDE.md` "Do not mix cleanup or refactor work into a bug fix").
- The Hook scripts (`petrobrain-mission-start-hook.lua`, `petrobrain-mission-telemetry-
  hook.lua`, and the rest) build their JSON through DCS's own shipped `Scripts\JSON.lua`
  encoder (`JSON:encode(...)`), never through `json_escape_string`/hand-rolled
  concatenation. Not susceptible to this bug class.

No second occurrence of the double-quoting defect found.

### What mode 2 lost

`collector/server.py` drops the **entire line** on a `JSONDecodeError`, before the
`"apw_parked_active" in data` routing check ever runs — so every field on the status
line was lost together, not just the broken text fields: `apw_parked_active`,
`apw_seat`, `apw_arg852`/`apw_arg952`, `apw_takeover_stage`, `apw_correction_path`,
`apw_goal_progress`, `apw_goal_seq`, `apw_cam_fwd_m`.

`aircraft-layer/src/collector/cache.py`'s `AiPilotWheelCache` only ever records a
*successfully parsed* line (`.push()` is never called with a drop); `.latest()` then
keeps returning the **last successfully-parsed sample**, not `None` and not a
staleness marker. `body-layer/src/belief/ai_pilot_wheel.py`'s
`advance_parked_flight_state` has no timestamp/staleness check of its own — a `None`
sample (nothing received *ever* this session) leaves `state` unchanged, by design, but
there is no path that notices a sample is old. The practical effect: once the overlay
shows any text (which, per the evidence above, includes the very first poll once AI
mode is active, since `apw_goal_progress` defaults to `"idle"`), every later line is
malformed and dropped, so `ParkedFlightState` freezes at whatever was last validly
parsed and never advances again for the rest of that session — not "fields go null",
but "fields go stale and silently stop updating." This matches
`body-layer/CLAUDE.md`'s own description of mode 2's gating: "AI flying means stick
stowed **and** the player in the operator seat" — both `parked_active` and
`player_seat` are carried on this same frozen line, so the gate that decides whether
Petrovich is allowed to drive the AI wheel was itself running on stale data for the
duration of the bug, not just the cosmetic readback (mode/course/alt/speed text) the
flight evidence happened to surface as `null`.

**`#needs-flight`**: this fix needs a live sortie to confirm `GET /ai_pilot_wheel/
latest` now advances continuously (not just once) while the AI pilot wheel overlay is
showing live mode/course/altitude/speed text, and that mode 2's seat/parked gating
tracks a live seat change correctly rather than freezing at its first value.

### Verification

- New test `aircraft-layer/tests/test_ai_pilot_wheel_lua.py::TestPushAiPilotWheelStateJson`
  (4 cases: all-text-nil, one text field set, every text/string field set at once
  matching the live-flight shape, and a field containing quote/backslash characters to
  confirm `json_escape_string`'s own escaping still holds). Extracts the real
  `push_ai_pilot_wheel_state` plus `core.lua`'s `fmt_num_or_null`/`json_escape_string`
  and runs them under `luajit` against a fake `client:send`, then `json.loads`es the
  captured line.
  - Confirmed to **fail** against the pre-fix code (all 4 cases, via a temporary
    `git stash` of just the Lua fix with the test left in place) with exactly the
    `JSONDecodeError` described above.
  - Passes against the fix (4 passed).
- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py` full file: 83 passed.
- `aircraft-layer/tests` full suite: 885 passed.
- `luac5.1 -p aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`: syntax OK.
- GETGLOBAL audit (`luac5.1 -l -p ... | grep -oE 'GETGLOBAL.*; [A-Za-z_]+' | awk
  '{print $NF}' | sort -u`) on the touched file: every name is either Lua stdlib
  (`math`/`string`/`tonumber`/`tostring`/`type`), a genuine DCS API (`GetDevice`/
  `LoGetADIPitchBankYaw`/`LoGetAltitudeAboveGroundLevel`/`LoGetAltitudeAboveSeaLevel`/
  `LoGetCameraPosition`/`LoGetSelfData`), or one of this project's own deliberate
  `core.lua` cross-module globals (`client`, `debug_log`, `extract_json_number_field`,
  `extract_json_string_field`, `fmt_num_or_null`, `json_escape_string`, `safe_call`,
  `WHEEL_CENTER_BUTTON`, `WHEEL_MENU_BUTTON` — each confirmed exported via `_G.<name> =
  <name>` in `core.lua`). No new global leak introduced by the fix.
- `ruff format --check` / `ruff check` (`aircraft-layer/src aircraft-layer/tests`):
  clean (one test-file formatting pass applied before the final check).
- `cd aircraft-layer && .venv/bin/mypy src`: `Success: no issues found in 27 source
  files`.
