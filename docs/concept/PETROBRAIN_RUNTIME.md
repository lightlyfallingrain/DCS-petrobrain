# Petrobrain Runtime — Draft Design

> **Status: Draft / provisional**
>
> This document describes the intended runtime Petrovich cognition layer.
>
> It depends heavily on:
>
> 1. what the DCS World Model Builder can represent and query reliably;
> 2. what the Mission Interpreter can produce reliably;
> 3. what Petrovich perception/state can actually be extracted from DCS.
>
> Do not treat the interfaces or structures below as final. Revise this document as the preceding layers mature.
>
> See also `division-or-responsibility.md` for a microservice-style decomposition of this layer into brain/body/aircraft/memory sublayers with concrete I/O examples — also draft/provisional, not yet reconciled in detail with this document.

## Purpose

Petrobrain aims to turn DCS Mi-24 Petrovich from a set of scripted AI functions into something closer to a useful crew member.

The first and highest-priority role is:

> **Petrovich acting as gunner/pilot-operator while the human player flies from the rear cockpit.**

The first problem is not autonomous tactics.

The first problem is:

> **memory + situational awareness + useful communication**

Petrobrain should eventually:

- remember contacts Petrovich has actually detected;
- know where those contacts were in the simulated world;
- relate them to terrain and mission geography;
- distinguish current observation from stale memory;
- maintain attention on targets or areas;
- understand references such as “that Shilka by the village”;
- answer questions about known contacts;
- generate useful proactive callouts;
- understand current mission context and priorities.

It must not make Petrovich omniscient.

## Runtime architecture

```text
Persistent World Model
        │
Mission Understanding
        │
        ▼
┌─────────────────────────────┐
│ Petrobrain Runtime          │
│                             │
│ aircraft state              │
│ perception adapter          │
│ contact memory              │
│ spatial relationships       │
│ attention / relevance       │
│ mission state               │
│ intent / reference parser   │
│ response generation         │
└──────────────┬──────────────┘
               │
               ▼
         speech / actions
```

The LLM is only one component.

## Core principle

> **Petrobrain remembers application state. The LLM does not “remember” via a huge chat history.**

Long-lived information should be explicit:

```text
contact records
observations
mission state
attention state
player intent
recent events
```

The LLM sees relevant subsets.

## Knowledge layers

### 1. World knowledge

Provided by the World Model:

- roads;
- settlements;
- ridges;
- valleys;
- named places;
- terrain geometry.

### 2. Mission knowledge

Provided by the Mission Interpreter:

- objective;
- role;
- protected friendly element;
- expected threats;
- route;
- key terrain;
- player plan;
- priorities.

### 3. Episodic memory

What Petrovich has observed during this sortie:

- detected BMP;
- lost sight of Shilka;
- reacquired vehicle;
- player asked to watch village;
- target moved north.

### 4. Working memory

What matters now:

- current tracked contact;
- player-selected target;
- high-priority threat;
- current mission phase;
- recent significant event.

These memories need different lifetimes and update rules.

## World truth versus Petrovich belief

This is a fundamental boundary.

DCS may know:

```text
Unit #817 is a ZSU-23-4
at exact X/Z
heading 120
alive
```

Petrovich may know only:

```text
Possible air-defence vehicle
last seen 45 seconds ago
north edge of village
moving east
```

Petrobrain should operate on **belief state**, not omniscient DCS truth.

Where possible, perception should come from Petrovich's actual DCS targeting/detection information.

## World model acquisition: incremental, on-demand probing

> **Status: proposed, not implemented.** Raised 2026-09-06, right after the World Model
> Builder's M7 (full-theatre pipeline) completed. This section depends on an open technical
> unknown (below) that should be resolved, likely by the Investigator agent, before any of this
> gets designed further — do not start implementing against this section yet. See
> `WORLD_MODEL_BUILDER.md`'s matching "Incremental, on-demand probe-tier data" section for the
> storage/schema side of the same idea.

Full-theatre live-mission probing (the thing M7 deliberately avoided for elevation by using SRTM
instead) is expensive, and mostly wasted effort: a player — especially flying a helicopter — is
very unlikely to need probe-tier terrain resolution (fine elevation, `surface_type`, ridge/
valley) across a whole theatre. Real sorties are geographically contained.

