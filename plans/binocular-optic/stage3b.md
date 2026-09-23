# Stage 3b — a look is a sweep, not a stare

Plan for the Stage 3b entry in `plans/binocular-optic/plan.md`. Read that first; this only
elaborates it, and **corrects one factual claim in it** (see "The tripwire is mislabelled").

---

### Goal

A binocular identification look sweeps the believed bearing's own angular uncertainty instead of
staring at its centre, so a contact known only to be "around two o'clock" is actually found.

---

### The tripwire is mislabelled — read this before anything else

`plan.md` Stage 3b and the `xfail(strict=True)` marker on
`test_mock_flight_chain_single_threaded_reaches_expected_contact_state` both state that the
fixture's four lost observations (36 → 32) come from *aiming a single stare at a quantised believed
bearing*. **That is not what happens in that fixture.** Replayed poll-by-poll with the optic
decision traced:

```
t=20  phase=searching  optic=binocular  az=-11.25  el=-15.57   targets=[CONTACT_1 lvl=type improve=False]
t=25  phase=searching  optic=binocular  az= -3.75  el= -6.57   targets=[CONTACT_1 lvl=type improve=False]
t=50  phase=searching  ... (same two steps)
t=55  phase=searching  ...
t=80  phase=searching  ...
t=85  phase=searching  ...
observations: 32
```

**`OpticPhase.GLASSING` is never entered.** The fixture's only contact is `type`-level from frame 0
(Hybrid founds it immediately), `improvement_window_m` returns `(0.0, 0.0)` for `type`, so
`can_still_improve` is `False` on every poll and no look is ever chosen. The binoculars go up
because the test's permanent `scan_area("ahead")` task makes `_search_sweep` non-empty, so
`decide` falls through to **`SEARCHING`** — Stage 3's raster, not Stage 2's look.

The four lost observations are the four search polls at `t=20, 25, 50, 55` where the naked-eye
channel still held the truck (it drops out at `t=80` anyway, at the cockpit-mask cutoff). They are
lost because the sweep is aimed at the 2333–5647 m search band — 6.6°–15.6° below the horizon at
this fixture's 650 m AGL — while the truck sits at ~1.1 km and ~-10°. The nearest miss is about
1° of angular separation outside the 4.25° cone.

**Consequence: building this stage as briefed will not turn that test green.** The fix and the
tripwire are about different phases. Both problems are real; they are not the same problem. See
"Decisions requiring user input" — this needs settling before the Implementer starts, because the
acceptance criterion currently written into the marker cannot be met by this work.

The rest of this plan designs the look sweep, which is correct and worth building regardless.

---

### Affected Modules / Files

- `body-layer/src/belief/association_over_time.py` — promote the private `_CLOCK_BUCKET_DEG` to a
  public `CLOCK_BUCKET_DEG` (value unchanged). It is already documented there as *the reporting
  vocabulary's* quantisation, which is exactly what the sweep width is. No behaviour change.
- `body-layer/src/belief/optic_policy.py` — the whole of this stage:
  - new `look_sweep(...)`, sibling to `search_pattern` (not a reuse of it — see D2 below);
  - extract the step-centre spacing both now share into one private helper;
  - `decide`'s `GLASSING` branch becomes step-indexed, the way `SEARCHING` already is;
  - `look_is_finished` / `_target_in_current_look` widen from the field of view to the sweep's
    envelope;
  - the attempted-range marking widens to the envelope for the same reason;
  - `MAX_LOOK_S` divides by the derived step count — no new constant.
- `body-layer/tests/test_optic_policy.py` — unit coverage for the sweep, including the tripwire
  this stage actually needs (a class-level contact offset from truth by most of a clock bucket:
  a stare misses, the sweep hits).
- `body-layer/tests/test_mock_flight_chain.py` — the `xfail` marker's *reason text* is wrong and
  must be corrected whatever else is decided. Whether the marker is removed depends on the open
  decision below.
- `body-layer/src/logger.py` — no change expected. `_apply_active_gaze` already rebuilds
  `ScanPlan.fixed_look_at` from whatever direction `decide` returns each poll, so a moving look
  needs nothing new downstream. `ScanPlan.fixed_look_at`'s gaze half-width is
  `FOCUS_CONE_HALF_WIDTH_DEG = 15.0`, which already admits the entire ±15° envelope — only the
  optic cone was ever the narrow thing.

---

### D1. The sweep width is the clock bucket, not `last_position_uncertainty_m`

