# AC-6 — Unit-velocity channel

- [x] **Unit-velocity channel — implemented 2026-09-22, ACCEPTED live 2026-09-23** #status/done on the five-fix sortie (`docs/acceptance/2026-09-22-five-fixes-sortie.md`): movement callouts were produced in flight, which exercises the whole transport end to end. Originally:
  (`plans/movement-detection/plan.md` Stage 1). Second Hook→collector direction, alongside the F10
  channel above: `petrobrain-mission-telemetry-hook.lua` polls `Object.getVelocity()` for every unit
  and static object at 1 Hz via `net.dostring_in("scripting", ...)` (the same bridge the F10 hook
  already proved live), stamping sim time **inside the scripting state** via `timer.getTime()`
  (never `DCS.getRealTime()` — the replay-determinism risk the plan flags as sharpest), and forwards
  one JSON datagram per poll over loopback UDP 7795 to `UnitVelocityReceiver`, served via
  `GET /unit_velocity/latest`. `Export.lua` gains `unit_name` (`LoGetWorldObjects`'s `UnitName`) on
  every world-object entry — the join key body-layer's `perception.motion` uses to pair a candidate
  with its velocity sample; wire-format version bumped (`EXPORT_SCRIPT_VERSION`/
  `EXPECTED_EXPORT_VERSION` → `2026-09-22b`) accordingly. Needs the same `autoexec.cfg`
  `net.allow_dostring_in = { "scripting" }` opt-in as the F10 channel. Self-measures its own cost
  (`unit_count`/`bridge_call_ms`, logged to `dcs.log` every poll) since the in-state `O(N)`
  `getVelocity()` loop's per-call cost cannot be measured off a live DCS session.
