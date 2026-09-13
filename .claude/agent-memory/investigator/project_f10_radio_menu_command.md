---
name: project_f10_radio_menu_command
description: Hook→mission-scripting bridge is live-confirmed — net.dostring_in("scripting", ...) registers F10 items and polls selections back, given the autoexec.cfg opt-in.
metadata:
  type: project
---

**Fact (live-confirmed 2026-09-13, DCS 2.9.29.27278):** `missionCommands` exists only in the
mission scripting state. Hooks can't see it, `RadioCommandDialogsPanel` (globalL) or `a_do_script`.
Without `Config/autoexec.cfg`, `net.dostring_in` is visible in Hooks but returns
`("Invalid state name", false)`. With `net.allow_unsafe_api`/`net.allow_dostring_in` set,
`net.dostring_in("scripting", "missionCommands.addCommand(...)")` from `onSimulationStart` adds
F10 → Other entries. Their callbacks run in the scripting state, and a Hook poll through the same
bridge reads selections back within one poll interval. `"server"` is the same Lua state as
`"scripting"`. `"mission"` (trigger state) only has `a_do_script`: it returned `""`, didn't reach
the scripting state, and went invalid on a second mission. Don't use it.

**Why:** closes the open question flagged 2026-09-09 (text-panel note) and 2026-09-13 (F10 note):
the bridge works, but only behind the user-machine opt-in.

**How to apply:** For any Hook→mission-scripting need (F10 input, outText, trigger flags), use
`"scripting"` via `dostring_in`, not `a_do_script`. Poll only between `onSimulationStart` and
`onSimulationStop`, because `onSimulationFrame` also fires between missions. Still open: the
minimal opt-in set (run 2 enabled all six state names plus `"gui"`), multiplayer group scoping,
and `onRadioCommand` for built-in commands (it doesn't fire for mission-registered items; moot for this route). A static-read trap: `getDataParameter` in
`RadioCommandDialogsPanel.lua` looked promising but is unreachable from Hooks. Check the Lua state
before designing around a GUI module. Full findings:
`aircraft-layer/research/2026-09-13-f10-radio-menu-command-input.md` Findings 7–11.
