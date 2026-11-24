# BL-B124 — alignment

## Goal check — 2026-11-24

**Verdict:** CONCERNS

### Why

Today Petrovich sees the same at 04:50 as at noon, which is the "hawk-eyed" failure ED's own
Petrovich has. That makes his reports (and his silences) mean nothing at dawn, dusk and night. The
point is that **what he reports matches what a crewman could see in the same light**. The pilot sees
the darkness too, so he can tell what Petrovich's reports and silences mean. A low-light mission
then plays like one: the 9K113 is the instrument that still works at dusk, and at night only light
gives a unit away.

Second "why": the pilot needs to trust Petrovich. If he reports a BTR at 3 km in darkness, the
pilot stops believing him in daylight too.

### Player expectations

- **E1** — In full daylight, nothing changes from today: the same ranges and the same callouts.
- **E2** — At dawn and dusk, the naked eye and binoculars fall off sharply. In the user's
  measurements, at sunrise −18 min the eye detects at ~0.5 km and classifies at ~0.2 km. At −28 min
  neither the eye nor binoculars detect anything. Below sunrise, the eye and binoculars never give a
  type at any range.
- **E3** — With Petrovich in the operator seat, the 9K113 keeps finding things at dusk far beyond
  the eye: narrow field ~12 km detection at −18 min and ~7 km at −28 min, with class and type at
  short range. The sight is the instrument that matters in low light, and the pilot hears contacts
  he cannot see himself.
- **E4** — In real darkness no optic sees an unlit unit: *"In real darkness, cannot see anything."*
  Petrovich reports nothing that is not giving off light.
