# Mission Interpreter — Roadmap

Decisions locked in for this phase (`plans/mission-interpreter/plan.md`):

- **`.miz`/Lua parsing**: vendored pydcs `dcs.lua` parse/serialize subpackage (Decision 1), not the
  full `pydcs` package.
- **`trigrules`**: parsed as a raw `predicate`-string tree directly, not through pydcs's wrapper
  classes (Decision 1a).
- **World-model transport**: HTTP, not in-process import (Decision 2) -- `mission-interpreter` <->
  `world-model` is a network call, mirroring `aircraft-layer` <-> `body-layer`'s existing seam, not
  `body-layer` <-> `world-model`'s deliberate single in-process exception.
- **Player-intent input**: text console for MVP (MI-5), a web form later (MI-5b) (Decision 4).
- **`mission["trig"]` vs. `trigrules` runtime authority**: open, not blocking (Decision 5) --
  `trig` is treated as an explicitly documented out-of-scope gap through MI-1.5.
- **MI-4's capable-model choice/hosting**: still open (Decision 3) -- gates only MI-4; MI-0 through
  MI-3 do not need it.

Milestones below are from `plans/mission-interpreter/plan.md`'s Implementation Plan.

- [x] **MI-0 — Get a real `.miz` and lock the schema shape.** Completed 2026-09-12:
  `mission-interpreter/research/samples/Mission 02-Bagram.miz` obtained (gitignored, third-party
  campaign content) and validated against a first secondhand research pass, producing
  `research/2026-09-12-miz-file-structure.md` (Hoggit/forum/pydcs-source only, no real bytes) and
  `research/2026-09-12-miz-validation-against-real-sample.md` (real-bytes corrections/confirmations
  -- load-bearing wherever the two disagree). Only one sample/author/DCS mission-format version has
  been examined; treat every finding as "true in this file," not yet "true in general."
