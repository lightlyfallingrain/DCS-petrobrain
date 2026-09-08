### Goal

Build PB-1 ("text-only perception logger, no LLM": time, aircraft position, Petrovich
detections, bearing/range) by standing up the `body-layer` subproject's BL-0 (harness/replay)
and BL-1 (observation ingestion) slices, against a `PerceptionSource` abstraction that was built
tier-independent so a live-DCS spike could decide its concrete producer without a rewrite.
**Status update (2026-09-08):** the spike ran (Session 4 below) and resolved the question
differently than either originally-anticipated tier — the concrete producer is now a single
hybrid `PerceptionSource` (real HelperAI detection gate + `LoGetWorldObjects`-derived geometry
via a new association step), not a choice between "real feed" and "ground-truth proxy". See
Session 4 and the redesigned Affected Modules / Invariant Check / Implementation Plan below.

### Context this plan is built on

- Aircraft-layer telemetry (ownship kinematic state, `GET /telemetry/latest`) is done and
  merged (`51654ec`) — the BL-0 prerequisite that blocked the body-layer plan's drafting is
  resolved.
- Investigator ran two sessions this same day
  (`aircraft-layer/research/2026-09-07-petrovich-perception-export.md`), resolving PB-0's
  perception unknown enough to design against, though **neither session reached a live DCS
  instance** — both are desk research, Session 2 materially stronger than Session 1:
  - **Session 1**: `get_param_handle` is falsified for HelperAI's UI chain (primary source
    read of the actual cockpit Lua). Petrovich's UI instead declares named `controllers`
    (`middle_list_text`, `az_text`, `el_text`, `hdg_text`, `list_red_arrow`, …) architecturally
    matching what `list_indication`/`list_cockpit_params` are documented to query. **No
    `range_m` field exists anywhere in Petrovich's UI, in any tier** — range must always be
    derived externally regardless of which tier is used.
  - **Session 2**: found real, actively-maintained production code
    (`asherao/DCS-ExportScripts`, LGPL-3.0) whose `Mi-24P.lua` calls `list_indication(8)`
    directly from Export.lua for a *different* indicator (kneeboard chaff/flare counter, not
    HelperAI) on this exact aircraft. This **confirms `list_indication` is Export.lua-callable
    for the Mi-24P in general**, falsifying the earlier forum claim that dynamic reads need a
    Hook script — at least for some device IDs. It also gave the **exact wire format**: one raw
    string per call, repeating `-----...-----\n<Key>\n<Value>\n` blocks, one per currently-
    populated named controller — resolving "one blob vs. individually addressable" concretely
    (a parseable string, not a table). `LoGetWorldObjects`'s field list was cross-checked at
    moderate confidence (`ID`/`Name`/`Country`/`Coalition`/`LatLongAlt`/`Heading` — **no
    Pitch/Bank/Yaw for world objects**, only heading).
  - **What is still genuinely unknown, resolvable only by a live probe, not further desk
    research**: HelperAI's own numeric device ID (needed as `list_indication(n)`'s argument —
    not the same device as the kneeboard example); whether HelperAI is reachable the same way
    given it's registered as an "auxiliary sight" render target rather than an ordinary panel
    indicator; what `<Value>` actually contains for `middle_list_text`/`az_text`/etc.; whether
    target IDs persist frame-to-frame; `LoGetWorldObjects`'s coalition/visibility-scope
    semantics (one relevant forum thread still 403'd).
- `plans/body-layer/plan.md` (drafted 2026-09-07, not yet accepted — 6 open decisions in its
  §10) reconciles PB-1 = BL-1 and sketches the `observation:`/`contact:` schema. This plan makes
  BL-1 concrete and narrows §10 decision 6 (proceed synthetically vs. wait) with a third option:
  build the tier-independent scaffolding now, decide the concrete tier from one cheap live
  spike rather than from further argument.

**Why the plan sequences a spike before committing to a tier**: Session 2's finding
meaningfully lowered Tier 1's remaining risk (one unknown fact — the device ID — plus one
behavioral unknown, down from two open mechanism questions), which changes the economics: a
live probe is far cheaper than building Tier 3's full LOS/degradation heuristic, and if Tier 1
pans out it avoids that heavier build entirely. Neither tier should be locked in from a desk
chair when a cheap, decisive test is available first.

