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

### D2. It is a phase cycle, not an interrupt

**This is the decision the user's clarification forced, and it simplifies everything downstream:**

> when scan detects target, do not immediately raise binoculars. First complete the current sector
> naked eye scan to get as many naked eye detections as possible, then raise binoculars to take a
> closer look.

So perception alternates **phases** rather than being interrupted:

- **Scan phase** — the naked-eye plan runs to *completion*: the full 16 s o'clock cycle when
  free-scanning, or one complete pass of a commanded sector. Detections accumulate; nothing is
  glassed yet.
- **Glass phase** — entered only at a phase boundary, and only if there is work for it: contacts
  queued by D1's window, or a commanded sector to search (D6). It ends on its own stop conditions
  and hands back to the scan phase.

**The lockout stops being a rule and becomes structural.** *"at least one naked eye scan before the
next binocular usage"* is true by construction, because a glass phase can only be entered from the
end of a scan phase. There is no timer to enforce and no way to express the illegal state.

**And its length follows the scan mode, which is what the user asked for** (*"depends on scan mode.
Full scan takes time, sector or o'clock scan is faster, allowing more frequent binocular use"*). A
free scan cycles in 16 s, so binoculars come round every 16 s plus the look. A commanded o'clock
sector cycles far faster, so they come round more often. **Nothing computes this** — it is the
period of whatever plan is active, and it falls out for free.

### D2a. One look serves everything inside the field of view

> Special case, if binocular FOV sees multiple units at once, they all get the benefit of binocular
> looking at them.

This needs no special case at all, which is worth stating so nobody builds one: `check_visibility`
is evaluated per candidate against the current optic, so **every contact inside the 8.5° cone
during a glass phase is already evaluated at the binocular tier.** The "special case" is the
natural consequence of the optic being a property of the look rather than of a target. It gets a
test rather than a mechanism, because the risk is a future refactor quietly making the optic
per-target.

It does change how a look is *chosen*: pointing at the direction that puts the most unresolved
contacts inside one cone is strictly better than pointing at the nearest one. Stage 2 picks the
direction, not the contact.

### D2b. A look ends when there is nothing left to learn from it

Max **6 s** (user), but it ends early on the condition the user stated, which is sharper than a
timer:

> - unit(s) looked at gained more detailed identification
>   - no other units in FOV at distance where more detailed identification can be expected

Both halves are one predicate: **stop when no contact inside the field of view is still within
D1's improvement window** — each has either improved to type, or sits outside the band where the
binocular could have helped. The 6 s cap then only fires when recognition simply is not happening,
which is exactly the case where continuing to stare is wasted.

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

The user's worked example is the specification:

> command "scan 12 o'clock" -> naked eye scan 12 o'clock sector -> binocular scan of 12 o'clock
> sector from distance where naked eye cannot see to as high as there is ground ahead. Depending on
> binocular FOV vs sector width, do S shaped scan from close to far. This should be fast, not
> dwelling on any spot, but rather trying to *detect* targets. Detected targets then get the dwell
> behaviour.

Four properties, each with a consequence:

- **It sweeps, it does not fixate.** Short steps, no dwell. The act is detection, and what it finds
  is handed to D2b's dwell behaviour on a later glass phase — so search and identification compose
  rather than competing for the same budget.
- **An S-shaped raster, close to far.** Azimuth sweeps alternating direction, stepping outward in
  range. **Range maps to elevation**: further out is nearer the horizon, so "from close to far" and
  "as high as there is ground ahead" are the same axis. The far limit is where the ground stops
  being visible, not an arbitrary distance.
- **Starting where the naked eye stops.** The near band is already covered by the scan phase that
  alternates with this one, so sweeping it again spends the budget re-covering known ground.
- **No sky**, unless the player asked for it. Elevation clamps at the horizon.

**Cost, stated because it is the thing most likely to feel wrong:** a 30° sector against 8.5° of
binocular width is ~4 azimuth steps; three range bands makes ~12 steps. At a short step time that
is several seconds — reasonable. **A commanded `full` (180°) sector is ~21 steps per band and is
not reasonable**; Stage 3 has to either decline a binocular search that wide or cover it coarsely,
and that is a real decision rather than an oversight to discover in the air.

### D7. The overlay shows it; he does not announce it

**No spoken announcement** (user, asked directly). The 2C sortie's lesson — *"very difficult to
judge when I don't visually see where Petrovich is looking"* — is answered by the overlay, which
already shows the gaze cone and gains the optic. Adding a line of speech for every raise would buy
the same information at the cost of chatter on a channel one person occupies at a time.

This does leave a real property unannounced: **while glassed, his silence means something
different** — he is not failing to see, he is looking somewhere very narrow. The overlay carries
that, and whether it needs saying out loud is a judgement for the sortie rather than a decision to
guess at now.

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

## Questions resolved before building (user, 2026-09-23)

1. **Lockout length** — *"depends on scan mode"*. Resolved structurally by D2: the lockout is one
   complete pass of whatever plan is active, so a free scan gives 16 s between looks and a
   commanded sector gives much less. No constant.
2. **Announcement** — no (D7).
3. **Look duration** — 6 s cap, with D2b's earlier stop condition doing most of the work.
4. **Search duration** — one complete area scan of the commanded sector (D6).

## Risks

- **The budget makes him worse at his job, correctly.** Every second glassed is a second not
  scanning. If the sortie says he misses things he used to catch, that is the model working, and
  the fix is the budget rather than the mechanism.
- **The constants are uncalibrated** — dwell, lockout, smoothness threshold, retry fraction. Same
  debt class as every other perception constant before its first sortie; stated rather than hidden.
- **Stage 3 is the speculative one.** Alternating a raster search with a scan is the part with no
  measurement behind it at all, and it is deliberately last so Stage 2 can be flown alone.
