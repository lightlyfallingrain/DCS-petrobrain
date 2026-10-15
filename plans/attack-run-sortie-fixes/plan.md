# Attack-run sortie fixes (2026-10-15) — `BL-B70`, `BL-B71`

### Goal

Make attack-run guidance say something only when the pilot would hear a difference, stay silent when
Petrovich physically cannot see the target, mark the arrival at 12 o'clock, and reach for the
least-capable optic that can actually resolve the target instead of calling every non-observation
*"obstructed"*.

Source of truth: `docs/acceptance/2026-10-15-attack-run-sortie-feedback.md` §1–§9. The user's words
outrank this plan wherever the two differ.

**Two roadmap entries, not one** — see "Staging" at the end for why.

---

## What the investigation found before designing (step 3a)

Four of these change the design, and three contradict the brief's own framing. Reported rather than
quietly followed.

### F1 — §1's fix is *already half-built*; the defect is the **other** clause

`attack_run._should_emit` already compares the rendered utterance:

```python
if text != state.last_spoken_text:
    return True
...
return (azimuth_delta > ATTACK_RUN_CHANGE_THRESHOLD_DEG
        or elevation_delta > ATTACK_RUN_CHANGE_THRESHOLD_DEG)
```

It is a **disjunction**. The text comparison the brief asks for exists; the repeats come from the
second clause firing while the text is unchanged. So the fix is not "compare the utterance instead of
the state" — it is **make the text comparison a veto rather than one of two triggers**.

**Measured, from `dcs-belief-truth-20261015-164451.jsonl`:** 47 of 125 attack-run utterances (38%)
were byte-identical to the one immediately before. Driven mainly by the **elevation** clause —
`dev` of 4.5°, 5.1°, 5.5°, 8.1°, 8.6° against azimuth deltas as small as 0.09°.

**Why it is structural, not a tuning miss:** the emit threshold is 3.0°, but the vocabulary's own
quantisation is coarser than that on every axis — `ELEVATION_WORD_TABLE`'s single gate is **10°**
(direction §11: *"wide on purpose"*), an o'clock sector is 30°, and the azimuth rows sit at 7.5° and
5.0°. A 3° threshold on a 10° word gate **cannot** do anything except re-speak unchanged text. The
angular clause is not redundant — it is the whole defect.

**This is consistent with direction §10, not a reversal of it.** §10 recorded the slow-drift guard as
*"the known risk, recorded rather than designed around… whether that happens in the air is a sortie
question."* The sortie answers it: the guard fires 47 times and never once carries information. Drift
that matters always crosses a word boundary and therefore always changes `text`.

### F2 — the `", obstructed"` cause is already available on `Contact`, tri-state, with a precedent

`Contact.live_los_clear: bool | None` (`contacts.py` L470) already carries the live DCS verdict per
contact — `True` clear, `False` blocked, **`None` no verdict**. So §8 needs no new plumbing and the 8%
no-verdict case is *distinguishable at this call site*, which was the open question.

Better still, `ContactStore.tick`'s engagement term (L1655) already decided this exact question and
wrote down the answer: `live_los_clear is None` **or** staler than `decay.OBSERVED_WINDOW_S` ⇒
**fail-open**, with the reasoning *"no fresh look, there is nothing to clear a danger state on."*

**So the plan reuses that predicate rather than minting a rule.** The perception *admission* gate
stays fail-closed (not claiming to see things you cannot) and the *spoken word* is fail-open (not
claiming terrain that may not be there). Two different questions, two different defaults — the same
split `optics.py`/`association.py` already draw between "can this optic claim to have resolved it"
and "is it worth computing at all". **`", obstructed"` is spoken only on `live_los_clear is False`
with a fresh verdict.** The 8% figure therefore stops mattering at this call site, which answers the
coordinator's question without needing the figure quantified.

### F3 — the hysteresis band the brief asked me to size against something real is **too small if sized the obvious way**, and a band alone is insufficient

Measured range-rate of the attack target, from both sorties' belief-truth logs:

| sortie / target | range span | median rate | max closing | **max opening** |
|---|---|---|---|---|
| 17:55 `CONTACT_15` | 154–2836 m | **−64.6 m/s** | −378 m/s | +20 m/s |
| 16:44 `CONTACT_21` | 220–2829 m | −59.0 m/s | −191 m/s | **+130 m/s** |
| 16:44 `CONTACT_23` | 78–5880 m | −36.1 m/s | −212 m/s | +97 m/s |

