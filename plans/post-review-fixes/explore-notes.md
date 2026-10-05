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

---

## 2. Re-identification is a group-level judgement, and the data says it can only be

**User, on what survives losing sight:**

> *"Losing line of sight alone does not do it. Because I remember where it is, and if it was moving.
> I can go hide behind a ridge, circle to different position and pop up for an attack run, or to
> just observe from different angle. It such case, I compare what I see againt what I remember.
> Even if the units have moved, does the count match? Classification? Movement (direction? on
> road?). It could be that I see more units from a different angle and maybe some are hidden by
> buildings, but I can remember that they were there. If I see no movement, then I especially expect
> that the units I remember have not moved."*

**On what makes something a new unit:**

> *"It not being *with* the group I remember. There being more units in the group that memory tells,
> so some unit(s) have to be newly detected. Group composition changing from what I remember.
> Location changing so much that unit movemnt is not an explanation (considering typical unit
> movement speeds). Different type of group, e.g. AAA installment (especially entrenced = not
> capable of movememnt) would be different than other units that are nearby."*

Every predicate in that list is over a **remembered group compared with an observed cluster**.
`ContactStore.ingest` (`belief/contacts.py:957-971`) compares one percept against every individual
contact with a Mahalanobis gate and nothing else, and `Group` — which already exists from the
group-reporting work — takes no part in association.

### The flat inflation rate is the churn mechanism

`GATE_GROWTH_RATE_MPS = 20.0` (`belief/position_belief.py:161`) inflates a contact's position
uncertainty at 20 m/s of **elapsed time, regardless of observed motion state**. 20 m/s is 72 km/h,
a truck on a road, applied equally to an entrenched Shilka. 30 s unseen is a ±600 m disc. The
user's sentence replaces it with a per-classification rate, and `object_model.profile_for` already
carries per-type data.

### Measured spacing, which is the number the parked decision was waiting for

`plans/contact-duplication-ambiguity-runaway/debug.md` escalated the gate-sizing trade-off to
Architect and said picking a value *"requires knowing what real DCS mission object spacing and
naked-eye range distributions actually look like, not just a code read."* Reduced from this
sortie's belief-truth log (deduplicated by `object_id` — the raw log double-counts, which is the
churn itself; 1,200 polls, median 5 distinct tracked objects, max 69):

| nearest-neighbour spacing, distinct objects | |
|---|---|
| p05 | 2 m |
| p25 | 6 m |
| **median** | **16 m** |
| p75 | 55 m |
| p95 | 342 m |

Flat per-object, by range band, the median sits at 11–23 m everywhere.

**That settles the trade-off by showing it has no solution at the unit grain.** A gate that
tolerates 30 s of motion is ±600 m; the objects it must separate are 16 m apart. No single radius
is both. So per-unit identity is **not recoverable from position** at real DCS spacing — which is
not a tuning failure, it is the same fact the group contact model already established in the
*resolution* domain (twelve units at 9 km are one mark). The user's group-level model is not merely
more human, it is the only grain the data supports.

At the group grain the numbers invert and become workable — single-link clustering of the same
data:

| link | cluster-to-cluster nearest separation | |
|---|---|---|
| 100 m | p05 124 m · p25 168 m · **median 236 m** · p75 378 m |
| 250 m | p05 328 m · p25 389 m · **median 625 m** · p75 962 m |

### Why "never a guessed merge" needs revisiting, and it is a premise failure not a wrong call

`ingest`'s "two or more plausible candidates → found a new contact" is a deliberate, named
invariant (`plans/pb2-contact-memory/plan.md` Stage 1, "never a guessed merge"). The user supplies
the density assumption it was silently resting on:

> *"DCS missions are not usually saturated with units, like real life frontlines would be. DCS just
> cannot handle so many units. So a group that leaves the road and heads off is likely the same one,
> if the group composition matches."*

In a saturated world, refusing to guess a merge is right: the alternative explanation (a different
unit) is cheap. In a sparse world it is backwards — ambiguity should resolve toward *the group I
already know*, because there usually is no second candidate group. The invariant is not wrong; its
premise is, and nothing wrote the premise down.

### Road-following, in the user's own terms

> *"Units traveling on a road typically follow that road. That is the whole point of roads… They may
> turn at intersecions naturally and I typically cannot predict where and when they turn, unless I
> know the route or destination. When attacked DCS units spread and take cover, so they move a bit
> off the road and stop. Then after a certain time of not being attacked they resume their route on
> the road. Units can, of course, also leave the road and drive through terrain, though that's less
> usual. Direction matters too, units typically do not turn around and head back, not in DCS (real
> life is very different, but DCS follows routes)."*

Design consequences, each cheap because world-model already holds the data:

- The search region for a remembered moving group is a **directional corridor along the road
  graph**, branching at junctions (`M10` junction detection exists), not a disc.
- **Direction is monotone** — a reversal is evidence against identity, since DCS units follow routes.
- **"Spread off-road and stopped" is a recognised state**, the signature of having been attacked,
  and it should read as the same group displaced rather than new units. It also expires: they resume.
- Off-road is allowed but less likely; composition match outweighs it.

---

## 3. Persistent spoken group identity, and the error the user prefers

> *"persistent, spoken group identity. In most cases units do not actively move, so it'll be mostly
> right by default. If a new group is mistakes as existing group, it's the unusual occurence and I
> can live with that easier than new group beliefs popping up all the time."*

**This is the decision the ambiguity policy needed, stated as an asymmetry rather than a
threshold**, and it is the opposite of the current invariant's bias:

