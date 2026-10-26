# `LoGetWorldObjects()` object-id (`pairs()` key) stability across polls

> **Rescued onto `main` 2026-10-26** from the unmerged `feature/omniscient-mission-memory` branch
> (deleted). Its "Unresolved" Tacview gap is closed by
> `2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md`, which cites this note as
> its base evidence. Relevant again for `[[BL-B67]]` impact detection (the launched missile's own id).

**Date:** 2026-09-09
**DCS version:** not verified locally — see below (desk research only, no live DCS access this session)
**Theatre:** n/a

### Question
Aircraft-layer's `WorldObjectsSnapshot`/`WorldObjectSample` (`aircraft-layer/src/schema/world_objects.py`)
carries `object_id: int`, taken as the numeric Lua `pairs()` key over `LoGetWorldObjects()`'s
returned table. That module's own docstring flags this as unconfirmed. A deferred milestone
(persistent diffed omniscient world-object store, upstream of body-layer perception) depends
entirely on this key being a stable per-physical-object identity across consecutive polls —
if it's actually a pairs()-iteration-order artifact, "diff instead of re-filter every poll"
doesn't work at all.

### Findings

- **The returned table's index is documented, by the original ED export-API reference text
  itself, as "object identificator," not an arbitrary Lua iteration position** — the exact
  API doc comment (found embedded verbatim in a community export script,
  `github.com/sprhawk/dcs_scripts` `Export.lua`) reads: *"LoGetWorldObjects() ... Returned
  table index = object identificator. Returned object table structure (see
  LoGetObjectById())."* — **evidence: documented** (this is ED's own original API reference
  text, reproduced verbatim across many community export scripts; not this session's own
  primary-source read of Hoggit, but a primary artifact quoting ED's canonical doc, source:
  `raw.githubusercontent.com/sprhawk/dcs_scripts/master/Export.lua`). This directly refutes
  the "may just be a `pairs()` iteration-order key" framing in the schema docstring: the key
  is semantically defined by the API as an object identifier, not an incidental table-iteration
  side effect. `LoGetObjectById(id)` is explicitly the sibling function meant to fetch that
  same object again by that same id — a function whose entire purpose (fetch again, later) is
  meaningless unless the id it takes remains valid to reference the object at a later call.
- **`Unit.getObjectID()` returns what Hoggit's wiki describes as "the runtime object Id
  associated with the unit… every single object on the map is represented by a unique
  objectID value"** — **evidence: documented**, source: `wiki.hoggitworld.com/view/DCS_func_getObjectID`.
  The word "runtime" is doing real work here (see Possible Approaches/caveat below): it reads
  as an id assigned for the object's current lifetime, not a mission-authoring-time id baked
  into the .miz.
- **`Group/Unit/StaticObject/Airbase.getID()`** is a *different, separate* id — "the unique
  mission id of a given object," documented since DCS 1.2.0 — **evidence: documented**, source:
  `wiki.hoggitworld.com/view/DCS_func_getID`. This is very likely the mission-editor-assigned
  id baked into the `.miz`'s trigger/group tables (stable across respawns of the *same
  scripted unit slot*), distinct from the export-side runtime object id `LoGetWorldObjects`
  hands back. No source found directly confirming these two ids are related/derivable from
  each other, or that `LoGetWorldObjects`'s key equals either one exactly (see Unresolved).
- **A mature, widely-deployed DCS mission-scripting framework (MIST, `ciribob/DCS-CTLD`'s
  `mist.lua`) treats the engine's own object/unit id as untrustworthy for persistent identity
  across a unit's death/respawn/regeneration, and works around it** — **evidence:
  reproduced-locally (read the actual file), moderate-strength inference**. Specifically:
  MIST keeps parallel `unitsByName` and `unitsById` tables but prefers name-based lookup, has
  an explicit dead-object id-collision fallback (`while mist.DBs.deadObjects[id] do id =
  tostring(original_id) .. ' #' .. tostring(id_ind) end`), and for units it spawns itself
  allocates its *own* sequential id (`mistUnitId = mistUnitId + 1`) rather than trusting
  whatever id the engine assigns. This is strong indirect (not direct-quote) evidence for the
  community consensus: **within one continuous object lifetime (no death/despawn/respawn) the
  engine id is a real, stable identifier; across a death→respawn/regenerate boundary, expect a
  new id for what a human would call "the same" unit/group slot.** This matches how DCS group
  regeneration is generally understood to work (a fresh unit instance is spawned, not the old
  one revived) — but this specific claim is not from a primary ED source, so treat the
  "survives death" half of the sentence as **forum-claim/community-convention, not documented**.
- **Direct primary Hoggit page for `LoGetWorldObjects()` itself 404s under every guessed URL
  slug** (`DCS_func_getWorldObjects`, `DCS_func_LoGetWorldObjects`) — repeated across two
  sessions now (this one and `2026-09-07-petrovich-perception-export.md` finding 10). The
  field-level detail available (id/Name/Country/Coalition/LatLongAlt/Heading) is
  search-summary/community-script-sourced, not a primary Hoggit page read, and remains at
  that same moderate-confidence level from the prior session — this investigation did not
  upgrade it further.
