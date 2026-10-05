---
name: los-fixed-literal-command-channel
description: The "fixed string literal" Lua rule forbids composing code from runtime bytes, not commands — and the digit-dispatch trick that passes an arbitrary number without weakening it
metadata:
  type: project
---

**`petrobrain-mission-telemetry-hook.lua`'s rule — the bridge snippet is "a fixed string literal,
baked in at authoring time, never built from network input" — forbids *composing* executable text
from runtime bytes. It does not forbid a runtime value from *selecting among* audited literals.**

**Why:** the repo already ships that exact pattern inside DCS. `Export.lua`'s
`handle_petrovich_search_command` takes a LAN command, rejects anything but `"forward"`/
`"boresight"`, and drives real cockpit switches; `server.py` validates against
`_VALID_SEARCH_MODES` first. `Export.lua` also already **binds a UDP socket and polls
`receivefrom()` non-blockingly every frame**. The user's own framing: a "look in this direction"
directive is the same class of traffic as flipping a switch.

**How to apply:**

- **Three Lua states, and two of the three obvious homes for shared state are impossible.** The
  bridge snippet runs in the **mission-scripting** state (`dostring_in("scripting", …)`);
  `Export.lua` runs in the **Export** state — separate globals, and `land.*`/`world.*` are not
  reachable from Export at all. The collector's Python can only reach scripting through the code
  string. **So pushed state must live as a global in the mission-scripting state**, which
  `petrobrain-f10-commands-hook.lua` already proves persists across `dostring_in` calls
  (`PB_F10_QUEUE`: `REGISTRATION_CODE` creates it, `POLL_CODE` drains it).
- **An arbitrary number crosses via digit dispatch**, not a splice: three hand-authored tables of
  ten one-line literals (`PB_FOV_H = <d>` …), the Hook decomposes a validated integer and executes
  three literals *by index*, the snippet recomposes `100*H + 10*T + U`. Nothing concatenated, the
  executable set fixed at authoring time. The alternative — one validated `string.format("%d", …)`
  — is four lines instead of forty but moves the property from "structurally impossible" to
  "correct because a validator is correct". **Flag that choice to the user; do not take it
  unilaterally.**
- **Prefer an arbitrary value over a named preset at this seam.** User direction, 2026-10-05:
  *"accept arbitrary FOV for the LOS cone, that way future changes, like peripheral vision, can
  easily be taken aboard."* It keeps the optics model on the body-layer side and turns a future
  redesign (attention capture needs a wider cone) into sending a bigger number.
- **A latency-lagged or wrong wedge must cost coverage, never correctness.** The tri-state join
  maps absence to `None` → the existing fallback path. Widen the queried wedge beyond the gaze
  (90° against a 30° focus cone) so command lag is handled by geometry rather than timing.

See [[los-cone-scoping]] for why the cone defines the query set at all.
