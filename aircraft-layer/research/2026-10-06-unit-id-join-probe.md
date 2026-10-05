# Unit-identifier join: `LoGetWorldObjects` key vs `Unit:getObjectID()` / `Unit:getID()`

**Date:** 2026-10-06
**DCS version:** not verified locally — no DCS install is reachable from this session (macOS;
`/mnt/f/Games/DCS World/` absent, no cached `DCS-files.txt` in this worktree). The install was
`2.9.29.27278` at last read by prior sessions. **The probe itself records nothing about the version
— read it off `autoupdate.cfg` or the `dcs.log` header when the run comes back.**
**Theatre:** any (the probe is theatre-independent; whatever the test mission uses)

> **This is a pre-flight note.** Almost every claim below is marked
> **unverified, pending the run**. Nothing here is a finding yet, and nothing downstream should be
> planned on an assumed outcome — the "Outcome → decision" table exists so that whichever way the
> run lands, the next step is already decided rather than re-argued.

### Question

`body-layer`'s DCS-driven LOS verdicts are joined to the world-objects feed on **`unit_name`**
(`body-layer/src/perception/naked_eye_source.py:1066`, drop at `:1118`). The 2026-10-05 sortie shows
**323 of 425 admitted objects never received a live verdict once**, while 2,602 of 2,621 polls
carried *some* verdict — a per-object *permanent* join failure, not an availability problem
(`plans/post-review-fixes/explore-notes.md` §1;
`aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md`).

The user has now authorised using DCS unit IDs for this, bounded: an ID may stand in for
*what a human could have re-identified anyway* — same place a second ago, small displacement — not
as a free oracle across gaps or long absences (`explore-notes.md` decision 3).

But whether a usable identifier exists **across the two Lua states** is explicitly open.
`aircraft-layer/research/2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md`
line 139 lists as unresolved: *"Whether `LoGetWorldObjects`'s key equals `Unit.getObjectID()`,
`Unit.getID()`, neither, or something else"*. So, concretely:

1. Does `Unit:getObjectID()` exist in this DCS version, and does its value equal the
   `LoGetWorldObjects` table key for the same unit?
2. If not, does `Unit:getID()`? Or neither?
3. Does the same hold for **static objects** (`coalition.getStaticObjects`) and for **scenery** —
   the population that today can never be joined at all?
4. **How often are names missing or duplicated** among in-bubble units? Per poll: total units,
   count with a nil/empty name, count of names shared by 2+ units, and the duplicate names
   themselves.

Question 4 is the root-cause measurement and is worth having even if 1 answers cleanly.

### What is already known (not re-derived here)

From `2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md` and the 2026-09-09 note
it cites — read in full, see those files for the underlying evidence:

- **The `LoGetWorldObjects` table index is an object identifier, per ED's own doc comment**
  ("Returned table index = object identificator") — **evidence: documented** (ED comment, surfaced
  via `github.com/sprhawk/dcs_scripts`).
- **That key is stable per physical object across consecutive polls within one continuous life** —
  **evidence: reproduced-locally (source read) + strong indirect empirical** — Tacview's shipped
  `TacviewExportDCS.lua` bases its entire spawn/update/destroy lifecycle model on the key's
  presence/absence across polls, with no geometric re-identification step. Not a first-party ED
  statement, and still not a project-run live probe.
- **`getObjectID` and `getID` are distinct calls** in the mission-scripting API, and MIST carries a
  defensive workaround for **id collision after death/respawn** — **evidence:
  forum-claim/community-convention**, not confirmed. This matters to outcome B below.
- **`forum.dcs.world` blocks automated fetch (403)**, including
  `topic/194777-exportlua-destroyed-object/`, whose title suggests direct relevance — **unread**.
  Per standing practice this is not recorded as a give-up gap; see "Questions for the user" below.