**Session 3 update (same day, user-supplied primary source)**: the previously-403'd forum thread
on `LoGetWorldObjects`'s coalition/visibility scope was pasted by the user and read in full. It
**confirms `LoGetWorldObjects` returns global, unfiltered multiplayer ground truth by default**
— no built-in own-aircraft/coalition filter; a caller must build one itself. This is no longer an
open risk, it's a confirmed design premise: Tier 3's detectability gate is not an optional
refinement, it is the *entire* mechanism standing between this data source and true omniscience.
Also newly noted: the same source reports this export can fail on some public multiplayer
servers (mechanism unconfirmed, no replies on the thread) — low risk for this project
(self-hosted DCS instance per the project's compute topology), but worth remembering if the
design is ever pointed at a third-party server.

**Session 4 — live spike executed, stage 1 complete (2026-09-08, user-run, 4 flights)**: see
`aircraft-layer/research/2026-09-08-pb1-live-spike-results.md` for the full record. Net result:
all four candidate numeric-geometry channels (`list_indication(2)` ASP-17 values,
`get_param_handle` on the sight's named params, `LoGetTargetInformation`,
`LoGetLockedTargetInformation`/`LoGetSightingSystemInfo`) are confirmed dead — nil, empty, or
stuck at zero, live, not just theoretically absent. `HELPERAI_DEVICE_ID` is confirmed `6`; its
`list_indication(6)` dump is confirmed live and working, but carries classification text only
(`middle_list_text`/`lower_list_text`/`lower_lower_list_text`, e.g. `"Ural truck"`) in a
**recursive** tree wire format (`-----...-----\n<name>\n<value-if-any>\nchildren are {...}`),
not the flat one-block-per-controller shape Session 2 anticipated — no numeric field anywhere.
This falsifies the plan's original two-tier framing (a real feed with real bearing vs. a pure
proxy): neither tier as originally conceived is buildable. **Reverse-engineering DCS's compiled
Petrovich-detection internals was explicitly considered and rejected as out of scope**
(user-directed, same session) — no sanctioned API surface, breaks the read-only-DCS invariant.
Stage 4 below is redesigned around the resulting hybrid: HelperAI's text as a real detection
gate, `geometry.py` + `LoGetWorldObjects` for all geometry, and a new association problem this
plan did not originally need to solve.

### Affected Modules / Files

- `aircraft-layer/dcs-export/Export.lua` — **status update**: the stage-1 spike's probe was
  disposable and ran from a separate, unmerged test `Export.lua`
  (`win-mac-sync/to-windows/Export.lua`) — none of it is in the canonical file yet. Two things
  now need to land in the canonical `Export.lua` for real, both minimal and read-only:
  1. **`LoGetWorldObjects` poll** — already built and merged (`08ba9c0`), unchanged by this
     redesign. Still the sole source of geometry for every detection, per the research note's
     "no tier ever gets geometry from Petrovich's own systems" conclusion.
  2. **NEW — permanent `list_indication(6)` (HelperAI) push**, promoted from the spike's
     disposable probe to a production feed pushed over the same socket as telemetry/world
     objects, at the confirmed working device ID (`6`). Pushes the raw recursive dump string
     (`-----...-----\n<name>\n<value-if-any>\nchildren are {...}`) as-is — Export.lua stays
     "deliberately dumb" (no Lua-side tree parsing) per this file's existing stdlib-only policy;
     parsing happens in `aircraft-layer/src/schema/`, mirroring how telemetry/world-object
     parsing is already split.
- `aircraft-layer/src/schema/` — **NEW** `petrovich_indication.py`, sibling to `world_objects.py`.
  Parses the recursive wire format confirmed in the spike into a flat `{leaf_name: text}` record
  (at minimum `middle_list_text`/`lower_list_text`/`lower_lower_list_text`) plus `t_sim`. Small,
  self-contained parser (recursive-descent over the `-----...-----` delimiter, not a copy of any
  reference implementation — same reimplement-not-adopt posture as decision 5 below covers the
  flat-format case, extended to the tree case now that the real shape is known).
