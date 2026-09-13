### Goal
Give body-layer a live, deterministic notion of "which mission phase are we in right now" (walking
MI-6's `RuntimeMissionUnderstanding` phase boundaries against ownship telemetry) and use it as a
second, phase-aware signal in the existing deterministic relevance stand-in (`tools.
_highest_attention_contact`), without adding a new tool to the now-frozen `TOOL_SET`.

### Stale-flag resolution (required reading before the rest of this plan)
`body-layer/ROADMAP.md`'s BL-7 entry still says this milestone "adds `get_mission_phase` to the
tool API." That is stale. `tool_api.py`'s own docstring is unambiguous: the tool-set freeze point
moved to BL-6 ("With BL-6 landed, `TOOL_SET` is now the frozen surface `plans/body-layer/plan.md`
§3.3 names in full"). §3.3's list has no `get_mission_phase` entry and BL-6's own ROADMAP entry
confirms the freeze already happened without it.

**Decision: no new tool.** Mission phase is folded into `get_situation`'s existing facts payload
instead of a new `TOOL_SET` entry. Reasoning, not just least-resistance:
- `get_situation` is explicitly the "aggregate sitrep" tool (`tool_api.py`: "contact counts,
  highest-attention contact, unacknowledged event count, one-line summary of our own position").
  Current mission phase is exactly one more aggregate sitrep fact, not a targeted per-entity query.
- Contrast with `get_task_status`, which *does* need to be its own tool because it takes an `id` —
  there can be several pending tasks. Mission phase is a single global value; a dedicated
  `get_mission_phase` tool would be a strict, id-less subset of what `get_situation` already
  returns, with no query shape `get_situation` can't already express.
- The freeze (per `tool_api.py`'s docstring and BL-6's ROADMAP entry) is about the *tool
  inventory* not growing incidentally — it says nothing about a tool's own facts payload staying
  frozen. `get_situation`'s facts already evolved release over release (BL-2 through BL-6) without
  reopening the freeze question; this is the same kind of change.

This is the plan's answer to the "amendment vs. some other way" question the roadmap entry left
open. `TOOL_SET` itself is unchanged by this plan. `tool_api.py`'s module docstring gets one
sentence recording that this question was raised and resolved this way (so a future reader doesn't
re-litigate it), and the ROADMAP.md BL-7 line gets corrected at milestone completion (per root
CLAUDE.md's Milestone Completion note), not mid-plan.

### What "mission phase" and "relevance" mean here (grounded in the concept docs)
- `docs/concept/PETROBRAIN_RUNTIME.md` PB-9: "Use Mission Understanding and mission phase to
  prioritize speech." PB-9 itself (proactive speech selection) is Petrobrain Runtime work, which
  does not exist yet (root CLAUDE.md: "Mission Interpreter and Petrobrain Runtime modules do not
  exist yet"). BL-7 is PB-9's *deterministic half* per the roadmap's own framing: it computes the
  phase and a relevance signal a future runtime can consume — it does not build proactive speech
  triggers itself. That stays out of scope here.
- `docs/concept/PETROBRAIN_SYSTEM.md` "Working memory / attention" section is a different,
  already-built mechanism (BL-4's `Attention`/`AttentionArea`, direct player-set watch/priority
  marks) — not what BL-7 adds. The same section does name the concrete phenomenon BL-7's relevance
  signal targets: deterministic code detecting "target approaching a mission-critical area." BL-7
  operationalizes exactly this, using MI-6's route/phase data as the source of "which area is
  mission-critical right now" instead of a player-declared `AttentionArea`.
- Confirmed via `mission-interpreter/src/runtime/compact.py`'s module docstring: MI-6 deliberately
  emits no `current_phase` — "that engine doesn't exist yet... `phases` carries the ordered phase
  boundaries... for that future engine to walk instead of a single 'current' value." BL-7 is that
  live state engine, confirmed also by `plans/mi6-runtime-compilation/plan.md` line ~90: wiring
  `RuntimeMissionUnderstanding` into a live consumer "is explicitly BL-7's own design decision."

### The artifact BL-7 consumes
`mission-interpreter/src/runtime/compact.py`'s `RuntimeMissionUnderstanding`, written to disk as
JSON by `player_intent/main.py --emit-compact PATH` (`dataclasses.asdict` of the dataclass, so
every field arrives wrapped as `Tagged`'s `{value, epistemic_status, basis, confidence}` shape).
Fields BL-7 actually needs:
- `phases: tuple[Tagged[MissionPhase], ...]` — `MissionPhase = {name: str, waypoint_index: int}`,
  one entry per phase boundary, ordered by `waypoint_index` (MI-3's guarantee, unchanged by MI-6).
- `route: tuple[Tagged[CompactRoutePoint], ...]` — `CompactRoutePoint = {index, x, y, place_name}`.
  `x`/`y` are DCS-native planar coordinates (`miz/tree.py RoutePoint`'s own docstring: "`x`/`y` are
  DCS's native planar coordinates, not lat/lon"), and per `world-model/research/
  2026-09-02-m1-coordinate-transform.md` (ED-documented, already verified): DCS-native
  `x` = northing, `z` = easting. `body-layer/src/perception/geometry.py`'s `GeoPosition` already
  uses that same `(x, z)` convention (`tools.describe_our_position`: `GeoPosition(x=ownship.x,
  z=ownship.z, ...)`). So a route point's `(x, y)` maps directly onto `GeoPosition(x=x, z=y)` — no
  new coordinate transform needed, no fresh unverified-DCS-internals claim, just reusing an
  already-verified convention. (Investigator not invoked for this reason — nothing here is an
  open DCS-internals question; it's application logic over an artifact whose own producer already
  cites verified research.)
- `key_locations: tuple[Tagged[CompactLocation], ...]` — `CompactLocation = {id, kind,
  place_name}`. **No position field.** This means BL-7 cannot score relevance by proximity to a
  named key location without a further `find_place`-style lookup (substring match, not guaranteed
  to resolve) — out of scope for this plan; relevance is scored against *route waypoints* only
  (see below), not `key_locations`. Flagged under Risks, not solved here.

`schema_version`/`theatre`/`ownship`/`purpose`/`task`/`expected_threats` are not needed by BL-7's
phase/relevance logic and are not parsed.

### Affected Modules / Files
- `body-layer/src/belief/mission_phase.py` (**new**) — the whole feature:
  - `CompactRoutePoint`/`MissionPhaseInfo` — small local frozen dataclasses mirroring the two MI-6
    compact fields BL-7 needs (`index/x/y/place_name`, `name/waypoint_index`), each carrying
    `epistemic_status`/`basis` alongside the value (not discarded — root CLAUDE.md: "preserve
    provenance... on every feature derived from mixing DCS + external sources"). This is a
    hand-parsed local mirror, not an import of mission-interpreter's own `Tagged`/`MissionPhase`
    classes — mission-interpreter is not the world-model exception root CLAUDE.md's "Module
    independence" section carves out, so the boundary is a file read + JSON parse, never a Python
    import across the subprojects.
  - `MissionUnderstandingData` — immutable, loaded once: `phases: tuple[MissionPhaseInfo, ...]`
    (sorted ascending by `waypoint_index`, defensively re-sorted even though MI-3/MI-6 already
    guarantee order — cheap, and this is the one place a violated upstream guarantee would
    silently break phase sequencing), `route: tuple[CompactRoutePoint, ...]`.
  - `load_mission_understanding(path: Path) -> MissionUnderstandingData` — reads the
    `--emit-compact` JSON, unwraps each `Tagged` envelope, builds the dataclasses above. Raises a
    plain `ValueError` with a clear message on any missing/malformed field — this file is a
    one-time startup load, not a per-poll hot path, so failing loudly at startup (rather than
    degrading silently) is the right posture, mirroring `aircraft_client`'s raise-on-write-failure
    precedent for "this is meaningful information for the caller."
  - `MissionPhaseTracker` — the live state engine. Mutable, one instance per session:
    `last_reached_waypoint_index: int = -1` (starts "before" the route). `update(position:
    GeoPosition) -> None`: for the next un-reached route point (`index == last_reached_waypoint_index
    + 1`), if `range_m(position, that_point) <= WAYPOINT_CAPTURE_RADIUS_M`, advance
    `last_reached_waypoint_index` to that index (and keep checking subsequent points in case a poll
    gap skipped one). **Monotonic — never decrements.** `current_phase() -> MissionPhaseInfo | None`
    returns the last phase (by `waypoint_index`) whose `waypoint_index <=
    last_reached_waypoint_index`, or `None` if the route hasn't reached the first phase's waypoint
    yet (or no mission data was loaded).
  - `WAYPOINT_CAPTURE_RADIUS_M: Final[float]` — a guessed constant (placeholder value, e.g.
    `3000.0`), flagged explicitly under Risks as needing live-flight calibration, same debt class
    as `visibility.py`'s already-flagged tier constants (ROADMAP backlog: "Calibration needs live
    sorties, so it's meant to ride along with a milestone that's flying anyway").
  - `mission_phase_relevance(position: GeoPosition, phase: MissionPhaseInfo | None, route:
    tuple[CompactRoutePoint, ...]) -> float | None` — pure function: distance in meters from
    `position` to the active phase's waypoint (the route point at `phase.waypoint_index`), or
    `None` if there is no active phase or that index isn't in `route`. Smaller = more relevant.
    Deliberately a plain distance, not a 0..1 normalized score — nothing downstream needs
    normalization yet, and inventing a scale before there's a second relevance dimension to combine
    it with would be a speculative abstraction.

- `body-layer/src/belief/tools.py` — `_highest_attention_contact` gains mission-phase as a
  **tie-breaker only**, not a replacement for attention rank. Docstring today: "priority > watch >
  most-recently-observed visible... ties within a tier break on `last_seen_sim`, most recent
  first." New tie-break order within a tier: `mission_phase_relevance` ascending (closer to the
  active phase's waypoint wins) *before* `last_seen_sim`, when phase data is loaded and the
  relevance value is available for both candidates; falls back to the existing `last_seen_sim` rule
  otherwise (no mission data loaded, or a contact's `last_position` is `None`). Attention rank stays
  the dominant signal deliberately — it's the one relevance dimension the player directly controls
  (`set_attention`/`watch_area`), and CLAUDE.md's decision heuristics favor stable, predictable
  behavior over a cleverer combined score.
  `get_situation` gains one new fact: `facts["mission_phase"]` = the active phase's `name`, or
  `None` with a distinguishable reason ("no mission data loaded" vs. "before first phase") folded
  into the summary line only when present (mirrors `unacknowledged_events`'s "only mention it if
  nonzero" pattern) — e.g. `"Phase: ingress."` appended to the summary when a phase is active,
  nothing appended when it isn't.
  `describe_contact`/other per-contact tools are **not** touched this milestone — extending
  relevance display to individual contact facts is a reasonable follow-on, deliberately deferred to
  avoid scope creep beyond "get_situation's stand-in gets a real second dimension."

- `body-layer/src/logger.py` — new optional `--mission-understanding PATH` CLI flag. When given,
  `main()` calls `load_mission_understanding(path)` once at startup and constructs one
  `MissionPhaseTracker`, held alongside `EnrichmentContext` (not added as a new `EnrichmentContext`
  field — it isn't world-model/ownship-shaped state, it's its own lifecycle) and threaded through to
  wherever `EnrichmentContext` is already threaded (the `--console` poll loop and the REPL).
  `ConsolePerceptionRunner`'s poll loop calls `mission_phase_tracker.update(ownship_position)` once
  per poll, on the same thread that owns `EnrichmentContext.ownship`'s mutation — **not** on the
  REPL thread, mirroring the fix `body-layer/ROADMAP.md`'s BL-6 entry just re-confirmed
  ("`ConsolePerceptionRunner.enrichment`... sqlite thread-affinity is a recurring defect class in
  this codebase's polling/REPL architecture"). The REPL thread only *reads*
  `mission_phase_tracker.current_phase()`, never mutates it — same read/write split
  `EnrichmentContext.ownship` already uses. When the flag is omitted, behavior is unchanged
  (`mission_phase_tracker` is `None`, `get_situation` reports no phase data, exactly like optional
  `enrichment` degrading today for contact-facing tools).
- `body-layer/src/belief/tool_api.py` — one added sentence in the module docstring recording the
  "no new tool, folded into `get_situation`" decision (see Stale-flag resolution above), so a future
  reader doesn't re-litigate an already-closed question. `TOOL_SET` itself unchanged.
- `body-layer/ROADMAP.md` — **not edited by this plan** (Architect doesn't own roadmap-narrative
  edits mid-plan); flagged here so the eventual DoD/milestone-completion pass corrects the stale
  "adds `get_mission_phase` to the tool API" line to reflect the decision above, per root
  CLAUDE.md's Milestone Completion note.
- `body-layer/tests/test_mission_phase.py` (**new**) — loader parsing, tracker sequencing, and the
  pure `mission_phase_relevance` function, all fixture-based, no live dependency.
- `body-layer/tests/fixtures/mission_understanding_sample.json` (**new**, committed — matches
  `tests/fixtures/` convention of small synthetic fixtures, not gitignored) — a hand-written
  compact-artifact-shaped JSON with 2-3 phases and a handful of route points, small enough to reason
  about by eye.
- `body-layer/tests/test_tools.py` — extended: `get_situation`'s new `mission_phase` fact, and
  `_highest_attention_contact`'s new tie-break rule (two same-tier contacts, one closer to the
  active phase's waypoint).

### Implementation Plan
1. **Minimal working version.** `mission_phase.py` (dataclasses, loader, `MissionPhaseTracker`,
   `mission_phase_relevance`), the fixture JSON, and `test_mission_phase.py` covering: loading a
   valid fixture; loading a fixture with an empty `phases`/`route` (degrades to `current_phase() is
   None` rather than raising); `MissionPhaseTracker.update` advancing across a synthetic sequence of
   ownship positions that walks the fixture route; monotonicity (a position that regresses toward an
   earlier waypoint does not decrement `last_reached_waypoint_index`); a poll gap that jumps past an
   intermediate waypoint still advances past it (checks all unreached points, not just the very
   next one).
2. **Validate correctness — wire into `get_situation`/`_highest_attention_contact` and `logger.py`.**
   Add the `--mission-understanding` flag, thread the tracker through per the read/write thread
   split above, fold `mission_phase` into `get_situation`'s facts/summary, add the tie-break rule.
   Extend `test_tools.py` and add a `test_logger.py` case for the new flag (fixture-based, no live
   aircraft-layer needed, matching this file's existing pattern). Add the `tool_api.py` docstring
   sentence.
3. **Validate performance.** Not a meaningful concern here — `MissionPhaseTracker.update` and
   `mission_phase_relevance` are O(route length) per poll (a Mi-24 mission route is at most a few
   dozen waypoints), run once per poll tick alongside `ContactStore.tick`'s already-larger O(contacts
   × areas) work. State this explicitly rather than skip it: no profiling or optimization pass is
   warranted this milestone.
4. **Refine.** Run the full body-layer test suite + format/lint/type-check per `CLAUDE.md`
   Verification. Confirm the mock-flight chain fixture (`test_mock_flight_chain.py`) still passes
   untouched (mission-understanding loading is fully optional/additive, so it should need no
   changes) — this is exactly the kind of cross-layer regression that fixture was built to catch.

### Risks & Unknowns
- `WAYPOINT_CAPTURE_RADIUS_M` is a guessed placeholder pending live-flight calibration — same debt
  class as `visibility.py`'s already-flagged, still-uncalibrated tier constants. Do not treat the
  placeholder value as validated.
- `key_locations` in the compact artifact carries no position (`CompactLocation` has no `x`/`y`),
  so relevance can only be scored against route waypoints this milestone, not named mission-critical
  locations directly — a real gap against PETROBRAIN_SYSTEM.md's "target approaching a
  mission-critical area" framing if the mission-critical area isn't itself a route waypoint (e.g. an
  off-route objective). Not solved here; would need either MI-6 to start carrying positions on
  `CompactLocation` or a `find_place`-based resolution layer on this side.
- Monotonic waypoint-capture sequencing means a route point the aircraft never comes within
  `WAYPOINT_CAPTURE_RADIUS_M` of (overflies wide, or a waypoint type that isn't meant to be
  physically approached) permanently stalls phase progression at the last one actually reached —
  known limitation of the simplest sequencing algorithm, not addressed this milestone.
- This is the first real cross-subproject artifact body-layer has ever consumed that isn't
  world-model (in-process import) or aircraft-layer (HTTP) — `plans/mi6-runtime-compilation/plan.md`
  itself flags "no live BL-7 consumer exists to validate against." No live Mission Interpreter run
  against a real `.miz` has been tested end-to-end with body-layer; only the hand-written fixture is
  exercised this milestone. Live acceptance (does a real `--emit-compact` output actually load and
  sequence correctly against a real flight) is acceptance-testing debt, same posture as BL-6's
  deferred live-DCS acceptance of `scan_area`.
  Given this, this fixture is also the "gate" for schema drift: **whoever runs a real
  `player_intent/main.py --emit-compact` output through `load_mission_understanding` for the first
  time should treat a parse failure as a real schema-mismatch signal**, not a bug in the fixture.
- Thread-affinity: `MissionPhaseTracker` is designed with the same write-thread/read-thread split as
  `EnrichmentContext.ownship` specifically because this codebase has hit the same defect class twice
  already (BL-2 Stage 6, BL-5's `situation` crash). If the Implementer deviates from that split
  (e.g. mutates the tracker from the REPL thread for convenience), that's a reintroduction of a
  known defect class, not a new judgment call.

### Second-order effect
Once this lands, BL-8 (memory layer) gains a mission-phase dimension it can key episodic
memory off (e.g. "first seen during ingress" vs. "first seen during egress") without inventing its
own phase concept — narrows BL-8's design space usefully. It also gives the eventual Petrobrain
Runtime / brain layer (PB-9 proper, not built yet) a concrete phase + relevance signal to consume
once that layer exists, rather than nothing — this plan does not build proactive speech selection
itself, only the deterministic inputs a future PB-9 pass will need.
