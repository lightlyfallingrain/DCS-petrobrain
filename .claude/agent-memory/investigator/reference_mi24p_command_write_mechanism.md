---
name: reference_mi24p_command_write_mechanism
description: Confirmed-live mechanism for writing/reading Mi-24P cockpit switches from Export.lua -- GetDevice/performClickableAction/SetCommand/get_argument_value, and command_defs.lua/clickabledata.lua as the canonical arg/command source
metadata:
  type: reference
---

**Settled 2026-09-11, still true 2026-10-05 — don't re-investigate "can we write a cockpit
switch from code" from scratch.** Full detail: `aircraft-layer/research/
2026-09-11-command-injection-surface.md` and its durable reference `aircraft-layer/research/
mi24p-command-surface.md`.

- **Write:** `GetDevice(<device_id>):performClickableAction(<cmd_id>, <value>)` for clickable
  switches, or `:SetCommand(<cmd_id>, <value>)` for axes with no clickable element (e.g. the 9K113
  sight slew). Both confirmed callable and effective from the **`Export.lua`** Lua state, live,
  2026-09-11. Production `aircraft-layer/dcs-export/Export.lua` already uses this
  (`GetDevice(30):performClickableAction(...)` for the AI-wheel trigger, BL-6) — this is shipping,
  not just probed.
- **Read:** `GetDevice(0):get_argument_value(<arg>)` — **device 0 (mainpanel) only**, never the
  device being written. Confirmed live.
- **Source of truth for IDs:** `Mods/aircraft/Mi-24P/Cockpit/Scripts/{devices.lua,command_defs.lua,
  clickabledata.lua}`, all plaintext, directly readable (see [[project_spu8_intercom_write_recon]]
  for this session's note that the install is reachable from this environment, not Windows-only).
  **IDs are positional** (`counter()` in `command_defs.lua`) — re-derive after any DCS patch, never
  hardcode without checking the installed build.
- **Known generator gap:** the hand-rolled `mi24p-command-surface.md` enumeration misses 13 of 749
  `clickabledata.lua` elements that use raw table-literal form instead of the `default_*(...)`
  helpers — both PTT triggers (arg 738/856) and both collectives are in that missed set. Grep
  `clickabledata.lua` directly for anything not found in the generated reference before concluding
  an arg doesn't exist.
- **Still genuinely open, not settled by the above:** whether a write to a `crew_member_access = 1`
  (operator-only) control succeeds when the player occupies a different seat. See
  [[project_spu8_intercom_write_recon]] — this is a real, narrow, un-live-tested gap, not folklore.
