---
name: reference-logetworldobjects-field-list
description: LoGetWorldObjects() returns only Name/Country/Coalition/LatLongAlt{Lat,Long,Alt}/Heading per object -- no Type level1-4 table (that belongs to LoGetPayloadInfo's weapon field) and no launcher/owner link field. Confirmed live on the current Hoggit DCS_export page, 2026-10-29.
metadata:
  type: reference
---

**Confirmed 2026-10-29** by fetching the live `wiki.hoggitworld.com/view/DCS_export` page
directly (not search-summary): `LoGetWorldObjects`'s Object-category worked example iterates
`pairs(o)` and uses exactly `k` (table key / object_id), `Name`, `Country`, `Coalition`,
`LatLongAlt` (`.Lat`/`.Long`/`.Alt` -- the page is internally inconsistent and shows `.x`/`.y` in
one of its two examples, treat the Lat/Long/Alt field names as the documented ones), `Heading`.

This matches what this project's own `aircraft-layer/src/schema/world_objects.py` has always read
(confirmed by reading that file 2026-10-29) and what the 2026-09-07 `petrovich-perception-export.md`
research note already recorded as forum-claim-tier -- this upgrades that specific field list to
documented (direct primary-source page read), though the broader claims on that page (coalition/
visibility scope, static-object behavior) remain unconfirmed by this fetch.

**No `Type`/level1-4 classification table exists on this function** -- that belongs to
`LoGetPayloadInfo`'s `weapon` field (mission's weapon-database classification) and to the
mission-scripting `Unit`/`Weapon` object API, a different function/environment entirely. A future
question that asks about "LoGetWorldObjects's Type table" is conflating the two APIs -- check
which function a Type/level field actually belongs to before assuming either one has it.

**No launcher/owner/parent field exists either.** A newly-launched weapon's world-object cannot be
joined to its launcher via any field `LoGetWorldObjects` returns; identification has to be by
type-match + same-poll timing against a known launch event (button press, loadout count drop),
not by a reference field. [[reference_dcs_export_lua_template_comments]]
