---
name: reference-dcs-bios-mi24p-source
description: DCS-BIOS's own Mi-24P.lua module is a reliable, cheap cross-reference for cockpit draw-arg numbers (gauges/lamps/switches) when no DCS install is reachable — clone and grep it before guessing.
metadata:
  type: reference
---

`github.com/DCS-Skunkworks/dcs-bios`, file
`Scripts/DCS-BIOS/lib/modules/aircraft_modules/Mi-24P.lua` — a third-party, actively-maintained
module that exhaustively maps the Mi-24P's clickable cockpit controls and gauges to draw-argument
numbers. Confirmed valuable twice now:

- 2026-10-21 (`aircraft-layer/research/2026-10-21-dcs-bios-mi24p-9k113-controls.md`): cross-checked
  seven already-committed arg numbers (773, 885, 886, 955, 956, 673, 874/876) — all agreed, zero
  disagreements.
- 2026-11-19 (`aircraft-layer/research/2026-11-19-mi24p-readable-args-recon.md`, `[[BL-B132]]`):
  found pilot/operator rotor-RPM args (42/845) and engine-RPM args (40/41, 838/839) that no
  existing project research file had — this project's own corpus is almost entirely 9K113/sight-
  focused and had never looked at engine/rotor instruments. Two of the names it gave (rotor brake
  745, rotor-RPM circuit breaker 606) independently cross-checked clean against this project's own
  `mi24p-command-surface.md`.
- 2026-11-20 (`aircraft-layer/research/2026-11-20-slip-ball-recon.md`, BL-16 mode 1 pedal law):
  found the pilot/operator ADI slip-ball draw args (943/784, category `"PKP72M Gauges"`) that no
  official DCS source or forum thread named anywhere — again a gap this project's own corpus had
  (the `clickabledata.lua`-driven generator skips pure-gauge elements with no click action, so the
  ball was never going to appear in `mi24p-command-surface.md` on its own). Device family
  (`PKP72M_P`/`PKP72M_O`, ids 32/33) cross-checked clean against that file. Third confirmation —
  reach for this file before guessing or declaring a gauge's arg "undocumented."

**How to use it:** `git clone --depth 1 https://github.com/DCS-Skunkworks/dcs-bios.git <scratch>`,
then grep the one file above. Works from a Mac dev session with no DCS install at all — this is
its main value, since it substitutes (partially) for a local `mainpanel_init.lua`/
`clickabledata.lua` read when neither is reachable.

**Known gap, not a universal substitute:** it does not map every readable state — it found no
sight-readiness (`READNS.`) lamp either, confirming that absence is a real gap in the module's
*clickable* data, not just DCS-BIOS not getting to it. And its `defineFloat` ranges are the raw
gauge-declared input range (often `{0,1}`), never the physical-unit calibration — that still needs
a local `mainpanel_init.lua` `CreateGauge` read.

**Licence: GPL-3.0** (`feedback`-worthy for whoever builds a shipped table from it — see the 2026-
10-21 note's "Licence" section). Citing an arg-number *fact* learned from it is lower-risk than
reproducing its tables verbatim as a derived shipped file; that line is Architect's/the user's to
draw, not this role's.

See also [[reference_dcs_bios_general]] if written later for non-Mi-24P modules.