Consequences, neither of which was guessable:

1. **Closing is ~60 m/s, not the ~17 m/s the §5 block implies** (that block is one 15 s slice, not the
   run). A 15% band at the naked-eye rung (0.15 × 2333 m = 350 m) is crossed in **under 6 s** — six
   hands-busy intervals of margin, not a safety factor.
2. **The range genuinely reverses, by up to +130 m/s.** The fly-past is in the data. So **no band of
   any plausible width survives a fly-past** — a band is a guard against noise, not against the
   pilot turning around. The brief's instruction to treat hysteresis as load-bearing is right, and
   the consequence is that it needs **two** guards, not a wider single one.

The cheapest of the two guards falls out of §2 for free: **do not re-evaluate the ladder at all while
the target is behind the cockpit mask.** A fly-past masks the target, so the suppression that §2
already requires for *speech* removes most fly-past optic thrash at its root, before any band or
timer is consulted.

### F4 — a fresh-construction branch will silently drop every new field (the `BL-B64` bug class, pre-emptively)

`attack_run.decide`'s emit path builds `AttackRunState(...)` **fresh**, not `replace(...)`:

```python
new_state = AttackRunState(last_spoken_azimuth_deg=..., ..., last_contact_id=contact.id)
```

It happens to set all six fields today, so nothing is dropped. **The moment this plan adds
`last_spoken_clock_hour`, every spoken tick silently resets it** — and the §4 marker would then fire
on every callout, or never, depending on default. `OpticState`'s own docstring already carries this
warning for `actual_aim_*` (*"Every branch of `decide` that constructs a fresh `OpticState` must carry
these two fields forward explicitly"*). This is instance four of the class `BL-B64` produced three of.
**Both new-field sites switch to `replace()`.** See Co-moving Fields.

### F5 — §9's LOS priority is **already most of the way built**, and neither candidate home is needed

The brief offers two homes (aircraft-layer slot reservation vs. body-layer explicit request), both
assuming the target may not be raycast at all. Reading
`aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` says otherwise:

- **The Hook's query set is the look-direction wedge, and body-layer already pushes that wedge from
  the same `scan_plan` the attack run owns.** `logger.run_once` computes `gaze_for_look_direction =
  gaze_at(t_sim, self.scan_plan)` and `POST`s `_hour_for_gaze(...)` on change — and during a run
  `_active_gaze` returns a `fixed_look` **at the target**. So the wedge already centres on the attack
  target. *Petrovich's intent already pushes outward to the export side; this is not a new coupling
  and no precedent needs setting.*
- Inside the wedge the Hook **sorts nearest-first** and caps at `MAX_SIGHTLINES_PER_CALL = 128`,
  documented in its own header as *"a blow-up guard, not a policy… would essentially never bite under
  a correctly-sized wedge"*.
- `POLL_INTERVAL_S = 1.0`, so the target is **recomputed every second already**. Priority-as-ordering
  buys nothing it does not already have.

**So the residual no-verdict causes are all on the body-layer side**, and one of them is large:
`LOOK_DIRECTION_FOV_HALF_DEG = 90`, i.e. the pushed wedge is the forward hemisphere about the gaze
hour. **When the pilot flies past, the target leaves the wedge and no sightline is computed for it at
all** — which is very likely a major share of the 8%, and is *exactly* the §2 cockpit-mask case that
now goes silent anyway. §2 therefore removes the dominant no-verdict case as a side effect.

What remains: join skew beyond `LOS_MAX_AGE_S = 3.0`, a `unit_name` join miss, and the cap biting.

### F6 — the attack run's gaze and its optic come from two different places

The run claims the *gaze* in `logger._active_gaze` (a `ScanPlan.fixed_look_at`, checked before the
`scan_area` loop), which bypasses `optic_policy`'s phase machine entirely. The *optic* meanwhile still
comes from `optic_policy.decide`'s own SCANNING/GLASSING cycle. During an attack run those two
disagree by construction: the eyes are pinned on the target while the instrument is chosen by a scan
cycle that does not know a run is happening. That split is why §5 happened at all — nothing ever asked
"is the instrument in my hands good enough for the thing I am staring at".

---

## Affected Modules / Files

| file | change |
|---|---|
| `body-layer/src/belief/attack_run.py` | `_should_emit` → text equality becomes a veto (F1); new `NoLookCause` taxonomy and its per-cause behaviour (§2/§5/§8); `last_spoken_clock_hour` on `AttackRunState` + `replace()` fix (F4); ladder's requested optic computed here (`BL-B71`) |
| `body-layer/src/belief/speech.py` | `render_alignment` — `", obstructed"` becomes conditional on cause; new `", <age phrase>"` qualifier reusing `_spoken_age_phrase`; optional `"Twelve o'clock, "` prefix (§4) |
| `body-layer/src/belief/optic_policy.py` | `BL-B71` only: `guidance_optic`/`guidance_optic_since_sim` on `OpticState`, a new `guidance_request` parameter to `decide`, the least-capable-optic predicate, the OBSERV gate, the hysteresis band, and revocation on every existing exit transition |
| `body-layer/src/logger.py` | `BL-B71` only: thread the run's requested optic from `drain_attack_run`'s target into `decide_optic` |
| `body-layer/src/belief/crew_console.py` | pass the cause/age inputs through `drain_attack_run`; the §9 presence/skew tripwire on the belief-truth row; no logic |
| `body-layer/src/perception/naked_eye_source.py` | `ATTACK_TARGET_LOS_MAX_AGE_S` beside `LOS_MAX_AGE_S` (§9); no change to the existing join |
| `body-layer/tests/test_attack_run.py`, `test_speech.py`, `test_optic_policy.py` | per stage |
| `body-layer/ROADMAP/BL-B70.md`, `BL-B71.md` | new entries |

**Not touched:** `perception/visibility.py`, `perception/optics.py`, `perception/detection_trace.py`.
The cause taxonomy is recomputed at the guidance site from the same pure primitives
(`cockpit_mask.is_visible`, `visibility.tier_ranges`, `Contact.live_los_clear`) rather than reading
`DetectionTrace`. **`DetectionTrace` is a diagnostic channel; using it as a control input would make
the log load-bearing** and couple guidance to a per-poll, per-candidate record that is not addressable
by contact. The primitives are pure, cheap, and already imported in `belief/`.

---

## `BL-B70` — what to say and when (§1, §2, §4, §8, §9, and §5's fallback phrasing)

### The cause taxonomy, which everything else keys off

Today `decide` infers "not observed" from percept staleness and renders one word for all of it. It
gains an explicit cause, computed in this order (matching `check_visibility`'s own gate order, so the
two cannot disagree about precedence):

| cause | test | behaviour |
|---|---|---|
| `MASKED` | `not cockpit_mask.is_visible(STATION_CO_PILOT, az, el)` | **silence** — emit nothing, speak nothing, run stays active (§2) |
| `OBSTRUCTED` | `live_los_clear is False` **and** verdict fresher than `decay.OBSERVED_WINDOW_S` | tier 2 + `", obstructed"` (§8) |
| `TOO_FAR` | range > `tier_ranges(...)[0]` for the current optic | tier 2 + `", <age phrase>"`; `BL-B71` first tries a better optic |
| `UNKNOWN` | anything else, incl. `live_los_clear is None` | tier 2, **no qualifier** — fail-open (F2) |

**The run never ends.** User direction: *"keep attack run active until pilot commands otherwise."*
`disengage` and `drop_target` already exist and both appear in the 16:44 sortie's speech log, so the
pilot already has the off switch. The "is target destroyed" model is explicitly out of scope.

`MASKED` suppresses the utterance **without updating the cadence baseline** — `last_spoken_*` must keep
describing the last thing actually *said*, so that coming back round the turn re-speaks if and only if
the words changed. Writing a baseline for an unspoken tick is the same defect as the masking
bookkeeping `AGENTS.md`'s own worked example describes.

### §1 — text equality becomes a veto

```python
if text == state.last_spoken_text:
    return False          # nothing the pilot could hear has changed
return True               # first utterance, or the words differ
```

The angular clause is **deleted**, not re-tuned — F1 shows no threshold can fix a comparison that is
finer-grained than the vocabulary it guards. `last_spoken_azimuth_deg`/`last_spoken_elevation_deg`
lose their only reader and are **removed** with it; they are not read anywhere else (the speech log's
`attack_run_azimuth_deg` comes from the current tick, not the baseline).

Stage 2 adds a **documentation test** asserting the structural property directly — that no two renders
differing only within a word band can be unequal — rather than pinning the 3.0° number that no longer
exists. (`.claude/agent-memory/implementer/project_reset_frozen_state_on_identity_change_inside_the_pure_function.md`
names this test shape and the case it was learned on.)

### §4 — the twelve o'clock marker

`render_alignment` already computes the sector test (`abs(azimuth_deg) > CLOCK_BUCKET_DEG/2`) and the
hour (`_alignment_clock_hour`). The marker needs one new state field, `last_spoken_clock_hour: int |
None`, and one new renderer input, `announce_twelve: bool`.

Rendered as a **prefix on the same utterance**, not a second one: `"Twelve o'clock, come left."`
This is the only form that guarantees §4's ordering (*"the announcement precedes the qualitative
guidance"*) without a second speech slot competing with the one-voice rule (direction §23), **and** it
changes `text`, so §1's new veto emits it automatically with no cadence special case.

**Decision 3 below** covers whether the trigger is literally 1→12 and 11→12 or any o'clock→sector
entry. The measured azimuth deltas (up to 11.7° per ~3 s tick) say a fast turn can skip the adjacent
sector, so the literal reading silently fails exactly when the pilot is turning hardest.

### §5's fallback phrasing — reuse, do not mint

The existing form the user named is `speech._spoken_age_phrase(ago_s)` → *"under a minute old"* /
*"about a minute old"* / *"a couple minutes old"*. It composes in the identical qualifier slot
`", obstructed"` uses: `"Come left, under a minute old."` One rule applied uniformly, which is the
property `render_alignment`'s docstring already defends.

### §9 — the target's LOS verdict: body-layer, and what enforces it

> *"during an attack run the current target is **the** thing to LOS and must take priority over any
> other DCS LOS checks."*

**Chosen home: body-layer. No aircraft-layer change.** F5 is the justification: the Hook already
raycasts the target every second, because the wedge it queries is the wedge body-layer pushes from the
attack run's own gaze. The export side needs nothing it does not already do.

**What the aircraft-layer option would have cost, for the record:** a slot-reservation or
priority-ordering field on the look-direction datagram, which means teaching the Hook *which contact
is the attack target* — a second thing Petrovich's intent pushes outward, and one carrying belief
identity (a contact id) rather than a geometric wedge. It would also have bought nothing measurable:
nearest-first ordering under a 128 cap on flat desert against single armour cannot drop the target.
**It is the right answer only if a sortie shows `sightlines_computed < units_in_wedge` during a run** —
at which point the Hook's own header says the wedge is wrong, not the budget.

**1. Staleness: priority means *fresher*, not *first*.** `LOS_MAX_AGE_S = 3.0` is the **join
tolerance**, not the compute rate — the Hook recomputes at 1 Hz regardless. So the binding number is
body-layer's own, and at the measured 60 m/s closing a 3 s-old verdict describes a position 180 m
behind the target. Add `ATTACK_TARGET_LOS_MAX_AGE_S = 1.5` — one feed interval plus half for jitter,
90 m at the measured rate — applied **only** to the attack target's own verdict. Costs nothing on the
export side and needs no new wire field. A verdict older than that is `UNKNOWN`, never `OBSTRUCTED`.

**2. `BL-B63`: stay independent.** The fast lane is about *ownship telemetry* poll rate; the LOS feed
already recomputes the target every second, and F5 shows the loss is the join window and the wedge,
not the rate. Raising the Hook's own LOS rate is an unmeasured DCS-side cost and is not needed while
the join tolerance is the binding constraint. **Revisit only if a sortie shows 1 Hz LOS is itself too
slow** — then it belongs with `BL-B63`, not duplicated here.

**3. If no verdict exists even with priority — and what enforces the guarantee.** The honest answer is
**`UNKNOWN`: tier-2 guidance, no qualifier.** Silence would hide a real obstruction and
`", obstructed"` would invent one; the third option is to say the alignment and claim nothing about
why. **The guarantee is not asserted — it is observable, through data already on the wire:**

- `units_in_wedge` / `sightlines_computed` (the Hook's existing observability triad) — the cap biting
  is `sightlines_computed < units_in_wedge`, already a defined tell.
- A new **per-target tripwire** on the belief-truth row: for every poll of an active run, log whether
  the target's `unit_name` was present in the snapshot and the join skew. That turns "priority is
  working" into a countable number per sortie, measurable the same way the 47-of-125 figure above was.

This is deliberately a *measurement*, not an invariant assertion. An unenforced guarantee is the shape
that produced `BL-B64`'s field-of-regard security finding — a bound declared in one stage and never
checked in the next.

### Stages

1. **Cause taxonomy + §2 silence.** Pure function change in `attack_run.decide`, inputs threaded from
   `crew_console`. Removes the 45-of-66 rear-aspect calls on its own — two-thirds of the measured noise.
2. **§1 veto.** Delete the angular clause and its two baseline fields; add the structural test.
3. **§8 + §5 fallback.** Make `", obstructed"` conditional on `OBSTRUCTED`; add the age-phrase
   qualifier for `TOO_FAR`; no qualifier for `UNKNOWN`.
4. **§4 marker.** `last_spoken_clock_hour` (via `replace()`, F4), `announce_twelve` into
   `render_alignment`, prefix form.
5. **§9 freshness + tripwire.** `ATTACK_TARGET_LOS_MAX_AGE_S = 1.5` applied to the target's own
   verdict; the per-poll presence/skew tripwire on the belief-truth row.
6. Regression pass over `test_attack_run.py`'s existing cadence tests — several pin the 3.0° threshold
   and must be *rewritten*, not extended. (Escalation rule flagged: this is a rewrite, and it is
   unavoidable because the constant they assert on ceases to exist.)

---

## `BL-B71` — the least-capable-optic guidance ladder (§6, §7)

### The rule, and why least-capable is correct

At every moment, the **least capable optic that can still resolve the target**, with a floor.
Continuous and bidirectional — not an escalation evaluated at run start.

**The ordering is derivable, not a new table.** `Optic.presence_range_mult` ascending *is*
`fov_half_angle_deg` descending across the whole shipped table:

| optic | presence mult | FOV half-angle | peripheral |
|---|---|---|---|
| `UNAIDED_OPTIC` | 1.00 | 90.0° | yes |
| `BINOCULAR_OPTIC` | 2.42 | (set) | **no** |
| `SIGHT_WIDE_OPTIC` | 3.55 | 5.75° | — |
| `SIGHT_NARROW_OPTIC` | 5.81 | 3.0° | — |

That single fact is the whole product argument: more capable means narrower, so magnification he does
not need costs him everything else he would have noticed. The ladder is therefore `sorted(table, key=
presence_range_mult)` and the first rung whose `tier_ranges(...)[0] >= range_m` wins. No new ordering
constant, and a future optic joins the ladder by existing.

**Second-order benefit worth naming** (the brief's point 3, and it is a product argument not a
fidelity one): de-escalating as the run closes *restores* situational awareness exactly when the pilot
most needs Petrovich noticing threats, wingmen, and the next target. A one-way ladder would leave him
staring down a 6° tube over the target at 200 m.

### The gate on the sight, and the ATGM arm

- **The 9K113 is never reached for autonomously.** The ladder may select a sight optic **only** when
  `OpticState.home_phase is OpticPhase.SIGHTING` — i.e. the pilot has already said "Observ on".
  Otherwise the ladder's ceiling is `BINOCULAR_OPTIC` and the `TOO_FAR` age-phrase fallback takes over.
  Designating a target must not turn the sight on (§6, and `2026-10-15-9k113-sight-direction.md` §6).
- **The ATGM arm is shaped for, not built.** §7's mandatory-sight floor with narrow→wide widening has
  no run concept to attach to until the effector entry exists, so the ladder takes its floor and
  ceiling as **parameters** (`floor`, `ceiling`) rather than hardcoding `UNAIDED_OPTIC`/`BINOCULAR_
  OPTIC`. The ATGM case then becomes `floor=SIGHT_WIDE_OPTIC, ceiling=SIGHT_NARROW_OPTIC` — one call
  site, no rewrite. Named here so `BL-B66`/`BL-B67` inherit it instead of rediscovering it.

### Where it lives, and why not in `attack_run`

**`optic_policy` owns the decision; `attack_run` owns the request.**

`attack_run.decide` computes *which optic would resolve this target* — it is the module that knows the
target, its range and its profile, and it already consumes `tier_ranges`' sibling via the cause
taxonomy. It produces a **request**, not a grant.

`optic_policy.decide` grants or refuses it, because only it knows `home_phase` (the OBSERV gate),
`hands_busy_until_sim` (the attention cost), `sight_steady` (the manoeuvre revocation) and the
hands-busy exclusivity rule. An attack run reaching for binoculars **is an optic decision with an
attention cost**, and that cost is `optic_policy`'s whole subject.

Mechanically: a new keyword `guidance_request: Optic | None = None` on `optic_policy.decide`,
defaulting `None` for a bit-identical no-op — the same pattern `sight_steady`, `group_salient` and
`forest` each established in this module. When granted, it **overrides the returned
`OpticDecision.optic`** and leaves the phase machine otherwise untouched.

**Rejected: a new `OpticPhase.GUIDING`.** It is the tidier long-run shape — it would unify the gaze
claim (currently in `logger._active_gaze`, F6) and the optic choice in one phase, which is how this
module expresses "what the eyes are doing" everywhere else. It is rejected *for now* because it means
moving the gaze claim out of `_active_gaze`, which is scope well beyond these four items and lands in
the same files `BL-B66` is about to rewrite for the sight's slew controller. Named as the consolidation
`BL-B66` should absorb, not as a thing to avoid.

### Hysteresis — two guards, both sized against measurement (F3)

1. **Do not re-evaluate while `cause is MASKED`.** Free, falls out of §2, and removes the fly-past
   case — which F3 shows is the only case a band cannot survive.
2. **A fractional margin for *de*-escalation only.** Escalate when `range_m > threshold(current)`;
   de-escalate to rung *n−1* only when `range_m < threshold(n−1) × (1 − GUIDANCE_OPTIC_HYSTERESIS_
   FRACTION)`. **Fractional, not metric**, because rungs are 2.42× apart — a fixed metre band would be
   enormous at the naked-eye rung and negligible at the sight's.
3. **A minimum interval between grants.** `GUIDANCE_OPTIC_MIN_INTERVAL_S`, clocked by
   `guidance_optic_since_sim`.

**Sizing, from the measured numbers rather than invented ones:** at the median −60 m/s a 25% band at
the naked-eye rung is 583 m ≈ 10 s of closing, so recommend `0.25`. Guard 3 must then exceed the time
the *worst observed reversal* (+130 m/s) needs to re-cross that band, which is 4.5 s — recommend
`10.0 s`, which also bounds the worst case to one 1 s blind interval per 10 s (10% duty) against the
`HANDS_BUSY_DURATION_S = 1.0` cost. Both `tuning.real(..., status="agreed-guess")`, uncalibrated like
every perception constant before its first sortie.

**The 1 s gap itself is accepted by direction** — user, verbatim: *"Raising binoculars costs the 1 s
hands-busy interval -> acceptable"*. So: no pre-emptive raise, no deferring the switch to a quiet
moment, no announcement, no attack-run special case on `hands_busy_until_sim`. This is recorded as
**answered**, not open. It raises rather than lowers the stakes on the band, because nothing else in
the design now discourages switching.

### Tier 1 / tier 2 and the ladder

**Confirmed expressible, no new state.** Tier is derived per tick from whether a fresh
`relative_direction` percept exists; binoculars restoring a live look simply means `_tier1_alignment`
returns a value again and the run is tier 1 on that tick. The transition already re-speaks, because
tier 2's qualifier is part of `text` and §1's veto compares `text`. Nothing to add.

### Stages

1. **The pure predicate.** `least_capable_sufficient_optic(range_m, object_type, *, floor, ceiling)`
   in `optic_policy`, built on `tier_ranges`' **presence** threshold. A sibling of
   `improvement_window_m`, deliberately **not** a generalisation of it — that function answers
   "would a look raise this contact's *recognition tier*" over two hardcoded optics, this one answers
   "can the instrument in my hands *see* the thing I am guiding on" over the whole ladder. This
   module's own history (its `LOOK_SWEEP_SIGMA` docstring) is explicitly about not letting two
   different questions share a number.
2. **State + grant.** `guidance_optic`/`guidance_optic_since_sim` on `OpticState`; `guidance_request`
   on `decide`; the OBSERV gate; hands-busy charged on a change; revocation wired into **every**
   existing exit transition (Co-moving Fields).
3. **Hysteresis.** Both guards, with the constants above.
4. **Wiring.** `attack_run.decide` returns the request; `logger` threads it into `decide_optic`.
5. **Sortie.** The acceptance test is the same scenario: single armour, flat desert, run from ~3 km.

---

## Co-moving Fields

Trigger: this extends `optic_policy`'s phase machine (`phase` internal, `home_phase` external,
`hands_busy_until_sim` both) with a continuously-evaluated optic preference and its hysteresis clock,
and adds a co-moving field to `AttackRunState`.

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `AttackRunState.last_spoken_text` | internal (`decide`) | any emitted tick | equals the string just handed to `OutgoingSpeech`; **never written on a `MASKED` tick** |
| `AttackRunState.last_spoken_clock_hour` | internal (`decide`) | any emitted tick | carried via `replace()`, **not** a fresh `AttackRunState(...)` (F4); equals the hour just spoken, or `None` if the utterance was in the qualitative register |
| `AttackRunState.last_spoken_clock_hour` | internal (`decide`) | re-point (`last_contact_id` mismatch) | `None` — a new target's first callout is never a "twelve o'clock" crossing |
| `AttackRunState.last_spoken_tier` | internal (`decide`) | any emitted tick | equals the tier that produced `last_spoken_text`; the two are written in the same `replace()` or neither |
| `OpticState.guidance_optic` | internal (`decide`), from `attack_run`'s request | run engaged | equals the granted optic; `guidance_optic_since_sim == now_sim`; `hands_busy_until_sim == now_sim + HANDS_BUSY_DURATION_S` iff the optic actually changed |
| `OpticState.guidance_optic` | internal | ladder escalates **or** de-escalates | changed only if guard 1 (not `MASKED`), guard 2 (band) and guard 3 (interval) all pass; `guidance_optic_since_sim` re-stamped in the **same** `replace()` |
| `OpticState.guidance_optic` | internal | `disengage` / `drop_target` / run ends | `None`, and `guidance_optic_since_sim is None` — a stale grant must not outlive the run that asked for it |
| `OpticState.guidance_optic` | **external** (pilot "Observ off") | `home_phase` → `SCANNING` | **not a sight optic.** The `SIGHTING` dispatch branch must re-check `home_phase` *and* demote `guidance_optic` in the same transition — this is precisely `BL-B64`'s diverged pair, one level up |
| `OpticState.guidance_optic` | internal (`_force_observ_off`) | `sight_steady` violated | **not a sight optic**, same as above; a violent manoeuvre revokes a sight *grant*, not only the phase |
| `OpticState.home_phase` | **external** (pilot command) | "Observ on" / "Observ off" | unchanged by the ladder. **The ladder may read it and must never write it** — §6's hard gate is that designating a target cannot turn the sight on, and the only way to guarantee that is for `guidance_optic` to have no write path to this field |
| `OpticState.hands_busy_until_sim` | both | any `guidance_optic` change | advanced exactly once per change; a *refused* request (OBSERV off, band, interval) must **not** advance it — refusing costs no hands |
| `OpticState.actual_aim_*` | internal (`advance_sight_aim`) | every fresh-`OpticState` branch | carried forward explicitly, per that field's existing docstring. **The two new guidance fields join this list**, and `_back_to_home` is the branch most likely to drop them |

**The diverged pair to construct a test for, by hand:** `guidance_optic is SIGHT_WIDE_OPTIC` while
`home_phase is OpticPhase.SCANNING`. Every natural test path sets both consistently, which is exactly
why `BL-B64`'s equivalent survived a full test suite and had to be found by a reviewer building the
state manually. Build it manually here.

---

## Risks & Unknowns

- **Deleting the angular clause removes the only drift guard there has ever been.** F1 argues drift
  that matters always crosses a word boundary. If a sortie shows a case it does not, the fix is a
  *coarser* re-assert keyed on the word gates, never a return to a 3° threshold.
- **No max-silence re-assert.** A steady run is now silent indefinitely. Direction §10 and §4's
  design-A silence both say that is correct, but §1's complaint was too *much* talking and the
  opposite complaint is now reachable. Flagged, not designed around.
- **`UNKNOWN` speaks tier-2 guidance with no qualifier at all.** Honest (we do not know why) but the
  pilot cannot distinguish it from a live look. The 8% no-verdict rate is **unquantified** — an earlier
  investigation could not reproduce it from the raw logs — so treat the frequency as unknown.
- **Tests pinning `ATTACK_RUN_CHANGE_THRESHOLD_DEG` must be rewritten, not extended** (escalation rule).
- **The ladder changes what Petrovich sees of the whole world during a run**, which is the one thing in
  this plan that can degrade behaviour outside the feature. It is why `BL-B71` stages behind `BL-B70`.
- **`_spoken_age_phrase` is tuned for the report path**, where ages run to 120 s. Mid-run ages are
  seconds, so nearly every utterance renders *"under a minute old"* — truthful but possibly too blunt
  to be worth the syllables. A sortie question.
- **The ATGM arm is unvalidated.** Parameterising `floor`/`ceiling` is a shape claim, not a tested one.

## Second-order effects

`BL-B70`'s cause taxonomy is the thing `BL-B66`/`BL-B67` will need in order to say anything honest
about why a missile run cannot see its target, so building it now **unblocks** them rather than
narrowing them. `BL-B71`'s `guidance_request` parameter puts a second writer on the optic choice, which
**complicates** `BL-B66`'s warm-up/OBSERV/slew state machine — the Co-moving Fields table above is the
mitigation, and `BL-B66`'s own plan needs that table extended rather than written fresh. F6's
unification (`OpticPhase.GUIDING`) is the consolidation `BL-B66` should absorb while it is already in
those files.

## Staging

**Two entries.** `BL-B70` is four pure-function changes in `attack_run.py`/`speech.py` with no
attention cost, no new state machine, and a measured payoff — 45 of 66 rear-aspect calls and 47 of 125
duplicate utterances, both gone. It can merge and be flown the same day. `BL-B71` changes what
Petrovich can perceive of everything else during a run, needs two tuning constants no sortie has yet
touched, and needs its own flight to validate. Forcing them into one deliverable would hold the cheap,
measured win behind the risky one — and the user flies between stages.

## Decisions Requiring User Input

1. **§4's trigger: literally 1→12 and 11→12, or any entry into the 12 o'clock sector from the o'clock
   register?** *Recommend: any entry.* The pilot's stated reason — not overshooting the turn — applies
   identically however he arrived, and the measured azimuth deltas (up to 11.7° per tick) mean a hard
   turn can skip the adjacent sector entirely, so the literal rule fails exactly when he is turning
   hardest. The literal reading is one `in (1, 11)` check away if you prefer it.
2. **§4's form: a prefix on the same utterance (`"Twelve o'clock, come left."`) or two separate
   utterances?** *Recommend the prefix.* It guarantees §4's ordering without a second speech slot
   competing for the one-voice rule, and it changes `text`, so §1's veto emits it with no special case.
3. **The `TOO_FAR` qualifier wording.** *Recommend reusing `_spoken_age_phrase`* — you named the
   `describe` form and this is it. But mid-run it will almost always render *"under a minute old"*,
   e.g. `"Come left, under a minute old."` If that reads wrong in the air, the alternative is a fixed
   phrase in the same slot (*"too far to make out"*), which is a new vocabulary item — which §8 says
   not to mint. Your call on which cost is lower.
4. **Hysteresis constants: `GUIDANCE_OPTIC_HYSTERESIS_FRACTION = 0.25` and
   `GUIDANCE_OPTIC_MIN_INTERVAL_S = 10.0`.** *Recommend as stated* — both derived from this sortie's
   measured −60 m/s median and +130 m/s worst reversal, not invented. Flagging because they are the two
   numbers in this plan that decide whether the ladder feels steady or twitchy, and no sortie has
   touched either.
5. **§9's home: body-layer only, no aircraft-layer change.** *Recommend as stated* — F5 shows the Hook
   already raycasts the target every second because the wedge follows the run's own gaze, so the
   export-side option would add a belief-identity coupling for no measurable gain. Flagging it because
   it is a cross-subproject boundary call and your §9 wording ("must take priority") could reasonably
   be read as asking for the export-side change explicitly. If you want it anyway, say so and it
   becomes a third entry.
6. **Does an unqualified `UNKNOWN` tier-2 callout need any marker at all?** *Recommend no* — it is the
   fail-open default and adding a word for "I'm not sure why" is the collapse §5 just undid. Raising it
   because the no-verdict rate is unquantified, so the frequency could turn out to be high enough to
   matter.
