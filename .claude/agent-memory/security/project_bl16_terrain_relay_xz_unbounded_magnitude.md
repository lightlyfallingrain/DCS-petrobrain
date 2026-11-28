---
name: bl16-terrain-relay-xz-unbounded-magnitude
description: BL-16 M3 terrain floor/look-ahead security pass -- APPROVED with two low/low non-blocking findings; the flight_lease "terrain" relay field's h got a magnitude bound in review but x/z did not, and the existing review's "regex can't carry inf/nan" safety argument misses decimal-literal overflow
metadata:
  type: project
---

`plans/flight-lift-vector/security-m3.md` (BL-16 M3, diff `ca0bcb50..0347b8c7`): APPROVED, no
blocking findings, two Low/Low findings written up for the user/orchestrator to file (this
dispatch's own scope said "no roadmap edits," so neither got an `AC-B<n>` minted here).

**The `terrain_points` Hook op itself (the task's named "most important surface") is clean** --
`_safeClampInt` is the *correct, total* NaN/±Inf-guarded clamp (explicit `value ~= value`,
explicit `math.huge`/`-math.huge` checks before any min/max comparison), used for every value
spliced into `SET_TERRAIN_TEMPLATE`'s `2+2*32=66`-`%d`-only template, mechanically asserted by a
test. This is the form [[project_dostring_in_numeric_splice_naN_clamp_gap]] says a naive
`math.max(math.min(...))` is *not* -- this code does it right, matching the already-approved
`probe_points` precedent.

**The real gap is on the opposite-direction channel**: `POST /command/flight_lease`'s own
`terrain` field (`Export.lua`'s answers relayed back down to the law, not a query). It's a plain
string on an *unauthenticated* collector endpoint, validated server-side only by a regex
(`_TERRAIN_RELAY_PATTERN`) and a 4096-char total-length cap, then parsed by `flight_control.lua`'s
`parse_terrain_relay`. The M3 re-review (`review-m3.md`, fix "2b") added a magnitude bound to `h`
(`|h| < 1e5`) after finding it missing, but **never added the equivalent bound to `x`/`z`** --
only a NaN check (`x == x`). The re-review's own stated reasoning for accepting this
("`_TERRAIN_RELAY_PATTERN` cannot carry an 'inf'/'nan' token") is true for a literal token but
does not cover the actual mechanism: a long all-digit string (no "inf"/"nan" substring anywhere)
is valid under that regex and overflows IEEE-754 double parsing in Lua's `tonumber` to
`math.huge` -- a legitimate decimal literal, never an injected token. **Lesson: "the regex can't
carry X token" is not the same claim as "the regex can't produce a non-finite number" -- digit-
string overflow is a third path to non-finite that a token-based safety argument misses
entirely.** Check for this specifically whenever a reviewer's safety argument for an unbounded-
length numeric string rests on "no inf/nan substring" rather than "every number has a magnitude
cap."

**Traced, not just flagged**: `±math.huge` for `x`(or `z`) propagates through
`run_active_frame`'s projection (`d = dx*nose_x + dz*nose_z`) into `law_terrain_w_floor`, which
gates on `type(d)=="number" and d>0.0` -- `+huge` passes and produces `tau = math.huge`, so
`w_i = finite/huge ≈ 0.0` (harmless); `-huge` fails the gate and is skipped. **Not exploitable
today**, but the protection is an *incidental* interaction of two guards written for an unrelated
purpose (the ground-speed NaN gate, the reach gate), not a declared bound -- a future change to
either function (e.g. a direct division by `d`, or dropping the `d>0.0` gate for a "behind
ownship" case) could silently regress this. **How to apply next time a magnitude bound is added
to one field of a multi-field relay string during a fix pass: grep every sibling field in the
same parse function and check whether the same bound needs to travel with it** -- here `h` got
checked, `x`/`z` sitting right next to it in the same `entry:match` line did not, and nothing
caught the asymmetry until this pass.

**Second finding, same root cause (intent vs. check mismatch)**: the relay's point count is
unbounded in practice -- `server.py`'s own comment claims "`_TERRAIN_POINTS_MAX_POINTS` points"
worth of sanity bound, but the actual check (regex + 4096-char length cap) bounds only total
string length, not entry count; `parse_terrain_relay`'s `gmatch("[^;]+")` loop has no truncation
unlike the Hook's own `_applyTerrainPoints`. ~680 points fit instead of the intended 32. Low
impact (no crash, bounded blow-up, no quadratic cost) but the comment's claim is simply false --
worth grepping for "same posture as X points" style comments and verifying the code actually
enforces the count it claims, not just skimming the comment as true.

See also [[project_expected_area_look_probe_points_deep_analysis]] (the pattern for the *request*
direction of this same two-op Hook listener, already correctly bounded both ways) and
[[project_bl16_flight_authority_nan_int_crash]] (the sibling "unguarded non-finite at a LAN-JSON
boundary" category, same batch's earlier instance, already fixed).
