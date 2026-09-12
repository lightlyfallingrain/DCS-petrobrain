# mission-interpreter/CLAUDE.md

Subproject instructions for Mission Interpreter. Augments the root `CLAUDE.md` -- read that first
for overall Petrobrain architecture; this file adds stack/testing/structure specifics that apply
only within `mission-interpreter/`.

See `ROADMAP.md` in this directory for milestone status, `plans/mission-interpreter/plan.md` for
the plan this subproject was built from, and `docs/concept/MISSION_INTERPRETER.md` for the
(draft/provisional) design rationale.

## Tech stack

- Python 3.11+, fully type-hinted, `mypy --strict` (`pyproject.toml`).
- Formatter/linter: `ruff format` / `ruff check`.
- Test runner: `pytest`.
- **`.miz`/Lua-table parsing: vendored pydcs `dcs.lua` subpackage (MI-1 / Decision 1)**. `.miz`
  mission files are Lua tables with no official ED schema (community-reverse-engineered, see
  `research/`). Rather than hand-roll a Lua-table parser or depend on the full `pydcs` package
  (whose generated `weapons_data.py`/`countries.py` catalogs are ~1.7MB combined and unneeded --
  this subproject's semantic layer is bespoke), `dcs/lua/parse.py` and `dcs/lua/serialize.py` are
  vendored verbatim into `src/_vendor/dcs_lua/` (LGPL-3.0, `LICENSE.txt` included) -- they have no
  imports beyond `typing`, so they vendor cleanly without the rest of `dcs/`. Excluded from this
  subproject's own `mypy --strict` run via a `[[tool.mypy.overrides]]` entry; treat as an opaque
  third-party dependency, not code to edit in place. See `src/_vendor/dcs_lua/__init__.py` for
  exact provenance (upstream commit, pydcs version).
- **`trigrules` parsed as a raw `predicate`-string tree, not through pydcs's wrapper classes (MI-1.5
  / Decision 1a)**. Real-bytes validation showed pydcs's `TriggerRule`/condition/action classes are
  a lossy abstraction over this specific structure for author-only-knowledge filtering purposes;
  `filter/trigrules.py` reads the raw `predicate` field (`c_*`/`a_*`/rule-kind/`"or"`) directly.
  See `mission-interpreter/research/2026-09-12-miz-validation-against-real-sample.md`.
