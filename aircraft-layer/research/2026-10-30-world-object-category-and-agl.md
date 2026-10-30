# World-object category (ground vs air) and helicopter AGL

**Date:** 2026-10-30
**DCS version:** not verified locally — this session has no DCS access (`$DCS_INSTALL_PATH`/
`$DCS_SAVED_GAMES_PATH` unset on this Mac). Prior reproduced-locally evidence cited below is dated
to the sessions that produced it: `land.getHeight` against `2.9.29.27278`/Syria (`world-model`,
2026-09-03); the conflicting `Type{level1..4}`/`Flags{...}` dump against an unstated version,
2026-09-19 sortie.
**Theatre:** not applicable to this recon (API-shape and classification questions, not
theatre-specific data).

### Question

BL-B104 needs to classify each `LoGetWorldObjects` object as ground (vehicles, infantry,
statics/structures, ships) vs air (aircraft/helicopters/weapons in flight), and for helicopters,
whether they are landed or hovering a few metres up — from unit data, without a new channel if one
already exists. Two research notes on file disagree about whether `LoGetWorldObjects` even carries
a `Type` table at all.

### Findings

1. **The `Type`-table conflict is resolved: `LoGetWorldObjects` does carry `Type{level1..4}` and a
   `Flags` table, per DCS's own shipped `Export.lua` template comments — the Hoggit page the
   2026-10-29 note trusted is incomplete, not authoritative on this point.** — **evidence:
   documented (primary-source-adjacent — DCS's own shipped file text)** — **source:** DCS's
   `Scripts/Export.lua` commented reference block, reproduced verbatim at
   `pastebin.com/raw/Hq6bvJqz` (the same pastebin mirror this project's own
   `.claude/agent-memory/investigator/reference_dcs_export_lua_template_comments.md` already treats
   as the best available primary-source-adjacent text for this file, established 2026-10-29 for
   `LoGetPayloadInfo`). The relevant lines state, verbatim:

   > `LoGetWorldObjects() ... Returned object table structure (see LoGetObjectById())`

   and `LoGetObjectById()`'s own documented structure is:

   ```
   {
     Name = ,
     Type = {level1,level2,level3,level4},  ( see Scripts/database/wsTypes.lua )
     Country = number,  ( see Scripts/database/db_countries.lua )
     Coalition = ,
     CoalitionID = number ( 1 or 2 ),
     LatLongAlt = { Lat = , Long = , Alt = },
     Heading = radians, Pitch = radians, Bank = radians,
     Position = {x,y,z},  -- internal DCS coordinate system
     -- only for units (Planes, Helicopters, Tanks etc)
     UnitName = unit name from mission (UTF8),
     GroupName = unit name from mission (UTF8),
     Flags = {
       RadarActive, Human, Jamming, IRJamming,
       Born, AI_ON, Invisible,
       Static  -- "true if the unit is a static object"
     }
   }
   ```

   and `LoGetSelfData()`'s comment states it "return[s] the same result as `LoGetObjectById` but
   only for your aircraft" — i.e. `LoGetSelfData` and each per-object entry of `LoGetWorldObjects`
   share one documented shape, not two different ones. This directly contradicts the 2026-10-29
   note's "documented, no Type table" conclusion, which rested only on the Hoggit `DCS_export`
   page's one worked *example* (a bandwidth-reduction demo script that happens to read only
   `Name`/`Country`/`Coalition`/`LatLongAlt`/`Heading`) — confirmed by re-fetching that page this
   session: it genuinely lists no return-field spec for `LoGetWorldObjects`, `LoGetObjectById`, or
   `LoGetSelfData` at all, so "no Type table on this page's one example" was overclaimed as "no Type
   table on this function."
