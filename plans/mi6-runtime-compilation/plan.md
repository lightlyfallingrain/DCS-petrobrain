### Goal

Compile MI-3/MI-4/MI-5's full `MissionUnderstanding` into a small, runtime-facing
`RuntimeMissionUnderstanding` (the concept docs' `current_mission` block) via a pure, deterministic
mapping — the artifact a future BL-7 will consume, produced and tested standalone since BL-7 itself
does not exist yet.

### Context this plan rests on

- **The concrete `current_mission` shape lives in `docs/concept/MISSION_INTERPRETER.md` (lines
  318-345), not in `PETROBRAIN_SYSTEM.md`/`PETROBRAIN_RUNTIME.md`** — those two describe the
  runtime's knowledge-layer *concepts* (mission knowledge = objective/role/threats/route/phase) but
  the only literal `current_mission:` YAML example in the whole doc tree is `MISSION_INTERPRETER.md`'s:
  `purpose`, `priorities` (list), `key_locations` (name→id dict), `intended_plan` (dict),
  `expected_threats` (list of strings), `current_phase` (single string). This plan treats that
  example as the target shape, corrected below where the current schema can't actually produce a
  field it names.
- **`current_phase` cannot be MI-6's output.** `PETROBRAIN_RUNTIME.md`'s "Runtime mission state"
  section is explicit: "A separate state engine should track [phase]... using aircraft position,
  waypoint progress... Petrobrain receives a current phase, not the entire reasoning needed to infer
  it." That state engine doesn't exist yet (no BL-milestone has built it) and by definition needs
  live aircraft state MI-6 doesn't have — MI-6 runs offline/pre-mission. So MI-6 emits the *ordered
  phase boundaries* (`MissionPhase.name` + `MissionPhase.waypoint_index`, from
  `MissionUnderstanding.mission_phases`, effectively unchanged) for that future engine to walk, not a
  `current_phase` value. Flagged as a real design correction to the concept doc's example, not an
  oversight to silently paper over.
- **`priorities` and `intended_plan` have no data source in the schema as it exists today.**
  `mission-interpreter/src/schema/understanding.py`'s `MissionUnderstanding` has no `priorities`
  field at all, and `player_intent/questions.py`'s `detect_questions` only ever asks four question
  shapes today (`ownship`, `purpose`, `task`, `threat_{index}`) — none of which is a route-deviation/
  approach-preference question that could fill `intended_plan: {ingress: south_of_western_ridge}`.
  Inventing either at MI-6 (guessing a priority ordering, or fabricating an intended-plan value from
  unrelated data) would be exactly the "models invent facts" failure this project's invariants rule
  out — MI-6 is a compiler, not a synthesizer (MI-4 already did the one synthesis stage this pipeline
  has). Both fields are therefore **declared but left `None`/`()`-populated, a documented gap** — same
  posture MI-3 already used for `purpose`/`task`/`known_threats` before MI-4 existed. See "Decisions
  Requiring User Input" for whether to close this gap now upstream (MI-3/MI-4 schema change) instead
  of carrying it.
- **`player_intent`'s answers are never merged back into the fields they answered** —
  `player_intent/console.py`'s `PlayerIntentConsole.run` only ever appends to
  `MissionUnderstanding.player_intent`; `ownship`/`purpose`/`task`/`known_threats` are left exactly as
  MI-3/MI-4 produced them, guess-and-all. This is precisely the reconciliation MI-5's plan flagged as
  MI-6's job (per this task's framing) — MI-6 is the first and only stage that reads `player_intent`
  and folds it back into the compact fields it answers. Reconciliation rules (all pure, no model):
  - `question_id == "ownship"`: only fires when `understanding.ownship.epistemic_status == "UNKNOWN"`
    (`_detect_ownship_question`). The player's answer (`choice` from real candidates, or `free_text`
    fallback — `_ownship_candidates` is always empty today per that module's own docstring, so in
    practice this is always `free_text`) becomes the compact `ownship` identifier string, tagged
    `FACT`, `basis=("player:console",)` — there is no parser from that free text back into
    `Ownship.aircraft`/`.flight`/`.role` sub-fields, so the compact `ownship` field is a plain display
    string, not a reconstructed `Ownship`.
  - `question_id in ("purpose", "task")`: two cases from `_detect_purpose_or_task_question`. (a) the
    tagged value was `None` → question was `free_text` → the player's answer *is* the compact value,
    `FACT`, `basis=("player:console",)`. (b) the tagged value existed at `confidence == "low"` →
    question was `bool` confirming/rejecting the model's guess → `True` keeps the model's value but
    upgrades `basis` to include `"player:console"` and raises `confidence` to `"high"`
    (`epistemic_status` stays whatever MI-4 set it to — player confirmation doesn't make a model
    inference into ground truth); `False` clears the compact field to `None` with `epistemic_status`
    `"UNKNOWN"` — the guess was wrong and nothing better is known.
  - `question_id.startswith("threat_")`: index into `understanding.known_threats` (stable — nothing
    between `detect_questions` running and MI-6 compiling mutates that tuple, since `console.run` only
    ever replaces `player_intent`). `True` keeps the threat in `expected_threats`, `confidence`
    raised to `"high"`, `basis` gains `"player:console"`. `False` drops it from the compact list
    entirely (the raw `MissionUnderstanding.known_threats` still has it, for research/debugging —
    MI-6 only trims the compact projection, mirroring MI-1.5's "raw tree keeps everything, filtered
    tree doesn't" pattern applied to a different filter axis).
  This reconciliation logic is new judgment this plan introduces (nothing upstream specifies it) —
  called locally rather than escalated, since it's reversible and doesn't touch any other
  subproject's schema (Auto-Advance / Escalation Rules: local, reversible, no cross-cutting effect).
- **Route needs to survive compaction, lightly** — `MissionPhase.waypoint_index` only means something
  if the compact artifact also carries a route to index into (the future BL-7 phase-engine's whole
  job is comparing ownship position against these waypoints). Carrying `EnrichedRoutePoint` verbatim
  is wrong: its `WorldRef.position`/`.name_matches` are raw, unbounded `describe_position`/
  `find_place_by_name` JSON blobs (`world_enrich/schema.py`'s own docstring calls this "the raw JSON
  world-model's API returned") — too heavy and not runtime-shaped. Compact route points keep only
  `x`/`y` (from `RoutePoint`) plus one best-effort place name string (first `name_matches` entry's
  name, or `None`), which is the actual "runtime-facing subset" cut MI-6 is supposed to make.
- **This is a pure deterministic mapping, no model involvement** — confirmed, not assumed. MI-4
  already did the one model-in-the-loop stage this pipeline has (`src/synth/`); everything MI-6 does
  above is table lookups, tuple filtering, and dataclass reshaping over already-produced `Tagged`
  values. No new `OllamaClient` call, no new prompt.
- **No live BL-7 consumer exists to validate against.** `body-layer/ROADMAP.md`'s BL-7 entry is
  "Not started," gated on Mission Interpreter existing "or a hand-written Mission Understanding
  fixture" — no such fixture exists in `body-layer/` today (`grep` for
  `current_mission`/`MissionUnderstanding`/`get_mission_phase` across `body-layer/src`+`tests` found
  nothing). BL-7's own entry also carries an unresolved "stale-flag" about whether
  `get_mission_phase` still extends the frozen `TOOL_SET` post-BL-6 — not this plan's call to make,
  noted here only because it means BL-7's actual consumption contract for this artifact is still
  undefined. MI-6 therefore produces the compact artifact and stops; wiring it into BL-7's actual
  consumption (an HTTP endpoint, a file BL-7 reads, an in-process import — the last one would need
  the same justification `body-layer↔world-model`'s sole exception required, per root `CLAUDE.md`'s
  "Module independence" note) is explicitly **BL-7's own design decision**, not this plan's scope.
- Epistemic tagging stays on: every compact field reuses `schema.tags.Tagged[T]` rather than a
  stripped plain value — this is the direct answer to the "does the runtime need full `Tagged`
  wrappers or a simplified confidence summary" question this task raised. `Tagged` already carries
  exactly what a runtime consumer needs to avoid the no-omniscience violation
  (`epistemic_status`+`confidence`, e.g. so a future dialogue layer can say "I think..." for
  `INFERENCE`/low-confidence vs. a flat statement for `FACT`) without introducing a second epistemic
  vocabulary. `basis` (the provenance trail, e.g. `("miz:unit.skill",)`) is retained too rather than
  stripped — it is cheap (short string tuple) and dropping it would remove debuggability for no
  runtime cost saved; nothing in `PETROBRAIN_RUNTIME.md` asks for it to be hidden. No new epistemic
  abstraction is introduced — this directly reuses MI-3's existing `Tagged[T]`, satisfying "don't
  introduce new abstractions unless they remove clear duplication" (here, reuse *removes* the need
  for a second mechanism).

