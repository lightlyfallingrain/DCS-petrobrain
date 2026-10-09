# BL-B7 — F10 radio-menu command input

- [x] **BL-B7 — F10 radio-menu command input for Petrovich — mechanism done, merged 2026-09-13 (merge
  `eacc45c`, `feature/f10-crew-commands`).** #status/done The player's preferred in-cockpit command UI: the
  native DCS F10 radio menu, not keybinds (F-4E-style radial wheel explicitly out of scope). A
  Hook script (`aircraft-layer/dcs-export/petrobrain-f10-commands-hook.lua`) registers
  F10 → Other → Petrovich (Watch Nearest / Scan Forward / Cancel Task) via
  `net.dostring_in("scripting", "missionCommands.addCommand(...)")` at `onSimulationStart`, polls
  selections back at 1 Hz, and forwards them over loopback UDP 7794 to the collector's
  `GET /f10_commands/poll` (drain-once queue); `logger --crew-text --f10-commands` dispatches them
  through `CrewConsole.handle_f10_command` into the same output/overlay path as typed commands.
  Prerequisite: `Saved Games\DCS\Config\autoexec.cfg` with `net.allow_dostring_in = { "scripting" }`
  (minimal set, live-confirmed). Recon: `aircraft-layer/research/2026-09-13-f10-radio-menu-command-input.md`
  Findings 7–11. **Live acceptance (user, 2026-09-13, DCS 2.9.29.27278):** menu appears and all
  three items reach body-layer, including across pause and mission restart. User verdict: "the
  commands themselves need work. But the mechanism is ok." — merged on the mechanism, command
  behaviour split into the follow-ups below. History: `plans/f10-crew-commands/` (plan, review,
  dod-check). Next-milestone impact: none on the BL sequence; it adds a second `CrewConsole` input
  surface that [[BL-10]]'s audio transport can follow.
