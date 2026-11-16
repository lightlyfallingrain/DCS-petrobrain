# BL-B104 — behaviour alignment

## Goal check — 2026-10-30

**Verdict:** CONCERNS

### Why

Whatever Petrovich does with a ground contact he is not looking at right now — point the 9K113 at
it, guide the pilot onto it, call it out, recognise it when he sees it again — has to come from a
believed position that stays near the real unit while the aircraft climbs, descends and closes.
Today it does not: the belief sits at the aircraft's own altitude at the last look and at a guessed
range, so it drifts away exactly during an attack run, and the run's whole point — *"he sees it AND
tracks it with the 9K113"* (§4) — fails. Asked once more: the purpose is that the pilot is put onto
the real target and Petrovich's sight finds it, not a more correct number for its own sake.

### Player expectations

- **E1** — On an `engage … missiles` run against a ground contact first seen from a different
  altitude, the 9K113 mark goes **down toward the target**, near enough that the sight acquires it
  (directly or with the decided bearing-line depression search), and Petrovich says *"Tracking."*
  It never parks on the ASP-17's top edge or the +20° gimbal stop for a target below the aircraft.
- **E2** — In the debug POV / top-down view, the believed marker for a ground contact sits **on the
  ground at or near the unit**, not floating at the aircraft's altitude; during a run the sight's
  view stays on that area rather than swinging to the side.
- **E3** — Attack-run direction words for a remembered ground target **converge on the real target**
  as the aircraft closes — no late swing *"right and steeply down"* away from it (run 2).
- **E4** — Spoken range for a ground contact ("…two kilometres") is **never worse than today** in the
  normal envelope (50–800 m AGL, a few km), and gets better the closer he is and the more he looks
  (user: *"The closer the target is, the more we look at it, the better we can tell"*).
- **E5** — A ground unit seen again after a large altitude change is **the same contact**, not a new
  one called out twice.
- **E6** — Helicopters, aircraft and weapons in the air behave **exactly as before**.
- **E7** — No omniscience: a ground unit seen once, far away, is still believed **plausibly wrong**,
  and a heavily-observed one still never converges exactly on truth.

### Open assumptions

- **How large the depression error is** — serves the why: an error at the scale of *looking straight
  at it*, small enough that the ground intersection beats today's range guess across the envelope;
  would not: reusing `BEARING_SIGMA_DEG = 3.0` (the *stating a bearing* error), which makes ranges
  worse than today across most of the envelope (Finding 2); nor `RELATIVE_DIRECTION_SIGMA_DEG = 0.0`,
  which makes the belief exact truth (Finding 3).
- **Whether range is still used at all** — serves the why: depression and the range estimate both
  constrain the point, each weighted by how good it is at that geometry (steep → depression wins,
  shallow → range wins); would not: "range not guessed" taken literally, which leaves no answer at
  shallow or upward look angles.
- **What "a ground unit" is** — serves the why: *whatever is on the ground now* (user's rule is
  AGL-based: *"Any unit at AGL > 0 is aircraft or weapon in the air"*); would not: DCS unit category
  alone, which puts a landed helicopter or parked jet on the air path (Finding 4).
- **Whose ground height a group contact takes** — serves the why: for the sight and the run, the one
  unit being engaged; would not: an average or centroid height of the group (calibration case 3).
- **When the aircraft is level with or below the unit** (NOE in hills, target on a slope above) —
  serves the why: fall back to the range estimate; would not: a ray that never meets the unit's
  height, or meets it far away.

### Findings

1. **Two fixes with different certainty are bundled; only the altitude half is settled** — lens:
   Purpose
   - Assumption: altitude and range are one change.
   - In the sim / the logs: run 1 is purely altitude (+72° goal elevation vs −84° truth). Run 2 is
     420 m of altitude error plus 700 m of range error with the **bearing correct**. Fixing altitude
     alone cures run 1 and most of run 2's depression error; the remaining run-2 miss is a
     depression error on a good bearing, which is exactly what the already-decided bearing-line
     depression search sweeps.
   - The pilot would see: E1–E3 delivered by the altitude half plus the decided search; the range
     half pays off mainly in E4/E5 (spoken range, recognition).
   - Grounded in: §4 run traces; the user's *"ground units are on the ground … we know for certain
     that the unit is at AGL 0"*.
   - Suggests: treat "ground contact at its own ground height" as the certain core; settle the range
     half on its own terms (Questions 1–2) rather than let it gate the core.

