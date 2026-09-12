### Goal

Hand-map MI-1.5's crew-available mission tree + MI-2's world-model enrichment directly into a new,
versioned `MissionUnderstanding` dataclass schema — populating only the fields that require no
judgment (theatre, ownship, route, a mechanical `mission_phases` skeleton, `important_locations`
from named entities that resolved against the World Model) — so BL-7 gets a real, schema-valid,
model-free Mission Understanding to integrate against, and the schema itself gets exercised before
MI-4's capable-model synthesis is built on top of it.

### Investigation before finalizing this plan

The plan's own MI-3 sketch calls `ownship` a "trivial passthrough," but nothing in
`mission-interpreter/src/miz/tree.py`'s `Unit` dataclass, `mission-interpreter/research/
2026-09-12-miz-validation-against-real-sample.md`, or `synthetic_mission.py` records how DCS marks
*which* unit is the player's own aircraft — a real gap, not a documented fact, so this was sent to
`investigator` before finalizing field mappings below (per this role's process step 2).

**Result** (`mission-interpreter/research/2026-09-12-player-slot-skill-field.md`, real bytes from
`Mission 02-Bagram.miz`): every `unit[]` entry carries a `skill` field; the one `skill = "Player"`
unit in the sample is exactly the player's Mi-24P. No other field (`callsign`, `onboard_num`,
`AddPropAircraft`, `uncontrolled`, or the unit's own `name` text) reliably signals a player slot —
all were checked and ruled out. `"Client"` (the MP-slot variant) does not appear in this
single-player sample; whether DCS guarantees exactly one `Player`/`Client` unit in general is
**not established** from one sample. `tree.py`'s `Unit` dataclass does not yet carry `skill` at
all — this plan adds it.

Design consequence: ownship selection must scan every unit for `skill in {"Player", "Client"}`
and handle 0 or ≥2 matches explicitly (`UNKNOWN`, not a guess) — see Ownship below.

### A second gap found while reading, before designing new behavior (process step 3a)

Reading `world_enrich/enrich.py` and `world_enrich/schema.py` (not just the plan's own framing of
"important_locations from named waypoints/objectives") surfaced two structural facts the plan text
didn't anticipate:

- `miz.tree.RoutePoint` has **no `name` field** — DCS route waypoints can carry an optional
  user-typed name, but MI-1's dataclass never parsed it, and `enrich.py`'s `_enrich_route_point`
  never calls `find_place_by_name` for a waypoint at all (only for named `Group`s and
  `TriggerZone`s — see `enrich.py` lines 105–112 vs. `_world_ref_for`). "Named waypoints" is
  therefore not a field this pipeline currently supports; treating it as in-scope for MI-3 would
  require reopening MI-1's frozen `RoutePoint` dataclass *and* MI-2's already-tested `enrich.py`,
  which is disproportionate to a "hand-map, no judgment" milestone.
- What the pipeline *does* already compute per-entity is `WorldRef.name_matches` — populated (via
  `find_place_by_name`) for every named `Group` and `TriggerZone`, empty when unnamed or no match
  found. That field is exactly "did this named thing resolve to a real place" — a mechanical,
  already-computed signal requiring no new enrichment work.

**Scope decision (local, reversible, not escalated):** `important_locations` for MI-3 = every
`EnrichedGroup`/`EnrichedTriggerZone` whose `world_ref.name_matches` is non-empty. "Named
waypoints" is deferred — flagged below as a real, out-of-scope gap for a future milestone, not
silently substituted without comment.

### Epistemic tag mechanism (new reusable pattern — MI-4/5/6 build on this)

Two established precedents exist in this codebase for carrying provenance/confidence alongside a
value:

1. `world-model/src/store/models.py`'s `StoredFeature` — a plain dataclass plus **parallel
   per-field-name dict maps** (`provenance: dict[str, str]`, `confidence: dict[str, str]`).
2. The concept doc's own example (`docs/concept/PETROBRAIN_SYSTEM.md` / `MISSION_INTERPRETER.md`)
   — each *statement* (e.g. one `known_threats` entry) carries `epistemic_status`/`confidence`/
   `basis` **inline as its own fields**, not in a separate top-level map.

These don't generalize the same way. `StoredFeature`'s per-field-name map works because each row is
independently fetched and flat. `MissionUnderstanding` is a nested tree where `mission_phases` and
`important_locations` are *lists whose individual items* may carry different epistemic status once
MI-4 adds true inference (one threat FACT-backed by the briefing, another INFERENCE) — a flat
`dict[str, str]` keyed by field name can't express "item 3 of this list is INFERENCE, item 4 is
FACT." Precedent 2 (per-statement inline tagging) is the one that actually matches this need.

**Decision:** a small generic wrapper, not a per-field-name map:

```python
EpistemicStatus = Literal["FACT", "OBSERVATION", "INFERENCE", "ASSUMPTION", "UNKNOWN"]