Knowledge graph was queried before writing this note (`.claude/scripts/gq.sh`, which does now work
from a worktree). It returned the 2026-09-10 note above and a large set of symbol-level nodes;
**it surfaced no document covering this question that was not already named in the task** — so no
prior answer exists to point at instead of probing.

Two further facts, read from code this session (**evidence: reproduced-locally — code read**):

- **The Export side of the join already exists and needs no change.** `Export.lua` publishes
  `object_id` (the `LoGetWorldObjects` key), `unit_name`, and `is_ownship`, served as
  `GET /world_objects/latest` — fields `object_id`/`object_type`/`lat_deg`/`lon_deg`/`altitude_m`/
  `heading_true_rad`/`is_ownship`/`unit_name` (`aircraft-layer/src/schema/world_objects.py:178`).
  `is_ownship` is set by comparing the table key against `LoGetPlayerPlaneId()`, which makes the
  ownship object's `object_id` a *known-good* table key for a *known* unit — the basis of the
  strongest correlation anchor below.
- **`Export.lua`'s `aircraft_layer_debug.log` does not dump the world-objects payload** (only send
  failures), so there is no log-only route to the Export side. One saved `/world_objects/latest`
  response is required for the equality half of Q1/Q2.

Also relevant and **independent of any id choice**: `explore-notes.md` §1 names a *second* join
mechanism — `petrobrain-line-of-sight-hook.lua:261-263` walks `coalition.getGroups()` →
`grp:getUnits()`, so statics and scenery are never in a LOS result at all. **Switching the join key
does not fix that**; it needs `coalition.getStaticObjects` added to that Hook. Q3 measures whether
doing so would even be joinable.

### What the probe does

`aircraft-layer/dcs-export/petrobrain-unit-id-join-probe-hook.lua` — a Hook-state script that, at
1 Hz for at most 10 polls between `onSimulationStart`/`onSimulationStop`, calls
`net.dostring_in("scripting", ...)` once per poll and writes the result to `dcs.log`.

- **Scripting state only.** This box is configured `net.allow_dostring_in = { "scripting" }`
  (`petrobrain-api-surface-probe-hook.lua:50`, `petrobrain-damage-events-probe-hook.lua:17`).
  Nothing here needs `"export"` added, and the probe opens no socket, uses no port, and requires no
  collector change — it writes to `dcs.log` and nothing else.
- Per poll it enumerates every live unit on all three sides within 10 km of ownship, then statics
  via `coalition.getStaticObjects`, then one 300 m `world.searchObjects(SCENERY)` sphere (300 m
  because scenery search cost is superlinear above that —
  `2026-09-29-bridge-terrain-probe-results.md` Finding 14). For each object it records
  `<name>~<getID>~<getObjectID>~<lat>~<lon>~<alt>`, with `<NONE>` when the accessor does not exist
  on that object and `<ERR>` when calling it raised — so "absent" is distinguishable from "failed"
  from "returned nil".
- It separately logs the **type and live value** of each candidate accessor on a real unit
  (`class.Unit.getObjectID`, `class.Object.getID`, `inst.getObjectID`, `inst.getID`,
  `inst.getNumber`, …). That line alone answers the *existence* half of Q1/Q2 with no Export side at
  all.
- For Q4 it counts, per poll, total in-bubble units, units whose name accessor failed or returned
  nil/empty, the number of names shared by 2+ units, how many units that covers, and emits the
  duplicate names with their counts.
- **Correlation between the two Lua states**, three anchors, strongest first:
  1. **Ownship, name-free.** `Export.lua` flags exactly one object `is_ownship: true`, so its
     `object_id` is a genuine table key for a known unit. The probe logs the player's own
     `getID()`/`getObjectID()` on `PB_UIDJ_OWN`. **One integer comparison settles Q1/Q2** with no
     name matching whatsoever.
  2. **Lat/lon, name-free.** Every entry carries lat/lon from `coord.LOtoLL` *inside the scripting
     state*. `/world_objects/latest` reports lat/lon too, so entries pair positionally. This is
     what covers duplicate-named and nil-named objects, which cannot be matched by name by
     construction.
  3. **Unique names**, as a cross-check on (2) for units whose name is unique that poll.

