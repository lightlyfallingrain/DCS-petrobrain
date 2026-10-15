# BL-B64 — The 9K113 Raduga-Sh sight

> **Planning only.** User direction, 2026-10-14: *"start architect on it. Do not implement yet."*
> Reaffirmed 2026-10-15 for this amendment pass. Nothing in this plan is to be built yet.

> **AMENDED 2026-10-15 (second pass).** User direction arrived in response to this plan's five open
> decisions and is captured verbatim in **`docs/acceptance/2026-10-15-9k113-sight-direction.md`**,
> §1–§11. **That document is the specification and outranks this plan wherever they differ.**
>
> It settles Decisions 1, 2 and 3 (marked in place below — the original reasoning is kept, because
> *why the optics were the wrong place to look* is the transferable part), removes one use case
> entirely, and adds four requirements this plan did not have: both fields of view from the start,
> a non-instant slew, a directional player-bubble exemption to 20 km, and a ranging act with a cost.
>
> **It also splits this item into three roadmap entries** (§5 of the direction), which is the other
> half of this pass: `[[BL-B64]]` (perception — this plan's Axis A), `[[BL-B66]]` (effectors),
> `[[BL-B67]]` (the ATGM run). **Sections 10–16 below are the amendment**, and are where the
> perception entry's design actually lives; sections 0–6 are the first pass, preserved.

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

> **PARTLY SUPERSEDED 2026-10-15 — §1 of the direction removes one row from the table above.**
> *"ASP-17 must not be manipulated directly. It shows the pilot where the 9K113 is pointing, but
> that's automatic, not manual."* So "the pilot reading the sight off the ASP-17" is **not** an Axis
> B deliverable and must not be built as an action at all: the mark follows the sight's pointing by
> itself, and whatever makes the sight point somewhere makes the mark move. It stays in this plan
> only as a *consequence* of Axis B, with no effector, no `AUTO/MAN` switch step, and no entry of
> its own. §4.6 below (step 6 of the Axis B list) is superseded by the same sentence.
>
> The rest of the table stands, and the direction confirms its recommendation (§5).

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

> **SUPERSEDED 2026-10-15 (direction §8).** *"the 9K113 via cockpit manipulation takes time to move
> so we cannot expect instant alignment with anything."* **Instant pointing is not an acceptable
> placeholder in the perception stage, labelled or not**, and the reasoning above is wrong in one
> specific way worth keeping visible: it argued the fiction was harmless because nothing could check
> it. That was true when the plan had no cone. **Direction §7's 20 km exemption is pointed *in the
> direction the sight is looking*, so the pointing direction now has a consumer** — an instantly
> teleporting cone would let Petrovich perceive at 19 km in a direction he could not have been
> looking at a second earlier, which is an omniscience leak, not a placeholder. §15 below settles
> which stage owns slew and recommends this one.

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

   > **SUPERSEDED 2026-10-15 (direction §1).** The crosshair-hold half of this item does not exist
   > as work. The ASP-17 mark follows the sight automatically, so there is no "hold the crosshair"
   > action to build and no `AUTO/MAN`/PUVL precondition to satisfy for it — this paragraph's
   > "real precondition the spec does not mention" was reasoning from an action that is not real.
   > Pinpoint-on-request survives, as part of `[[BL-B66]]`.

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
> **SUPERSEDED IN FULL 2026-10-15 (direction §6).** No `/explore` is owed. OBSERV is entered on
> pilot command and the sight is autonomous within it, *"like he uses binoculars"* — so the trigger,
> the cost, the release and the is-it-autonomous question below are all answered by the existing
> optic policy rather than by a conversation. Kept for the record; §13 replaces it. The one thing
> this section got right and §13 carries forward: `peripheral=False` means OBSERV really does cost
> the peripheral channel.

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
- ~~**Axis A's instant-slew fiction** will be believed if it is not labelled.~~ **Retired
  2026-10-15 (direction §8): there is no instant-slew fiction, because slew time is modelled in the
  perception stage (§15).** The risk it is replaced by is that the slew *rate* is a stated modelling
  choice rather than a measurement — carried in §16.
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

   > **DECISION 1 ANSWERED 2026-10-15 (direction §5): yes.** *"Lets start with that, that let's us
   > test the behaviour. We'll then add actually manipulating the systems in cockpit. Only then can
   > we add the ATGM attack run."* The reason given is **testability** — it is the stage that lets
   > the behaviour be flown — which is a stronger reason than the cheapness this plan argued from.
   > Three entries in that order, not one feature. One clause of the recommendation is now wrong:
   > the instant-slew fiction is **not** to be labelled and kept (see §15).

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

   > **DECISION 2 ANSWERED 2026-10-15 (direction §2), and none of the three candidates was right.**
   > *"The 9K113 itself is very precise on where it is pointing. However, the copilot only has
   > azimuth reading for it, and not a precise one. […] Nothing at all tells the vertical offset."*
   >
   > **The answer is upstream of the optics entirely: the sight is precise, the *instrumentation* is
   > asymmetric.** The reticle carries an azimuth scale (a bottom arc marked `1`/`3`/`6` = 10°/30°/60°
   > off boresight — `docs/concept/mi-24_info/9k113-reticle-narrow-x10.png`) and **no elevation scale
   > at all**. The crewman judges the vertical from the view itself, with no instrument to read.
   >
   > **The original reasoning is kept deliberately, because its negative finding was correct and is
   > the reusable part:** this pass checked the optics, found the sourced FOVs symmetric (wide 11.5°,
   > narrow 6.0°, circular eyepiece), and concluded nothing in the optics supports an az/el
   > asymmetry. That was right. The mistake was assuming the asymmetry therefore had to be *in* the
   > optics, so all three candidate mechanisms were drawn from the wrong layer. **When a spec claims
   > an asymmetry the physics does not have, look at what the operator can read, not at what the
   > instrument can see.**
   >
   > Consequences, smaller than this decision feared: **no elevation angle is ever spoken** (§10);
   > world reference is fine and is cross-reference rather than instrument readout (*"on the ridge"*
   > — the existing semantic-position machinery); and the approximate azimuth offset feeds `BL-14`'s
   > existing o'clock-then-left/right register with **no new guidance vocabulary**. The feared ATGM
   > target-selection problem belongs to `[[BL-B67]]`, not to this entry.

3. **Where does autonomous OBSERV go?** `/explore` now, or defer it and ship OBSERV as
   pilot-commanded only (§6). **Recommendation: defer.** Pilot-commanded is the spec's own first
   bullet, it is cheaper, and the autonomous policy is better decided after flying the commanded
   one.

   > **DECISION 3 ANSWERED 2026-10-15 (direction §6), by splitting the question this plan could not
   > answer.** *"OBSERV ON only on pilot command / if OBSERV is ON, then Petrovich can use the 9K113
   > autonomously, like he uses binoculars."*
   >
   > **Entering** the mode is always the pilot's call — so the recommendation to defer was right
   > about the mode switch. **Within** the mode the sight is autonomous, which the recommendation
   > got wrong, and the four questions §6 of this plan said an `/explore` had to settle (trigger,
   > cost, release, whether it is autonomous at all) **do not need answering**: the second clause
   > hands them all to a mechanism that already exists.
   >
   > *"Like he uses binoculars"* is the load-bearing phrase. It makes the 9K113 **a new entry in
   > `optic_policy`'s existing dwell/scan machinery, not a new attention model** — which is a far
   > smaller build than §6 assumed. §13 below is what that actually costs, and it is not zero: the
   > mechanism is shared but §9 inverts its *shape*.
   >
   > So **no `/explore` is owed on OBSERV**, and §6 of this plan is superseded in full.

4. **The missile word.** Investigator established that only 9M114 **Shturm** exists in DCS; the
   spec's example says *"Ataka"*. Options: `"Shturm"` (correct, and he will hear it if he ever flies
   with a Russian-speaking crew), or a generic `"missile"` (one word, no Russian, no risk of being
   wrong again when Ataka ships). His call, and his document is not edited either way.

