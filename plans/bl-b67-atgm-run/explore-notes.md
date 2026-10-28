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

## 2026-10-26 — fourth round: command form, out of missiles, end of run

> *"1 - missiles = ATGM"*

`engage <what> <where> missiles` starts the **ATGM run**. Without a weapon word, or with
`guns`/`rockets`, it is the `BL-14` guns/rockets run, which never touches the selector. (The
weapon slot is already parsed by audio-adapter, `parse_weapon`; body-layer does not read it yet.)

> *"2 - "no more missiles". Keep tracking for guns/rockets."*

Last missile gone: Petrovich says **"No more missiles"** and **keeps tracking** so a guns/rockets
attack can follow. The run does not end.

> *"3 - OBSERV stays on unless commanded off."*

Ending the run (`disengage`) turns the missile selector OFF and **leaves OBSERV on**. OBSERV goes
off only on command.

### Mi-24P quirk: OBSERV and the cannon are mutually exclusive

> *"One Mi-24P quirk to note down. OBSERV ON and the Hind's 30 mm cannon being selected as weapon
> (pilot weapon selector) are *mutually exclusive*. If cannon is selected, OBSERV will not turn
> on."*

With the cannon selected on the **pilot's** weapon selector, OBSERV cannot be turned on. This
reaches beyond this entry: `[[BL-B66]]`/`[[BL-B80]]`'s OBSERV-on path will see the switch refused
(the observed arg 886 stays off) whenever the pilot has the cannon selected. Recorded also in
`docs/acceptance/2026-10-17-9k113-procedures-direction.md`, addendum 2026-10-26.

## 2026-10-26 — fifth round: the quirk's consequences

Asked (1) what Petrovich says when OBSERV is refused because the cannon is selected — he sees only
arg 886 staying off, not the pilot's selector — and whether an `engage … missiles` run then waits or
fails; (2) whether selecting the cannon while OBSERV is on drops OBSERV.

> *"1 - defer, I don't know yet"*

**Deferred, undecided.** No callout and no wait/fail behaviour chosen for an OBSERV refusal. The plan
must not invent one.

> *"2 - I believe DCS drops OBSERV OFF then"*

**Believed, not verified:** selecting the cannon with OBSERV on makes DCS turn OBSERV off. If true,
the existing OBSERV on→off edge handling (`fix/observ-off-axis-zero`: zero the AI axis once,
whoever caused the edge) already covers it, and Petrovich's OBSERV state has to follow the
observed arg 886 rather than his own command (the gap `[[BL-B66]]` carried into `[[BL-B80]]`).
**Wants a flight check.**

## State at end of 2026-10-26

Behaviour for the run is settled except for the deferred OBSERV-refusal response. Still owed:

- **User:** sim names/args for the extra readers ("some others too"), the **pylon selector knob**
  (arg and position values) and the **launch button**.
- **Desk:** how the loadout count is read (Export API or arg) and how the launched missile's own
  object is identified for impact detection.
- **Flight:** `[[BL-B80]]` Flight A (`docs/acceptance/2026-10-22-bl-b80-v2-flight-a.md`) before the
  plan — the run rests on the pointing chain being accurate; plus the cannon→OBSERV-off belief above.

## 2026-10-29 — sixth round: the owed args, and how impact finds its missile

Answers to the "User" and "Desk" items above.

### Pylon selector

> *"pylon selector know is probably `SHSCHO-KNOB-PTR` from
> @body-layer/config/sequences/mi-24p/switch-reference.md. step 0 is off, steps 1-8 are the
> pylons."*

`switch-reference.md` row: `SHSCHO-KNOB-PTR`, "Select Station", operator, `multiposition_switch`,
cmd `[3038]`, arg `[963]`, values *"0 to 0.8 (9 steps)"*. So step *n* = value
`n × 0.1`, step 0 = OFF, steps 1–8 = pylons. **"Probably"** is the user's word — the knob's
identity is believed, not yet seen moving in the sim; which step is which physical pylon is not
stated.

### Launch button

> *"launch button for copilot is OP-STICK-RS-PTR and STICK-RS-PTR for pilot"*

| name | seat | shape | cmd | arg |
|---|---|---|---|---|
| `OP-STICK-RS-PTR` | operator (explicit) | `default_button`, 0/1 momentary | 3021 | 187 |
| `STICK-RS-PTR` | pilot (**defaulted**) | `default_button`, 0/1 momentary | 3001 | 741 |

Launch detection reads the **pilot's** button (arg 741) — the player flies the pilot seat and
Petrovich operates the other one (round 1's "pilot pressing weapon launch button"). Two notes for
the plan, not user questions: `switch-reference.md` marks 741's seat as *defaulted*, not explicit,
so the user's naming is what settles it; and a momentary button read at the export tick can be
missed by a short tap, so whether a 5 Hz continuous poll is enough is a design question.

### Loadout count

> *"how we read loadout - unknown, but DCS will that that somehow"*

Unknown; desk recon owed (Export API — e.g. a payload/weapons getter — or a cockpit arg).

### The launched missile's object

> *"launched missiles object id - there was an earliear investigation of can we detect tracers
> that found out that fired missile becomes it's own DCS object, and so has id. We know the
> missile type we carry and can filter world object by that when launch button is pressed."*

The investigation is `aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md`,
"PROBE RESULTS, 2026-09-25": the player's own S-8 rockets appeared in `LoGetWorldObjects` as new
`C_8` objects at the poll they were fired, and the count settled back; gun rounds never appeared.
That was measured for **rockets**, not ATGMs — a 9M114 appearing the same way is the expected
case, not yet observed, and its object `Name` is unknown. Design as the user states it: on launch
(button + loadout −1), take the new world object whose type matches the carried missile; impact =
that object leaving the list (round 2).
