---
name: project_apw_status_json_quotes_deep_analysis
description: fix/apw-status-json-quotes (ai_pilot_wheel.lua double-quoting) deep analysis -- APPROVED; the fix makes a dead parsing path live for the first time, which is where the real (low/low) finding was, not the fix itself.
metadata:
  type: project
---

`fix/apw-status-json-quotes` fixed `text_or_null` double-wrapping `json_escape_string`'s
already-quoted output. No code execution, no new file path, no new dependency, no new network
surface -- straightforward correctness fix to a loopback-only ingest path (`Export.lua` -> collector
on `127.0.0.1`), exposed read-only on the LAN API afterward.

**The useful finding wasn't in the diff, it was in what the diff made reachable.** Before this fix,
*every* `push_ai_pilot_wheel_state` line was malformed JSON (the `apw_goal_progress` default,
`"idle"`, is itself a non-nil string), so the entire downstream parse of `apw_mode_text`/
`apw_course_text`/etc. in `aircraft-layer/src/schema/ai_pilot_wheel.py` was dead code on the live
wire. The fix makes it live. That's exactly the "a pre-existing hit is not this feature's finding
unless the feature made it reachable" rule (`AGENTS.md` Mode 2 step 2) -- check what a fix newly
exercises, not just the lines it touches.

**Filed `[[AC-B15]]`**: `core.lua`'s `json_escape_string` only escapes `\`/`"`/`\n`, not the rest of
JSON's required C0 control-character set -- same gap class `BL-B91` already fixed for the
effector-registry TOML renderer (2026-10-23), same severity reasoning applies (text sourced from
DCS's own engine/cockpit readback, not LAN-reachable, implausible but not provably impossible to
carry a raw control byte). Low/low, not blocking.

**Not filed, correctly passed to Reviewer**: `belief/ai_pilot_wheel.py`'s `_parse_float` does
`float(value)` on `apw_course_text`/`apw_alt_text`/`apw_speed_text` -- Python's `float()` accepts
`"nan"`/`"inf"`/`"infinity"` (case-insensitive) without raising, unlike the `int()`-on-NaN pattern
in `project_nan_infinity_int_conversion_at_lan_boundary.md`. Here it's a belief-state correctness
question (a flight-control goal set from a NaN heading/altitude), not a security one -- no crash,
no code exec, no escalation -- and this role's own scope section is explicit that belief/phase
divergence is Reviewer's territory. Realistically unreachable anyway: this field is DCS's own
compass/altitude/speed digit readout, not a string DCS would ever render as literally "nan".

**Confirmed independently** (not just trusted from the commit message): grepped every
`json_escape_string` call site and every hand-built `'"' .. x .. '"'` concatenation across
`aircraft-layer/dcs-export/`. Only the fixed site double-wrapped; `sight.lua`'s `servo_mode` and
`core.lua`'s `export_version` bypass the helper entirely but are fixed internal enums/constants,
never DCS-read text, so no live defect there.

Also confirmed: `ai_mode`/`held_heading`/`held_altitude`/`held_speed` never reach brain-layer or any
`TOOL_SET`/state-param surface -- `grep -rln "apw_\|ai_pilot_wheel\|ParkedFlightState" brain-layer/`
is empty. No LLM prompt-injection path through this feed.