5. **The flight-time callout's interim.** Recommendation above is to speak the missile word with no
   time and suppress the range callouts until speed and range are measured rather than guessed.
   Confirm — the alternative is a number from community consensus, which this project does not
   encode as fact.

   > **Deferred, not answered (direction, "What this leaves open").** Decisions 4 and 5 both belong
   > to `[[BL-B67]]`, which §5 places last, and both are partly superseded by the 2026-10-15 missile
   > addendum. Not urgent; they are not this entry's to settle and are not re-asked below.

---
---

# AMENDMENT, 2026-10-15 — the perception entry's design

Everything from here down is the second pass. It designs **`[[BL-B64]]` only** — the perception
entry, this plan's Axis A, now carrying §§7–11 of the direction. `[[BL-B66]]` (effectors) and
`[[BL-B67]]` (the ATGM run) are deliberately *not* designed here; their entries say what they are
waiting for.

## 10. What the direction added, removed, and left alone

| direction | effect on this entry |
|---|---|
| §1 ASP-17 is automatic | **removes** the crosshair-hold use case entirely. Not an action, not an entry. |
| §2 instrumentation asymmetry | **answers** Decision 2 with no optics work. No elevation readout exists. |
| §5 three entries, in order | **splits** this item. Perception → effectors → ATGM. |
| §6 OBSERV commanded, autonomous within | **answers** Decision 3. New `optic_policy` entry, not a new attention model. |
| §7 20 km directional cone | **adds** work, body-layer only. `AC-B3` not involved. |
| §8 both FOVs, slew takes time | **adds** work: two optics from the start, and a slew rate limit. |
| §9 inverted dwell shape | **adds** work: shared mechanism, inverted *shape* (§13). |
| §10 no elevation spoken | **removes** work. No new vocabulary; `BL-14`'s register is enough. |
| §11 ranging costs 2 s, group ranged once | **adds** a range-error model; **removes** per-unit ranging cost. |

