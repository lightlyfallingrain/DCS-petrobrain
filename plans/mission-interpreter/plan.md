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
- Investigator resolved `.miz` internal structure this session (no prior research existed in this
  repo) — `mission-interpreter/research/miz_file_structure.md`. Load-bearing findings:
  - `.miz` is a zip: `mission`, `options`, `warehouses`, `l10n/DEFAULT/dictionary`, `mapResource`,
    optional `KNEEBOARD/<aircraft>/IMAGES/*` (real embedded image files).
  - Briefing/task text is **externalized**: `mission["descriptionText"]` /
    `descriptionBlueTask`/`descriptionRedTask`/`sortie` hold `DictKey_...` IDs resolved against
    `l10n/DEFAULT/dictionary`, not inline text.
  - Author-only knowledge has **real structural markers**, not just heuristics: `Group.hidden` /
    `hiddenOnPlanner` / `hiddenOnMFD`, and `MovingGroup.lateActivation` + `start_time` (the
    mechanism behind "hidden ambush" groups — they don't exist in the world until a trigger
    activates them).
  - Two distinct trigger structures: `triggers` (zone geometry) vs. `trigrules` (condition→action
    rules — where scripted spawns/ambushes are wired up).
  - Prior art: `pydcs` (dcs-liberation/pydcs, LGPL-3.0) is the de facto standard — a hand-written
    recursive-descent Lua-table parser (`dcs/lua/parse.py`/`serialize.py`), no embedded Lua VM,
    no `lupa`/`slpp`. `dcs-liberation` itself is built on pydcs rather than reimplementing.
  - **Unresolved, carried as risk**: no official ED schema exists anywhere — the whole `mission`
    table shape is community-reverse-engineered (pydcs has an open issue where a DCS content
    update broke its parsing assumptions). Exact `route.points[]` field names and `weather`
    sub-schema were summarized secondhand, not source-quoted. Nothing has been validated against
    real bytes — **no `.miz` file exists anywhere in this repo**.

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
    vendored Lua parser, DictKey resolution. Output: an inspectable intermediate dataclass tree
    (theatre, date, weather, groups/units, routes, triggers/trigrules, briefing text, kneeboard
    image refs) — this is deliberately a *typed mirror of the raw mission file*, not yet filtered
    or interpreted. No model involved at this stage — deterministic parser only, per "code owns
    truth."
  - `src/filter/` — the author-only-knowledge boundary (concept doc's central invariant). Takes
    the raw parsed tree and produces a "crew-available" subset: drops `hidden`/`hiddenOnPlanner`/
    `hiddenOnMFD` groups and `lateActivation` groups entirely from what reaches the schema below
    (their existence is not crew knowledge — a `lateActivation` group may still inform *derived*
    threat expectations from `trigrules`/briefing text, but never as "this exact unit is here");
    keeps `trigrules` only as raw data for research/debugging, never surfaced in Mission
    Understanding. This module is the concrete mechanism the concept doc only names in principle
    — see "Decisions Requiring User Input" for what's still open about it.
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
- `world-model/` — no code change expected at Stage 1-2. If Decision 2 resolves toward an HTTP
  boundary, a small `src/api/` read-only HTTP wrapper around `query.describe`/`query.search` would
  be new scope there, out of this plan (flag to the user, don't silently add it here).
- `body-layer/ROADMAP.md` — update BL-7's entry once this subproject exists, noting it's
  available (not requiring BL-7 to still wait on a fixture) — a bookkeeping change for later, not
  part of this plan's own commits.
- Root `ROADMAP.md` — add Mission Interpreter's status row once MI-0/MI-1 land.

### Implementation Plan

1. **MI-0 — Get a real `.miz` and lock the schema shape.**
   Cannot proceed past this stage without a real sample mission file — flagged as a blocking
   prerequisite, see Decisions below. Once obtained: `unzip -l`/`unzip -p` it directly, confirm
   the investigator's findings against real bytes (top-level listing, DictKey round-trip,
   `lateActivation`/`hidden` fields, `route.points[]` field names, `weather` sub-schema). Update
   `research/2026-09-12-miz-file-structure.md` findings from "reproduced-locally-equivalent" to
   genuinely reproduced, or correct them. Freeze a first-draft `MissionUnderstanding` schema
   (dataclasses, not YAML-only) informed by real data instead of the concept doc's example.

2. **MI-1 — Structured `.miz` parser (minimal working version).**
   `src/miz/` reads the zip, parses `mission` + `l10n/DEFAULT/dictionary` via the vendored Lua
   parser, resolves DictKeys, and produces the raw typed intermediate tree. Scope: theatre,
   date/weather, ownship group/route, briefing text, kneeboard image refs (pass through as opaque
   bytes/paths, no OCR/VLM). Explicitly out of scope this stage: `trigrules` action-type
   enumeration (open per investigator), full unit/weapon taxonomy (no pydcs country/weapon
   catalogs). Inspectable JSON/YAML dump for manual review, matching the concept doc's MI-1 scope
   and this project's "prefer inspectable intermediate representations" invariant.

3. **MI-1.5 — Author-only-knowledge filter (validate correctness, before enrichment).**
   `src/filter/` implementation + tests proving `hidden*`/`lateActivation` groups never appear in
   the crew-available tree, using MI-0's real mission file as the primary fixture (add a
   deliberately-hidden/late-activated group to it if the sample doesn't already have one). This is
   pulled forward ahead of world-enrichment and model synthesis because it is the plan's central
   invariant (per CLAUDE.md's "must filter out mission-author-only knowledge before it reaches the
   crew layer") and is cheap to get wrong silently if built last, under schedule pressure, as an
   afterthought bolted onto a later stage.

4. **MI-2 — World enrichment.**
   `src/world_enrich/` resolves route/objective/group DCS x/z coordinates against World Model
   (`describe_position` for "what's near this waypoint", `find_place_by_name` for named
   objectives/briefing place mentions). Transport per Decision 2. Output: the raw tree gains
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

7. **MI-5 — Player questions.**
   Deterministic-first ambiguity surfacing (concept doc's examples), player answers written back
   into `player_intent` as structured fields, not prose. Reuses BL-5a's precedent (typed
   console I/O first, answers persisted outside conversation history) rather than inventing a new
   interaction pattern.

8. **MI-6 — Runtime compilation.**
   Compile the full `MissionUnderstanding` into the compact runtime-facing subset
   `PETROBRAIN_SYSTEM.md`/`PETROBRAIN_RUNTIME.md` describe (`current_mission` shape) — this is the
   artifact BL-7 actually consumes, not the full Mission Understanding.

### Risks & Unknowns

- **No `.miz` sample exists anywhere in this repo or reachable from this Mac dev session** —
  MI-0/MI-1 are blocked without one. This is the same class of gap as `body-layer/ROADMAP.md`'s
  F10-menu backlog item ("blocked on DCS access"), but resolvable more cheaply: any existing
  Petrobrain test mission, or a trivially hand-built one, would unblock it — doesn't need a live
  DCS session, just DCS/Mission Editor access once, on the Windows box, to export one `.miz`.
- **`.miz`/mission-table schema is entirely community-reverse-engineered, not ED-documented.**
  pydcs has a known open issue where a DCS content patch broke its parsing assumptions. Format
  drift across DCS versions is a real, standing risk to any parser built here — same category as
  `world-model`'s own "DCS internals are incompletely documented and change over versions" rule,
  not a one-time gap to close and forget.
  - `route.points[]` exact field names and `weather` sub-schema were sourced secondhand
    (Hoggit prose / summarized fetches), not directly source-quoted from pydcs — verify against
    `dcs/point.py`/`dcs/weather.py` directly before MI-1's implementer writes route/weather
    parsing code.
  - Whether `trigrules` action types form a closed, greppable set (needed to reliably keep
    scripted-ambush data out of the crew-available tree) is unverified — worth a direct read of
    `dcs/action.py`/`dcs/condition.py` before MI-1.5 is implemented, not assumed.
- **Author-only-knowledge filter completeness is not provably exhaustive.** `hidden*`/
  `lateActivation` cover the mechanisms found so far, but the investigator's own findings flag
  that the schema is reverse-engineered — a future DCS version or an author-only field this
  session didn't find could leak through silently. Mitigate with an explicit test fixture that
  intentionally exercises every known author-only flag, and treat any *new* top-level `mission`
  key encountered during MI-1 parsing as "investigate before assuming it's safe to expose,"
  not "pass through by default."
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

1. **New dependency: pydcs's `dcs.lua` parse/serialize subpackage (LGPL-3.0).** Investigator's
   recommendation is to vendor or depend on this rather than hand-roll a regex parser or pull in a
   full Lua VM (`lupa`) — the format has real nested-table/comment/numeric-edge-case handling
   pydcs already solved against years of real ED mission files. This is a genuine new third-party
   dependency for a from-scratch subproject (AGENTS.md escalation rule: "a new dependency seems
   necessary" → stop and ask), and an LGPL-3.0 license implication worth the user's explicit
   sign-off before Implementer starts. Alternative considered and not recommended: hand-rolled
   parser (more maintenance, no benefit over a proven implementation) or a full Lua VM (unneeded
   weight for a format that isn't executing Lua logic, only reading a data literal).
2. **World-model query transport: in-process import (body-layer's precedent) vs. HTTP.** Root
   `CLAUDE.md`'s module-independence rule defaults to HTTP/JSON across a subproject boundary,
   naming body-layer↔world-model's in-process import as "the sole exception... do not introduce a
   similar in-process cross-subproject import elsewhere without the same explicit justification."
   Mission Interpreter runs offline/pre-mission (no live-DCS latency pressure, unlike body-layer),
   which weakens the "same box, tight coupling" argument that justified body-layer's exception —
   but building a new HTTP server for world-model's currently-in-process-only `query` API is new
   scope not otherwise needed yet, and world-model has no such server today. Two reasonable
   approaches, CLAUDE.md's stated default doesn't cleanly resolve which one applies to a batch
   offline consumer: (a) in-process import mirroring body-layer, justified the same way ("same Mac
   box always, at least for now"); (b) a small read-only HTTP wrapper around `query.describe`/
   `query.search`, keeping the exception genuinely singular as CLAUDE.md's wording implies it
   should stay. Recommend (a) for cost reasons but this is the user's call, not a local/reversible
   detail.
3. **Capable-model choice and hosting for MI-4 synthesis.** `division-or-responsibility.md`'s
   compute-topology note (Mac/Ollama + Windows/DCS split, "model-swap only at briefing/on-ground")
   was written with the *runtime* model-swap constraint in mind; Mission Interpreter runs entirely
   pre-mission/offline, so that specific timing constraint doesn't bind here, but the model choice
   itself is still open: a local Ollama-hosted capable model on the Mac (cost: possibly weaker
   reasoning + no vision unless a vision-capable local model is chosen) vs. a cloud API model (cost:
   external dependency, ongoing API cost, sends mission content off-machine). This is a new
   dependency / architecture decision per AGENTS.md's escalation rules, gates MI-4 specifically —
   MI-0 through MI-3 don't need it and can proceed first.
4. **Player-intent input form.** Concept doc says "the player may need to clarify intent the
   mission file cannot know" but doesn't fix a UI. Proposed default (not escalated — mirrors
   BL-5a's already-accepted pattern of typed console I/O before voice): a pre-flight text console
   prompt/response loop, answers persisted as structured `player_intent` fields, run once per
   mission before MI-6's runtime compilation. Flagging here so the user can object before MI-5 is
   built, but this one is treated as local/reversible per AGENTS.md's autonomy criterion unless
   told otherwise.

### Note on planning depth

This plan spans a from-scratch subproject, an LLM-in-the-loop design (MI-4), and a
community-reverse-engineered file format with no official schema — architecturally complex,
high-uncertainty planning by this role's own criteria. It was produced at this role's default
(sonnet) depth; per this role's instructions, re-invoking Architect with an explicit opus model
override before MI-4's synthesis-stage design is finalized (not needed yet for MI-0-MI-3, which
are mostly deterministic parsing/schema work) would be a reasonable next step if the user wants
deeper scrutiny on the model-synthesis architecture specifically.
