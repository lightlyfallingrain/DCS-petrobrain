# Binoculars: raise to identify, lower and keep scanning

## Goal

Petrovich scans with the naked eye, raises binoculars when a closer look would actually tell him
something, and lowers them again — paying the real cost of being nearly blind while glassed.

User direction, 2026-09-23 (the whole brief, quoted because every decision below traces to it):

> - what triggers binoculars: detection -> raise to classify -> lower and keep scanning.
>   - given believed class, at distance where binoculars would identify type, raise them -> then
>     continue naked eye scan
>     - if ID failed, try again when we get closer
>   - given a command to scan a narrow area (o'clock) or certain location, alternate between naked
>     eye scan and binocular scan of that region.
>     - binocular scan should use a pattern given limited FOV. Do not scan at sky unless instructed
>       by player. Limit scan beyond naked eye detection threshold, unless classifying/identifying a
>       detected target.
> - cost
>   - that is the point, yes. Binocular usage must have time limit, then return and do at least one
>     naked eye scan before next binocular usage.
> - new command from player lowers binoculars
> - jittery flying and hard manouvering lowers binoculars, they are useless unless the flight is
>   fairly smooth

---

## What already exists, and what is actually missing

**The binocular is fully built and completely unreachable.** `perception/optics.py`'s
`BINOCULAR_OPTIC` carries calibrated per-tier multipliers (2.42 presence / 3.50 class / 3.00 type,
BTR-60-derived), a real 4.25° field-of-view half-angle, and a stabilisation penalty. It is tested.
And **`check_visibility` is called in exactly one place** (`naked_eye_source.py:475`) **which never
passes `optic` at all**, so the unaided default is the only path any real poll has ever taken. A
grep for `optic=` across `body-layer/src/` returns nothing.

So this milestone adds no optical model. It adds the **decision**, and that decision is the same
hole as two other open items:

- `Optic.peripheral` is wired with no triggers (standing exposure since 2C).
- The 2C sortie's *"flying so close by a unit that I could clearly identify it, brought no
  identification"*.

All three are the same missing thing: **nothing can currently redirect the scan based on what was
seen.** Petrovich looks where he is told and reports what he sees; he cannot decide to look harder.

---

## The architectural constraint that shapes everything

**`perception` must not import `belief`** (`perception/source.py`'s own module docstring), and the
binocular decision reads beliefs — what is detected, at what class, at what range. `gaze.py` already
resolved this exact tension and its resolution is reused verbatim:

> Belief owns the *intent*; `logger.py`'s poll loop reads that intent each tick and hands perception
> a frozen `Gaze`; perception owns the *act* of filtering against it.

So: **`belief/optic_policy.py` decides; `perception` receives a frozen `Optic` beside the frozen
`Gaze`.** No import direction is violated, and the decision stays a **pure function of its inputs**
— which is what keeps replay deterministic, the property 2C's `gaze_at` was built around.

---

## Decisions

### D1. The raise window is computed from the existing calibration, not a new constant

*"at distance where binoculars would identify type"* is exactly computable. For a contact of
believed class, with `distinctiveness` and the calibrated tier bases already in `visibility.py`:

```
unaided_type_range  = TYPE_BASE  * distinctiveness * 1.00
binocular_type_range = TYPE_BASE * distinctiveness * 3.00
```

**Raise only when `unaided_type_range < slant_range <= binocular_type_range`.** Below the lower
bound the naked eye will identify it anyway on the next dwell — glassing there spends the budget to
learn nothing. Above the upper bound the binoculars cannot identify it either. The window is the
band where the instrument makes the difference, and it falls out of numbers already measured rather
than a tuned threshold.

**Consequence worth stating:** this is a *type*-tier trigger. A contact already identified to type
is never re-glassed, and a contact too far for even the binocular type tier waits until it closes —
which is also D5's retry rule, for free.

### D2. A budget, and a mandatory naked-eye scan between looks

Binoculars cost near-blindness: a 4.25° half-angle against the naked eye's 15° focus cone, so while
glassed everything outside a narrow tube is unseen. That is the point, and the accounting has to be
real or it is not a cost at all:

- **`BINOCULAR_DWELL_S`** — one look is bounded. It must be long enough for a recognition to be
  plausible and short enough that the scan is not abandoned.
- **Then at least one full free-scan cycle before the next raise** (`SCAN_CYCLE_PERIOD_S`, 16 s).
  This is the *lockout*, and it is deliberately expensive: it means binoculars are used a few times
  a minute, not continuously. See Open Question 1 — the user's phrase was "at least one naked eye
  scan", which could also mean one cone dwell.

### D3. The smoothness gate is about manoeuvring, not vibration

*"jittery flying and hard manouvering lowers binoculars"*. Two different things, and only one is
observable here:

- **Hard manoeuvring is observable.** Body-layer sees `OwnshipState.pitch_deg`/`bank_deg`/
  `heading_true_deg` once per poll, so successive samples give an angular-rate estimate. Sustained
  bank or a fast heading change is catchable.
- **Fine vibration is not.** The poll interval is 1 s by default, which aliases anything faster
  than a couple of hertz. **It is also already priced in**: `BINOCULAR_OPTIC`'s stabilisation
  penalty exists precisely because a helicopter cockpit is never still. Modelling it twice would
  double-count.

So the gate is **"is the aircraft being thrown around"**, computed from the attitude samples body
already has, and the docstring says plainly that it cannot see vibration and why it does not need
to.

### D4. A player command lowers them, unconditionally

Any new command — F10 or voice — lowers the binoculars before it is dispatched. Not a special case
per command: the pilot asking for something is prima facie evidence that what Petrovich is doing
matters less than what was just asked for.

### D5. A failed identification retries on range, not on time

*"if ID failed, try again when we get closer"*. Per-contact state: the range at which the last
attempt was made. A retry is allowed once the contact has closed by a stated fraction. **Not a
timer**, because a contact at constant range has not become more identifiable and re-glassing it
spends the budget on a question already answered.

### D6. Binocular *search* is a different act from binocular *identification*

For a commanded narrow scan, the binoculars sweep rather than fixate, and three rules from the user
apply only here:

- **A raster pattern at the instrument's own width.** 8.5° of full width against a 30° o'clock cone
  is roughly four steps across.
- **No sky.** Elevation is clamped at or below the horizon unless the player explicitly asked
  otherwise. He is looking for ground units.
- **Only beyond the naked eye's own reach.** The near band is already covered by the scan that is
  alternating with this one; pointing the binoculars there spends the budget re-covering it. The
  exception is D1's identification, which is allowed at any range in the window.

### D7. He must say so, and the overlay must show it

The 2C sortie's sharpest lesson was *"very difficult to judge when I don't visually see where
Petrovich is looking"* — and binoculars make that worse, because while glassed **his silence is
meaningful**: he is not failing to see things, he is looking somewhere very specific. The overlay
already shows the gaze cone; it gains the optic. See Open Question 2 on whether he speaks it too.

---

## Stages

**Stage 1 — the optic becomes a resolved per-poll value. Behaviour-preserving.**
`logger._active_gaze` becomes a resolution of `(Gaze, Optic)`; `NakedEyePerceptionSource` carries
the optic and passes it to `check_visibility`; the resolver always answers `UNAIDED_OPTIC`. Nothing
observable changes — the same regression gate 2B used, for the same reason: it proves the plumbing
before any behaviour rides on it. **The trace gains the optic**, so every later stage is legible in
`--detection-trace` rather than inferred.

**Stage 2 — raise to identify.** `belief/optic_policy.py`: the D1 window, the D2 budget and
lockout, the D3 smoothness gate, D4's command interrupt, D5's retry rule. This is the milestone's
substance and it is where the constants that need a sortie are introduced.

**Stage 3 — binocular search within a commanded sector.** D6's raster, sky clamp and far-band
restriction, alternating with the naked-eye scan.

**Stage 4 — sortie.** Whether it *feels* like a crewman using binoculars, and whether the budget
and lockout are anywhere near right. Expect the constants to move once, as they did after every
other perception milestone.

---

## Open questions for the user

1. **How long is the lockout?** *"at least one naked eye scan"* reads most naturally as one full
   16 s cycle — which makes binoculars a few-times-a-minute act. It could equally mean one 2 s cone
   dwell, which would make them nearly continuous. The first is a real cost; the second is barely
   one.

2. **Does he announce it?** *"Taking a closer look, two o'clock."* on raise. It costs chatter and it
   buys the pilot an explanation for why he went quiet — which matters more than usual here,
   because glassed silence is not the same as nothing-to-report.

3. **How long is one look?** Long enough to be plausible, short enough not to abandon the scan.
   This is a feel judgement, not a derivable number.

---

## Risks

- **The budget makes him worse at his job, correctly.** Every second glassed is a second not
  scanning. If the sortie says he misses things he used to catch, that is the model working, and
  the fix is the budget rather than the mechanism.
- **The constants are uncalibrated** — dwell, lockout, smoothness threshold, retry fraction. Same
  debt class as every other perception constant before its first sortie; stated rather than hidden.
- **Stage 3 is the speculative one.** Alternating a raster search with a scan is the part with no
  measurement behind it at all, and it is deliberately last so Stage 2 can be flown alone.
