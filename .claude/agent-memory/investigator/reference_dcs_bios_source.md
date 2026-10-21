---
name: reference-dcs-bios-source
description: DCS-BIOS GitHub source (DCS-Skunkworks/dcs-bios) is a reliable, independently-maintained cross-check for Mi-24P arg/device/command numbers and for how DCS-BIOS itself reads cockpit state
metadata:
  type: reference
---

`github.com/DCS-Skunkworks/dcs-bios` (the maintained continuation of the original, now-abandoned
DCS-BIOS) ships `Scripts/DCS-BIOS/lib/modules/aircraft_modules/Mi-24P.lua`, a large, actively
maintained table of every clickable-cockpit control DCS-BIOS's authors have found for the Mi-24P:
identifier, device id, command, arg number, type, and a human description, grouped by panel
category (`WEAP_SYS` = device 6, `I9K113` = device 7, `ASP17` = device 16, etc.).

**Used 2026-10-21** to cross-check seven arg numbers this project had already committed to for
`BL-B66` (773, 885, 886, 955, 956, 673, 874/876) — all seven agreed with DCS-BIOS's independent
survey, none disagreed. Also surfaced two previously-unresolved args (761 `OP_USR_PW`, 762
`OP_USR_CHECK`, both device 16/`ASP17`) and a real disagreement between 762 and the sight's own
905/903 3-position check selector for what a quickstart procedure's "OPER/TEST1/TEST2" step means.
Full finding: `aircraft-layer/research/2026-10-21-dcs-bios-mi24p-9k113-controls.md`.

**Worth reaching for again** whenever an aircraft-layer arg/device/command number for the Mi-24P
needs a second, independent opinion before committing to it, or after a DCS patch that might have
renumbered arguments. Shallow-clone it (`git clone --depth 1`) into a scratch dir and `grep` the
module file — no DCS install needed for this cross-check.

**Limits, so the next investigator doesn't over-trust it:**
- It is a survey of clickable-cockpit elements, not of every draw argument that exists. A gap in
  its coverage (no control defined) is weak evidence something is unmapped/unreadable, never proof.
- It reads every lamp/switch/gauge via exactly `GetDevice(0):get_argument_value(arg_number)` inside
  an export hook — the same mechanism this project already uses. There is no second read technique
  (e.g. `list_indication`) hiding in its source to borrow.
- It has no control for the Mi-24P's player sight-slew axis (device 7, commands 3025/3026) — axis
  `SetCommand`s with no backing clickable element fall outside what its module-authoring process
  would ever surface.
- Licence is GPL-3.0 (confirmed from the repo's own `LICENSE` file and README prose — **the
  README's own license *badge* image reads "MIT", which is wrong/stale; don't trust the badge over
  the file and the prose**). Copying its Lua code verbatim would pull in GPL obligations; citing
  facts (arg numbers) learned by reading it is lower-risk but the line between the two wasn't drawn
  by this investigation — leave that to Architect/the user if a derived table file is ever shipped.
- A `--depth 1` clone only shows the one commit at HEAD for `git log`, even scoped to one file — it
  cannot answer "how recently was `Mi-24P.lua` itself last touched." Needs a full clone for that.
