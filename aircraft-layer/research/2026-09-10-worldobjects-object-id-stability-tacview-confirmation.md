# `LoGetWorldObjects()` object-id stability — Tacview source cross-check

**Date:** 2026-09-10
**DCS version:** not verified locally — see below (desk research only, no live DCS access this session)
**Theatre:** n/a

### Question

Follow-up to the prior unmerged-branch investigation
(`feature/omniscient-mission-memory:aircraft-layer/research/2026-09-09-worldobjects-object-id-stability.md`,
read in full this session, not re-derived — see that file for the base evidence: ED's own doc
comment "Returned table index = object identificator," `Unit.getObjectID()` vs `Unit.getID()`
distinction, MIST's death/respawn id-collision workaround). That session's own "Unresolved"
section flagged two concrete next steps: (1) read Tacview's actual `TacviewExportDCS.lua`
id-handling code — unreachable last session (`lomac.strasoftware.com` connection refused); (2)
retry three 403'd ED forum threads. This session re-attempts both, for the current, narrower,
higher-stakes question: body-layer's proposed "continuity-of-track" fix
(`plans/contact-duplication-ambiguity-runaway/debug.md`, `todo/todo.md`'s "Continuity-of-track
association" item) would use the same `object_id` key to *skip* the spatial/class gate when an
id repeats across consecutive polls. If the id is not a stable per-physical-object identifier
within one continuous life, this fix would cause silent false merges of distinct objects —
strictly worse than the bug it's meant to fix.

### Findings

- **Tacview's actual production export script (`TacviewExportDCS.lua`, fetched successfully
  this session from `tacview.net/download/TacviewExportDCS.lua` — the canonical current
  distribution, not a stale mirror) treats the `LoGetWorldObjects()` table key as a stable
  dictionary identity across consecutive polls, and is built entirely around that assumption**
  — **evidence: reproduced-locally (read the actual current source)**, source:
  `https://www.tacview.net/download/TacviewExportDCS.lua`. Specifically:
  - It maintains `self.LastObjectsStatus[ID]` (current-frame-known objects) and
    `self.LoggedObjectsStatus[ID]` (last-written-to-file state), both keyed directly by the
    `LoGetWorldObjects()` table index.
  - **New-object detection**: `not self.LastObjectsStatus[ID]` — an id appearing that wasn't
    present last poll is treated as a new object.
  - **Update-in-place**: `UpdateObject()` diffs current vs. previous frame *for the same key*
    (`not PrevObjectData or CurrentObjectData.Property ~= PrevObjectData.Property`) and emits
    only changed fields — this only produces correct output if the same key really does refer
    to the same physical object frame-to-frame; if the key were an unstable iteration artifact,
    this diffing would silently corrupt tracks (wrong object's old properties compared against
    a different object's new ones) — something that would have been immediately visible as
    garbled/teleporting tracks in a tool used by a very large, long-running community, and no
    such defect is documented anywhere found this session or last.
  - **Removal detection**: `RemoveObjects()` walks the *previous* poll's known-ids and flags
    any id missing from the *current* poll's fresh `LoGetWorldObjects()` result as destroyed
    (event code `!20`) — i.e. Tacview's whole object-lifecycle model (spawn/update/destroy) is
    derived purely from this id's presence/absence across consecutive polls, with no auxiliary
    geometric re-identification step at all.
  - A `GetOptimizedID()` helper XORs a high bit of the id for a file-size optimization
    unrelated to identity semantics (it toggles the same conceptual id between two encodings
    for delta-compression, not a re-derivation of identity) — noted so it isn't mistaken for
    evidence of instability.
  - This is materially stronger evidence than anything in the prior session's file: it is not
    a doc comment or a framework's defensive workaround, it is the actual, currently-shipped
    behavior of the tool the DCS community most relies on to render continuous, non-garbled
    object tracks from this exact API, at effectively unlimited real-world flight-hours of
    tacit validation. It does not, however, constitute a first-party ED statement, and it is
    still this session's *reading* of the source (not a live DCS probe run by this project).
- **ED forum threads remain unreachable** — `forum.dcs.world/topic/194777-exportlua-destroyed-object/`
  (promising title — appears to be exactly about object destruction/id lifecycle) and
  `.../topic/302542-how-to-use-logetworldobjects-only-for-my-aircraft/` both 403'd again this
  session, consistent with the standing project finding that `forum.dcs.world` blocks
  automated fetch (`aircraft-layer/research/` memory: forum-dcs-world-fetch) — **not recorded
  as an unread gap in the give-up sense**; flagged below for the user to paste manually if
  wanted, since `194777`'s title suggests it may bear directly on the destroy/respawn boundary.
- **No new evidence changes the death/respawn-boundary finding from the prior session** — it
  remains community-convention-level (MIST's workaround), not directly addressed by Tacview's
  code read this session (Tacview's own removal-detection logic, above, is consistent with
  "a destroyed object's id simply stops appearing," which is exactly the graceful-degradation
  behavior the current body-layer design already assumes for that boundary case — it does not
  newly confirm or refute id *reuse* after death).
- **`github.com/sprhawk/dcs_scripts` re-fetch this session reconfirms** the same ED doc-comment
  text as before ("Returned table index = object identificator") but, as before, has no
  additional stability discussion — no new information beyond what the prior session already
  extracted from this source.

### Reproducible Test

Unchanged from the prior session's file — still the authoritative closing test if a live
confirmation is wanted. Restated concretely here:

1. Deploy a variant of `Export.lua` (following the existing disposable-spike pattern,
   `aircraft-layer/dcs-export/Export.probe-pb15.lua`) that on each `LuaExportAfterNextFrame`
   call runs:
   ```lua
   for k, v in pairs(LoGetWorldObjects()) do
     debug_log(k .. " " .. tostring(v.Name) .. " " ..
       tostring(v.LatLongAlt.Lat) .. "," .. tostring(v.LatLongAlt.Long))
   end
   ```
   writing into the same flag-gated `aircraft_layer_debug.log` mechanism already built into the
   production script.
2. Fly/observe a mission with a handful of stationary or slow-moving AI ground units (no
   combat, no deaths) for at least 30-60 seconds of continuous polling at the existing 5 Hz
   rate.
3. Confirm the same physical unit (same `Name`, same lat/lon trajectory) reports the same
   numeric `k` on every poll across that window. This is the entire base claim
   continuity-of-track depends on — a clean pass here is direct, project-specific confirmation
   rather than inference from a third party's code.
4. Optional: kill one unit and confirm whether a same-slot AI-regenerated replacement gets a
   new `k` — settles the death/respawn boundary definitively (currently only
   community-convention-level evidence either way, though not load-bearing for the
   no-death-involved case this fix targets).

### Possible Approaches

Unchanged in substance from the prior session, now on firmer footing:

- **Proceed with continuity-of-track keyed on `object_id`, scoped strictly to `perception/`**,
  as currently planned — the evidence base has moved from "documented API semantics + one
  defensive community framework" to that plus "the id is the sole identity key a mature,
  heavily-used, long-running production export tool bases its entire non-garbled object-track
  reconstruction on, with no known defect reports of spurious identity swaps within a
  continuous object life." That is a real, if indirect, empirical validation — Tacview's
  correctness at scale is itself evidence the id doesn't shuffle mid-life, because if it did,
  Tacview's tracks would visibly break and the tool would be unusable for exactly the purpose
  it's known for.
  - As the prior session flagged, this fix's design must still treat "id disappears, a new id
    appears nearby" as a distinct *replacement* event (Tacview's own `!20` removal + separate
    addition modeling) — do not fold that into the continuity-skip path.
  - Reduce the ambiguity-runaway attack surface, not the whole gate: continuity-of-track
    should skip the gate only for the *specific* percept whose id repeated, not disable the
    gate structurally for the poll.

### Unresolved

- **Still no live, project-run two-poll confirmation** — this session upgrades the evidence
  from "desk research, ED doc + defensive framework" to "desk research, ED doc + defensive
  framework + a mature production tool's actual current source code that structurally depends
  on the same stability claim and is known to work correctly at scale." That is high
  confidence but is still not the same evidentiary class as "we watched it happen in our own
  probe." If the user wants to close this to "confirmed" rather than "high-confidence desk
  research," the test above is the way to do it — it is short (30-60s of flight) and reuses
  existing tooling.
- **`forum.dcs.world/topic/194777-exportlua-destroyed-object/`** — title strongly suggests
  direct relevance to the destroy/id-lifecycle question and remains unread (403). Ask the user
  to paste its content manually if a faster path than the live probe is wanted.
- **Whether `LoGetWorldObjects`'s key equals `Unit.getObjectID()`, `Unit.getID()`, neither, or
  something else** — still not established by any source found across either session.

### Sources
- `https://www.tacview.net/download/TacviewExportDCS.lua` — fetched and read this session
  (current canonical distribution).
- `https://github.com/sprhawk/dcs_scripts/blob/master/Export.lua` — re-confirmed ED doc-comment
  text, no new stability info.
- `forum.dcs.world/topic/194777-exportlua-destroyed-object/`,
  `forum.dcs.world/topic/302542-how-to-use-logetworldobjects-only-for-my-aircraft/` — both
  403'd, unread.
- Prior session (cited by reference, not duplicated):
  `feature/omniscient-mission-memory:aircraft-layer/research/2026-09-09-worldobjects-object-id-stability.md`.
