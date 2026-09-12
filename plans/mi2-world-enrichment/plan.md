### Goal

Implement MI-2 from `plans/mission-interpreter/plan.md`: stand up world-model's first-ever HTTP
server wrapping `describe_position`/`find_place_by_name`/`line_of_sight_clear`, and have
mission-interpreter's new `world_enrich` package call it over HTTP to attach world-model context
(nearest settlement/road/junction/terrain, name matches) to route waypoints, group positions, and
trigger zones from MI-1.5's `CrewAvailableMission` — producing an `EnrichedMission` tree, still no
inference/interpretation layer.

### Context confirmed before finalizing this plan

- No unverified DCS-internals dependency here — MI-2 only calls world-model's already-confirmed
  `query` functions and reads MI-1/MI-1.5's already-typed `RawMission`/`CrewAvailableMission`
  fields. No investigator pass needed (matches the parent plan's own Decision 2 assessment).
- `world-model/src/query/__init__.py` today exports exactly `describe_position`,
  `find_place_by_name`, `PlaceMatch`, `line_of_sight_clear` — unchanged surface since the parent
  plan was drafted. What *did* change since then (read `describe.py` in full):
  - `PositionDescription` (M5-M10) now carries `nearest_road`/`nearest_road_osm`/
    `nearest_settlement`/`inside_settlement`/`nearest_water`/`nearby_ridges`/`nearby_valleys`/
    `nearest_junction` (M10, new)/`named_places_within_radius`/`nearest_airfield`/
    `nearest_runway`/`navaids_within_radius`/`region`, each a nested frozen dataclass or `None`.
    M9's OSM-boundary-aware settlement data flows through the *existing* `nearest_settlement`/
    `inside_settlement` fields with no shape change (M9's own "zero downstream changes" design) —
    so the HTTP wrapper needs no special-casing for it, it just serializes whatever
    `describe_position` returns today.
  - No `to_dict`/`asdict`-equivalent exists anywhere in `query/` or `store/models.py` today
    (confirmed by grep). Every dataclass involved (`PositionDescription` and all its nested
    `*Info` types, `PlaceMatch`) is `@dataclass(frozen=True)` with only primitives/`list`/`None`/
    other such dataclasses as field types — stdlib `dataclasses.asdict()` recurses through all of
    that correctly and the result round-trips through `json.dumps` with no custom code. This *is*
    "the smallest one that round-trips through `json.dumps`" the parent plan asked for — no new
    method needed on any dataclass.
  - `src/api/` does not exist yet (confirmed).
- `aircraft-layer/src/api/server.py` confirmed pattern to mirror: module-level path constants,
  a `_make_handler(...)` factory closing over caches/senders and returning a
  `BaseHTTPRequestHandler` subclass, a `_respond_json(status, body)` helper (`Content-Type`/
  `Content-Length` headers, `json.dumps(body).encode()`), a `TelemetryAPIServer`-shaped owning
  class (`open()`/`close()`/`serve_forever()`/`port` property/context-manager), `DEFAULT_HOST =
  "0.0.0.0"` (LAN-reachable), all read paths returning `200`/`404`, only `POST` paths validating
  a JSON body and returning `400`/`503`/`500` — world-model's server has no `POST` path at all
  (fully read-only), so only the `400` "bad query param" case applies here.
- `body-layer/src/aircraft_client.py` confirmed pattern to mirror: a frozen/slots dataclass
  wrapping `base_url`/`timeout_s`, one `get_*` method per endpoint, a `_get_json(path)` helper
  (`urllib.request.urlopen` -> `AircraftLayerError` on `URLError`/`OSError` or bad JSON), every
  `get_*` method raising its client's `*Error` on a wrong response shape rather than silently
  returning something malformed. `body-layer/tests/test_aircraft_client.py` confirmed the test
  pattern to mirror exactly: a hand-rolled `BaseHTTPRequestHandler` test double defined **inside
  the client's own test file**, not an import of the real server class from the other subproject
  — module independence means mission-interpreter's tests for `world_model_client.py` must not
  import anything from `world-model/`.
- `mission-interpreter/src/miz/tree.py` confirmed field shapes MI-2 must resolve:
  - `RoutePoint.x`/`RoutePoint.y` — **`y` is DCS's `z` axis** (the tree.py docstring: "`x`/`y` are
    DCS's native planar coordinates" and the parent plan's Context section: "`y` before `x` in
    file order, DCS planar coordinates"). World-model's `describe_position`/`line_of_sight_clear`
    take `(x, z)` — a call must be `describe_position(conn, theatre, x=point.x, z=point.y)`, never
    `z=point.z` (no such field). Same mapping applies to `Unit.x`/`Unit.y` and
    `TriggerZone.x`/`TriggerZone.y`/`TriggerZoneVertex.x`/`.y`. **This naming collision (mission
    file's `y` meaning world-model's `z`) is the single easiest thing to get backwards in this
    milestone — flagged explicitly, not left implicit in a field-name coincidence.**
  - `Group` has no single "group position" field — a group's position is really its route's start
    or its first unit's position. `Group.route: Route | None` (may be `None` for a static/non-moving
    group) and `Group.units: tuple[Unit, ...]` (always at least conceptually present, each with its
    own `x`/`y`).
  - `TriggerZone.kind` distinguishes circle (`0`, has `x`/`y`/`radius`) from polygon (`2`, has
    `vertices`, its own `x`/`y` fields still present but not necessarily meaningful for a polygon —
    treat as the shape's nominal anchor only when `kind == 0`; for `kind == 2` use the centroid of
    `vertices`, mirroring `query.search.find_place_by_name`'s own established point-for-polygon
    convention (`_representative_point`: mean of vertices) rather than inventing a different
    approximation.
  - `CrewAvailableMission` (from `filter/crew_available.py`) is MI-2's actual input — `RawMission`
    itself is never enriched (it still carries hidden/late-activation groups; enriching it would
    put world-model context next to author-only-knowledge fields with no filter boundary between
    them, silently widening what a later stage could accidentally treat as crew-known). MI-2 reads
    `RawMission` for nothing; `CrewAvailableMission.theatre`/`.coalitions`/`.trigger_zones` are the
    only structured inputs enriched.
- `body-layer/src/belief/enrichment.py`'s design precedent, directly on point: that module
  deliberately keeps world-model-derived semantic facts **outside** `belief.contacts.Contact`
  ("deliberately outside `belief.contacts.Contact` to keep zero shared surface with BL-2.6's
  concurrent work on that file") rather than adding new fields to the earlier stage's own frozen
  dataclass. MI-2 follows the identical shape: it does **not** add a `world_ref` field onto
  `miz.tree.RoutePoint`/`Unit`/`Group`/`TriggerZone` or `filter.crew_available.CrewAvailableMission`
  (MI-1/MI-1.5-owned files, frozen dataclasses) — doing so would mean editing another stage's
  already-tested module every time enrichment's shape changes, and would not be reversible without
  touching MI-1.5's filter tests. Instead, `world_enrich/schema.py` defines a **parallel tree**
  (`EnrichedMission`/`EnrichedCoalition`/`EnrichedCountry`/`EnrichedGroup`/`EnrichedRoutePoint`/
  `EnrichedTriggerZone`), each wrapping the original MI-1/MI-1.5 dataclass by reference plus a
  `WorldRef` field, mirroring the parent plan's own wording ("the raw tree gains `world_ref`
  fields... alongside DCS coordinates") without literally mutating MI-1.5's types. This is a local,
  reversible implementation choice under this project's escalation rules (not a fork CLAUDE.md
  needs to resolve) — noted here rather than escalated.

### Scope narrowing (stated explicitly, not silently dropped)

- **Per-unit enrichment is out of scope.** The parent plan says "resolve route/objective/group
  ... coordinates" (group, singular) — a group's units are colocated at mission start, so
  enriching every `Unit.x`/`.y` individually would mean redundant near-identical
  `describe_position` calls per group member. MI-2 enriches one representative position per group
  (its first unit's `x`/`y` if `units` is non-empty, else skipped) plus every one of that group's
  route waypoints (`Group.route.points[]`, when `route` is not `None`). `EnrichedGroup` still
  carries the original `Group.units` tuple untouched (no per-unit `WorldRef`).
- **Free-text place-mention extraction from briefing text is out of scope.** The parent plan's MI-2
  wording ("`find_place_by_name` for named objectives/briefing place mentions") is read here as
  covering *structured* name fields only (`Group.name`, `TriggerZone.name`) — deterministically
  calling `find_place_by_name` on a string a mission author typed as an entity's own name. Scanning
  free-text briefing paragraphs for candidate place names is a genuinely different capability (it
  requires deciding which words in prose are plausibly place names before ever querying
  world-model) and would be interpretation, not deterministic resolution — squarely the thing the
  project invariant "models interpret facts, they never invent them" and this plan's own "no
  inference/interpretation layer yet" scope boundary rule out at this stage. `EnrichedMission.
  briefing` is `CrewAvailableMission.briefing` unchanged, byte-for-byte. Deferred to MI-4 (the
  capable-model synthesis stage), where a model could propose place-name candidates from briefing
  text for MI-2's *existing* `world_model_client.find_place_by_name` call to verify against the
  store — i.e. MI-4 would call back into this milestone's client, not duplicate it.
- **No "objective" field exists in `RawMission`/`CrewAvailableMission`** — there is no separate
  objectives list to resolve beyond route waypoints, group positions, and trigger zones (which
  frequently *are* a mission's objective/target-area markers). MI-2 treats those three as the
  complete set of coordinate-bearing entities available to enrich; if a future mission sample
  surfaces a distinct "objective" construct MI-1 didn't model, that is a MI-1 scope gap to raise
  then, not something MI-2 should invent a placeholder for now.

### Affected Modules / Files

- `world-model/src/api/__init__.py` (new, empty) — new subpackage.
- `world-model/src/api/server.py` (new) — `WorldModelAPIServer`, mirroring
  `aircraft-layer/src/api/server.py`'s shape: `_make_handler(conn, theatre, probe_db_path,
  named_places_radius_m, navaids_radius_m, los_samples)` closing over one already-open
  `sqlite3.Connection` bound to one theatre's `.sqlite`; `_respond_json` helper identical in shape
  to aircraft-layer's. Three `GET` routes, `404` on anything else, no `POST` routes at all:
  - `GET /describe_position?x=<float>&z=<float>&theatre=<str>` — `400` if `x`/`z` missing or not
    parseable as `float`; `400` if `theatre` is missing or does not match the server's own bound
    `theatre` string (a caller passing the wrong theatre against this process would otherwise get
    a silently-wrong lat/lon via the wrong projection — see `describe.describe_position`'s own
    `dcs_to_wgs84(theatre, ...)` call — so this mismatch must be loud, not silently accepted).
    On success: `200`, body = `dataclasses.asdict(query.describe.describe_position(conn, theatre,
    x, z, named_places_radius_m=..., navaids_radius_m=..., probe_db_path=...))`.
    `named_places_radius_m`/`navaids_radius_m`/`probe_db_path` are constructor args on
    `WorldModelAPIServer`, not query params (per the parent plan's Decision 2 design — no reason
    for a per-call override, and exposing `probe_db_path` as a client-suppliable path would be a
    needless surface even under the current no-auth exemption).
  - `GET /find_place_by_name?text=<str>[&kinds=<comma-separated>]` — `400` if `text` missing.
    `kinds` omitted means `query.search.PLACE_KINDS`'s own default (pass `None` through, not an
    empty list). On success: `200`, body = `[dataclasses.asdict(m) for m in
    query.search.find_place_by_name(conn, text, kinds)]`.
  - `GET /line_of_sight?ox=<float>&oz=<float>&oalt=<float>&tx=<float>&tz=<float>&talt=<float>&theatre=<str>`
    — same `400`s as `/describe_position` for missing/non-numeric params and theatre mismatch. On
    success: `200`, body = `{"clear": query.line_of_sight.line_of_sight_clear(conn, theatre,
    (ox, oz, oalt), (tx, tz, talt), samples=...)}`. `samples` is a constructor arg, same reasoning
    as the radii above.
- `world-model/src/api/__main__.py` (new) — process entrypoint: `argparse` for `--db` (required,
  path to `<theatre>.sqlite`), `--theatre` (required — the store itself doesn't self-report which
  theatre it was built for as a queryable string the same way `--theatre` needs to match for the
  coordinate transform, so this stays an explicit flag rather than something read from the DB),
  `--probe-db` (optional), `--host`/`--port` (default `WorldModelAPIServer`'s own module
  constants, mirroring `aircraft-layer`'s `DEFAULT_HOST`/`DEFAULT_PORT` naming). Opens
  `sqlite3.connect(db_path)`, builds the server, `serve_forever()`.
- `world-model/tests/test_api.py` (new) — spins up a real `WorldModelAPIServer` on `port=0` in a
  background thread against a small real on-disk store built the same way `tests/test_describe.py`
  (or whichever existing test builds a minimal store fixture — implementer to confirm the
  established fixture-building helper before writing a new one) already does, queries all three
  routes with `urllib.request`, mirroring `aircraft-layer/tests/test_api.py`'s pattern exactly:
  happy path for each endpoint, `400` for missing/non-numeric params, `400` for a mismatched
  `theatre`, `404` for an unknown path.
- `world-model/CLAUDE.md` — add a one-line "World-model seam: HTTP, not in-process" note under
  Tech stack (documentation of the now-existing fact, not new design).
- `mission-interpreter/src/world_enrich/__init__.py` (new).
- `mission-interpreter/src/world_enrich/world_model_client.py` (new) — `WorldModelClient`
  (`@dataclass(frozen=True, slots=True)`, `base_url`/`timeout_s`), `WorldModelClientError`
  (`RuntimeError` subclass). `get_describe_position(x, z) -> dict[str, Any]`,
  `get_find_place_by_name(text, kinds=None) -> list[dict[str, Any]]`,
  `get_line_of_sight_clear(observer, target) -> bool` — all three raise
  `WorldModelClientError` on network failure, non-200, or malformed JSON (no `get_*`-swallows-to-
  `None` methods at all, unlike `aircraft_client.py` — see the parent plan's reasoning: there is no
  "world-model not built yet" expected-empty state once MI-2 runs, a query failure is a real gap).
  `theatre` is a constructor field too (matches the server binding to one theatre) so every call
  site doesn't have to pass it per-call.
- `mission-interpreter/src/world_enrich/schema.py` (new) — `WorldRef` (`position: dict[str, Any]`
  — the raw `describe_position` JSON, `name_matches: tuple[dict[str, Any], ...]` — raw
  `find_place_by_name` JSON, empty when the source entity has no name or no match was found), and
  the parallel enriched tree: `EnrichedRoutePoint(point: RoutePoint, world_ref: WorldRef)`,
  `EnrichedGroup(group: Group, world_ref: WorldRef | None, route: tuple[EnrichedRoutePoint, ...] |
  None)` (`world_ref` is `None` only when the group has no units to derive a representative
  position from), `EnrichedCountry(country: Country, groups: tuple[EnrichedGroup, ...])`,
  `EnrichedCoalition(coalition: Coalition, countries: tuple[EnrichedCountry, ...])`,
  `EnrichedTriggerZone(zone: TriggerZone, world_ref: WorldRef)`, `EnrichedMission(theatre: str,
  coalitions: tuple[EnrichedCoalition, ...], trigger_zones: tuple[EnrichedTriggerZone, ...],
  briefing: BriefingText, kneeboard_images: tuple[str, ...])`. Deliberately dicts for
  `WorldRef.position`/`.name_matches`, not re-declared mirror dataclasses of world-model's
  `PositionDescription`/`PlaceMatch` — avoids a second, hand-maintained copy of world-model's
  schema inside mission-interpreter that could silently drift from the real one (mirrors
  `aircraft_client.py`'s own `dict[str, Any]` return convention for exactly this reason).
- `mission-interpreter/src/world_enrich/enrich.py` (new) — `enrich_mission(mission:
  CrewAvailableMission, client: WorldModelClient) -> EnrichedMission`, the walk described in
  "Scope narrowing" above: one `describe_position` call per route waypoint and per group's
  representative position, one `describe_position` call per trigger zone (circle anchor or polygon
  centroid), one `find_place_by_name` call per named `Group`/`TriggerZone` (name stripped/
  non-empty check mirroring `find_place_by_name`'s own empty-string guard so an unnamed entity
  doesn't burn a call for nothing).
- `mission-interpreter/tests/test_world_model_client.py` (new) — a hand-rolled
  `BaseHTTPRequestHandler` test double defined in this file (per the confirmed
  `body-layer/tests/test_aircraft_client.py` pattern), covering: happy path for all three
  `get_*`/`get_line_of_sight_clear` methods, network-error and non-JSON-response raising
  `WorldModelClientError`, a `404`/`400` response raising `WorldModelClientError` too (no `get_*`
  method here has a legitimate "expected empty" response to swallow).
- `mission-interpreter/tests/test_enrich.py` (new) — `enrich_mission` against a fake
  `WorldModelClient`-shaped double (a small recording stub, not a real HTTP server — no need for
  wire-format fidelity at this layer, that's `test_world_model_client.py`'s job) plus the
  committed synthetic `.miz` fixture (`tests/fixtures/synthetic_mission.py`) run through MI-1 +
  MI-1.5 first to get a real `CrewAvailableMission`. Assert: every route waypoint and every named
  group/trigger-zone gets a `WorldRef`; an unnamed group/zone's `name_matches` is empty and no
  `find_place_by_name` call was made for it (assert on the stub's call log); the `y`->`z` axis
  mapping is exercised correctly (a waypoint with distinct `x`/`y` values must reach the stub as
  `x=point.x, z=point.y`, not swapped or dropped).
- `mission-interpreter/tests/test_api_integration.py` (new, optional — see Risks) — if cheap, a
  true end-to-end test: spin up a real `WorldModelAPIServer` (imported directly, since this one
  test file is explicitly allowed to reach across the subproject boundary for its own
  self-contained integration check — unlike `test_world_model_client.py`, which must stay
  import-free per module independence) against a tiny fixture store, point a real
  `WorldModelClient` at it, run `enrich_mission` end to end. Skip this file (or guard it
  `@pytest.mark.skipif`) if wiring a second subproject's `PYTHONPATH` into mission-interpreter's
  own `pytest` run turns out to fight the module-independence setup non-trivially — implementer's
  call once attempted; not worth forcing if it becomes its own small saga, since
  `test_world_model_client.py` + `world-model/tests/test_api.py` already cover both halves
  independently.
- `mission-interpreter/CLAUDE.md` — update the "No spatial storage, no HTTP server yet" Tech stack
  line to describe the now-real HTTP seam (mirrors `world-model/CLAUDE.md`'s new line from the
  other side), and add `world_enrich/` to the Structure section.
- `mission-interpreter/ROADMAP.md` — mark MI-2 in progress, then done, once merged.

### Implementation Plan

1. **World-model HTTP server, minimal working version.** `src/api/server.py` +
   `src/api/__main__.py` with all three `GET` routes (simplicity: no reason to stage
   `describe_position` before the other two, the routing/response-helper scaffolding is identical
   for all three and stdlib-only). Manual smoke test against a real built `.sqlite` before writing
   automated tests.
2. **Server tests (validate correctness).** `world-model/tests/test_api.py` — happy path + every
   `400`/`404` case listed above.
3. **Mission-interpreter HTTP client.** `world_model_client.py` + `test_world_model_client.py`
   against the hand-rolled local test double.
4. **Enrichment walk.** `schema.py` + `enrich.py`, tested with the fake-client double
   (`test_enrich.py`) against the committed synthetic fixture — this is where the `y`->`z` mapping
   correctness gets proven, before ever touching a real server.
5. **Wire the two together (validate end-to-end).** Attempt `test_api_integration.py` per the
   note above; keep or drop per that note's guidance.
6. **Docs/roadmap.** `CLAUDE.md` updates on both sides, `ROADMAP.md` flip to done.

### Risks & Unknowns

- **The `y`==DCS-`z` naming collision is the single most likely correctness bug in this
  milestone** — a swapped or misnamed argument would not crash, it would silently query the wrong
  ground position and return a plausible-looking but wrong `describe_position` result (wrong
  settlement/road distances). Mitigated by `test_enrich.py`'s explicit assertion on this mapping
  using a fixture with visibly distinct `x`/`y` values (not a symmetric/coincidental one where a
  swap bug would go undetected).
- **HTTP call volume is unbounded by mission size** — one call per route waypoint + one per
  group + one per trigger zone + one `find_place_by_name` per named entity, all synchronous,
  serial. For the one real sample mission (`Mission 02-Bagram.miz`) this is likely dozens of
  calls, not thousands — acceptable for an offline pre-mission tool, and Performance Reviewer is
  exempt this phase per `CLAUDE.md`'s Agents section. Flagged here in case a much larger mission
  sample surfaces later and this becomes a real latency complaint worth revisiting (batching
  endpoint, connection reuse) — not addressed now.
- **No batching/connection-reuse in `WorldModelClient`** — each call opens a fresh
  `urllib.request.urlopen`, same as `aircraft_client.py`'s own established pattern. Consistent
  with precedent, not a new risk this milestone introduces.
- **`test_api_integration.py`'s cross-subproject `pytest`/`PYTHONPATH` wiring may or may not be
  cheap** — genuinely unknown until attempted (this is a from-scratch subproject with its own venv
  and no prior cross-subproject test in this direction to copy from). Not a blocking risk: the
  split unit-test coverage on each side already proves both halves independently even if this one
  integration file is dropped.
- **`theatre` as a required, hand-typed CLI flag on `api/__main__.py`** rather than something the
  store self-reports: if a user starts the server with the wrong `--theatre` for the `.sqlite`
  they pointed at, `dcs_to_wgs84` inside `describe_position` will silently use the wrong
  theatre's projection. This is the same class of risk `describe_position`'s own signature already
  carries today (it takes `theatre` as a plain argument, not derived from the connection) — MI-2
  does not introduce a new version of this risk, just exposes the existing one at a new (CLI)
  entry point. Not fixed here; worth a future world-model milestone if it becomes a real
  operator-error source (e.g., storing `theatre` as store metadata and reading it back instead of
  requiring the flag).

### Second-order effect

This is the first real HTTP seam between two Petrobrain subprojects other than
aircraft-layer<->body-layer, so it is now a second live precedent (alongside that one) for "the
default cross-subproject boundary is HTTP/JSON" — future subproject pairs (e.g., a future
Petrobrain Runtime consuming Mission Interpreter's output) have two worked examples to follow
instead of one, which narrows that future design space rather than leaving it open. It also means
world-model's query surface (`describe_position`/`find_place_by_name`/`line_of_sight_clear`) now
has two consumers with different transport needs (body-layer in-process, mission-interpreter over
HTTP) — any future change to those three functions' signatures or `PositionDescription`'s shape
needs to consider both call sites, not just the in-process one it was originally designed for.

### Decisions Requiring User Input

None. The one implementation-shape choice this plan makes on its own initiative — a parallel
`Enriched*` tree instead of adding `world_ref` fields onto MI-1/MI-1.5's frozen dataclasses — is a
local, reversible choice with a direct precedent already in this codebase
(`belief.enrichment`'s "keep zero shared surface" reasoning), not an architectural fork CLAUDE.md
leaves open; stated above rather than escalated, per AGENTS.md's escalation rules.
