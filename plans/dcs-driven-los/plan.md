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

### Effort/value check first

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
   Duplicating body-layer's cockpit-mask/gaze logic in Lua, across the seam, to shave an
   already-cheap number, is complexity with no measured benefit.

So: bubble-only filtering, done once per poll inside the Lua snippet (distance check against
ownship's own true position, the same self-contained shape `petrobrain-mission-telemetry-hook.lua`
already uses for enumerating units — no argument passing needed from the collector).

### Cadence

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

### Implementation Plan

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

- **Confirm the engagement-term behaviour change above** (hybrid-only and stale contacts always
  fail-open to "can be seen," rather than getting an actively-computed terrain clearance as they do
  today). This is the one substantive consequence of "belief stops computing LOS" that was not
  visible before working through the reciprocity argument, and it changes what "safe from" can mean
  for a contact outside the naked-eye channel's recent coverage.
- **`LOS_MAX_AGE_S`'s value (proposed 3.0 s)** — reasonable default, not measured; confirm or
  adjust once flown.
- **Stage 3's terrain swap is optional relative to Stages 1-2.** Given the 12 m tolerance already
  covers the specific defect that motivated this work, confirm you want the terrain-source swap
  built now rather than deferred behind Stage 1/2 landing and being flown for a while first.
- **Whether to hand the tree probes to the Windows-box session now or after Stages 1-3 land** —
  they are independent of this plan's build work and can run in parallel, but only if scheduled.