- `aircraft-layer/src/` (Windows collector + LAN API) — two endpoints, same shape/lifecycle as
  `GET /telemetry/latest`:
  1. `GET /world_objects/latest` — already built and merged (`6cd5be6`), unchanged. Raw ground
     truth only: id, type/category string, coalition, position, heading (no pitch/bank/yaw —
     confirmed absent from `LoGetWorldObjects`). No detection/interpretation logic here — stays
     body-side per the aircraft-layer plan's decision 3.
  2. **NEW** `GET /petrovich_indication/latest` — raw parsed HelperAI text + `t_sim`, same
     "no interpretation here" posture as `/world_objects/latest`: this endpoint reports what
     Petrovich's UI currently shows, nothing more. Association against `LoGetWorldObjects` (below)
     is body-layer's job, not aircraft-layer's — consistent with the existing division-of-
     responsibility decision that all detection/interpretation logic lives body-side.
- `aircraft-layer/research/` — no new Investigator pass needed to *finalize this plan*; the one
  remaining piece of research (HelperAI device ID + live probe) is execution, not research, and
  is stage 1 of this plan, handed to the user per the project's standing rule that live full-DCS
  work is executed by the user, not run by an agent (see `WORKFLOW.md`-style deploy/run pattern
  already established for aircraft-layer). If the live probe surfaces a genuinely new unresolved
  DCS-internals question (e.g. HelperAI behaves unlike the kneeboard example in some
  unanticipated way), that is the trigger for a fresh Investigator pass — not before.
