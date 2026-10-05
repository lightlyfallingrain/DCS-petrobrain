### Goal

Ask DCS for line of sight directly (terrain + buildings, batched, true position to true position,
at the aircraft layer) instead of approximating it from world-model's own SRTM elevation grid, and
use our own model only for *detectability* (angular size, optic, conditions, salience) on top of
that answered fact. The boolean is computed collector-side from true positions, reaches perception
as one more piece of joined unit data (the same shape movement detection already established), and
belief never computes LOS itself — it remembers what perception observed, exactly as it already
does for classification, cardinality and motion.

**Revision note (this pass, 2026-09-29):** three user corrections landed on this plan after the
first draft, as appended sections that argued against the body and against each other. This
revision folds their conclusions into one coherent design and restages the plan around it —
collector-side computation first, because that is now the foundation every consumer sits on, not a
supporting detail of a body-layer feature. Nothing in this revision changes the measured costs,
the buildings-before-terrain ordering, or the trees findings — all of that stood up to the
corrections and is carried forward as-is.

### Starting premise, corrected before this plan

The dispatch brief stated "trees have no DCS route at all" as settled. It is not, in the strong
form. The user's own evidence: the F10 map renders individual trees, flying into one crashes the
aircraft (collision geometry per tree), and DCS's own AI Petrovich with the 9K113 is blocked by
trees — so a shipped code path performs tree-occluded LOS against a specific target. What the
Windows investigation actually settled is narrower: **`world.searchObjects` never returns a tree
object, and `land.isVisible` is terrain-only.** Those two scripting-API calls exclude trees.
Whether any *other* exposed call reaches the engine's own tree-aware path was open when this plan
was drafted; the user has since reframed the requirement (see "Trees" below) and fixed a fallback
in advance, so it no longer blocks anything here.

> **READ THE 2026-10-05 REVISION AT THE END OF THIS FILE FIRST.** The costs are measured now rather
> than extrapolated, and the binding constraint turned out to be *per-call batch size*, not call
> frequency. Every cost figure in the body of this plan (0.5 ms fixed overhead, 8.7 µs/sightline,
> "0.2–0.5% duty at 1 Hz") is superseded there. Sections carrying a superseded claim say so inline.
>
> **Also superseded: everything this plan says about world-model's offline LOS primitive.** The user
> relaxed the offline requirement to *fixtures only* on 2026-10-05, which makes agreement with DCS an
> explicit non-goal and moves post-flight LOS analysis into the detection trace. Revision §3.

### Effort/value check first

**Re-read 2026-10-05 against the measured numbers: the balance is unchanged — see Revision §0.**

