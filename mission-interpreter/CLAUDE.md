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
- No spatial storage, no HTTP server yet (MI-2 adds a `world_model_client.py` HTTP client against
  world-model's future `src/api/server.py` -- not built yet, see the plan's Decision 2).
- No model/LLM involved through MI-1.5 (MI-4 is the first stage that adds one, gated on Decision 3
  in the plan -- model choice/hosting is still open).

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
  `CrewAvailableMission` at all.
- `src/_vendor/` -- third-party code (currently: pydcs's `dcs.lua` parse/serialize subpackage). Not
  our code to edit; see Tech stack above.
- `src/schema/`, `src/world_enrich/`, `src/synth/` -- future stages (MI-2 onward), not built yet.
- `tests/` -- parser tests (`test_reader.py`), dictionary-substitution tests (`test_dictionary.py`),
  and the central author-only-knowledge invariant tests (`test_filter.py`).
- `tests/fixtures/` -- committed synthetic `.miz` fixture builder.
- `research/` -- dated findings from `.miz` format investigation (see root `CLAUDE.md`'s
  "investigator" section). `2026-09-12-miz-validation-against-real-sample.md` is the load-bearing
  one wherever it disagrees with the earlier secondhand note.