- [x] **MI-1 — Structured `.miz` parser (minimal working version).** Done: `src/miz/` reads the zip
  (`reader.py`), parses `mission` + `l10n/DEFAULT/dictionary` via the vendored Lua parser
  (`src/_vendor/dcs_lua/`), and resolves every `DictKey_*` reference tree-wide
  (`dictionary.resolve_dict_keys` -- a generic recursive substitution pass, not a fixed field list,
  per the plan's corrected MI-1 scope) into the typed `RawMission` intermediate representation
  (`tree.py`): theatre, date, weather (raw passthrough), coalition/country/group/unit structure,
  routes, trigger zones (including the literal misspelled `"verticies"` key), `trigrules` (parsed
  structurally, predicate tree left raw), briefing text, kneeboard image paths (opaque, no
  OCR/VLM). `mission["trig"]` is carried through verbatim, unparsed (`RawMission.trig_raw`).
- [x] **MI-1.5 — Author-only-knowledge filter.** Done: `src/filter/crew_available.py` produces
  `CrewAvailableMission` from a `RawMission`, dropping every `hidden`/`hiddenOnPlanner`/
  `hiddenOnMFD`/`lateActivation` group entirely -- `CrewAvailableMission` has no raw-passthrough
  field, so a hidden group's existence cannot leak back in through an unfiltered catch-all.
  `trigrules`/`mission["trig"]` are never surfaced on `CrewAvailableMission` (kept as raw
  research/debugging data on `RawMission` only); `src/filter/trigrules.py` parses `trigrules`' raw
  `predicate`-string schema (Decision 1a) for that research/debugging use. Tests
  (`tests/test_filter.py`) prove the invariant against both the committed synthetic fixture (must
  pass in every checkout) and the real sample mission (skipped if absent).
- [x] **MI-2 — World enrichment.** Done (`plans/mi2-world-enrichment/plan.md`): world-model's
  `src/api/server.py` (`WorldModelAPIServer`, three read-only `GET` routes wrapping
  `describe_position`/`find_place_by_name`/`line_of_sight_clear`, theatre-mismatch validated as a
  `400` to prevent silently-wrong-projection results) is this project's first HTTP seam, called by
  `mission-interpreter/src/world_enrich/world_model_client.py` (`WorldModelClient`, raises on every
  failure -- no "not built yet" expected-empty state). `src/world_enrich/enrich.py`'s
  `enrich_mission` walks a `CrewAvailableMission` (route waypoints, one representative position per
  group, every trigger zone) into a parallel `EnrichedMission` tree (`schema.py`), mirroring
  `belief.enrichment`'s "zero shared surface" precedent rather than mutating MI-1/MI-1.5's frozen
  dataclasses. Per-unit enrichment and free-text briefing-prose place extraction are explicitly out
  of scope this stage (deferred to MI-4). Does not change what MI-3 should be -- MI-3 still needs a
  first Mission Understanding schema, now with `EnrichedMission` as an available input alongside
  `CrewAvailableMission`.
- [x] **MI-3 — First Mission Understanding schema (no model synthesis).** Done
  (`plans/mi3-mission-understanding-schema/plan.md`): `src/schema/` hand-maps MI-1.5's
  crew-available tree + MI-2's `EnrichedMission` into a new, versioned `MissionUnderstanding`
  dataclass tree (`SCHEMA_VERSION = 1`), populating only `theatre`/`ownship`/`route`/a mechanical
  `mission_phases` skeleton (`TakeOff*` -> DEPARTURE, `Land` -> RETURN, everything else left
  unpopulated rather than guessed)/`important_locations` (named `Group`/`TriggerZone` entities whose
  `world_ref.name_matches` is non-empty -- not route waypoints, which the pipeline doesn't resolve
  names for). Every populated field is tagged `FACT` or `OBSERVATION` via the new `Tagged[T]`
  epistemic-tagging mechanism (`src/schema/tags.py`), never `INFERENCE`/`ASSUMPTION` -- proven by a
  dedicated invariant test. Required adding `Unit.skill` to `miz/tree.py` (real-bytes-confirmed
  field, per the investigator's `research/2026-09-12-player-slot-skill-field.md`) so ownship
  resolution can scan for `skill in ("Player", "Client")`; 0 or >=2 matches resolve to `UNKNOWN`
  rather than guessing. `purpose`/`task`/`known_threats`/`player_intent` are declared on the schema
  but deliberately left unpopulated -- MI-4's job once a capable model exists. Does not change what
  MI-4 should be, but confirms `Tagged[T]` as the one epistemic-tagging convention MI-4/5/6 should
  reuse rather than reinvent.
- [x] **MI-4 — Capable-model synthesis.** Completed 2026-09-12 (`plans/mi4-capable-model-synthesis/plan.md`, Decision 3: model=`qwen3:14b`, non-thinking mode, merged commit `9dbb8fa`). **Delivered:** `Tagged[T]` gained a `confidence` field (separate axis from `epistemic_status`, defaults to `None` so MI-1-MI-3 values remain valid); `MissionUnderstanding.known_threats` retyped to `tuple[Tagged[Threat], ...]` (with new `Threat` dataclass: `kind`, `description`, `area_ref: WorldRef | None`); `src/filter/threat_signals.py` (the second, MI-4-specific author-only-knowledge boundary -- derives coarse `ThreatSignal`s from `RawMission`'s hidden/lateActivation groups only, never a name/id/unit count/activation timing, unmapped unit types → `"unknown"`); `world_enrich.enrich.enrich_threat_signals` (resolves each signal's raw coordinate to a `WorldRef` -- the last point that coordinate exists in memory); `src/synth/` (`ollama_client.py` with three-exception design: `OllamaUnavailableError`/`OllamaModelNotPulledError`/`OllamaOutputError`, with `/api/tags` preflight preventing silent model auto-pull; `prompts.py` with structured-output JSON schema restricting `epistemic_status` to `["INFERENCE", "ASSUMPTION"]` only; `synthesize.py` re-validating as defense in depth). **Live validation:** end-to-end tested against real sample mission `Mission 02-Bagram.miz` and `qwen3:14b`; real output: purpose INFERENCE (medium confidence), task INFERENCE (high confidence), 3 known_threats all INFERENCE, zero FACT/OBSERVATION/UNKNOWN overclaims observed across 74 unit tests + 1 live integration test. User confirmed output "looks kinda correct" per the briefing. **Key decisions:** coordinate-leak boundary verified by Reviewer (full data flow from raw signals → world-ref → prompt respects WorldRef.position place names only, never x/z); fail-closed guard against Ollama auto-pull added per project posture (see `OllamaModelNotPulledError`). **Second-order effects:** first real INFERENCE/ASSUMPTION values in the schema provide concrete contract for MI-6's downstream consumption; MI-5 (player questions) independent, unblocked.
- [x] **MI-5 — Player questions (text console MVP).** Completed 2026-09-12
  (`plans/mi5-player-questions/plan.md`, locked commit `9947c93`). **Delivered:** `PlayerAnswer`
  dataclass (`question_id`, `question_text`, `question_kind`, `parsed: bool | str | int`);
  `MissionUnderstanding.player_intent` retyped from the unused MI-3 placeholder `Tagged[str] |
  None` to `tuple[Tagged[PlayerAnswer], ...]`, mirroring `known_threats`'s per-item-tagged-tuple
  shape; new `src/player_intent/` package -- `questions.py`'s `detect_questions` (a pure,
  deterministic detector grounded in what MI-3/MI-4 actually produce today: ownship `UNKNOWN`,
  `purpose`/`task` `None` or `confidence == "low"`, per-threat `confidence == "low"` -- not the
  concept doc's three literal worked examples, which need schema fields that don't exist yet, see
  Decision 1); `console.py`'s `PlayerIntentConsole` (typed `bool`/`choice`/`free_text` parsing over
  a `TextIO` pair, one re-prompt on a parse failure then give-up-as-unparsed-`free_text` with the
  original `question_kind` preserved, mirroring `body-layer`'s `CrewConsole` shape without
  importing it); `main.py`'s `main()` (a plain script wiring MI-1 through MI-5 end to end, same
  construction sequence `test_synth_live_ollama.py` already used, not a new subcommand framework).
  93 unit tests (detector: one case per rule + a no-questions case; console: `io.StringIO`-driven,
  including both re-prompt-once-then-give-up paths). **Does not change what MI-6 should be**, but
  narrows its scope: `player_intent`'s new tagged shape means `bool`/`choice` answers reach MI-6
  already structured (`PlayerAnswer.parsed` typed by `question_kind`), leaving only the two
  genuinely free-text questions (`purpose`/`task` when MI-4 produced nothing) and the runtime
  block's specific field-name/enum mapping as MI-6's remaining interpretation work.
