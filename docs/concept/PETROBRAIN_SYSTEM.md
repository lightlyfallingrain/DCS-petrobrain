# Petrobrain System — Project Goal and Architecture

## Purpose

This project aims to make DCS World helicopter operations feel like operations conducted by a real crew rather than a player interacting with disconnected game systems.

The first target is the Mi-24P and its Petrovich AI crew member, especially Petrovich acting as the pilot-operator/gunner while the player flies from the rear cockpit.

The central problem is not merely speech generation. Petrovich needs usable **situational awareness and memory**:

- understand the geographic world in which the mission takes place;
- understand the mission, plan, objectives, capabilities, limitations, threats and relevant terrain;
- remember what he has actually observed;
- relate observed contacts to terrain, landmarks, the aircraft, friendlies, routes and objectives;
- distinguish current observation from remembered or inferred information;
- maintain attention on things the player asks him to watch;
- communicate naturally and usefully with the player.

The system must not turn Petrovich into an omniscient AI. DCS and deterministic software provide facts. AI models interpret bounded information, maintain useful abstractions, and communicate.

A guiding principle is:

> **Code owns truth. Models own interpretation and language.**

## High-Level Architecture

The project consists of three major layers that depend on one another.

```text
┌───────────────────────────────────────────────┐
│ 1. DCS WORLD MODEL                           │
│ Persistent knowledge of each DCS theatre     │
│ Syria, Caucasus, Kola, Afghanistan, etc.     │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│ 2. MISSION INTERPRETER                       │
│ Understand this mission in that world        │
│ briefing + .miz + route + world + player     │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│ 3. PETROBRAIN                                │
│ Runtime crew cognition                       │
│ perception + memory + attention + dialogue   │
└───────────────────────────────────────────────┘
```

These should be separate components/projects with explicit interfaces.

---

# 1. DCS World Model

The World Model is persistent geographic knowledge.

It is built independently of individual missions and stored on disk. A theatre such as Syria should be processed once and incrementally updated when DCS or the model-building software changes.

It should answer questions such as:

- What is at this DCS coordinate?
- What settlement is this?
- What road is this vehicle beside?
- What ridge lies west of this point?
- Is this position in a valley?
- What terrain lies between A and B?
- What named place is nearest?
- What are useful human-recognizable landmarks around this location?
- How does this DCS location correspond to real-world latitude/longitude?

The World Model should combine multiple sources.

### DCS-derived sources

DCS is authoritative about the simulated world.

Potential sources include:

- F10 / Mission Editor raster map assets;
- terrain elevation;
- DCS coordinate transforms;
- roads and surface information;
- scenery objects where accessible;
- airfields;
- terrain configuration/assets.

### Real-world augmentation

DCS theatres approximate real geography closely enough that external GIS sources may provide valuable semantics:

- OpenStreetMap;
- open elevation/DEM datasets;
- open satellite/land-cover datasets;
- other appropriately licensed geographic sources.

Real-world data must **augment rather than override DCS**.

For example, OpenStreetMap may provide the real name and topology of a road, while the DCS road may be displaced or simplified. The World Model should retain that distinction.

Every derived feature should ideally record provenance and confidence.

```yaml
feature:
  type: settlement
  geometry_dcs: ...
  geometry_wgs84: ...
  name: ...
  sources:
    dcs_raster: high
    osm: high
    derived: medium
  match_quality: 0.82
```

DCS geometry remains authoritative for gameplay.

The World Model is discussed in detail in `WORLD_MODEL_BUILDER.md`.

---

# 2. Mission Interpreter

The Mission Interpreter creates an understanding of one particular mission using the persistent World Model.

This is deliberately separated from the low-latency runtime AI.

Inputs may include:

- the `.miz` file;
- DCS mission Lua data;
- briefing text;
- briefing images;
- kneeboard material;
- routes and waypoints;
- coalition/unit information where appropriate;
- loadout;
- weather;
- mission triggers/goals where useful;
- the World Model;
- player answers and intentions.

