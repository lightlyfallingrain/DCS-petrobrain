---
name: project_f10_radio_menu_command
description: F10 radio-menu registration (missionCommands.addCommand) is not in Export or Hook/GUI state; needs mission-scripting or the untested net.dostring_in bridge.
metadata:
  type: project
---

**Fact:** Neither `Export.lua`'s API surface nor the full official Hook/GUI-state doc
(`Sim_ControlAPI.md`, vendored at `aircraft-layer/research/reference/`) mentions
`missionCommands`/`addCommand` anywhere (grepped both in full, zero hits). Hook/GUI state does
expose two *observation-only* F10-adjacent callbacks — `onShowRadioMenu(a_h)` and
`onRadioCommand(command_message)` — but neither registers a menu item.

**Why:** F10 radio-menu item registration (`missionCommands.addCommand`-family) is, by widespread
DCS community convention (MOOSE/MIST/mission frameworks), a Mission-Scripting-environment API —
called from trigger DO SCRIPT / `.miz`-embedded Lua — not something Export or Hook state can do
natively. This repo has never synced an ED doc that documents `missionCommands`'s home environment
directly (only the Hook/GUI-only `Sim_ControlAPI.md` is vendored); that claim is still
forum-convention-unverified, not doc-confirmed.

**Corroboration found without live DCS access:** this project's own captured file listing
(`world-model/data/raw/dcs/2026-09-02/DCS-saved-games-file-list.txt`) already contains a path hit —
an installed campaign's DCE Dynamic Campaign Engine ships
`.../Mods/tech/DCE/ScriptsMod.NG/Mission Scripts/AddCommandRadioF10.lua`, filed under a
"Mission Scripts" folder (mission/trigger context), not Hooks or Export. Content unread — reading
it next session would very likely upgrade Finding 4 from convention to reproduced-locally with zero
live DCS interaction, since it's a static file already inside Saved Games.

**How to apply:** Before recommending an inbound-DCS-command design (F10 menu, or any other
mission-scripting-only capability), check this file listing for a path hit first — it's a free
`grep` against already-synced data, cheaper than a live probe, and has paid off twice now (this
finding, plus the earlier towns.lua/roadnet discoveries — see [[../MEMORY.md]] world-model entries).
The remaining open question is whether the `net.dostring_in` Hook→Mission bridge (see
`aircraft-layer/research/2026-09-09-dcs-text-panel-output-channel.md`) actually works live once
`autoexec.cfg`'s opt-in is set — still untested as of 2026-09-13, same status as when first flagged
2026-09-09. Full findings: `aircraft-layer/research/2026-09-13-f10-radio-menu-command-input.md`.
