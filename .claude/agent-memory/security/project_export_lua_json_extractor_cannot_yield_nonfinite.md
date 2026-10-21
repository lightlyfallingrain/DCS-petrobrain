---
name: project_export_lua_json_extractor_cannot_yield_nonfinite
description: Export.lua's extract_json_number_field regex is digits-only, so it can never produce NaN/Infinity -- a new inbound op's handler skipping the belt-and-suspenders NaN/huge re-check (that cockpit_switch's handler has) is not a gap, it is unreachable redundancy
metadata:
  type: project
---

`aircraft-layer/dcs-export/Export.lua`'s `extract_json_number_field` (around line 959) matches
fields with `"field"%s*:%s*(-?%d+%.?%d*)` -- plain decimal digits only, no exponent notation, no
`NaN`/`Infinity` literals. Any JSON datagram whose field is non-numeric or holds `NaN`/`Infinity`
text simply fails to match and the field extracts as `nil`, which every handler on this file
already treats as "ignore this command."

`handle_cockpit_switch_command` additionally re-checks `value ~= value` (NaN) and
`value == math.huge`/`-math.huge` after extraction -- defensive redundancy, since the extractor
cannot hand it a non-finite number in the first place. BL-B80's `handle_sight_target_command`
(2026-10-22) omits that re-check and only guards `nil`. This is not a vulnerability: checked during
BL-B80's deep security analysis (`plans/9k113-sight-pointing/security-review.md`) and found
provably unreachable via this channel.

**How to apply:** when reviewing a new Export.lua inbound op built on `extract_json_number_field`,
do not treat a missing NaN/Inf re-check as a finding by itself -- check whether the extractor can
even produce one (it cannot, by construction of the regex). A finding would be a *different*
extraction path (e.g. one that parses exponent notation or trusts a raw Lua `tonumber` on
attacker-controlled text without the digits-only regex gate first).
