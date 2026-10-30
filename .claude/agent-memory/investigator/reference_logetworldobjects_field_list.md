---
name: reference-logetworldobjects-field-list
description: LoGetWorldObjects() DOES carry Type{level1..4} and Flags{...} per object -- confirmed via DCS's own shipped Export.lua template comments ("Returned object table structure, see LoGetObjectById()"), 2026-10-30. CORRECTS this file's own 2026-10-29 "no Type table" claim, which rested only on one Hoggit worked example, not the function's documented full shape.
metadata:
  type: reference
---

**CORRECTED 2026-10-30 (BL-B104 recon).** This file previously said "no `Type`/level1-4
classification table exists on [`LoGetWorldObjects`]," sourced from the Hoggit `DCS_export` page's
one worked example. That was an overclaim: the page lists no return-field *spec* for
`LoGetWorldObjects`/`LoGetObjectById`/`LoGetSelfData` at all (re-confirmed by re-fetching it this
session) -- its one example merely happens to read a subset of fields (`Name`/`Country`/
`Coalition`/`LatLongAlt`/`Heading`). "No Type table in this one example" was relayed as "no Type
table on this function," the same shape of overreach `2026-09-21-unit-velocity-via-mission-
scripting.md` already warns about for exactly this function.

**The actual documented shape** comes from DCS's own shipped `Scripts/Export.lua` commented
reference block (`pastebin.com/raw/Hq6bvJqz`, [[reference_dcs_export_lua_template_comments]]),
which states verbatim: `LoGetWorldObjects() ... Returned object table structure (see
LoGetObjectById())`, and `LoGetObjectById()`'s structure is `{Name, Type = {level1,level2,level3,
level4} (see Scripts/database/wsTypes.lua), Country, Coalition, CoalitionID, LatLongAlt, Heading,
Pitch, Bank, Position, UnitName, GroupName, Flags = {RadarActive, Human, Jamming, IRJamming, Born,
AI_ON, Invisible, Static}}`. `LoGetSelfData()` is documented as "the same result as
LoGetObjectById but only for your aircraft" -- i.e. one shared shape across all three functions,
not three different ones. **Evidence: documented (primary-source-adjacent).**

**wsType level1 enumeration** (community-corroborated across three independent sources --
`DCS-OpenSource/dcs-opensource-modding-guide`, the `Mysteryfx/NH90` mod's bundled SDK header, and
`RevolvingDCON/DCONs-DCS-Waypoint-Computer`'s lookup table -- not ED-authored, evidence: community):
`wsType_Air=1, wsType_Ground=2, wsType_Navy=3, wsType_Weapon=4, wsType_Static=5,
wsType_Destroyed=6`; within Air, level2 `wsType_Airplane=1, wsType_Helicopter=2,
wsType_Free_Fall=3`. `wsType_Static` is a separate engine object class (airdromes/explosions/
wrecks/containers per its own level2 table), not necessarily the same thing as the
mission-editor-placement `Flags.Static` boolean -- a mission-placed static T-72 or infantry group
plausibly still carries `level1=2` (Ground) with `Flags.Static=true` layered on top. **Not
confirmed live** -- full reasoning and the live-check that would settle it:
`aircraft-layer/research/2026-10-30-world-object-category-and-agl.md`.

**No launcher/owner/parent field exists either.** A newly-launched weapon's world-object cannot be
joined to its launcher via any field `LoGetWorldObjects` returns; identification has to be by
type-match + same-poll timing against a known launch event (button press, loadout count drop),
not by a reference field. [[reference_dcs_export_lua_template_comments]]

**Lesson for next time a Hoggit page looks thin**: a worked *example* on a wiki page documents what
that example happened to read, never the function's full return shape. Check DCS's own shipped
`Export.lua` template comments (reachable via the pastebin mirror, no DCS install needed) before
concluding a field is absent.
