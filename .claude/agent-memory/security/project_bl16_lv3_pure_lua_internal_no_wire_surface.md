---
name: project_bl16_lv3_pure_lua_internal_no_wire_surface
description: BL-16 LV-3 (fix/bl16-flight-epoch-bound, 4ff2e2f7+d25bdc0a) security deep analysis -- APPROVED, no findings; a diff touching only aircraft-layer Lua control-law internals (no src/api, no src/schema, no body-layer) adds no LAN-HTTP attack surface even when it threads new estimator fields through several functions
metadata:
  type: project
---

LV-3 added a real hover/forward blend (`law_lambda`, new `measured.lambda`/`v_g_f`/`v_g_r`
fields, two new intra-process getters `get_lambda`/`get_take_speed_kmh` crossing
`flight_control.lua` -> `flight_desired.lua`) touching a large diff (325+35+71 lines across three
Lua files) that reads, on its face, like exactly the shape this project's recurring
non-finite-at-a-boundary finding targets (new estimator field, a value crossing a module
boundary). It is not: the plan itself states "LV-3 adds no wire field and no body-layer change"
(`plans/flight-lift-vector/plan.md`, LV-3 amendment, Design Overview diagram 1), confirmed by
`git diff --stat` showing zero touched files under `src/api/`, `src/schema/`, or `body-layer/`.
The getters cross a Lua *module* boundary inside one `Export.lua` process (`dofile`-composed,
`AC-B12`), not a LAN-HTTP boundary -- no serialization, no parse step, nothing a LAN actor can
feed. `POST /command/flight`'s field set and every `isinstance`/`isfinite`/bounds check at the
real wire boundary (`src/api/server.py`, `flight_desired.lua`'s `validate_flight_fields`) are
byte-for-byte unchanged from the prior, already-approved batch.

**How to apply:** before scrutinizing a new Lua estimator/getter value for the NaN/Infinity-at-
boundary category, check whether the diff touches `src/api/` or `src/schema/` at all (`git diff
--stat <range> -- aircraft-layer/src`). If it does not, and the plan's own scope section states no
wire field was added, the "crosses into another module" framing in a task brief can be
misleading -- a Lua-internal function call is not a wire boundary, even when it looks exactly like
one on the page (comments explicitly say "crossing into flight_desired.lua"). Still worth tracing
every new numeric path for a non-finite value with a plausible *local* source (ring-buffer
telemetry, sensor glitches) -- `law_lambda`'s own explicit NaN/Infinity guard here was correctly
placed defensive code, just not a security finding under this project's LAN-only threat model
(`.claude/agents/security.md`'s own scope carve-out: local-sensor-glitch-driven uncommanded output
is Reviewer's/player-experience territory, not Security's, unless a LAN-reachable input can cause
it).