- **New subproject `body-layer/`** (first code in it — see Decisions Requiring User Input #1).
  - `body-layer/src/perception/source.py` — `PerceptionSource` protocol/ABC:
    `poll(now_sim, ownship_state) -> list[Observation]`. Built first, before either concrete
    tier, so stage 1's spike result is a config choice, not a rewrite trigger.
  - `body-layer/src/perception/geometry.py` — bearing/range/LOS-terrain-masking helpers, calling
    `world-model/src/query` (in-process import, per the body-layer plan's seam decision) for
    elevation/terrain data. **Shared by every tier** — confirmed by both investigator sessions
    that no tier has a native range field, so this helper is load-bearing regardless of which
    concrete `PerceptionSource` gets built.
  - `body-layer/src/perception/association.py` — **NEW.** Pure, fixture-testable logic with no
    network I/O: given a parsed HelperAI indication record, `OwnshipState`, and a
    `WorldObjectsSnapshot`, selects which world object (if any) the indication refers to. See
    "Association design" below Implementation Plan for the algorithm. Kept separate from the
    `PerceptionSource` implementation itself (same reasoning as `geometry.py` being separate from
    a concrete source) so the decision logic is testable against recorded fixtures without a live
    aircraft-layer connection — same BL-0 replay-determinism requirement `geometry.py`'s tests
    already follow.
  - `body-layer/src/perception/hybrid_source.py` — **NEW, replaces the planned
    `petrovich_feed.py`/`proxy.py` split with a single concrete implementation** — see the
    "Single implementation, not two" note after the Implementation Plan for why a hybrid is one
    class, not a third tier alongside two dead ones.
    `HybridPerceptionSource`: polls both new aircraft-layer endpoints
    (`GET /petrovich_indication/latest`, `GET /world_objects/latest`) each tick, debounces on
    indication-text change (only a *new* or *changed* detection produces an `Observation` — see
    Implementation Plan), calls `association.py` to resolve a candidate, then `geometry.py` for
    bearing/range/LOS against whichever candidate (or best-guess candidate) it resolved. This is
    now the **only** concrete `PerceptionSource` this plan builds — there is no second tier to
    branch on, since the "real feed with real bearing" and "pure ground-truth proxy" tiers the
    original design branched between both turned out to be unbuildable in their original forms
    (see Session 4 above). `source: petrovich_detection_associated` on the emitted `Observation`
    (a new value in the still-open `source: str` field, per `source.py`'s docstring on why that
    field stays a plain string rather than a closed enum for now).
  - `body-layer/src/logger.py` — the actual PB-1 deliverable: polls ownship telemetry +
    `PerceptionSource.poll()` on a fixed tick, prints/logs each observation as flat text
    (`t_sim, aircraft position, classification, bearing_deg, range_m`). No contact memory, no
    *multi-frame* association across observations, no LLM — that's BL-2/PB-2. (Note the
    terminology split: `association.py` above resolves a *single* detection to a *single* world
    object within one poll; BL-2's "data association" is the separate, harder problem of linking
    observations to persistent contacts *over time* — the two are not the same mechanism and
    should not be merged even though both are called "association".) `logger.py` is written
    against the `PerceptionSource` interface, so it does not know or care which concrete
    implementation is behind it.
  - `body-layer/src/aircraft_client.py` — add `get_petrovich_indication()`, mirroring the
    existing `get_world_objects()`/`get_telemetry()` methods, for the new
    `GET /petrovich_indication/latest` endpoint.
  - `body-layer/tests/fixtures/` — recorded `(telemetry, world_objects, petrovich_indication)`
    frame triples for the BL-0 replay harness and for `association.py`'s unit tests — the latter
    specifically need multi-candidate scenes (2+ same-type objects near ownship) to exercise the
    ambiguous-match path, not just single-target scenes.
  - `body-layer/src/replay.py` — minimal BL-0 replay harness feeding fixture frames through the
    same `PerceptionSource` interface the live logger uses.
  - `body-layer/pyproject.toml`, `body-layer/CLAUDE.md` — mirror `aircraft-layer/`'s conventions
    (ruff/mypy --strict/pytest, stdlib-only-by-policy), per the project's per-subproject
    CLAUDE.md pattern.
- `docs/concept/PETROBRAIN_RUNTIME.md` — update the "Perception adapter" section's status once
  the hybrid source ships: real HelperAI detection gate + geometry-derived position via
  world-object association, and why (no channel ever exposed native geometry — see Session 4).
- `plans/body-layer/plan.md` — leave as-is; this plan supersedes its BL-1 sketch with a concrete
  design but does not change BL-2+ or its other open decisions, except narrowing §10 item 6 as
  noted above.

### Invariant Check

- **DCS authoritative, code owns facts:** satisfied — the hybrid source reads DCS state
  read-only via the aircraft-layer I/O boundary only; no model is involved anywhere in PB-1.
- **Petrovich must not be omniscient:** both tier-specific paragraphs this bullet originally
  carried no longer apply as written — neither the "real feed" tier nor the "pure proxy" tier
  exists anymore (Session 4). The hybrid design splits the invariant's defense across two
  mechanisms with genuinely different jobs and different risk profiles:
  - **Existence of a detection is real, not synthetic — this is the invariant's primary
    defense, and it is now structurally stronger than either original tier would have been.**
    `HybridPerceptionSource` never emits an `Observation` unless HelperAI's own live UI actually
    populated a classification field — Petrovich's AI decided something was there, not a
    heuristic standing in for that decision. There is no detectability/LOS gate to build or
    validate for the "did Petrovich notice this at all" question, because the answer comes
    straight from DCS's own (compiled, unreachable, and per Session 4's scope decision
    deliberately *not* reverse-engineered) detection logic. This is a better structural fit for
    the invariant than Tier 3's synthetic gate would have been, and removes an entire class of
    threshold-tuning risk the original plan carried for that tier.
  - **Which world object the detection refers to, and its geometry, is not real — this is where
    a Tier-3-style plausibility heuristic re-enters, but scoped narrowly as a *disambiguator*,
    not a *gate*.** `association.py` restricts the `LoGetWorldObjects` candidate pool by a
    forward-hemisphere-from-ownship-heading filter and a range cap (both heuristic, tunable, see
    Risks below) before matching on classification-text keywords — the same kind of
    plausibility reasoning Tier 3's detectability gate would have done, just applied *after* a
    real detection event has already gated existence, not instead of one. The stakes are lower
    than Tier 3's would have been: picking the wrong nearby truck among several identical ones is
    an association error (wrong position attributed to a real, correctly-gated detection), not an
    omniscience leak (Petrovich still only "detected" one real thing DCS itself flagged).
  - **Residual risk carried forward from the original Tier 1 concern**: over-trusting
    `middle_list_text`'s precision. Confirmed live as a coarse category string ("Ural truck"),
    not an exact DCS unit type — the concern from the original plan is resolved, not just
    deferred, since this is now observed fact rather than an assumption pending a live read.
  - **New residual risk this hybrid introduces**: if `association.py`'s candidate pool is drawn
    too loosely (e.g. range cap too generous), a wrong-but-plausible match could attribute a real
    detection to the wrong object's `Coalition`/`Country` — e.g. reporting a friendly vehicle's
    position under a detection that was actually of a hostile one nearby. This is a correctness
    risk, not an omniscience one (no ground truth reaches the player that DCS didn't already
    flag as detected), but it is exactly the kind of silent-wrong-answer failure mode the body
    layer plan's §2 "prefer a new contact over a bad merge" heuristic exists to avoid one layer
    up — `association.py`'s ambiguous-match handling (see Implementation Plan) is this plan's
    analogous guard at the single-detection level.
