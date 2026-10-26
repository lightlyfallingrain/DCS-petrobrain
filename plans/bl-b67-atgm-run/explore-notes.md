# BL-B67 — ATGM attack run: explore notes

Started 2026-10-26. Captured verbatim as the answers arrived, before any design. Spec stays
`docs/concept/9K113.md` + `docs/acceptance/2026-10-15-9k113-sight-direction.md` §5; entry
`body-layer/ROADMAP/BL-B67.md`.

## 2026-10-26 — first round of answers

Asked: what the entry's open items still need (elevation/selection, launch, impact, damage,
missile data, readbacks, angle error).

### Launch detection

> *"human would hear and feel it, we approximate it by a) pilot pressing weapon launch button AND
> b) aircraft load out -1 missile. Both needed to confirm launch. Both needed to that jettison does
> not count as launch."*

So launch = **conjunction** of (a) the pilot's weapon-release input and (b) the loadout dropping by
one missile. Neither alone counts. The conjunction exists so that a **jettison** (loadout drops, no
release button) is not read as a launch.

### Impact detection

> *"impact: that weapon that launched gets its own DCS id. It then vanishes at impact."*

So impact = the launched weapon's own DCS object disappearing. Open for design/recon: how that id is
obtained and associated with this launch, and whether "vanishes" is distinguishable from leaving the
channel's view (out of range, guidance-wire break) — not asked yet.

### Damage channel

> *"damage channel as later stage"*

Hit/damage/fire reporting is a later stage of this entry, not the first build.

### Missile speeds

> *"missile speeds, leave it, Wikipedia is good enough approximation"*

**Supersedes** the entry's caution that `db_weapons*.lua` must be read before the numbers reach a
callout. Wikipedia figures (Shturm 345 m/s, 400–5,000 m; Ataka 400 m/s avg, 400–6,000 m) are
accepted as the approximation. No file read owed.

### Readbacks

> *"tags: 962, 673 need readers. And some others too."*

Arg 962 (launch permission lamp) and arg 673 (weapons safety bar) both need readers. "Some others
too" — which ones is **not yet stated**; to ask.

### Questions the user asked back

> *"elevation, what exactly is the problem here?"*
> *"angle error: explain please"*

Answered in conversation 2026-10-26; the answers and his response go below.

## 2026-10-26 — second round

Context given: `BL-14`'s `select`/`step` order candidates by bearing and range only
(`belief/crew_console.py` `_step_candidates`); elevation is used only in guidance, which this run
drops (azimuth-only). On angle error: the map channel carries `BEARING_SIGMA_DEG = 3.0`, the
look-at-it channel `RELATIVE_DIRECTION_SIGMA_DEG = 0.0`; any non-zero tracking error lands on the
target, since the missile flies down the line of sight.

> *"Elevation - drop"*

The entry's "target selection is now harder" section is **struck**: there is no elevation problem
for selection.

> *"Angle error - 0"*

`RELATIVE_DIRECTION_SIGMA_DEG` stays `0.0` for the ATGM run. `BL-B62`'s "non-zero before a second
consumer" note does not apply to this consumer.

> *"Cluster: ATGM attack run is *always* at *single* target. Never a cluster. This is noted down
> somewhere already."*

Already recorded for `BL-14`: `docs/acceptance/2026-10-14-attack-run-guidance-direction.md` §25
(group-as-target dropped, not deferred). **Design consequence, not a user question:** the sight must
aim at the one selected unit's position, not at a cluster centroid that may average several units —
at 3.5 km, 0.02° is ~1.2 m, so a two-vehicle centroid misses. The plan has to show how the aim
point is a single unit.

> *"1 - I have to check the names in sim, will provide later."*

The "some others too" readback args are **owed by the user**, after checking in the sim.

> *"2 - yes, any impact, missile dropping off the DCS unit list. Hind's missiles are radio guided
> BTW."*

Impact = the launched missile's object leaving the DCS object list, **for any reason** — target,
terrain, anything. No distinction. **Correction:** the missiles are **radio-guided**, not
wire-guided; there is no guidance wire to break (the question had assumed one).

## 2026-10-26 — third round: at and after launch

Shown a mock run (readback → "Observ on, wait" → arm + pylon → "Out of range" → guidance →
"In range" → "Lined up" → launch → "Shturm, 12 seconds" → silent tracking → "Impact" → reset →
???) and asked four questions.

> *"1 - keep tracking and select next missile in preparation for another attack"*

**Impact does not end the run.** Petrovich keeps the sight on the target and selects the next
missile, ready for another launch. The run ends on the pilot's command (`disengage`).

> *"2 - yes. End of attack run sets missile selector off. Only select missile when ATGM attack run
> is commanded, for guns/rockets it stays at off position."*

- After each launch, Petrovich turns the pylon knob to the next missile-present pylon himself.
- **End of the ATGM run turns the missile selector to OFF.**
- **The selector is touched only for an ATGM run.** A guns/rockets run (`BL-14`) leaves it at OFF.

> *"3 - silence"*

Missile in flight: **silence**. No warning about the ±60° azimuth limit either.

> *"4 - just track"*

Launch while out of range or inside 400 m: **say nothing extra, just track.**
