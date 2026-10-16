# BL-B72 — A firing unit gives itself away (emitter visibility)

Architect pass, 2026-10-15, against `main` @ `9cb582f`.
Specification: `docs/acceptance/2026-10-15-firing-unit-visibility.md` (the user's own words).
Entry: `body-layer/ROADMAP/BL-B72.md`.

### Goal

Give Petrovich a detection-only path by which a unit's **own emission** — gun fire, a SAM
launch's smoke trail, or a burning hull — makes it detectable at any range out to the player
bubble and through tree cover, without ever raising classification or identification.

---

### The one mechanism, three emitters

The user's three sources differ in channel and lifetime but are **one gate change**. Keeping them
one mechanism is the whole architectural point: body-layer must see *"this object is emitting, and
has been since t"* and nothing about how that was learned.

| emitter | channel | lifetime | owner of the lifetime |
|---|---|---|---|
| `BURNING` | `getLife()`/`getLife0()` per unit, existing 1 Hz bridge | while the fraction is in the fire band | nobody — a polled predicate |
| `FIRING` | `S_EVENT_SHOOTING_START`/`_END` | start → end, latched | the collector |
| `LAUNCH_SMOKE` | `S_EVENT_SHOT` | event + a dissipation constant | the collector |

**Burning is a polled state and therefore exempt from every hard problem the other two carry** (no
latch, no missed burst, no start-without-end, no external lifetime). It needs no new transport
either: `petrobrain-mission-telemetry-hook.lua` already runs an in-state `O(N)` per-unit loop
calling `getVelocity()`, joined body-side by `unit_name`. Adding `getLife()`/`getLife0()` to that
same loop is a field addition, not a mechanism. **So burning stages first and alone**, and the
feature's product value lands before any event plumbing exists. Agreed with the coordinator's read.

#### Where the bypass goes, exactly

`check_visibility`'s chain is unchanged in order and in every gate the user said still applies.
One new per-candidate parameter, `emitter: Emitter | None = None` — resolved by the caller, exactly
the pattern `gaze`/`group_salient` already use, so the join and the set lookup stay out of this
function:

| gate | behaviour with an emitter |
|---|---|
| 0 gaze | unchanged — he must be looking that way |
| 1 cockpit mask | unchanged — he cannot see through the airframe |
| 2 optic FOV | unchanged — *"with optic where FOV allows seeing"* |
| 3 range/size | **bypassed**; the player bubble (`PLAYER_BUBBLE_RADIUS_M`, applied upstream in `filter_player_bubble`) remains the only range bound |
| 4 terrain LOS | unchanged, fail-closed — *"Terrain just blocks LOS"* |
| 5 forest | **bypassed** — *"bright flashes through trees and tracer fire raising from the forest"* |

**The tier clamp is the invariant that makes this detection-only.** If either bypass was used, the
result is forced to `("lowres", NAKED_EYE_PRESENCE_CONFIDENCE)` and `_achieved_tier` is not called.
`_classification_for_tier("lowres", …)` already yields `object_model.DEFAULT_OP_CLASS` at level 1,
so `PRESENCE` falls out of machinery that exists — **no new classification path at all.** If the
candidate would have cleared both gates unaided, the ordinary tier stands: an emitter must never
*lower* what Petrovich can see.

That clamp also answers the in-range forest case correctly without a special rule: a BMP firing
from a treeline at 800 m is seen as *something firing there*, not identified through the canopy.

#### Provenance rides on a field that already exists

`Observation.provenance: str` is a free-form string carrying which filtering produced the
observation (today always `PROVENANCE_VISIBILITY_FILTER_ONLY`). Three new values —
`PROVENANCE_EMITTER_FIRING` / `_LAUNCH_SMOKE` / `_BURNING` — give the callout layer everything it
needs to word the three differently. **No schema change to `Observation`, `Percept` or `Contact`.**

A cluster takes an emitter provenance only when **every** member was emitter-admitted; a mixed
cluster keeps the ordinary value, following `Cluster.classification_raw`'s existing
"identical keeps, disagreement degrades" rule rather than a second one.

---

### Affected Modules / Files

**Stage A — burning (no new transport)**

- `aircraft-layer/dcs-export/petrobrain-mission-telemetry-hook.lua` — add `getLife()`/`getLife0()`
  to the existing in-state per-unit loop and to the payload. One extra `pcall` per unit per second,
  on DCS's own thread (see Risks).
- `aircraft-layer/src/schema/unit_velocity.py` — `life`/`life0` as optional fields on
  `UnitVelocitySample`. The feed is already "per-unit mission-scripting state joined by
  `unit_name`"; only its *name* says velocity (Decision 1).
- `aircraft-layer/src/collector/unit_velocity_receiver.py`, `src/api/server.py` — thread the new
  fields; no new endpoint, no new receiver.
- `body-layer/src/perception/emitters.py` **(new)** — `EmitterKind`, the frozen `Emitter` value,
  `FIRE_LIFE_FRACTION_MAX` (tuning), and `burning_emitters(raw_objects, samples)` returning
  `dict[int, Emitter]`. Pure, fixture-testable, no I/O.
- `body-layer/src/perception/visibility.py` — the `emitter` parameter, the two bypasses, the tier
  clamp.
- `body-layer/src/perception/detection_trace.py` — `DetectionTrace.emitter_kind: str | None = None`
  and `threshold_bound = "emitter_bypass"`, so a live sortie can show *why* a 9 km candidate was
  admitted. Additive, defaults preserve today's rows byte-for-byte.
- `body-layer/src/perception/naked_eye_source.py` — resolve the per-poll emitter map off the
  already-joined samples (same `unit_name` join, same `LOS_MAX_AGE_S`-style skew discipline), pass
  the per-candidate `Emitter | None`, set the provenance.
- `body-layer/src/perception/source.py` — the three `PROVENANCE_EMITTER_*` constants, beside
  `PROVENANCE_VISIBILITY_FILTER_ONLY`.
- `body-layer/src/belief/events.py` + `belief/callouts.py` — `CONTACT_BURNING_SEEN`, its priority,
  its wording (Decision 3).
- `body-layer/src/tuning_defaults.*` (wherever `tuning.real` defaults are registered) — the fire
  threshold.
- Tests: `test_visibility.py`, new `test_emitters.py`, `test_detection_trace.py`,
  `test_clustering.py` (the group-salience non-interaction test below).

**Stage B — gun fire (new event channel)**

- `aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua` **(new)** — productionises
  `petrobrain-damage-events-probe-hook.lua`, which already registered `world.addEventHandler` live
  (`register: ok=true`). Accumulates events in-state, drains per 1 Hz poll.
- `aircraft-layer/src/schema/firing.py`, `src/collector/firing_receiver.py`, `src/api/server.py` —
  new `FiringSnapshot` + `GET /firing/latest`, following `line_of_sight.py`'s shape exactly.
- `aircraft-layer/src/collector/` — **the emitter state machine** (see Co-moving Fields).
- `body-layer/src/perception/aircraft_client.py` — `get_firing_latest()`, with the same
  independently-degradable `AircraftLayerError` → `None` posture the velocity and LOS joins use.
- `body-layer/src/perception/emitters.py` — fold the firing snapshot into the same
  `dict[int, Emitter]`. **Nothing in `visibility.py` changes in Stage B.**
- `belief/events.py`, `belief/callouts.py` — `CONTACT_FIRING_SEEN`, and the `targets_ownship`
  distinction.

**Stage C — SAM launch and its tail**

- The Stage B channel, extended with `S_EVENT_SHOT` and a per-entry `expires_at_sim` from
  `LAUNCH_SMOKE_DISSIPATION_S` (tuning).
- `body-layer/src/perception/naked_eye_source.py` — the frozen-position substitution and the
  synthetic candidate (Decision 4).

---

### Implementation Plan

**Stage A — burning units, end to end (minimal working version)**

1. Life fields onto the existing telemetry hook, schema, receiver and endpoint. No new transport.
2. `perception/emitters.py`: `Emitter`, `EmitterKind.BURNING`, the fire-band predicate.
3. `visibility.py`: the `emitter` parameter, the range and forest bypasses, the tier clamp. Pin
   with tests that a 9 km burning unit is admitted at `lowres` and that the same unit not burning
   is rejected at `RANGE_OR_SIZE` — the regression gate for the whole feature.
4. Wire it in `naked_eye_source.poll`, set `PROVENANCE_EMITTER_BURNING`, extend the trace.
5. `CONTACT_BURNING_SEEN` + wording. **Informational, not a threat line** (Decision 3).

**Stage B — gun fire**

6. The firing-events Hook, drained per poll; the collector's emitter state machine with its latch
   and watchdog; the schema, receiver and endpoint.
7. `emitters.py` folds the snapshot in. `EmitterKind.FIRING`, `targets_ownship`.
8. `CONTACT_FIRING_SEEN`, and *"taking fire"* when `targets_ownship`.

**Stage C — SAM launch**

9. `S_EVENT_SHOT` into the same channel, with `LAUNCH_SMOKE_DISSIPATION_S` and a frozen launch
   position per entry.
10. Position substitution via `dataclasses.replace(candidate, x=…, z=…)` — never fresh
    construction, which is the `BL-B64` lesson — plus a synthetic candidate for the launcher that
    no longer exists.

**Stage D — correctness and live validation (every stage)**

11. The non-interaction tests: an emitter must not widen `group_salient_ids` for its neighbours; an
    emitter must not clear gaze, cockpit mask, optic FOV or terrain LOS; a mixed cluster must not
    take an emitter provenance.
12. One sortie per stage, read through the detection trace's new `emitter_kind` column. Stage A's
    acceptance is the one that retunes `FIRE_LIFE_FRACTION_MAX`; Stage C's retunes
    `LAUNCH_SMOKE_DISSIPATION_S`.

---

### Co-moving Fields

**Step 6a's trigger fires — for the collector-side emitter state in Stages B and C, not for
Stage A.** Stage A has no state at all: the predicate is recomputed from each poll's samples, so
there is nothing to diverge. Stages B and C introduce per-unit state with `kind`, `since_sim`,
`expires_at_sim` and the frozen launch position, written by **two** parties — the DCS event stream
(external) and the collector's own expiry/latch logic (internal) — which is exactly the shape that
produced `BL-B64`'s `phase`/`home_phase` divergence.

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `kind` | external (`SHOOTING_START`) | gun fire begins | `kind is FIRING`, `since_sim` = event time, `expires_at_sim = now + FIRING_WATCHDOG_S`, `frozen_x/z is None` |
| `expires_at_sim` | internal (latch) | `START` and `END` arrive in the **same** drained batch | `expires_at_sim >= now + FIRING_MIN_VISIBLE_S` — a sub-poll burst must survive at least one body-layer poll, or it is invisible |
| `expires_at_sim` | external (`SHOOTING_END`) | gun fire ends, later batch | `expires_at_sim = max(now, since_sim + FIRING_MIN_VISIBLE_S)`; the entry is gone on the next poll at the latest |
| `expires_at_sim` | internal (watchdog) | `START` with no `END` ever | entry removed once `now > expires_at_sim`; **no entry outlives its watchdog**, whatever the event stream does or fails to do |
| all fields | internal | initiator seen as `S_EVENT_DEAD`/`_CRASH`, or absent from `world_objects` | the `FIRING` entry is **removed** (a dead unit is not firing); a `LAUNCH_SMOKE` entry is **kept** — smoke outlives the launcher, and this is the one asymmetry between the two kinds |
| `frozen_x/z` | external (`S_EVENT_SHOT`) | SAM launch | `kind is LAUNCH_SMOKE`, `frozen_x/z` set from the initiator's position **at event time**, `expires_at_sim = now + LAUNCH_SMOKE_DISSIPATION_S`; and `frozen_x/z` is **never rewritten afterwards**, however the unit moves |
| all fields | internal | `onSimulationStart` / mission restart / bridge reconnect | the whole map is **empty**; no entry survives a mission boundary |
| `kind` | both | a unit both fires and burns | one entry per unit; `FIRING` wins over `BURNING` for wording priority, and since Stage A's burning map is recomputed per poll, precedence is resolved **once**, where the two maps are merged in `emitters.py`, never in two places |

The last row is the one that would otherwise bite: burning is stateless and firing is stateful, so
"which emitter is this unit" has two possible answers each poll. Resolving it at the single merge
point is what stops a wording branch and a gate branch disagreeing.

---

### Answers to the five design questions

1. **Where "is firing" lives.** In the **collector**, not body-layer. The collector already owns
   per-feed caches stamped with `dcs_model_time_s` and an event-queue discipline
   (`f10_command_receiver`); body-layer's perception is deliberately recomputed-per-poll and
   stateless (`gaze` is recomputed every tick and never stored, by design), so an
   event-accumulating state machine in `perception/` would be its first stateful input and would
   break replay determinism. Putting it collector-side turns all three emitters into the same
   *polled snapshot* body-layer already knows how to consume. A `START` whose `END` never arrives
   is bounded by the watchdog row above, and cleared outright when the unit dies or vanishes.
2. **What Petrovich says — and a finding that changes the design.** `threat.envelope_for()` keys on
   `ClassificationBelief`. A `PRESENCE`-only contact has `DEFAULT_OP_CLASS`, so it matches no
   envelope, lands in `callouts.py`'s `_DEFAULT_THREAT_BAND = 0`, and is scheduled at the **lowest**
   priority there is. **The existing threat path cannot prioritise an emitter contact, and would
   bury the most urgent thing in the scene.** So the three emitters need their own `EventKind`s with
   priorities set independently of the classification-derived threat band — not a reuse of the
   existing path. `targets_ownship` changes the wording and the priority (*"taking fire, two
   o'clock"* versus *"something firing, two o'clock, far"*). Burning is **not** a threat line at all.
3. **What is believed afterwards.** An ordinary `PRESENCE` contact decaying by `BL-2`'s rules —
   `POSITION_HALF_LIFE_S = 30`, `LOST_THRESHOLD_S = 120` — and nothing more durable. The `and/or`
   resolves to *and not yet*: mission memory does not exist, and inventing a parallel store here
   would be a new abstraction removing no duplication. The provenance already rides on the
   `Observation`, so a later mission memory can derive "shots came from there" without this entry
   guessing its shape. Explicitly **not** changing any global decay constant — a firing position may
   deserve a longer memory than a glimpsed truck, but that is a brain-layer judgement and changing
   `LOST_THRESHOLD_S` would move every contact in the game.
4. **Cardinality — no new machinery.** Existing clustering applies unchanged, and gives the right
   answer for free: at 9 km a firing section's units are angularly unresolvable, so they collapse
   into one cluster with a `count_bucket` — *"several things firing there"*, which is the honest
   report. The caveat worth a test rather than a change: `group_salient_ids` runs over the whole
   bubble pool *before* visibility and relaxes the presence threshold for cohesive groups. **An
   emitter must not widen that for its non-firing neighbours**, or one AAA gun makes a whole convoy
   visible. It does not today, because the emitter path is inside `check_visibility` and group
   salience is computed outside it — pin that with a test so a later refactor cannot quietly undo it.
5. **A burst between two 1 Hz polls.** Not acceptable to lose, and it does not have to be: the
   event handler is an engine callback running *inside* the scripting state continuously, so it
   accumulates into a Lua table and each 1 Hz `dostring_in` drains the batch. A 0.3 s burst arrives
   as a `START` and `END` in the same batch — which the collector must latch for
   `FIRING_MIN_VISIBLE_S` rather than discard as already-over (Co-moving Fields, row 2). **Unrelated
   to `BL-B63`**, despite the surface resemblance: `BL-B63` lowers *latency* on a selected target by
   raising a poll rate, while this needs *no loss* between polls at an unchanged rate. Different
   problem, different mechanism, no shared implementation.

---

### What this entry does *not* do: *"did we get it?"*

**`plans/brain-layer/explore-notes.md`'s open question stays open, and this plan does not touch it.**
User direction, 2026-10-15: *"did we get it is a separate thing, don't close it here. It might be
'we got it' but it might be another unit that somebody else got."*

Seeing a fire is not knowing who caused it. A vehicle killed by a wingman or by artillery reads
identically to the one the pilot shot at, and asserting the link would be exactly the omniscience
the project forbids. **This entry supplies one input a future attribution model could use** —
*something at that location is burning* — alongside inputs it does not supply: what we fired at,
when, and whether a hit followed.

**Concretely, for the wording:** *"that one's burning"* is honest. *"We got it"*, *"target
destroyed"*, *"got him"* are not, and the difference is one word in a template nobody will revisit
once it ships.

---

### Effort / Value

**Stage A is cheap and should be built.** Two fields on an existing bridge loop, one pure predicate,
and the shared bypass that the other two stages then need nothing new from. It lands visible product
value — a burning hull marked at range — before any event plumbing exists.

**Stages B and C are moderate and justified, but not cheap**, and the honest accounting is: a new
Hook, a new schema, a new receiver, a new endpoint, a new client method, and a stateful collector
machine with a latch and a watchdog. The gate change they share is already paid for by Stage A.
Worth it — a unit shooting at the aircraft from 4 km is invisible today, and that is the single
thing most worth telling the pilot about.

**Hot-path cost is not where it looks.** `check_visibility` gains one `dict.get` per candidate per
poll at the caller; emitters are single-digit in any real scene. The bypass pushes more candidates
past gate 3 into gate 4 — a read of an already-joined field, free — while **skipping** gate 5, the
only DB-touching test in the chain. So the body-layer cost is nil to negative. **The real cost is on
DCS's own thread**: the in-state loop gains two `pcall`s per unit per second beside the existing
`getVelocity()` call, roughly doubling that loop's per-unit work. That is the number to measure, not
reason about — `AC-B4`'s still-unmeasured `LoGetWorldObjects` cost is the standing precedent for not
guessing, and the bridge already self-measures `bridge_call_ms`, so the measurement is a log read
rather than a probe.

---

### Risks & Unknowns

- **~~Open: does `S_EVENT_SHOOTING_START` retrigger during a sustained burst?~~ ANSWERED by user
  direction, 2026-10-16** — *"start and end are paired. No unit ever fires for tens of seconds
  straight. They fire bursts."* So the watchdog's remaining case (unit alive, firing past the
  timeout) **does not occur in practice**: fire comes in bursts, each with its own paired start and
  end, and the end arrives. `FIRING_WATCHDOG_S = 180.0` is therefore a pure backstop against a
  genuinely dropped `END` with no death event either — over-generous by design, and harmless,
  because nothing should ever reach it. **Do not tune it down on the grounds that 180 s looks long**:
  its only job now is the case that should never happen, and a short value there is what the
  review's finding was about.

- **`MAX_SIGHTLINES_PER_CALL = 128`, nearest-first, can silently neuter the whole feature.**
  `petrobrain-line-of-sight-hook.lua` sorts the look-wedge's bubble candidates by range and
  truncates, so **truncation drops the far ones** — precisely the emitters this feature exists to
  admit. Gate 4 is fail-closed, so a truncated far emitter gets `live_los_clear = None` and is
  rejected, with no indication that the reason was a cap rather than terrain. In a scene with ≥128
  units in the 180° look wedge, the feature stops working and looks like it was built wrong.
  **Mitigation, cheap and worth doing in Stage B**: splice the current emitter ids into the LOS
  call's sort key so they are never truncated. The wedge itself is fine —
  `LOOK_DIRECTION_FOV_HALF_DEG = 90` is far wider than the 15° gaze focus cone, so anything that
  clears the gaze gate is inside it.
- **This introduces the first exception to the forest gate, and an open plan says there are none.**
  `plans/forest-occlusion/plan.md` describes gate 5 as *"flat and binary, no directionality"*, and
  its Stage 3 (flip the live default on) is still open and pending a flown A/B. The two do not
  conflict mechanically — an emitter skips the gate, it does not weaken it for anything else — but
  that plan's own description stops being complete the moment this one merges. **At merge, add a
  numbered sub-decision there** (`Decision N REVISED`, `docs/PROCESS.md`) rather than editing the
  original sentence.
- **Position uncertainty at 9 km.** `look_sigma_m(range, optic)` applies per-look noise that scales
  with range, so an emitter sighting's position estimate will be coarse. That is honest, not a
  defect — but the callout must not imply a precision the estimate does not have, and nobody has
  looked at what that sigma actually is at 9 km through the naked eye. Read it before writing the
  wording.
- **The fire band is a bracket, not a number.** `(0.69, 0.84]`, measured, with the exact value
  inside it and whether it is global or per-type unresolved. Handled as `tuning.real(…,
  status="assumption")` at the band's midpoint, which is a stated assumption a sortie retunes — not
  an open question and not a reason to probe again.
- **`LAUNCH_SMOKE_DISSIPATION_S` is wrong in both directions** and only a sortie settles it: too
  short and the pilot never gets the warning, too long and Petrovich keeps pointing at smoke.
  `tuning.real`, `status="judgement"`.
- **`world.addEventHandler` reachability from the `"scripting"` state** was confirmed live by the
  2026-09-25 probe (`register: ok=true`). It is *not* re-derived here and no probe is outstanding —
  but it was confirmed by a probe Hook, not by production code, and `AC-B5` records that a probe
  Hook left deployed taxes every sortie. Stage B must ship as a production Hook, not by promoting
  the probe.
- **Which units the bridge's in-state loop iterates.** The existing loop covers live units and
  skips statics (no velocity API). Burning statics and firing statics are therefore invisible, which
  may be right or may be a gap nobody has looked at.
- **Unit `getLife()` for a unit outside the bubble** is still read by the in-state loop, which is
  theatre-wide. That is a provenance concern, not a leak — the emitter map is intersected with the
  bubble-filtered candidate list before any gate sees it, and the LOS/gaze/mask gates still stand.
  Worth one explicit test: no emitter ever bypasses a gate the user said still applies.

---

### All four ANSWERED — user direction, 2026-10-15

| # | question | answer |
|---|---|---|
| 1 | life/burning fields: existing feed or new endpoint? | **existing** — ride `/unit_velocity/latest` |
| 2 | split `BL-B72` three ways? | **split** — `BL-B73`, `BL-B74`, `AC-B7`, `AC-B8` stand |
| 3 | callout wording | **proposals accepted as drafted** |
| 4 | does the smoke trail outlive the launcher's world object? | **yes**, built that way from the start |

**On 3**, the accepted forms, each claiming presence only and none implying attribution:

| emitter | callout |
|---|---|
| gun fire, not at us | *"something firing, two o'clock, far"* |
| gun fire, event names us | *"taking fire, two o'clock"* |
| SAM launch | *"launch, two o'clock"*, then *"smoke trail, two o'clock"* |
| burning unit | *"something burning, two o'clock"* |

**On 4**, the consequence to build for rather than discover: a launcher destroyed seconds after
firing is the **normal** case under attack, so the smoke record must be able to mint its own
candidate rather than annotating a live one. A version that works only while the launcher survives
would fail in exactly the engagement that matters.

**Implementation authorised** the same message: *"Go ahead and implement"*. Stage A (`BL-B72`,
burning) plus `AC-B7`'s transport is the first slice; `BL-B73`/`BL-B74` wait on `AC-B8`.

### Decisions Requiring User Input

1. **Does the burning/life data ride on the existing `/unit_velocity/latest` feed, or get its own
   endpoint?** *Recommendation: ride on the existing feed.* It is already "per-unit
   mission-scripting state joined by `unit_name`" and only its name says velocity; reusing it means
   no new hook, receiver, endpoint, client method or join — the whole of Stage A's transport cost
   disappears. The cost is a feed whose name is narrower than its content, noted in its docstring.
   A rename with a compatibility alias is the alternative and is pure churn across two subprojects.
2. **Is `BL-B72` split into three roadmap entries, or kept as one with three stages?**
   *Recommendation: split.* Stage A ships without the event channel and should not be blocked behind
   it. Proposed, with IDs minted per the directory recipe: `BL-B72` keeps the shared bypass plus
   burning; **`BL-B73`** gun fire; **`BL-B74`** SAM launch and its tail; **`AC-B7`** life fields on
   the existing bridge; **`AC-B8`** the firing-event channel. Entry files are drafted and staged on
   this branch — say the word and they stand, or they come out in one commit.
3. **The wording for the three callouts.** This is product voice and I will not pick it. My
   proposals, each deliberately claiming only presence:
   - firing, not at us — *"something firing, two o'clock, far"*
   - firing at us — *"taking fire, two o'clock"*
   - launch — *"launch, two o'clock"*; after the event, *"smoke trail, two o'clock"*
   - burning — *"something burning, two o'clock"* — and never *"we got it"* / *"target destroyed"*.
4. **Does the SAM smoke trail outlive the launcher's world object?** *Recommendation: yes, and build
   it that way from the start.* A launcher destroyed seconds after launch is the normal case under
   attack, and the smoke physically hangs regardless. It costs a synthetic candidate minted from the
   emitter record when no live world object matches — about a dozen lines — and the alternative is a
   feature that works only when the launcher survives, which is the less interesting half.
   Say no and Stage C substitutes the frozen position onto the live candidate only.