- [ ] **MI-5b — Player questions, web form.** Future; not started, no design work until MI-5 proves
  out.
- [x] **MI-6 — Runtime compilation.** Completed 2026-09-12
  (`plans/mi6-runtime-compilation/plan.md`, locked commit `48a2f5c`). **Delivered:** new
  `src/runtime/` package -- `compact.py`'s `RuntimeMissionUnderstanding` (`schema_version`,
  `theatre`, `ownship`, `purpose`, `task`, `phases`, `route`, `key_locations`,
  `expected_threats`, all still `Tagged[T]`-wrapped -- no epistemic metadata stripped) with two
  new small dataclasses (`CompactRoutePoint`, `CompactLocation`) dropping `WorldRef`'s heavy raw
  JSON down to `x`/`y`/`place_name`; `compile.py`'s `compile_current_mission`, a pure deterministic
  mapping (no model, no world-model call) that also folds MI-5's `player_intent` answers back into
  the fields they answered -- the actual substantive work of this stage, since nothing upstream
  ever did that reconciliation. Two documented corrections to
  `docs/concept/MISSION_INTERPRETER.md`'s `current_mission` example, both per the locked plan:
  **no `current_phase` field** (that needs a live aircraft-position state engine that doesn't exist
  yet -- MI-6 emits ordered `phases` boundaries for that future engine to walk instead) and **no
  `priorities`/`intended_plan` fields** (no data source anywhere in the pipeline -- declared gap,
  not fabricated). `key_locations` keyed by `ImportantLocation.id`, not a semantic role (no role
  classifier exists). `player_intent/main.py` gained an additive `--emit-compact PATH` flag.
  18 new unit tests covering all three reconciliation rules (ownship free-text fill, purpose/task
  confirm-raises-confidence-without-upgrading-status vs. reject-clears-to-`None` vs.
  fill-from-free-text vs. untouched-when-no-answer, threat confirm-keeps/reject-drops-from-compact-
  only), route/key-location place-name extraction, the absence of `priorities`/`intended_plan`/
  role-keying, and `asdict()`→`json.dumps` round-tripping. **Does not change what comes after** --
  no BL-7 consumer exists yet; wiring this artifact into body-layer is BL-7's own design decision,
  explicitly out of this plan's scope. This is the last planned Mission Interpreter stage per the
  parent plan's original stage list.

