---
name: dostring_in-numeric-splice-nan-clamp-gap
description: Lua %d splice into a dostring_in snippet is injection-proof but naive math.min/max clamps pass NaN through unchanged
metadata:
  type: project
---

X-B29 (dcs-driven-los, 2026-10-05) introduced the first `string.format("%d", x)` splice of a runtime
value into a `net.dostring_in` code string in this codebase (prior Hook scripts —
`petrobrain-f10-commands-hook.lua`'s `REGISTRATION_CODE`/`POLL_CODE`,
`petrobrain-mission-telemetry-hook.lua`'s `VELOCITY_CODE` — are all genuinely fixed literals, no
interpolation at all). `Export.lua`'s `handle_petrovich_search_command`, often cited as precedent for
"a validated LAN value already drives real behavior through a closed set," is NOT the same
mechanism: `mode` there only branches between direct `performClickableAction` calls in the Export
state — it never flows into a Lua code string or `dostring_in`. Don't let that precedent be
over-read as "this codebase already splices into dostring_in" — it doesn't, prior to X-B29.

**Core finding, reusable for any future numeric splice into a Lua code string:** `%d` format output
is injection-safe regardless of how extreme the input is — it can only ever emit `-`+digits or raise
an error, never characters that could break out of a fixed template. So the actual risk is never
injection; it's clamp totality. The idiomatic Lua clamp `math.max(MIN, math.min(MAX, x))` **silently
passes NaN through unchanged** (IEEE 754: every comparison against NaN is false), and casting a Lua
NaN to a C int for `%d` is UB (deterministically `INT_MIN` on x86/SSE2 in practice, not a crash, but
a legal-looking garbage integer spliced into the snippet). Correct clamp needs explicit `x ~= x`
(NaN self-inequality) and `x == math.huge` / `x == -math.huge` checks before any min/max comparison.
Also: whether `tonumber("nan")`/`tonumber("inf")` even produces a Lua NaN/Inf from an inbound string
depends on whether the bundled Lua/CRT's `strtod` is C99-conformant (new MSVC UCRT, glibc: yes;
old MSVC CRT: no) — platform-dependent, test directly against the real DCS install rather than
assume either way.

**Why this matters beyond correctness in this project specifically:** X-B29's whole design rests on
a bounded LOS query cone for cost safety; a NaN-defeated clamp producing a garbage FOV could in
principle degrade the wedge toward the full-bubble query the design exists to avoid — mitigated here
only because `MAX_SIGHTLINES_PER_CALL = 128` is an independent hard cap, not because the clamp is
actually total. Don't assume a stated cap elsewhere always backstops a clamp gap — check for one
each time.

See also [[project_spu8_scale_wav_volume_unguarded_frombytes]] for the same class of bug (unguarded
edge case silently corrupting a live path) in a different subproject the same day.