**Use half the 30° clock bucket (15°), imported from `association_over_time.CLOCK_BUCKET_DEG`.
Do not derive it from `Contact.last_position_uncertainty_m`.** They are not the same figure
arrived at two ways; reading the metres field as a bearing error is a category error of precisely
the class that module's own docstring warns about.

Three independent reasons:

1. **It is a hypot of two different errors.**
   `_naked_eye_uncertainty_m = hypot(range_m · sin(15°), range_bucket_width_m)`. Only the first
   term is angular. Converting the combined radius back to an angle with `asin(u / R)` folds the
   *down-range* bucket width into a *bearing* figure, and overstates it — worse the closer the
   contact is, which is exactly where looks happen:

   | range | true bearing error | `asin(last_position_uncertainty_m / R)` |
   |---|---|---|
   | 300 m | 15.0° | 24.9° |
   | 1000 m | 15.0° | 16.2° |
   | 3000 m | 15.0° | 15.4° |

   Over-sweeping is not free: the step count is `ceil(2U / 8.5°)`, so 24.9° buys a fifth and sixth
   step and cuts the dwell per step from 1.5 s to 1.0 s, to cover ground the belief was never
   uncertain about.

2. **It is isotropic by construction and has thrown away the direction of the error.** It is
   budgeted for a spatial gate — a circle that must *contain* the true position for a merge
   decision. A sweep needs the component perpendicular to the line of sight and nothing else. The
   radius no longer knows which component was which.

3. **On the scope/hybrid channel it is a documented placeholder.**
   `SCOPE_UNCERTAINTY_M = 300.0`, described in its own comment as "not a calibrated value". At
   500 m that is `asin(300/500) = 36.9°` — a seven-step sweep aimed by a number nobody measured.

**What may legitimately be shared is the measurement, not the budget.** "The clock bucket is 30°
wide" is one fact about the reporting vocabulary, and both the gate radius and the sweep width are
honest derivations from it. That is why the change is to expose `CLOCK_BUCKET_DEG` rather than to
re-declare a literal `15.0` in `optic_policy` — a second copy would drift, and the existing
`LookTarget.bearing_uncertainty_deg = 15.0` default is already that second copy.

The width is range-independent, which is correct: the quantisation that causes it is angular.

**Deferred, named rather than built:** a contact whose `last_position` was last set by the
scope/hybrid channel is not clock-quantised at all and deserves a narrower figure. The seam
already exists — `bearing_uncertainty_deg` is a per-`LookTarget` field — and `look_target_for`
can start passing it whenever there is a measured number to pass. 15° is the loosest of the two
channels and therefore the safe floor: over-sweeping costs budget, under-sweeping misses, and
missing is the defect this stage exists to remove.

---

### D2. A new `look_sweep`, not a reuse of `search_pattern`

`search_pattern` is the wrong tool, and forcing it would be the same mistake the gate/clustering
split already cost this codebase once.

- **The two answer different questions.** `search_pattern` covers *unknown* ground between two
  ranges; its vertical axis is a range→depression mapping and its sky clamp is a property of
  looking at ground. A look covers the *known* angular error around one believed direction, at an
  elevation the belief already supplies. Getting `search_pattern` to produce that requires passing
  `near_m = far_m = believed range` and a height, to recover an angle already in hand.
- **Its cap is a search policy.** `MAX_SEARCH_SECTOR_HALF_WIDTH_DEG = 15.0` exists because the user
  said "no wide area binocular scan". That it happens to equal the sweep width today is a
  coincidence, and a coincidence that would silently clamp a future wider uncertainty.
- **Its sky clamp is wrong for a look.** A look must point where the contact is believed to be.

```
look_sweep(
    *, centre_azimuth_deg, centre_elevation_deg,
    bearing_uncertainty_deg, fov_full_width_deg,
) -> list[tuple[float, float]]
```

- Elevation is constant at `centre_elevation_deg`. The down-range bucket also perturbs elevation,
  but at helicopter geometry that is well under a degree against a 4.25° half-angle — a second
  axis would buy nothing and cost steps. Say so in the docstring so nobody adds one later.
- Step count `N = max(1, ceil(2 · U / fov_full_width_deg))`. At U = 15° and 8.5°, **N = 4**.
- Step centres evenly spread across `[-U, +U]`, the same arithmetic `search_pattern` already uses.
  **Extract that into one private helper and have both call it** — this is the only new
  abstraction in the stage and it removes a real, named duplication.