| error | current policy | user's preference |
|---|---|---|
| a new group reported as an existing one (false continuity) | avoided at all costs | **acceptable, rare** |
| an existing group re-founded as new (duplicate beliefs) | accepted as the safe default | **the one to eliminate** |

The justification is the same sparsity fact as above plus a second one: *most units do not actively
move*, so continuity is right by default and the flat 20 m/s inflation is modelling a world that
mostly is not happening.

So `ingest`'s "two or more plausible candidates → found a new contact" inverts: ambiguity resolves
toward the remembered group, and founding a new one requires positive evidence — the user's own
list in §2 (not *with* the group, count exceeds memory, composition differs, displacement
implausible for the type, different kind of group).

Petrovich may therefore speak of a group as the same group across a repositioning — *"that column,
now 2 o'clock, three kilometres, still moving north on the road"* — which is the pilot-facing payoff
of the whole change.

---

## 4. The memory layer is the home for long-horizon re-identification (BL-8 gets its first real spec)

> *"We could use the memory layer for exactly this sort of things. Units that have been detected go
> to memory (group, where, movement, etc) and when they have not been visible for a (long) while the
> memory layer data can be used to determine if these are the ones we saw 10 mins ago. Or expect
> that on the other side of the ridge there's a group of units, we better not go there."*

This draws the seam for the §2/§3 work: **short-horizon continuity stays in the belief layer**
(seconds to a minute — the pop-up-from-behind-a-ridge case), **long-horizon re-identification and
spatial expectation belong to BL-8**. The second sentence is the more important half and is a
*new* capability, not a restatement: a remembered group becomes an expectation about a place the
aircraft has not yet looked at — *"we better not go there"* — which is route-level advice, not a
callout. `BL-8` has been "deliberately last, gated on BL-2..BL-7 real-flight experience"; this is
that experience arriving, and it is the first consumer-driven requirement the milestone has had.

## 5. `GATE_GROWTH_RATE_MPS = 20.0` is far too fast, by the pilot's own reckoning

> *"20 m/s is *fast* for most units. Armor can barely make that at full speed. Expect slower."*

72 km/h. Confirms the per-classification rate from §2 and sets its scale: the default belongs well
below 20 m/s, with entrenched classes at ~0.

## 6. The "7 o'clock" callout is not late — it is a no-omniscience violation, and it is measured

> *"Some callouts have been late. Like unit 7 o'clock, which is late by definition because Petrovich
> can't even see 7 o'clock."*

The pilot read it as lateness. The log says it is worse than that. Of 357 spoken lines in the
2026-10-05 sortie, broken down by the clock hour spoken:

| hour | lines | body azimuth | `_CO_PILOT_MASK.rear_cutoff_deg = 130.0` says |
|---|---|---|---|
| 4 | 6 | 120° | visible |
| **5** | **5** | 150° | **masked** |
| **6** | **4** | 180° | **masked** |
| **7** | **11** | 150° | **masked** |
| 8 | 11 | 120° | visible |

**20 lines about hours the project's own cockpit mask declares unviewable**, and they carry
classification, not just position — *"unit 7 o'clock, very close is Tigr armored vehicle"* spoken
while the gaze was at 11 o'clock, *"unit 6 o'clock, very close is infantry"* while gazing 12.

This is the same class as the defect fixed on 2026-09-27, when "Getting closer" was being said about
contacts behind the cockpit mask, two of them dead astern. That fix put crossing and motion callouts
behind an observability gate (FOV + cockpit mask + LOS, with a grace window). **Classification and
group-disclosure lines were evidently not put behind it.** So the gate exists, is correct, and is
applied to two callout kinds out of several.

(Caveat worth keeping: the spoken hour derives from *believed* position, which lags, so a contact
genuinely at 8:30 could be rendered "8 o'clock". Hours 6 and 7 are far inside the cutoff and cannot
be explained that way.)

## 7. The real pilot-facing bottleneck is the query path, not detection

> *"I did see a lot of unknown detected units in the degub ASCII graph, but getting usefull reports
> was difficult. Also because "report" comamnds did either not STT correctly or the command logic
> did not exits."*

Detection is working — he can see in the debug view that Petrovich knows things — and he cannot get
them out of him. That reframes the priority: `BL-B28` (`report right` → `say_again` while
`report left` → `confirm`) and the missing `describe` synonym are not small vocabulary chores, they
are the only channel to everything the belief layer holds.

**Requested command grammar, in the user's own words:**

> *"I'd need way to say "report/describe 2 o'clock close" of more generally "report/describe <what>
> <where> <how far>" where shat can be "group" or classification etc, where typically clock hand,
> but could be north/etc or even south of village, and how far would be near (<2km)/medium distance
> (2-5km)/far(5+km)."*

| slot | values |
|---|---|
| verb | `report` / `describe` (synonyms) |
| **what** | `group`, or a classification (armor, trucks, air defence, infantry…) |
| **where** | clock hour *typically*; also cardinal (`north`); also landmark-relative (`south of <village>`) |
| **how far** | `near` < 2 km · `medium distance` 2–5 km · `far` 5 km+ |

Every slot optional, by the shape of the example (`"report 2 o'clock close"` has no *what*).
Landmark-relative `where` needs world-model place names and therefore runs into `WM-B1`'s
Latin-script problem (DCS cannot render non-Latin-1, so Arabic names reach the cockpit as blanks) —
`WM-B1` is already open and already forcing a rebuild.