- **E5** — At night, a light source is seen out to the player bubble. The sources are firing and
  burning today, explosions if DCS exposes them, and a missile launch.
  - A launch's plume is visible **for a few seconds**, from the launch event itself (the firing hook
    already carries `S_EVENT_SHOT`).
  - The smoke trail is **not** a night cue (user: *"Missile plume is certainly not reported, but
    that is the same thing as missile launch, the plume is there for a few seconds. And smoke
    trail, though that we do not see in the dark."*).
  - So at night a launch must not get `[[BL-B72]]`/`[[BL-B74]]`'s long daytime smoke-dissipation
    tail. It gets a few-second flash. Vehicle lights are out of scope (user, recorded at
  `f2f37ab8`: *"Ignore vehicle lights for now. The only case for them is friendly units in deep
  friendly territory anyway."*). An unlit vehicle driving at night therefore stays unseen. It gives **presence only, at
  where the light was**. It never gives class or type, and it does not light up the units around it
  (*"nothing else is known about it than where the flash was"*). Once the light stops, it is an
  ordinary decaying contact.
- **E6** — The change follows sun elevation smoothly. The same sun elevation gives the same
  performance at dusk as at dawn. No contact pops in or out at a threshold minute, and nothing
  flickers as the light changes.
- **E7** — It holds at any theatre and date, because it is keyed to sun elevation and not to clock
  time. Examples: a June Syria dawn, a January Caucasus afternoon, a Kola summer night where the sun
  barely dips.
- **E8** — Petrovich says nothing about the light. As darkness falls there is no burst of
  "lost" chatter (`CONTACT_LOST` has no template today, so this holds already). A contact identified
  in daylight keeps its identity while its confidence decays (the existing invariant). "Last I saw"
  answers behave as they do today.
- **E9** — Moonlight can be added later as a change to the light level alone. It should not need
  the per-optic behaviour reworked.
- **E10** — When Petrovich is in the pilot seat (no 9K113) or flying (no optics, U6), he has only
  his eyes, so at night he sees only lights. This follows from existing rules and needs no new one.

### Open assumptions

- **The ends of the measured range: what happens outside the three measured points.** The three
  points all lie within ~6° of the horizon (derived below). Nothing is measured for full day or full
  dark.
  - Serves the why: explicit end points. The light factor is 1.0 from some "full day" sun elevation
    upward. Every optic reaches 0 at some "full dark" elevation below −28 min, unlit units only.
  - Would not: interpolating between the three points and **clamping at the end values**, which is
    the obvious way to code a table. That leaves the eye at ~0.19 of normal all day, which breaks
    E1. It also leaves the 9K113 seeing 7 km in full night, which breaks E4. **This is the concern
    behind the verdict.**
- **Converting minutes to sun elevation.** The table is in minutes from sunrise. The user asked for
  it to be keyed to sun elevation, and the conversion needs the test mission's date, which the
  document does not record.
  - Derived here (astronomy, not DCS knowledge): a sunrise azimuth of 63.2° at 31.58° N means solar
    declination ~+22.6°, so early June or early July. That gives the sun's rate of climb at the
    horizon as ~0.19°/min. So **−28 min ≈ −6° (end of civil twilight), −18 min ≈ −4°, +2 min ≈
    −0.5°**.
  - Serves the why: anchor on these elevations, with the date confirmed by the user.
  - Would not: anchoring on minutes, which breaks E7. In a Kola summer, or a winter mission at
    another latitude, "−28 min" is a different amount of light.
- **The shape of the factor.** BL-B124 calls BL-B22 "the spec". BL-B22's lead framing is *"optics
  multiply up, conditions multiply down"*, which is one scalar. The 2026-09-26 analysis supersedes
  that, and BL-B22 itself says so further down.
  - Serves the why: a factor per optic and per tier. In low light the 9K113 narrow field holds up
    best. Type drops to zero for the eye and binoculars, which is a floor, not a short range. The
    tiers compress.
  - Would not: one scalar per light level. That cannot give E3 (the sight 20× the eye at −18 min)
    and E2 (eye type at zero) at the same time.
- **Smooth blend or coarse tiers.** The research note argues for coarse tiers, because measurement
  precision falls with the light. Since then the user has said "smooth blend on sun elevation".
  These do not conflict: a few coarse measured anchor points with smooth interpolation between them
  meets both. **The user's later words win.**
  - Would not: steps at fixed times, which bring back pop-in and break E6.
- **Units already held when it gets dark.**
  - Serves the why: no special rule. As light falls, re-detections stop, existing contacts decay
    through `estimated` to `lost`, and mission memory keeps them. That is what a crewman's memory
    does.
  - Would not: dropping or downgrading held contacts at nightfall, or keeping them "observed" in
    the dark because they were seen before.
- **The light-level input.**
  - Serves the why: one named "light level" quantity, derived from sun elevation today with a slot
    for moonlight. This is also `[[BL-B94]]`'s worked-example param, so build one, not two.
  - Would not: per-optic tables keyed directly on raw sun elevation, which leaves nowhere for the
    moon to go (E9).
- **When the date or time is not known at runtime.** This happens if no mission understanding was
  loaded, or the date cannot be read.
  - Would not: silently assuming full daylight. That keeps today's hawk-eyed Petrovich on every
    night mission where the date is missing, which breaks E4 without anyone noticing. Silently
    assuming dark is worse.
  - The fallback is the user's call (question below). Whatever it is, it should be loud
    (`feedback_broken_config_fail_loud_not_recover`).
- **Search behaviour in low light.**
  - Obvious filling: the optic policy is unchanged. It still runs naked-eye scan phases and
    binocular glass phases that at −28 min can see nothing. That breaks no stated expectation:
    Petrovich just spends time on useless instruments.
  - It does matter that the policy's own range estimates (`tier_ranges`, used by
    `sight_can_still_improve`) see the reduced ranges. Otherwise it keeps choosing to glass contacts
    it cannot resolve, and may stall on them.
  - Whether he should *prefer* the sight at dusk is a behaviour question for the user. It is not
    settled by "no speech change".
- **How long a launch stays visible at night.**
  - Serves the why: the plume lasts a few seconds from `S_EVENT_SHOT`, then the launcher is an
    ordinary decaying contact.
  - Would not: reusing the daytime launch-smoke rule (`[[BL-B72]]`: *"SAM launch shows where the
    launcher was for quite a while"*, `[[BL-B74]]`, not built) unchanged at night. That reveals the
    launcher from a trail the user says cannot be seen in the dark, which breaks E5.
  - If BL-B74 is built later, its smoke tail has to fade with light level, as the user's words
    imply.
- **Air targets.** All measurements are a BTR-60 on the ground.
  - Obvious filling: the same factor for aircraft. A helicopter silhouetted against a bright
    twilight sky may in fact stay visible longer than a vehicle on dark ground. That is the agent's
    understanding of DCS, so it is a question, not a finding.
- **Weather.** Out of scope. Until weather is built, an overcast dusk is modelled as clear-sky
  dusk, and so too generous. This is known and accepted, not a defect of this card.

### Findings

1. **The measured points do not reach day or night, and the obvious interpolation silently breaks
   E1 and E4.** Lens: World truth.
   - Assumption: interpolate the light factor over the measured points and clamp outside them.
   - In the sim: measured at sun elevations of roughly −6°, −4° and −0.5° only. The clear-day
     calibration was flown in full daylight.
   - The pilot would see: either an eye that is weak at noon, or a 9K113 that finds a BTR at 7 km at
     midnight.
   - Grounded in: `docs/concept/detection-in-non-perfect-conditions.md`, where the user writes
     *"In real darkness, cannot see anything"* and the last row is −28 min.
   - Suggests: the plan states a "full day" elevation (factor 1) and a "full dark" elevation (every
     optic 0, except for light sources), as data with their source named. Either the user measures
     them, or the user agrees on a stated assumption.
2. **The BL-B22 "spec" leads with a model its own later paragraph refutes.** Lens: Purpose.
   - Assumption: one condition scalar after the optic multiplier.
   - In the sim: measured factors at −18 min run from 0.03 to 0.22 depending on the optic, and type
     is zero for the eye and binoculars.
   - The pilot would see: either a 9K113 as blind as the eye at dusk, or an eye that types at dusk.
   - Grounded in: `body-layer/research/2026-09-26-condition-factors-first-analysis.md` findings 1–3.
   - Suggests: the plan reads the analysis rather than the BL-B22 framing paragraph, and the factor
     is a per-optic, per-tier table with a type floor.
3. **Earlier records versus this week's words.** Lens: none (bookkeeping). Not contradictions that
   block anything, but a planner should know which wins:
   - The research note's "coarse tiers" versus "smooth blend": settled above.
   - `[[BL-B94]]`'s deferral (*"no need to actually build the light level things yet"*) is overtaken
     by `[[X-T29]]` priority 4. The light-level param comes into being here. The dome-light rules
     stay out.
   - BL-B22 factor 2 asked *"whether Petrovich has any low-light aid at all"*. It is answered: NVG
     is useless for detection, and the 9K113's orange filter is the aid.
4. **At night, existing emitters are the light sources, and the gates they keep need a look.**
   Lens: The non-obvious case.
   - Today `[[BL-B72]]` lifts the range and tree gates for emitters but keeps gaze, cockpit mask and
     optic FOV. Terrain LOS is still open (its question 1, which itself notes *"at night a muzzle
     flash can light a hillside it is not visible over"*).
   - At night this matters more, because the emitter is the *only* thing he sees.
   - Not a concern for this card. Leave the emitter gates as they are and keep the BL-B72 question
     open, unless the user wants it settled now.
5. **The hands rule and the pilot seat are not new work here (E10).** Lens: Whose job.
   - Flying (U6) and the pilot seat already reduce him to the naked eye, which this card simply
     dims. At night, with the player in the CPG seat, Petrovich sees only lights. That is correct.
   - The pilot-seat cockpit mask bounds which lights he sees from that seat, so the user's reminder
     belongs here.
   - **Recommendation:** a measurement row on the test card, as the user asked (*"remind me about
     the pilot seat mask at the test card"*). Making the mask per-seat is separate perception work,
     not folded into this plan.

Vignette walked (the non-obvious case): a dusk mission from the operator seat at 200 m AGL, with a
column at 3 km identified as BMPs at sunset.
- Over the next ~25 minutes the eye loses them first, at ~−4°. The binoculars go next, and the
  narrow 9K113 last.
- With no special rule the contacts decay silently and stay "BMP" in memory. "What's at two
  o'clock?" gets a "last I saw" answer, which matches what the pilot sees out of the window.
- Then one BMP fires. It reappears as a presence-only "something firing", at the flash.
- That is right on every count, provided Finding 1's "full dark" end point exists. Without it, the
  9K113 would keep re-identifying the column all night.

### Questions for the user

1. Where does the 9K113 go fully blind? At what time before sunrise does it stop detecting a BTR in
   the test mission: −40 min, −50 min? This is the "full dark" end point.
2. Where does the naked eye get back to full daylight performance: sunrise +10, +20 or +30 min?
   (At +2 min it detected at 1.8 km, against ~9 km in clear daylight.)
3. The test mission's date: was it early June or early July? That confirms −28/−18/+2 min ≈ −6°/−4°/
   −0.5° sun elevation.
4. Aircraft against a twilight sky: do they fade like ground vehicles, or stay visible longer?
5. At dusk, should Petrovich lean on the 9K113 and skip binocular glances that cannot help, or keep
   today's search routine with only the ranges dimmed?
6. If the mission date or time cannot be read: run as daylight with a loud warning, or refuse in
   the way the missing-world-model case does?
7. Pilot-seat mask: only a measurement row on this test card, or should a per-seat mask be built in
   this work?