- **Tacview's actual DCS export script (`TacviewExportDCS.lua`) could not be fetched this
  session** — `lomac.strasoftware.com` connection refused via `WebFetch`, and this session's
  sandbox denied a direct `curl` to that host. Tacview is known to do frame-to-frame object
  tracking against DCS (it draws continuous per-object tracks, which requires *some* persistent
  key), but its actual ID-handling code remains **unread this session** — the one source most
  likely to give a direct empirical answer is the one I could not reach. Ask the user to fetch
  `http://lomac.strasoftware.com/download/misc/DCS/TacviewExportDCS.lua` manually if this
  matters enough to close the gap without a live DCS probe.
- ED forum threads most likely to bear on this directly (`forum.dcs.world/topic/133284-logetworldobjects`,
  `forum.dcs.world/topic/302542-...`, `forum.dcs.world/topic/348227-getting-the-object-from-its-id`)
  all 403'd on `WebFetch` this session, consistent with prior sessions' finding that
  `forum.dcs.world` blocks automated fetch — **not recorded as an unread gap in the "give up"
  sense; flagged for the user to paste manually if wanted** (per project convention, see
  `aircraft-layer/research/... forum-dcs-world-fetch` memory).

### Reproducible Test
No live probe was run this session (no DCS access). The concrete test, reusing the existing
`Export.probe-pb15.lua` disposable-spike pattern (`aircraft-layer/dcs-export/Export.probe-pb15.lua`):

1. Deploy a variant of `Export.lua` that on each `LuaExportAfterNextFrame` call runs
   `for k, v in pairs(LoGetWorldObjects()) do debug_log(k .. " " .. tostring(v.Name) .. " " ..
   tostring(v.LatLongAlt.Lat) .. "," .. tostring(v.LatLongAlt.Long)) end` into the same
   flag-gated `aircraft_layer_debug.log` mechanism already built into the production script.
2. Fly/observe a mission with a handful of stationary or slow-moving AI ground units (no
   combat, no deaths) for at least 30–60 seconds of continuous polling at the existing 5 Hz
   rate.
3. Confirm: (a) the same physical unit (same `Name`, same lat/lon trajectory) reports the same
   numeric `k` on every poll across that window — settles the base stability question; (b) kill
   one unit (e.g. via a trigger or by shooting it) and confirm whether the *same* group's
   AI-regenerated replacement (if the mission uses group respawn/regeneration) reports a new
   `k` — settles the death/respawn boundary question, currently only community-convention-level
   evidence.
4. Optionally cross-check against `Unit.getID()`/`Unit.getObjectID()` from a parallel
   Mission-Scripting-side probe (trigger "DO SCRIPT" on the same unit) to see whether either
   value matches the `LoGetWorldObjects` key directly — would settle which of the two documented
   id concepts (mission id vs. runtime object id) the export key actually is.

### Possible Approaches
- **If confirmed stable within a lifetime (the likely outcome given the evidence above):**
  the deferred diffed-store design is sound as long as it treats an id disappearing-then-a-new-
  id-appearing-at-the-same-place as a *replacement* event, not an update — i.e. the diff layer
  needs an explicit "object died / new object spawned" case alongside "moved," not just a naive
  `dict[id]` overwrite. This is a cheap design accommodation, not a blocker.
- **If it turns out to shift even within one continuous life** (not indicated by any evidence
  found, but not fully ruled out without the live test): fall back to a synthetic identity
  keyed on `(object_type, coalition, position-at-first-sight)` with nearest-neighbor
  re-association each poll — materially weaker and reintroduces most of the "re-filter every
  poll" cost the diffed store was meant to avoid, so this is a real design risk worth flagging
  to Architect even though current evidence leans against needing it.
- Regardless of outcome, do not conflate `LoGetWorldObjects`'s key with the mission-editor
  `getID()` — they are documented as two different concepts; only a live cross-check (test
  step 4 above) can say whether/how they relate.

### Unresolved
- **No live two-poll (or death/respawn) confirmation exists yet** — everything above is
  documented-API-semantics plus a strong community-framework-design inference, not a
  reproduced-locally result. This is the single test that would move the whole question from
  "high confidence, desk research" to "confirmed."
- **Tacview's own DCS export script's actual id-handling code is unread** — connection to
  `lomac.strasoftware.com` failed via both `WebFetch` and a sandboxed `curl`. If the user can
  fetch `http://lomac.strasoftware.com/download/misc/DCS/TacviewExportDCS.lua` manually (or
  point to a GitHub mirror), it likely contains a direct, empirical answer already validated
  by a much larger, longer-running community tool than anything else found this session.
- **Whether `LoGetWorldObjects`'s key equals `Unit.getObjectID()`, `Unit.getID()`, neither, or
  something else entirely** is not established by any source found — both are separately
  documented DCS id concepts, and no source states which one (if either) the export table's
  index actually is.
- **forum.dcs.world threads specifically about this** (133284, 302542, 348227) are unread —
  403'd on automated fetch; ask the user to paste manually if a faster resolution than the live
  probe is wanted.