Log format is specified in full in the script's header; every line carries a `PB_UIDJ` marker and
`|`-delimited fields, object sections are chunked with an explicit `chunk=<i>/<m>` so a missing
piece is detectable rather than silent. (Lines are *not* truncated by DCS — verified 2026-10-05 —
the chunking is for readability and loss-detection, not a workaround.)

Verification done on the script itself, with no DCS available:

- `luac5.1 -p` (Lua **5.1.5**, the version DCS embeds) passes on the file, **and separately on the
  bridged inner chunk extracted from its long-bracket literal** — `luac` cannot see inside a string,
  so checking only the outer file would have proved nothing about the half that actually runs in the
  mission-scripting state.
- The **no-hoisting bug class was ruled out mechanically, not by eye**: `luac5.1 -l -p` lists every
  `GETGLOBAL` the bytecode performs, and for both chunks the global names referenced are exclusively
  Lua stdlib (`pcall`, `string`, `table`, `math`, `type`, `tostring`, `ipairs`, `pairs`, `require`)
  and genuine DCS APIs (`log`, `net`, `coalition`, `coord`, `world`, `timer`, `Unit`, `Object`,
  `StaticObject`). **None of the script's own helper names appear as globals**, which is exactly the
  signature the `push_ptt_state` failure (2026-09-23) would have left and which `luac -p` alone
  cannot see.
- Every DCS call is `pcall`-wrapped on both sides of the bridge, and the whole poll is `pcall`-wrapped
  inside `onSimulationFrame`, so a probe failure logs a `PB_UIDJ_ERR` line instead of taking the
  mission down mid-flight.
- `ruff`/`mypy` were **not** run on the reduction script: no subproject `.venv` exists in this
  worktree and `ruff` is not on `PATH`. The script is investigation scaffolding under `research/`,
  not pipeline code, and it was instead exercised end-to-end (below).

### Reproducible Test

**The reduction:** `aircraft-layer/research/2026-10-06-unit-id-join-reduce.py` (stdlib only, runs
anywhere including on the Windows box).

```sh
python3 aircraft-layer/research/2026-10-06-unit-id-join-reduce.py dcs.log world_objects.json
```

`dcs.log` alone answers Q4 in full and the existence half of Q1/Q2; the saved
`/world_objects/latest` response adds the equality verdict. It prints: the ownship anchor, the
accessor existence/value table, the per-poll Q4 census, the duplicate names, and — per population
(units / statics / scenery) — how often `getID` and `getObjectID` equal the Export-side `object_id`
among position-paired objects, with worked examples.

Pairing is deliberately conservative: 30 m tolerance (both sides are read within ~1 s, so a 20 m/s
vehicle can legitimately differ by ~20 m, while measured object spacing is 2 m p05 / 16 m median),
and **a probe entry with two or more Export objects inside the tolerance is reported `ambiguous` and
dropped rather than guessed at** — a wrong pairing would otherwise fabricate a match or a mismatch.
Read the `paired / unmatched / ambiguous` counts before believing any percentage.

**The reduction was exercised against a synthetic `dcs.log` + `/world_objects/latest` pair in the
probe's exact emitted format** — **evidence: reproduced-locally** — covering: `getObjectID`
matching, `getID` not matching, a duplicate-name pair, a nil-named unit, a `<NONE>` accessor, a
chunked multi-line section, statics, scenery, log-only mode with no JSON, and an empty log. It
produced the correct verdict in each case and exits `1` with an actionable message when no
`PB_UIDJ_META` line is present. **This is a test of the reduction, not of the probe** — the probe's
own behaviour inside DCS is unverified until the run.

### Deployment steps

Copy-pasteable; the whole thing is seconds of flight, not a sortie.