- **Read-only DCS:** satisfied — `list_indication(6)` and `LoGetWorldObjects` are both read
  calls, no install-tree edits.
- **Provenance/uncertainty/timestamps:** satisfied by the `Observation` schema, unchanged by the
  redesign — `source: petrovich_detection_associated`, a `provenance` string distinguishing
  unique from ambiguous association (see Implementation Plan), `t_sim`/`t_wall`, and
  `derived_world_position.confidence` carrying the association's confidence — already specified
  in `plans/body-layer/plan.md` §5; this plan fills in the concrete hybrid producer.
- **World Model authoritative for terrain, DCS/OSM boundary:** satisfied — `geometry.py` calls
  `world-model/src/query`, doesn't reimplement terrain logic.
- **`world-model/data/` gitignore boundary:** `body-layer/tests/fixtures/` is new persisted data
  outside that path — needs its own gitignore treatment (see Decisions below).
- **Licensing:** reference-only reuse of `asherao/DCS-ExportScripts`' (LGPL-3.0) wire-format
  parsing *pattern*, reimplemented rather than copied, keeps `aircraft-layer`'s existing
  stdlib-only/"deliberately dumb" Export.lua policy intact and avoids the `dofile()`-linking
  ambiguity investigator flagged. Recommended, not yet a settled decision (see below).

### Single implementation, not two