**Idea**: treat the player's position as an expanding "known-area bubble" instead of pre-building
theatre-wide coverage.

- The World Model's base tier (roads, settlements, airfields, beacons, navaids — see
  `WORLD_MODEL_BUILDER.md`) stays exactly as M7 built it: cheap, whole-theatre, one offline pass,
  no reason to change.
- The **probe tier** (elevation detail beyond SRTM, `surface_type`, ridge/valley) is instead
  filled incrementally, chunk by chunk, only for terrain the player has actually flown near.
- When Petrobrain (or an underlying perception/terrain-awareness check) queries a chunk the store
  marks `unqueried`, and the aircraft is near or approaching it, trigger a **throttled** live DCS
  probe for that chunk — and plausibly a look-ahead ring of chunks in the direction of travel, so
  the bubble grows ahead of the aircraft rather than always one step behind it. Write the result
  back into the persistent store; the known-coverage bubble grows outward as the player explores.
- "Throttled" matters for the same reason M5/M7's terrain probes already use
  `timer.scheduleFunction` chunking instead of one blocking loop (see
  `tools/dcs-mission-probe/README.md`'s note on `terrain_probe_*.lua`'s incremental-ladder
  pattern) — a burst of live `land.getHeight`/`land.getSurfaceType` calls mid-mission must not
  visibly impact game performance. Rate-limit probe calls per tick, same discipline, just
  triggered by player movement instead of a pre-planned grid walk.