1. **Deploy the probe** — copy
   `aircraft-layer/dcs-export/petrobrain-unit-id-join-probe-hook.lua`
   to `Saved Games\DCS\Scripts\Hooks\petrobrain-unit-id-join-probe-hook.lua`.
   It sits alongside the other Petrobrain Hook scripts and conflicts with none of them (no shared
   port, no shared global, its own `log.write` tag `PetrobrainUnitIdJoin`).
2. **Confirm the `autoexec.cfg` opt-in is already in place** — `Saved Games\DCS\Config\autoexec.cfg`
   must contain `net.allow_dostring_in = { "scripting" }` (it already does, since the LOS and F10
   Hooks depend on it). No change needed, and **do not add `"export"`** — nothing here uses it.
3. **Restart DCS.** Required: Hook scripts are loaded once at startup, so a newly-copied file is not
   picked up by a mission restart alone.
4. **Start the collector** as usual (`aircraft-layer/RUN.md` / `WORKFLOW.md`) — needed only for
   step 6.
5. **Fly the lightest mission that has ground units near the player.** Any instant-action or
   quick-mission with a handful of ground units within ~10 km works; the **lightest adequate option
   is a Mission Editor / instant-action start already on the ground or hovering near a ground
   group** — the probe needs units in the bubble, not movement, altitude, or combat. Let it run
   **~15 seconds** after the mission starts: the probe polls at 1 Hz and stops itself after 10
   polls, logging `PB_UIDJ_DONE`. A mission with a *column of same-type vehicles* (a tank platoon,
   a road convoy, an infantry squad) is ideal, because that is the population Q4 is about.
6. **While still in that mission**, save one world-objects response:
   ```sh
   curl http://127.0.0.1:7791/world_objects/latest > world_objects.json
   ```
   (Or from the Mac: `curl http://<windows-box-lan-ip>:7791/world_objects/latest > world_objects.json`.)
   Timing is not tight — anything during the same mission is fine, since the pairing tolerance
   absorbs ordinary movement and the ownship anchor is exact regardless.
7. **Send back exactly two files:**
   - `Saved Games\DCS\Logs\dcs.log`
   - the `world_objects.json` from step 6

   Nothing else is needed. If `dcs.log` is inconveniently large, `grep PB_UIDJ dcs.log > pb_uidj.log`
   and send that instead — the reduction reads either.
8. **Optional, free:** the probe is harmless to leave deployed (it self-limits to 10 polls per
   mission), but delete the file once the question is settled, same discipline as every other probe.

### Outcome → decision

Each row states what becomes true and what the next step is, so the run's result does not need
re-arguing. **All rows are conditional — none is a finding yet.**

| Outcome (from the reduction) | What the join becomes |
|---|---|
| **A. `getObjectID` exists and equals `object_id`** for units *and* statics | **The join switches to the integer id.** The LOS Hook publishes `getObjectID()` per entry instead of (or alongside) `getName()`; `naked_eye_source` joins on that int. This removes **both** failure mechanisms at once — nil names and duplicate names stop mattering entirely. Still needs the Hook extended with `coalition.getStaticObjects` (a separate, independent fix). Keep the name on the wire too, for one sortie, as a cross-check. |
| **B. `getID` matches instead** | Same mechanical change, keyed on `getID`. **But flag the respawn risk explicitly**: `getID` is the mission-editor-ish unit id and MIST carries a death/respawn collision workaround (forum-claim-unverified). Under the user's own bound — an ID may only stand in for what a human could re-identify anyway — this is acceptable for within-life continuity but must not be treated as identity across a gap. Architect's call; worth one extra probe poll after a kill if it matters. |
| **C. `getObjectID` exists but matches nothing**, and `getID` does not either | **Fall back to a position join, not a name join.** The LOS Hook already computes each unit's `x/y/z`; have it publish lat/lon per entry and join against `/world_objects/latest` positionally. This is name-free, needs no new identifier, and reuses machinery `perception.association` already has. It is the recommended fallback because it is the one option whose correctness does not depend on any undocumented cross-state identifier at all. |
| **D. `getObjectID` reports `<NONE>`** on every object | Q1 answered negative outright; go straight to B, then C. |
| **E. Q4 shows high duplicate/nil-name counts** (expected, given the sortie) | Independently confirms the root cause and **makes the name join unfixable-in-principle**, whatever happens to A–D. Worth recording as the measurement the 2026-10-05 diagnosis was missing. |
| **F. Scenery entries never pair** with any Export object | Expected, and an architectural statement rather than a defect: `LoGetWorldObjects` has no scenery category, so **scenery can never be joined to the world-objects feed by any key**. If scenery LOS is wanted, it needs a different mechanism (the LOS Hook reporting scenery sightlines directly, not joined). Report to Architect; do not design a scenery join. |

