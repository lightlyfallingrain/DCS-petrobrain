---
name: bl6-command-feasibility
description: BL-6 recon — whether Petrovich's scan behavior can be commanded externally
metadata:
  type: project
---

2026-09-10, no live DCS access this session (desk research + install file-listing grep only).
Full findings: `aircraft-layer/research/2026-09-10-bl6-petrovich-command-feasibility.md`.

Two real, previously-unnoticed command surfaces found by path (contents unread — not synced,
worth pulling next session): `Mods/aircraft/Mi-24P/Cockpit/Scripts/HelperAI/AI_Wheel/*` (a radial
command-wheel UI namespaced under `Petrovich`, texture at `IndicationTextures/Petrovich/AI_Wheel.dds`)
and the older `Cockpit/Scripts/AI/ControlPanel/g_panel*.lua` + `AI/AI_Gunners.lua`/`AI_Side_Gunner.lua`
— relationship between the two unresolved. A dedicated input-binding profile
`Mods/aircraft/Mi-24P/Input/Mi_24P_AI_Menu/{keyboard,joystick,mouse}/default.lua` almost certainly
drives the wheel. `Export.LoSetCommand(commandID[, value])` is a real, historically-documented
numeric command-injection API directly callable from Export.lua's own state (not just Hook/GUI) —
but a live ED forum thread title itself questions whether it's deprecated for modern/full-fidelity
modules (topic/338836, unread — 403'd). Concrete next probe: pull `AI_Wheel_page_common.lua` +
`g_panel_definitions.lua` + `command_defs.lua`/`clickabledata.lua` + the two input-profile
`default.lua` files, then live-test `LoSetCommand` against whatever iCommand IDs those reveal.

Outcome-verification candidates: `HelperAI_sound.lua` event names `observ_on`/`target_acq`/
`still_searching`/`sight_blocked` are the right shape for "still scanning vs done" but NOT
confirmed externally observable (audio-only trigger, no confirmed Lua-readable mirror).
`list_indication(6)` target list is weapon-selection/attack-mode-gated per prior session
(forum snippet, topic/388039), not an ambient scan-state flag — don't assume it populates just
because a scan command fired.