### Affected Modules / Files

- `mission-interpreter/src/runtime/` — new module, sibling to `miz/`, `filter/`, `schema/`,
  `world_enrich/`, `synth/`, `player_intent/` per the subproject's existing per-stage layout.
  - `compact.py` — the `RuntimeMissionUnderstanding` dataclass tree: `schema_version` (int, carried
    through unchanged from the source `MissionUnderstanding` so a future consumer can branch on
    provenance schema version, not just this compact one — consider whether this needs its own
    separate version counter once BL-7 actually consumes it; not needed yet), `theatre: Tagged[str]`
    (passthrough), `ownship: Tagged[str]` (display identifier, see reconciliation rules above),
    `purpose: Tagged[str] | None`, `task: Tagged[str] | None` (both reconciled against
    `player_intent`, see above), `phases: tuple[Tagged[MissionPhase], ...]` (reuse
    `schema.understanding.MissionPhase` directly — it is already exactly the right shape, no new type
    needed), `route: tuple[Tagged[CompactRoutePoint], ...]` with a new small `CompactRoutePoint`
    (`index`, `x`, `y`, `place_name: str | None`), `key_locations: tuple[Tagged[CompactLocation], ...]`
    with a new small `CompactLocation` (`id`, `kind`, `place_name: str | None` — dropping
    `important_locations`' heavy `WorldRef` the same way route points do), `expected_threats:
    tuple[Tagged[str], ...]` (formatted `"{kind}: {description}"` strings, reconciled against
    `player_intent`'s `threat_{index}` answers per above). `priorities`/`intended_plan` are
    **explicitly not fields on this dataclass yet** — see Context's documented-gap note and
    Decisions below; do not add empty placeholders for fields with literally no producer, that would
    invite a future reader to assume they're wired up.
  - `compile.py` — `compile_current_mission(understanding: MissionUnderstanding) ->
    RuntimeMissionUnderstanding`, the single pure mapping function (mirrors `schema/build.py`'s
    `build_mission_understanding` shape/style exactly: one entry point, small private helpers per
    field group). Contains the player-intent reconciliation logic described above as its own helper
    (`_reconcile_purpose_or_task`, `_reconcile_ownship`, `_reconcile_threats`) so each rule is
    independently testable.
- `mission-interpreter/src/player_intent/main.py` — gains an optional `--emit-compact PATH`
  argument: after `console.run(...)`, if the flag is given, call `compile_current_mission` and write
  `json.dumps(dataclasses.asdict(compact), indent=2)` to that path. The existing unconditional
  stdout dump of the full `MissionUnderstanding` is unchanged — this is additive, not a
  behavior change to the default invocation.
- `mission-interpreter/tests/test_runtime_compact.py` — round-trip/serialization test
  (`dataclasses.asdict()` → `json.dumps`, matching every prior stage's convention) proving
  `RuntimeMissionUnderstanding` and its nested types serialize cleanly.
- `mission-interpreter/tests/test_runtime_compile.py` — the schema-mapping test suite, mirroring
  `test_schema_understanding.py`'s pattern (construct a `MissionUnderstanding` by hand, including a
  populated `player_intent` tuple, compile it, assert the compact shape is correct). Must cover, at
  minimum: (a) passthrough fields unchanged; (b) `purpose`/`task` reconciliation for all three player
  answer cases (confirm, reject, fill-from-free-text) plus the "no matching player_intent entry"
  no-op case; (c) `ownship` reconciliation from a `free_text` answer; (d) `threat_{index}`
  confirm-keeps / reject-drops, including that the *raw* `MissionUnderstanding.known_threats` is
  untouched (compaction only trims the compact projection); (e) `phases`/`route`/`key_locations`
  shape and place-name extraction from a `WorldRef` with populated vs. empty `name_matches`.
- `mission-interpreter/CLAUDE.md` — add a "Structure" bullet for `src/runtime/` (MI-6) once
  implemented, matching the existing per-stage bullet convention; note the `current_phase`/
  `priorities`/`intended_plan` corrections from Context so a future reader doesn't have to
  re-derive them from the concept doc mismatch.
- `mission-interpreter/ROADMAP.md` — mark MI-6 done once implemented (check whether this file exists
  yet; if not, this is out of this plan's immediate scope — flag rather than create it here).

### Implementation Plan

1. **Compact schema (minimal working version).** `runtime/compact.py`'s dataclasses, no behavior yet.
   Get the shape reviewed/settled before writing the mapping — this is the artifact's actual contract.
2. **Compilation function.** `runtime/compile.py`'s `compile_current_mission`, built field-group by
   field-group: passthrough fields first (theatre, phases, route, key_locations, expected_threats
   without reconciliation), then layer in the three player-intent reconciliation helpers.
3. **Tests (validate correctness).** `test_runtime_compile.py`'s full matrix of reconciliation cases
   above, plus `test_runtime_compact.py`'s serialization round-trip. This is the stage where the
   design earns its keep — if a reconciliation rule is wrong, it should fail here, not in a future
   BL-7 integration.
4. **CLI wiring.** `player_intent/main.py`'s `--emit-compact` flag, one light integration check (real
   or synthetic-fixture `.miz` through the full pipeline, assert the emitted file parses as JSON and
   round-trips into `RuntimeMissionUnderstanding`-shaped data) — not a new test tier, extend whatever
   `main.py`/pipeline integration test already exists if one does, otherwise a single new test.
5. **Docs.** `CLAUDE.md`/`ROADMAP.md` updates per Affected Modules above.

No performance stage — this is an offline, single-invocation, small-data compilation over one
mission's worth of dataclasses; nothing here is a hot path.

### Risks & Unknowns

- **No live BL-7 consumer to validate the compact shape against.** This is the same schema-churn risk
  the parent plan already flagged for `MissionUnderstanding` itself, one level further out — expect
  `RuntimeMissionUnderstanding` to need revision once BL-7 is actually designed and tries to consume
  it (field names, whether `route`'s cut is too thin or too heavy, whether `key_locations` keyed by
  `id` is usable or BL-7 needed the doc's semantic-role keying (`lz`/`threat_area`/...) instead —
  see Decisions below).
- **`priorities`/`intended_plan` documented gaps could be mistaken for "already handled"** by a
  future reader skimming the compact dataclass and not finding them — mitigated by the CLAUDE.md
  note in Affected Modules, but worth calling out as a real risk of silent scope-narrowing if that
  doc update is skipped.
- **`threat_{index}` question-id parsing is index-based and stability-dependent.** Correct today
  because nothing mutates `known_threats` between question detection and MI-6 compilation, but a
  future stage inserted between MI-5 and MI-6 that reorders/filters `known_threats` would silently
  break this without a type error — a comment at the parsing site should say so explicitly.
- **The player-intent reconciliation rules are this plan's own invention, not a pre-existing spec.**
  They are a reasonable, locally-reversible reading of "fold typed answers into runtime fields," but
  if the user has a different mental model (e.g., `False` on a `purpose` confirmation should keep the
  guess at low confidence rather than clearing it to `UNKNOWN`), that is a one-file, one-function
  change to `compile.py` — not a structural risk, just worth surfacing since no one has reviewed this
  specific judgment call before now.

### Second-order effect

This plan freezes `RuntimeMissionUnderstanding`'s field names/shape as the de facto target BL-7 will
design its ingestion against — same dynamic the parent plan already named for `MissionUnderstanding`
itself, now one layer closer to body-layer. Because MI-6 also formally corrects the concept docs'
`current_mission` example (dropping `current_phase`, deferring `priorities`/`intended_plan`), BL-7's
own planning should treat `docs/concept/MISSION_INTERPRETER.md`'s YAML example as superseded by this
plan/`compact.py`'s real dataclass, not re-derive expectations from the doc directly.

### Decisions Requiring User Input

1. **`priorities`/`intended_plan` — resolved: ship MI-6 without them, declared gap.** User
   confirmed. Populating either needs real cross-stage work (a new MI-4 synthesis target for
   `priorities`, a new MI-5 question shape for `intended_plan`) — not MI-6 scope. Matches MI-3's
   own precedent for `purpose`/`task` before MI-4 existed.
2. **`key_locations` keying — resolved: by `ImportantLocation.id`.** User confirmed. No semantic-role
   classifier exists anywhere in the pipeline yet (`ImportantLocation`'s own docstring: role is
   "deliberately not modeled here yet — that's a tactical judgment, MI-4's job, not MI-3's," and
   MI-4 doesn't populate it either) — keying by role would need that classifier built first, a
   separate cross-stage change outside MI-6.