The original plan branched stage 4 into two mutually-exclusive concrete `PerceptionSource`
implementations because it expected the spike to resolve a yes/no question ("does a real feed
exist"). Session 4 resolved a different question instead: *no* channel gives real geometry, but
*one* channel gives a real detection signal. There is no branch left to take — both of the
original tiers are gone, and what replaces them is one implementation
(`HybridPerceptionSource`) that always does the same thing: gate on a real HelperAI detection,
resolve it against `LoGetWorldObjects` via `association.py`, derive geometry via `geometry.py`.
Keeping this as a single class (rather than, say, a third "Tier 2" alongside two dead ones) is a
direct consequence of there no longer being a decision to defer — the `PerceptionSource`
protocol's job (letting `logger.py` not care which producer is behind it) is unaffected either
way, which is exactly why stage 6 below no longer needs a second implementation to prove that.

### Association design

`association.py`'s `associate(indication, ownship, world_objects) -> AssociationResult` runs
each time `HybridPerceptionSource` sees a new-or-changed HelperAI detection:

1. **Candidate pool.** Start from every `WorldObjectSample` in the current `world_objects`
   snapshot (no coalition/IFF filtering — see Risks below).
2. **Plausibility filter (heuristic, tunable constants).** Drop candidates outside a range cap
   from ownship (starting constant: 5000 m — roughly a generous optical-detection envelope for a
   ground vehicle from a helicopter, not derived from any DCS data since no sensor-range figure
   exists for Petrovich) and outside a forward-hemisphere bearing window from ownship heading
   (starting constant: ±90°). This is deliberately *not* a claim about where the ASP-17 sight is
   pointed — that signal is confirmed dead (Session 4 finding 3/4) — it is a plausibility filter
   on where a human-crewed optical detection could plausibly have come from, the same class of
   reasoning Tier 3's original detectability gate would have applied, just scoped to
   disambiguation rather than to gating existence (see Invariant Check).
3. **Type-match scoring.** Score remaining candidates on keyword overlap between
   `middle_list_text` (e.g. `"Ural truck"`) and the candidate's `Name` field. Exact mapping
   between HelperAI's coarse category words and `LoGetWorldObjects`' `Name` strings (DCS unit
   type identifiers) is **not yet known** — Session 4 never tested this cross-reference, since
   the spike's manually-placed targets were single instances with nothing to disambiguate
   against. Build the matcher with the sample data that exists, but do not treat its coverage as
   validated until checked against a live multi-object scene (see Risks below).
4. **Decision:**
   - **Zero candidates survive** steps 2–3: **drop the detection, emit no `Observation`.**
     `bearing_deg`/`range_m` are non-optional on `Observation` (`source.py`) — there is no
     geometry to report for an unresolved detection, and fabricating placeholder geometry to
     satisfy the schema would be worse than silence. Log the drop (count/rate, not per-instance
     noise) as a coverage-gap signal for tuning the filters or the type-match table.
   - **Exactly one candidate survives, or one is unambiguously top-scored** (score margin above
     a threshold over the next candidate): emit an `Observation` with `derived_world_position`
     computed from that candidate's position, confidence in the upper range (starting constant:
     0.6 — same order as the body-layer plan's own example confidences, not a claim of
     precision), `method: "bearing_range_terrain"`.
   - **Two or more candidates remain within the score margin of each other (ambiguous):**
     still emit an `Observation` — `Observation`'s schema has no "detection happened, position
     unknown" representation without extending `source.py` (out of scope here, see Decisions) —
     but built from the *nearest* surviving candidate, with `derived_world_position.confidence`
     deliberately low (starting constant: 0.25) and `method:
     "bearing_range_terrain_ambiguous_association"`. This is the closest approximation to "a
     lower-confidence/unresolved observation rather than a guess" achievable without a schema
     change: the position is a guess, but it is *marked* as one, machine-readably, not asserted
     at the same confidence as a clean match. Flag to user (Decisions below): confirm this
     compromise is acceptable, or treat a future nullable-geometry `Observation` as a fast-follow.

All three outcomes are driven by pure, fixture-testable logic in `association.py` — no network
calls, no world-model queries beyond what `geometry.py` already needs for the position itself.

### Implementation Plan