- **Ordered centre-outward**: sort the offsets by `|offset|` ascending, ties by sign. The believed
  bearing is the most likely one, so looking there first maximises the chance of ending the sweep
  on step 0, and it guarantees the single most likely direction is sampled even if the poll rate
  under-samples the rest (see Risks).
- **`N == 1` reproduces today's behaviour exactly.** When `U ≤ fov_half_angle`, the sweep is one
  step at the believed direction for the full budget — the current stare is the degenerate case,
  not a branch. That is the short-range common case the brief asks about, and it needs no special
  handling.

---

### D3. `MAX_LOOK_S` divides by the step count — no new constant

`step_s = MAX_LOOK_S / N`. With N = 4 that is 1.5 s per step, the figure `plan.md` guessed; with
N = 1 it is the full 6 s, identical to today.

This is preferable to a `LOOK_STEP_S` constant for the reason the milestone's raise/lower
thresholds were computed rather than invented: the budget is the user's 6 s, `N` falls out of the
field of view and the clock bucket, so the dwell is the quotient of two things already measured.
It also collapses two mechanisms into one — the sweep running out of steps and `MAX_LOOK_S`
expiring become the same event, so the cap can no longer truncate a sweep mid-way.

Mechanically, `decide`'s `GLASSING` branch takes the shape `SEARCHING` already has:

- store the sweep in `OpticState.search_pattern_steps` (the field is already shared by both glass
  phases and already documented as such) at phase entry;
- `index = int((now_sim - phase_started_sim) // step_s)`; `index >= len(steps)` ends the phase;
- `look_azimuth_deg` / `look_elevation_deg` in both the returned state and the decision become the
  **current step's** direction, not a fixed one. Everything reading those (the trace, the overlay,
  `_apply_active_gaze`'s `fixed_look_at`) then follows the sweep with no change.

`step_s` must be recomputed from `len(search_pattern_steps)`, not stored — `decide` stays a pure
function of `(state, now_sim, …)` and replay stays byte-identical.

---

### D4. Finding the contact mid-sweep ends the sweep — but `look_is_finished` must change first

**As written, `look_is_finished` would end every sweep on its first poll.** It asks whether any
target inside the *current field of view* can still improve. On step 0 of a sweep the target may
deliberately be outside the 4.25° cone — that is the entire premise of sweeping — so
`_target_in_current_look` is `False` for every target, `not any(...)` is `True`, and the look ends
before it has moved. This is not a predicate that already does the right thing; it is one that
actively defeats the fix.

**The change is to widen the test from the field of view to the sweep's envelope**: the look is
finished when **no contact within `bearing_uncertainty_deg` of the sweep centre, at the sweep's
elevation, can still improve**. That is the correct generalisation rather than a new rule —
today's stare is the `N = 1` case where the envelope *is* the field of view, so the predicate keeps
its current meaning exactly where it currently applies.

With that in place, "found mid-sweep" ends the sweep for free and without a new concept:
improvement moves a contact out of `can_still_improve` (either it reached `type`, or its next-tier
window no longer contains its range), so once the last improvable contact in the envelope resolves,
the predicate fires on the next poll. A contact that improves `presence → class` but is still
inside the class→type window correctly keeps the sweep running.

`MAX_LOOK_S` then fires only when recognition is not happening at all — its documented purpose,
now also the sweep's own exhaustion point (D3).

**The same widening applies to the attempted-range marking.** `decide` currently marks every target
within the *field of view* of the chosen centre as attempted. With a sweep the look will visit the
whole envelope, so every target in the envelope gets its benefit and must bear the retry rule —
otherwise a contact the sweep reaches at step 3 is never marked and re-triggers a look immediately.

**`choose_look` is deliberately left on the field of view.** It picks the sweep's *centre*, and the
centre should still be where contacts are most tightly clustered, because that is what maximises
what a single step resolves. The envelope governs what a look *covers*; the field of view governs
where it is best *aimed*. Stating this because the two now differ, and a later reader will
otherwise assume one of them is a bug.

---

### Implementation Plan

1. **Expose the bucket.** Rename `_CLOCK_BUCKET_DEG` → `CLOCK_BUCKET_DEG` in
   `association_over_time.py`, value and docstring intent unchanged. Point
   `LookTarget.bearing_uncertainty_deg`'s default at `CLOCK_BUCKET_DEG / 2.0` instead of the
   literal `15.0`. No behaviour change; the full suite must still pass here.
