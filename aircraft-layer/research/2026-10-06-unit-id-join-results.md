# Unit-id join probe — results from two live runs

**Date:** 2026-10-06. **DCS version:** read it off the logs with the runs if provenance is needed;
the probe does not record it (its own note's known gap).
**Runs:** `win-mac-sync/from-windows/dcs.log` + `world_objects.json` (mission 1),
`dcs2.log` + `world_objects2.json` (mission 2).
**Reduction:** `aircraft-layer/research/2026-10-06-unit-id-join-reduce.py`, plus name-keyed
cross-checks run by the main loop.

Question, probe design and the pre-committed outcome table:
`aircraft-layer/research/2026-10-06-unit-id-join-probe.md`.

---

## The headline: the join key was never the problem

**Evidence status: reproduced live, twice.**

| | mission 1 | mission 2 |
|---|---|---|
| Export objects | 57 | **404** |
| AI units (probe) | 48 | 51 in bubble / 99 logged |
| static objects (probe) | **0** | **142** |
| scenery (probe) | 0 | 11 |
| `unit_name` null, either side | **0** | **0** |
| duplicate `unit_name`, either side | **0** | **0** |

**Mission 2 is the 2026-10-05 sortie's own mission** — its type histogram is that sortie's
signature (`Soldier M4 GRG` ×139, `T-55` ×34, `Tigr_233036` ×27, `5p73 s-125 ln` ×17), and it is
Syria at 33.29 N 36.47 E.

So the mechanism named in `BL-B31` and in `BL-11` Stage 4 — *nameless statics and duplicate names
can never receive a live verdict* — **did not reproduce in the mission it was diagnosed from.**
Name-keyed joins against the Export feed, mission 2:

- **units: 50/50 join by name.**
- **statics: 94/94 join by name.**

## Q1/Q2: `getObjectID` is the `LoGetWorldObjects` key — for units only

- `Unit:getObjectID()` == `object_id`: **32/32 (mission 1)**, **50/50 name-keyed (mission 2)**.
- `Unit:getID()` == `object_id`: **0/32**, **0/50**. It is the small mission-editor id (1, 13, 175).
  Outcome **B** is therefore excluded, and with it the MIST respawn-collision risk.
- Ownship anchor, stable across all 10 polls of both runs: `getObjectID` equals the one object the
  Export feed flags `is_ownship`.

**But `getObjectID` does not exist on `StaticObject`: `<NONE>` in 94/94 cases.** `StaticObject.getID`
exists and returns a small id that is **not** the table key. So there is no integer key that spans
both populations, and an integer join would have to be units-only — asymmetric, for no gain over the
name join that already works for both.

## The real mechanism: the Hook never looks at statics

`aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua:261-263` walks
`coalition.getGroups()` → `grp:getUnits()`. **Static objects are not in that enumeration at all**,
so they cannot appear in a LOS result and cannot receive a verdict, whatever the join key is.

In mission 2 that is **278 of 404 objects — 68.8 %** invisible to the LOS feed by construction.
Compare the explore's own measurement from the sortie: **323 of 425 admitted objects (76 %) never
received a live verdict once.** The two figures are the same fact.

It also explains the anomaly the sortie note could not: no-verdict rows had a **lower** median true
range (3,820 m) than verdict-bearing ones (6,750 m). Static vehicles are placed *around* positions
as emplacements and decoration, so they cluster closer in — the opposite of what truncation would
produce, which is why the 128-sightline cap was correctly ruled out.

## Q3 / scenery: unjoinable by any key, as expected

11 scenery entries, **0 position-paired**. `LoGetWorldObjects` has no scenery category, so scenery
can never be joined to the world-objects feed by name, by id, or positionally. If scenery LOS is
ever wanted it needs the Hook reporting scenery sightlines *directly*, not joined. **Do not design a
scenery join.** (Outcome **F** of the probe's table, confirmed.)

## A falsified comment the join rests on

`Export.lua:362-366` states that `unit_name` is `obj.UnitName` *"since mission scripting's
`Unit:getName()` returns the identical string."* For the player's own aircraft it does not:

| object id | mission scripting `getName()` | Export `UnitName` |
|---|---|---|
| 16791808 (mission 1) | `Rotary-2-1` | `sg` |
| 16888576 (mission 2) | `01-A-Mi-24P011` | `sg` |

The Export side substitutes the **player's callsign**. Harmless today — ownship is filtered on the
`is_ownship` flag, not by name — but the comment asserts an identity that does not hold, and the
whole name join was built on it.

## What this corrects, and who was wrong

**The orchestrator's diagnosis of 2026-10-06 was wrong in its mechanism**, and the error propagated
into `BL-11` Stage 4, `BL-B31`, and `plans/post-review-fixes/explore-notes.md` §1. It was built from
two true facts — `unit_name` is `str | None` in the schema, and `name_counts[name] > 1` drops
duplicates — plus an assumption that the sortie's missing population *was* that drop. The probe
shows the schema's `None` case and the duplicate case are both **empty** in these missions, and the
real population is one nobody had enumerated.

**The sign of the range anomaly was the clue, and it was read as supporting evidence for the wrong
mechanism.** "Nameless statics cluster close in" and "static vehicles cluster close in" predict the
same observable; only the second is true here. A hypothesis that explains the anomaly is not thereby
the mechanism.

## Consequences

1. **Keep the name join.** It works 144/144 across both populations in mission 2. Dropping to an
   integer buys nothing and cannot cover statics.
2. **Add `coalition.getStaticObjects` to the LOS Hook.** This is the change that recovers ~69 % of
   objects, and it is the whole fix on the Lua side. User direction 2026-10-06: statics are in scope
   (`docs/acceptance/2026-10-05-sortie-feedback.md`, final section) — they are tanks, infantry and
   eight `ZSU-23-4 Shilka` in this mission, not map furniture.
3. **Re-measure the sightline cap and the bridge cost before trusting them.** The pre-statics figures
   were *median 43, max 71 units in a result* against a 128 cap, with `bridge_call_ms` ~1 ms. Adding
   278 candidate statics to a 404-object mission may reach that cap for the first time. **Unmeasured
   — do not assume the old headroom.**
4. **`BL-11` Stage 4 and `BL-B31` need rewriting**, not amending: their first step ("settle the join
   key", "the join key is `unit_name` and cannot be total") is answered and wrong.
5. **Fail-closed on a missing verdict stays the goal**, and is still gated on this fix landing — it
   just now blocks on statics being enumerated rather than on a key change.

## Unresolved

- **The 128-sightline cap under statics** — item 3 above. One sortie with the fix in place answers it.
- **DCS version provenance** for these two runs: not captured by the probe. Its own note already
  records this as a required-field gap for future probes.
- The single 25/26 `getObjectID` miss in mission 2's position-paired units is almost certainly a
  pairing artifact among 17 ambiguous rows — the name-keyed test over the same run is 50/50. Not
  chased further.
