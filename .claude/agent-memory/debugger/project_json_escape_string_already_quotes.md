---
name: json-escape-string-already-quotes
description: aircraft-layer's json_escape_string (core.lua) returns a quoted literal, not a bare escaped body -- a caller that wraps its result in another pair of quotes produces invalid JSON silently dropped by the collector
metadata:
  type: project
---

`aircraft-layer/dcs-export/Petrobrain/core.lua`'s `json_escape_string(s)` returns
`'"' .. escaped .. '"'` -- the **full quoted JSON string literal**, not just the
escaped inner body. Every correct caller (`encode_scalar`'s string branch,
`telemetry.lua`'s `name` field) uses its return value directly as the field's
JSON value with no extra wrapping.

`ai_pilot_wheel.lua`'s `push_ai_pilot_wheel_state`'s local `text_or_null`
(found 2026-11-18, `plans/apw-status-json-quotes/debug.md`) did
`'"' .. json_escape_string(value) .. '"'` -- a second pair of quotes around an
already-quoted value, producing `""FLT""` for every non-nil text field. This
is valid Lua, valid-looking JSON-ish text, `luac -p` and the GETGLOBAL audit
both pass it clean -- it only breaks at `json.loads` in
`aircraft-layer/src/collector/server.py`'s `_handle_line`, which then drops
the **whole line**, not just the bad field: every other key on that status
line (`apw_parked_active`, `apw_seat`, ...) silently freezes at its last
successfully-parsed value for as long as any string field stays non-nil --
which, for an overlay status line, is "most of the time it is interesting."

**When touching a hand-rolled JSON encoder in this codebase, check whether
the per-field helper already returns the quoted literal or just the escaped
inner body before wrapping its result in `'"' .. ... .. '"'`.** The project
has two sibling helpers with different contracts that look interchangeable:
`json_escape_string` (returns `"quoted"`) and the escaped-body-only pattern
a careless caller might assume. Grep every caller of `json_escape_string`
(and any locally-duplicated copy, e.g. `Export.probe-pb15.lua`'s own) for a
surrounding `'"' .. ... .. '"'` whenever one of them changes -- that is
exactly the shape this bug took, and nothing short of running the line
through a real JSON parser catches it (not `luac -p`, not the GETGLOBAL
audit, not a human read of the escaping logic itself, which is correct in
isolation).