2. **`look_sweep` + the extracted step-centre helper**, with `search_pattern` refactored onto the
   helper. Pure geometry, unit-tested alone: N = 1 below the FOV width, N = 4 at 15°/8.5°, constant
   elevation, centre-outward order, offsets spanning `[-U, +U]`.
3. **Widen the predicates** — `_target_in_current_look` → an envelope test, `look_is_finished` and
   the attempted marking onto it. Suite green with the stare still in place (`N = 1` path), which
   is the regression gate proving the widening is a true generalisation.
4. **Step-index the `GLASSING` branch** and store the sweep at phase entry. The behavioural change
   lands here and nowhere else.
5. **The real tripwire.** A unit test in `test_optic_policy.py`: a `class`-level contact inside the
   class→type window, whose believed azimuth is offset from truth by ~12° (most of a half-bucket,
   comfortably outside 4.25°). Assert the sequence of look directions across the phase includes one
   within the FOV of the true bearing, and that the equivalent single stare does not. This is the
   test that must go red if the fix is reverted — the mock-flight fixture cannot play that role
   (see the opening section).
6. **Correct the `xfail` reason text** in `test_mock_flight_chain.py` to name the search phase, and
   resolve the marker per the open decision below.

---

### Risks & Unknowns

- **The fixture will not turn green from this work.** Stated once more here because the marker
  currently says it must. Unresolved until the open decision is settled.
- **Poll-rate under-sampling.** The sweep is indexed in sim time, so a poll interval coarser than
  `step_s` skips steps: at the default 1 s poll and `step_s ≥ 1.5 s` every step gets at least one
  sample, but the mock fixture's 5 s poll would sample 2 of 4. Centre-first ordering means the most
  likely direction is always among them. Not worth engineering around now — the real runtime polls
  at 1 s — but it is why the new tripwire is a unit test rather than a fixture assertion.
- **No dwell floor.** `step_s = MAX_LOOK_S / N` has no lower bound. Safe while `U = 15°` bounds
  `N ≤ 4`; if a later source supplies a wider bearing uncertainty the dwell shrinks without limit.
  Not building a floor now (it would be an invented constant), but a widening of
  `bearing_uncertainty_deg` must revisit this.
- **The sweep spends more of the budget than a stare, for the same contact.** At N = 4 a contact
  gets 1.5 s of dwell instead of 6 s. If recognition needs sustained dwell rather than presence in
  the cone for one poll, this trades a miss for a glance. `check_visibility` is evaluated per poll
  with no dwell accumulation, so today it does not — but that is an assumption the Stage 4 sortie
  should confirm rather than a property anyone measured.
- **The believed elevation is weak.** The fixture's `LookTarget`s all reported `elevation_deg =
  0.0`, because a contact's `last_position.alt_m` is reconstructed from a flat projection that
  carries no honest altitude. The sweep inherits that: it points at the right azimuth and a
  possibly wrong elevation. Out of scope here, but it is a second, independent aiming error of the
  same family and it will surface in the sortie.

---

### Second-order effect

Both glass phases end up sharing one stepping mechanism and one envelope predicate, so Stage 4's
sortie retunes dwell and coverage in one place rather than two — and the search phase, which is the
milestone's genuinely speculative part, inherits the look's fix for free if its own aiming turns
out to be the thing the sortie objects to.

---

### Decisions Requiring User Input

- **What the mock-flight tripwire should become.** Its 36 → 32 loss is the binocular *search*
  phase's designed cost (four polls glassed at 2.3–5.6 km while a truck sat at 1 km), not the stare
  defect the marker names, and this stage cannot remove it. Three options:
  1. **Accept it and say so** — remove the marker, assert 32, comment naming the four polls and the
     650 m AGL geometry that makes the miss so wide. Recommended, paired with step 5's unit
     tripwire, which tests the real fix directly and does not depend on fixture arithmetic.
  2. **Keep the marker, corrected**, as a standing flag that the search phase's cost is unsettled
     until the Stage 4 sortie judges it. Honest, but a `strict=True` xfail with no landing date is
     a test that will be silently re-reasoned about later.
  3. **Treat the search cost as the defect** and change Stage 3's aiming. That is a Stage 3
     redesign, not this stage, and it should wait for the sortie rather than be guessed at now.
- **Is ~30% of every scan cycle spent glassed acceptable?** At a real 1 s poll the fixture's
  8-step, 6.4 s search occupies most of a 16 s scan cycle's slack, every cycle, for as long as a
  commanded sector stands. The fixture only made it visible because its task never completes. This
  is a sortie question by design, but it is worth knowing the magnitude before flying it.
