# Mission Interpreter — Draft Design

> **Status: Draft / provisional**
>
> This document describes the intended Mission Interpreter layer in the Petrobrain system.
> It is not a fixed implementation specification. Its design depends heavily on what the DCS World Model Builder proves possible, what data it can expose reliably, and what interfaces it ultimately provides.
>
> The World Model Builder is foundational. Revise this document as that project matures.

## Purpose

The Mission Interpreter is the middle layer between persistent world knowledge and low-latency runtime cognition.

Its task is:

> **Understand this mission, in this world, well enough to produce a compact and explicit Mission Understanding for Petrobrain.**

The intended flow is:

```text
DCS World Model
      +
DCS mission data
      +
briefing / kneeboard / images
      +
player intent
      ↓
Mission Interpreter
      ↓
Mission Understanding
      ↓
Petrobrain Runtime
```

The Mission Interpreter should perform the slow, complex reasoning that is inappropriate for a small runtime model.

## Core responsibilities

It should eventually be able to:

- identify the player's aircraft, flight and role;
- understand the stated task and larger operational purpose;
- understand route, waypoints and mission phases;
- identify relevant friendly forces;
- identify known, expected and suspected threats;
- understand capabilities and limitations;
- place routes, threats, objectives and friendlies into the World Model;
- identify important terrain and geographic relationships;
- derive tactical implications without turning inference into fact;
- identify ambiguities and missing information;
- ask the player useful clarifying questions;
- record player intent explicitly;
- create a compact structured representation for runtime use.

It should not control the aircraft or act as Petrovich itself.

## Inputs

### DCS `.miz`

Potentially useful information includes:

- theatre;
- player aircraft and flight;
- coalition/group structure;
- routes and waypoints;
- tasks;
- loadout;
- date/time;
- weather;
- briefing/task text;
- briefing images;
- mission drawings;
- kneeboard assets;
- callsigns/frequencies;
- zones and triggers where useful.

A major design problem is that the mission file may contain hidden information the crew should not know. Raw mission-author knowledge must therefore be filtered before becoming crew knowledge.

### Persistent World Model

The Mission Interpreter should query the World Model through a stable API.

Potentially useful outputs:

- place names;
- roads;
- settlements;
- airfields;
- rivers;
- terrain elevation;
- ridges and valleys;
- landmarks;
- route context;
- spatial relations;
- reconciled real-world GIS semantics.

The Mission Interpreter should not read World Model storage directly.

### Briefing material

Potentially:

- briefing text;
- maps;
- diagrams;
- briefing images;
- kneeboard pages;
- custom documentation.

Visual material may require a vision-capable model.

### Player input

The player may need to clarify intent that the mission file cannot know.

Example:

> The planned route passes west of the village. Do you intend to follow it closely, or use the southern ridge for masking?

Player answers should become explicit structured mission knowledge.

## Mission Understanding

The main output should be a structured, inspectable artifact.

Example:

```yaml
mission:
  theatre: Syria
  title: ...

ownship:
  aircraft: Mi-24P
  flight: Colt 1
  role: armed escort

purpose:
  primary: protect transport helicopters during insertion

task:
  type: escort
  protected_element: Sokol

mission_phases:
  - startup
  - departure
  - rendezvous
  - ingress
  - insertion
  - egress

important_locations:
  - id: LZ_FALCON
    world_ref: ...
    relevance: objective

  - id: WESTERN_RIDGE
    world_ref: ...
    relevance: masking terrain

known_threats:
  - type: AAA
    area_ref: VILLAGE_NORTH
    epistemic_status: briefing
    confidence: medium

player_intent:
  approach: south_of_western_ridge
  reporting_priority:
    - air_defence
    - armour
```

The schema is expected to evolve.

## Epistemic model

Preserve the difference between:

```text
FACT
OBSERVATION
INFERENCE
ASSUMPTION
UNKNOWN
```

Example:

```yaml
statement:
  text: "AAA near the northern village may threaten the Mi-8 final approach."
  epistemic_status: inference
  basis:
    - "briefing mentions AAA in village area"
    - "Mi-8 route passes close to village"
  confidence: medium
```

Do not silently convert inferred conclusions into facts.

## Hidden mission truth

The interpreter must not expose mission-author knowledge that the player should not have.

Examples:

- exact hidden enemy locations;
- future ambushes;
- reinforcement timing;
- trigger-only information;
- mission success scripts;
- invisible enemy routes.

Conceptually:

```text
raw mission data
      ↓
mission-author knowledge
      ↓
crew-available knowledge filter
      ↓
Mission Understanding
```

This boundary is essential to prevent omniscience.