- Ridge/valley classification (M6's local Laplacian-curvature method) runs naturally per-chunk
  once that chunk's elevation is available — no separate design needed, it already operates on a
  local grid neighborhood.

**The one open blocker this whole idea hinges on**: there is currently no live data path from a
running DCS mission back into the persistent world-model store. Every extraction to date
(`world-model/WORKFLOW.md`) is a manual, offline, batch round-trip — a mission runs, writes to
`Saved Games/DCS/Logs/`, a human syncs the file back to the Mac hours later via Dropbox, then it
gets parsed into the store. "Fly into unmapped terrain and have Petrobrain answer a question
about it within the same flight" needs something meaningfully faster than that — a live socket
export, a Windows-side watcher process shipping newly-written probe output over the existing
Mac/Windows LAN split (see the project's compute-topology notes) in near-real time, or something
else entirely. Resolve this — likely via an Investigator pass into DCS's live export options
(`Export.lua`, DCS-gRPC, UDP telemetry, etc.) — before designing the chunk-grid/throttling
mechanics in more detail.

## Perception adapter

**Status (2026-09-08): shipped, as a hybrid design neither originally-anticipated tier
predicted.** `plans/pb1-perception-logger/plan.md` (see that plan's Session 4 and its
"Association design" section for the full record) ran a live-DCS spike answering the technical
unknown this section originally posed — what Petrovich detection/target state can actually be
extracted from DCS — across four independent channels (`list_indication(2)`/ASP-17 sight values,
`get_param_handle` on the sight's named params, `LoGetTargetInformation`,
`LoGetLockedTargetInformation`/`LoGetSightingSystemInfo`). **Every numeric-geometry channel is
confirmed dead** (nil, empty, or stuck at zero across four live flights) — Petrovich's detection
engine is compiled/native, not reachable via any documented Lua/Export API, and reverse-engineering
it was explicitly considered and rejected as out of scope (breaks the read-only-DCS-access
invariant, no sanctioned API surface). **One channel works and is real**:
`list_indication(HELPERAI_DEVICE_ID)` (device ID `6`, confirmed live) returns Petrovich's own
spotting/classification text (`middle_list_text`/`lower_list_text`/`lower_lower_list_text`, e.g.
`"Ural truck"`) — no numeric field of any kind, confirmed across ~4000 live samples.

The shipped design (`aircraft-layer/dcs-export/Export.lua`,
`aircraft-layer/src/schema/petrovich_indication.py`,
`body-layer/src/perception/hybrid_source.py`, `body-layer/src/perception/association.py`) splits
the observation into two mechanisms with different jobs:

- **Detection existence is real, not synthetic.** `HybridPerceptionSource` never emits an
  `Observation` unless HelperAI's own live UI actually populated `middle_list_text` — this is
  Petrovich's own (compiled, unreachable) detection logic deciding something is there, not a
  heuristic standing in for that decision. This is the invariant's primary defense, structurally
  stronger than either originally-anticipated tier (a full real feed with real bearing, or a pure
  ground-truth proxy) would have been.
- **Which world object the detection refers to, and its geometry, is inferred, not read.** No
  channel ever exposes native bearing/range — `perception.association`'s `associate()` resolves
  the classification text against a `LoGetWorldObjects` candidate pool (no coalition/IFF
  filtering) using a range-cap + forward-hemisphere plausibility filter and keyword-overlap
  type-match scoring, then `perception.geometry` computes bearing/range from ownship to whichever
  candidate (or best-guess candidate) it resolved. A confident single match emits at
  `confidence≈0.6` (`method: "bearing_range_terrain"`); an ambiguous multi-candidate scene still
  emits, from the nearest tied candidate, at `confidence≈0.25`
  (`method: "bearing_range_terrain_ambiguous_association"`) rather than staying silent — the
  current `Observation` schema has no "detection happened, position unknown" representation, so
  this is the closest achievable approximation without a schema change (a possible fast-follow).

Realized observation shape (`source: "petrovich_detection_associated"`, not the originally-drafted
`petrovich_detection`):

```yaml
observation:
  timestamp: 1281.4
  source: petrovich_detection_associated
  classification: Ural truck
  bearing_deg: 32
  range_m: 3100
  provenance: petrovich_indication+world_objects
```

This is neither of this section's originally-anticipated designs — not a full real feed with real
bearing, and not a pure ground-truth proxy — it is a hybrid: real detection existence + gated
classification from Petrovich's own UI, synthetic geometry derived from world-object association.
See `plans/pb1-perception-logger/plan.md`'s Invariant Check for the full reasoning on why this
split still satisfies "Petrovich must not be omniscient."

## Contact identity

Repeated observations need persistent contact identities.

Example:

```yaml
contact:
  id: C17

  classification:
    value: BMP-2
    confidence: 0.8

  first_seen: ...
  last_seen: ...

  last_known_position:
    dcs: ...
    confidence: 0.7

  movement:
    direction: north
    confidence: 0.6

  visible: false
```

Determine whether a new observation belongs to an existing contact using deterministic heuristics first:

- spatial proximity;
- classification compatibility;
- elapsed time;
- motion estimate.

This is primarily a data-association problem, not an LLM problem.

## Observation versus current belief

Keep raw observations separate from the synthesized contact state.

```text
Contact C17

Observation 1:
12:41:10
BMP
east side village

Observation 2:
12:41:28
BMP
moving north
near road

Current belief:
likely same BMP
last known near road
moving north
position confidence medium
```

This improves uncertainty handling and debugging.

## Spatial memory

Store absolute world location when it can be inferred reliably.

Also preserve historical relative geometry at observation time.

```text
absolute:
DCS world position

historical relative:
bearing/range when observed
```

Do not preserve an old bearing as if it were current.

World coordinates allow current relative geometry to be recalculated as the helicopter moves.

## Semantic contact context

For important contacts, derive relationships such as:

```text
near ROAD_41
east side of VILLAGE_12
south of RIDGE_7
600 m west of Mi-8 route
2 km north of LZ
```

The World Model provides geographic semantics.

The runtime computes their current mission relevance.

## Uncertainty and memory decay

Different attributes should become stale at different rates.

Example:

```text
identity:
slow decay

exact position:
fast decay

general area:
medium/slow decay

last movement direction:
medium decay
```

Petrobrain should distinguish:

```text
I see him.
I lost him.
Last saw him...
I think he was...
```

Those differences should come from structured confidence, not improvised wording.

## Attention model

Petrovich should not treat all contacts equally.

Potential states:

```text
IGNORE
NORMAL
WATCH
TRACK
PRIORITY
```

Example:

> Keep an eye on that Shilka.

Language layer:

```text
resolve "that Shilka" → C18
```

Application layer:

```text
C18.attention = WATCH
```

Then deterministic event logic watches for:

- reacquisition;
- loss;
- movement;
- firing;
- increasing relevance;
- proximity to mission-critical friendly units.

## Area attention

Attention should eventually work for places as well as units.

Example:

> Watch the north side of the village.

Possible representation:

```yaml
attention_area:
  world_ref: VILLAGE_12
  sector: north
  priority: watch
```

Whether Petrobrain can physically influence Petrovich's scan behavior depends on DCS control interfaces and is a separate research question.

> Later, `threat-levels.md`'s `urgent` tier ("must receive automatic 'tracking' status until threat level decreases") and `ignore` tier ("friendly unit in deep friendly terrain... drop noise") map onto this attention-state machine directly. Deferred, but worth keeping `TRACK`/`IGNORE` semantics free to be driven by a threat-priority lookup later instead of only manual player commands.

## Event model

Prefer event-driven runtime behavior where possible.

Candidate events:

```text
CONTACT_DETECTED
CONTACT_LOST
CONTACT_REACQUIRED
CONTACT_MOVED
CONTACT_CLASSIFICATION_CHANGED
CONTACT_BECAME_HIGH_THREAT
PLAYER_MARKED_CONTACT
PLAYER_MARKED_AREA
MISSION_PHASE_CHANGED
FRIENDLY_ENTERED_THREAT_AREA
```

Events update memory.

Some events trigger speech.

Example:

```text
CONTACT_REACQUIRED
contact=C18
```

may become:

> I've got the Shilka again, north edge of the village.

The event contains the fact. The model supplies wording.

## Mission relevance

The same contact may matter very differently depending on the mission.

Example:

```text
Truck 8 km behind:
low relevance

ZSU beside Mi-8 approach:
high relevance
```

Runtime relevance may depend on:

- contact type;
- threat type;
- distance;
- relation to friendlies;
- relation to route/objective;
- current mission phase;
- player attention;
- recency.

Initially prefer deterministic relevance rules over LLM judgment.

> **Deferred, later goal**: `threat-levels.md` sketches a concrete priority table (urgent/high/medium/low/ignore) plus what makes a contact "dangerous to self/flight" (engagement envelope, tracking/LOS, intercept course). It is not scheduled work — no milestone depends on it yet — but relevance/attention rules built here should stay compatible with a later threat-priority pass rather than needing a rewrite: keep relevance scoring as data (contact type, threat capability, tracking state, relation to friendlies) that a priority table can consume, not baked into ad hoc thresholds.

## Runtime mission state

Do not repeatedly ask the LLM what phase the mission is in.

A separate state engine should track:

```text
STARTUP
DEPARTURE
RENDEZVOUS
INGRESS
INSERTION
EGRESS
RETURN
```

Possible transition signals:

- ownship position;
- waypoint progress;
- protected flight position;
- DCS events;
- mission triggers where appropriate;
- explicit player input.

Petrobrain receives a current phase, not the entire reasoning needed to infer it.

## Runtime LLM role

The runtime model should ideally be:

- local;
- fast;
- small enough for low latency;
- given compact structured state;
- prevented from inventing factual world state.

Its main jobs:

### Reference resolution

> that BMP

> the Shilka by the road

> the one we saw earlier

→ contact or place ID.

### Intent interpretation

> Keep watching him.

→ attention command.

### Language generation

Structured event:

```json
{
  "event": "CONTACT_REACQUIRED",
  "type": "ZSU-23-4",
  "semantic_location": "north edge of village",
  "range_m": 2400
}
```

→

> Got the Shilka again. North edge of the village, about two and a half kilometres.

The model does not decide whether the Shilka exists.

## Speech input/output — SRS intercom

The audio transport is **SRS (SimpleRadio Standalone)**, with Petrovich on the aircraft's **ICS
(intercom) channel**. The player talks to Petrovich by transmitting on ICS; Petrovich answers on
the same channel. There is no separate mechanism per direction.

Audio never enters the runtime. An **SRS adapter** owns the audio boundary and deals in text only
on its inward side — see `division-or-responsibility.md`'s "Speech / audio (SRS ICS)" section for
the layer placement argument (adapter as a sibling of the aircraft layer, not part of it).

Inbound:

```text
player PTT on ICS
    ↓
debounce  (drop transmissions shorter than a sanity interval — accidental key clicks)
    ↓
silence/noise gate  (drop transmissions that are not speech, rather than STT'ing garbage)
    ↓
STT
    ↓
transcript text
    ↓
deterministic intent parse
    ↓
either: direct action + templated readback
    or:   escalate to the model
```

Outbound:

```text
chosen text  (templated by application logic, or written by the model)
    ↓
TTS
    ↓
SRS ICS
```

### Inbound routing gate

Not every player utterance needs the model.

```text
"scan 2 o'clock"        → deterministic. Body acts, reads back "scanning 2 o'clock".
"watch that Shilka"     → deterministic action, model-assisted reference resolution.
"where was that BMP?"   → structured memory answer, templated.
"should we go north of the ridge?"  → model. Judgement, not a command.
unparsable / ambiguous  → model, which acts or asks the player to clarify.
```

The model is not started from raw transcript text. It receives the transcript **plus whatever
deterministic parsing already extracted from it** — candidate intent, resolved references,
recognized bearings/ranges/places — so it is disambiguating a partly-understood utterance rather
than parsing from scratch.

Readbacks are deliberately templated, not generated. A readback's job is confirmation, and it
should be fast and identical every time. Waiting on an LLM to say "scanning 2 o'clock" is the
wrong trade.

### Outbound: what Petrovich says

Two classes, split on whether wording requires judgement.

**Templated (application logic writes the text):**

- command readbacks — "scanning 2 o'clock";
- contact reports — "enemy, 2 o'clock, 3 km, group of three tanks, two IFVs and infantry,
  crossroad east of the village";
- urgent reactive calls — "missile launch, 9 o'clock, break right".

**Model-written (application logic supplies facts, model supplies wording):**

- advisory and judgement calls — "commander, SAM threat in the target area, suggest terrain
  cover east of target";
- answers to open questions the templates do not cover;
- anything conversational.

## Proactive speech

Petrovich should speak without being asked when useful, but not chatter constantly.

Possible triggers:

- important new threat;
- watched target reacquired;
- watched target lost;
- threat fires;
- threat becomes relevant to protected friendlies;
- major mission-state change.

Application logic decides whether an event merits reporting.

The model decides how to phrase it — except for the templated classes above.

Cooldown/relevance logic should prevent repetitive chatter.

### Reactive urgent calls bypass the gate

One explicit exception to the cooldown/relevance logic above.

Immediate-survival calls — missile launch, tracer, imminent terrain — are **not** subject to
cooldown, relevance scoring, or "has this already been mentioned" suppression. A late or
suppressed break call is worthless. These calls are templated, generated by application logic,
and pre-empt anything currently being said.

Everything else stays under the normal gate. The two mechanisms must not be conflated: ordinary
proactive speech is filtered *because* chatter is a real failure mode, and urgent calls are exempt
*because* silence is a worse one.

## Speech comes last, its logic does not

A text debug console still precedes speech integration, and PB-7/PB-8 remain late milestones.

But the routing gate, the deterministic intent parser, the readback and contact-report templates,
and the urgent-call path are all **text-in/text-out application logic**. None of it requires audio.
It should be designed and largely implemented against typed input and printed output well before
STT or TTS is wired up — at which point PB-7/PB-8 reduce to attaching the audio transport to a
pipeline that already works.

## Senior model escalation

Complex tactical questions may be escalated to the Mission Interpreter/senior reasoning service.

Example:

> Do you think we should still go north of the ridge?

Possible flow:

```text
complex planning question
    ↓
senior reasoning service
    ↓
answer returned through Petrobrain
```

Normal runtime interactions should remain fast and local.

## Future control of Petrovich

This draft focuses on awareness and memory.

Later, Petrobrain may translate high-level intent into validated Petrovich actions such as:

- target selection;
- scan direction;
- weapon selection;
- target prioritization;
- engagement commands.

Do not allow the LLM to issue arbitrary Lua or low-level control.

Conceptually:

```text
LLM intent
   ↓
validated action
   ↓
PETROVICH_SELECT_TARGET(C17)
```

## Debugging and inspectability

Build developer visibility early.

Expose:

```text
aircraft state
mission phase
known contacts
observation history
contact confidence
semantic locations
attention state
recent events
runtime model context
model output
```

A debug map showing **Petrovich belief** versus **DCS truth** would be especially useful.

Keep the two visually distinct.

## Suggested development milestones

These are provisional and should be revised once World Model and Mission Interpreter prototypes exist.

### PB-0 — Proven inputs

- confirm World Model API;
- confirm Mission Understanding format;
- investigate Petrovich perception export;
- identify ownship state source.

### PB-1 — Text-only perception logger

No LLM.

Capture:

```text
time
aircraft position
Petrovich detections
bearing/range
```

### PB-2 — Contact memory

Associate observations into persistent contacts.

Support:

```text
detected
lost
reacquired
```

### PB-3 — World enrichment

For each contact:

- estimate/store world position;
- query semantic location;
- recompute current relative geometry.

### PB-4 — Attention

Implement simple states such as:

```text
NORMAL
WATCH
PRIORITY
```

Use a debug text command first:

```text
watch C17
```

### PB-5 — Deterministic runtime queries

Examples:

```text
where is C17?
do we still see C17?
what contacts are near the LZ?
what is the highest-priority threat?
```

### PB-6 — Small LLM interface

Add natural-language reference resolution and response generation.

### PB-7 — TTS

Speak useful callouts over SRS ICS.

By this point the templated readbacks, contact reports and urgent calls should already exist and
be verifiable as printed text — PB-7 attaches TTS and the SRS transport to them, it does not
invent them.

### PB-8 — STT

Allow push-to-talk interaction on SRS ICS, including the transmit debounce and silence/noise gate.

Both are signal-level and belong to the SRS adapter — raw audio must not cross into the runtime.
Any context-dependent suppression (a tighter tolerance mid-engagement, say) is a later refinement
that operates on already-transcribed text and belongs to the runtime instead.

Likewise, the deterministic intent parser and the deterministic-vs-model routing gate should
already exist and be verifiable against typed input before PB-8 starts.

### PB-9 — Mission-aware proactive behavior

Use Mission Understanding and mission phase to prioritize speech.

Only after these work should autonomous gunner-control behavior be expanded.

## Research areas

Investigate current DCS behavior when this layer enters active development.

Priority topics:

1. Mi-24 `HelperAI` / Petrovich cockpit scripts.
2. `list_indication()` behavior for Petrovich UI.
3. Export.lua visibility into Petrovich state.
4. Cockpit arguments/device APIs.
5. DCS-BIOS/community export techniques.
6. Whether target IDs exist or only rendered descriptions.
7. DCS events.
8. Aircraft own-state export.
9. DCS-gRPC applicability.
10. Safe high-level control paths into Petrovich.
11. SRS/intercom integration.
12. Existing VAICOM / VoiceAttack / Petrovich experiments.

Likely sources:

- installed Mi-24 cockpit Lua scripts;
- Eagle Dynamics forums;
- Hoggit wiki;
- GitHub;
- DCS-gRPC;
- DCS-BIOS;
- SRS;
- VAICOM/VoiceAttack community work.

Verify against the current DCS version.

## First useful success criterion

The first meaningful Petrobrain does not need voice and does not need to fire a weapon.

It succeeds if this is possible in a debug console:

```text
Petrovich detects a vehicle.

System:
C17 BMP
last seen near road east of village

Player:
watch C17

Petrovich later loses it.

System:
C17 lost
last known east edge of village

Petrovich later detects it again.

System:
C17 reacquired
```

Then:

```text
Player:
Where was that BMP?

Petrobrain:
Last saw it on the east side of the village, near the road.
```

If that answer comes from structured memory rather than improvisation, the central architecture works.

## Key dependencies

Do not hard-code final assumptions about:

- geographic object IDs;
- spatial query formats;
- terrain semantics;
- Mission Understanding schema;
- DCS perception format;
- coordinate uncertainty;
- runtime model context;
- live probe-to-store data channel (see "World model acquisition: incremental, on-demand
  probing" above — currently unsolved);

until practical experiments establish what is really possible.

Treat this document as a target architecture, not a contract.