- **World-model seam: HTTP, not in-process (MI-2 decision)**. `src/world_enrich/
  world_model_client.py`'s `WorldModelClient` is a stdlib-`urllib.request`-only HTTP client against
  world-model's `src/api/server.py` (`WorldModelAPIServer`) -- mirrors `aircraft-layer` <->
  `body-layer`'s existing HTTP seam, not `body-layer` <-> `world-model`'s deliberate single
  in-process exception (see root `CLAUDE.md`'s "Module independence" note). Unlike
  `aircraft_client.py`'s `get_*` methods, every `WorldModelClient` method raises
  `WorldModelClientError` on failure -- there is no "world-model not built yet" expected-empty
  state once this client is called. No spatial storage of its own.
- **No model/LLM involved through MI-3; MI-4 is the first stage that adds one** (Decision 3:
  Ollama's `qwen3:14b`, non-thinking mode). `src/synth/ollama_client.py`'s `OllamaClient` is this
  subproject's second HTTP seam (stdlib `urllib.request`, mirrors `world_model_client.py`'s
  shape), against a local Ollama daemon's `/api/chat`. Unlike `WorldModelClient`'s single error
  type, it raises two distinct exceptions -- `OllamaUnavailableError` (daemon unreachable: an
  environment problem the caller surfaces) and `OllamaOutputError` (200 OK but bad/unparseable/
  schema-violating output: a prompt/model-quality problem `synth/synthesize.py` degrades on,
  leaving the affected `MissionUnderstanding` field at its MI-3 `None`/`()` default rather than
  failing the whole pass) -- because those two failure modes need different handling. Testable
  offline against a fake `http.server` double (`tests/test_synth_ollama_client.py`,
  `tests/test_synth_synthesize.py`) with **no live Ollama daemon or `qwen3:14b` required** for the
  rest of the suite; `tests/test_synth_live_ollama.py` is the one real integration test, skip-
  guarded on reachability + the model being present (mirrors `REAL_SAMPLE_MIZ_PATH.exists()`'s
  skip convention). The exact `/api/chat` request/response shape (`format` for structured JSON
  output, `think: false` for non-thinking mode) was designed against Ollama's documented API, not
  confirmed live before `qwen3:14b` was available locally -- see `ollama_client.py`'s module
  docstring for the caveat and what to re-check if the daemon's real behavior differs.
- **A second, MI-4-specific author-only-knowledge boundary: `filter/threat_signals.py`**, distinct
  from MI-1.5's `crew_available.py`. `crew_available.py` drops hidden/lateActivation groups so no
  trace of them reaches `CrewAvailableMission`; `threat_signals.py` does the opposite walk --
  reading `RawMission` directly (those groups aren't reachable from `CrewAvailableMission` at all)
  specifically to look *at* them, deriving a deliberately coarse `ThreatSignal` (a type-category
  `kind` + raw position, via a small hand-maintained DCS-unit-type -> category lookup table --
  unmapped types surface as `"unknown"`, never dropped) -- never a group's name, id, unit count, or
  activation timing. `world_enrich.enrich.enrich_threat_signals` resolves that raw position to a
  `WorldRef` -- the last point in the pipeline a hidden unit's exact coordinate exists in memory;
  `synth/prompts.py` must only ever read a `WorldRef`'s place-name fields when building prompt
  text, never `x`/`z`. See `tests/test_synth_synthesize.py`'s coordinate-leak regression test.
- **`Tagged[T].confidence` (MI-4)**: a separate axis from `epistemic_status` -- `epistemic_status`
  says *how* a value was arrived at, `confidence` says *how sure* the model was, and only ever
  means anything once a model (not a deterministic mapping) produced the value. Defaults to `None`
  so every MI-1-MI-3 `FACT`/`OBSERVATION` value stays valid without a confidence judgment that was
  never asked of it.
- **Epistemic tagging: `Tagged[T]`, not a per-field-name dict-map (MI-3 decision)**. `src/schema/
  tags.py`'s `Tagged[T]` (`value`, `epistemic_status`, `basis`) wraps every top-level
  `MissionUnderstanding` field and every `mission_phases`/`important_locations` list item
  individually -- chosen over world-model's `StoredFeature` precedent (parallel
  `provenance`/`confidence` dict-maps keyed by field name) because `MissionUnderstanding` is a
  nested tree whose *list items* need independent epistemic status (one phase FACT, a later one
  INFERENCE once MI-4 exists), which a flat `dict[str, str]` can't express. Every later stage
  (MI-4's threats/purpose/task, MI-5's `player_intent`, MI-6's runtime compaction) is expected to
  reuse this mechanism rather than reinvent one. `basis` is always non-empty for anything MI-3
  populates. Round-trips through `dataclasses.asdict()` -> `json.dumps` with no custom `to_dict`,
  same as world-model's `src/api/server.py` convention.
- **FACT/OBSERVATION redefined for pre-mission use (MI-3 decision, flagged as an interpretation
  call)**. `PETROBRAIN_SYSTEM.md` defines "observation" as "perceived during the mission" (a
  runtime concept); MI-3 runs entirely offline/pre-mission, so nothing it produces is literally
  that. For this schema: **FACT** = read (or mechanically mapped via a fixed table) directly from
  the parsed `.miz`/`CrewAvailableMission` tree, no external source consulted. **OBSERVATION** =
  resolved by consulting the World Model (`describe_position`/`find_place_by_name`) rather than the
  mission file alone -- still fully deterministic, but required a second authority to produce.
  `INFERENCE`/`ASSUMPTION` are declared in the `EpistemicStatus` vocabulary but MI-3 never produces
  either -- see `test_schema_understanding.py`'s invariant test. If this reading of OBSERVATION
  needs tightening once MI-4 needs true inference, that's a cheap rename now, not later.

## Commands

```sh
ruff format mission-interpreter/src mission-interpreter/tests   # format
ruff check mission-interpreter/src mission-interpreter/tests    # lint
mypy mission-interpreter/src                                     # type check (strict)
pytest mission-interpreter/tests -q                               # test
```

Run a single test: `pytest mission-interpreter/tests/path/to/test_file.py::test_name -q`.

`mission-interpreter/.venv` is this subproject's own ad hoc virtualenv (module-independence rule,
root `CLAUDE.md`) -- no dependency lockfile exists yet; `ruff`/`mypy`/`pytest` versions pinned to
match `world-model/`'s own pins for consistency (no reason for the two to drift), reinstall with:

```sh
python3 -m venv mission-interpreter/.venv
mission-interpreter/.venv/bin/pip install "ruff==0.16.5" "mypy==2.3.1" "pytest==9.1.1"
```

## Testing

- `mission-interpreter/research/samples/Mission 02-Bagram.miz` is real third-party campaign content
  and gitignored (see repo root `.gitignore`) -- not present in every checkout. Any test depending
  on it must guard with `@pytest.mark.skipif(not REAL_SAMPLE_MIZ_PATH.exists(), reason=...)` (the
  path constant lives in `tests/conftest.py`).
- `tests/fixtures/synthetic_mission.py` is a small, committed, hand-authored `.miz`-shaped fixture
  (mirrors `body-layer/tests/fixtures/`'s "committed synthetic fixtures, not real DCS captures"
  convention) -- any test proving a structural invariant (most importantly, MI-1.5's "hidden/
  late-activation groups never leak into the crew-available tree") must not depend on the real
  sample alone, since the real sample is unavailable in some checkouts.
- Trigger-zone polygon parsing must use the literal (DCS-shipped-misspelled) key `"verticies"` --
  see `src/miz/tree.py`'s `TriggerZone` docstring. Do not "fix" this spelling anywhere.

## Structure

- `src/miz/` -- `.miz` zip reading: opens the archive, parses `mission` + `l10n/DEFAULT/dictionary`
  via the vendored Lua parser, resolves every `DictKey_*` reference tree-wide (`dictionary.py`), and
  builds the typed `RawMission` intermediate representation (`tree.py`). Deterministic parser only,
  no model involved -- this is MI-1.
- `src/filter/` -- the author-only-knowledge boundary (MI-1.5): `crew_available.py` drops every
  `hidden`/`hiddenOnPlanner`/`hiddenOnMFD`/`lateActivation` group from `RawMission`, producing
  `CrewAvailableMission`, which structurally has no raw-passthrough field (unlike `RawMission`) so a
  hidden group's existence cannot leak back in through an unfiltered catch-all field.
  `trigrules.py` provides predicate-inspection helpers for `trigrules`' raw schema, for
  research/debugging only -- `trigrules`/`mission["trig"]` are never surfaced on
  `CrewAvailableMission` at all. `threat_signals.py` (MI-4) is the second, distinct
  author-only-knowledge boundary -- see Tech stack above.
- `src/_vendor/` -- third-party code (currently: pydcs's `dcs.lua` parse/serialize subpackage). Not
  our code to edit; see Tech stack above.
- `src/world_enrich/` -- MI-2, done: `world_model_client.py` (HTTP client), `schema.py` (the
  parallel `Enriched*` tree), `enrich.py` (`enrich_mission`, the walk that attaches world-model
  context to route waypoints/group positions/trigger zones).
- `src/schema/` -- MI-3, done: `tags.py` (`EpistemicStatus`, `Tagged[T]`), `understanding.py`
  (`SCHEMA_VERSION`, `MissionUnderstanding`, `Ownship`, `MissionPhase`, `ImportantLocation` --
  shape only), `build.py` (`build_mission_understanding`, the mechanical, no-judgment mapping from
  an `EnrichedMission` to a `MissionUnderstanding`; player-slot/ownship resolution is the one piece
  of real logic, scanning every unit for `skill in ("Player", "Client")` and resolving to `UNKNOWN`
  on 0 or >=2 matches rather than guessing). `purpose`/`task`/`known_threats`/`player_intent` are
  declared on `MissionUnderstanding` but left unpopulated by MI-3 -- MI-4 fills in the first three.
- `src/synth/` -- MI-4, in progress: `ollama_client.py` (`OllamaClient`, the Ollama `/api/chat` HTTP
  client), `prompts.py` (system/user message construction + the structured-output JSON schema
  restricting `epistemic_status` to `INFERENCE`/`ASSUMPTION`), `synthesize.py`
  (`synthesize_mission_understanding`, the entry point). See Tech stack above.
- `tests/` -- parser tests (`test_reader.py`), dictionary-substitution tests (`test_dictionary.py`),
  the central author-only-knowledge invariant tests (`test_filter.py`), world-enrichment tests
  (`test_enrich.py`), and MI-3's schema/mapping tests (`test_schema_tags.py`,
  `test_schema_understanding.py` -- the latter's central invariant: no `Tagged` value MI-3 produces
  is ever `INFERENCE`/`ASSUMPTION`).
- `tests/fixtures/` -- committed synthetic `.miz` fixture builder.
- `research/` -- dated findings from `.miz` format investigation (see root `CLAUDE.md`'s
  "investigator" section). `2026-09-12-miz-validation-against-real-sample.md` is the load-bearing
  one wherever it disagrees with the earlier secondhand note.
