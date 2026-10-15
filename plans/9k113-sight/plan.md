# BL-B64 — The 9K113 Raduga-Sh sight

> **Planning only.** User direction, 2026-10-14: *"start architect on it. Do not implement yet."*
> Nothing in this plan is to be built until the decisions in the last two sections come back.

### Goal

Make the 9K113 a real third optic — what it lets Petrovich see, what it costs to use, and what it
makes possible that the naked eye and binoculars cannot — in an order that lands the pilot-visible
value before the parts that depend on unverified DCS internals and missing missile data.

**Specification:** `docs/concept/9K113.md` (the user's own words — it *is* the spec).
**Reconnaissance:** `body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md` (the full
11-switch sequence, the 3–4 min / 10–15 s timings, device/command/argument numbers, and three
findings that change this plan's shape). Optics: `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`.

---

## 0. Effort/value — the brief's own staging assumption is wrong, and in the project's favour

The brief asks whether the non-ATGM uses (holding the crosshair for the ASP-17, pinpointing a unit
on request) should land first as the cheap useful slice. **They should not, because they are not the
cheap slice.** Both of them require the pilot to *see* where the sight points, which requires the
real cockpit switches to move, which requires a write channel that does not exist and whose
feasibility on the two devices involved is unverified. They sit at the far end of the dependency
chain, not the near end.

**The genuinely cheap slice is the optic itself, and it is almost free.** Three things make it so:

1. **The hard numbers already exist.** The per-tier range multipliers were measured in detection-cones
   slice 2A and are sitting unused in `optics.py`'s own docstring — wide **3.55/7.00/6.50**, narrow
   **5.81/13.75/15.00**. The fields of view (wide 11.5°, narrow 6.0° full angle) and the field of
   regard (±60° azimuth, +20°/−15° elevation) are in the 2026-09-20 research note. No calibration
   sortie is needed to add this optic.
2. **`BINOCULAR_OPTIC` has no cockpit representation at all** and never has. Binoculars are purely
   a body-layer simulation. A purely-simulated 9K113 optic is therefore not a shortcut — it is the
   established pattern, and it is what the other four files that assert "there are only two optics"
   are waiting for.
3. **`BL-B55` is one parameter.** Its own entry establishes that `self.optic` is already in scope at
   `naked_eye_source.py:949`, so per-optic position sigma is a parameter added to one function and
   threaded at one call.

So the split that matters is not ATGM-versus-non-ATGM. It is:

| axis | what it delivers | what it depends on |
|---|---|---|
| **A — perception** | detection/classification/type ID at much greater range, and position belief that is actually *precise* at that range | nothing outside body-layer |
| **B — effectors** | the real switches moving, the pilot reading the sight off the ASP-17, the ATGM run | a cockpit-write channel for devices 6/7 (**unverified**), 9K113 telemetry args, a faster-than-1 Hz loop (`BL-B63`/`AC-B3`, filed not built), missile speed/range (**missing**), and a readiness lamp with **no confirmed read path** |

**Recommendation: build Axis A as its own roadmap entry and merge it. Then decide Axis B.** Axis A
is a few hundred lines with no new failure surface, no DCS dependency, no acceptance sortie beyond
an ordinary flight, and it is what the pilot actually notices — reports at range that are both
earlier and believed to the precision they deserve. Axis B is a multi-entry workstream with an
acceptance loop that costs ~3 minutes of warm-up per attempt and two unresolved external
dependencies.

**What Axis A does not do, stated plainly so it is not discovered in the air:** Petrovich would be
getting sight-grade perception without the warm-up having happened, without OBSERV, and without the
pilot being able to see where he is looking. That is a real honesty gap and it is the user's call
whether it is acceptable as an interim (Decision 1 below). The project's invariant is that *DCS is
authoritative about the world* — Petrovich's own body state is not the world, which is why
binoculars have never needed a switch. But "he is using a sight he never turned on" is a different
claim from "he raised binoculars", and it should be decided rather than assumed.

---

### Affected Modules / Files

**Axis A — body-layer only**

- `src/perception/optics.py` — two new `Optic` instances (`SIGHT_WIDE_OPTIC`, `SIGHT_NARROW_OPTIC`);
  `Optic` gains the field-of-regard fields its own docstring says "a future 9K113 slice adds back"
  (`regard_azimuth_half_deg`, `regard_elevation_up_deg`, `regard_elevation_down_deg`), plus
  `gyro_stabilised: bool` and `position_sigma_scale`. `peripheral=False` for both. Rewrite the
  scope-cut paragraph rather than leaving it contradicting the file.
- `src/perception/estimation.py` — `naked_eye_sigma_m` gains an `optic` parameter (this **is**
  `BL-B55`; see Stage 1b). Rename is a judgement call: `look_sigma_m` reads honestly once it is no
  longer naked-eye-only, but the rename touches tests — do it, the name is load-bearing.
- `src/perception/naked_eye_source.py` — thread `self.optic` into the sigma call; honour field of
  regard when a sighted optic is active.
- `src/belief/groups.py:385`, `src/perception/association.py:91`, `src/perception/visibility.py:49`,
  `src/perception/clustering.py:79` — the four places that assert there are only two optics. Each
  needs reading, not just editing: `clustering.py`'s floor fix already references the narrow sight's
  5.81 in its own derivation, so it may need no change at all.
- `src/belief/optic_policy.py` — a `SIGHTING` phase and a hands/eyes-busy field (Axis A can stop
  short of this; see Stage 2's note on what is reachable without Axis B).

**Axis B — aircraft-layer + body-layer (not planned in detail here; see Stage 4)**

- `aircraft-layer/dcs-export/Export.lua` — a new `op` on the existing inbound command listener
  (`poll_command_socket`, which already dispatches `petrovich_search` and already calls
  `performClickableAction` live on device 30); 9K113 state args 874/876/886 pushed as a telemetry
  line with the change-epsilon pattern `push_spu8_state` established.
- `aircraft-layer/src/collector/command_sender.py`, `src/api/server.py`, `src/schema/` — a cockpit-action
  op and a 9K113 state snapshot, following `look_direction`'s raise-on-failure posture.
- `body-layer/src/aircraft_client.py` — the matching write call and `get_9k113_state_latest`.
- `body-layer/src/belief/` — a new `sight.py` for warm-up/OBSERV/slew state; `attack_run.py` and
  `speech.py` for the ATGM register; `crew_console.py` for the observ/pinpoint commands;
  `audio-adapter/src/vocabulary.py` for the tokens and synonyms.

---

## Implementation Plan

### Stage 1 — the optic exists (Axis A)

Add both sight optics with the already-measured multipliers and the sourced FOV/regard figures.
Field of regard is the first genuinely new concept in `Optic`: how far the sight can be *pointed*,
as distinct from what it shows once pointed and from the cockpit occlusion mask. Three fields, not
one, because the elevation envelope is asymmetric (+20°/−15°).

Nothing selects these optics yet — exactly the posture `BINOCULAR_OPTIC` held between slice 2A and
`plans/binocular-optic/`, and for the same reason: the table entry and the policy that reaches it
are separate decisions with separate risks.

### Stage 1b — per-optic position sigma (this is `BL-B55`, folded in)

**Answering the brief's question 2: `BL-B55` is not a blocker to be scheduled ahead of this item; it
is this item's Stage 1b, and the two must not be separated.** Shipping a sight that sees to 8 km
while every look lands with `σ_down ≈ 0.17·R` gives the pilot a confident-sounding range wrong by
1.4 km — the precise pathology `BL-B55` was filed against, and worse with the sight than without it.

The sigma scale is a **judgement call, not a measurement**, and that is a scope statement worth
seeing: `BL-B55` left open whether the per-optic figures are derived from magnification or measured
in-game, and noted the calibration precedent argues for measurement. The cheap path is to derive
cross-range sigma from the optic's own FOV ratio (a narrower field is a tighter bearing read) and
down-range sigma from the stadiametric aid the spec names — *"linearly decreasing error as the unit
gets closer"*, useful inside ~5 km, which the 2026-09-20 note verifies against the reticle's own
5000 m / 2.5 m calibration. One constant per optic, stated as an assumption, tuned from flying.
**Do not retune `GROUP_REPORTING_EAGER_COHESION_CAP_M` as part of this** — `BL-B55` says so
explicitly, and fixing the error model is what makes the cap behave.

### Stage 2 — using it costs something (Axis A, partial)

The optic becomes selectable, under the same structural rule the binocular cycle already uses: a
`SIGHTING` phase reachable **only** from a phase boundary, so the illegal state (abandoning a scan
mid-sweep to glass up) cannot be expressed. Two costs, both already half-built:

- **Exclusivity and the 1 s hand movement.** A `hands_busy_until_sim` on `OpticState`: any cockpit
  action sets it, and while it is set the sight yields no observations. The spec's eyes-away →
  switch → eyes-back is then two of these back to back, which is the structure it describes rather
  than a special case. The 1 s itself is a project modelling choice, not from the manual (research
  note, Finding 1) — one constant, easily changed, as the spec asks.
- **Violent manoeuvre forces OBSERV off.** `optic_policy.STEADY_RATE_LIMIT_DEG_S = 12.0` already
  exists and already does exactly this job for binoculars, keyed on attitude rate from telemetry at
  the ~1 Hz poll. **Reuse the mechanism; declare a separate constant** — gyros tolerate far more
  than hands do, and that docstring's own argument (this gate sees manoeuvring, not vibration) is
  the right argument here too. The spec's 1–2 s reaction time is the poll interval, so it is free.

**What is not reachable in Axis A:** slewing as an inspect-and-adapt loop. The spec's own line —
*"ownship telemetry must contain 9K113 data"* — is the dependency, and it is Axis B. Without it the
sight's pointing is a body-layer fiction that cannot be checked against where it actually points,
which is the whole content of inspect-and-adapt. Axis A therefore models the sight as pointable
instantly within its field of regard, and Stage 4 replaces that with the real loop. Say so in the
docstring; an instant-slew model left unlabelled is the kind of placeholder that gets believed.

### Stage 3 — acceptance flight for Axis A

An ordinary sortie, no warm-up cost. What it decides: whether sight-grade detection ranges feel
right, whether the position sigma scales produce reports the pilot trusts, and whether the phase
cycle's handover between naked eye, binoculars and sight reads as a crew member choosing an
instrument rather than thrashing.

### Stage 4 — Axis B, and it is several roadmap entries, not stages

Not planned in detail here, because three of its inputs are unresolved and planning around them
would be planning around assumptions. What it contains, in dependency order:

1. **The cockpit-action channel.** Export.lua's `op` dispatch and `performClickableAction` are
   proven live — but **on device 30 (the AI wheel) and device 55 (SPU-8)**, not on `WEAP_SYS`
   (device 6) or `I9K113` (device 7). Every argument number in the warm-up table is cross-referenced
   from a 2026-09-11 probe of a *different* device set. Before this is built, the one probe worth
   running is: can `performClickableAction` actually move args 673 / 955 / 885 / 886 / 963, and does
   the lamp state follow? Plus `list_indication` on `ccGunnersCPanel` (index 8, never tried) for the
   `READY` lamp. **I am not dispatching that Investigator pass from here** — it belongs ahead of
   Axis B's own plan, not inside this one, and the main loop should dispatch it when Axis B is
   scheduled.
2. **Warm-up and OBSERV as real modes**, with the 3–4 min and 10–15 s timers as *two* timers (the
   research note is explicit that collapsing them is wrong), the *"Guidance unit ready"* and
   *"Observ on/off"* callouts, and the spec's constraint that OBSERV is not left on. If the lamp
   probe comes back negative, readiness is a timer Petrobrain owns — honest, and the manual itself
   presents the timing as elapsed-time gates.
3. **The slew loop**, which needs args 874/876 read back and the AI-axis write (3060/3061). Note
   that 876's degrees-per-unit is **unmeasured** — the raw read is confirmed, the conversion is not.
   Elevation slew is therefore not plannable to a degree today.
4. **`BL-B65`** — the weapons safety switch (arg 673). Its own entry, as the spec requires, and it
   gates the ATGM run.
5. **The ATGM run.** See §5 below for what reuses `BL-14` and what differs.
6. **The non-ATGM uses** — crosshair-hold for the ASP-17, and pinpoint-on-request. Cheap *once*
   (1)–(3) exist, and worth noting they also need the ASP-17 `AUTO/MAN` switch at arg 553 and the
   PUVL selector at arg 523 (research note, steps 2.2 and 3) for the pilot's HUD mark to follow the
   sight at all. That is a real precondition the spec does not mention.

---

## 5. The ATGM run as a sibling of `BL-14` — what reuses, what differs

Reused unchanged, and this is most of it: the register rules (§§1, 6, 9, 19, 23–25 of
`docs/acceptance/2026-10-14-attack-run-guidance-direction.md`). O'clock outside the ±15° sector,
qualitative *"come left"* / *"a bit right"* inside it, one *"lined up"* then silence, the
`", obstructed"` qualifier composing onto any tier-1 utterance, change-driven cadence, one voice
with the inter-utterance gap, and **one contact is the target** (§25 — mechanically forced here too:
one crosshair cannot point at two units).

Where ATGM guidance differs:

- **Azimuth only.** The spec says so, and it is consistent with §1 — but note it removes §9's
  vertical half entirely, so the aligned conjunction becomes a single gate. That is a real departure
  from what just shipped and should be flagged in the ATGM plan, not inherited silently.
- **The target is tracked, not held.** `BL-14` guides the *aircraft* onto a target. The ATGM run
  also slews the *sight* to keep the crosshair on a moving unit — a second inspect-and-adapt loop,
  running against a 1.0 s poll. **This is where `BL-B63`/`AC-B3`'s selective fast lane stops being
  optional**: §22 of the direction document already scoped that fast lane as *"a reusable seam for
  the deferred 9K113 missile-guidance work too"*. It was filed, not built.
- **New utterances with no `BL-14` analogue:** *"out of range"* / *"in range"* (once each), the
  launch callout, *"impact"* (with hit/miss if detectable), and the transmitter reset 1 s later
  (arg 882, `LAlt+R`). Only the last of these is fully specified today.
- **It cannot run on the naked-eye channel at all**, per the `BL-14` explore: *"ATGM guidance is
  with 9K113 only, there is no naked eye channel."* So the whole of Axis B is its precondition.

**The launch callout cannot be built yet, and the right interim is to say less rather than guess.**
Missile speed and maximum range are in neither manual edition this project holds (research note,
Finding 4). The community figure of ~400–450 m/s must not be encoded — that is precisely the
unverified-community-claim-as-fact the project forbids. So:

- **Interim:** speak the missile word alone, with no flight time. Suppress *"in range"* /
  *"out of range"* entirely. A missing callout is honest; a wrong seven-seconds is not.
- **To resolve it, two cheap routes, neither needing a planned feature.** Maximum range is in DCS's
  own shipped weapons tables — a file read in the install, an Investigator task, not a flight.
  Speed can be derived from a flight the user already has to make: fire one ATGM at a known range
  and time it, or better, have the collector sample the missile's own world-object position across
  frames and derive speed live. The second also gives impact detection for free, since the spec's
  own guess — the missile vanishing as a world object — is the same observation.
- **And the missile word is "Shturm", not "Ataka".** Only 9M114 Shturm is implemented; 9M120 Ataka
  is marked in-development. The spec's own example names the missile the sim does not have. The user
  has been told; his document is not edited. Decision 4 below asks which word he wants.

> **AMENDED 2026-10-15 — the data gap is closed and the framing was wrong.** The user supplied the
> missile sources himself, with the framing *"Hind can carry **either** 9K114 Shturm **or** 9M120
> Ataka"*. Full figures and consequences: `body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md`,
> "Addendum, 2026-10-15". In short:
>
> - **Speed and max range are known**: Shturm 345 m/s / 400–5,000 m; Ataka 400 m/s average
>   (550 m/s peak) / 400–6,000 m. Flight time is therefore computable — **~14.5 s to 5 km,
>   ~15 s to 6 km** — so the interim above (speak the word, suppress the time) **loses its
>   premise**. It was correct only while the numbers were unknown.
> - **In-range / out-of-range becomes implementable**, bounded by a **400 m minimum** that both
>   families share and that `BL-14`'s attack-run guidance currently has no concept of.
> - **The missile word is a loadout read, not a constant.** "Shturm" is right *today* only because
>   DCS has not shipped the Ataka family; a hardcoded word is wrong for half the loadouts the moment
>   it does. Derive from the loaded store, fall back to generic `"missile"`. This strengthens
>   Decision 4's second option rather than settling Decision 4 — the question of which word to speak
>   when the store *can* be read is still the user's.
> - **Speed and max range belong in `X-T26`'s configurable set as two per-family profiles**, not as
>   inline numbers. The ~40% speed difference is large enough to be audible in a spoken flight time.
>
> **One caution that keeps the original reasoning alive:** these are Wikipedia figures, not DCS's
> own weapons tables. The paragraph above was right that an unverified community number must not be
> encoded as fact, and that still applies — DCS's shipped `db_weapons*.lua` remains the
> authoritative read (a file read, not a flight) before any of these numbers reaches a callout the
> pilot trusts.

---

## 6. Autonomous OBSERV — not designed here

The spec leaves *"When to Observ → Autonomously given conditions → TBD"* open, and I am not
inventing it. **It needs an `/explore`**, and what that conversation has to decide:

- **The trigger.** What belief state justifies it — an unidentified contact at a range where
  binoculars have already failed? A contact the pilot asked about? A class the pilot cares about?
- **The cost it is spending.** OBSERV is not free in the spec's own terms: wear, the lost peripheral
  channel (`peripheral=False`), the 10–15 s alignment, and a 3–4 min warm-up that must already be
  done. The binocular cycle's rule was *"at least one naked-eye scan before the next binocular
  usage"*; the equivalent rule here is unknown and is the substance of the question.
- **The release.** When he comes off it — and whether coming off it is a callout.
- **Whether it is autonomous at all.** The spec's first bullet is *"when pilot requests it"*. It is
  entirely possible the honest answer is that OBSERV is pilot-commanded for now and the autonomous
  case is a later item. That would be a cheaper and more defensible place to stop.

---

### Risks & Unknowns

- **The cockpit-write channel is unverified on devices 6 and 7.** Every warm-up argument number is
  cross-referenced from a probe of other devices on a DCS build from 2026-09-11, and the numbers are
  positional — an ED patch inserting a table entry shifts them. Regenerate before coding against
  them. This is Axis B's single largest risk and the reason Axis A should not wait behind it.
- **The readiness lamp has no confirmed read path** and one unexplored probe. If it comes back
  negative, *"Guidance unit ready"* is a timer asserting a state nobody verified.
- **Missile speed and maximum range are missing**, as above. Carried as a risk, not an assumption.
- **Elevation slew's degrees-per-unit is unmeasured**, so any elevation-aware slew logic is
  unplannable to a degree today.
- **Acceptance is unusually expensive for Axis B** — ~3 minutes of warm-up before anything is
  testable, and the research note adds a failure mode the spec does not model: a gyro toppled by an
  excessive-rate manoeuvre needs `GUID.UNIT POWER` cycled and **another 3–4 minutes**. A single
  mistake mid-test costs a full reset. Budget acceptance in sorties, not in attempts, and build the
  flag-gated debug logging up front.
- **Axis A's instant-slew fiction** will be believed if it is not labelled. Label it in the
  docstring where the fiction lives, not only in this plan.
- **Four files assert there are only two optics.** Two of them (`clustering.py`,
  `visibility.py`) have derivations that already reference the sight's numbers, so each needs
  reading rather than find-and-replace.
- **`BL-12` Stage 0's cohesion cap** gets better, not worse, from Stage 1b — but it was calibrated
  against naked-eye-grade believed spacing, so its behaviour will change. Expected, and `BL-B55`
  explicitly forbids retuning the cap to compensate.

---

### Second-order effect

Axis A closes `BL-B55`, gives `BL-B62`'s relative-versus-map split its second real consumer, and
turns `BL-B63`/`AC-B3`'s selective fast lane from a filed idea into a hard dependency of the next
entry in this series. It also makes `BL-12`'s group-cohesion work tractable at range for the first
time, since a sight-grade look is the only look whose believed spacing is close to its true spacing.
Axis B, if built, makes the cockpit-write channel a general facility — the SPU-8 and wheel channels
are each one-off, and a sequenced switch-action op would be the first reusable one, which the
weapons-safety switch, the ASP-17 mode switch and anything else cockpit-side would then inherit.

---

### Decisions Requiring User Input

1. **Is a perception-only 9K113 acceptable as an interim?** Axis A gives Petrovich sight-grade
   detection, identification and position precision with no warm-up, no OBSERV and nothing visible
   to the pilot in the cockpit — the same posture binoculars have always had. It is the whole of the
   cheap value and it lands in one entry. The alternative is holding all of it behind Axis B's
   unverified write channel and missing missile data. **Recommendation: yes, build Axis A first**,
   with the fiction labelled where it lives.

2. **"Poor vertical understanding" — what is the mechanism?** The spec says the 9K113 gives poor
   vertical understanding; `BL-14` uses the vertical axis as a *discrimination* aid for picking the
   right unit. `BL-14`'s own entry already reads these as two different instruments (its tiers are
   naked-eye/binocular with no 9K113 channel), so there is no conflict in code today — but there
   will be the moment the ATGM run needs to pick a unit. And nothing in the optics supports the
   claim: the sourced fields of view are **symmetric** (wide 11.5°, narrow 6.0° full angle, circular
   eyepiece), so the sight has no az/el resolution asymmetry of its own. **The question that needs
   answering is which of three different things is meant**, because each implies a different model:
   - the *readout* is coarse — which matches a real finding, that DCS's elevation argument 876 is a
     piecewise gauge whose degrees-per-unit nobody has measured;
   - the *reticle* helps only horizontally — its mil marks are the ranging aid, and ranging is a
     horizontal fit;
   - or judging the *depression angle to a ground target* is simply hard, which is about the
     geometry rather than about the sight.

   The consequence that makes this worth his time: **if "poor vertical" means the sight cannot tell
   which of two vertically-separated units is meant, the ATGM run cannot discriminate targets the
   way `BL-14` does, and selection has to come from somewhere else.** I am not picking an answer —
   the spec itself asks for an `/explore` here.

3. **Where does autonomous OBSERV go?** `/explore` now, or defer it and ship OBSERV as
   pilot-commanded only (§6). **Recommendation: defer.** Pilot-commanded is the spec's own first
   bullet, it is cheaper, and the autonomous policy is better decided after flying the commanded
   one.

4. **The missile word.** Investigator established that only 9M114 **Shturm** exists in DCS; the
   spec's example says *"Ataka"*. Options: `"Shturm"` (correct, and he will hear it if he ever flies
   with a Russian-speaking crew), or a generic `"missile"` (one word, no Russian, no risk of being
   wrong again when Ataka ships). His call, and his document is not edited either way.

5. **The flight-time callout's interim.** Recommendation above is to speak the missile word with no
   time and suppress the range callouts until speed and range are measured rather than guessed.
   Confirm — the alternative is a number from community consensus, which this project does not
   encode as fact.
