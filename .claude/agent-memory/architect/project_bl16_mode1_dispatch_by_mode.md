---
name: project-bl16-mode1-dispatch-by-mode
description: BL-16 mode 1 re-cut (2026-11-18) — one BL-17 rule set dispatched by flight mode; U5 made control persist across park/unpark (Lua armed state, same-frame take, lease); mode-2 one-shot transition fields are NOT cleared while unparked, a latent leak once has_controls widens; confirmed readbacks reuse effector.write's `says`-on-landing contract
metadata:
  type: project
---

**Pattern for adding a second effector behind the BL-17 rule surface:** keep one rule per command
(wording and readbacks stay in `config/rules/*.lua`), and give each action an
`_by_mode(overlay=..., axes=...)` invoke. A single `CrewConsole.flight_mode()` is the one "which
mode" decision. Separate per-mode rules lose, because D9's collision check disables duplicate
wordings.

**Latent leak found by reading, not by narrative:** `body._apply_ai_pilot_wheel_goal` returns early
while unparked, before it clears `crew_console.ai_pilot_goal_transition` and its level-flight and
HVRT siblings. They are cleared only on mission reset. This was harmless while
`CrewState.has_controls == parked_active`, because the gate refused every flight action while
unparked. Once has_controls is true unparked (mode 1), a mode-2 action write would sit there and fire
on the next park.

**Why:** state that persists across a mode change is this project's recurring defect class
([[project_lua_loop_body_limits_split]]).

**How to apply:** whenever a gate's precondition is widened, grep every one-shot field the gated
actions write, and check where it is cleared. Do not assume the gate keeps it dead.

**Readback after a remote confirm:** when a spoken line must state a fact another process confirms
(Lua says "active"), pass the line as a `says` argument that is spoken on landing. This is the
precedent set by `effector.write`'s `says` (speech-rules D20). It keeps wording in the rule file
rather than in a code-side drain.

**U5 answered 2026-11-18 against my recommendation:** the user wanted "Petrovich has the controls"
to persist across park/unpark (mode switch only), which is A8/Decision 17's original spirit that my
re-cut had dropped. Lesson: when a cockpit event switches mechanisms, the user's default is
continuity of *who flies*, not a handback. Consequences worth reusing:

- A handover that must survive a ~1 Hz body-layer poll needs a Lua-side armed state and a
  same-frame take (probe v2 showed the stale/physical input lands at once on unpark).
- A "no watchdog" decision (Decision 2) can silently rely on an escape route (park→unpark). Any
  change that auto-retakes control closes that route; check for it and lease the auto-take.
- Capture source after an AI period is the AI's arg set (pilot 1100–1103), not the player's seat.

**Also:** from 2026-11-18, rule actions *raise* unable instead of returning `{ok=false}`, so rule
handlers carry no `r.ok` checks (`refactor/rule-action-unable-throw`).
