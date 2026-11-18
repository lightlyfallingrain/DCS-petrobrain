# AC-B15 — `json_escape_string` escapes only `\`/`"`/`\n`, not the rest of JSON's required control-character set

- [x] **AC-B15 — Escape every C0 control character (or reject the field) in `core.lua`'s `json_escape_string`, not just backslash/quote/newline — REJECTED 2026-11-18 (user), not fixed.** #status/done User: *"reject AC-B15, extremely unlikely to happen"*.

`aircraft-layer/dcs-export/Petrobrain/core.lua:180-183`:

```lua
local function json_escape_string(s)
    local escaped = tostring(s):gsub("\\", "\\\\"):gsub("\"", "\\\""):gsub("\n", "\\n")
    return "\"" .. escaped .. "\""
end
```

The JSON grammar requires every codepoint U+0000–U+001F inside a string literal to be escaped
(either a short escape — `\b \t \n \f \r` — or `\uXXXX`); this function only ever produces three of
them. Any other raw control byte (a bare `\t`, `\r`, or anything below U+0020) that reaches this
function passes straight into the quoted literal unescaped. Python's `json.loads` (`strict=True`,
the collector's default) raises `JSONDecodeError: Invalid control character` on such a literal, so
the whole line is dropped by `aircraft-layer/src/collector/server.py`'s `_handle_line` — the same
"invalid JSON drops the whole line" failure mode `fix/apw-status-json-quotes` just fixed for the
double-quoting case, reachable here from a different cause.

**Found during the Mode 2 deep analysis of `fix/apw-status-json-quotes`** (`plans/
apw-status-json-quotes/security.md`): that fix made `push_ai_pilot_wheel_state`'s JSON valid again,
which means its `apw_mode_text`/`apw_course_text`/`apw_alt_text`/`apw_alt_add_text`/
`apw_speed_text`/`apw_last_press` fields — `Export.lua`'s own flattened `list_indication
(HELPERAI_DEVICE_ID)` readback, passed through verbatim per `aircraft-layer/src/schema/
ai_pilot_wheel.py`'s own docstring — are live on the wire for the first time in practice (every
previous line was malformed from the `apw_goal_progress` default alone, so this parsing path was
effectively dead code until the fix). Also reachable through `telemetry.lua`'s `name` field and
`Export.probe-pb15.lua`'s own duplicated copy of the same function.

**Probability:** low — every field through this function is either a fixed internal enum (`off`/
`caged`/.../`hold` in `sight.lua`, `idle`/`pressing`/.../`settled` in `ai_pilot_goal`) or DCS's own
cockpit-panel readback text (`list_indication`), not externally-attacker-controlled input on this
project's stated threat model (malicious dependency code, a LAN port scanner). A raw control
character other than `\n` in a cockpit indicator string is implausible but not provably impossible
— this function has no way to know which caller it is protecting.

**Impact:** low — the existing failure mode (the collector drops the one malformed line, logs it,
and keeps running; confirmed by this project's own fix for the double-quoting case) is unchanged in
kind, just reachable from one more cause. No crash, no code execution, no new trust boundary.

**Recommended fix:** extend `json_escape_string` to `\uXXXX`-escape every codepoint below U+0020
(or DEL, matching `BL-B91`'s precedent for the same control-character-escaping gap in the
effector-registry TOML renderer, fixed 2026-10-23) rather than guessing at a closed set — fail
closed the same way, not silently truncate or strip.

Not blocking `fix/apw-status-json-quotes`'s merge — low/low on this project's stated threat model,
and the failure mode this gap can cause (one dropped line) already exists and is already accepted
for the unrelated non-JSON-line case. Filed so it is schedulable rather than sitting in a security
report's prose (this role's own closing-step rule); same severity reasoning `BL-B91` already used
for the analogous TOML gap.
