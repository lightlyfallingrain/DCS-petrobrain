# Sortie feedback, 2026-10-05 — the pilot's own words

Captured verbatim so none of it is lost to a conversation. The user flew the merges of 2026-10-05
(contact-report flood suppression, redundant group disclosure, terrain callouts, `silence`,
confirm band, SPU-8 intercom, and the first flight carrying DCS-driven LOS).

Log analysis of the same sortie:
`aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md`.

---

## Verdicts on what was flown

> *"very good improvements on contact detection and reporting. Not perfect, but we will refine."*

| item | verdict |
|---|---|
| `silence` command | **pass** |
| Contact-report flood suppression | **pass** |
| Confirm band | **pass** |
| SPU-8 intercom (flown separately) | **pass** — *"SPU-8 feature works, tested and accepted."* |
| Brain Stage 2 | **not testable** — *"needs brain to free text path, not testable yet"* |
| DCS-driven LOS | **not judgeable from the cockpit** — *"I can't tell about DCS LOS directly from flight"*; read from logs instead |

---

## Change requests from this sortie

Planned in `plans/sortie-2026-10-05-refinements/plan.md`. Items 2–4 are small and independent;
item 1 grew into its own branch.

### 1. The location fragment — rewrite

> *"'next to a road' → many, many are next to road, it kinda loses its meaning. Say that only for
> watched contacts."*

Then, expanding it:

> *"terrain wins when present. Use this priority: settlement, terrain feature, road. Drop the x
> meters from callout. Add direction from like 'south of village, near' or 'in next valley, north,
> medium distance'."*

Then, on where water sits (answering a direct question): **settlement → terrain feature + water →
road → coastline / landcover.** A lake shore is a landform a pilot steers by; a coastline is
kilometres long and landcover is a region, so neither is a point.

Then, correcting the direction word — **it is per-kind, not universal**:

> *"'armor, 3 o'clock, next valley, medium distance' → yes, this is good and enough.*
> *'in a valley, north' → not really informative for valleys. North of village, south of lake, west
> of junction, etc are useful.*
> *for ridges it could be useful, since one side hides and the other exposes → north of ridge or
> near/far side of ridge"*

| feature kind | direction word |
|---|---|
| settlement, water, junction, road | compass — *"north of village"* |
| valley | **none** — *"in a valley"* is the whole fact |
| ridge | **near side / far side** — states the masking conclusion |
| `"next valley"` (divide form) | **none** — o'clock and distance band carry it |

### 2. `describe` as a synonym for `report`

> *"use 'describe' as synonym for 'report'"*

Independent evidence from the same flight: the pilot actually said **`"Describe eleven o'clock."`**
at t_sim 258 and it fell through unrecognised.

### 3. `follow` / `watch group <where>` tags the whole group

> *"'follow/watch group <where>' should tag all units in that group as watched"*

Settled: **tag once, statically.** Members at the moment of the command become watched; a later
joiner is not, a leaver stays. No watch-to-group binding to maintain as groups split and merge.

### 4. `scan ahead` sweeps three hours

> *"scan ahead is now equal to scan 12 o'clock → change so that scan ahead is 11-12-1 o'clock scan"*

Clarified, and this is the load-bearing half:

> *"still one clock hour at a time. A sweeping scan like any other scan, repeating loop 11-12-1
> o'clock."*

**Not a widened cone.** The gaze stays one hour wide and steps 11 → 12 → 1 → 11 …, so the DCS LOS
query cone is unaffected. The real effect is dwell: each hour is revisited a third as often.

---

## Standing direction given the same day, recorded here because it is easy to lose

- **No live elevation polling**, with a caveat: *"unless another reason comes up that requires it in
  live missions… build it if that happens."* (`X-B26` closed.)
- **The 12 m LOS tolerance** *"becomes obsolete and incorrect. It may be used in test code when LOS
  is simulated offline, but must not be used in actual code."*
- **Offline LOS is for testing only**: *"recreating LOS of actual flights offline makes no sense, we
  cannot get required accuracy without DCS. Instead, detection trace logs could carry the LOS
  boolean from DCS-driven LOS."*
- **LOS scoping principle**: *"If Petrovich is not looking at something, for all practical purposes
  it has no LOS or LOS does not matter. **LOS only matters for things that we would process, if
  there is LOS.**"*
- **Arbitrary FOV** for the LOS cone *"that way future changes, like peripheral vision, can easily
  be taken aboard"* — and the command shape *"will be something like `look(int bearing, int FOV)`.
  It could also be `look_around(x_coord, y_coord, (alt))`, but that is not needed now."*

---

## Reading the four review reports, 2026-10-05 (later the same day)

The user read the whole-subproject performance and security reports
(`{body-layer,world-model}/research/2026-10-05-{performance-review,security-audit}.md`) and raised
two things. Verbatim:

> *"2 - Agents on worktrees cannot use graphify -> needs to be fixed"*

> *"3 - LOS on world model being a backup and potentially taking a lot of time -> As discussed when
> doing the DCS LOS change, world model LOS_must not be used_. It is to be a *testing* only tool,
> not for live flight. Not only because of performance, but especially for *correctness*."*

**Item 3 is a restatement of direction already in this very file** ("The 12 m LOS tolerance…
must not be used in actual code", "Offline LOS is for testing only"), and it is worth recording
that it had to be restated. Both reports, and the `BL-11` / `M11` milestones written from them,
treated the offline fallback as something to make **observable** — a coverage counter, a provenance
field, a tolerance derived from the store. That is the right fix for a fallback that is *allowed to
exist*. The standing direction is that on the live path it is **not** allowed to exist, and the
reason is correctness first and performance second. An observable that reports a 77 % share of a
path that should be 0 % is measuring the wrong thing.

Explored with the user immediately after (see the `/explore` session that follows this entry).

