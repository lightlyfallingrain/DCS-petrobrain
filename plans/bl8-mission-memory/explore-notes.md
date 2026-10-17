# BL-8 Mission Memory — explore notes

Branch: `feature/bl8-mission-memory`. Conversation started 2026-10-17 (`/explore mission memory`).

## The framing the user gave it: a kneeboard flight log

> *"The knee board in flight log entry is a good reference for this. What was seen, when and where,
> in condensed format."*

> *"Goal: being able to use "knee board notes" as reference during mission and as input to debrief
> phase (debrief not even concepted yet)"*

So this is **BL-8**, not the static mission-understanding artifact. Two consumers: in-mission
reference, and a debrief phase that does not exist yet and is not being designed here.

## What goes in — user's own words, 2026-10-17

- **groups**
  - location
    - `x,y,z` for Petrobrain internal use
    - lat, lon for debrief
    - landmark reference for in-cockpit communication
  - IFF, though not yet implemented
  - composition at class level, "like the describe call is currently. Not per unit data, but general
    composition and count using the existing granularity words"
- **all air defence earns a separate entry.** If part of a group, link there. A group *of* air
  defence units → that group itself is the entry.
  > *"This is like Petrovich marking a red dot on knee board map for where air defence units are."*
- **attack runs**: time, target, weapon, did the target get destroyed or not.
- **pilot-ordered marks**: the pilot may tell Petrovich to remember a location — landmark,
  unit/group position, grid coordinate. That earns an entry and a *"mark with growing index"*, so it
  can be referred to later as "mark #".
- **being attacked by another unit/group** — suppress repeat entries from the same unit unless
  minutes pass in between.

## Already-known constraints this must respect

- `X-B20` (open): a landmark reference may only be spoken if LOS- and knowledge-gated. A kneeboard
  entry's landmark reference is one of the two things that item is about.
- `BL-8`'s existing named consumer: the **"safe from" callout**, switched off in
  `belief/speech.py`'s `engaged=False` branch until BL-8 exists. It needs *believed position now*,
  not last-observed — see the immutability question below.
- `docs/concept/PETROBRAIN_SYSTEM.md:252` says mission memory is "updated as mission phases change";
  only the read half (`belief/mission_phase.py`) was ever built.

## Decisions, 2026-10-17 (user, in the explore conversation)

1. **Obsolescence, not mutation.** *"old lines cannot be modified but can be marked obsolete. On
   paper I would draw a line through it to mark it obsolete. Append new data. Then Petrovitch can
   just ignore obsolete lines."* So: append-only log + a struck-through flag. No derived "latest per
   group" index is needed as a separate structure — "ignore obsolete lines" *is* the index.
2. **Destruction comes from belief, with no new logic.** *"use belief to populate, no extra logic.
   Just add entry when unit is destroyed is determined."* An attack-run entry's outcome is whatever
   belief concludes, whenever it concludes it — `UNKNOWN` stays legal and common.
3. **Marks and air-defence entries are separate spaces.** *"Air defence reference by self relative
   position as usual and/or landmark reference. Not index number, unless user sets a mark there."*
   Only pilot-ordered marks get the growing index. Air defence is referred to the way everything
   else is: relative position and/or landmark.
4. **Re-sighting a group writes a new line** (and strikes the old one), and the same-group judgement
   is Petrovich's own association, fallible.
5. **The being-attacked suppression window is a tunable constant, default ~2 min.**
6. **Moving groups need a movement direction** — N/NE/… — not just "moving".

## Two gaps this spec runs into, found while checking (flag before planning)

- **Movement direction does not exist.** `belief/motion.py` is a deliberate two-state flag
  (`"moving"`/`"stopped"`) with no heading, and only the naked-eye channel supplies motion evidence
  at all, so a scope-only contact is honestly `None`. A direction word is therefore *new belief
  work*, not a read of existing state. (`docs/concept/PETROBRAIN_SYSTEM.md`'s example contact shows
  `motion_when_seen: north`, which was never built.)
- **Nothing in belief determines destruction today.** Decision 2 above says "use belief", but there
  is no destroyed/dead state anywhere in `body-layer/src/belief/`. Deciding a unit died needs a
  source, and the obvious one (it vanished from world objects) is ambiguous with losing sight of it
  — exactly the no-omniscience trap. Needs its own decision before the attack-run outcome field can
  be populated by anything but `UNKNOWN`.

## The two kneeboards (user, 2026-10-17, mid-conversation)

> *"Imagine that Petrovitch has two knee boards: notepad and current section of map. He can make
> notes on either."*

Read structurally: **one store, two surfaces.** The notepad is the entries ordered by time; the map
section is the same entries drawn at their positions. The map is not a second memory — the "red dot
for air defence" is this surface rendering an `AD` entry, not a separate record. That keeps the
append-only/obsolete rule (decision 1) sound on both: a struck entry stays on the map, crossed out
in place, exactly as it stays on the notepad.

Open consequence, not yet decided: the map has a *current section*, so it is bounded and scrolls/
re-centres with the aircraft. An entry outside the current section still exists on the notepad. Does
anything have to happen when an entry leaves the drawn section, or is it purely a view concern?

Mock of all three (notepad page, map page, entry anatomy):
https://claude.ai/artifact/Swg1RDkBbkt4qZihnUrP75
