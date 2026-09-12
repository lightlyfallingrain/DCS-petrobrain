### Goal

Stand up the `mission-interpreter/` subproject — the second Petrobrain layer, currently zero code
— starting with a deterministic `.miz`/briefing parser and a provisional, versioned "Mission
Understanding" schema, deferring the capable-model synthesis stage until the schema and the
author-only-knowledge filter have proven out on a real mission file.

### Context this plan rests on

- Both concept docs (`docs/concept/MISSION_INTERPRETER.md`, `docs/concept/PETROBRAIN_SYSTEM.md`)
  are explicitly "draft/provisional... revise as the World Model Builder matures." World Model is
  now "good enough" (M0–M8 done, `world-model/ROADMAP.md`), so this plan treats those docs as a
  hypothesis to grounded-check against what World Model actually offers today
  (`query.describe.describe_position(x, z, ...)`, `query.search.find_place_by_name`), not as a
  fixed spec.
- `body-layer/ROADMAP.md`'s BL-7 is gated on either this layer existing or a hand-written Mission
  Understanding fixture. This plan's schema (Stage 2) is written so a fixture can mimic it
  faithfully without waiting on the rest of the pipeline.
- Investigator resolved `.miz` internal structure across two sessions — a first secondhand pass
  (`mission-interpreter/research/2026-09-12-miz-file-structure.md`, Hoggit/forum/pydcs-source only,
  no real bytes) and a second pass validating that against a real sample file
  (`mission-interpreter/research/2026-09-12-miz-validation-against-real-sample.md`,
  `mission-interpreter/research/samples/Mission 02-Bagram.miz`, gitignored). The second pass is now
  the load-bearing one wherever the two disagree; findings below are the corrected/confirmed
  picture, not the secondhand original:
  - `.miz` is a zip: `mission`, `options`, `warehouses`, `theatre` (plain-text top-level file),
    `l10n/DEFAULT/dictionary`, **`l10n/DEFAULT/mapResource`** (nested under `l10n/DEFAULT/`, not a
    zip-root member as the secondhand note assumed), and a flat `KNEEBOARD/IMAGES/` tree in this
    sample (not `KNEEBOARD/<aircraft>/IMAGES/` — that per-aircraft nesting is unconfirmed, possibly
    author-dependent).
  - Briefing/task text is **externalized**, and this externalization is **tree-wide, not limited to
    the four briefing fields**: `mission["descriptionText"]` / `descriptionBlueTask`/
    `descriptionRedTask`/`sortie` hold `DictKey_...` IDs as the secondhand note found, but so does
    every trigger-action's user-facing text (`DictKey_ActionText_*`, `DictKey_ActionRadioText_*`,
    `DictKey_ActionComment_*`) — real-bytes finding, not anticipated secondhand. MI-1's dictionary
    resolution must be a **generic recursive substitution pass over the whole parsed tree**
    (replace any string value matching `^DictKey_` via `l10n/DEFAULT/dictionary` lookup), not four
    hardcoded field lookups — see the corrected MI-1 scope below.
  - Author-only knowledge has **real structural markers, confirmed present and in active use**:
    `Group.hidden`, `hiddenOnPlanner` (9 occurrences in the sample), `lateActivation` (5
    occurrences, ambush/late-spawn groups) all confirmed against real bytes. `hiddenOnMFD` remains
    unconfirmed (zero occurrences in this one sample — not falsified, just unexercised by this
    author).
  - Two distinct trigger structures, both confirmed, plus a **third, previously-unknown one**:
    `triggers.zones[]` (zone geometry — real bytes confirm **two shapes coexist**, `type=0` circles
    and `type=2` polygons; polygon vertices sit under the literal key `"verticies"` — **DCS ships
    this key genuinely misspelled**, not a documentation typo, so a parser/schema must use that
    exact spelling or it will silently find nothing) and `trigrules` (condition→action rules — real
    schema is a `predicate`-string tree: rule-kind predicates `triggerStart`/`triggerOnce`/
    `triggerContinious` [DCS's own spelling] /`triggerFront`, condition predicates prefixed `c_`,
    action predicates prefixed `a_`, plus an `"or"` combinator — 39 unique predicate strings
    observed, closed and greppable per-file). A third table, `mission["trig"]`, was not documented
    anywhere secondhand and holds **generated Lua source-code strings** using the same `a_*`/`c_*`
    predicates as literal function calls — looks like a compiled/flattened form of `trigrules`, but
    whether `trig` or `trigrules` is authoritative at runtime is unresolved (see Risks and Decision
    5 below).
  - `route.points[]` and `mission["weather"]` sub-schemas are now **real-bytes-confirmed**, not
    secondhand-sourced: waypoints carry `alt`/`action`/`alt_type`/`speed`/`task.id`/
    `task.params.tasks[]`/`type`/`ETA`/`ETA_locked`/`x`/`y` (y before x in file order, DCS planar
    coordinates)/`speed_locked`/`formation_template`; weather carries
    `wind.{atGround,at2000,at8000}.{speed,dir}`, `enable_fog`/`fog.{visibility,thickness}`/`fog2`,
    `season.temperature`, `qnh`, `cyclones`, `dust_density`/`enable_dust`,
    `clouds.{thickness,density,preset,base,iprecptns}`, `atmosphere_type`, `groundTurbulence`,
    `halo.preset`, `type_weather`, `name`, `visibility.distance`.
  - Group/unit container path, not anticipated secondhand: `mission.coalition.<side>.country[N].
    <category>.group[]` (`<category>` by unit type — `helicopter`/`plane`/`vehicle` — not by side).
  - Prior art: `pydcs` (dcs-liberation/pydcs, LGPL-3.0) is still the recommended base for the
    general Lua-table parse (`dcs/lua/parse.py`/`serialize.py`, no embedded Lua VM, no
    `lupa`/`slpp`) — real-bytes reading found nothing that would break it. For `trigrules`
    specifically, real bytes show pydcs's `TriggerRule`/condition/action wrapper classes are a
    **lossy abstraction** over the raw `predicate`-string tree — see Decision 1a below for whether
    MI-1.5 should parse that raw form directly instead of going through pydcs for it.
  - **Standing risk, not fully closed by the real-bytes pass**: no official ED schema exists
    anywhere — the whole `mission` table shape is still community-reverse-engineered (pydcs has an
    open issue where a DCS content update broke its parsing assumptions), and **only one sample
    mission has been examined** (single author, single terrain, mission-format `version` = 23) —
    every "confirmed" finding above is confirmed *in this file*, not proven universal across DCS/
    Mission-Editor versions. MI-1's parser should be written expecting adjustment against a second
    sample, not treated as fully general from this one.

### Affected Modules / Files (new subproject)

- `mission-interpreter/` — new subproject root, sibling to `world-model/`/`aircraft-layer/`/
  `body-layer/`, own venv per the module-independence rule.
  - `pyproject.toml` — `dcs-mission-interpreter`, Python 3.11+, `mypy --strict`, `ruff`, `pytest`.
    New dependency: pydcs's `dcs.lua` parse/serialize subpackage (see Decision 1 below) —
    vendored or a scoped dependency, not the full `pydcs` package (its generated
    `weapons_data.py`/`countries.py` are ~1.7MB combined and unneeded — Mission Interpreter's own
    semantic layer is bespoke, it doesn't need pydcs's weapon/country catalogs).
  - `CLAUDE.md` — stack/testing/structure specifics, modeled on `world-model/CLAUDE.md`'s
    structure (Tech stack / Commands / Testing / Structure sections).
  - `ROADMAP.md` — MI-x milestone tracking, mirroring `world-model/ROADMAP.md`'s format; add its
    row to root `ROADMAP.md`'s status table (currently "Not started — —").
  - `src/miz/` — `.miz` zip reading, `mission` table + `l10n/DEFAULT/dictionary` parsing via the
    vendored Lua parser, DictKey resolution. DictKey resolution is a **generic recursive
    tree-walk substitution pass** over the entire parsed tree (any string matching `^DictKey_` is
    replaced via a `l10n/DEFAULT/dictionary` lookup), not a fixed list of known fields — real
    bytes showed trigger-action text (`DictKey_ActionText_*`/`ActionRadioText_*`/`ActionComment_*`)
    uses the same mechanism as the four briefing fields, so a hardcoded field list would silently
    miss it. Output: an inspectable intermediate dataclass tree (theatre, date, weather,
    groups/units, routes, triggers/trigrules, briefing text, kneeboard image refs) — this is
    deliberately a *typed mirror of the raw mission file*, not yet filtered or interpreted. No
    model involved at this stage — deterministic parser only, per "code owns truth." Trigger-zone
    polygon parsing must read the vertex array under its real (misspelled) key, `"verticies"` — do
    not "fix" this to `"vertices"` when writing the dataclass/parsing code; it is DCS's own shipped
    spelling, confirmed in real bytes, and using the corrected spelling will just find nothing.
  - `src/filter/` — the author-only-knowledge boundary (concept doc's central invariant). Takes
    the raw parsed tree and produces a "crew-available" subset: drops `hidden`/`hiddenOnPlanner`/
    `hiddenOnMFD` groups and `lateActivation` groups entirely from what reaches the schema below
    (their existence is not crew knowledge — a `lateActivation` group may still inform *derived*
    threat expectations from `trigrules`/briefing text, but never as "this exact unit is here");
    keeps `trigrules` only as raw data for research/debugging, never surfaced in Mission
    Understanding. This module is the concrete mechanism the concept doc only names in principle
    — see "Decisions Requiring User Input" for what's still open about it. Parses `trigrules`'
    real schema directly (a `predicate`-string tree — rule-kind/`c_*`/`a_*`/`"or"` — confirmed
    closed and greppable, 39 values in the one sample examined) rather than through pydcs's
    `TriggerRule`/condition/action wrapper classes, which real-bytes reading showed to be a lossy
    abstraction over that structure for this specific purpose (see Decision 1a). Tolerate an
    unrecognized `predicate` value by logging and skipping, not failing hard — the vocabulary is
    undocumented by ED and could gain values across patches. `mission["trig"]` (the newly-found
    generated-Lua-source table, see Decision 5) is explicitly **not** parsed by MI-1.5 — documented
    as an out-of-scope gap, not silently ignored.
  - `src/schema/` — the "Mission Understanding" dataclasses/schema (Stage boundary below), with
    the FACT/OBSERVATION/INFERENCE/ASSUMPTION/UNKNOWN epistemic tag as a first-class field on
    every derived statement, not a convention. Includes a schema version field from day one — BL-7
    and any hand-written fixture need a stable target.
  - `src/world_enrich/` — resolves route/objective/group coordinates against World Model's
    `describe_position`/`find_place_by_name` (see Decision 2 — transport boundary).
  - `src/synth/` — the capable-model synthesis stage (Stage 4+, gated — see Decision 3).
  - `tests/` — parser tests against a real (or hand-built minimal) `.miz` fixture, filter tests
    asserting hidden/late-activation groups never leak into the crew-available tree, schema
    round-trip tests.
  - `research/` — already seeded with `2026-09-12-miz-file-structure.md` (investigator's note,
    currently at `mission-interpreter/research/miz_file_structure.md` — rename to add the date
    prefix other subprojects use, e.g. `research/2026-09-12-miz-file-structure.md`, for
    consistency with `world-model/research/`'s naming convention).
- `world-model/` — **real new scope (Decision 2 resolved to HTTP, see below), not "out of this
  plan" any more.**
  - `src/api/server.py` — world-model's **first-ever HTTP server**, mirroring
    `aircraft-layer/src/api/server.py`'s shape exactly: stdlib `http.server.ThreadingHTTPServer`,
    no framework, no auth (Security is exempt this phase per `CLAUDE.md`'s Agents section).
    Read-only GET only — world-model has no write path and this plan adds none. One server
    instance is bound to one already-open `sqlite3.Connection` (i.e. one theatre's built
    `<theatre>.sqlite`, optionally with a probe store path for `describe_position`'s
    `probe_db_path`), the same "one process, one region" shape `query`'s functions already
    assume — a second theatre means a second server process/port, not a theatre selector on every
    request.
    - `GET /describe_position?x=<float>&z=<float>&theatre=<str>` -> `query.describe.
      describe_position(conn, theatre, x, z)` result as JSON (`PositionDescription` needs a
      `to_dict`/`asdict`-equivalent — check whether one already exists on that dataclass before
      adding one; if not, add the smallest one that round-trips through `json.dumps`).
      `named_places_radius_m`/`navaids_radius_m`/`probe_db_path` stay server-side configuration
      (constructor args), not query params — Mission Interpreter has no reason to vary them
      per-call, and exposing `probe_db_path` as a client-supplied filesystem path would be a
      needless surface even under this phase's no-auth exemption.
    - `GET /find_place_by_name?text=<str>[&kinds=<comma-separated>]` -> `query.search.
      find_place_by_name(conn, text, kinds)` -> JSON list of `PlaceMatch` dicts. `kinds` omitted
      means the function's own `PLACE_KINDS` default, not an empty list.
    - `GET /line_of_sight?ox=<float>&oz=<float>&oalt=<float>&tx=<float>&tz=<float>&talt=<float>&theatre=<str>`
      -> `query.line_of_sight.line_of_sight_clear(conn, theatre, (ox, oz, oalt), (tx, tz, talt))`
      -> JSON `{"clear": <bool>}`. `samples` stays server-side default, same reasoning as
      `describe_position`'s radii above.
    - All three: `400 {"error": ...}` on a missing/non-numeric required param, matching
      `aircraft-layer/src/api/server.py`'s `_respond_json` error-body convention exactly (reuse
      that convention's shape, don't invent a new error envelope).
  - `src/api/__main__.py` (or a `--serve` mode wired through an existing entrypoint, implementer's
    call) — process entrypoint: open one theatre's `.sqlite` (+ optional probe store), bind
    `TelemetryAPIServer`-equivalent (name it e.g. `WorldModelAPIServer`), `serve_forever()`.
  - `tests/test_api.py` — spin up a real server on an OS-assigned port in a background thread,
    query with stdlib `urllib.request`, mirroring `aircraft-layer/tests/test_api.py`'s pattern
    exactly (same precedent Decision 2's design leans on).
  - `CLAUDE.md` — add a "World-model seam: HTTP, not in-process" line under Tech stack once this
    lands, so a future reader of world-model's own doc sees the same fact body-layer's `CLAUDE.md`
    states from the client side (see below) — this is documentation of an existing-project-wide
    fact, not new design, but it belongs on both sides.
- `mission-interpreter/src/world_enrich/` — an HTTP client module, `world_model_client.py`,
  mirroring `body-layer/src/aircraft_client.py`'s shape: a small `@dataclass(frozen=True, slots=True)`
  wrapping `base_url`/`timeout_s`, stdlib `urllib.request` only (no `requests` dependency — matches
  this project's stdlib-only-unless-justified policy already followed by both aircraft-layer and
  body-layer's HTTP clients), one `get_*` method per endpoint above
  (`describe_position`/`find_place_by_name`/`line_of_sight_clear`), raising a
  `WorldModelClientError` on network failure or non-JSON response (all three are reads Mission
  Interpreter needs to succeed to enrich a waypoint — unlike aircraft-layer's `/latest` "empty
  cache is not an error" convention, a world-model query failure here is a real gap the caller
  should know about, closer to `push_text_line`'s raise-on-failure posture than `get_telemetry_latest`'s
  swallow-to-`None` one, since there is no "not built yet" expected-empty state once MI-2 runs —
  the store either has an answer or the call itself failed).
- `body-layer/ROADMAP.md` — update BL-7's entry once this subproject exists, noting it's
  available (not requiring BL-7 to still wait on a fixture) — a bookkeeping change for later, not
  part of this plan's own commits.
- Root `ROADMAP.md` — add Mission Interpreter's status row once MI-0/MI-1 land.

### Implementation Plan

1. **MI-0 — Get a real `.miz` and lock the schema shape. Done.**
   Completed 2026-09-12: `mission-interpreter/research/samples/Mission 02-Bagram.miz` obtained and
   validated against, producing `research/2026-09-12-miz-validation-against-real-sample.md`
   (top-level listing, DictKey scope, `lateActivation`/`hidden*` fields, `route.points[]` fields,
   `weather` sub-schema, trigger-zone geometry, `trigrules` predicate schema, the `trig` table —
   all now real-bytes findings, not secondhand). Only one sample/author/DCS mission-format version
   has been examined; treat every finding as "true in this file," not yet "true in general."
   `MissionUnderstanding` schema freeze from real data still applies as originally scoped.

2. **MI-1 — Structured `.miz` parser (minimal working version).**
   `src/miz/` reads the zip, parses `mission` + `l10n/DEFAULT/dictionary` via the vendored Lua
   parser, and produces the raw typed intermediate tree. DictKey resolution is a **recursive
   tree-wide substitution pass** (walk the whole parsed tree, replace any `^DictKey_`-matching
   string via dictionary lookup) — corrected from the plan's original "resolve DictKeys in the
   known briefing/sortie fields" framing, which real bytes showed to be incomplete (trigger-action
   text uses the same mechanism). Scope: theatre, date/weather, ownship group/route
   (`mission.coalition.<side>.country[N].<category>.group[]`), briefing text, trigger zones
   (including the literal `"verticies"` key for polygons — do not respell it), kneeboard image
   refs (pass through as opaque bytes/paths, no OCR/VLM). Explicitly out of scope this stage: full
   unit/weapon taxonomy (no pydcs country/weapon catalogs), `mission["trig"]` (documented gap, see
   Decision 5). `trigrules` action-type enumeration is **no longer open** — real bytes confirmed a
   closed `predicate`-string vocabulary (39 values, one sample) — but MI-1 itself only needs to
   parse `trigrules` structurally; deciding *how* to interpret those predicates for filtering is
   MI-1.5's job. Inspectable JSON/YAML dump for manual review, matching the concept doc's MI-1
   scope and this project's "prefer inspectable intermediate representations" invariant.
   Implementer should expect this parser to need adjustment once tried against a second sample
   mission — it is written against one file, not a spec.

3. **MI-1.5 — Author-only-knowledge filter (validate correctness, before enrichment).**
   `src/filter/` implementation + tests proving `hidden*`/`lateActivation` groups never appear in
   the crew-available tree, using MI-0's real mission file as the primary fixture (the sample
   already contains real `hidden`/`hiddenOnPlanner`/`lateActivation` groups — no synthetic fixture
   needed for those three flags; `hiddenOnMFD` still needs a hand-added fixture case since the
   sample doesn't exercise it). Parses `trigrules`' `predicate`-tree directly for reasoning about
   scripted spawns/ambushes (see Decision 1a). `mission["trig"]` is out of scope this stage — see
   Decision 5; this is a documented gap in filter completeness, not a silent omission. This is
   pulled forward ahead of world-enrichment and model synthesis because it is the plan's central
   invariant (per CLAUDE.md's "must filter out mission-author-only knowledge before it reaches the
   crew layer") and is cheap to get wrong silently if built last, under schedule pressure, as an
   afterthought bolted onto a later stage.

4. **MI-2 — World enrichment.**
   Prerequisite sub-stage: stand up world-model's `src/api/server.py` (HTTP wrapper around
   `describe_position`/`find_place_by_name`/`line_of_sight_clear`, see Affected Modules/Decision
   2) and `mission-interpreter/src/world_enrich/world_model_client.py` against it — this is new
   scope in a subproject (world-model) that otherwise has none planned this cycle, so treat it as
   its own small implementation+test pass, not folded silently into MI-2's "resolve coordinates"
   work. Once the client is up: `src/world_enrich/` resolves route/objective/group DCS x/z
   coordinates against it (`describe_position` for "what's near this waypoint",
   `find_place_by_name` for named objectives/briefing place mentions). Output: the raw tree gains
   `world_ref` fields (settlement/road/terrain context) alongside DCS coordinates, still no
   inference/interpretation layer yet.

5. **MI-3 — First Mission Understanding schema without model synthesis.**
   Hand-map MI-1.5's filtered tree + MI-2's world context directly into the `MissionUnderstanding`
   schema fields that don't require judgment (theatre, ownship, route, mission_phases skeleton
   from waypoint `action`/`type`, important_locations from named waypoints/objectives). Every
   field here is FACT or OBSERVATION, never INFERENCE — this deliberately produces a real,
   schema-valid, capable-model-free Mission Understanding early, so BL-7 has something concrete to
   integrate against without waiting for Stage 4-6, and so the schema itself gets exercised and
   corrected before the harder synthesis work is built on top of it.

6. **MI-4 — Capable-model synthesis (gated on Decision 3).**
   `src/synth/` adds the actual reasoning layer: purpose/task inference from briefing text +
   route/objective geometry, known/suspected threats from briefing + `trigrules` (never raw
   `trigrules` verbatim — only what a briefing-literate crew could plausibly expect), tactical
   relationship analysis (terrain masking, threat-to-route proximity). Every model-produced
   statement carries `epistemic_status` + `basis` + `confidence`, never silently upgraded to FACT.
   Only start once MI-3's schema has been exercised against at least one real mission and found
   basically right — the concept doc's own MI-3 milestone already assumes this ordering.

7. **MI-5 — Player questions (MVP: text console).**
   Deterministic-first ambiguity surfacing (concept doc's examples), player answers written back
   into `player_intent` as structured fields, not prose. Reuses BL-5a's precedent (typed
   console I/O first, answers persisted outside conversation history) rather than inventing a new
   interaction pattern. **This is the MVP mechanism, confirmed by the user (Decision 4, resolved
   below) — not a placeholder pending a UI decision.**

7a. **MI-5b — Player questions, web form (future, not this plan's Implementer scope).**
   User-confirmed direction: once MI-5's console mechanism proves out, replace the console loop's
   *input surface* with a simple web form asking the same structured questions — same
   `player_intent` schema and write-back target, only the I/O surface changes. Flagged here as a
   named future milestone so it doesn't get silently conflated with MI-5's own scope or with the
   separate briefing/debriefing capability below. No design work happens on this until MI-5 has
   run against a real mission.

   **Explicitly out of scope for this entire plan** (not MI-5, not MI-5b): a briefing/debriefing
   web page with text and images (maps, kneeboard images). The user raised this only as a
   "could be" aside, not a request — and it is a materially different capability (image/map
   rendering, not a Q&A form) from MI-5's player-intent clarification. Do not let a future MI-5b
   implementation grow into building this; it needs its own plan if/when the user asks for it.

8. **MI-6 — Runtime compilation.**
   Compile the full `MissionUnderstanding` into the compact runtime-facing subset
   `PETROBRAIN_SYSTEM.md`/`PETROBRAIN_RUNTIME.md` describe (`current_mission` shape) — this is the
   artifact BL-7 actually consumes, not the full Mission Understanding.

### Risks & Unknowns

- **`.miz`/mission-table schema is community-reverse-engineered, not ED-documented, and only one
  sample has been validated.** MI-0's real-bytes pass confirmed most secondhand findings and
  corrected several (mapResource path, DictKey scope, trigrules schema — see Context), but it is
  one file from one author on one terrain at mission-format `version` = 23. pydcs also has a known
  open issue where a DCS content patch broke its parsing assumptions. Format drift across DCS
  versions, and simple non-universality across authors/missions, are both real standing risks —
  same category as `world-model`'s own "DCS internals are incompletely documented and change over
  versions" rule. `route.points[]` field names and the `weather` sub-schema are **no longer open**
  (real-bytes-confirmed, see Context) — that specific sub-risk from the plan's earlier draft is
  resolved; the general "one sample only" risk above supersedes it.
- **`mission["trig"]` — a third trigger-adjacent table with unresolved runtime authority — is a new
  risk this MI-0 pass surfaced, not present in the plan before.** It holds generated Lua
  source-code strings that look like a compiled/flattened form of `trigrules`, cross-referencing
  the same predicates and DictKeys. No source (ED, Hoggit, pydcs) mentions it. Whether `trig` or
  `trigrules` is what DCS actually executes at runtime is unknown — if `trig` is authoritative and
  ever diverges from `trigrules` (e.g. an editor bug, a manually-edited mission file), MI-1.5's
  filter could reason correctly about `trigrules` while `trig` still encodes a leak of hidden-unit
  existence through generated text (radio calls, on-screen messages) that never gets checked.
  **Decision needed on how to carry this risk — see Decision 5.**
- **Author-only-knowledge filter completeness is not provably exhaustive.** `hidden*`/
  `lateActivation` cover the mechanisms found and now confirmed present in real bytes, but the
  schema is still reverse-engineered — a future DCS version, a different author's mission, or (per
  the `trig` risk above) a table this pass didn't fully resolve could leak author-only knowledge
  silently. Mitigate with an explicit test fixture that intentionally exercises every known
  author-only flag (including `hiddenOnMFD`, unconfirmed in the one real sample), and treat any
  *new* top-level `mission` key encountered during MI-1 parsing as "investigate before assuming
  it's safe to expose," not "pass through by default."
- **Vision-capable model need for briefing images/kneeboards** is out of scope through MI-4 (Stage
  2's "Possible Approaches" note: treat as opaque pass-through, not OCR/VLM). If a later milestone
  wants kneeboard text extracted, that's a new capability decision, not assumed here.
- **Schema churn.** `docs/concept/MISSION_INTERPRETER.md`'s own "Key dependency" section warns not
  to lock coordinate/provenance formats until World Model shows what's practical — World Model has
  now done that (M0-M8), but the *Mission Understanding* schema itself is still genuinely first-
  draft (MI-0). Expect BL-7 to need at least one schema revision once real body-layer consumption
  is attempted — this is why MI-3 deliberately ships an early, model-free schema instance rather
  than waiting for MI-4-6 to validate the shape.

### Second-order effect

A real, versioned Mission Understanding schema (even a model-free one from MI-3) unblocks BL-7
from indefinitely relying on a hand-written fixture, but it also puts schema-stability pressure on
this not-yet-implemented layer earlier than the concept doc originally assumed — BL-7's design
choices will start to depend on field names/shapes this plan freezes at MI-0/MI-3, so a schema
change after BL-7 lands is a two-subproject coordination cost, not a local one.

### Decisions Requiring User Input

Three of the original four decisions are resolved (1, 2, 4). **Decision 3 (MI-4's model choice)
remains open and gates only MI-4** — MI-0 through MI-3 (and MI-2's world-model HTTP prerequisite
sub-stage) are unblocked by it and can proceed first. MI-0's real-sample validation adds one new
resolved sub-decision (1a) and one new open question (5), assessed below as **not blocking for
MI-1/MI-1.5 Implementer sign-off** — see Decision 5's reasoning.

1. ~~New dependency: pydcs's `dcs.lua` parse/serialize subpackage (LGPL-3.0).~~ **Resolved:
   approved as-is.** Vendor or depend on pydcs's `dcs.lua` parse/serialize subpackage (not the
   full `pydcs` package) rather than hand-rolling a parser or pulling in a full Lua VM. No design
   change from the original recommendation.
1a. ~~Whether MI-1.5's filter should parse `trigrules` through pydcs's wrapper classes or its raw
   `predicate`-string form directly.~~ **Resolved by the architect from MI-0's real-bytes findings,
   no user input needed — this is a local, reversible implementation choice, not an architectural
   fork.** Parse the raw form directly: real bytes showed pydcs's `TriggerRule`/condition/action
   classes are a lossy abstraction over the actual schema for this specific need (a closed,
   greppable `predicate` vocabulary), so going through pydcs here would need translating back out
   of its wrapper only to re-derive what the raw tree already states plainly. Pydcs is still used
   for the general Lua-table parse (Decision 1, unchanged).
2. ~~World-model query transport: in-process import vs. HTTP.~~ **Resolved: HTTP.** The user chose
   the HTTP wrapper over mirroring body-layer's in-process-import exception — keeping that
   exception genuinely singular, per CLAUDE.md's own wording, rather than extending it to a second
   subproject pair. This is real new scope (world-model's first-ever HTTP server) and is now
   designed as part of this plan — see Affected Modules/Files above (`world-model/src/api/
   server.py`, `mission-interpreter/src/world_enrich/world_model_client.py`) and MI-2's
   prerequisite sub-stage in the Implementation Plan.
3. **Capable-model choice and hosting for MI-4 synthesis — still open, needs more investigation
   (user's own words).** `division-or-responsibility.md`'s compute-topology note (Mac/Ollama +
   Windows/DCS split, "model-swap only at briefing/on-ground") was written with the *runtime*
   model-swap constraint in mind; Mission Interpreter runs entirely pre-mission/offline, so that
   specific timing constraint doesn't bind here, but the model choice itself is still open: a
   local Ollama-hosted capable model on the Mac (cost: possibly weaker reasoning + no vision unless
   a vision-capable local model is chosen) vs. a cloud API model (cost: external dependency,
   ongoing API cost, sends mission content off-machine). This is a new dependency/architecture
   decision per AGENTS.md's escalation rules. Do not guess an answer here — MI-4 stays unstarted
   until this is resolved; MI-0 through MI-3 do not need it.
4. ~~Player-intent input form.~~ **Resolved: text console for MVP (MI-5, unchanged mechanism from
   this plan's original proposal), a simple web form later (MI-5b, new future milestone — see the
   Implementation Plan). Briefing/debriefing as a web page with text and images is explicitly out
   of scope for this entire plan** — a distinct future capability, not MI-5/MI-5b's job. See the
   Implementation Plan's MI-5/MI-5b/MI-6 entries for where each piece now lives.
5. **`mission["trig"]` vs. `trigrules` runtime authority — new question from MI-0's real-sample
   pass, assessed as not blocking, but the reasoning is stated here rather than silently dropped.**
   The architect's judgment: MI-1/MI-1.5 can proceed treating `trig` as an explicitly documented
   out-of-scope gap (parse and filter `trigrules` only; MI-1's raw dump still preserves `trig`
   verbatim, unfiltered, in the "raw data for research/debugging" tier `src/filter/` already
   defines — it simply never reaches the crew-available tree). Reasoning: `trig` looks
   structurally like a derived/compiled artifact of `trigrules` produced by the Mission Editor
   (same predicates, same DictKey cross-references, same argument shapes), not an independent
   authoring surface — the practical risk is divergence between the two for a hand-edited or
   malformed mission file, not `trig` being a routinely-used separate channel for author intent.
   Given that, and given MI-1.5's own filter is deny-by-default for anything not explicitly proven
   safe (per the Risks section's "investigate before assuming safe" rule), the residual exposure is
   bounded: `trig` never reaches the crew-available tree at all under this plan, so even an
   undetected divergence can leak a hidden unit's existence only if `trigrules`-driven filtering
   were itself wrong — a `trigrules` correctness bug, not a `trig`-specific gap. **This is not a
   permanent closure** — before MI-1.5 is treated as authoritative for a mission with real stakes
   (i.e. before this filter output is trusted for actual play, not just schema validation), get a
   dedicated investigator pass on `trig` (ED/Hoggit search for `mission.trig` specifically, plus
   cross-checking a second sample mission to see if `trig` and `trigrules` stay in lockstep). Flag
   this explicitly to the user: if they want stronger assurance now rather than after MI-1.5 ships,
   say so and this decision reopens as blocking.

### Note on planning depth

This plan spans a from-scratch subproject, an LLM-in-the-loop design (MI-4), and a
community-reverse-engineered file format with no official schema — architecturally complex,
high-uncertainty planning by this role's own criteria. It was produced at this role's default
(sonnet) depth; per this role's instructions, re-invoking Architect with an explicit opus model
override before MI-4's synthesis-stage design is finalized (not needed yet for MI-0-MI-3, which
are mostly deterministic parsing/schema work) would be a reasonable next step if the user wants
deeper scrutiny on the model-synthesis architecture specifically.