2. **The 2026-09-20 note's "reproduced-locally" dump is very likely a mislabeled `LoGetSelfData()`
   capture, not a `LoGetWorldObjects()` one — but this matters less than it looks, because finding
   1 shows the two share the documented shape anyway.** — **evidence: inferred, not confirmed** —
   **source:** `aircraft-layer/dcs-export/Export.lua` (current), which has two separately-labelled
   `debug_dump` call sites — `debug_dump("LoGetSelfData()", self_data)` and
   `debug_dump("LoGetWorldObjects()", world_objects)` — and whose own `encode_world_objects_line`
   function only ever reads `obj.Name`/`obj.Coalition`/`obj.LatLongAlt`/`obj.Heading`/
   `obj.UnitName` per object, never `Type` or `Flags`, from the live `world_objects` table it is
   given. The field list the 2026-09-20 note quotes (`Pitch, Bank, Heading, Type{level1..4},
   Country, CoalitionID, Coalition, GroupName, Name, UnitName, Position{x,y,z},
   PositionAsMatrix{x,y,z,p}, LatLongAlt{...}, Flags{...}`) matches the documented
   `LoGetObjectById`/`LoGetSelfData` shape far more closely than the sparse
   `LoGetWorldObjects`-via-`encode_world_objects_line` shape, and carries fields
   (`PositionAsMatrix`) the template text for `LoGetObjectById` doesn't even mention, suggesting
   the raw dump the note quoted was a different, richer source than either — most plausibly the
   ownship `LoGetSelfData()` debug dump in the same 10.4 MB log, picked up by a grep that didn't
   check which `debug_dump` label preceded it. The original 10.4 MB log is gone (gitignored,
   `aircraft_layer_debug.log`, never committed) so this cannot be re-checked from this machine.
   **Because the documented shape (finding 1) says `LoGetWorldObjects` objects use the same
   structure as `LoGetObjectById`/`LoGetSelfData` anyway, this mislabeling question doesn't change
   the answer Architect needs** — only whether the 2026-09-20 note's specific *evidence grade*
   ("reproduced-locally" for *this* function) should be downgraded to "reproduced-locally, for a
   different function that documentedly shares this one's shape."
3. **`Scripts/Database/wsTypes.lua` was not reachable this session** (no DCS install on this
   machine), but the `level1`/`level2` enumeration is independently corroborated by three unrelated
   community sources, consistent with the user's own guess — **evidence: community (reverse-engineered,
   not ED-authored, but convergent across independent authors)** — **sources:**
   `DCS-OpenSource/dcs-opensource-modding-guide` (`docs/Database/wsTypes.md`, an open community
   modding-guide project), the `Mysteryfx/NH90` mod's bundled SDK header
   (`SDK_Perso/include/worldgeneral/Include/wsType.h`, C constants evidently mirrored from the Lua
   source), and `RevolvingDCON/DCONs-DCS-Waypoint-Computer` (`index.js`, a lookup table). All three
   agree:

   | level1 | name | level | value |
   |---|---|---|---|
   | 1 | `wsType_Air` | — | 1 |
   | 2 | `wsType_Ground` | — | 2 |
   | 3 | `wsType_Navy` | — | 3 |
   | 4 | `wsType_Weapon` | — | 4 |
   | 5 | `wsType_Static` | — | 5 |
   | 6 | `wsType_Destroyed` | — | 6 |

   and, within `wsType_Air`, level2: `wsType_Airplane = 1`, `wsType_Helicopter = 2`,
   `wsType_Free_Fall = 3` (unpowered air objects — bombs/flares in flight, not helicopters).
   The user's own guessed enumeration (Air=1/Ground=2/Navy=3/Weapon=4/Static=5/Destroyed=6;
   Airplane=1/Helicopter=2 within Air) is **confirmed correct** by this cross-source check.
4. **`wsType_Static` (level1=5) is very likely a separate engine-level object class (airdromes,
   explosions, wrecks, game containers — level2 values `Airdrome=13`, `Explosion=14`,
   `GContainer=15`, `AirdromePart=18`, `WingPart=19` per the same modding-guide page), not the same
   thing as the mission-editor "placed as a static unit" flag (`Flags.Static`) — these are two
   different axes and a classification rule must not conflate them.** — **evidence: inferred**
   — **source:** cross-reading finding 3's level2 table against this project's own
   `petrobrain-line-of-sight-hook.lua` header, which documents this project's actual observed static
   population in a real mission as **112 infantry, 31 T-55, 34 T-72B/B3, eight ZSU-23-4 Shilka** —
   ordinary ground vehicles and infantry placed without AI/waypoints, not airdromes or wrecks. If
   `wsType_Static`/level1=5 only covered engine object classes like airdromes and wrecks, those
   mission-editor-placed T-72s and infantry are presumably still `Type.level1 = wsType_Ground (2)`
   with `Flags.Static = true` layered on top — i.e. **a ground-classification rule should test
   `Type.level1 ∈ {wsType_Ground(2), wsType_Navy(3)}`, and separately `Flags.Static` only tells you
   *how* the object was placed, not *what* it is.** This has **not been confirmed against a live
   object** — the LOS hook's statics population has never had its `Type.level1` read (the hook only
   ever reads `getName()`/`getPoint()`), so this is a plausible reading of two independently-sourced
   facts, not a direct observation. A one-shot live check (dump `Type.level1` for one
   mission-editor-placed static T-72 or Shilka) would settle it outright.