Five things the first pass carried as open or as work are now closed at zero cost: the ASP-17 use
case, Decision 2's three-way mechanism question, autonomous OBSERV's `/explore`, a sight-specific
guidance vocabulary, and per-unit ranging. That is the context for the effort/value re-read in §17.

## 11. Wide and narrow are two optics, and the mechanism is the one binoculars already use

**Two new `Optic` table rows, not a mode flag.** The reach-versus-field axis `BINOCULAR_OPTIC`
already sits on is the same axis; the sight simply sits further along it, which is the direction's
own reading (§8: *"quite analogous… the 9K113 just has a longer reach, can see further, though also
a much more limited FOV"*).

| field | `UNAIDED` | `BINOCULAR` | `SIGHT_WIDE` | `SIGHT_NARROW` |
|---|---|---|---|---|
| `presence_range_mult` | 1.00 | 2.42 | **3.55** | **5.81** |
| `class_range_mult` | 1.00 | 3.50 | **7.00** | **13.75** |
| `type_range_mult` | 1.00 | 3.00 | **6.50** | **15.00** |
| `fov_half_angle_deg` | (wide) | 4.25 | **5.75** | **3.00** |
| `peripheral` | `True` | `False` | **`False`** | **`False`** |

The multipliers are **already measured** (detection-cones slice 2A) and sit in `optics.py`'s own
docstring, deliberately not instantiated. The FOVs are the sourced 11.5°/6.0° full angles halved.
So the table rows cost nothing to fill — this is the first pass's finding and it survives.

**Selection needs no new logic.** `improvement_window_m()` / `tier_ranges()` already answer *"what
would a different optic gain on this contact"* per optic, which is exactly the wide-versus-narrow
question. A third and fourth row make that machinery answer it for the sight too.

**What genuinely differs, and it is one new field, not a new value.** Field of regard — how far the
sight can be *pointed* — has no analogue in the eye or binoculars, which are pointed by the head and
are unrestricted. `Optic` gains `regard_azimuth_half_deg` (±60), `regard_elevation_up_deg` (+20),
`regard_elevation_down_deg` (−15); `None` on the two existing optics, which is the state its own
docstring already anticipates (*"a future 9K113 slice adds them back"*). Three fields because the
elevation envelope is asymmetric.

**One figure to fix while in the file.** `visibility.NAKED_EYE_RANGE_CAP_M`'s docstring says *"a 7 m
vehicle reaches 9333 m from the formula, just inside this cap"*. With the current
`LOWRES_ANGULAR_RADIUS_RAD = 0.003` it reaches **2333 m**; 9333 m was a 0.00075 threshold that no
longer exists. Stale, and it matters here because that docstring is what the next reader will use to
sanity-check the sight's reach.

## 12. The 20 km cone goes inside the bubble filter — the constant's own docstring says so

**Direction §7's requirement was anticipated on disk.** `association.PLAYER_BUBBLE_RADIUS_M`'s
docstring already prescribes this exact design, down to the reason:

> *"They will diverge the moment the 9K113 sight lands… its cone reaches 20 km while the naked eye's
> own cap stays at 10 km, and when that exception exists it will be evaluated **within** the bubble
> filter below (narrowed to the sight's own FOV), **not by raising this radius** — raising it would
> reinstate the whole-sphere cost the bubble exists to remove, at four times the area."*

So: `filter_player_bubble()` gains an optional frozen `sight_cone: SightCone | None` (azimuth,
half-angle, depth), handed down per poll by the same seam `gaze` and `optic` already use — belief
decides, `logger` passes a frozen value, perception owns the act. Admission becomes: inside the
radius, **or** inside the cone and within its depth. `PLAYER_BUBBLE_RADIUS_M` is not raised, not
aliased, and `tests/test_association.py`'s `test_player_bubble_radius_is_not_…` pair (which asserts
neither module's source names the other's constant) must keep passing.

### 12a. The cone alone buys nothing — this is the finding the direction could not have

`visibility.py:854`:

```python
range_threshold_m = min(NAKED_EYE_RANGE_CAP_M, size_curve_threshold_m)
```

`NAKED_EYE_RANGE_CAP_M = 10000.0`. A narrow-sight candidate at 13.6 km computes
`size_curve_threshold_m ≈ 13 556` and is then **clamped back to 10 000 and rejected**, with trace
outcome `range_cap`. The cone would admit it into the pipeline and the cap would throw it away.

**So the entry needs two changes, and neither is sufficient alone:** the cone in `association.py`,
*and* an optic-aware range cap in `visibility.py`. The honest shape for the second is a per-optic
cap (`optic.range_cap_m`, defaulting to today's 10 000 for eye and binoculars) rather than scaling
the existing constant — scaling it by `presence_range_mult` would make the sanity bound stop being a
sanity bound, which is the one job that constant has. It must not be aliased to
`PLAYER_BUBBLE_RADIUS_M` in either direction.

### 12b. What the cone costs per tick, and what has to be measured

**The numbers below are on disk already** (`plans/player-bubble/performance.md`, and the
performance-reviewer's own measurement): 423 median candidates/tick on the real 2026-10-01
engagement trace, the bubble dropping **~76.6%** of them (so ~98 survive), the bubble filter costing
**~0.53 µs/candidate**, terrain LOS costing **~540 µs/candidate** — a **~1000×** gap — and the
realised whole-tick work median at **12.6 ms** after `BL-11`.

**Area bound on the admission count.** Bubble area = π·10² = 314 km². The cone's area *outside* the
bubble = (fov/360)·π·(20² − 10²): **15.7 km² narrow** (6.0°), **30.1 km² wide** (11.5°) — i.e. **5%
and 10% of the bubble's own area**. At uniform density that is ~5–10 extra candidates per tick on
the 423/98 figures. The exemption is small because a 6° wedge is small, not because 20 km is close.

**Filter-side cost: negligible and bounded.** `range_m` already runs on all 423 candidates. The cone
adds a `bearing_deg` only for candidates that *fail* the radius test (~325 of them), at the same
order as `range_m`: **~0.16 ms/tick against a 12.6 ms tick, ~1.3%.** Guard the whole branch on
`sight_cone is not None` so an OBSERV-off tick pays nothing at all.

**Downstream cost: this is the real one, and it is the number that decides the design.** ~5–10 extra
candidates entering `check_visibility`'s gate chain cost ~nothing at the cheap gates but **~540 µs
each if they reach terrain LOS** — **~2.7–5.4 ms/tick, i.e. +20–40% on a 12.6 ms tick.** That is not
negligible. The upper end is also pessimistic: a candidate past 10 km survives only while the sight
is active *and pointed at it*, which is at most one 6° wedge, so the realistic count is a handful
rather than ten, and the cheap gates (the new per-optic cap, the FOV cone, the cockpit mask) run
first by construction — `check_visibility`'s gate order is cheap-before-LOS.

**What must be measured, and it is a re-run rather than new instrumentation.**
`plans/player-bubble/performance.md` already has the harness, the trace and the per-candidate costs:

1. **candidates admitted by the cone but not the radius**, per tick, median *and max*;
2. **how many of those reach the LOS step** — not how many are admitted. `detection_trace` already
   records the gate-outcome histogram, including `PLAYER_BUBBLE` and `range_cap`, so this is a
   query, not a new counter;
3. **realised tick time with the cone on and off**, on the same trace.

**(2) is the measurement that matters, and the reason is a recorded lesson rather than a guess.** The
performance reviewer's own finding on this filter was that *"an exclusion-rate percentage is not
itself the saving — check what gate would have rejected those candidates anyway, and at what
cost"*: the bubble's headline 76.6% exclusion was worth **~1.4%** end-to-end, because
`NAKED_EYE_RANGE_CAP_M` was already rejecting the same candidates cheaply. The mirror-image error is
available here — reading an admission count as a cost.

**And this is the change that finally makes the bubble earn its keep**, which the same measurement
predicted: *"the bubble's real payoff is structural/future… will diverge once a wider-range optic
(9K113, 20 km cone) lands — that is when this filter starts actually saving LOS cost rather than
duplicating an existing cheap gate."* Worth stating, because it retires a justification that has
been soft since 2026-10-02.

## 13. §9's inverted dwell is a policy *shape* change — but one parameter, not a second policy

**It is not just constants, and that is the honest answer to the question.** `optic_policy`'s
machine hardcodes `SCANNING` as the resting phase in three places (`_back_to_scanning`, the
first-poll branch, `lower_binoculars`), and its central structural invariant — the module docstring
calls it out as *"the illegal state cannot be expressed"* — is that **`GLASSING` is reachable only
from a scan boundary**. That exists to enforce the user's binocular rule, *"at least one naked eye
scan before next binocular usage"*.

§9 inverts exactly that: *"When using 9K113 we typically use it for a longer period of time. Maybe
take eyes off it for a quick glance around and then continue with the sight."* **With the sight, the
sight is the baseline and the naked eye is the interruption.** A fourth phase bolted on with its own
entry rules would duplicate the whole machine.

**Design: parameterise the home phase.** `OpticState` gains `home_phase: OpticPhase =
OpticPhase.SCANNING`; `_back_to_scanning` becomes `_back_to_home`. OBSERV ON sets `home_phase` to a
new `SIGHTING`; OBSERV OFF sets it back.

- **OBSERV off: behaviour is identical to today**, by construction — same default, same transitions.
  That is pinnable as a property test, and it is what makes the refactor safe to do at all.
- **OBSERV on: the symmetry is exact.** `SIGHTING` rests; the existing `SCANNING` phase becomes the
  bounded interruption, reached at a dwell boundary precisely as `GLASSING` is reached at a scan
  boundary today. One parameter earns its place because it removes a duplicate machine — the test
  this project's own rule sets for a new abstraction.

**Constants that differ (these really are only constants):** `MAX_LOOK_S = 6.0` → a much longer
`SIGHT_MAX_DWELL_S`; a new `SIGHT_GLANCE_AWAY_S` bounding the interruption (the inverse of
`SCAN_CYCLE_PERIOD_S`'s role today); and `STEADY_RATE_LIMIT_DEG_S = 12.0` → a separate
`SIGHT_STEADY_RATE_LIMIT_DEG_S`, because gyros tolerate far more than hands do. All start as stated
modelling choices tuned from flying, like every perception constant before its first sortie, and
all belong in `X-T26`'s configurable set rather than inline.

### 13a. Two traps in this refactor, both already recorded

- **`lower_binoculars` must not drop OBSERV.** It is called on **every** player command (*"the pilot
  asking for something is itself evidence that what Petrovich is doing matters less"*). But §6 makes
  OBSERV a **pilot-commanded mode**: any command silently cancelling it would be wrong, and would be
  the kind of wrong that is very hard to see in the air. It may end the current *dwell*; it must
  leave `home_phase` alone.
- **The interrupted-look attempt-burn gets worse with a long dwell.** There is a live defect on
  record: `decide` marks a look-target attempted the moment a look *starts*, and `lower_binoculars`
  can end it early with no distinction from a completed look, which can permanently lock a
  stalled-range contact out. The pending/committed split (Stage 2, Fix B1) is what handles the
  interrupted case for `GLASSING` — **confirm it covers `SIGHTING` before lengthening the dwell**,
  because a 30 s dwell interrupted at 1 s burns the attempt on a far larger window than a 6 s look
  does.

## 14. The range model: fractional like the eye's, with a smaller coefficient, drawn once per group

**Phase 1 is instant but imprecise** (§11: *"instant, though not perfect… it does not give exact
answers"*). What must be right from the start is that the answer is **approximate**; the 2 s cost
can come later.

**Shape, with the number left to `[[BL-B55]]`'s own calibration:**

- **Down-range: keep the existing shape, change only the coefficient.**
  `σ_down = SIGHT_RANGE_FRACTIONAL_SIGMA × R`, mirroring `RANGE_FRACTIONAL_SIGMA = 0.17`. Keeping it
  fractional is what makes this *one parameter* on `naked_eye_sigma_m` (`BL-B55`'s own finding:
  `self.optic` is already in scope at the call site) rather than a new estimator.
- **One caution on that shape.** A purely fractional error understates how a stadiametric aid
  actually degrades: it is useful inside ~5 km and falls off faster once the target subtends less
  than the smallest reticle division. If flying shows that, the honest upgrade is **a fraction that
  grows past ~5 km**, not a different estimator. Noted; not built.
- **Cross-range: scale `BEARING_SIGMA_DEG` by the optic** — a narrower field is a tighter bearing
  read. **But** that constant's docstring says it models *stating* a bearing, floored by optical
  resolution, so scaling it is coherent for the **observation** channel only. It must not be
  confused with `[[BL-B62]]`'s relative-direction channel, whose `RELATIVE_DIRECTION_SIGMA_DEG` is
  `0.0` and is fenced to two files by test.
- **A group is ranged once, at its middle unit** (§11), and **this is a correctness argument, not an
  optimisation.** Draw the ranging error **once per group per look** and share it across members.
  Independent per-unit draws would scatter members' believed positions; a shared draw keeps the
  group *cohesive*, which is exactly what `BL-12` Stage 0's cohesion cap needs — the cap is
  calibrated on true spacing and applied to believed spacing. So honour §11 from the start rather
  than deferring it. Per-unit ranging stays an explicit, occasional act with one named use case
  (ATGM range checks), and it belongs to `[[BL-B67]]`.
- **Phase 2, named but deferred:** the ~2 s cost as an eyes-busy interval, reusing the same
  `hands_busy_until_sim` field the 1 s switch movement uses. Not in this entry.

`[[BL-B55]]` closes as this entry's own stage and must not be separated from it — the first pass's
reasoning stands unchanged: a sight seeing to 13–19 km while every look carries `σ_down ≈ 0.17·R`
reports a precise-sounding range wrong by **~2.3–3.3 km at those ranges** (worse than the 1.4 km the
8 km case gave), which is worse than having no sight.

## 15. Slew: ANSWERED by direction §12 — deferred to the effectors, but the perception stage must not collapse two fields into one

> **DECISION 6 ANSWERED 2026-10-15 (direction §12), and my recommendation below was wrong in its
> conclusion while right in its reasoning.** The sight is slewed by a joystick-like device whose
> axes command angular **speed**: *"The axis input is the slew speed. Not desired angle, but angular
> speed of slew… we need a constant inspect and adapt loop… There's a maximum to angular velocity of
> course, and that is why it takes time to move the 9K113 from one point to another."*
>
> So **"point the sight at X" is not an action with an argument — there is no angle to write.** It is
> a closed loop, and slew time is the *consequence* of a rate limit inside it rather than a delay to
> wait out. The user's ruling: *"We don't need this modeled before the effectors, but we must be
> ready for how it will work with the effectors so we don't have to redo much of the mechanism."*
>
> **What survives from the reasoning below:** point 3 — that the cone gives the pointing direction a
> consumer — was the right observation and it is why this is not a plain deferral. It no longer
> argues for modelling slew *time* here; it argues for the **actual** pointing direction existing as
> a real field here, because the cone must be pointed at where the sight *is*, not at where belief
> wishes it were. Points 1, 2 and 4 are superseded: a rate limit in the perception stage would be
> the wrong mechanism, not merely an early one.

### 15a. The requirement the perception entry does carry

**Keep *desired aim direction* and *actual sight direction* as two distinct things from the start**,
even while the perception stage sets `actual := desired` instantly. The effector stage then inserts
a controller between two fields that already exist. Collapsing them into a single "where Petrovich is
looking" *is* the rework §12 asks to avoid.

**Evaluated against the code rather than adopted, and the answer is better than it looks: the
distinction is collapsed today, but the collapse sits on one line, and everything downstream of it
is already shaped correctly.**

The chain today is:

```
OpticDecision.look_azimuth_deg      (belief's DESIRED aim — optic_policy.decide)
  -> ScanPlan.fixed_look_at(...)    (logger.py ~881-885  <-- the collapse, one place)
  -> Gaze.center_azimuth_deg        (semantically the ACTUAL pointing direction)
  -> check_visibility(boresight_azimuth_deg=gaze.center_azimuth_deg)
```

- **Not carried today**: one value plays both roles. `logger.py` converts belief's desired look
  straight into the `Gaze` that perception treats as fact, so `actual == desired` by construction.
- **But every consumer already reads *actual*.** They read a `Gaze`, whose meaning is already "where
  the head/sight is pointed" — `within_optic_fov` even takes the boresight as a *parameter*
  precisely because *"an optic is pointed by the head, not bolted to the airframe"*. So there is no
  "everything that assumed one field" to refactor. **The coordinator's concern is real but its blast
  radius is one conversion point, not the model.**
- **What is genuinely missing is persistence.** `gaze_at` is a *pure function of `t_sim`* and
  recomputes the direction from the plan every poll, so nothing *holds* an actual aim that could lag
  a desired one. A converging sight needs state.

**Cheapest non-collapsing shape, and it costs the perception entry very little:**

1. **Put the actual aim on `OpticState`** (`actual_aim_azimuth_deg`, `actual_aim_elevation_deg`),
   which the runner already carries across polls and which is already *"frozen and replaced rather
   than mutated"*. That preserves replay determinism **by construction** — the property `gaze_at`'s
   purity exists to protect — rather than smuggling state into a pure function. This is the one
   design constraint that could have cost real money, and `OpticState` already solves it.
2. **One named function, one call site**: `advance_sight_aim(actual, desired, dt, …)`, called at the
   `logger.py` conversion point. Its perception-stage body is `return desired`; the effector stage
   replaces that body with the rate-limited controller. Nothing else moves.
3. **Build the `Gaze` from *actual*, and point the §7 cone at *actual*.** This is the part that earns
   its place immediately rather than as future-proofing.
4. **Per-optic, not global.** For the naked eye and binoculars `actual := desired` is not a
   placeholder but *permanently correct* — a head turn is instant against a 1 Hz poll — so the
   controller must never be imposed on them. A global rate limit would be a regression in the
   existing channels.

**Cost: one field pair, one trivially-bodied function, one call site, and the discipline that the
boresight comes from actual.** Call it a dozen lines and a naming decision. It is worth doing even
on its own merits, because *"desired"* and *"actual"* sharing a name is the kind of collapse that
makes a later bug unreadable.

### 15b. The superseded recommendation, kept for its point 3

**Recommendation: the perception entry owns a slew *rate limit*; the effector entry owns the *closed
loop*.** Two different things, and only the second needs anything unmeasured.

1. **The direction's own reason for building both FOVs now applies verbatim** (§8): the perception
   simulation is being built regardless, and a model that snaps instantly produces behaviour
   `[[BL-B66]]` could never reproduce — *"the difference would surface as a regression rather than as
   a known gap."*
2. **It is cheap here and expensive later.** In perception, slew is a bounded pointing state: a
   commanded azimuth/elevation, a rate, and observations yielded only from where the sight points
   *now*. `OpticState` already carries that shape — `look_azimuth_deg`, `look_elevation_deg`,
   `phase_started_sim` — so this is **a rate limit on how fast the commanded direction may change**,
   not a new subsystem.
3. **The decisive point: slew changes what the cone admits.** §7's exemption is pointed *where the
   sight is looking*. Instant pointing means the cone teleports — a different 6° wedge out to 20 km
   every tick — which both inflates §12b's cost and lets Petrovich perceive at 19 km in a direction
   he could not have been looking a second earlier. **That is an omniscience leak, not a
   placeholder**, and it is why the first pass's "label the fiction" was safe then and is not now:
   the cone gives the pointing direction a consumer it did not have.
4. **The honest objection, and why it does not bite.** The slew *rate* is not measured — arg 876's
   degrees-per-unit is unmeasured (research note). But a rate constant needs **seconds per degree**,
   which is a stated project modelling choice tuned from flying, exactly like the 1 s hand movement.
   The unmeasured conversion blocks *reading back* where the sight actually went, which is
   `[[BL-B66]]`'s inspect-and-adapt loop — not modelling a plausible rate here.

~~**This is a view, not a decision** — it is open question 4 in the direction's own list, and it is
Decision 6 below.~~ **Settled by §12; see §15 and §15a above.**

### 15c. What §12 does to the effector entry — three constraints, recorded here and in `[[BL-B66]]`

Not this entry's work, but it changes `[[BL-B66]]`'s shape enough to be worth stating where the
reasoning lives:

1. **The sight's current angle must be readable every iteration**, or the loop has no feedback term.
   **This promotes the deferred cockpit probe from useful to load-bearing** for that stage —
   specifically whether arg **876**'s degrees-per-unit is measurable and whether the OBSERV readout
   (arg **886**) can be sampled at loop rate. Still not dispatched from here; it gates that stage's
   own plan.
2. **Loop rate becomes a correctness property, not a performance preference.** A rate-commanded loop
   closed at body-layer's current **1 Hz would overshoot every time**. So `[[BL-B63]]`'s selective
   fast lane is a **hard dependency of the effector stage**, not the optional optimisation its entry
   reads as today — the same mechanism it was already filed for (missile guidance), arriving one
   stage earlier than it expects.
3. **Maximum angular velocity is a constant** and belongs in `X-T26`'s tunable set
   (`body-layer/config/defaults.toml` + `src/tuning.py`, merged to `main` 2026-10-15). Overshoot,
   deadband and settling become real concerns there too — a loop that chatters would be visible in
   the cockpit and, during an ATGM run, a guidance failure.

## 16. Risks this amendment adds

- **The cone's downstream LOS cost is estimated, not measured** — §12b's +20–40% upper bound is the
  one number in this plan that could change the design. It gates the stage, and the cheap lever if
  it comes back high is in §17.
- **Lifting the range cap for the sight creates contacts beyond 10 km for the first time.**
  `ContactStore` never prunes (an accepted, documented bound), and `BL-B23`'s analysis says the
  bubble does not reduce accumulation *today* only because `NAKED_EYE_RANGE_CAP_M` bounded it
  anyway. An optic-aware cap removes that bound, so the never-pruned growth axis gets a genuinely
  new source. Not a vulnerability; a quantity to watch in the sortie logs.
- **`BL-12`'s cohesion cap will behave at ranges nothing has flown.** §14's shared per-group draw is
  the design that keeps it sane, and it has not been exercised past 10 km. `BL-B55` still forbids
  retuning the cap to compensate.
- **The `home_phase` refactor touches the most behaviour-critical function in the belief layer**, and
  near a live defect (§13a). Pinned-behaviour tests for the OBSERV-off path are the mitigation, and
  they are cheap because the default is unchanged.
- ~~**The slew rate is a modelling choice, not a measurement.**~~ **Retired 2026-10-15 (direction
  §12): no slew rate is modelled in this entry at all.** It is replaced by a smaller, different
  risk — **that the desired/actual collapse gets rebuilt by accident.** It is one line in
  `logger.py` (§15a) and nothing downstream enforces the distinction, so a later change that reads
  the boresight from `OpticDecision` instead of from `OpticState`'s actual aim would silently
  reinstate it. Cheap guard: a test asserting the cone and the `Gaze` are both built from the actual
  aim, in the spirit of the existing `test_player_bubble_radius_is_not_…` pair.
- **The effector stage now has a correctness-level dependency on `[[BL-B63]]`** (§15c) that its own
  entry does not yet reflect. Noted on `BL-B63` as part of this pass.
- **`NAKED_EYE_RANGE_CAP_M`'s docstring is stale** (§11) and is the figure a reader would check the
  sight's reach against.

## 17. Effort/value, re-read against the direction

**It is no longer "nearly free". It is still the cheap slice, and it should still go first — but it
is a three-stage entry with one measurement gate, not a drop-in.** Stated plainly because the first
pass called it *"a few hundred lines with no new failure surface"* and that sentence is now wrong.

**The first pass's three reasons all survive**: the multipliers are measured and on disk, a
purely-simulated optic is the established pattern (`BINOCULAR_OPTIC` has never had a cockpit
representation), and `BL-B55` is one parameter. **And the direction removed five things** (§10),
including the entire ASP-17 use case and the OBSERV `/explore`.

**The growth is concentrated in two places, not spread:**

1. **The `home_phase` inversion** (§13) — a refactor of `optic_policy`'s central structural
   invariant, next to a known live bug whose blast radius the long dwell *increases*. Not a
   constant; a careful pass with pinned-behaviour tests.
2. **The cone plus the optic-aware cap** (§12) — a two-sided change where neither side works alone,
   with a cost question that needs a bench measurement, and the first change that lets contacts be
   created beyond 10 km.

Everything else the direction added is genuinely small: two table rows (§11), the desired/actual
field split (§15a — ~a dozen lines, and §12 *removed* the slew rate limit this entry was going to
carry), a coefficient and a per-group draw (§14). **§12 is net negative work for this entry**: it
took slew modelling out and put in one field pair.

**One cheap lever, identified before the measurement rather than after it.** If §12b's LOS cost
comes back at the top of the range, **narrow the cone rather than optimise LOS** — and the right cut
is already visible in the arithmetic: **§7's cone is only load-bearing for narrow mode.** Wide
presence reaches `2333 × 3.55 ≈ 8.3 km` for a 7 m vehicle — *inside* the existing 10 km bubble — and
only ~11.8 km for a 10 m one. **Narrow reaches 13.6 km and 19.4 km.** So the wide cone buys almost
nothing for ordinary ground vehicles while costing twice the narrow cone's area (30.1 vs 15.7 km²).
Dropping wide from the cone in phase 1 halves the added cost at near-zero product cost, and it is a
one-line gate.

**Verified, not accepted:** the direction's parenthetical that *"the measured multipliers put narrow
presence at ~13.6 km for a 7 m vehicle and ~19.4 km for a 10 m one, so 20 km is close to where the
sight genuinely runs out, not a round number"* is **exactly right** —
`7/0.003 × 5.81 = 13 556 m` and `10/0.003 × 5.81 = 19 367 m` from
`LOWRES_ANGULAR_RADIUS_RAD = 0.003` and the measured narrow presence multiplier. Checked rather than
taken, because a sizing figure in a brief is the one most likely to be wrong by 2×. This one is not.

**Nothing here argues for deferring the entry.** The alternative — holding perception behind the
effectors — is *strictly worse* than it was before, because the direction removed the effector
axis's cheapest use case.

## 18. Second-order effect

Unchanged from the first pass in substance, with two additions. **The cone is the first consumer of
the sight's pointing direction**, which is what makes slew time load-bearing now rather than later
(§15) — so this entry hands `[[BL-B66]]` a pointing model to make real rather than a fiction to
replace. And **the per-optic range cap is a seam, not a one-off**: it is the first time
`NAKED_EYE_RANGE_CAP_M` stops being global, which is the shape any future sensor with its own reach
would need. Against that, `[[BL-B67]]` is now *more* constrained than before: §2's no-elevation-
readout finding means ATGM target selection cannot discriminate vertically the way `BL-14` does, and
that has to be solved in that entry rather than assumed away.

---

### Decisions Requiring User Input (second pass)

The five from the first pass are settled or deferred above. These are new.

6. ~~**Does slew time belong in the perception entry, or with the effectors?**~~ **ANSWERED by
   direction §12 — the effectors.** No longer open. What replaced it is a requirement rather than a
   choice (§15a): keep desired and actual aim distinct from the start. Evaluated against the code,
   that costs ~a dozen lines, because the collapse is one line in `logger.py` and every downstream
   consumer already reads the *actual* side.
7. **Should the wide cone be in phase 1 at all?** §17: wide reaches ~8.3 km for a 7 m vehicle, which
   is *inside* the existing bubble, while costing twice narrow's cone area. **Recommendation:
   narrow-only cone in phase 1**, wide added if a sortie shows something missed. This is cheap to
   reverse and halves the one cost that needs measuring.
8. **Does `BL-B64` keeping its number as the *perception* entry read correctly to you?** The
   alternative was an umbrella entry holding all three. **Recommendation: as done** — an umbrella
   never closes, so it would sit `[ ]` open indefinitely and make the backlog's status unreadable,
   whereas the three entries share the specification document and cross-link. Flagged because four
   other entries point at *"the 9K113 slice"* and some of them mean the ATGM run, which is now
   `[[BL-B67]]`.
9. **Is the ~2 s ranging cost deferred to a later entry, or in phase 1?** §14 defers it, on the
   direction's own *"acceptable first phase implementation is that distance measurement is
   instant"*. **Recommendation: defer** — the approximation is what matters and it is in phase 1;
   the cost is a second eyes-busy interval on a field that does not exist yet.
