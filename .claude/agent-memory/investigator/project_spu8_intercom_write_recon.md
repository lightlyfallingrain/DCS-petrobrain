---
name: project_spu8_intercom_write_recon
description: SPU-8 intercom (audio-adapter Slice 2) cockpit-write recon -- command/arg mapping, crew_member_access evidence, and that the DCS install is directly readable from this environment
metadata:
  type: project
---

**2026-10-05 session.** Audio-adapter Slice 2 needs to set arg 664 (SPU-8 intercom power,
`crew_member_access = {1}`, operator panel) from code while the player occupies the pilot seat.

**The DCS install is directly readable from this (WSL) environment at `/mnt/f/Games/DCS World/`
and `/home/sg/winHome/Saved Games/DCS/`** — it is not exclusively reachable only from a separate
Windows machine as several earlier sessions' phrasing implied. Static file/binary reads (grep,
`strings`) work here without any cross-machine hop; only a *live DCS process* (actually flying,
observing `Export.lua` output) needs the Windows box. Check this path before assuming a static
read needs the user to fetch files.

**Command/arg table for SPU_8 (device 55)**, from `clickabledata.lua:999-1050` (DCS 2.9.29.27278):

| Arg | Command | Cmd ID | `crew_member_access` |
|---|---|---|---|
| 456 | `CMD_SPU8_P_ICS_RADIO` | 3004 | absent -> default 0 (pilot) |
| 457 | `CMD_SPU8_P_MAIN_VOLUME` | 3001 | absent -> default 0 (pilot) |
| 376 | `CMD_SPU8_NETWORK_2` | 3018 | absent -> default 0 (pilot) |
| 377 | `CMD_SPU8_NETWORK_1` | 3017 | absent -> default 0 (pilot) |
| **664** | `CMD_SPU8_O_ICS` | **3015** | **`{1}` explicit (operator)** |

Write call: `GetDevice(55):performClickableAction(3015, 1)`. Read: `GetDevice(0):get_argument_value(664)`.

**`crew_member_access` is natively consumed (confirmed: the literal string exists in
`bin/CockpitBase.dll`, absent from the module's own `CockpitMi24.dll`/`Mi24.dll`) — but the
surrounding strings (`is_custom`, `turn_box`, `box_min_max`, `device`, `hint`, `updatable`,
`children`, `clickable_common.lua`) show it belongs to the clickable-element/mouse-pick table
parser, not to the `GetDevice`/`SetCommand`/`performClickableAction` cluster found in the same
binary elsewhere. Inference (not proof): it gates which 3D clickspot responds to a human's mouse
in-cockpit, not whether a device command dispatched by id/value (e.g. from Export.lua) executes.
**No prior or current session has live-tested a write against an explicit
`crew_member_access = {1}` control** — every previously-confirmed write (`Brightness_PM` arg 564,
9K113 AI-axis commands) either defaulted to pilot or had no clickable-element entry at all. This is
the one gap a live probe would close; card at
`docs/acceptance/2026-10-05-spu8-intercom-probe.md`.

See [[reference_mi24p_command_write_mechanism]] for the general (already-settled) write mechanism
this builds on, and `aircraft-layer/research/2026-10-05-spu8-intercom-write-path-recon.md` for the
full write-up.
