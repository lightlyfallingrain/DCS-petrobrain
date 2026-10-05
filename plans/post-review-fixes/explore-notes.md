# Explore: the 2026-10-05 review findings

Running notes of the `/explore` conversation held after the four whole-subproject reports
(`{body-layer,world-model}/research/2026-10-05-{performance-review,security-audit}.md`). Written as
it emerged, per `.claude/skills/explore/SKILL.md`. The user's words are quoted where the phrasing
carries the reasoning.

Feedback capture that preceded this: `docs/acceptance/2026-10-05-sortie-feedback.md`, final section.

---

## 1. World-model LOS must leave the live path entirely

**User direction, restating a standing one:**

> *"As discussed when doing the DCS LOS change, world model LOS _must not be used_. It is to be a
> *testing* only tool, not for live flight. Not only because of performance, but especially for
> *correctness*."*

This reverses the shape of what the reports proposed. Both of them, and the `BL-11` Stage 4 /
`M11` Stage 1 entries written from them, treated the offline fallback as something to make
**observable** — a coverage counter, a provenance field, a tolerance derived from the store. That
is the right fix for a fallback allowed to exist. It is the wrong fix for one that must not run.
An observable reporting a 77 % share of a path that should be 0 % measures the wrong thing.

### What the sortie trace actually says (reduced in-session, 2026-10-05)

Post-`X-B29` region of `~/dcs-detection-trace.jsonl`, 14,703 admissions:

| | objects |
|---|---|
| admitted at least once | 425 |
| **never got a live verdict, not once** | **323** |
| always had one | 74 |
| verdict in some polls, not others | 28 |

2,602 of 2,621 polls carried *some* verdict, so the feed was up essentially the whole flight.
**This rules out timing/coverage as the explanation**: under an availability story objects would
flip in and out, and only 28 did. 76 % of objects never resolved once, and they are ordinary
traffic — T-55 1,326 rows with zero verdicts, `Soldier M4 GRG` 3,020 against 213, BMP-2 / Tigr /
Shilka likewise. The same *types* appear on both sides, so the failure is per-unit and permanent.

### And they were being looked at

Heading estimated per poll from the verdict-bearing rows in that same poll (they must lie within
the commanded wedge), then the no-verdict rows tested against it — 1,190 usable polls:

| no-verdict rows | all | admitted |
|---|---|---|
| **inside** the commanded ±90° wedge | 104,025 | **4,668** |
| outside it | 76,556 | 300 |

So the answer to the user's own question — *"When can it happen that Petrovich looks directly at
something, but there's no DCS LOS verdict? The whole point here is that we know the LOS from
DCS."* — is that it happens constantly, it is **not** the cone, and it is not truncation either
(the 128 cap was never reached; max 71 units in a result). **It is the join.** Which means it is a
plumbing defect, not a state that needs designing for: fail-closed on a missing verdict is the
correct behaviour *once the join is fixed*, and the order is forced — join first, fallback removal
second.

### Two mechanisms in the join, not one

1. **The key is `unit_name`** (`body-layer/src/perception/naked_eye_source.py:1066`, drop at
   `:1118`). `aircraft-layer/src/schema/world_objects.py:109` declares it `str | None`, `None` for
   scenery and statics, and `name_counts[name] > 1` drops every unit sharing a name with another.
2. **The Hook only iterates units in groups** —
   `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua:261-263` walks
   `coalition.getGroups()` → `grp:getUnits()`, so statics and scenery are never in a result at all.
   An `outpost` appears in the no-verdict population, consistent with this.

### The user relaxes the no-DCS-ID rule, with a bound

> *"I do not create missions myself, I fly missions created by others. There are units that of same
> type, like a column moving on a road, a tank platoon, infantry units guarding something, etc. So,
> yes, lot's of units of same type are expected to exist. DCS unit ID is a unique ID, that could be
> used, but it should not cause omniscience. I'd rather have detection work better and relax the
> rule of not using DCS ID's than have the detection work poorly. A human scanning would not know
> any unit ID either, but could fairly easily determine "this was here a second ago, it's moved
> 20 m, it's still the same unit"."*

The bound is in the last sentence and it is the design: an ID may stand in for **what a human could
have re-identified anyway** — same place a second ago, small displacement — not as a free oracle
across gaps, occlusion or long absences.

**The open unknown this creates is already on file and unresolved.** The name-based join exists
precisely because `aircraft-layer/research/2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md`
concluded the two environments share no other identifier, and that note's own line 139 lists as
unresolved: *"Whether `LoGetWorldObjects`'s key equals `Unit.getObjectID()`, `Unit.getID()`,
neither, or ..."*. One probe answers it — log name + `getID()` + `getObjectID()` from the Hook and
the table key + `UnitName` from `Export.lua` for the same frame, and compare. Investigator work,
before any plan depends on it.
