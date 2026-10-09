# AC-5 — F10 command inbound channel

- [x] **F10 command inbound channel — done, merged 2026-09-13 (`eacc45c`).** #status/done First Hook→collector
  direction: `petrobrain-f10-commands-hook.lua` registers F10 menu items through
  `net.dostring_in("scripting", ...)` and forwards selections over loopback UDP 7794 to
  `F10CommandReceiver` (three allowed tokens only), served once via `GET /f10_commands/poll`.
  Needs `autoexec.cfg` `net.allow_dostring_in = { "scripting" }`. Wall-clock provenance only.
  See `body-layer/ROADMAP.md` "F10 radio-menu command input" and `plans/f10-crew-commands/`.