2. **At the project's own bearing error, depression ranging is worse than today across most of the
   envelope** — lens: The envelope
   - Assumption: depression error "in the same range as the azimuth angular error" means
     `BEARING_SIGMA_DEG = 3.0`.
   - Arithmetic (flat ground between, ownship height above the unit = h): the ground point's range
     from a ±1σ depression error —

     | h above unit | true range | depression | ±0.5° | ±1° | ±3° | today ±17% |
     |---|---|---|---|---|---|---|
     | 100 m | 2 km | 2.9° | 1.7–2.4 km | 1.5–3.1 | 1.0–**no ground hit** | 1.7–2.3 |
     | 300 m | 3 km | 5.7° | 2.8–3.3 | 2.5–3.6 | 2.0–6.3 | 2.5–3.5 |
     | 420 m (run 2) | 5 km | 4.8° | 4.5–5.6 | 4.1–6.3 | 3.1–13 | 4.2–5.9 |
     | 800 m | 2 km | 21.8° | 2.0–2.1 | 1.9–2.1 | 1.7–2.3 | 1.7–2.3 |

     At 3° it only beats today's range guess above ~18° depression (close and high); below that it
     is worse, and at 100 m AGL beyond 2 km a fifth to a quarter of looks put the ray above the horizon. At ~0.5–1° it beats
     today almost everywhere except very low and far.
   - The pilot would see: with 3°, ranges and run guidance from far looks **worse** than now — E4
     violated, and run 2 would have been believed anywhere from 3 to 13 km.
   - Grounded in: `perception/estimation.py` constants (user-approved 3.0, Decision 3); operating
     envelope 50–800 m AGL (user memory).
   - Suggests: the depression error is the decision that makes or breaks this item — Question 1.

3. **The no-omniscience fence depends on that same number** — lens: Bounded knowledge
   - Assumption: "angular error stays the percept's own".
   - In the code: the direction channel a look already carries is the ownship-relative one, and its
     error is `RELATIVE_DIRECTION_SIGMA_DEG = 0.0` by the user's §20 (*"Relative direction while he's
     looking at it -> exact"*) — for guidance. Exact direction ∩ the unit's own DCS height is the
     unit's true position.
   - The pilot would see: Petrovich knowing exactly where a unit is from one glance at 6 km — E7
     violated, silently.
   - Grounded in: §18/§20 of `docs/acceptance/2026-10-14-attack-run-guidance-direction.md` (two
     mechanisms: world-anchored belief carries error, relative observation is exact); the per-object
     systematic bias that must never average out.
   - Suggests: the world-anchored belief needs its own non-zero depression error and keeps the
     systematic bias; it must not borrow the relative channel's zero.

4. **"Ground vs air by unit category" departs from the user's own rule** — lens: World truth
   - Assumption: category decides.
   - In the sim: a landed helicopter at an FARP or an aircraft parked on an airfield is on the ground
     at AGL 0 but is an air category; a hovering helicopter at 10 m is in the air. What a crewman
     perceives is *on the ground or in the air*, not the type.
   - The pilot would see: a parked jet on an airfield strike believed at the aircraft's altitude —
     run 1's bug again, for that target class.
   - Grounded in: user, *"Any unit at AGL > 0 is aircraft or weapon in the air"* — an AGL rule.
   - Suggests: Question 2.

5. **The world-elevation exclusion and unit-data height are already consistent with earlier
   decisions** — lens: World truth (no concern)
   - Unit data for height was settled on 2026-10-14 (*"No world elevation necessary since unit data
     has elevation"*); "no world-model elevation grid" matches the 2026-10-05 "testing only"
     direction. A unit on a slope or in a valley gets its own height, which is the right answer the
     flat projection could never give.

Vignette walked (non-obvious case): hovering at 40 m AGL behind a crest, a BMP on a hillside 2.5 km
away **level with** the aircraft. Depression ≈ 0°; the direction ray meets the unit's height
nowhere useful. Unless range still has a say, he has no position for a unit he can plainly see —
the open assumption on fallback.

### Questions for the user

1. When Petrovich places a ground unit he has seen, how precisely does he judge the *down-angle* to
   it — about as well as he can point at it while looking (well under a degree), or as coarsely as
   he states a bearing (~3°, which at low level is worse than today's range guess)?
2. Should depression replace the range estimate, or should both count — depression winning close
   and steep, range winning far and shallow?
3. A helicopter landed at a FARP or a jet parked on an airfield: on the ground (AGL 0) for this rule?
4. Ships: same rule (on the surface, at sea level)? — one word is enough.
