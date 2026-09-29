### Goal

Ask DCS for line of sight directly (terrain + buildings, batched, at the aircraft layer) instead
of approximating it from world-model's own SRTM elevation grid, and use our own model only for
*detectability* (angular size, optic, conditions, salience) on top of that answered fact.

### Starting premise, corrected before this plan

The dispatch brief stated "trees have no DCS route at all" as settled. It is not. The user's own
evidence: the F10 map renders individual trees, flying into one crashes the aircraft (collision
geometry per tree), and DCS's own AI Petrovich with the 9K113 is blocked by trees — so a shipped
code path performs tree-occluded LOS against a specific target. What the Windows investigation
actually settled is narrower: **`world.searchObjects` never returns a tree object, and
`land.isVisible` is terrain-only.** Those two scripting-API calls exclude trees. Whether any
*other* exposed call reaches the engine's own tree-aware path is open, not closed. This plan
treats terrain+building LOS as measured and ready to build, and treats trees as a named,
unresolved follow-up investigation that does not block it — see "Trees" below.

### Effort/value check first

**The specific defect this was proposed to fix already has a shipped mitigation.** The debug
report (`plans/missed-aaa-detection/debug.md`) diagnosed a real miss — SRTM overestimating terrain
under a real unit's position placed it permanently "underground" to the model — and Fix option 1
(a 12 m tolerance on the terrain check, sized to M7's own recorded SRTM-vs-DCS stddev) is **already
merged** into `world-model/src/query/line_of_sight.py` (`_TERRAIN_TOLERANCE_M = 12.0`, with a long
comment carrying the Mi-24P-specific justification for that number). So X-B29's value is not "stop
missing AAA that DCS driving LOS would have caught" — that class is already closed. Its real,
smaller value is:

1. Removing reliance on a *guessed* error margin for terrain, by asking DCS for ground truth
   instead of interpolating a 1000 m SRTM grid. The 12 m tolerance still lets through false
   negatives beyond its own margin (the reproduction table showed +20 m still blocking); DCS's own
   terrain has none of that error, at any margin.
2. **Building occlusion, which does not exist today in either path.** This is new capability, not
   a fix — and it is the cheaper, lower-risk, higher-value half of this plan (Stage 1 below).

Recommendation: ship building occlusion first (new, additive, cannot regress anything that works
today) and treat the terrain-source swap as a second, independent, lower-urgency stage — not
"this is all one bug fix that must land together."

### The model

```
DCS answers "is there terrain/a building in the way?" (a physical fact)
        -> our own model answers "can Petrovich actually detect this?" (angular size,
           optic, conditions, salience — check_visibility's existing gates, unchanged)
```

LOS stops being approximated from a static grid and becomes something DCS is asked directly, for
every ground/air unit inside the already-settled 10 km player bubble (`todo/todo.md`, "Player
bubble: 10 km, settled 2026-09-28"), once per second, batched in one bridge call — exactly the
shape the user proposed. Nothing here grants Petrovich new knowledge: LOS is a fact about the
physical world (a ray either crosses geometry or it doesn't), not information about a unit's
identity or position that he could not otherwise derive; this project's no-omniscience invariant is
about identity/position/interpretation, and this plan touches none of those.

### CORRECTION 2 (user, 2026-09-29) — LOS is computed collector-side from TRUE positions, and belief never computes it at all

The correction below got the conclusion right and the mechanism wrong. It proposed the engagement
term ask point-to-point using the contact's **believed** position, and called preserving that error
a feature. **The user rejected that too, and the reasoning is the one that settles the whole
design:**

> *"Whether we can see a target, LOS or no LOS, is a world state **fact**. It is not a belief. Our
> belief about a unit's location is belief and can be wrong. It in no way affects LOS, it is a
> property of the simulated world, a 'physical' fact even though simulated. LOS **must use** the
> unit's **factual** location and our ownship's **factual** location. Belief is in a layer above
> all this."*
>
> *"--> bake 'LOS / no-LOS' boolean into unit data transmitted from collector. Then belief system
> can use that information without doing its own bogus calculations."*

**Why the believed-position version was not merely different but wrong.** A line of sight to a
point where nothing stands is not a preserved error, it is a fabricated answer to a question about
empty space. The ray either clears real geometry between two real points or it does not. Asking
about a believed position produces a verdict that corresponds to no physical fact at all — and it
would have read as principled, which is what makes it worth recording rather than quietly fixing.

**The design, then:**

1. **The collector computes LOS per unit**, true ownship position to true unit position, batched
   through the mission bridge in one call at the settled cadence. Ownship truth it already has from
   telemetry; unit truth it already has from `/world_objects/latest`.
2. **The boolean ships as a field on the unit data** — the same feed, the same join, no second
   channel and no new staleness class beyond the feed's own.
3. **Perception consumes it as a gate input** at `visibility.check_visibility` gate 4, replacing
   that gate's own terrain computation. This is pre-boundary, where identity legitimately exists.
4. **Belief never computes LOS.** The observed LOS state rides into the `Percept` and is carried on
   the `Contact` as a last-known property, exactly as classification, cardinality and motion already
   are. `belief/contacts.py::tick`'s engagement term **reads** that stored value instead of calling
   `line_of_sight_clear` at all.

Point 4 is the load-bearing one for an implementer: it is not "belief calls a different LOS
function", it is **belief stops calling one**. The pattern is already the project's own — perception
observes, belief remembers, nothing downstream re-derives. A contact that has not been observed
recently carries a stale LOS flag for the same reason it carries a stale classification, and the
existing decay/certainty machinery is where that is expressed.

**What this leaves of world-model's `line_of_sight_clear`:** the offline and test path, unchanged
and still first-class — Mission Interpreter enrichment, the replay harness, and every test that must
run with no DCS and no collector (`plans/body-layer/plan.md` §2). It stops being the live path.

### CORRECTION (user, 2026-09-29): both call sites use DCS LOS — the obstacle was the join key, not belief

The section below concludes that `belief/contacts.py::tick`'s engagement term "keeps calling
world-model's offline primitive forever, unaffected by this plan", because a `Contact` structurally
cannot carry a DCS object id. **The user rejected that conclusion, and he is right:**

> *"No. With cheap access to DCS calculated LOS, that is the world truth and we must use that. LOS
> is not a question of belief, it is a property of the DCS world state. If LOS exists and other
> detection criteria pass, we can see it."*

**What the analysis below actually established, and what it wrongly generalised.** The real
obstacle is narrower than "belief cannot consume this": it is that a feed **keyed by DCS unit
name** has no key the engagement term can join on. That much is true. But line of sight does not
have to be asked per unit — `land.isVisible` and the `SEGMENT` search both take **coordinates, not
unit handles**. So the engagement term asks exactly what it asks today, point to point, with the
contact's *believed* position as the endpoint; only the terrain and occluder source underneath
changes.

**So there are two query shapes on one wire, not two mechanisms:**

| call site | endpoint | keyed by |
|---|---|---|
| `visibility.check_visibility` gate 4 | the candidate's true position (pre-boundary, already holds it) | DCS unit, or coordinates — either works |
| `contacts.tick` engagement term | the contact's **believed** position | our own contact id, never a DCS one |

**The no-omniscience boundary holds in both directions, and is worth stating explicitly because
this is the seam where it would be easiest to lose.** We send a position we already believe; DCS
returns a geometric fact about a ray. Nothing comes back that we did not already have — no
identity, no true position, no existence claim about anything we had not already posited.

**And one property to preserve deliberately rather than treat as a defect:** when the believed
position is wrong, the point-to-point query returns the LOS answer *for that wrong point*. That is
correct. Petrovich checks whether he can see where he **thinks** the thing is, which is what a crew
member does — the error is preserved rather than laundered by asking about the real unit instead.

**What this changes in the staging below:** the engagement term is no longer out of scope by
invariant. It is a second consumer of the same source, and whether it lands in the same stage as
the detection gate or a following one is an ordinary sequencing decision, not a structural one.
The rest of the section below stands as written — its rejection of per-candidate round trips, and
its argument for letting DCS answer terrain and buildings together on one sightline rather than
mixing provenances, are unaffected.

### Where the verdict is computed, and the finding that decides it

**Only the perception-layer gate can consume a live, DCS-object-keyed verdict — the belief-layer
engagement term cannot, by an existing invariant, not by this plan's choice.**

`geometry.line_of_sight_clear` (body-layer) has exactly two callers today:

1. `perception/visibility.py::check_visibility`'s gate 4 — called with a `WorldObjectCandidate`,
   which still carries ground-truth identity (`candidate.object_id`). This is *before* the
   no-omniscience boundary (`belief/percept.py`).
2. `belief/contacts.py::tick`'s engagement term (`plans/watch-reporting/plan.md` Stage 4) — called
   from a closure over a `Contact`'s *belief-estimated* `GeoPosition`, with no DCS object id at
   all. `Contact` structurally cannot carry one (`body-layer/CLAUDE.md`'s invariant: "belief code
   never sees `Observation.derived_world_position` or a DCS object id" — `detection_trace_writer.py`
   is the one sanctioned exception, and this is not it).

So a live feed keyed by DCS unit identity can only ever be joined at call site 1. Call site 2
keeps calling world-model's offline primitive forever, unaffected by this plan. This is worth
stating plainly because it means "DCS-driven LOS" does not become uniformly true everywhere LOS is
checked in this codebase — only at the detection gate, which is also the only place it needed to
be true to close the value this plan is chasing.

**Rejected alternatives**, per the brief's request to argue rather than assume the user's shape:

- *Body-layer asks DCS per-candidate.* Rejected — this is the exact N-round-trips-per-poll shape
  `todo/backlog.md`'s X-B29 entry itself rejects, and it does not remove the LAN-cost objection
  X-B26/X-B30 already argued about per-candidate building checks.
- *Body-layer keeps its own terrain LOS and asks DCS only for building occluders.* Rejected —
  still N round trips (one per candidate, to test buildings along that one candidate's sightline),
  throws away the batching that is the whole reason the LAN stopped being a problem, and — more
  importantly — mixes two terrain provenances on one sightline (our SRTM-derived terrain, DCS's
  building geometry). A sightline that clears our terrain model but would have grazed DCS's own
  (different) terrain surface near a ridge is exactly the failure class the missed-AAA bug was, just
  moved to a different geometry. Letting DCS answer the whole sightline test — terrain and
  buildings together — removes that mismatch class entirely rather than only the building half of
  it.

### What exactly is asked, and for which units

Every unit aircraft-layer already knows about from `LoGetWorldObjects` (via `/world_objects/latest`
today; the new hook script enumerates independently, see below), excluding ownship
(`is_ownship`), filtered to the 10 km player bubble around ownship's current position — the same
radius body-layer's detection pipeline is already scoped to.

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
   Duplicating body-layer's cockpit-mask/gaze logic in Lua, across the seam, to shave a
   already-cheap number, is complexity with no measured benefit.

So: bubble-only filtering, done once per poll inside the Lua snippet (distance check against
ownship's own position, the same self-contained shape `petrobrain-mission-telemetry-hook.lua`
already uses for enumerating units — no argument passing needed from the collector).

### Cadence

1 Hz, riding the same `dostring_in("scripting", …)` / Hook-script pattern
`petrobrain-mission-telemetry-hook.lua` already runs at 1 Hz for unit velocity. The user's own
"maybe not every tick?" is answered from the physics, not the cost: at 83 m/s (the backlog entry's
own figure) LOS state changes over seconds, and body-layer's naked-eye poll is 5 Hz — so a verdict
up to ~1-2 s old is not stale relative to how fast the underlying fact actually changes. No new
cadence concept is introduced; this is a fourth sibling to the existing telemetry/world-objects/
indication feeds, all polled from body-layer's own 5 Hz loop regardless of how often aircraft-layer
refreshes them.

### Wire shape and the join key that makes staleness precedented, not new

New Lua script `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`, structurally a sibling
of `petrobrain-mission-telemetry-hook.lua` — own loopback port, own `onSimulationStart/Frame/Stop`
lifecycle, own fixed code-literal snippet run via `dostring_in`, `timer.getTime()` stamped inside
the scripting state (never `DCS.getRealTime()`, for the same replay-determinism reason that file's
header already gives). The snippet enumerates units the same way `VELOCITY_CODE` does
(`coalition.getGroups`/`getUnits`), filters to the bubble, and for each survivor runs the sightline
test (Stage 1: buildings only; Stage 2 adds terrain — see below), packing
`"unitName:buildingClear01;..."` the same delimited-string-in-JSON-envelope shape every other bridge
feed here uses.

**Join key: `unit_name`, not `object_id`.** `object_id` is `LoGetWorldObjects`'s `pairs()` key,
explicitly flagged in `aircraft-layer/src/schema/world_objects.py`'s own docstring as
"unconfirmed" for cross-poll stability. `unit_name` (`Unit:getName()`, matching
`LoGetWorldObjects`'s `UnitName`) is the join key movement detection already established for
exactly this same cross-feed problem (`plans/movement-detection/plan.md` Decision 1,
`naked_eye_source.py::_resolve_velocity_by_object_id`). This plan reuses that precedent rather than
inventing a second one: a new `_resolve_los_by_unit_name` follows the same shape — join this poll's
`/line_of_sight/latest` snapshot onto the raw `/world_objects/latest` dicts by `unit_name`,
computing a skew (`|world_objects_t_sim - line_of_sight_t_sim|`) exactly as `_resolve_velocity_by_
object_id` already computes `motion_skew_s`, and dropping to `None` when that skew exceeds a new
`LOS_MAX_AGE_S` constant (propose 3.0 s — three poll cycles at the feed's own 1 Hz rate, mirroring
`brain-layer`'s D4 pattern of comparing a carried-through sim timestamp against "now" and discarding
what's too old, `crew_console.py`'s `BRAIN_REPLY_MAX_AGE_S`). The result lands on a new optional
field, `WorldObjectCandidate.live_los_clear: bool | None` — `None` means "no live verdict this poll
(feed absent, unit not in the bubble that poll, or too stale)", never coerced to a guessed true/
false, same tri-state discipline every other join field in this module already follows
(`is_ownship`, `velocity`, `heading_true_deg`).

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

### What happens to the 12 m tolerance and the probe grid

Unchanged, and this plan does not touch either. `_TERRAIN_TOLERANCE_M` and world-model's
`line_of_sight_clear` remain the offline/test path and the belief-layer engagement term's *only*
path (see "Where the verdict is computed" above) — both real, permanent uses, not a stopgap this
plan replaces. The probe grid (M8) and its spacing redesign stay exactly where `todo/backlog.md`'s
X-B28 (superseded) already left them: lower priority, for land formations/`describe_position`, not
line of sight. Nothing here changes that.

### Trees — REFRAMED by the user, 2026-09-29, after this plan was drafted

The section below was written against the standing measurement that a vehicle under trees is
undetectable at any range from any optic, which made trees look like a *forest* problem — a
statistical transmission model over landcover polygons, safely off the critical path. **The user
has corrected the scope, and it changes the shape of the requirement:**

> *"'vehicle under trees is undetectable at any range from any optic' — in a forest, yes very much.
> But if it's just a couple of trees or a line of trees along a road, then tree LOS really matters.
> We must investigate if there is any way to get LOS considering trees. We don't need to know
> individual tree placement (though that wouldn't hurt and could be useful), but need to know if
> they block LOS. If we can."*

So there are **two distinct tree problems**, and only the first is covered by the landcover model:

1. **Forest** — a mass of canopy, where the honest model is probabilistic transmission over an OSM
   polygon and the answer is "he cannot see in there". The measurement supports this.
2. **Sparse and linear tree cover** — a treeline along a road, a windbreak, a handful of trees
   between the aircraft and a vehicle. A polygon model answers this *wrongly in both directions*:
   OSM may carry no polygon at all for a roadside treeline, and where it does, a probability over
   an area cannot express "this particular sightline is blocked and the one ten metres left is
   not". This is **discrete occlusion**, the same shape as the building test, and it is exactly the
   case a Mi-24P attacking along a road meets constantly.

**What this changes:** the tree question is no longer safely deferrable behind Stages 1 and 2. The
user's ask is explicit — *"We must investigate if there is any way to get LOS considering trees"* —
and his acceptance criterion is looser than full tree geometry: **a blocked/clear verdict is
enough**; individual tree placement would be a bonus, not a requirement. That materially widens
what counts as success for the probes named below, and it means a negative result on those probes
is a real finding rather than a formality.

**It does not change the staging below.** Stage 1 (buildings) is unaffected, measured and ready;
trees ride a parallel investigation rather than blocking it. But if the probes come back positive,
the tree verdict joins the same batched sightline call rather than becoming a second mechanism —
which is an argument for settling the probes before Stage 1's wire format is frozen.

**Fallback settled in advance (user, 2026-09-29):** *"If there's no way for tree aware LOS, then
we'll take the statistical model instead."* So the probes are not a gate — a negative result
selects the OSM-landcover transmission model rather than leaving trees unhandled, and the sparse /
linear-treeline case above is then a known, accepted limitation of that model rather than an
unsolved problem. Worth recording that the decision was taken *before* the result, so a negative
does not get relitigated as a failure.

### Trees

**Not resolved, and this plan does not resolve it.** Established: `world.searchObjects` never
returns a tree object across ten flights (not a scenery object, no volume search will find one),
and `land.isVisible` is confirmed terrain-only (the SEGMENT-through-known-buildings control,
Finding 12). Both facts stand. **Also established, per the user's correction, and not previously
weighed**: the F10 map renders individual trees, tree collision exists per-tree (crashing into one
ends the aircraft), and DCS's own AI Petrovich with the 9K113 is blocked by trees — so the engine
holds tree geometry and at least one shipped code path (`Scripts/AI/Detection.lua`'s
`trees_LOS_test_T4`, feeding `Controller.isTargetDetected`/`getDetectedTargets`) tests LOS against
it. The open question is narrow and specific: **is there any scripting-API call that reaches that
same tree-aware geometry, as opposed to the terrain-only surface `land.*` exposes?**

Named follow-up for the Windows-box session, not this plan's build work:

1. **Characterise `Controller.isTargetDetected`/`getDetectedTargets` even though it is probably the
   wrong shape to consume directly.** Set up a controlled pair: an identical target with clear
   terrain+building LOS, once with trees between observer and target and once without. If
   `isTargetDetected` returns `false` only in the tree case, it *does* reach the tree test — and
   then the real question becomes whether its skill/alertness/range/reaction-time terms can be
   pinned to values that make it behave as a pure LOS oracle (e.g. maximum skill, zero reaction
   time, `Controller.Detection.VISUAL` only), or whether those terms are inseparable from the
   result. Reject it only once that's tried, not on the shape alone.
2. **Fire `land.getIP` along a sightline into known tree canopy** (the Windows session flagged this
   and never tried it). If the returned impact point sits at canopy height rather than bare-ground
   height, `getIP` is sensing something above the terrain mesh at that point — worth knowing even
   if it turns out to be a height-field artifact rather than a real per-tree hit.

**If neither resolves it, the interim stand-in is the OSM `landcover` polygon set world-model
already holds (44,811 polygons) — but built as a probabilistic transmission model per optic, not a
binary ray test, because that is a genuinely different mechanism from the SEGMENT/`isVisible`
tests this plan builds, not a variant of them.** Naming it as an interim stand-in matters
concretely: if a tree-aware call is later found, it replaces this model outright rather than being
fused with it — a design that treated the statistical model as permanent would resist that
replacement. **Not built in this plan.** File as its own backlog item once the two probes above
report back, rather than building it against a question that might make it moot.

### Affected Modules / Files

- `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` — new. Sibling Hook script to
  `petrobrain-mission-telemetry-hook.lua`; Stage 1 tests buildings only (`world.searchObjects` +
  `world.VolumeType.SEGMENT`), Stage 2 adds terrain (`land.isVisible`).
- `aircraft-layer/src/schema/line_of_sight.py` — new. `LineOfSightVerdict`
  (`unit_name`, `clear`, `dcs_model_time_s`, `received_wall_clock_s`) and `LineOfSightSnapshot`,
  mirroring `world_objects.py`'s shape.
- `aircraft-layer/src/collector/cache.py` — new `LineOfSightCache`, same shape as
  `WorldObjectsCache`.
- `aircraft-layer/src/collector/__main__.py` — wire the new receiver/cache in, alongside the
  existing four.
- `aircraft-layer/src/api/server.py` — new `GET /line_of_sight/latest`.
- `body-layer/src/aircraft_client.py` — new `get_line_of_sight_latest()`, same shape as
  `get_unit_velocity_latest()`.
- `body-layer/src/perception/naked_eye_source.py` — new `_resolve_los_by_unit_name` (mirrors
  `_resolve_velocity_by_object_id`), wired into the same poll step that already resolves velocity;
  new `LOS_MAX_AGE_S` constant.
- `body-layer/src/perception/association.py` — `WorldObjectCandidate` gains
  `live_los_clear: bool | None = None`.
- `body-layer/src/perception/visibility.py` — gate 4 reads `candidate.live_los_clear` first,
  falls back to `line_of_sight_clear` unchanged when `None`.
- `world-model/src/query/line_of_sight.py`, `body-layer/src/perception/geometry.py`,
  `body-layer/src/belief/contacts.py` — **unchanged.** Named here so a reader checking "what did
  this plan touch" sees the negative confirmed, not merely absent.

### Implementation Plan

1. **Stage 1 — buildings only, the new-capability slice.** Hook script + schema + cache + endpoint
   + client method, all building-occlusion only (`world.searchObjects`/`SEGMENT`, ~8.7 µs/
   sightline). Join and wire into `check_visibility` as above. Flyable: any AAA/vehicle sitting
   behind a real building that reads as clear today should now read as occluded. Zero regression
   risk — `live_los_clear` is `None` until this stage's feed exists, and the fallback path is
   exactly today's code.
2. **Stage 2 — terrain via `land.isVisible`, replacing the SRTM sample for the live path only.**
   Add the terrain test (~10.6 µs/sightline) to the same hook snippet; `clear = building_clear and
   terrain_clear`. This is the tolerance-removal half — verify against a live sortie flown in
   mountainous terrain (the missed-AAA geometry) that the live path agrees with the already-shipped
   12 m-tolerance fallback at the case that motivated it, and diverges (correctly) somewhere the
   tolerance alone would not have caught.
3. **Stage 3 — acceptance sortie.** One flight validating both: a target behind a building
   (new detection gained), and a paused-state check per `aircraft-layer/CLAUDE.md`'s testing note
   (a bug class this exact family of Hook script has hit before).
4. **Not this plan**: the tree probes above (hand to the Windows-box session whenever it next
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
  mechanism accounted for trees at all; after Stage 2, a target hidden by trees but with clear
  terrain+building LOS will read as visible, same as today — not a regression, but worth saying
  plainly since "DCS-driven LOS" could otherwise be misread as "solves occlusion."

### Second-order effect

Once buildings+terrain LOS is DCS-driven, world-model's elevation grid has no remaining role in
*detection correctness* — only in land-formation description and offline Mission Interpreter
enrichment, exactly as X-B28 (superseded) already recorded. That narrows, rather than blocks, the
already-deprioritized probe-grid-spacing redesign: whoever picks it up next should size spacing
for `describe_position`/ridge-valley description quality, with no line-of-sight accuracy
requirement pulling in the opposite direction.

### Decisions Requiring User Input

- **`LOS_MAX_AGE_S`'s value (proposed 3.0 s)** — reasonable default, not measured; confirm or
  adjust once flown.
- **Stage 2's terrain swap is optional relative to Stage 1.** Given the 12 m tolerance already
  covers the specific defect that motivated this work, confirm you want the terrain-source swap
  built now rather than deferred behind Stage 1 landing and being flown for a while first.
- **Whether to hand the tree probes to the Windows-box session now or after Stage 1/2 land** — they
  are independent of this plan's build work and can run in parallel, but only if scheduled.