## Geographic interpretation

The World Model owns geography.

The Mission Interpreter owns **what the geography means for this mission**.

Example:

```text
Waypoint 4
→ in a north-south valley
→ west ridge may mask line of sight
→ near the protected flight's final approach
```

Likewise:

```text
AAA expected near Village X
```

may become:

```text
Threat area lies close to the Mi-8 approach and may dominate the final insertion corridor.
```

The inference should retain its evidence and confidence.

## Mission phases

Many runtime priorities depend on phase.

Possible phases:

```text
STARTUP
DEPARTURE
RENDEZVOUS
INGRESS
ESCORT / ATTACK
INSERTION
EGRESS
RETURN
```

The interpreter should define likely phases and their relevance.

A separate runtime state engine can later determine which phase is currently active using aircraft position, waypoint progress, friendly positions, events, or explicit player input.

Do not rely on an LLM continuously re-inferring phase.

## Player questions

Ask only questions whose answers materially improve mission understanding or runtime behavior.

Useful examples:

> Is the briefed route mandatory, or may we deviate for terrain masking?

> Should Petrovich prioritize air-defence and armour, or report all detected vehicles?

> Is protection of the Mi-8 flight more important than completing attacks?

Persist the answers outside conversation history.

## Model role

This layer is where a more capable model is useful.

Suitable tasks:

- briefing comprehension;
- multi-source synthesis;
- visual briefing interpretation;
- identifying ambiguity;
- tactical relationship analysis;
- producing a compact mission representation;
- formulating useful player questions.

Use deterministic parsers for structured data and the capable model for meaning.

Guiding rule:

> **Code owns truth. Models own interpretation.**

## Output for Petrobrain

Petrobrain should receive a compact runtime representation, not the full mission.

Example:

```yaml
current_mission:
  purpose: protect Sokol during insertion

  priorities:
    - air-defence threats
    - threats to transports
    - threats near LZ

  key_locations:
    lz: LZ_FALCON
    threat_area: VILLAGE_NORTH
    masking_terrain: WESTERN_RIDGE

  intended_plan:
    ingress: south_of_western_ridge

  expected_threats:
    - AAA near VILLAGE_NORTH

  current_phase: ingress
```

## Optional senior reasoning during gameplay

The capable model may remain available for complex questions, but should not be part of the normal runtime loop.

Example:

> Given the AAA we found and the transports' current position, is the original approach still sensible?

That query may be escalated with:

- Mission Understanding;
- current mission state;
- relevant contact memory;
- player question.

This is optional and should be added only after the basic architecture works.

## Suggested development milestones

These are provisional and should be revised after World Model v0.1 exists.

### MI-0 — Define actual inputs

- inspect World Model API;
- inspect representative `.miz` files;
- identify safe knowledge boundaries;
- define provisional Mission Understanding schema.

### MI-1 — Structured `.miz` parser

Parse only clearly useful fields:

- theatre;
- ownship;
- route;
- loadout;
- weather;
- briefing text;
- briefing image references.

Produce inspectable JSON/YAML.

### MI-2 — World enrichment

Resolve route/objective coordinates against the World Model.

### MI-3 — Capable-model synthesis

Produce a first Mission Understanding from structured mission data + world context + briefing.

### MI-4 — Provenance and uncertainty

Track basis and confidence for important conclusions.

### MI-5 — Player questions

Identify only high-value ambiguities and persist answers.

### MI-6 — Runtime compilation

Compile the full Mission Understanding into a compact Petrobrain runtime context.

## Research areas

Investigate current sources rather than assuming this draft is correct.

Likely sources:

- DCS installation and `.miz` files;
- Eagle Dynamics forums;
- Hoggit DCS World Wiki;
- DCS mission scripting documentation;
- GitHub `.miz` parsers;
- Liberation / Retribution;
- mission planning tools;
- DCS-gRPC;
- Olympus;
- campaign tooling.

Useful searches:

```text
DCS miz mission parser
DCS mission Lua structure
DCS briefing image miz
DCS mission drawings Lua
DCS waypoint task structure
DCS hidden units mission file
DCS trigger structure miz
```

Verify against actual mission files.

## Definition of success for first useful version

Given a test mission, produce a structured document that a human familiar with the briefing can inspect and reasonably say:

> Yes, this correctly understands what we are doing, where we are doing it, what matters, and what remains uncertain.

It does not yet need live DCS integration.

## Key dependency

Do not lock in:

- place reference format;
- coordinate schema;
- world-query API;
- terrain feature model;
- confidence/provenance format;

until the World Model project shows what is practical.

Treat this document as an architectural hypothesis.
