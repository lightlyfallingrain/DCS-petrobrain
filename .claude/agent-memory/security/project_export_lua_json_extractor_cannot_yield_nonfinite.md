---
name: project_export_lua_json_extractor_cannot_yield_nonfinite
description: CORRECTED 2026-10-22 -- the prior claim (digits-only regex is safe) was itself the bug. extract_json_number_field now accepts exponent notation and rejects non-finite results explicitly; a new handler no longer gets this for free by construction of the old regex.
metadata:
  type: project
---

**This memory's original claim was wrong and caused a real bug to ship.** It said
`aircraft-layer/dcs-export/Export.lua`'s `extract_json_number_field` (around line 959) matched
fields with a digits-only pattern that could never produce a non-finite number, so a handler
skipping a NaN/huge re-check was "unreachable redundancy, not a gap." That reasoning missed that the
digits-only pattern does not merely reject non-numeric text -- it **silently truncates** exponent
notation at the `e`, parsing `"1e-05"` as `1` and `"-3.3e-07"` as `-3.3`. Both are ordinary,
in-range-looking numbers, not `nil` and not non-finite, so no caller's `nil`/NaN/huge check ever saw
anything wrong. `aircraft-layer/src/collector/command_sender.py`'s `send_sight_target`/
`send_cockpit_switch` built their datagram with `json.dumps`, which emits exactly that notation for
`|value| < 1e-4` -- a magnitude body-layer float arithmetic near sight centre readily produces. Found
2026-10-22, fixed under BL-B80 (`plans/9k113-sight-pointing/plan.md`,
`plans/9k113-sight-pointing/implementation.md`'s "Exponent-float fix" section).

**The fix, both sides:**

- `command_sender.py` gained `_format_fixed_point`, used by `send_sight_target` and
  `send_cockpit_switch` instead of `json.dumps` for their float fields -- fixed-point decimal only,
  never exponent notation, for exactly the reason above.
- `extract_json_number_field` itself now accepts an optional exponent (`[eE]?[%-%+]?%d*`) **and**
  rejects a non-finite result (`value ~= value or value == math.huge or value == -math.huge`)
  before returning -- moved into the shared extractor rather than left to each caller, so a future
  numeric op built on this function gets the finite guard by construction instead of needing its own
  re-check to be correct. `handle_sight_target_command` additionally clamps to
  `SIGHT_TARGET_CMD_BOUND` (1.5, mirroring `api.server`'s `_SIGHT_TARGET_CMD_BOUND`), since a huge
  but now-finite exponent value (e.g. `"1e10"`) would otherwise pass the extractor's finite check
  and still be a nonsense command.

**How to apply:** when reviewing a new Export.lua inbound op built on `extract_json_number_field`,
the extractor itself now guarantees "absent, non-numeric, or non-finite -> nil" -- a missing
additional NaN/huge re-check in the handler is genuinely redundant now, in a way it was not before
this fix (before, the premise was false and the redundancy claim was unearned). **The lesson that
generalizes:** "this input channel's own parser can't produce X, so a downstream guard against X is
dead code" is a claim about the parser's *full* accepted grammar, not about the subset of inputs
anyone had tried feeding it -- verify by constructing the adversarial input (here: a sender that
actually emits the notation the regex was assumed to never see) rather than reasoning from the
regex's intended character class alone.
