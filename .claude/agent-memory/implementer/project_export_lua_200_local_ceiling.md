---
name: export-lua-200-local-ceiling
description: aircraft-layer/dcs-export/Export.lua hit Lua 5.1's hard 200-live-local ceiling during BL-16's takeover revision (2026-11-16) -- a real, growing constraint on every future addition to this file, not a one-off.
metadata:
  type: project
---

`aircraft-layer/dcs-export/Export.lua` is one giant Lua 5.1 chunk (no module boundaries), so every
top-level `local` — a variable **or** a `local function` — permanently occupies one of Lua 5.1's
200 live-local-variable slots for the rest of the file, never freed. `luac5.1 -p` fails with "main
function has more than 200 local variables" once the count is exceeded; it gives no line number
pointing at the overflow, only the message.

**Why:** before BL-16's "Revised 2026-11-16" takeover/stabilisation revision, the file already had
193 top-level locals (`grep -cE '^local ' aircraft-layer/dcs-export/Export.lua`). That revision's
dozen-odd new takeover/correction-state fields, declared as individual locals (the file's own
established convention — see the plan's "One naming departure" note), pushed the count to 217.

**How it was resolved, in order of effectiveness:**
1. Grouped the new per-takeover state (12 fields: stage, t, handover_altitude_m, menu_open,
   menu_closed_since_t, awaiting_correction_decision, correction_path, correction_substage,
   correction_phase, correction_hold_cmd, raw_arg852, raw_arg952) into **one** table local
   (`ai_pilot_takeover = { ... }`), initialised with every field up front so there is no forward-
   reference/hoisting risk — the single biggest win (-11 locals for one).
2. Merged near-duplicate press-shape functions that differed only by which fixed command they
   pressed (`ai_pilot_open_hold_up`/`_down` → one `ai_pilot_open_hold(cmd, t)`;
   `ai_pilot_toggle_reference_blind`/`ai_pilot_toggle_menu` → one `ai_pilot_tap30(cmd)`) — safe
   because the restricted caller set (never the forbidden directions) keeps this from becoming the
   project's forbidden generic `press(direction, duration)` combinator.
3. Inlined a function used at only 2 call sites (the quick-path centre pulse) rather than keeping
   it as its own local.
4. Removed genuinely dead code found while touching this area: `LONG_PRESS_HOLD_S` (its one user,
   the old one-shot nudge, was itself removed by this revision) and the unused, reserved-for-later
   `AI_WHEEL_LEFT`/`AI_WHEEL_RIGHT` declarations (P2+ can re-declare them when a stage actually
   needs heading left/right).

Final count: exactly 200 (the passing boundary — the error is "**more than** 200").

**For the next implementer (P2–P6 of this same plan, or any other Export.lua addition):**
- Run `grep -cE '^local ' aircraft-layer/dcs-export/Export.lua` *before* starting — there is no
  slack by default, and the count only grows.
- A `local function` costs a slot exactly like a `local` variable — factoring logic into more
  small functions is not free here, unlike in ordinary code.
- Prefer one state table per feature's own per-instance fields over one local per field, declared
  with every field defaulted at construction (not built up piecemeal) to avoid the forward-
  reference bug the file's existing convention (`push_ptt_state`'s 2026-09-23 incident) is itself
  guarding against.
- `luac5.1 -p` is the only check that catches this — `ruff`/`mypy`/`pytest` never see Lua at all.

See also: [[prune-the-comment-you-are-standing-next-to]] (this same revision's other procedural
lesson), `plans/flight-control/implementation.md`'s "Revision 2026-11-16" section for the full
account.
