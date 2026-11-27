---
name: device-id-by-analogy-is-unsafe
description: A performClickableAction command id is meaningless without its exact device id -- never assume a control is on the same device as a visually/conceptually related one; it silently no-ops instead of erroring.
metadata:
  type: feedback
---

A 2026-11-27 BL-B67 probe wrote `GetDevice(7):performClickableAction(3038, n*0.1)` to move the
SHSCHO/launch-station knob (arg 963), reasoning "device 7 (`I9K113`) is the device the production
`Export.lua` already uses for this unit." Wrong: the knob is on device 6 (`WEAP_SYS`), not device
7 — confirmed by `aircraft-layer/research/mi24p-command-surface.md`'s per-element device column
and by an earlier (2026-10-17) live probe that moved the same arg correctly on device 6. The write
to device 7 did not error or return `false` — it silently did nothing, same behaviour already
noted for an unrelated inert command in the 2026-10-17 note.

**Why:** every Mi-24P cockpit device's command table restarts its id counter at 3000
(`command_defs.lua`, `start_command = 3000`), so a bare command number like 3038 exists
identically in at least five different device tables. "Same unit, so probably same device" is not
evidence — the device id is the only thing that disambiguates the command, and it must be read
off `mi24p-command-surface.md`'s own generated per-element table (or `clickabledata.lua` directly),
never inferred by family/colloquial grouping.

**How to apply:** before writing or recommending any `GetDevice(X):performClickableAction(cmd,
value)` call, grep the control's own row in `aircraft-layer/research/mi24p-command-surface.md`
(or regenerate it) for its exact device name/id — do not reuse a device id from a *different*
control on the same cockpit panel/system, even one that worked. Full writeup:
`aircraft-layer/research/2026-11-27-bl-b67-shscho-knob-command.md`.