**The specific defect this was proposed to fix already has a shipped mitigation.** The debug
report (`plans/missed-aaa-detection/debug.md`) diagnosed a real miss — SRTM overestimating terrain
under a real unit's position placed it permanently "underground" to the model — and Fix option 1
(a 12 m tolerance on the terrain check, sized to M7's own recorded SRTM-vs-DCS stddev) is **already
merged** into `world-model/src/query/line_of_sight.py` (`_TERRAIN_TOLERANCE_M = 12.0`, with a long
comment carrying the Mi-24P-specific justification for that number). So this plan's value is not
"stop missing AAA that DCS-driven LOS would have caught" — that class is already closed. Its real,
smaller value is:

1. Removing reliance on a *guessed* error margin for terrain, by asking DCS for ground truth
   instead of interpolating a 1000 m SRTM grid. The 12 m tolerance still lets through false
   negatives beyond its own margin (the reproduction table showed +20 m still blocking); DCS's own
   terrain has none of that error, at any margin.
2. **Building occlusion, which does not exist today in either path.** This is new capability, not
   a fix — and it is the cheaper, lower-risk, higher-value half of this plan.

Recommendation, unchanged by the corrections: ship building occlusion first (new, additive, cannot
regress anything that works today) and treat the terrain-source swap as a second, independent,
lower-urgency stage — not "this is all one bug fix that must land together."

### The model

```
DCS answers "is there terrain/a building in the way, between the two real positions?" (a physical
fact, computed true-to-true)
        -> our own model answers "can Petrovich actually detect this?" (angular size, optic,
           conditions, salience — check_visibility's existing gates, unchanged)
        -> belief remembers whether that fact held the last time this contact was actually
           observed, and forgets it the same way it forgets everything else it hasn't looked at
           recently.
```

Nothing here grants Petrovich new knowledge: LOS is a fact about the physical world (a ray either
crosses geometry or it doesn't), not information about a unit's identity or position that he could
not otherwise derive. This project's no-omniscience invariant is about identity/position/
interpretation, and this plan touches none of those — it is stated explicitly, per call site, in
the section below.

### Where the boolean is computed, how it reaches perception, and how belief carries it

**This is the section three separate corrections landed on. What follows is the settled design,
not a debate.**

**1. The collector computes LOS per unit, true ownship position to true unit position.** Every
unit aircraft-layer already knows about from `LoGetWorldObjects`, excluding ownship
(`is_ownship`), filtered to the 10 km player bubble around ownship's current position — the same
radius body-layer's detection pipeline is already scoped to (`todo/todo.md`, "Player bubble: 10
km, settled 2026-09-28"). Batched through the mission bridge in one call per poll, `world.
getPlayer()` for ownship truth, `LoGetWorldObjects`-derived truth for each unit — both already
available to the Lua side, per the measured probe work below.

**Why it must be true-to-true, not believed-to-true.** The user, rejecting an earlier draft of
this plan that asked the question against the contact's *believed* position:

> *"Whether we can see a target, LOS or no LOS, is a world state **fact**. It is not a belief. Our
> belief about a unit's location is belief and can be wrong. It in no way affects LOS, it is a
> property of the simulated world, a 'physical' fact even though simulated. LOS **must use** the
> unit's **factual** location and our ownship's **factual** location. Belief is in a layer above
> all this."*

A line of sight to a point where nothing stands is not a preserved error, it is a fabricated
answer to a question about empty space. The ray either clears real geometry between two real
points or it does not. **Recorded wrong turn, kept rather than deleted because it would have read
as principled**: an earlier draft asked the engagement term to query point-to-point using the
contact's *believed* position, and called preserving that error a feature — a plausible-sounding
argument for a design that produces a verdict corresponding to no physical fact at all. Rejected;
not revisited.

**2. The boolean reaches body-layer as one more piece of joined unit data — a second endpoint, not
a merge into `/world_objects/latest`'s own payload.** The user's own framing:

> *"bake 'LOS / no-LOS' boolean into unit data transmitted from collector. Then belief system can
> use that information without doing its own bogus calculations."*

That intent is honored at the point where "unit data" actually means something to a consumer: once
`naked_eye_source.py` has joined it onto a `WorldObjectCandidate`, exactly as velocity already is.
It is **not** honored by folding the field into `/world_objects/latest`'s own JSON, and that is not
a new judgment call — it is `plans/movement-detection/plan.md` Decision 2, already made and
already documented in `aircraft-layer/src/api/server.py`'s own module docstring:

> *"A **separate endpoint from `/world_objects/latest`, not merged into it**: merging would mean
> either holding a world-objects snapshot back until a matching velocity snapshot arrives, or
> emitting one timestamp for two feeds whose sim-clock stamps genuinely differ (5 Hz vs. 1 Hz
> polls) -- silently destroying the provenance the dual-clock schema exists to preserve. The join
> (by `unit_name`, within a skew bound) is `perception.motion`'s job on the body-layer side, not
> this layer's."*

LOS is exactly this shape again: computed by a 1 Hz Hook-script bridge call (mission-scripting
environment, `world.*`/`land.*`), while `/world_objects/latest` is Export.lua-native at 5 Hz. The
same reasoning that kept velocity a sibling endpoint applies unchanged to LOS, and reusing it
rather than re-deciding it is the point of writing this down. So: new `GET /line_of_sight/latest`
endpoint, new schema, new cache, joined client-side by `unit_name` — see "Wire shape" below for the
concrete shapes, which is the one section of the pre-correction draft that needed no revision.

**3. Perception consumes it as a gate input**, at `visibility.check_visibility`'s gate 4, replacing
that gate's own terrain-only computation for the live path. This is pre-boundary
(`WorldObjectCandidate.object_id` still carries ground-truth identity here), where identity
legitimately exists — the same seam `perception.association`/`perception.naked_eye_source` already
own.

**4. Belief never computes LOS.** The observed value rides into the `Percept` for whichever
contact this poll's admitted naked-eye observation belongs to, and is carried on the `Contact` as
a last-known property, the same pattern classification and motion already use — see "What changes
in body-layer" below for the exact field, fold rule, and staleness handling.
`belief/contacts.py::tick`'s engagement term **reads** that stored value instead of calling
`line_of_sight_clear` — or any callable at all — the way it does today. The user, rejecting the
draft's conclusion that the engagement term was structurally locked out of this by the
no-omniscience boundary:

> *"No. With cheap access to DCS calculated LOS, that is the world truth and we must use that. LOS
> is not a question of belief, it is a property of the DCS world state. If LOS exists and other
> detection criteria pass, we can see it."*

**Why this is not a boundary violation, and why it is not merely a delegation either.** The
engagement term's question ("can the threat see us") and the detection gate's question ("can we
see the threat") are the *same ray test* run in the opposite conceptual direction: LOS is
symmetric — a sightline either crosses geometry or it doesn't, independent of which end is asking.
So the moment gate 4 admits a naked-eye observation of a contact, that admission is itself proof
the ray was clear at that instant, in both directions at once. Belief does not need to re-derive
this: it only needs to remember it, the same way it remembers "last seen moving north" without
re-deriving the physics that produced that observation. A contact currently being freshly observed
therefore always carries a *true* LOS fact (not a guess), and a contact that has gone quiet decays
to *unknown* — which the engagement term already treats as "assume the threat can see us" (see
`LOS_MASK_CONFIRM_S`'s existing fail-open direction below), the conservative default this codebase
already prefers everywhere a signal is missing rather than merely stale.

**The no-omniscience boundary, stated at the seam where it is easiest to lose:** the collector's
LOS computation is DCS-object-keyed and identity-bearing; it may only cross into body-layer at
`naked_eye_source.py`'s join (pre-boundary, alongside `object_id`, exactly where velocity already
crosses). It may reach `belief/contacts.py` **only** as a value already carried on a `Percept`,
never as a DCS-keyed lookup a `Contact` could perform on demand — `Contact` still cannot carry a
DCS object id, and this plan does not change that. Nothing the collector knows about a unit's
*identity* or *true position* reaches belief; only the yes/no fact of whether a ray it already
looked at was clear.

### What exactly is asked, and for which units

Same bubble and same "no cone filtering" reasoning as originally drafted, unaffected by any of the
corrections:

**No cone filtering, deliberately, despite the user's own framing ("within the 130 degree
visibility cone").** Reading `check_visibility`'s gate chain settles what that number actually is:
it is not a separate cone concept, it is the co-pilot cockpit mask's own rear cutoff
(`cockpit_mask.py`, `rear_cutoff_deg=130.0`, an *asymmetric*, elevation-varying envelope, not a
simple cone — `gaze.py`'s own docstring calls out exactly this distinction). Two reasons not to
replicate any version of that shape in the Lua bridge script:

1. **LOS itself is gaze/attitude-independent** — this is the missed-AAA debug report's own finding
   (gate 4 "is not gaze- or attitude-dependent — it is purely a function of the unit's fixed
   `(x, z)` position"). Pre-filtering by a cone would only ever be a cost optimization, never a
   correctness requirement.
2. **It is not needed as a cost optimization either.** The measured cost table (`aircraft-layer/
   research/2026-09-29-bridge-terrain-probe-results.md` Finding 21, ~8.7 µs/sightline for
   buildings) already gives 500 units in one 10 km bubble at 4.9 ms — under 0.5% duty at 1 Hz.
   **SUPERSEDED by Revision §1 (2026-10-05): duty cycle is not the constraint, single-call cost is,
   and a 500-sightline call is ~12 ms — a dropped frame. The conclusion (no cone filtering) survives;
   the reason changes, and a per-call cap replaces it as the control.**
   Duplicating body-layer's cockpit-mask/gaze logic in Lua, across the seam, to shave an
   already-cheap number, is complexity with no measured benefit.

So: bubble-only filtering, done once per poll inside the Lua snippet (distance check against
ownship's own true position, the same self-contained shape `petrobrain-mission-telemetry-hook.lua`
already uses for enumerating units — no argument passing needed from the collector).

### Cadence

**Re-derived 2026-10-05 against the batch-size finding — conclusion unchanged (1 Hz), and the
batch-size finding is what *forbids* raising it. See Revision §2.**

1 Hz, riding the same `dostring_in("scripting", …)` / Hook-script pattern
`petrobrain-mission-telemetry-hook.lua` already runs at 1 Hz for unit velocity. The user's own
"maybe not every tick?" is answered from the physics, not the cost: at 83 m/s (the backlog entry's
own figure) LOS state changes over seconds, and body-layer's naked-eye poll is 5 Hz — so a verdict
up to ~1-2 s old is not stale relative to how fast the underlying fact actually changes. No new
cadence concept is introduced; this is a fourth sibling to the existing telemetry/world-objects/
indication feeds, joined the same way velocity already is.

### Wire shape and the join key that makes staleness precedented, not new

Unaffected by the corrections — this is the one section of the original draft that stayed correct
throughout, and the reasoning above ("Where the boolean is computed…", point 2) is exactly why.

New Lua script `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`, structurally a sibling
of `petrobrain-mission-telemetry-hook.lua` — own loopback port, own `onSimulationStart/Frame/Stop`
lifecycle, own fixed code-literal snippet run via `dostring_in`, `timer.getTime()` stamped inside
the scripting state (never `DCS.getRealTime()`, for the same replay-determinism reason that file's
header already gives). The snippet enumerates units the same way `VELOCITY_CODE` does
(`coalition.getGroups`/`getUnits`), filters to the bubble, and for each survivor runs the sightline
test (Stage 1: buildings only; Stage 3 adds terrain — see staging below), packing
`"unitName:losClear01;..."` the same delimited-string-in-JSON-envelope shape every other bridge
feed here uses.

**Join key: `unit_name`, not `object_id`.** `object_id` is `LoGetWorldObjects`'s `pairs()` key,
explicitly flagged in `aircraft-layer/src/schema/world_objects.py`'s own docstring as
"unconfirmed" for cross-poll stability. `unit_name` (`Unit:getName()`, matching
`LoGetWorldObjects`'s `UnitName`) is the join key movement detection already established for
exactly this same cross-feed problem (`plans/movement-detection/plan.md` Decision 1,
`naked_eye_source.py::_resolve_velocity_by_object_id` — a misleading name for what is actually a
unit-name join, kept as-is rather than renamed mid-plan). This plan reuses that precedent rather
than inventing a second one: a new `_resolve_los_by_unit_name` follows the same shape — join this
poll's `/line_of_sight/latest` snapshot onto the raw `/world_objects/latest` dicts by `unit_name`,
computing a skew (`|world_objects_t_sim - line_of_sight_t_sim|`) exactly as `_resolve_velocity_by_
object_id` already computes `motion_skew_s`, and dropping to `None` when that skew exceeds a new
`LOS_MAX_AGE_S` constant (proposed 3.0 s — three poll cycles at the feed's own 1 Hz rate, mirroring
`brain-layer`'s D4 pattern of comparing a carried-through sim timestamp against "now" and
discarding what's too old, `crew_console.py`'s `BRAIN_REPLY_MAX_AGE_S`). The result lands on a new
optional field, `WorldObjectCandidate.live_los_clear: bool | None` — `None` means "no live verdict
this poll (feed absent, unit not in the bubble that poll, or too stale)," never coerced to a
guessed true/false, same tri-state discipline every other joined field in this module already
follows (`is_ownship`, `velocity`, `heading_true_deg`).

`check_visibility`'s gate 4 becomes:

```python
if candidate.live_los_clear is not None:
    if not candidate.live_los_clear:
        _record(GateOutcome.TERRAIN_LOS)
        return None
elif not line_of_sight_clear(conn, theatre, observer, target):
    _record(GateOutcome.TERRAIN_LOS)
    return None
```

No new parameter on `check_visibility` itself — the join already happened upstream in
`naked_eye_source.py`, exactly where velocity's join already happens, so this function only ever
reads a field off the candidate it was already handed. **Default behaviour (aircraft-layer feed
absent, as in every test and the replay harness) is unchanged**: `live_los_clear` stays `None`
forever if nothing populates it, and the `elif` branch is today's code, untouched.

### What changes in body-layer, and what is deleted

**New field: `Contact.live_los_clear: bool | None = None`.** Set unconditionally from the incoming
`Percept.live_los_clear` in `record()`/`from_percept()` — an overwrite, not a fold, the same
semantics as `last_class_raw` (a raw most-recent-look value) rather than `classification`'s
monotone specificity lattice. There is no ordering or specificity relation between "clear" and
"masked" to fold over; it is a plain fact about the most recent look, nothing more.

**Staleness reuses existing machinery rather than adding a bespoke half-life.** `Contact` already
distinguishes "currently being perceived" from merely "recently tracked" via `decay.
OBSERVED_WINDOW_S` (16.0 s, re-derived from the naked-eye scan cycle — `belief/decay.py`). LOS is a
fast, physically transient fact exactly like the thing that window already gates, and reusing it
avoids inventing a second, uncalibrated threshold for the same concept: the engagement term treats
`live_los_clear` as meaningful only while `now_sim - contact.last_seen_sim <= OBSERVED_WINDOW_S`,
and as unknown otherwise — not because it decays on its own timer, but because it was never
observed to begin with once the contact has gone quiet. This is the "already has machinery for
exactly that" the dispatch brief pointed at; it did not require adding a sixth half-life to
`decay.py`.

**The engagement term's block in `ContactStore.tick` (`plans/watch-reporting/plan.md` Decision
4/5a-ii) keeps its existing masking-dwell logic untouched, fed a different input:**

```python
elif contact.live_los_clear is None or (now_sim - contact.last_seen_sim) > OBSERVED_WINDOW_S:
    # No fresh live verdict -- correct degradation is fail-open, same
    # posture as "no world-model connection" today.
    los_ok = True
    contact.los_masked_since_sim = None
elif contact.live_los_clear:
    contact.los_masked_since_sim = None
    los_ok = True
else:
    if contact.los_masked_since_sim is None:
        contact.los_masked_since_sim = now_sim
    masked_for_s = now_sim - contact.los_masked_since_sim
    los_ok = masked_for_s < LOS_MASK_CONFIRM_S  # Decision 5a-ii, unchanged
```

`LOS_MASK_CONFIRM_S` and `Contact.los_masked_since_sim` are **not new** — they already exist
(`plans/watch-reporting/plan.md` Decision 5a-ii, `belief/decay.py`) and needed no change; only the
signal feeding them moves from a live per-tick query to a carried observation.

**Deleted, because belief genuinely stops computing LOS rather than delegating it:**

- `_threat_has_los()` (`belief/contacts.py`) — the three-point uncertainty sweep against a believed
  position has no remaining caller once the geometry is ground-truth and pre-computed; there is
  nothing left to sweep.
- `ContactStore.tick`'s `los_clear: Callable[[GeoPosition, GeoPosition], bool] | None` parameter,
  and `logger.py`'s closure that builds and passes it (`src/logger.py` ~lines 506-517, plus the
  `line_of_sight_clear` import there used only for this purpose).
- `LOS_UNCERTAINTY_SAMPLES` (`belief/contacts.py`) — documented the sweep's sample count; nothing
  reads it once the sweep is gone.

**Narrower than the pre-correction draft, and worth stating as a real finding rather than a
tidy-up:** the earlier draft still had `contacts.py::tick`'s engagement term calling world-model's
`line_of_sight_clear` forever, unaffected by this plan. That is no longer true. After this plan,
world-model's `line_of_sight_clear` has exactly one live caller left in body-layer —
`visibility.check_visibility`'s gate 4, and only on its fallback branch when the live feed is
absent.

### What this leaves of world-model's `line_of_sight_clear`

**AMENDED by Revision §3 (user direction, 2026-10-05): this is now permanent *and narrower than
"offline/test path" suggests* — it serves fixtures only, and agreeing with DCS is an explicit
NON-GOAL. Recreating a real sortie's LOS offline is not attempted; the detection trace records what
DCS said instead. Read §3 before assuming any divergence here is a defect.**

The offline and test path, unchanged and still first-class — Mission Interpreter enrichment, the
replay harness, and every test that must run with no DCS and no collector (`plans/body-layer/
plan.md` §2). It also remains gate 4's own fallback when the live feed is absent (test fixtures,
the replay harness, a collector that hasn't started the LOS hook yet). It is **not** deleted and
**not** deprecated — see "Risks & Unknowns" for one consequence of narrowing its live footprint to
a single call site.

### What happens to the 12 m tolerance and the probe grid

Unchanged, and this plan does not touch either. `_TERRAIN_TOLERANCE_M` and world-model's
`line_of_sight_clear` remain the offline/test path and gate 4's fallback — both real, permanent
uses, not a stopgap this plan replaces. The probe grid (M8) and its spacing redesign stay exactly
where `todo/backlog.md`'s X-B28 (superseded) already left them: lower priority, for land
formations/`describe_position`, not line of sight. Nothing here changes that.

### Trees

The user reframed this after the plan's first draft, and the reframing is now the settled
position, not an open question:

> *"'vehicle under trees is undetectable at any range from any optic' — in a forest, yes very much.
> But if it's just a couple of trees or a line of trees along a road, then tree LOS really matters.
> We must investigate if there is any way to get LOS considering trees. We don't need to know
> individual tree placement (though that wouldn't hurt and could be useful), but need to know if
> they block LOS. If we can."*

Two distinct tree problems, only the first covered by a landcover model:

1. **Forest** — a mass of canopy, where the honest model is probabilistic transmission over an OSM
   polygon and the answer is "he cannot see in there." The measurement supports this.
2. **Sparse and linear tree cover** — a treeline along a road, a windbreak, a handful of trees
   between the aircraft and a vehicle. A polygon model answers this *wrongly in both directions*
   (OSM may carry no polygon at all for a roadside treeline; where it does, a probability over an
   area cannot express "this sightline is blocked and the one ten metres left is not"). This is
   **discrete occlusion**, the same shape as the building test, and exactly the case a Mi-24P
   attacking along a road meets constantly. The user's acceptance bar here is a bare blocked/clear
   verdict — individual tree placement would be a bonus, not a requirement.

**Fallback settled in advance, before any probe result comes back:** *"If there's no way for tree
aware LOS, then we'll take the statistical model instead."* So the probes below are not a gate — a
negative result selects the OSM-landcover transmission model, and the sparse/linear-treeline case
becomes a known, accepted limitation of that model rather than an unsolved problem. The decision
was taken before the result on purpose, so a negative does not get relitigated as a failure.

**Not resolved, and this plan does not resolve it.** Established: `world.searchObjects` never
returns a tree object across ten flights (not a scenery object, no volume search will find one),
and `land.isVisible` is confirmed terrain-only (the SEGMENT-through-known-buildings control,
`aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md` Finding 12). Also established:
the F10 map renders individual trees, tree collision exists per-tree, and DCS's own AI Petrovich
with the 9K113 is blocked by trees — so the engine holds tree geometry and at least one shipped
code path (`Scripts/AI/Detection.lua`'s `trees_LOS_test_T4`, feeding `Controller.isTargetDetected`/
`getDetectedTargets`) tests LOS against it. The open question is narrow: **is there any
scripting-API call that reaches that same tree-aware geometry, as opposed to the terrain-only
surface `land.*` exposes?**

Named follow-up for the Windows-box session, not this plan's build work:

1. **Characterise `Controller.isTargetDetected`/`getDetectedTargets`** even though it is probably
   the wrong shape to consume directly — a controlled pair (identical target, once with trees
   between observer and target, once without) settles whether it reaches the tree test at all, and
   if so whether its skill/alertness/range/reaction-time terms can be pinned to a pure-LOS-oracle
   configuration or are inseparable from the result.
2. **Fire `land.getIP` along a sightline into known tree canopy** — if the returned impact point
   sits at canopy height rather than bare-ground height, `getIP` is sensing something above the
   terrain mesh there, worth knowing even if it turns out to be a height-field artifact.

**If neither resolves it**, the interim stand-in is the OSM `landcover` polygon set world-model
already holds (44,811 polygons) — built as a probabilistic transmission model per optic, a
genuinely different mechanism from the SEGMENT/`isVisible` tests this plan builds, not a variant of
them, so a later tree-aware call can replace it outright rather than needing to be fused with it.
**Not built in this plan.** File as its own backlog item once the two probes above report back.

**It does not change the staging below.** Buildings (Stage 1) are unaffected, measured and ready;
trees ride a parallel investigation rather than blocking it.

### Affected Modules / Files

- `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` — new. Sibling Hook script to
  `petrobrain-mission-telemetry-hook.lua`; Stage 1 tests buildings only (`world.searchObjects` +
  `world.VolumeType.SEGMENT`), Stage 3 adds terrain (`land.isVisible`).
- `aircraft-layer/src/schema/line_of_sight.py` — new. `LineOfSightVerdict`
  (`unit_name`, `clear`, `dcs_model_time_s`, `received_wall_clock_s`) and `LineOfSightSnapshot`,
  mirroring `world_objects.py`'s shape.
- `aircraft-layer/src/collector/cache.py` — new `LineOfSightCache`, same shape as
  `UnitVelocityCache`.
- `aircraft-layer/src/collector/__main__.py` — wire the new receiver/cache in, alongside the
  existing ones.
- `aircraft-layer/src/api/server.py` — new `GET /line_of_sight/latest`, same "separate endpoint,
  not merged" posture as `/unit_velocity/latest` (see "Where the boolean is computed" above).
- `body-layer/src/aircraft_client.py` — new `get_line_of_sight_latest()`, same shape as
  `get_unit_velocity_latest()`.
- `body-layer/src/perception/naked_eye_source.py` — new `_resolve_los_by_unit_name` (mirrors
  `_resolve_velocity_by_object_id`), wired into the same poll step that already resolves velocity;
  new `LOS_MAX_AGE_S` constant.
- `body-layer/src/perception/association.py` — `WorldObjectCandidate` gains
  `live_los_clear: bool | None = None`.
- `body-layer/src/perception/visibility.py` — gate 4 reads `candidate.live_los_clear` first,
  falls back to `line_of_sight_clear` unchanged when `None`.
- `body-layer/src/perception/source.py` — `Observation` gains `live_los_clear: bool | None = None`,
  set by `naked_eye_source.py` only for admitted candidates (never by the hybrid channel, which has
  no geometric gate to source it from).
- `body-layer/src/belief/percept.py` — `Percept` gains `live_los_clear: bool | None`, carried
  straight through from `Observation` in `percept_of`.
- `body-layer/src/belief/contacts.py` — `Contact` gains `live_los_clear: bool | None = None`, set
  in `record()`/`from_percept()`. `tick`'s engagement term reads it per "What changes in
  body-layer" above; `_threat_has_los`, the `los_clear` parameter, and `LOS_UNCERTAINTY_SAMPLES`
  are **deleted**.
- `body-layer/src/logger.py` — the LOS closure passed to `store.tick(..., los_clear=...)` is
  **deleted**; `store.tick(ownship.t_sim, ownship=ownship)` no longer takes a third argument for
  this purpose. `world_model_conn` remains required for enrichment/`describe_position`/gate 4's
  fallback — this removes only its one LOS-specific use site.
- `world-model/src/query/line_of_sight.py`, `body-layer/src/perception/geometry.py` — **unchanged**
  except in role: still gate 4's fallback and the offline/test/Mission-Interpreter path, no longer
  called anywhere in `belief/`. Named here so a reader checking "what did this plan touch" sees the
  negative confirmed, not merely absent.

### REVISION (user, 2026-09-29): one hook computing both verdicts, published as two fields

The staging below deploys the Hook script twice — buildings in Stage 1, terrain added to the same
snippet in Stage 3. The user questioned whether those are really separate:

> *"The DCS LOS calculation that detects a blocking building should also detect blocking terrain,
> right? So that would be 1 and 3 in the same call, no?"*

**Half right, and the half that is wrong is worth stating precisely.** They are **two engine
calls**: `world.searchObjects`/`SEGMENT` returns *scenery objects* intersecting the volume, and
terrain is not a scenery object; `land.isVisible` is the terrain test and was measured
terrain-*only* (40 rays through 40 buildings, 0 blocked). Complementary, not redundant — hence
`clear = building_clear and terrain_clear`.

**But they ride one bridge payload.** One `dostring_in` round trip, two engine calls per sightline
inside it. The 0.5 ms fixed overhead is paid once either way; terrain adds ~10.6 µs/sightline on top
of buildings' 8.7 µs. So deploying the hook twice buys nothing.

**Approved revision: write the hook once, compute both, publish them as two fields.**

- The Hook script computes `building_clear` and `terrain_clear` per unit from the first deployment.
- The endpoint publishes **both**, as separate fields, rather than a single pre-ANDed boolean.
- Body-layer wires them into the gate **in two steps**, exactly as the stages below describe —
  buildings first, terrain second.

This keeps the whole reason the stages were split, which is **attributability, not call structure**:
Stage 1 cannot change any answer the current code gives (nothing models buildings today), while the
terrain swap changes answers the existing path already produces. Keeping the verdicts separable in
the data means a misbehaviour after both are live is still attributable to one half. What it removes
is a second Windows-box deployment, a second schema change, and a second flight to enable a field
that was already being computed.

**Consequence for the stage descriptions below:** Stage 1's "Hook script + schema + endpoint" work
covers both fields; Stage 3 becomes a body-layer-only change (start reading the second field) plus
its verification sortie, with no Windows-side work at all.

**One assumption to test before relying on it.** That `SEGMENT` ignores terrain is *inferred* from
what it returns (scenery objects), never tested by firing a ray through a hill. **If SEGMENT does
catch terrain, Stage 3 collapses into Stage 1 entirely** and `land.isVisible` is not needed at all.
Added to the Windows-box probe list alongside the tree questions — it is one ray from a known
position into a known ridge, with an open-ground control at the same range.

### Implementation Plan

**SUPERSEDED by Revision §5.** The four stages below are still the right *content*; the revision
adds a zero-flight Stage 0 (size the cap against the real bubble population from logs already on
disk), folds the cap and the ordering policy into Stage 1, and removes the SEGMENT-probe block.

1. **Stage 1 — buildings only, collector-side, the new-capability slice.** Hook script + schema +
   cache + endpoint + client method + body-layer join, all building-occlusion only
   (`world.searchObjects`/`SEGMENT`, ~8.7 µs/sightline true-to-true). Wire into `check_visibility`'s
   gate 4 as above. Flyable: any AAA/vehicle sitting behind a real building that reads as clear
   today should now read as occluded. Zero regression risk — `live_los_clear` is `None` until this
   stage's feed exists and is joined, and the fallback path is exactly today's code.
2. **Stage 2 — belief carries the observed value; the engagement term stops querying anything.**
   `Contact.live_los_clear`, the `Percept`/`Observation` plumbing, and the engagement-term rewrite
   above, plus the deletions (`_threat_has_los`, `tick`'s `los_clear` parameter,
   `LOS_UNCERTAINTY_SAMPLES`, `logger.py`'s closure). Flyable and independently testable without a
   live DCS session: fixtures can set `Percept.live_los_clear` directly, exercising the
   masking-dwell logic exactly as `plans/watch-reporting/plan.md`'s own tests already do, just
   against a fixed value instead of a fake callable. **After this stage, for currently-observed
   contacts, the engagement term is building-aware for the first time** even before Stage 3 adds
   terrain, because it is now reading Stage 1's ground-truth boolean rather than world-model's
   terrain-only offline primitive.
3. **Stage 3 — terrain via `land.isVisible`, added to the same collector-side call.** Add the
   terrain test (~10.6 µs/sightline) to the same hook snippet; `clear = building_clear and
   terrain_clear`. This is the tolerance-removal half — verify against a live sortie flown in
   mountainous terrain (the missed-AAA geometry) that the live path agrees with the already-shipped
   12 m-tolerance fallback at the case that motivated it, and diverges (correctly) somewhere the
   tolerance alone would not have caught.
4. **Stage 4 — acceptance sortie.** One flight validating: a target behind a building (new
   detection gained), the engagement term correctly calling danger/safe against a building/terrain
   occluder while actively tracked, and a paused-state check per `aircraft-layer/CLAUDE.md`'s
   testing note (a bug class this exact family of Hook script has hit before).
5. **Not this plan**: the tree probes above (hand to the Windows-box session whenever it next
   flies), and the OSM-landcover transmission model (blocked on those probes' answer, filed
   separately once they report).

### Risks & Unknowns

- **`unit_name` collision**, same risk `_resolve_velocity_by_object_id` already carries and already
  handles (drop ambiguous matches rather than guess) — this plan's join reuses that handling, not a
  new risk.
- **`object_id` cross-poll instability** is pre-existing and unrelated to this plan; noted only
  because the join deliberately avoids it by using `unit_name` instead.
- **Cold-terrain bridge cost** (`aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md`
  Finding 9): a probe that jumps across the map pays ~30-40 ms once. This plan's bubble is
  ownship-following, the cheap case per that finding, but the very first poll of a session (or
  right after a long transit) could show one slow poll — acceptable at 1 Hz, worth knowing before
  attributing a one-off stutter to this feature.
- **`LOS_MAX_AGE_S = 3.0 s` is a proposed, unmeasured number**, same debt class as
  `BRAIN_REPLY_MAX_AGE_S`/`STAND_BY_AFTER_S` already carry in this codebase — fine to ship, flagged
  rather than presented as derived.
- **The trees gap is now explicit rather than silently absent.** Before this plan, no naked-eye
  mechanism accounted for trees at all; after Stage 3, a target hidden by trees but with clear
  terrain+building LOS will read as visible, same as today — not a regression, but worth saying
  plainly since "DCS-driven LOS" could otherwise be misread as "solves occlusion."
- **A real behaviour change for contacts that are watched but not currently corroborated by the
  naked-eye channel — new with this revision, not present in the pre-correction draft.** Today,
  the engagement term actively queries world-model's terrain LOS against every watched contact's
  believed position on every tick, regardless of channel or recency. After this plan, only a
  contact **freshly observed by the naked-eye channel within `OBSERVED_WINDOW_S` (16 s)** carries a
  real LOS fact; a contact known only through the hybrid/HelperAI channel, or one that has gone
  quiet, always fail-opens to "the threat can see us." This is the same conservative direction the
  codebase already prefers (`LOS_MASK_CONFIRM_S`'s own asymmetry, "a false danger call costs a
  glance, a missed one costs the aircraft"), and it is *more* physically grounded than before for
  the contacts it does cover — but it is a real narrowing of which contacts ever get a "safe from"
  clearance at all, worth confirming rather than discovering in a debrief. See "Decisions Requiring
  User Input" below.

### Second-order effect

Once buildings+terrain LOS is DCS-driven, world-model's elevation grid has no remaining role in
*detection correctness* — only in land-formation description and offline Mission Interpreter
enrichment, exactly as X-B28 (superseded) already recorded. That narrows, rather than blocks, the
already-deprioritized probe-grid-spacing redesign: whoever picks it up next should size spacing
for `describe_position`/ridge-valley description quality, with no line-of-sight accuracy
requirement pulling in the opposite direction. This revision adds a second, narrower effect: once
`belief/contacts.py` no longer holds a live callable into world-model at all for LOS, a future move
of body-layer off the Mac (`todo/backlog.md` X-B27/X-B31) loses one more reason to keep world-model
in-process on that box for the live path — though gate 4's fallback and the offline/enrichment path
still need it, so this narrows rather than removes the coupling.

### Decisions Requiring User Input

- ~~**Confirm the engagement-term behaviour change**~~ **SETTLED (user, 2026-09-29): defer
  "safe from" entirely rather than ship it narrowed.** His answer to the fail-open consequence:

  > *"We can optimize and not LOS units that are outside possible visibility cone, if need be. Then
  > for 'safe from' when unit is not within visibility cone, mission memory of where those are
  > believed to be would have to be used. Defer safe-from."*

  **This dissolves the concern rather than accepting it.** The worry was that hybrid-only and stale
  contacts would fail open to "can be seen", quietly narrowing what a clearance means. The answer is
  that the clearance should not be issued at all yet.

  **The asymmetry is the reasoning, and it is worth keeping:** *"Danger"* is a claim about something
  Petrovich can currently see. *"Safe from"* is a claim about an **absence** — it asserts a unit is
  no longer able to shoot you, which requires knowing where it is *now*, not where it was last
  observed. Without mission memory that is a guess wearing the clothes of a clearance, and it is the
  more dangerous of the two to get wrong.

  **What this means concretely:** `CONTACT_ENGAGEMENT_CHANGED`'s `engaged=False` branch
  (`belief/speech.py`, the `"Safe from "` lead) stops producing a callout; `engaged=True`
  (*"Danger, ..."*) is untouched. The event itself may continue to exist for state-tracking; it is
  the *utterance* that is deferred. Shipped in watch-reporting and never flown, so nothing the pilot
  has heard changes.

  **Un-defers when mission memory lands** (BL-8 territory — believed positions of units currently
  outside the visibility cone are exactly what it would hold). Record the dependency there rather
  than leaving this as a permanently dropped feature.

- ~~**Cone filtering is an available optimisation, not a requirement**~~ **REVISED by Revision §2
  (2026-10-05): still not required, but the *reason given below is wrong now*. A per-call sightline
  cap with nearest-first ordering is the control that bounds cost, and it subsumes what a cone filter
  would have bought while staying gaze-independent. Original text kept:**
- **Cone filtering is an available optimisation, not a requirement** (same user message: *"if need
  be"*). Worth recording why it is not needed yet: the measured cost is 0.5 ms fixed plus 8.7 µs per
  sightline, so the settled 10 km bubble alone keeps a 200-unit sweep at ~2.2 ms, about 0.2% duty at
  1 Hz. The bubble is already doing the filtering the cone would do, and LOS is gaze-independent, so
  adding a cone filter now would buy nothing measurable while coupling the feed to where Petrovich
  happens to be looking. Reach for it if a scene ever makes the sweep expensive.
- ~~**`LOS_MAX_AGE_S`'s value (proposed 3.0 s)**~~ **SETTLED (user, 2026-09-29): 3.0 s, ship it.**
  Still unmeasured and still carried as that debt class; revisit from a sortie if a stale verdict
  ever produces a visibly wrong call. At 83 m/s the aircraft covers ~250 m in 3 s, which is the
  shape of error to listen for.
- ~~**Stage 3's terrain swap is optional relative to Stages 1-2**~~ **SETTLED (user, 2026-09-29):
  build Stages 1-3 together, gated on the SEGMENT probe.** **REVISED — see Revision §4: the gate can
  be removed by design rather than waited out, because publishing two fields makes the schema and the
  gate wiring identical under both probe outcomes. Needs the user's confirmation, since it revises a
  decision they took.** His words: *"Do stages 1-3 together, but
  there's dependency to whether SEGMENT ignores or catches terrain."*

  **So this plan is now blocked on one measurement**, and deliberately: if `SEGMENT` catches
  terrain, the hook makes **one** engine call per sightline and `land.isVisible` is never wired at
  all; if it does not, the hook makes two and publishes two fields as the revision above describes.
  Those are different hook scripts, different schemas and different gate wiring, so starting before
  the answer means writing one of them twice.

  The staging survives as **build order within one delivery** rather than as three separately-flown
  increments: buildings wired first, terrain second, so a misbehaviour is still attributable to one
  half — but one deployment, one schema, one sortie.

  **Unblocks when the Windows-box session reports the SEGMENT-through-terrain probe** (sent
  2026-09-29, alongside the tree questions; one ray through a ridge with an open-ground control).
- ~~**Whether to hand the tree probes to the Windows-box session now**~~ **DONE (2026-09-29):
  sent.** `land.getIP` into known canopy, and characterising `Controller.isTargetDetected`'s
  `Controller.Detection` VISUAL bit for tree awareness. The user's acceptance bar is a blocked/clear
  verdict rather than tree geometry, and the fallback is pre-decided (statistical landcover model),
  so a negative result selects a design rather than reopening the question.

**No open user decisions remain on this plan.** It is ready to implement the moment the SEGMENT
probe reports. **SUPERSEDED — Revision §6 opens three.**

---

# REVISION 2026-10-05 — measured costs, a per-call cap, and a permanent second implementation

Everything above was written against *extrapolated* costs. The user has since flown the
elevation-cost probe (`aircraft-layer/research/2026-10-05-elevation-cost-probe-results.md`) and
taken two scope decisions (`todo/backlog.md`, `X-B29`). This revision restates what changes. The
model, the seam, the wire shape, the join key, the trees section and the no-omniscience argument are
all untouched — they survived the measurement intact.

## §0. Effort/value, re-read against the measurements

**Unchanged in direction, with one claim withdrawn and one new cheap stage found.**

The AAA-miss defect this was proposed to fix still has a shipped mitigation
(`_TERRAIN_TOLERANCE_M = 12.0`), so the value is still *buildings as new capability* plus *removing
a guessed error margin*. Today's numbers move it slightly in both directions and the net is a wash:

- **Up:** buildings are now proven on real geometry at a price we can afford, and `SEGMENT` turns out
  to be *cheaper* than the terrain-only call it sits beside (8.7 µs vs 10.6 µs, Finding 21). The
  cheapest half of the plan is also the valuable half.
- **Down:** the cost is no longer "free at 1 Hz". It is bounded only if we bound it, the user has
  already *felt* the unbounded version, and the bound costs a coverage compromise (§2).

**One claim must not be carried forward.** The probe note concludes that ~130 rays is *"comfortably
above what a 10 km bubble needs"*. That is not supported by this project's own data: a sortie already
in `dcs.log` carried **565–568 units** theatre-wide (`research/2026-09-29-bridge-call-cost-at-scale.md`,
Finding 1). How many of those sat inside a 10 km bubble is **unmeasured**. The design must therefore
be correct when the bubble holds more units than one call can price — which is §2 — rather than
assuming it does not.

**The new cheap stage:** that population is derivable from logs the project already produces, with no
flight (§5, Stage 0).

## §1. Per-call batch sizing — the cap, the arithmetic, and where it is enforced

**Cost basis, peaks and baseline-subtracted, replacing "0.5 ms fixed + 8.7 µs/sightline":**

| per-sightline test | call | steady | **peak** | derivation |
|---|---|---|---|---|
| buildings | `world.searchObjects` + `SEGMENT` | 8.7 µs | **~10 µs** | Finding 21, N=0 baseline subtracted: `(2.00−1.00)/100 = 10.0`, `(3.00−1.00)/200 = 10.0` — the two rungs agree, same check that validated the steady figure |
| terrain | `land.isVisible` | 10.0 µs | **15 µs** | 2026-10-05 note, 200 rays: 2.0 ms steady / 3.0 ms peak |
| **both, per unit** | one bridge call, two engine calls | 18.7 µs | **25 µs** | sum |

Fixed overhead: **none worth amortising** (null call 0.00 ms). What remains is a ~1 ms *peak jitter
floor* (Finding 21's N=0 rung peaked at 1.00 ms doing no work) and an 18–20 ms tail that is
indifferent to payload size and is therefore not ours (bridge-cost note, Finding 3). **Neither is
removable by this design and neither should be blamed on it** — worth writing down before the next
one-off stutter gets attributed here.

**Budget: ≤2 ms of in-call work**, an eighth of a 60 fps frame, which is the probe note's own
figure. `2000 / 25 = 80` sightlines.

**Cap: `MAX_SIGHTLINES_PER_CALL = 64`.** The 20 % haircut off 80 buys margin against the one
unmeasured term that matters: **`SEGMENT`'s cost was measured on 2 km rays** (Finding 21's hit rates
are explicitly "2 km rays from 30 m AGL"), and a 10 km bubble ray is **5× longer**. A volume search
plausibly scales with the volume, and nothing has measured it. At the measured rate 64 sightlines is
1.6 ms; if long rays turn out to cost 2× the measured rate it is 3.2 ms — a fifth of a frame, against
the 1.5 frames (24–26 ms) that produced the felt stutter. That is the margin's whole job.

**Where the cap is enforced: inside the Lua snippet, as a constant in the code literal.** This is
not a preference, it is forced. `petrobrain-mission-telemetry-hook.lua`'s own docstring states the
posture: *"`VELOCITY_CODE` below is a fixed string literal, baked in at authoring time — never built
from network input, mission data, or any other runtime value."* A collector-chosen unit list, or a
collector-pushed cap, would build the payload from runtime values and break that. So the snippet does
its own bubble filter (as planned), its own ordering (§2) and its own truncation, and the collector's
only role is to publish what came back.

**Observability, reusing the existing mechanism rather than inventing one.** The snapshot carries
`bridge_call_ms` (self-measured via `os.clock()`, exactly as `UnitVelocitySnapshot` already does),
plus `sightlines_computed` and `units_in_bubble`. When the second exceeds the first, the cap bit, and
the log says by how much. **That is how the cap gets tuned: from a flown log, between sorties — not
in flight.**

**Explicitly rejected: an in-flight adaptive cap** (halve on sustained overrun). It makes the
feature's coverage depend on unlogged history, makes two sorties in the same mission behave
differently, and hides the condition it is reacting to. The self-measurement already surfaces that
condition post-flight, where a human can change a constant. Predictable over clever.

## §2. Cadence re-derived, and what happens when the bubble overflows the cap

**Cadence stays 1 Hz, and the batch-size finding is now the reason it cannot rise.** At the cap, a
call is ~1.6 ms; at 5 Hz that is 8 ms/s of DCS-thread work in ~1.6 ms slices, which is affordable —
but it buys nothing, because the underlying fact changes over seconds (83 m/s) and
`LOS_MAX_AGE_S = 3.0` already tolerates a verdict three polls old. Raising the rate would multiply
the number of chances to land a bad slice for no freshness gain.

**Overflow policy: prioritise by range, truncate the tail, do not split across ticks.**

- **Order, in Lua, per poll: ascending true range from ownship.** Nearest first. The nearest units are
  the ones most likely to pass the detectability gates at all, the ones that can shoot, and the ones
  whose LOS changes fastest. Range is also the only priority signal available in the snippet without
  replicating body-layer's threat model across the seam — the same argument that already rejected
  cone filtering.
- **Truncate at the cap. Units past it are simply absent from the payload.** No new mechanism is
  needed for this and that is the point: the tri-state join already specified above maps "absent this
  poll" to `live_los_clear = None`, and `None` means gate 4 falls back to world-model's offline
  primitive and the engagement term fail-opens. **So a unit beyond the cap degrades to exactly
  today's behaviour**, which is the correct degradation and is already tested.
- **Round-robin across polls is useless here, and the reason is an interaction between two
  constants.** With a 64 cap and, say, a 300-unit bubble, a round-robin gives each unit a verdict
  every 5 polls = **5 s**, against `LOS_MAX_AGE_S = 3.0 s`. The join would discard every verdict the
  round-robin produced for the other four fifths. Splitting therefore delivers nothing *unless*
  `LOS_MAX_AGE_S` rises or the cap does — and `LOS_MAX_AGE_S` exists to stop a stale verdict being
  joined onto a moved aircraft. Do not split. Revisit only if Stage 0 shows the cap biting hard and
  the user prefers stale-everywhere to fresh-nearest.

**The accepted cost of nearest-first, stated plainly:** a long-range SAM/AAA at 6 km can be crowded
out by 64 closer trucks, and it is the long-range threat the pilot most wants a verdict on. A
two-tier ordering (air-defence-attributed hostiles first by range, then everything else) is cheap in
Lua (`Unit:hasAttribute`) and is the obvious fix — but it puts a threat vocabulary in the Lua snippet
that has to stay in step with body-layer's own, for a cap that may never bite. **Deferred to a named
follow-on, conditional on Stage 0's population figure.** See §6.

## §3. The offline primitive serves tests only — and agreement with DCS is now an explicit NON-GOAL

**This section was rewritten mid-pass on new user direction, 2026-10-05, which dissolves the problem
it was originally written to solve.** The earlier version (§3 as first drafted, and the body of this
plan above) treated the offline primitive as a permanent *stand-in* for DCS and designed machinery to
keep the two from silently disagreeing: a parametrised cross-implementation contract test, a recorded
disagreement rate with a direction breakdown, and a docstring carrying the last measured figure. **All
of that is dropped.** The user:

> *"I'm willing to relax the offline LOS requirements, we only need it for testing. If we build a fine
> grid for a very small area, we can use that for test scenarios. Recreating LOS of actual flights
> offline makes no sense, we cannot get required accuracy without DCS. Instead, detection trace logs
> could carry the LOS boolean from DCS-driven LOS."*

### §3a. The non-goal, stated plainly, because the next reader will otherwise call it a defect

**The two implementations are not trying to agree, and a disagreement between them is not a bug.**
They answer different questions:

| | question it answers | authority |
|---|---|---|
| `land.isVisible` + `SEGMENT`, in flight | *what did DCS say about this real sightline* | the simulated world itself |
| `query/line_of_sight.py`, offline | *what does this fixture assert about a constructed sightline* | the test author |

A fixture's job is to make a known geometry produce a known verdict so that the **gate logic around
it** can be exercised with no DCS and no collector (`plans/body-layer/plan.md` §2, unchanged and still
hard). It is not a prediction of flight. Recreating a real sortie's LOS offline is **not attempted**,
because the accuracy to do it does not exist without DCS — and pretending otherwise is what would
produce a confident wrong answer in a debrief.

**So: no cross-implementation contract test, no disagreement corpus, no reconciliation number.** This
paragraph exists because replacing a real constraint with an explicit non-goal is invisible unless
written down; the shape of the dropped machinery is recorded above so nobody rebuilds it believing it
was simply forgotten.

What *is* kept is one cheap property test of the offline primitive **on its own terms**, because
fixtures depend on it: `los(a, b) == los(b, a)` (reciprocity) and raising the observer never turns
clear into blocked (monotonicity). These are assertions about a deterministic function, not about
DCS. **Live reciprocity remains an assumption** — the engagement term's justification rests on it, it
is not measured, and it stays in Risks.

### §3b. What the offline primitive stands on: fine-but-tiny, not coarse-but-everywhere

Note the inversion against this morning's assumption. `X-B26`'s closure (no live elevation polling)
pointed at a *coarse grid over the whole theatre* (`WM-B7`) as the offline primitive's new elevation
source. Under this direction it is the opposite: **a fine grid over a very small area, built for test
scenarios.** Fixture-scale, not a theatre layer — sized so a test can place a ridge where it wants one
and get a verdict that is stable across runs.

This plan does not design that artifact and does not need it to ship: the existing tests already pass
against the existing grid, and gate 4's fallback branch is untouched code. It is named here so
whoever builds it knows what it is *for* (fixtures) and what it is explicitly not for (predicting
flight).

**Knock-on to flag, not to decide: what is left of `WM-B7`.** It was filed this morning specifically
to feed the offline primitive at theatre scale. That rationale is now mostly gone. What survives, as
far as this plan can see, is only what never depended on LOS at all — ridge/valley description and
`describe_position` quality, and Mission Interpreter's offline waypoint enrichment, where coarse is
already adequate. If those do not justify it on their own, `WM-B7` is a candidate for retirement or
reshaping into the fixture-scale grid above. **Not this plan's call** — recorded so it can be made
with the reasoning visible. See §6.

### §3c. The detection trace carries the DCS LOS boolean

This is the replacement for offline recomputation, and it is the honest version of what "why did
Petrovich not see that?" actually needs: **recorded truth from the flight, not a reconstruction.**

**Where the field goes: on `perception.detection_trace.DetectionTrace`, annotated per poll, exactly
as the movement gate's inputs already are.** `annotate_motion` is the precedent — same shape, same
call site (`NakedEyePerceptionSource.poll`), same "no-op if the entry doesn't exist" posture. A new
`annotate_los(object_id, *, building_clear, terrain_clear, live_los_clear, skew_s)` records both
published fields, the joined verdict, and the join skew, so a debrief can tell "blocked by a building"
from "blocked by terrain" from "no live verdict this poll" — which is the distinction that makes the
log worth reading at all. Nulls mean "no live feed / dropped by the cap / too stale", never a guessed
boolean, same tri-state discipline as the rest of the join.

**`detection_trace_writer.py` needs no change, and that is the point — its invariants are not even
engaged.** Checked against its own module docstring:

- It serialises entries with `asdict(entry)`, so a new `DetectionTrace` field appears in the JSONL
  automatically. Only `_entry_to_dict`'s explicit special cases (enum `outcome`, tuple
  `cluster_member_object_ids`) need touching, and a plain `bool | None` needs neither.
- **The read-only, one-directional join is untouched.** The new field is ground truth arriving on the
  ground-truth side (`perception/`), not belief; nothing is read from `ContactStore` to produce it and
  nothing is written back. `ContactStore.ingest`, `Percept` and `Contact` are not touched by this
  field's path into the log.
- **No new import direction.** `perception/` still does not import `belief/`; `belief/` still does not
  import this module or `detection_trace.py`. The no-omniscience boundary is where it was.

The one thing to say explicitly, since it is the kind of claim that looks like a violation at a
glance: `Contact.live_los_clear` (§Stage 2, unchanged) and `DetectionTrace.live_los_clear` are **two
separate recordings of the same observed fact on opposite sides of the boundary** — belief's copy
arrives via `Percept` and is what Petrovich acts on; the trace's copy arrives via the annotator and is
what a human reads afterwards. Neither is derived from the other, and that duplication is deliberate
in exactly the way `detection_trace.py` already duplicates geometry belief also holds.

## §4. The aimed-vs-sweep building discrepancy — settled by design, not by another flight

**The question:** `occlusion_urban` found 2 of 40 pairs terrain-clear-but-`isVisible`-blocked (0 of 40
in desert), suggesting `isVisible` sees buildings — while the *aimed* `through_buildings` /
`through_buildings_wide` checks came back 6/6 clear.

**The repo's own evidence weighs heavily against the sweep, and the plan should say so rather than
carry it as an open coin-flip:**

- **Finding 12** (flight 6) fired **52 rays through 52 buildings located by `searchObjects` itself**,
  confound deliberately removed, and **none blocked**.
- **Finding 16 / 19** is a direct contradiction pair at *identical endpoints*: `SEGMENT` returned
  three named buildings, `land.isVisible` returned `true` (clear).
- **2026-10-05's own aimed test** is 6/6 clear — a *third* aimed result agreeing.
- The contrary evidence is one sweep differential, **2 vs 0 at n=40** — and the same sweep in flight 4
  gave **1 vs 0**, which that note itself called "within the sampling noise the control exists to
  expose". 2 vs 0 is not a different conclusion from 1 vs 0.
- There is a likelier mechanism than buildings, and it is worth naming: the sweep's "terrain-clear"
  reference is computed from *our own* sampled terrain profile, which is coarser than whatever
  `isVisible` samples internally. A marginal grazing ridge reads clear to the coarse baseline and
  blocked to `isVisible`. That produces exactly a small, urban-biased differential (towns in this
  theatre sit in broken ground; the desert control does not) with no building involved.

**Read: `land.isVisible` is terrain-only. The 2/40 is noise or a coarse-baseline artifact.**

**And the design is built so that it does not matter.** The call shape this plan already chose —
`SEGMENT` for buildings, a separate terrain test, two published fields — is correct under *both*
hypotheses: `SEGMENT` is proven 3D on real buildings, is *cheaper* than `isVisible`, and needs no
type-name→size table (Finding 19). Nothing is gained by routing buildings through `isVisible` even if
it did see them. **So no probe gates this plan on the building question.**

**What is still worth measuring, as a cost optimisation rather than a gate:** if the 2 positives were
real, `isVisible` alone would answer both halves in one call at 15 µs instead of two at 25 µs — a 40 %
cap increase. Settle it cheaply **on the next sortie flown for any other reason**, with the
discriminating probe rather than another sweep: for each of the sweep's positives, log the `SEGMENT`
hit list *and* a dense (≤5 m) terrain profile over the same endpoints. A positive with no `SEGMENT`
hit and a dense-profile block is the artifact; a positive with a `SEGMENT` hit and a clear dense
profile is a real building. Either way the plan ships first.

## §4b. Affected modules — delta against the list in the body of this plan

Additions only; nothing in the body's list is removed.

- `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` — **the cap (`64`) and the
  nearest-first ordering live here, as literal constants in the code string** (§1: the snippet must not
  be built from runtime values). Terrain tested through a separately named function in the snippet, so
  §6.1's optimisation is a one-function change.
- `aircraft-layer/src/schema/line_of_sight.py` — snapshot gains `bridge_call_ms`,
  `sightlines_computed`, `units_in_bubble` alongside the per-unit verdicts.
- `body-layer/src/perception/detection_trace.py` — `DetectionTrace` gains `building_clear`,
  `terrain_clear`, `live_los_clear`, `los_skew_s` (all `| None`); new `annotate_los`, mirroring
  `annotate_motion` (§3c).
- `body-layer/src/perception/naked_eye_source.py` — calls `annotate_los` in the same poll step that
  already calls `annotate_motion`.
- `body-layer/src/detection_trace_writer.py` — **no change expected** (`asdict` picks the fields up;
  `bool | None` needs no special case). Named so the reviewer confirms the negative rather than
  assuming it.
- `world-model/tests/test_query_line_of_sight.py` — gains the two
  property assertions of §3a. **No cross-implementation test is added.**

## §5. Staging — buildings first, with a zero-flight Stage 0 in front

0. **Stage 0 — size the cap from logs already on disk. No flight, no code.** Extract the in-bubble
   candidate count per poll from an existing sortie's `dcs-detection-trace.jsonl`: rows per `t_sim`
   excluding `GateOutcome.PLAYER_BUBBLE` *is* the 10 km bubble population, by construction
   (`perception/detection_trace.py`). Report the distribution (p50/p95/max). **This does not gate
   anything** — the cap bounds cost unconditionally, by truncation — it tells us *coverage*: how often
   the cap bites, and therefore whether §2's two-tier ordering is needed now or never. If no existing
   log carries a dense mission, the pessimistic bound is the 568-unit theatre-wide figure already in
   `dcs.log`, and the design is still safe under it.
1. **Stage 1 — one hook, both fields, capped and ordered, and the trace records it.** As the body's
   Stage 1, plus: the nearest-first sort, `MAX_SIGHTLINES_PER_CALL = 64` as a literal constant in the
   snippet, and `bridge_call_ms` / `sightlines_computed` / `units_in_bubble` on the snapshot schema.
   Both `building_clear` and `terrain_clear` are computed and published from this one deployment (the
   2026-09-29 revision, unchanged). Body-layer wires **buildings only** into gate 4, and
   `DetectionTrace.annotate_los` records both fields plus the joined verdict (§3c) — the trace lands in
   the same stage as the feed, so the first sortie flown is already readable afterwards rather than
   needing a second one.  Zero regression risk: `live_los_clear` is `None` until the feed exists.
2. **Stage 2 — belief carries the observed value.** Unchanged from the body of the plan, including the
   deletions (`_threat_has_los`, `tick`'s `los_clear` parameter, `LOS_UNCERTAINTY_SAMPLES`,
   `logger.py`'s closure) and the deferred "safe from" callout.
3. **Stage 3 — body-layer starts reading `terrain_clear` too.** No Windows-side work (that was the
   2026-09-29 revision's whole point). `clear = building_clear and terrain_clear`.
4. **Stage 4 — the acceptance sortie, read back from the trace.** Target behind a building (detection
   newly gained); engagement term calling danger/safe correctly against a building and against terrain
   while actively tracked; paused-state check per `aircraft-layer/CLAUDE.md`. **Evidence comes from the
   trace's recorded booleans (§3c), not from recomputing anything offline** — for each interesting
   object, what DCS said and whether a building or terrain was the blocker. Read `bridge_call_ms`,
   `sightlines_computed` and `units_in_bubble` from the same log before declaring the cap right.
5. **Not this plan:** the tree probes and the OSM-landcover model (unchanged); the two-tier threat
   ordering (§2, conditional on Stage 0); the `isVisible`-sees-buildings cost optimisation (§4, next
   sortie of opportunity); the fixture-scale fine grid and whatever becomes of `WM-B7` (§3b).

## Risks & Unknowns added by this revision

- **`SEGMENT` cost at 10 km ray length is unmeasured.** Finding 21 measured 2 km rays. The cap's 20 %
  margin covers a 2× penalty; a worse-than-linear scaling would not be covered, and Stage 1's own
  `bridge_call_ms` is what detects it — on the first sortie, not in review.
- **The 18–20 ms payload-indifferent tail cannot be designed away** (bridge-cost note, Finding 3).
  With a 1.6 ms call it will be rare and it will still occasionally land on a frame. Expect one, do
  not re-open the cap over it.
- **Reciprocity of `land.isVisible` / `SEGMENT` is assumed, not measured.** The engagement term's
  justification rests on it. §3a asserts it of the *offline* function only; the live assertion costs
  double rays and is deliberately not run in flight. Unchanged by the offline-requirements relaxation
  — this one was never an offline question.
- **Coverage, not cost, is now the thing that can quietly be wrong.** A capped feed silently falls
  back to the old path for the units it drops, and the old path is the one with the error this plan
  exists to remove. `units_in_bubble` vs `sightlines_computed` in the log is the only thing that makes
  that visible — treat it as required, not diagnostic.
- **A green test suite says less than it did, and now says so by design.** Every test exercises the
  fallback branch against a fixture, which per §3a is no longer claiming to resemble flight. **Stage 4's
  sortie, read through the trace, is the only evidence about the live branch** — so it is not an
  optional formality, and "all tests pass" must never be reported as evidence that LOS is right.

## Second-order effect (added)

**The relaxation in §3 removes a dependency rather than adding one, and it lands on `WM-B7`.** Once
the live LOS answer comes from DCS *and* offline LOS is only required to satisfy fixtures, world-model's
elevation grid has no remaining accuracy obligation anywhere on the detection path — neither in flight
(DCS answers) nor in tests (a fixture-scale grid answers). `WM-B7` was filed this morning precisely to
carry that obligation at theatre scale, so this plan **narrows `WM-B7`'s purpose to whatever ridge/valley
description and Mission-Interpreter enrichment justify on their own**, and may remove its reason to
exist entirely. That is the knock-on worth watching, because it is the kind of milestone that otherwise
gets built to a requirement that was retired while it waited.

A second, smaller effect: `DetectionTrace` now carries a DCS-authoritative fact, which makes the trace
the project's record of *what the simulator said* and not only of what our own gates computed. Later
debug tooling (BL-9's lineage) gets more honest for free, and any future "replay a sortie" ambition
should read that recorded boolean rather than recompute — the mistake §3a exists to prevent.

## §6. Decisions Requiring User Input (four, re-opened)

1. **Remove the SEGMENT-probe block, or keep waiting?** You settled on 2026-09-29: build Stages 1–3
   together, *gated* on whether `SEGMENT` catches terrain, because "those are different hook scripts,
   different schemas and different gate wiring". **I think the gate can be designed away rather than
   waited out.** If the hook computes `terrain_clear` through a separately-named function in the
   snippet and publishes it as its own field, then: if `SEGMENT` turns out to catch terrain,
   `terrain_clear` is sourced from the `SEGMENT` result and the `isVisible` call is simply dropped —
   **same schema, same gate wiring, one function body changes, and the cap rises from 64 to ~130.**
   **Recommendation: unblock and build.** The probe becomes a cost optimisation of the kind §4 already
   describes. Your call, since it revises your decision.
2. **Nearest-first truncation, or two-tier threat ordering now?** Nearest-first is simple and
   gaze-independent, but can let 64 close trucks crowd out a long-range SAM — the one verdict you'd
   most want. Two-tier (`hasAttribute` air-defence first) fixes that and puts a threat vocabulary in
   Lua that must track body-layer's. **Recommendation: nearest-first for Stage 1, and let Stage 0's
   population figure decide whether two-tier is ever needed.** If the p95 bubble population is under
   64 the question is moot.
3. **Is a ≤2 ms call actually imperceptible?** Nobody has flown one; the probe note says so
   explicitly. The arithmetic predicts it vanishes, and the prediction is load-bearing for the whole
   design. Stage 4's sortie is the test, and **if you feel anything at all, say so before we tune
   anything** — the cap is one constant and the log will say which call was expensive.
4. **Does `WM-B7` still have a reason to exist?** Your relaxation of the offline LOS requirement
   removed the rationale it was filed under this morning (a theatre-scale grid to feed the offline
   primitive). What is left is ridge/valley description, `describe_position` quality and Mission
   Interpreter enrichment — none of which need LOS accuracy. **Recommendation: retire or reshape it,
   and if a fixture-scale fine grid is wanted, file that as its own small item** rather than letting
   `WM-B7` absorb a different artifact under the old name. Flagged, not decided — this plan does not
   touch `WM-B7`.

---

## Stage 0 result (main loop, 2026-10-05) — the bubble is bigger than the cap

Run against the existing `~/dcs-detection-trace.jsonl` (4,457,317 rows, 1,034 polls) with no flight,
exactly as the revision's Stage 0 specifies: objects per poll minus the `player_bubble`-outcome
rows *is* the 10 km population.

| | median | p90 | max |
|---|---|---|---|
| objects per poll, all | 403 | 415 | 425 |
| **objects per poll, inside the 10 km bubble** | **172** | **179** | **195** |

**94% of polls (970 of 1,034) hold more than 64 units in the bubble.** So a 64 cap is not a rare
truncation — it would drop roughly two thirds of the bubble on almost every poll, and the revision's
"units past the cap are simply absent, which is today's behaviour" is true but much larger in scope
than the figure it was reasoned against.

At the revision's own 25 µs/unit (SEGMENT ~10 µs + `isVisible` 15 µs, both peak): **172 units ≈
4.3 ms, 195 ≈ 4.9 ms.** That is over the 2 ms budget the cap was derived from, and far under the
24–26 ms single calls that produced the felt stutter — about 30% of one 60 fps frame, once per
second.

**This makes the ordering question (revision decision 2) load-bearing rather than hypothetical.**
Under a 64 cap, nearest-first really would let close trucks crowd out a distant SAM, on most polls.
Under a cap that covers the whole bubble, ordering stops mattering at all. The two decisions are
therefore one decision, and it is the user's: **frame budget against coverage.**

This supersedes the revision's expectation that Stage 0 would be "informative, not blocking".

> **SUPERSEDED IN ITS CONCLUSION by SECOND REVISION §8 below.** The two population figures (172
> median, 195 max in the 10 km bubble) are measured and stand. The framing — "frame budget against
> coverage", a cap, an ordering policy — does not: the same log says **162 of those 172 are rejected
> at the gaze gate before LOS is ever asked**, so the set that matters is ~10, and the tradeoff this
> section posed to the user does not exist.

---

# SECOND REVISION (2026-10-05, later the same day) — the cone replaces the cap

**The user rejected the cap-vs-coverage framing outright** and supplied the replacement in two
messages. First:

> *"How many units are in the bubble depends entirely on the mission. Scanning is per o'clock sector
> -> can we tell the LOS query which o'clock we are scanning -> then LOS for only that sector? Other
> option, prioritize targets that are within possible detection range and closer units more than
> distant units."*

Then, dissolving the constraint the first message ran into:

> *"We anyway need to manipulate the aircraft — switches, buttons, etc — so directive 'look in this
> direction' would be well in line and instead of manipulating the aircraft, would just tell the
> export script what area to LOS check. While thinking about this, we could also simply not query all
> the units always, just ones that are in the visibility cone (FOV dependent on optics, possible
> peripheral vision, etc)."*

And then, closing the last open risk this revision had — **the governing principle for the whole
design, and the sentence to read first:**

> *"Watch list items still need Petrovich to **look at** them to get an update. Threat warnings as
> well (perception capture is not implemented yet). Memory of something is independent of LOS, it's
> memory. Update on its status does require LOS and looking at it. → If Petrovich is not looking at
> something, for all practical purposes it has no LOS or LOS does not matter. **LOS only matters for
> things that we would process, if there is LOS.**"*

**He is right, and the measurement is more decisive than the argument.** This revision replaces §1's
cap, §2's overflow/ordering policy and §6 decisions 1–2 with a cone-scoped query. Everything else in
both earlier revisions stands.

### The principle, stated as the design rule it is

**The visibility cone is not an optimisation. It is the definition of the query set.**

The earlier revisions treated coverage and frame time as opposing quantities and spent several pages
rationing between them — a cap, an ordering policy, a round-robin, a two-tier threat vocabulary, an
"accepted cost". **All of that was answering a question that does not exist.** A unit outside the
cone is not *uncovered*, *truncated* or *degraded*: nothing downstream would consume its LOS, because
every consumer of LOS requires Petrovich to have looked at the thing (§11). Its absence from the
payload is **semantically correct**, and the `None` the tri-state join produces there means *"not
looked at"* — which is precisely, and independently, what gate 0 already concludes about the same
unit on the same poll.

Two things follow, and they are load-bearing for how the rest of this file should be read:

- **Anything in this plan phrased as truncation, a cap as a budget compromise, coverage loss across
  the cone boundary, or splitting work across ticks is superseded.** Those passages are left in place
  per `docs/PROCESS.md` with forward pointers (§7), not because either framing might still apply.
  Where this revision still says "coverage", it means **one specific residual case only**: a unit
  inside the current gaze that a *lagging wedge* missed (§9c) — he is looking at it and we failed to
  ask. That is a real, bounded gap and the 90° wedge exists to close it. It is not the same thing as
  a unit outside the cone, and the two must not be conflated.
- **The one condition that reopens this: attention capture.** `Optic.peripheral=True` already lets
  salience bypass the gaze gate (`gaze_for`, gate 0) and `perception/gaze.py` records that **no
  triggers are wired behind it**. The day one is, something outside the focus cone becomes a thing
  "we would process, if there is LOS" — the principle's own condition — and the query set must widen
  with it. **That is the named reopening trigger for this scoping, and the only one** — and because
  the query cone crosses the seam as an arbitrary number rather than a named preset (§9b, user
  direction), reopening it is *sending a bigger number* (45 → 130), not a redesign.

## §7. What this revision overturns, with pointers

| superseded | by | why |
|---|---|---|
| §1 `MAX_SIGHTLINES_PER_CALL = 64` as the cost control | §9–§10 | the cone bounds the work by geometry; the cap survives only as a blow-up guard |
| §2 "overflow policy: order by range, truncate the tail" | §10 | nothing overflows — there is no tail to truncate at the measured scale |
| §2 "accepted cost of nearest-first… a long-range SAM crowded out by 64 trucks" | §10 | does not arise; the deferred two-tier threat ordering is **withdrawn, not deferred** |
| §6 decision 2 (nearest-first vs two-tier now) | §10 | moot |
| "Stage 0 result" framing ("frame budget against coverage") | §8 | the tradeoff was posed against the wrong population |
| body §"What exactly is asked" — *"No cone filtering, deliberately"* | §8–§10 | its reason 1 (LOS is gaze-independent) is still true and is **not** why it is being reversed; reason 2 (not needed as an optimisation) is now contradicted by measurement, and the cross-seam-duplication objection is answered by passing the direction as a command rather than replicating the logic |
| §6 decision 3's premise (is a ≤2 ms call imperceptible?) | §10 | still worth flying, but the call is now ~0.25–1.1 ms, not 2 ms |
| §2's round-robin-across-ticks discussion | the governing principle above | it rationed coverage across a boundary that carries no information |
| body §Risks — *"a real behaviour change for contacts that are watched but not currently corroborated"* | §11a | the user's principle reframes this: a watch is a standing instruction to look, not a subscription to continuous truth |

**Not superseded, and carried forward unchanged:** the true-to-true rule, the two-field
(`building_clear` / `terrain_clear`) call shape, the `unit_name` join, the tri-state `None`
discipline, `LOS_MAX_AGE_S = 3.0`, the deferred "safe from" callout, §3's offline-primitive
relaxation and `DetectionTrace` recording, §4's reading that `land.isVisible` is terrain-only.

**One open question in the first revision is settled, not open.** The body of this plan and §4 both
treat "does `SEGMENT` catch terrain?" as needing a probe. `aircraft-layer/research/2026-09-29-bridge-
terrain-probe-results.md` **Finding 21 already answers it**: *"`land.isVisible` costs 10.6 µs/ray and
sees only terrain. A SEGMENT search costs 8.7 µs and sees buildings in 3D."* Both calls are needed;
that is exactly what the 25 µs/unit figure assumes. **§6 decision 1 is therefore resolved by the
repo rather than by the user: unblock and build, no probe gates this plan.**

**`WM-B7` is retired and `WM-B8` filed** (fixture-scale fine grid, `world-model/ROADMAP.md`, commit
`7dd6f92`). **§6 decision 4 is closed.** §3b's pointer should be read as naming `WM-B8`.

**Withdrawn claim kept withdrawn:** the probe note's *"~130 rays comfortably covers a bubble"* is
still unsupported and is not relied on anywhere below.

## §8. The measurement that settles it — 94% of the bubble never reaches the LOS gate

**Method:** the same `~/dcs-detection-trace.jsonl` Stage 0 used, first 2,000,001 rows, **deduplicated
by `(t_sim, object_id)`** — the earlier pass did not dedupe, which is why its per-poll outcome counts
did not reconcile with its own 403-objects figure. 1,028 polls, 403 distinct objects per poll
(median), matching Stage 0 exactly. Gate order is `visibility.py`'s own: **gaze (0) → cockpit mask
(1) → optic FOV (2) → range/size (3) → terrain LOS (4)**, first failure wins, so an outcome count
*is* a per-gate survivor count.

| gate outcome | share of rows | **per poll (median)** |
|---|---|---|
| `player_bubble` (outside 10 km) | 61.9% | 298 |
| **`gaze` (outside the focus cone)** | **34.4%** | **162** |
| `range_or_size` | 1.8% | 2 |
| `optic_fov` | 0.7% | 0 |
| `admitted` | 0.7% | 0–1 |
| `cockpit_mask` | 0.4% | 0 |
| `terrain_los` | 0.1% | 0 (332 in 1,028 polls) |

**In the bubble: 172 per poll (median), 185 p95, 195 max — of which 162 die at gate 0.** About **10
units per poll** ever reach gate 4, where LOS is asked.

Three consequences, each of which kills a piece of the earlier design:

1. **LOS computed for the other ~162 units is work whose answer a gate upstream of it discards.**
   Cone scoping is not a budget compromise — it removes work that was never needed. This is the
   user's point and it is the whole argument.
2. **At 25 µs/unit the real workload is ~0.25 ms, not 4.3 ms.** The cap was sized against a
   population 17× larger than the one that matters.
3. **`cockpit_mask` rejects essentially nothing (0 per poll)** because the 30° gaze cone sits wholly
   inside the 260° mask. So the mask is *not* a useful Lua-side filter on its own — an earlier draft
   of this revision proposed it as the safe, body-layer-free cut and the data says it buys ~28% where
   the gaze buys 94%. Recorded because it reads as the obvious conservative move and is nearly
   worthless.

**What is measured and what is not.** Measured: every number in the table, from one sortie's log.
Estimated: every widened-wedge figure in §10, which scales the measured 172 by wedge fraction
assuming units are spread evenly in azimuth — **they are not** (units cluster, and the aircraft is
usually flown toward them, so the forward wedge is denser than uniform). Treat §10's estimates as
order-of-magnitude, and note that `units_in_wedge` on the snapshot (§11) measures the real figure on
the first sortie. Nothing here needs a flight; nothing here is a live-DCS measurement.

**Effort/value, re-read once more:** unchanged in direction. Note soberly that gate 4 rejects ~0.3
candidates per poll today — terrain LOS is a rarely-firing gate, so the terrain half of this plan
changes few answers. Buildings remain the valuable half (new capability, cheaper call), and cone
scoping makes the whole thing ~17× cheaper than the design it replaces. Still worth building; still
buildings-first.

## §9. "Look in this direction" as a command — where the state lives, and why the literal rule holds

**The rule is not in tension here, and the first revision framed it too narrowly.** The constraint in
`petrobrain-mission-telemetry-hook.lua`'s docstring is that the snippet is *"a fixed string literal,
baked in at authoring time — never built from network input, mission data, or any other runtime
value."* That forbids **composing** executable text from runtime bytes. It does not forbid a runtime
value from *selecting among* audited literals, and this repo already does exactly that, inside DCS:

- `Export.lua`'s `handle_petrovich_search_command(mode, …)` rejects anything but `"forward"` /
  `"boresight"` and dispatches to fixed `performClickableAction` sequences — a closed enum from the
  LAN driving real cockpit switches, shipped today.
- `aircraft-layer/src/api/server.py` validates against `_VALID_SEARCH_MODES` before
  `command_sender.send_command` ever runs.
- `Export.lua` already **binds a UDP socket and polls `receivefrom()` non-blockingly every frame**
  (`try_open_command_socket`, `settimeout(0)`), so an inbound command path into DCS is proven, not
  proposed.

A *"look in this direction"* directive is the same class of traffic as flipping a switch. **So the
rule holds unweakened: the sector arrives as a command, never as a string fragment.**

### §9a. Where the state must live — forced, not chosen

Three candidate homes, and two are impossible:

| home | verdict |
|---|---|
| collector's Python | **impossible.** The only channel from the Hook state into the scripting state is the code string. Putting the value there means composing the snippet from it — the thing the rule forbids. |
| `Export.lua` globals | **impossible.** Export.lua runs in the **Export** Lua state; the LOS snippet runs in the **mission-scripting** state via `net.dostring_in("scripting", …)`. Separate states, no shared globals. That separation is why these Hook scripts exist at all — `land.*` / `world.*` are not reachable from Export. |
| **a global in the mission-scripting state** | **the only possibility, and it is already precedented.** `petrobrain-f10-commands-hook.lua` keeps `PB_F10_QUEUE` alive in that state across `dostring_in` calls: `REGISTRATION_CODE` creates it, `POLL_CODE` drains it. Persistence across calls is proven in this repo. |

### §9b. The mechanism, stated so a reviewer can audit it in one read

- **Vocabulary — a direction and an angular width, both numeric.** User direction: *"We'd better
  accept arbitrary FOV for the LOS cone, that way future changes, like peripheral vision, can easily
  be taken aboard."* **So the Lua side holds no optic table, no preset names and no idea what a
  9K113 is.** It takes a look direction and a half-angle and answers for whatever falls inside.
  Optic selection, peripheral widening and any future cone shaping stay in `perception/optics.py`
  where the model already lives, and cross the boundary as **one number**.
  - **Direction:** the **12 o'clock hours** (`0`–`11`), the granularity `perception.gaze` already
    uses (`FOCUS_CONE_HALF_WIDTH_DEG = 15.0`, 30° per hour — the o'clock cone *is* the o'clock
    position, per that module's own docstring). Not generalised further because nothing asks for it
    yet; the mechanism below extends to arbitrary bearing for free if it ever does.
  - **Width:** `PB_LOOK_FOV_DEG`, an **arbitrary integer half-angle in degrees**, not an enum.
- **Naming: `PB_LOOK_*`, not `PB_LOS_*`** — see §15; LOS is this channel's first consumer, not its
  only one.
- **How an arbitrary number crosses without the snippet being built from it — digit dispatch.** A
  closed enum of presets would have been three literals; an arbitrary value cannot be. The resolution
  keeps the rule **exactly** intact: three hand-authored setter tables of ten one-line literals each,
  `PB_FOV_H = <d>` / `PB_FOV_T = <d>` / `PB_FOV_U = <d>` for `<d>` in `0`–`9`, every digit typed out
  by hand. The Hook decomposes a validated integer into three digits and executes **three literals
  selected by index**; the poll snippet recomposes `fov = 100*H + 10*T + U`. **Nothing is
  concatenated at any point, and the set of strings the Hook can ever execute is fixed at authoring
  time at 42 entries** (12 hour + 30 digit). The value is data; only audited literals are code.
  *(Rejected alternative: one validated `string.format("%d", clamped)` splice. It is four lines
  instead of forty and is almost certainly safe — but it moves the invariant from "structurally
  impossible" to "correct because a validator is correct", on a rule this repo deliberately audits.
  Named in §16 as the user's call, not taken unilaterally.)*
- **Validation, and what happens to a bad value — stated because the failure mode is the exact cost
  this scoping exists to prevent.** Accepted range **5–180 degrees half-angle**. The collector
  rejects anything outside it with 400; the Hook **validates again and clamps** into range, logging
  what it clamped. An unset, unparseable or zero value resolves to the **default 45**, never to a
  360° query. 180 is a full-circle query and is legal only because it is the honest ceiling; it is
  never the fallback.
- **The LOS poll snippet stays one fixed literal** and reads the globals exactly as `POLL_CODE` reads
  `PB_F10_QUEUE`.
- **Transport:** body-layer `POST /command/look_direction {"hour": <int 0..11>, "fov_half_deg":
  <int 5..180>}` → collector range-validates (the `_VALID_SEARCH_MODES` pattern, generalised from a
  tuple membership to a range check) → UDP to a **new loopback-bound listener in the LOS Hook
  script**, `receivefrom()` polled per frame (`Export.lua`'s own pattern).
- **What the parameter means, so nobody reads more into it:** it is the **LOS query cone** — which
  units are worth asking DCS about. It is **not** a claim about what Petrovich can perceive. Every
  perception gate downstream (gaze, cockpit mask, optic FOV, range/size) remains the sole authority
  on detectability, unchanged. A query cone wider than the perceptual one costs frame time; a query
  cone narrower than it costs coverage (§9c). Neither changes what is detectable.
- **Pushed on change, not per poll.** The Hook re-issues the setter only when the value differs from
  what it last sent, plus unconditionally on `onSimulationStart` and whenever the poll snippet
  reports the globals unset (mission restart clears the scripting state). Self-healing, no handshake.

### §9c. Latency, and why it costs coverage rather than correctness

Round trip is body-layer → collector (LAN HTTP, pushed on change) → loopback UDP → next DCS frame →
next 1 Hz LOS poll. Against `FOCUS_DWELL_S = 2.0 s` a dwell change can still straddle a poll.

**Do not drop mismatched verdicts.** A verdict is a physical fact about one unit at one instant; the
hour only decided *which* units got one. So:

- a unit covered by the old wedge and still inside the current gaze → a correct verdict, at most one
  poll old, already governed by `LOS_MAX_AGE_S = 3.0`;
- a unit newly inside the gaze but outside the queried wedge → **absent → `None` → gate 4 falls back
  to today's offline path.**

**The safety property, stated once because everything else rests on it: a wrong, stale or absent
wedge costs coverage for a poll and can never produce a wrong answer.** The tri-state join already
specified in the body of this plan is what makes that true, and it is already tested.

**This is the one place in this revision where "coverage" still means something lost.** It is a unit
Petrovich *is* looking at that a lagging wedge failed to ask about — not a unit outside the cone,
whose absence is correct by the governing principle. Do not read the two as the same failure.

Latency is then handled by **geometry rather than timing**: query a wedge wider than the gaze (§10),
so one dwell of lag still covers the current focus cone. The hour the snippet actually used is
published alongside the verdicts and recorded in the trace — as observability, not as a gate.

## §10. The cone — how wide, per optic, and the arithmetic

`body-layer/src/perception/optics.py`, read rather than assumed:

| optic | `fov_half_angle_deg` | `peripheral` | effective cone today |
|---|---|---|---|
| `UNAIDED_OPTIC` (the default since 2026-09-20) | `None` — no FOV restriction | `True` | the **gaze focus cone, 30° full** (the cockpit mask is its only other envelope, and the mask never binds — §8) |
| `BINOCULAR_OPTIC` | 4.25 (≈8.5° true field) | `False` | **8.5°**, and always *inside* the gaze cone |
| 9K113 | deferred entirely (that module's own scope cut, 2026-09-20) | — | not modelled |

**So the optic does not need to change the wedge at all in the current two-optic world, and that
directly answers "which optic's cone is authoritative when it changes."** A single 45°-half-width
pushed wedge (90° full) is a strict superset of both the 30° unaided focus cone and the 8.5°
binocular field, with a full o'clock hour of lag margin on each side. Making the wedge
optic-dependent would introduce exactly one failure mode — binocular→unaided with a stale *narrow*
wedge is a **subset** of the new gaze, i.e. silent coverage loss — for no saving. **Recommendation:
send a constant 45 today**, and let the number become dynamic when something actually needs it.

**That "when" is the whole reason the width is a number rather than a preset**, and it is worth
being concrete about it here because it converts the reopening trigger named above from a redesign
into a parameter change:

- **Attention capture** (the standing backlog item, `Optic.peripheral=True`, zero triggers wired):
  salience bypasses gate 0, so something outside the focus cone becomes a thing "we would process,
  if there is LOS". **The change is `fov_half_deg: 45 → 130`** — the cockpit-mask rear cutoff — or a
  second, wider query with a cheaper downstream gate. No new mechanism, no schema change, no Lua
  edit.
- **The 9K113 slice**, whenever it lands: a narrower field, which is simply a smaller number.
- Diagnostics: `180` for a full-circle query, which is why the range runs that far.

Useful reference values, for whoever sets the number: **45** (ships — the 30° gaze focus cone plus a
full o'clock hour of lag margin either side), **130** (cockpit-mask rear cutoff, the attention-capture
value), **180** (everything in the bubble).

**Arithmetic. The first row is measured; the rest scale the measured 172 by wedge fraction assuming
uniform azimuth, which §8 says to distrust.**

| wedge | fraction of 360° | units/poll | cost @ 25 µs/unit |
|---|---|---|---|
| **gaze focus, 30° (what gate 0 actually admits)** | 1/12 | **~10, measured** | **~0.25 ms** |
| **90° full (`fov_half_deg = 45`) — what ships** | 1/4 | ~43 est. | ~1.1 ms est. |
| 260° full (`fov_half_deg = 130`) — only if attention capture is built | 0.72 | ~124 est. | ~3.1 ms est. |
| whole bubble (the superseded design) | 1 | 172 med / 195 max | 4.3 / 4.9 ms |

**The cap survives only as a blow-up guard, and should be read as an assertion rather than a
policy.** `MAX_SIGHTLINES_PER_CALL` stays in the snippet at **128** (~3.2 ms, covering the `mask`
`fov_half_deg = 130` estimate), with nearest-first ordering deciding only what a guard drop
discards. **If
`sightlines_computed < units_in_wedge` ever appears in a log, the wedge is wrong — not the budget.**
It is not a truncation policy and must not be reasoned about as one. **§2's two-tier threat ordering,
its round-robin discussion and its "accepted cost of nearest-first" are all withdrawn**: they
rationed a cap that no longer binds, for a coverage question the governing principle dissolves.

**On the user's second option — "prioritize targets within possible detection range".** Worked
through and **not adopted as a filter**, for a reason worth recording rather than leaving as an
unexplained omission. A *provably safe* range cut needs an upper bound on detection range over all
unit types and optics: largest `size_m` in `object_model.py` is 100 m (ships), loosest presence
threshold is `RESOLUTION_ANGULAR_RADIUS_RAD = 0.00128`, best multiplier is binocular
`presence_range_mult = 2.42`. Even for a 7 m vehicle that is `7/0.00128 × 2.42 ≈ 13.2 km` — **beyond
the 10 km bubble.** The bubble is already tighter than the detection envelope, so a safe range cut
removes nothing. A range cut keyed on the unit's actual type would work, but requires the ~400-row
size table to exist in Lua and stay in step with body-layer's — the cross-seam duplication this plan
already rejected once. **Range survives only as the ordering key for the guard.** The user's
intuition was right about *prioritisation*; the cone is what delivers the *reduction*.

## §11. Who actually reads LOS — the audit, and why absence outside the cone is correct

Audited by grep over `body-layer/src/`, not assumed. **Four readers, and the user's principle settles
every one of them: none consumes LOS for something Petrovich is not looking at.**

1. **`visibility.check_visibility` gate 4.** Runs **only** for candidates that already passed gate 0
   (gaze). By construction it can never want a verdict outside the cone. **Absence is impossible
   here, not merely acceptable.** ✅
2. **`perception/detection_trace.py` via `annotate_los` (§3c).** Records `None` for everything outside
   the wedge. Honest — a debrief asking "why wasn't that seen?" for such a unit already gets the real
   answer, `outcome: "gaze"`, from gate 0. ✅
3. **`HybridPerceptionSource`.** Has no geometric gate and never sourced LOS (`naked_eye_source.py`'s
   own docstring states this). Unaffected. ✅
4. **`belief/contacts.py::tick`, seventh block — the engagement term (watch list / threat warnings).
   Settled by the principle, not a problem.** ✅ — see §11a.

### §11a. The engagement term, and the three things the user settled about it

It runs for a contact that is **watched** *and* has a threat envelope *and* passes `range_ok and
alt_ok`. Those contacts can be anywhere: a watched SAM at 4 o'clock while free scan looks at 12. That
looked like the case the cone breaks, and I raised it as the main open risk. **It is not, and the
reason is the user's own, in three parts:**

- **Watch-list contacts** — *"still need Petrovich to look at them to get an update."* Watching a
  contact is a standing instruction to keep looking, not a subscription to continuous truth. No gaze,
  no update — **with or without LOS.**
- **Threat warnings** — same, and attention capture is not built, so nothing can fire from outside
  the focus cone today in any case.
- **Belief's memory** — *"Memory of something is independent of LOS, it's memory."* A `Contact`
  persists, decays and is reported from memory whether or not a sightline exists. Only a **status
  update** needs LOS, and a status update needs him looking.

So the engagement term never wanted a verdict for an unlooked-at contact. Its existing `None` →
fail-open branch is not a degradation the cone imposes; it is the correct reading of "we have not
looked at this recently", which `OBSERVED_WINDOW_S` (16.0 s, equal to `SCAN_CYCLE_PERIOD_S` so a
forward-hemisphere contact is re-gazed once per cycle) already expresses. The user has separately
deferred the **"safe from"** utterance entirely, so the fail-open direction produces no callout the
pilot hears.

**What changes versus today is real but is not a loss of information Petrovich was entitled to.**
Today `_threat_has_los` queries world-model's terrain LOS against a **believed** position for any
watched contact, gazed at or not — which is precisely the kind of answer this plan exists to stop
producing (a verdict about a point where nothing may stand; see the body's "Why it must be
true-to-true"). Replacing it with "no recent look, therefore no verdict" is **more honest, not less
covered.**

### §11b. ~~A second wedge for watched contacts~~ — WITHDRAWN

An earlier draft of this revision proposed pushing a second o'clock hour derived from each watched
contact's believed bearing, so the engagement term could keep getting verdicts outside the gaze.
**Withdrawn on the user's direction above**: it would compute LOS for things Petrovich is not looking
at, which is exactly what the principle says has no meaning. It is recorded rather than deleted
because it is a plausible-sounding "restore the old behaviour" move that a later reader may re-derive
— and the reason it is wrong is a product decision about what a watch *is*, not a technical one.
**The corresponding decision in §16 is closed, not deferred.**

## §12. Affected modules — delta against §4b and the body's list

Additions and changes only.

- `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` — **gains the inbound loopback UDP
  listener** (`setsockname("127.0.0.1", <port>)`, `settimeout(0)`, polled per frame, mirroring
  `Export.lua`'s `try_open_command_socket`), the **42-entry literal setter table** (§9b — 12 hour,
  30 digit), the FOV clamp, the push-on-change/re-issue-on-restart logic, and the wedge filter in
  the poll snippet. The cap becomes `MAX_SIGHTLINES_PER_CALL = 128` and is a guard, not a policy.
- `aircraft-layer/src/api/server.py` — new `POST /command/look_direction`, validating `hour` as an
  int in `0..11` and `fov_half_deg` as an int in `5..180`, structurally copying
  `_handle_command_petrovich_search`.
- `aircraft-layer/src/collector/command_sender.py` (or a sibling) —
  `send_look_direction(hour, fov_half_deg)`, same shape as `send_command`.
- `aircraft-layer/src/schema/line_of_sight.py` — snapshot gains `hour_used`, `fov_half_deg_used`,
  `units_in_bubble`, **`units_in_wedge`**, `sightlines_computed`, `bridge_call_ms`.
  `units_in_wedge` is the field that turns §10's estimates into measurements.
- `body-layer/src/aircraft_client.py` — `post_look_direction()`.
- `body-layer/src/logger.py` — pushes the look direction on change from the gaze it already resolves
  (`_active_gaze`). **One source of truth for gaze stays `perception.gaze.gaze_at`; the Lua side
  never re-derives it.**
- `body-layer/src/perception/detection_trace.py` — `annotate_los` additionally records `hour_used` /
  `fov_half_deg_used` so a debrief can tell "outside the queried wedge" from "queried and no
  verdict".
- Everything else in §4b and the body's Affected Modules list is unchanged.

## §13. Restaged implementation plan

Stage 0 is **done** (§8 supersedes its own conclusion but keeps its numbers). Stages renumbered;
content otherwise as the first revision's §5.

1. **Stage 1 — one hook, both fields, cone-scoped, and the trace records it.** Hook script + schema +
   cache + endpoint + client method + body-layer join, computing and publishing **both**
   `building_clear` and `terrain_clear` (2026-09-29 revision, unchanged). **Plus** the look-direction
   command path end to end (§9) and the wedge filter. Body-layer wires **buildings only** into gate 4;
   `annotate_los` records both fields, the joined verdict, the skew and the wedge actually used.
   Zero regression risk: `live_los_clear` is `None` until the feed exists, and the fallback branch is
   today's code.
   *Build order inside the stage, so a failure is attributable:* (a) the look-direction command path
   with the snippet ignoring it, verified from `dcs.log` alone; (b) the wedge filter; (c) the gate
   wiring.
2. **Stage 2 — belief carries the observed value.** Unchanged, including the deletions
   (`_threat_has_los`, `tick`'s `los_clear` parameter, `LOS_UNCERTAINTY_SAMPLES`, `logger.py`'s
   closure) and the deferred "safe from" callout.
3. **Stage 3 — body-layer starts reading `terrain_clear`.** No Windows-side work.
   `clear = building_clear and terrain_clear`.
4. **Stage 4 — the acceptance sortie, read back from the trace.** As before, plus: read `hour_used`
   against the trace's own `gaze` outcomes to confirm the wedge tracked the scan, and read
   `units_in_wedge` / `sightlines_computed` / `bridge_call_ms` to replace §10's estimates with
   measurements before anyone tunes a constant.
5. **Not this plan:** the tree probes and the OSM-landcover model (unchanged); the
   `isVisible`-sees-buildings cost optimisation (§4, next sortie of opportunity); `WM-B8`'s
   fixture-scale fine grid; widening the query cone for attention capture (§10 — a number, when
   that backlog item is built). **The watch wedge is withdrawn, not deferred** (§11b).

## §14. Risks & Unknowns added by this revision

- **A new inbound network listener inside DCS.** The LOS Hook binds a UDP socket. Mitigations, all
  specified rather than assumed: **bind 127.0.0.1 only** (the collector runs on the same Windows box
  as DCS), validate twice (collector and Hook), and use the value **only as an index into a fixed
  literal table**. The pattern is shipped in `Export.lua`, but **in the Export state, not a Hook
  state** — same LuaSocket, and the Hook state is the less restricted of the two, so this is low risk
  rather than no risk. First deployment confirms it from `dcs.log`; no probe sortie needed.
- **The wedge can silently be narrower than the gaze** if a push is lost and the Hook never notices.
  That is coverage loss, not wrongness (§9c) — but it is *invisible* without `hour_used` in the
  payload and in the trace. Treat those two fields as required, the same way §2 treated
  `units_in_bubble`.
- **§10's non-measured rows.** Every figure except the ~10/poll is a uniform-azimuth estimate and
  units are not uniform in azimuth. `units_in_wedge` is the fix and it arrives with Stage 1.
- **`SEGMENT` cost at 10 km ray length is still unmeasured** (Finding 21 used 2 km rays). The margin
  is now enormous rather than 20%: at ~10 units/poll even a 5× penalty is ~1.3 ms. **This risk is
  effectively retired by cone scoping** — recorded as such rather than deleted.
- **The 18–20 ms payload-indifferent bridge tail remains** and is not ours (Finding 3). Expect one;
  do not re-open the cone over it.
- **Reciprocity of `land.isVisible` / `SEGMENT` is still assumed, not measured.** Unchanged, and the
  engagement term's justification still rests on it.
- **The peripheral-bypass seam is a live tripwire for this design.** The day an attention-capture
  trigger is wired, `gaze_for` starts returning `None` for salient candidates, gate 0 stops filtering
  them, and a 45° query cone becomes narrower than what gate 4 is asked for — silently, as coverage
  loss. **Whoever wires the first trigger must widen `fov_half_deg` to 130**, and this sentence is
  the only thing that will tell them so. Worth a line in the attention-capture backlog item too; the
  arbitrary-FOV parameter (§9b) is what makes that a one-number change rather than a redesign.

## §15. Second-order effect

**This revision creates a general "tell the aircraft where to look" command channel, and LOS is its
first consumer rather than its only one.** The user's own framing — a look directive is the same class
of traffic as a switch press — makes it reusable by anything that needs the simulation side to know
where Petrovich's attention is: the 9K113 slice when it lands, any future tree-aware LOS call, and the
in-cockpit feedback that would let the pilot *see* where the copilot is looking. That is a larger
unlock than the frame-time saving, and it is worth not burying it inside the LOS hook: **the setter
table and the listener should be written so a second consumer can read `PB_LOOK_HOUR` /
`PB_LOOK_FOV_DEG` without owning them** — hence the `PB_LOOK_*` naming rather than `PB_LOS_*` (§9b).
The user's instruction to carry an **arbitrary** FOV rather than a named preset is what makes this
general: a channel that says "look here, this wide" serves any consumer, whereas one that says
`focus | mask | off` only ever serves the thing those names were coined for.

Narrowing, in the other direction: binding the LOS feed to the gaze couples a *DCS-side* feed to a
body-layer concept for the first time. The coupling is one integer with a closed vocabulary and a
fail-safe degradation, which is about as thin as it gets — but a future redesign of the scan model
(`gaze.py`'s plan-C "swap the table" escape hatch) now has a second place to look.

## §16. Decisions Requiring User Input (two)

**Closed since §6:** (1) the SEGMENT gate — resolved by Finding 21, no probe needed; (2) nearest-first
vs two-tier ordering — moot, withdrawn; (3) is a ≤2 ms call imperceptible — superseded, the call is
now ~0.25–1.1 ms and Stage 4 still measures it; (4) `WM-B7` — retired, `WM-B8` filed.
**Closed by the user during this revision:** the watch-wedge question I was about to ask — *"LOS only
matters for things that we would process, if there is LOS"* settles it, and §11b records the
withdrawn design; and the preset-vs-arbitrary-FOV interface — *"accept arbitrary FOV"*, now §9b.

1. **Confirm the command-channel reading of the fixed-literal rule, and which variant.** This
   revision holds that a validated numeric selecting among 42 hand-authored literals (§9b's digit
   dispatch) honours the rule rather than bending it, on the precedent of `Export.lua`'s own
   `petrovich_search` dispatch — which already takes a LAN command and drives real cockpit switches.
   The rule is audited and load-bearing, so **this should be your call, not mine.** Two sub-choices:
   - **Digit dispatch (recommended).** 42 trivial literals, nothing ever concatenated, invariant
     untouched. Costs about forty lines of repetitive Lua.
   - **One validated `string.format("%d", clamped)` splice.** Four lines instead of forty, almost
     certainly safe — but the property becomes "correct because the validator is correct" rather
     than "structurally impossible". Cheaper to write, more to audit forever.

   If you would rather not touch the rule at all, the fallback is to derive the free-scan hour
   Lua-side from `timer.getTime()` (the scan plan is a pure function of sim time), needing no
   inbound channel — but it **duplicates body-layer's scan table across the seam and goes blind the
   moment you issue a commanded scan or raise binoculars**, i.e. it fails exactly when you asked for
   attention. Not recommended.
2. **Does the query cone (90° full, `fov_half_deg = 45`) feel right, or should it be one o'clock
   hour (30°)?** 90° is three
   o'clock hours: the one being scanned plus one either side, so a poll straddling a dwell change
   still covers the gaze. 30° is 3× cheaper and would drop coverage on roughly half the polls at 1 Hz
   against a 2 s dwell. **Recommendation: 90°** — the cost it saves is already negligible, and the
   thing it buys is not having to reason about timing at all.
