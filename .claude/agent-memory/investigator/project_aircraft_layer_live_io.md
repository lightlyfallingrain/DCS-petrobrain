---
name: project_aircraft_layer_live_io
description: Live-mission DCS I/O findings for the aircraft layer (Export.lua, DCS-BIOS, sensor contacts, LAN transport) — see aircraft-layer/research/2026-09-06-aircraft-layer-live-runtime-io.md
metadata:
  type: project
---

Investigated 2026-09-06 for Architect planning the aircraft layer (post-World-Model-Builder). Full findings + evidence labels in `aircraft-layer/research/2026-09-06-aircraft-layer-live-runtime-io.md` — read that file before re-investigating any of this.

Key verdicts (all desk research, no live probe run yet on Windows box):
- **Export.lua is a separate, unsanitized sandbox from Mission Scripting.** It ships with LuaSocket, `io`, `lfs` all enabled by default — no `MissionScripting.lua` edit needed (that edit, already made for M4, is irrelevant here). Lives at `Saved Games\DCS\Scripts\Export.lua`, runs per-install not per-mission.
- `LoGetSelfData`/`LoGetADIPitchBankYaw`/altitude/airspeed functions give ownship kinematic state, confirmed documented, satisfies pitch/bank/yaw/heading/speed/alt requirement directly. No documented hard sampling-rate cap — throttle via `LuaExportActivityNextEvent`.
- **DCS-BIOS is a *different* mechanism** (cockpit switch/indicator state via clickable-cockpit args, not kinematics) — bidirectional (UDP export + TCP/UDP command channel port 7778/5010). Aircraft layer needs BOTH a custom Export.lua kinematic script AND DCS-BIOS (or equivalent) for switches.
- Mi-24P DCS-BIOS support: exists (GH issue dcs-bios#571 "Mi-24 collective" presupposes the module), but completeness unverified — needs hands-on check of `control-reference.html` or the module's lua file on the Windows box.
- **No genuine sensor-detection-filtered contact API exists.** `LoGetTargetInformation`/TWS functions are FC3-legacy, maintainer explicitly said (GH discussion dcs-bios#1217) "we don't normally export these sorts of things." Confirms PETROBRAIN_SYSTEM.md's anticipated fallback (filter LoGetWorldObjects ground truth by LOS/range heuristic) is the only realistic path — no shortcut exists.
- No confirmed API for direct flight-control-axis (cyclic/collective/pedal) injection — only cockpit-control actuation (DCS-BIOS-style, i.e. "move the switch/lever") is documented anywhere reviewed. Consistent with project's own decision to defer flight-control manipulation.
- DCS-gRPC/Olympus use a **different environment**: Hook scripts (`Scripts/Hooks/*.lua`), more privileged, oriented at mission/GM-level control (spawning, events), not per-cockpit state — a third scripting environment distinct from both Export.lua and Mission Scripting, worth remembering if the project ever needs mission-truth manipulation.
- Tacview's real-time telemetry (Export.lua-based, TCP port 42674) is proof-of-production that "socket server inside Export.lua, LAN client on Mac" works at real-time rates.

Unresolved/needs live check: Mi-24P DCS-BIOS coverage completeness; LoGetWorldObjects anti-cheat/fog-of-war filtering semantics (ED forum thread 133284 blocked WebFetch, ask user to paste); safe max export sampling rate (frame-time cost); whether Export callbacks fire outside active flight (briefing/paused).