## First real acceptance — 2026-09-24

**MI ran end to end against three missions the pilot actually intends to fly**
(`MI24-outpost-M03/M04/M06.miz`, Syria), the first time it has faced anything other than the
committed synthetic fixture or the third-party Bagram sample. Card:
`docs/acceptance/2026-09-24-mission-interpreter-sortie.md`.

**Desk half: pass.** A1 (completes end to end), A3 (mission understanding — *"well enough for first
iteration implementation"*) and A4 (author-only-knowledge boundary — no hidden-group leak against
real content, not a fixture) all passed.

**Wall-clock, three runs:** 1:12 with `qwen3:14b` already resident, 3:19 cold (model load
dominates), 2:28 warm-ish. Worth knowing before anyone treats MI as interactive: the pre-mission
pass is minutes, not seconds, and the first run of a session pays roughly two extra minutes for the
model load alone.

**A2 — MI-5's question set is narrower than the stage claims.** In practice it asked only threat
confirmations (*"is this threat &lt;description&gt; real?"*), accepting yes/no. Pilot's verdict:
*"kinda pass ... will do for now, needs further work."* The ambiguity detector is doing its job for
threats and effectively nothing else — ownship, purpose and task ambiguities did not produce
questions on any of the three missions. Backlog, not a regression: MI-5 was never claimed to be
exhaustive, but the gap between "player questions" and "threat confirmations" is wide enough to
name.

**A5 — unicode in place names** surfaced in the compact artifact. Probably already fixed upstream
in the world-model builder and simply not rebuilt into the store the server is reading; unconfirmed
until a rebuild. Not blocking.

**B (sortie half) could not be run at all — see the finding below.**

### MI-6's artifact reaches body-layer and then stops

`body-layer`'s `--mission-understanding` loads the compact artifact and `MissionPhaseTracker`
updates every poll, but **no code path a pilot can reach in flight reads it.** `mission_phase`
appears in exactly four body-layer files (`console.py`, `tools.py`, `mission_phase.py`,
`tool_api.py`) — *not* `attention.py`, not `callouts.py`, not `crew_console.py`. BL-7's
phase-proximity tie-break is real but lives inside `_highest_attention_contact`, whose only caller
is `get_situation`, whose only caller is the `--console` debug harness. The brain layer that would
otherwise call the tool API is still `NullBrainClient`.

So BL-7 is complete as designed and **currently unreachable in a sortie**: mission phase changes
nothing about what Petrovich attends to or says. Closing that is a body-layer question (a
crew-facing way to ask for the situation, or phase feeding attention directly), tracked in
`body-layer/ROADMAP.md`, not more Mission Interpreter work.

## Keeping this current

See root `ROADMAP.md`'s "Keeping this current" note -- this file is the source of truth for Mission
Interpreter's own milestone status; the root file only tracks the cross-subproject picture.
