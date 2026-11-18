## Security Deep Analysis: apw-status-json-quotes

**Branch:** `fix/apw-status-json-quotes`, single commit `c7f2524e` on top of `main` `797f53db`
(verified: `git rev-parse HEAD` matched the expected tip after a clean `git merge --ff-only`; tree
clean before and after).

### Dependency Status

No dependency change. No new package, no new network surface, no new file path.

### What changed

`aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`'s `push_ai_pilot_wheel_state`'s local
`text_or_null` stops wrapping `json_escape_string(value)`'s return value (`core.lua:180-183`,
already a fully-quoted JSON literal, `'"' .. escaped .. '"'`) in a second pair of quotes. Pre-fix
this produced `""FLT""` for every non-nil text field — invalid JSON — which the collector's
`_handle_line` (`aircraft-layer/src/collector/server.py:389`) dropped whole on `JSONDecodeError`,
not just the bad field. A regression test (`aircraft-layer/tests/test_ai_pilot_wheel_lua.py::
TestPushAiPilotWheelStateJson`) extracts the real Lua function under `luajit` and round-trips its
output through `json.loads`; confirmed to fail pre-fix, pass post-fix. Full reproduce → isolate →
fix → verify account: `plans/apw-status-json-quotes/debug.md`.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `ai_pilot_wheel.lua:1375-1379` | removed double-quoting | Correct fix. `json_escape_string`'s own contract (escape `\`/`"`/`\n`, return a quoted literal) is unchanged; only the caller's incorrect re-wrap is removed. Verified by reading `core.lua:180-183` directly, not by trusting the commit message. | None |
| `core.lua:180-182`, `json_escape_string` | escapes `\`, `"`, `\n` only — not the rest of JSON's required C0 control-character set | Pre-existing, but **newly reachable by this fix** (see below) — low/low, not blocking | Filed `[[AC-B15]]`, not blocking |
| `aircraft-layer/src/schema/ai_pilot_wheel.py`, `optional_strings` loop | `isinstance(raw, str)` only, no length bound | No size cap on `apw_mode_text`/etc.; not exploitable in this project's threat model (see below) | Noted, not filed (see reasoning) |
| `belief/ai_pilot_wheel.py:257-263`, `_parse_float` | `float(value)` on `apw_course_text`/`apw_alt_text`/`apw_speed_text` accepts `"nan"`/`"inf"`/`"infinity"` without raising | Correctness/belief-state question, not security (no crash, no code exec) — Reviewer's territory per this role's scope | Passed to Reviewer, no verdict |

### Answering the brief's four questions

**1. Is `json_escape_string`'s escaping complete?** No. JSON requires every codepoint U+0000–U+001F
inside a string literal to be escaped; this function only produces three of the possible escapes
(`\\`, `\"`, `\n`). A raw control byte other than newline (a bare `\t`, `\r`, or anything below
U+0020) would pass through unescaped and produce invalid JSON that Python's `json.loads`
(`strict=True`, the collector's default) rejects with `JSONDecodeError: Invalid control character`
— the same "whole line dropped" failure mode this fix just addressed for a different cause.
**Why this didn't block the fix:** every string this function sees is either a fixed internal enum
(`sight.lua`'s `off`/`caged`/.../`hold`, `ai_pilot_goal.progress`'s `idle`/`pressing`/.../`settled`)
or `list_indication`'s own cockpit-panel readback text — DCS's own engine output, not
externally-attacker-controlled on this project's stated threat model (malicious dependency, LAN
port scanner). Implausible, not provably impossible, so filed rather than ignored: **`[[AC-B15]]`**,
`aircraft-layer/ROADMAP/AC-B15.md` — same gap class and severity reasoning `BL-B91` already used
for the effector-registry TOML renderer's analogous control-character gap (fixed 2026-10-23).

**2. Does anything downstream use these strings unsafely?** No. `ai_pilot_wheel.py`'s schema does
an `isinstance(raw, str)` check and passes the value through verbatim (`str | None`, by design —
the schema's own docstring: "carries the raw overlay text and decides nothing"). Checked every
consumer:
- `belief/ai_pilot_wheel.py`: `ai_mode = sample.get("apw_mode_text")` (stored, no parsing);
  `held_heading`/`held_altitude`/`held_speed` run through `_parse_float`, which catches
  `ValueError` and returns `None` on anything non-numeric — no exception path, no shell/file/eval
  use.
- `belief/crew_console.py`: `ai_mode in ("HVR", "HVRT")` — equality/membership only.
- `body.py`: `held_heading`/`held_altitude`/`held_speed` feed `set_parked_heading`/
  `set_parked_altitude`/`set_parked_speed` (flight-control goal setters) — numeric, no string
  interpolation into any command, file path, or query.
- **No LLM prompt-injection path**: `grep -rln "apw_\|ai_pilot_wheel\|ParkedFlightState"
  brain-layer/` returns nothing. These fields never reach `TOOL_SET`, a state param, or any prompt
  template — they stay inside body-layer's belief/gating logic. Confirmed by reading the grep
  result, not assumed from the absence of a "prompt" keyword near the field name.

**3. Is there a size bound?** No explicit one — `ai_pilot_wheel.py`'s field loop accepts any-length
`str`. Not filed: the sole writer is `Export.lua`'s own `list_indication` readback of a small
cockpit overlay box, over a loopback-only socket (`DEFAULT_HOST = "127.0.0.1"`,
`collector/server.py:192`) — not the LAN-facing surface (`GET /ai_pilot_wheel/latest` is read-only,
no write path accepts attacker-supplied text here). No realistic actor in this project's threat
model can grow this field; `AC-B11` (unbounded `Content-Length` on `TelemetryAPIServer` POST
handlers) already covers the actual LAN-facing unbounded-input risk and is a separate, pre-existing
item, not reopened here.

**4. Is the Debugger's "no other occurrence" claim right?** Confirmed independently, not just
trusted: `grep -rn "json_escape_string" aircraft-layer/dcs-export/` plus a manual check of every
hand-built `'"' .. x .. '"'` concatenation in `Petrobrain/*.lua`. Every other `json_escape_string`
call site (`core.lua`'s `encode_scalar`, `telemetry.lua`'s `name` field, `Export.probe-pb15.lua`'s
own duplicated copy) uses the result directly, no second wrap. The two hand-rolled bypasses
(`sight.lua`'s `servo_mode`, `core.lua`'s `export_version`) are both fixed internal
enums/constants, never DCS-read text — confirmed by reading every assignment site, not inferred.
Claim holds.

### Dependency / supply-chain / LAN-scanner surface

Unchanged by this fix. No new package. The loopback ingest socket and the LAN-facing read-only
`GET /ai_pilot_wheel/latest` endpoint both already existed; this fix only restores the correctness
of what the former sends and the latter was supposed to already be serving.

### Verdict

**APPROVED**

### Required Fixes (if any)

None. `[[AC-B15]]` filed to the aircraft-layer backlog, low/low, explicitly not blocking (same
severity reasoning this project already applied to `BL-B91`'s analogous gap).

### Passed to Reviewer

- `belief/ai_pilot_wheel.py`'s `_parse_float` silently accepts `"nan"`/`"inf"`/`"infinity"` strings
  from `apw_course_text`/`apw_alt_text`/`apw_speed_text` into a flight-control goal target — belief
  correctness, not security; no verdict given here.
