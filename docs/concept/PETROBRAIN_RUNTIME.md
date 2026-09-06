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

The first major technical unknown is:

> What Petrovich detection/target state can actually be extracted from DCS?

Investigate:

- Petrovich target list / HelperAI indication;
- `list_indication()`;
- cockpit export;
- Export.lua;
- cockpit arguments;
- Mi-24 Lua cockpit scripts;
- DCS-BIOS-style approaches;
- community Petrovich export experiments.

Ideal normalized observation:

```yaml
observation:
  timestamp: 1281.4
  source: petrovich_detection
  classification: BMP
  bearing_deg: 32
  range_m: 3100
```

Using aircraft position and heading, deterministic code may then infer a world position if accuracy is sufficient.

If actual Petrovich perception cannot be exported, document that limitation before building an approximation.

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

## Speech input/output

Voice is important, but not the first milestone.

Eventually:

```text
player microphone
    ↓
push-to-talk
    ↓
STT
    ↓
intent/reference resolution
```

and:

```text
Petrobrain response
    ↓
TTS
    ↓
intercom audio
```

A text debug console should precede speech integration.

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

The model decides how to phrase it.

Cooldown/relevance logic should prevent repetitive chatter.

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

Speak useful callouts.

### PB-8 — STT

Allow push-to-talk interaction.

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