### Questions for the user (queued — no reply needed before the run)

1. **Is there a forum thread you can paste?** `forum.dcs.world/topic/194777-exportlua-destroyed-object/`
   403s automated fetch and has 403'd across three sessions now. Its title suggests it covers the
   destroy/respawn id-lifecycle boundary directly — which is exactly outcome B's open risk. Pasting
   its content would likely settle that without a second probe. Not blocking.
2. **Should the probe also cover the respawn boundary?** It currently does not kill anything. If you
   want outcome B's collision risk measured rather than inferred, the addition is small (keep polling
   past a kill and watch whether an id reappears), but it changes the test from "15 seconds on the
   ground" into a sortie with a shot fired. Left out deliberately.
3. **Which mission did you fly?** Note the theatre and the mission name with the logs — the Q4
   duplicate-name census is a property of the *mission author's* naming, so the number means little
   without knowing what produced it. Mission-author naming habits are exactly what the user
   described in `explore-notes.md` decision 3 ("I fly missions created by others").

### Unresolved

- **Everything in "Outcome → decision" is conditional.** No live DCS was reachable from this
  session, so neither the probe's behaviour inside DCS nor any of Q1–Q4 is answered yet.
- **DCS version for the run is unrecorded by the probe itself.** Read it off `autoupdate.cfg` or the
  `dcs.log` header and record it when the results land, or the finding has no version provenance.
- **`coord.LOtoLL`'s availability in the mission-scripting state is assumed, not verified here**
  — **evidence: inferred** (it is standard mission-scripting API and `world-model/` research relies
  on it, but this specific Hook has not run). It is `pcall`-wrapped: if it is unavailable, lat/lon
  come back `<ERR>` and correlation anchor (2) is lost — anchors (1) and (3) still work, so the run
  still answers Q1/Q2, just with less coverage of the duplicate/nil-named population. If `<ERR>`
  appears on every entry, that is the explanation.
- **Whether `getObjectID` is stable across the *whole* object population** (it could match for
  aircraft and not ground units, or vice versa) — the reduction reports units, statics and scenery
  separately precisely so a partial answer is visible rather than averaged away.
- **The second join mechanism is untouched by this probe's outcome.** The LOS Hook enumerating only
  grouped units (`petrobrain-line-of-sight-hook.lua:261-263`) is a separate fix, needed under every
  outcome above except F.

### Sources

- `aircraft-layer/research/2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md` —
  read in full; the base evidence, not re-derived here.
- `plans/post-review-fixes/explore-notes.md` §1 — the sortie reduction and the user's own bound on
  ID use.
- `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`,
  `.../petrobrain-api-surface-probe-hook.lua`, `.../petrobrain-damage-events-probe-hook.lua` —
  the `dostring_in` pattern and the `allow_dostring_in` configuration this probe reuses.
- `aircraft-layer/src/schema/world_objects.py`, `aircraft-layer/src/api/server.py` — the Export-side
  field names the reduction parses.
- `aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md` Finding 14 — the 300 m
  scenery-search bound.
- `aircraft-layer/WORKFLOW.md` — deploy paths, collector port 7791.
- `.claude/scripts/gq.sh` — knowledge-graph query run before writing this note.