A `.miz` is a ZIP archive whose `mission` file contains a large Lua table describing much of the mission. Useful fields can include coalition units, waypoints, weather, briefing/task text, drawings, trigger zones, triggers, goals, date/time, theatre and briefing image references.

The Mission Interpreter should use a more capable model because this is where complex reasoning is valuable.

It asks questions such as:

- What is our role?
- What is the actual purpose of the mission?
- What are the important phases?
- What friendly elements matter to us?
- What threats are known, suspected or merely possible?
- What terrain matters to the plan?
- What is the relationship between route, terrain, threats and objective?
- What are our capabilities and limitations?
- What assumptions is the briefing making?
- What is ambiguous?
- What should Petrovich particularly pay attention to?

The output should be a structured **Mission Understanding**, not merely prose.

Example:

```yaml
role:
  aircraft: Mi-24P
  task: escort
  purpose: protect Mi-8 flight during insertion

mission_phases:
  - startup
  - departure
  - rendezvous
  - escort
  - insertion
  - egress

priorities:
  - protect transports
  - detect and suppress air-defence threats
  - monitor threats around LZ

important_places:
  - id: LZ_FALCON
  - id: VILLAGE_NORTH
  - id: WESTERN_RIDGE

known_threats:
  - type: AAA
    area: VILLAGE_NORTH
    epistemic_status: briefing
    confidence: medium

player_intent:
  approach: south_of_western_ridge
```

The system should distinguish:

- **fact** — directly supplied by DCS/briefing/player;
- **observation** — perceived during the mission;
- **inference** — reasoned conclusion;
- **assumption** — plausible but unverified;
- **unknown**.

The interpreter may ask the player questions before or during startup when important information is ambiguous.

Example:

> The briefing specifies escorting the Mi-8 flight but does not make the engagement priority clear. Should I prioritize air-defence threats and threats to the transports over other ground contacts?

The Mission Understanding should be inspectable and editable during development.

The expensive model can also remain available as an optional **senior reasoning service** during gameplay for genuinely difficult planning questions. Normal runtime interactions should not depend on it.

---

# 3. Petrobrain Runtime

Petrobrain is the active low-latency crew cognition system.

Initially it models Petrovich acting as gunner/pilot-operator while the human flies the Mi-24.

It consumes:

- persistent World Model queries;
- prepared Mission Understanding;
- current aircraft state;
- Petrovich's actual detections/perception where extractable;
- player commands/questions, spoken over the SRS intercom (ICS) channel and transcribed, or typed
  into the debug console;
- its own episodic and working memory.

It replies on the same ICS channel. Many interactions — command readbacks, contact reports,
urgent break calls — are templated by deterministic code and never reach the model at all; see
`PETROBRAIN_RUNTIME.md`'s "Speech input/output — SRS intercom".

It should use a small, fast local model where practical.

## Memory model

Petrobrain should not rely on an LLM conversation history as its memory.

Memory is explicit application state.

### Geographic memory

Provided by the World Model.

### Mission memory

Provided by the Mission Interpreter and updated as mission phases change.

### Episodic/contact memory

What Petrovich has actually observed.

Example:

```yaml
contact:
  id: C17
  classification: BMP-2
  first_seen: 1242.1
  last_seen: 1267.4
  last_known_position_dcs: ...
  visible: false
  confidence_identity: 0.9
  confidence_position: 0.6
  motion_when_seen: north
  attention: watch
```

Observations should preserve both:

- absolute location in the world;
- relative geometry at observation time.

Absolute position lets Petrobrain recompute the contact's relationship to the aircraft after the aircraft moves.

### Working memory / attention

Petrovich needs an explicit concept of relevance.

Possible attention states:

```text
IGNORE
NORMAL
WATCH
TRACK
PRIORITY
```

If the player says:

> Keep an eye on that Shilka.