5. **Ships should report `Type.level1 = wsType_Navy (3)`, not `wsType_Ground`** — **evidence:
   inferred from finding 3's table** — not independently confirmed live. A classification rule that
   treats "ground" as `level1 == 2` only (and forgets `3`) would silently misclassify every ship —
   worth a specific assertion in whatever test BL-B104's implementation adds, not just an
   eyeballed `if`.
6. **`land.getHeight(vec2)` — the AGL building block — is Mission-Scripting-only, documented, and
   already reproduced-locally by this project (a different module, `world-model`, but the same DCS
   version/engine call)** — **evidence: reproduced-locally** — **source:**
   `world-model/research/2026-09-03-m4-dcs-elevation.md`: "`land.getHeight` works as documented
   against DCS 2.9.29.27278 / Syria, called as `land.getHeight({x=.., y=z})`" — live-confirmed, and
   separately load-tested at 100 calls/trigger with no observed cost problem
   (`world-model/research/2026-09-03-m5-recon.md` finding 12). The `{x=, y=z}` argument convention
   (DCS's internal `y` field carries the world `z`/north-south coordinate for every 2D terrain
   call) is the same one `land.isVisible` already uses inside this project's own
   `petrobrain-line-of-sight-hook.lua`.
7. **The line-of-sight Hook (`petrobrain-line-of-sight-hook.lua`) is the cheapest existing carrier
   for a per-candidate AGL/landed flag, not a new channel** — **evidence: inferred, from reading the
   file directly this session** — it already runs in the Mission Scripting environment
   (`net.dostring_in("scripting", ...)`, the same bridge `2026-09-21-unit-velocity-via-mission-
   scripting.md` established is already in production) at 1 Hz, already resolves each candidate's
   true position (`up.x, up.y, up.z` from `obj:getPoint()`, used today for `buildingClear`/
   `terrainClear`), and already makes two pcall'd engine calls per candidate
   (`world.searchObjects`/`land.isVisible`). A third pcall'd call,
   `land.getHeight({x = up.x, y = up.z})`, subtracted from `up.y`, gives AGL for the same cost class
   already paid per candidate — no new transport, no new wire field category, just one more number
   per entry (today's wire entry is `"<unit_name>:<building_clear01>:<terrain_clear01>"`; an AGL or
   landed-flag field would extend that same `;`-joined line).

   Coverage matches what the naked-eye channel admits, which is the right population for "read only
   at the moment of a percept" (BL-B104 explore-notes Q, answered "ground rule"): the hook's
   candidate set is the look-direction wedge (`PB_LOOK_HOUR`/`PB_LOOK_FOV_DEG`), not the whole 10 km
   bubble — ~10 units/poll in the measured sortie (file header, plan SS8), the same wedge
   `naked_eye_source` already joins against by unit name. A candidate outside the wedge this poll
   gets no verdict at all (today's building/terrain fields, and would be true of an AGL field too)
   — the existing tri-state "not looked at" join already handles that.

   `Unit:inAir()` exists too (documented, DCS FAQ, boolean on `Object`), but it is **not** the
   better carrier for this specific need:
   - It does not exist on `StaticObject` at all (same gap the LOS hook's header already names for
     `getObjectID()` — units and statics share `getPoint()`/`getName()` but not every method), and
     the hook's statics population includes Shilkas/T-72s that would need the same treatment a
     helicopter does if one were ever placed as a static.
   - **Raw `inAir()` is documented (community-sourced, MOOSE library) to return `true` for a
     helicopter sitting on a rooftop/building** — **evidence: community (MOOSE source code, a
     widely-used DCS scripting framework, read directly this session)** — **source:**
     `FlightControl-Master/MOOSE`, `Wrapper/Unit.lua`, `UNIT:InAir(NoHeloCheck)`: it calls DCS's own
     `inAir()` first, and only when the result is `true` **and** the unit is a helicopter does it
     apply an override — "since we might have landed on a building where inAir()=true but actually
     is not" (source comment) — computing speed from the velocity vector and height above *terrain*
     via `land.getHeight`, and forcing `false` when speed < 1 m/s and height ≤ 60 m. This is
     community practice, not an ED statement, but it is exactly the AGL + speed combination BL-B104
     would need anyway, and it independently confirms `land.getHeight` + a velocity read is the
     established pattern for "is this helicopter actually on the ground" — not `inAir()` alone.
   - The unit-velocity bridge (`2026-09-21-unit-velocity-via-mission-scripting.md`,
     `Object.getVelocity()`) is the same Mission Scripting environment the LOS hook already
     bridges into — a speed-from-velocity check could be added at the same call site rather than as
     a separate channel, if the plan wants the MOOSE-style speed+height combination rather than
     height alone. **Whether height-alone (no speed term) is good enough for BL-B104's purposes is
     an open design question for Architect, not something this recon settles** — the alignment
     note's answer to the landed-vs-hovering question was simply "ground rule," without specifying
     the exact test.

### Reproducible Test

No new local probe was run — this question was resolved by reading already-committed source
(`Export.lua`, `petrobrain-line-of-sight-hook.lua`) plus external primary/community sources. A live
check that would close finding 4's remaining gap:

```lua
-- Run via a mission trigger (DO SCRIPT) against a mission containing at least one
-- mission-editor-placed static ground unit (e.g. a static T-72):
local statics = coalition.getStaticObjects(coalition.side.RED)  -- or whichever side
for _, st in ipairs(statics) do
    local id = tostring(st:getID and st:getID() or "?")
    local name = st:getName()
    -- LoGetObjectById-equivalent read, if reachable from this state; otherwise
    -- cross-check against LoGetWorldObjects()'s own per-object Type field from Export.lua.
    env.info("static " .. name .. " id=" .. id)
end
```
Combined with reading the matching object's `Type.level1`/`Flags.Static` from a one-shot
`LoGetWorldObjects()` dump (the same `debug_dump` mechanism `Export.lua` already has, just logging
`obj.Type` and `obj.Flags` for one poll) — this would confirm whether a mission-editor static ground
unit really carries `level1=2`+`Flags.Static=true`, as finding 4 infers, or `level1=5`.

### Possible Approaches

- **Classification**: `Type.level1 ∈ {wsType_Ground(2), wsType_Navy(3)}` → ground (vehicles,
  infantry, ships); `Type.level1 == wsType_Static(5)` → ground structures (airdromes etc, pending
  finding 4's confirmation that mission-placed static *units* don't also land here);
  `Type.level1 == wsType_Air(1)` → air, with `Type.level2` distinguishing `wsType_Helicopter(2)`
  for the landed/hovering question. `Flags.Static` is a placement-method flag, not a category —
  don't use it as the ground/air discriminator.
- **If `Export.lua`'s `encode_world_objects_line` needs extending** to forward `Type.level1`/
  `level2` (it currently reads neither), that's a small, well-scoped addition given finding 1 — the
  documented shape already has the field, this project's own shipped code simply never requested
  it. (Not implemented here — Investigator doesn't write pipeline code.)
- **AGL for helicopters**: extend the already-running LOS hook (finding 7) with one more pcall'd
  `land.getHeight` per candidate rather than opening a new channel; add a speed term from
  `Object.getVelocity()` only if Architect decides height-alone is too easily fooled (e.g. a
  helicopter momentarily at 3 m AGL mid-descent would read "landed" under a height-only rule, same
  false-positive risk the MOOSE library's own comment names as the reason it added the speed term).
- **Fallback if neither channel is wanted**: the existing unit-velocity bridge
  (`Object.getVelocity()`) already proves the Mission Scripting state is reachable and cheap; a
  from-scratch dedicated "helicopter ground-contact" poll could live there instead of inside the LOS
  hook, at the cost of a new channel the LOS hook's existing one avoids.

### Unresolved

- **Whether the 2026-09-20 note's raw dump really was `LoGetSelfData()` mislabeled as
  `LoGetWorldObjects()`** (finding 2) — the original log is gone; only a fresh live one-shot dump on
  Windows, with the `debug_dump` label intact, could confirm it. Low priority given finding 1 makes
  the practical answer the same either way.
- **Whether a mission-editor-placed static *unit* (T-72, infantry, Shilka) reports
  `Type.level1 == 2` (Ground) or `5` (Static)** (finding 4) — needs the live probe sketched above.
  This matters for exactly how a `wsType_Static` branch should be written.
- **The exact field name DCS uses for a helicopter's `Type.level2` value, and whether it is
  genuinely `2` for every Mi-8/Mi-24/UH-60/etc module** — assumed from the cross-corroborated
  community table (finding 3), never read from a live Mi-24P or helicopter AI unit this session.
- **Whether `land.getHeight` + a speed term, or height alone, is the right test for "landed vs.
  hovering a few metres up"** — a design decision for Architect, not a fact this recon can settle;
  finding 7 lays out the tradeoff MOOSE's own library made.
- **Two forum threads 403'd this session** (`forum.dcs.world/topic/291500-...wstype...` and
  `forum.dcs.world/topic/89350-unit-lower-than`) — per project convention, these are not recorded as
  "nothing there," just unread; if more wsType/helicopter-inAir detail is wanted, ask the user to
  open either URL and paste the content back rather than re-attempting the fetch.