Stages 1–3 are **done** (Session 4's live spike, and the `body-layer`/`world_objects` scaffolding
already merged per this branch's git history — `08ba9c0`, `6cd5be6`). Remaining work:

1. ~~Live spike~~ — **complete**, see Session 4 above and the research note.
2. ~~BL-0 slice: harness + tier-independent scaffolding~~ — **complete**
   (`source.py`, `geometry.py`, `aircraft_client.py`, `replay.py` merged).
3. ~~Aircraft-layer: world-objects endpoint~~ — **complete** (`GET /world_objects/latest`
   merged, `6cd5be6`).
4. **Aircraft-layer: promote the HelperAI probe to a permanent feed.**
   - Add the confirmed device-6 `list_indication` push to the canonical
     `aircraft-layer/dcs-export/Export.lua` (raw recursive string, no Lua-side parsing).
   - `aircraft-layer/src/schema/petrovich_indication.py`: parse the recursive wire format into
     the flat leaf-name record.
   - Collector cache + `GET /petrovich_indication/latest`, mirroring `/world_objects/latest`.
5. **Body-layer: `association.py`.** Implement the algorithm above against fixtures first —
   at minimum one clean single-candidate fixture and one ambiguous multi-candidate fixture (per
   the updated fixtures bullet in Affected Modules), before any live wiring. This is the piece
   most worth getting right in isolation, since `HybridPerceptionSource` itself is thin
   composition once this exists.
6. **Body-layer: `HybridPerceptionSource`.** Wire `aircraft_client.get_petrovich_indication()` +
   `get_world_objects()` + `association.py` + `geometry.py` together, with the change-debounce
   logic (emit only on a new-or-changed `middle_list_text`, not every poll tick while a detection
   persists — exact debounce window is an implementation detail, not an architectural one, but
   note it in code since an unbounced feed would spam `logger.py`'s flat-text output).
7. **Text-only logger (the actual PB-1 deliverable).** Wire `logger.py` against
   `HybridPerceptionSource`: poll loop, ownship state + `PerceptionSource.poll()`, flat-text
   output matching the runtime doc's PB-1 spec. Run against the replay harness first, then one
   live short Mi-24P sortie with a visible manually-placed target as the acceptance check —
   ideally with a second, similar decoy target nearby to exercise the ambiguous-match path live,
   not just in fixtures.
8. **Interface conformance check.** `test_logger.py`'s existing fake-`PerceptionSource` test
   already demonstrates `logger.py` doesn't know or care about the concrete implementation
   behind it — no separate "second tier" smoke test is needed now that there is only one
   concrete implementation to prove interchangeable (see "Single implementation, not two"
   above). Confirm that test still passes unmodified; that is sufficient evidence.
9. **Docs.** Update `PETROBRAIN_RUNTIME.md`'s "Perception adapter" section with the actual
   shipped design: real HelperAI detection gate, `LoGetWorldObjects`-derived geometry via
   `association.py`, and why no tier ever got native geometry (Session 4).

### Risks & Unknowns

- **Type-match vocabulary is unvalidated.** `association.py`'s keyword match between
  `middle_list_text` (`"Ural truck"`) and `LoGetWorldObjects`' `Name` field is built from a
  single-instance spike (one target type at a time, nothing to disambiguate against) — the
  mapping between Petrovich's coarse category words and DCS's unit-type identifiers for other
  vehicle classes is unverified. Treat the initial mapping as a starting guess, not a validated
  table; expect it to need real multi-object-scene testing to trust.
- **Plausibility-filter thresholds (range cap, forward-hemisphere window, ambiguity-margin) are
  arbitrary starting constants**, same class of risk as the original plan's Tier 3
  threshold-tuning risk (World Model's M6 ridge/valley classifier hit this too) — no ground
  truth to validate against beyond plausibility until real multi-target sessions accumulate.
  Carry the constants as named, tunable values, not inline literals.
- **No coalition/IFF filtering in the candidate pool** — `association.py` as designed does not
  restrict candidates by `Coalition`/`Country`, matching purely on type + geometry. A friendly
  and hostile vehicle of a visually similar type near each other could be confused. Not addressed
  in this plan; flag as a known gap, worth revisiting once real multi-unit scenes are tested
  (`LoGetWorldObjects` coalition scope is confirmed unfiltered/global per Session 3, so the data
  needed to add this filter later already exists).
- **Debounce/re-emission tuning is unspecified** — exactly when `HybridPerceptionSource` treats a
  persisting HelperAI detection as "new" (immediate text change only, vs. also a periodic
  keep-alive while continuously populated) is left as an implementation choice, not fixed here.
  Wrong tuning risks either spamming `logger.py`'s output or letting a genuinely persistent
  detection go unlogged for too long.
- **`LoGetWorldObjects` coalition/visibility scope is confirmed unfiltered/global** (Session 3) —
  no longer a Tier-3-specific risk, but still worth restating: `association.py`'s candidate pool
  is drawn from an intentionally-unfiltered global feed, which is exactly why the
  forward-hemisphere/range plausibility filter (not coalition filtering, see above) is the only
  thing narrowing it before a match is attempted.
- **Export may fail on some public multiplayer servers** (Session 3, mechanism unconfirmed) —
  low risk given this project's self-hosted DCS instance, but would need re-checking if the
  aircraft layer is ever pointed at a third-party server.
- **No Pitch/Bank/Yaw for world objects** (only Heading) — minor, non-blocking constraint on
  `association.py`'s scoring (heading could in principle help score a moving-target match, but
  isn't required for the v1 design above).
- **Fixture provenance**: any fixtures captured from a real Windows-box session contain real (if
  trivial) mission data — treat like `world-model/data/`-class captures for gitignore purposes.
  The new multi-candidate association fixtures are especially likely to be hand-authored rather
  than captured live, since a live multi-object ambiguous scene is harder to stage deliberately.
- **Heading reference (true vs. magnetic)** is an explicitly deferred project decision
  (`division-or-responsibility.md`) but `bearing_deg` is meaningless without picking one — this
  plan cannot defer it further (already resolved, see Decisions item 2 below).

### Decisions (resolved 2026-09-07)

1. **`body-layer/` created now** as a real sibling subproject to `aircraft-layer`/`world-model`.
2. **Bearing reference: true heading**, for `bearing_deg` throughout the `Observation`/`contact`
   schema — record this once in `plans/body-layer/plan.md` §5.
3. **Where body-layer runs: any LAN box, OS-agnostic, not necessarily the DCS box** — it always
   talks to the aircraft-layer's `GET /telemetry/latest`/`GET /world_objects/latest` over the LAN
   HTTP API (never in-process). **World Model stays in-process with body-layer** (this is
   unchanged from `plans/body-layer/plan.md`'s existing seam decision, not a network service): the
   *runtime query instance* of world-model runs on whichever box body-layer runs on. If that box
   differs from the one world-model was **built** on, the user is responsible for copying the
   built `.sqlite` file(s) over manually before running body-layer — this is a manual step, not a
   new sync mechanism to build.
4. **Fixtures: commit small fixtures** in `body-layer/tests/fixtures/` (no gitignore boundary,
   unlike `world-model/data/`) — keep them small/trivial as already planned.
5. **Licensing: reimplement the small wire-format-parsing pattern now** (not the full LGPL-3.0
   framework); revisit adopting the framework later only if a concrete need (e.g. its 1000+
   device-arg tables) makes it worth it. Can change from reimplement to adopt later without
   redesign — the `PerceptionSource` interface boundary already isolates this choice.
6. **Live spike (stage 1) runs in parallel with BL-0/BL-3 scaffolding (stages 2-3), not
   blocking them.** User runs it on the Windows box whenever convenient; stage 4's tier branch
   waits on its result, stages 2-3 do not. *(Superseded 2026-09-08: the spike is complete, see
   Session 4 above — "stage 4's tier branch" no longer exists in its original form, replaced by
   the hybrid design's stages 4-9.)*

### Decisions Requiring User Input (new, 2026-09-08)

1. **Ambiguous-association compromise (see "Association design" above).** An ambiguous
   detection still emits an `Observation` built from the nearest candidate at low confidence,
   because `bearing_deg`/`range_m` are non-optional on the current `Observation` schema and a
   true "detection happened, position unknown" representation would need a `source.py` change —
   explicitly out of scope for this redesign per the task framing. Confirm this compromise
   (low-confidence best-guess, machine-readably flagged) is acceptable, versus preferring a
   `source.py` extension (nullable `bearing_deg`/`range_m`, or an explicit
   `unresolved: bool` flag) as a near-term fast-follow once a live ambiguous scene is actually
   tested and this is felt to matter in practice.
2. **No coalition/IFF filtering in `association.py`'s candidate pool (Risks above).** Confirm
   this is acceptable for PB-1's scope (a text-only logger, no contact memory yet) or whether it
   should be added now given `LoGetWorldObjects`' coalition field is already available and cheap
   to filter on.
3. **New permanent aircraft-layer surface.** The original plan treated the HelperAI probe as
   disposable/spike-only; this redesign promotes it to a permanent production endpoint
   (`GET /petrovich_indication/latest`) alongside `/world_objects/latest`. This is materially new
   aircraft-layer scope beyond what `aircraft-layer/CLAUDE.md` currently documents — confirm this
   is the intended shape before stage 4 is implemented, rather than, say, folding the raw
   indication text into the existing `/world_objects/latest` response.