the language model resolves the reference to a contact and application state records that contact as `WATCH`.

Deterministic code can then detect events such as:

- target lost;
- target reacquired;
- target moving;
- target approaching a mission-critical area;
- new higher-priority threat.

The model turns those events into appropriate crew communication.

## Subjective knowledge versus world truth

This distinction is fundamental.

The system may internally know:

```text
DCS unit #4957 is at exact coordinate X/Y.
```

Petrovich may only know:

```text
BMP last seen near the eastern edge of the village,
approximately 40 seconds ago.
```

Petrobrain must not receive information merely because DCS internally knows it.

Detection/perception should come from Petrovich's actual DCS information if possible. If this cannot be exported, a perception approximation may eventually be required, but that is a fallback.

Uncertainty should evolve over time.

Identity may remain reliable while exact position becomes stale quickly.

Petrovich should therefore distinguish:

> I have him.

from:

> Last saw him near the road.

---

# Spatial Cognition

Coordinates alone are not useful crew awareness.

Petrobrain should reason through several simultaneous spatial representations.

### Absolute

```text
DCS x/z
lat/lon
altitude MSL
```

### Egocentric

```text
bearing
range
clock direction
relative elevation
```

### Semantic

```text
east side of the village
beside the road
behind the ridge
north of the LZ
between us and the transports
```

The World Model provides geographic semantics. Petrobrain relates contacts dynamically to them.

A contact should therefore be describable as:

```text
BMP-2
last seen 35 seconds ago
east side of village
near north-south road
currently approximately 2.7 km behind-right
600 m from Mi-8 planned route
```

This is substantially closer to human crew situational awareness than a list of coordinates.

---

# Model Architecture

Avoid solving every problem with one large LLM.

The intended division is:

```text
GIS / deterministic processing
    ↓
World Model

large/capable reasoning model
    ↓
Mission Understanding

deterministic runtime state + memory
    ↓
small/fast local model
    ↓
Petrovich dialogue and intent interpretation
```

The expensive model performs slow synthesis.

The runtime model operates on a compact, already-understood representation.

This should reduce latency, context size, computational cost and hallucination.

---

# Future Extension

Petrobrain is the first consumer of the architecture, not necessarily the last.

The same foundations could later support:

- AI Mi-24 wingmen;
- Mi-8 crews;
- ground commanders;
- FAC/JTAC-like roles;
- GCI;
- ATC;
- mission directors.

Each agent can share the same objective World Model while maintaining separate subjective observations and memories.

For example:

```text
WORLD MODEL
     │
 ┌───┴───────────┐
 │               │
Lead Petrovich   Wingman
 │               │
own observations own observations
 │               │
own beliefs      own beliefs
```

They can therefore disagree naturally without either being wrong:

> Lead: “I saw AAA west of the village.”

> Wingman: “I haven't seen it.”

---

# Engineering Principles

1. **DCS is authoritative about the simulated world.**
2. **Real-world GIS augments DCS; it does not overwrite it.**
3. **Code owns factual state.**
4. **Models interpret facts rather than invent them.**
5. **Agent knowledge must remain bounded by what that agent could know.**
6. **Memory is explicit structured state, not model chat history.**
7. **Preserve provenance, uncertainty and timestamps.**
8. **Separate expensive offline/pre-mission reasoning from low-latency runtime cognition.**
9. **Prefer inspectable intermediate representations.**
10. **Build the World Model first.**

# Current Development Priority

The immediate project is the **DCS World Model Builder**.

Do not begin by implementing conversational Petrovich behavior.

First establish whether a useful persistent semantic geographic representation of a DCS theatre can actually be constructed, queried and aligned with DCS coordinates.

See `WORLD_MODEL_BUILDER.md`.

See also `division-or-responsibility.md` (draft) for compute-topology constraints (local LAN split between Mac/Ollama and Windows/DCS) and a brain/body/aircraft/memory microservice decomposition of layer 3.