@dataclass(frozen=True, slots=True)
class Tagged(Generic[T]):
    value: T
    epistemic_status: EpistemicStatus
    basis: tuple[str, ...] = ()
```

Applied uniformly to every top-level `MissionUnderstanding` field and every `mission_phases`/
`important_locations` list item — one mechanism, not two conventions BL-7 has to remember. `basis`
is a short human-readable trail (e.g. `("miz:unit.skill",)`, `("world_model:find_place_by_name",)`)
— always non-empty for anything MI-3 populates, since "how do you know" should never be silently
blank even at the FACT tier. Generic-`Tagged`-in-`dataclasses.asdict()` round-trips through
`json.dumps` the same way `world-model/src/api/server.py`'s existing `asdict()`-only convention
does (confirmed: `asdict` recurses through nested dataclasses regardless of `Generic`, since the
wrapped `value` is still a concrete dataclass/primitive/tuple at runtime) — no custom `to_dict`
needed, consistent with that precedent.

**FACT vs. OBSERVATION, defined for this stage (a deliberate, stated broadening of the concept
doc's wording — flagged, not silently reinterpreted):** `PETROBRAIN_SYSTEM.md` defines
"observation" as "perceived during the mission" (a runtime concept). MI-3 runs entirely
pre-mission/offline, so nothing it produces is literally that. For this schema:

- **FACT** — read (or mechanically mapped, via a fixed documented table) directly from the parsed
  `.miz`/`CrewAvailableMission` tree, no external source consulted.
- **OBSERVATION** — resolved by consulting the World Model (an external, code-owned source of
  truth) rather than the mission file alone — still fully deterministic and reproducible, no model
  judgment, but distinguished from FACT because it required a second authority (`describe_position`/
  `find_place_by_name`) to produce.

This reuses the OBSERVATION label for "correlated against an external ground-truth source" rather
than "perceived live," which is a genuine interpretation call on an admittedly draft/provisional
concept doc. Flagging explicitly: if the user wants a stricter reading (e.g. a sixth tag for
pre-mission GIS correlation, leaving OBSERVATION reserved for true runtime perception), that's a
cheap rename before MI-4 starts consuming this vocabulary, but not something to guess silently now.

### Affected Modules / Files

- `mission-interpreter/src/miz/tree.py` — add `skill: str` to `Unit` (plain passthrough string,
  parsed from the real `["skill"]` key, real-bytes-confirmed present on every `unit[]` entry). This
  is an additive field on a frozen dataclass with no defaults — every existing positional
  construction site breaks until updated (see Risks).
- `mission-interpreter/src/miz/reader.py` — parse `skill` into the new `Unit.skill` field.
- `mission-interpreter/tests/fixtures/synthetic_mission.py` — extend with: a `skill="Player"` unit
  on the visible group (the "happy path" ownship case), and route waypoints with real-bytes-
  confirmed `type` values (`"TakeOffGround"`, `"Turning Point"`, `"Land"`) with distinct `x`/`y` so
  `mission_phases` mapping tests aren't coincidental. Existing `Unit`/`RoutePoint` construction call
  sites in this file need the new field added.
- `mission-interpreter/src/schema/` — new MI-3 package (was empty, per `CLAUDE.md`'s Structure
  section — "future stages (MI-3 onward), not built yet"):
  - `tags.py` — `EpistemicStatus`, `Tagged[T]` (above).
  - `understanding.py` — `SCHEMA_VERSION: int = 1`, `MissionUnderstanding`, `Ownship`,
    `MissionPhase`, `ImportantLocation` dataclasses. Every field MI-3 doesn't populate
    (`purpose`, `task`, `known_threats`, `player_intent`) is declared now with a default of `None`/
    `()` so BL-7 and any hand-written fixture can already target the full intended shape (per the
    parent plan's MI-0 "stable target" note) without this stage pretending to populate them.
  - `build.py` — `build_mission_understanding(enriched: EnrichedMission) -> MissionUnderstanding`,
    the actual MI-3 mapping logic (below).
  - `__init__.py`.
- `mission-interpreter/tests/test_schema_understanding.py` — mapping tests (below).
- `mission-interpreter/tests/test_schema_tags.py` — `Tagged`/JSON round-trip tests.
- `mission-interpreter/CLAUDE.md` — add a "Structure" line once `src/schema/` is real, and a note
  under a new "MI-3" bullet in "Tech stack" recording the `Tagged[T]` pattern and the FACT/
  OBSERVATION redefinition above, so a future reader doesn't have to reconstruct the reasoning from
  this plan file.
- `mission-interpreter/ROADMAP.md` — mark MI-3 done once merged (mirrors MI-1/MI-1.5/MI-2 entries).

### Field mappings MI-3 populates

- **`theatre`**: `Tagged(value=enriched.theatre, epistemic_status="FACT", basis=("miz:mission.theatre",))`.
  Trivial passthrough, exactly as the parent plan assumed.
- **`ownship`**: scan every `EnrichedGroup` (all coalitions/countries) for units with
  `unit.skill in ("Player", "Client")`, keeping track of which group each match belongs to.
  - Exactly one match → `Tagged(value=Ownship(aircraft=unit.type, flight=group.name, role=None),
    epistemic_status="FACT", basis=("miz:unit.skill",))`. `role` stays `None` — it requires
    understanding mission purpose (MI-4), not a mechanical field.
  - Zero or ≥2 matches → `Tagged(value=None, epistemic_status="UNKNOWN", basis=(f"found {n}
    Player/Client-skill units, expected exactly 1",))`. Never guess by taking the first match — the
    investigator's finding explicitly flagged this as a real, unresolved generalization risk, not a
    theoretical one.
- **`route`**: the `EnrichedGroup.route` belonging to the *same group* ownship resolved to (not a
  second independent scan). If ownship is `UNKNOWN`, route is also
  `Tagged(value=(), epistemic_status="UNKNOWN", basis=("no resolved ownship group",))` — there is no
  well-defined "the route" without a resolved ownship. If ownship resolved and
  `group.route is None`, `Tagged(value=(), epistemic_status="FACT", basis=("miz: group has no
  route",))` — a real fact (this group has no route), not a gap. Otherwise
  `Tagged(value=group.route, epistemic_status="FACT", basis=("miz:group.route",))`, reusing
  `world_enrich.schema.EnrichedRoutePoint` directly as the list item type — no third parallel
  waypoint dataclass; `route`/`world_ref` are already exactly what's needed.
- **`mission_phases`**: walk ownship's route (if resolved) and apply a **small, closed, explicitly
  extend-only-with-evidence mapping** from `RoutePoint.type` to a phase-boundary label, using only
  the real-bytes-confirmed values from `mission-interpreter/research/
  2026-09-12-miz-validation-against-real-sample.md`:
  - `type` starts with `"TakeOff"` (`"TakeOffGround"`, `"TakeOffParking"`) → `MissionPhase(name=
    "DEPARTURE", waypoint_index=i)`, `Tagged(..., "FACT", basis=("miz:route.points[i].type",))`.
  - `type == "Land"` → `MissionPhase(name="RETURN", waypoint_index=i)`, same tagging.
  - Any other `type` (including `"Turning Point"`, the only other confirmed value) → **not** a
    phase boundary, no entry emitted. This is a completeness gap, not a correctness one (see
    Risks) — intermediate phases (RENDEZVOUS/INGRESS/ESCORT/INSERTION/EGRESS) genuinely require
    task/purpose context this stage doesn't have, so they are correctly left out rather than
    guessed.
  - If ownship/route is `UNKNOWN`, `mission_phases` is `()`.
- **`important_locations`**: every `EnrichedGroup`/`EnrichedTriggerZone` (across the whole mission,
  not scoped to ownship's coalition — a threat/objective belonging to another group is still a
  location a crew could plausibly need to know about) whose `world_ref.name_matches` is non-empty →
  `ImportantLocation(id=<group.name or zone.name>, kind="unit_group"|"trigger_zone",
  world_ref=world_ref)`, `Tagged(..., "OBSERVATION", basis=("world_model:find_place_by_name",))`.
  `relevance` (the concept doc's `"objective"`/`"masking terrain"` field) is deliberately **not**
  populated — that's a tactical judgment, MI-4's job, not MI-3's. `ImportantLocation` therefore has
  no `relevance` field yet; MI-4 adds it when it exists to fill in, per "don't force a judgment call
  into a model-free stage."
- **Left `None`/`()`, deferred to MI-4/5/6 (not populated, not guessed):** `purpose`, `task`,
  `known_threats`, `player_intent`.

### Implementation Plan

1. **Add `Unit.skill`.** `tree.py` + `reader.py` change, `synthetic_mission.py` fixture update
   (skill on existing units, at least one `"Player"`-skill unit). Run `test_reader.py`/
   `test_filter.py`/`test_enrich.py` to confirm nothing else broke from the new required field —
   these are the "validate correctness" gate for this stage's only change to already-tested code.
2. **`src/schema/tags.py`** — `EpistemicStatus`, `Tagged[T]`. `test_schema_tags.py`: construct a
   `Tagged[int]`/`Tagged[str]`, round-trip through `dataclasses.asdict()` → `json.dumps` →
   `json.loads`, assert the reconstructed dict matches. This is the minimal working version — prove
   the mechanism before building the schema on top of it.
3. **`src/schema/understanding.py`** — `SCHEMA_VERSION`, `MissionUnderstanding`, `Ownship`,
   `MissionPhase`, `ImportantLocation`. No logic yet, just the shape — inspectable by hand (matches
   this project's "prefer inspectable intermediate representations" invariant) before `build.py`
   exists.
4. **`src/schema/build.py`** — `build_mission_understanding`, implementing the field mappings
   above. Extend `synthetic_mission.py` further as needed (route waypoints with `TakeOffGround`/
   `Turning Point`/`Land` types; a second synthetic mission variant, or a second `EnrichedMission`
   built directly in test code, for the zero-Player-unit and two-Player-unit ownship branches —
   building `EnrichedMission`/`EnrichedGroup` objects directly in test code, bypassing the zip/HTTP
   pipeline entirely, is the simpler path for these edge cases and mirrors `test_enrich.py`'s
   already-established `FakeWorldModelClient` precedent of not needing wire-format fidelity at this
   layer).
5. **`test_schema_understanding.py`** — validate correctness:
   - Happy path: synthetic fixture (one `Player`-skill unit, a route with `TakeOffGround`/
     `Turning Point`/`Land`, a named trigger zone whose fake `find_place_by_name` response is
     non-empty) → assert `theatre`/`ownship`/`route`/`mission_phases`/`important_locations` all
     populated as FACT/OBSERVATION with the expected values, `purpose`/`task`/`known_threats`/
     `player_intent` all `None`/`()`.
   - Zero-`Player`-unit case → `ownship`/`route` both `UNKNOWN`, `mission_phases` empty.
   - Two-`Player`-unit case → same `UNKNOWN` outcome, not a crash and not a silent first-match pick.
   - **The central invariant this stage exists to prove:** iterate every `Tagged` value reachable
     from a built `MissionUnderstanding` and assert `epistemic_status` is never `"INFERENCE"` or
     `"ASSUMPTION"` — mirrors `test_filter.py`'s role as "the one property that must be provable in
     every checkout" for MI-1.5's invariant, applied to MI-3's own.
   - Full-`MissionUnderstanding` JSON round-trip (`asdict` → `json.dumps` → `json.loads`), the
     shape BL-7 will actually consume as data, not just in-process objects.
6. **Docs**: `CLAUDE.md` Structure/Tech-stack update, `ROADMAP.md` MI-3 entry.

### Risks & Unknowns

- **Adding `Unit.skill` breaks every existing positional `Unit(...)` construction site** (parser,
  synthetic fixture, any test constructing `Unit` directly) — mechanical but real fan-out; the
  Implementer should grep for `Unit(` before assuming `reader.py`/`synthetic_mission.py` are the
  only two sites.
- **`Player`/`Client` cardinality is unverified beyond one sample** (investigator's own flagged
  gap). MI-3's 0-or-≥2 handling means this can't produce a wrong ownship, only an `UNKNOWN` one —
  bounded correctly, but real missions with a genuinely ambiguous or absent player slot will show up
  as `UNKNOWN` more often than ideal until a second sample (or a `Client`-slot multiplayer sample)
  is examined.
- **`mission_phases` is a real completeness gap, not just a stated limitation.** Only
  departure/return boundaries are derivable without judgment; a Mission Understanding with no
  intermediate phases at all is a thin skeleton. This is intentional per the parent plan's own
  framing ("skeleton"), but BL-7 should not be surprised that MI-3's output alone doesn't have
  RENDEZVOUS/INGRESS/EGRESS entries — that's explicitly MI-4 scope.
- **The FACT/OBSERVATION redefinition above is an interpretation call on a draft/provisional concept
  doc**, not a re-verified fact. If BL-7's own design leans on the concept doc's literal "perceived
  during the mission" meaning for OBSERVATION, this could need reconciling later — flagged, not
  silently resolved (see the epistemic tag section above).
- **`important_locations` excludes named waypoints entirely** (see the second gap found while
  reading, above) — a real scope narrowing from the parent plan's literal wording, driven by what
  `RoutePoint`/`enrich.py` actually support today, not a simplification for convenience alone.

### Second-order effect

`Tagged[T]` becomes the one epistemic-tagging mechanism every later stage (MI-4's threats/purpose/
task, MI-5's player_intent, MI-6's runtime compaction) is expected to reuse rather than reinvent —
correct now, but it also means an ill-fitting `Tagged[T]` design decided here (e.g. if MI-4 needs
per-field basis rather than per-statement, or richer confidence than a five-way enum) is a schema-
wide rename across three future milestones and BL-7's consumer code, not a local fix. The FACT/
OBSERVATION redefinition carries the same amplification risk in the other direction — MI-4 will be
the first stage to actually need the INFERENCE/ASSUMPTION tiers this stage never exercises, so
whether the five-way vocabulary as scoped here holds up won't be known until MI-4 is attempted.

### Note on planning depth

MI-3 itself (schema shape, mechanical field mapping) is not architecturally complex — this plan was
produced at this role's default (sonnet) depth, consistent with the parent plan's own note that
MI-0 through MI-3 don't need an opus-level pass (only MI-4's model-synthesis design was flagged for
that). The `Tagged[T]` pattern decision is the one piece of this plan with real downstream leverage
(three future milestones build on it) — if the user wants deeper scrutiny specifically on that
mechanism before implementation starts, re-invoking this role with an opus override for that one
question would be reasonable; nothing else here rises to that bar.
