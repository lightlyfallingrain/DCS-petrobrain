---
name: reference-dcs-export-lua-template-comments
description: DCS's own shipped Scripts/Export.lua comment block (reproduced on pastebin.com/Hq6bvJqz, corroborated by GitHub issue Sitsko1/DCSMCPServer#47) is the best primary-source-adjacent reference for LoGetPayloadInfo/LoGetNameByType's return shape -- Hoggit's own DCS_export page lists the function names but not their shapes.
metadata:
  type: reference
---

**Found 2026-10-29, BL-B67 loadout recon.** The Hoggit `DCS_export` wiki page
(`wiki.hoggitworld.com/view/DCS_export`) lists `LoGetPayloadInfo` only under its category
("Ownship") with zero return-shape detail -- it is not a useful source for this function's shape,
despite being the obvious first stop.

**What actually has the shape**: DCS ships `Scripts/Export.lua` with a commented-out reference
block documenting every export function, including this one. That template text, not any wiki
page, is where `LoGetPayloadInfo`'s `{CurrentStation, Stations = {{container, weapon =
{level1..4}, count}}, Cannon = {shells}}` shape and the `LoGetNameByType(level1..4)` lookup
pattern come from. A pastebin copy (`pastebin.com/Hq6bvJqz`, lines ~136-147 usage example,
~552-567 reference block) reproduces this verbatim; `github.com/Sitsko1/DCSMCPServer` issue #47
(a 2026 community project) independently states the same shape and adds `Unit:getAmmo()` as the
mission-scripting-state alternative (per-weapon `count` + `desc`, `desc`'s own fields unverified
live by that project).

**Takeaway for future investigations of any `LoGet*` export function**: if Hoggit's `DCS_export`
page lists the name but not the shape, check whether the function is one of the ones documented
in DCS's own shipped `Export.lua` template comments before concluding it is undocumented --
that template is a primary-source-adjacent reference this project had not previously reached for,
and is worth checking before falling back to forum-claim-tier search-summary evidence. [[reference_logetworldobjects_field_list]]
