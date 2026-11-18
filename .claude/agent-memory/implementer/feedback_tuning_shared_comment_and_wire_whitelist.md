---
name: tuning-shared-comment-and-wire-whitelist
description: a #: comment block shared above several tuning.* declarations only renders for the first one; a wire-field bounds dict (body-layer tuning -> api.server -> Export.lua) is a second enumeration that must be updated everywhere a new field is added, or it is silently dropped
type: feedback
---

Two real bugs found by tests during BL-16 mode 1 Stage M2 (`plans/flight-control/plan.md`),
both the kind root `CLAUDE.md`'s "Behaviour-affecting constants are tunable" and "A counterfactual
is evidence only if you ran it" sections warn about generically — this is the concrete case.

**1. One `#:` comment written above a *group* of `tuning.*` declarations only attaches to the
first one in source order.** `tools/generate_defaults.py` associates a comment with the
declaration immediately following it by AST position — it does not know a comment was meant to
cover five sibling constants. Writing `SPEED_BAND_FRAC`/`ALT_BAND_FRAC`/`ALT_BAND_MIN_M`/
`TURN_RATE_BAND_FRAC` under one shared `#:` block rendered a real, correct sentence for
`SPEED_BAND_FRAC` (first in file order) and a blank `# ` for the other three in
`config/defaults.toml`. Caught only by reading the **rendered** file, exactly as the standing rule
says to.

**How to apply:** give every `tuning.*` constant its own `#:` block, even when several constants
share the same rationale — repeat the rationale rather than hoisting it once above the group. A
quick self-check after any multi-constant addition: `grep -A1 "^# " config/defaults.toml` and look
for a bare `# ` line (empty comment) next to any new key.

**2. A tunable sent over an existing wire channel can have more than two enumeration points, and
all of them need the new field or it is silently dropped, not rejected.** BL-16's
`flight_control` channel has the constant declared three times: `body-layer/src/belief/
flight_control.py` (the tuning constant + `flight_control_limits()`'s dict), `aircraft-layer/src/
api/server.py`'s `_FLIGHT_CONTROL_LIMITS_BOUNDS` (a *whitelist* the `POST /command/flight_control`
handler iterates — `for field in BOUNDS: if field not in limits_raw: continue` — so an unlisted
field is silently never copied into the forwarded dict), and `Export.lua`'s own `FC_LIMIT_BOUNDS`/
`fc_limits`. Adding 8 new keys to the first and third without touching the second meant every new
constant reached `Export.lua`'s own validation correctly in isolation, while actually being dropped
one hop earlier — every unit-level test passed, and only an end-to-end test against the real `POST`
endpoint (not just `CommandSender` called directly) caught it.

**How to apply:** when a plan adds fields to an existing body-layer-to-aircraft-layer wire message,
`grep` for the channel's own bounds/whitelist dict **in the middle layer** (`api/server.py`) as a
separate step from checking the two ends — a middle-layer whitelist is easy to miss because it logs
nothing and returns `200` on the silently-dropped path, same shape as the "containing unit" lesson
in `.claude/agents/implementer.md`'s own retro section, just one layer removed from where a review
comment would usually point.
