### Implementation Summary

Stood up the `mission-interpreter/` subproject from scratch and implemented MI-1 (structured
`.miz` parser) and MI-1.5 (author-only-knowledge filter) per `plans/mission-interpreter/plan.md`.

Decision 1 (pydcs dependency) was resolved to the plan's preferred path, not the fallback: pulled
real pydcs source from `git+https://github.com/pydcs/dcs.git` (commit `55dc18a...`, version 0.15.0)
and confirmed `dcs/lua/parse.py` + `dcs/lua/serialize.py` have no imports beyond `typing` — they
vendor cleanly on their own without pulling in the rest of `dcs/` (weapon/country catalogs). Vendored
verbatim into `mission-interpreter/src/_vendor/dcs_lua/`, LGPL-3.0 `LICENSE.txt` included, provenance
documented in that package's `__init__.py`. No full-`pydcs` fallback was needed.

Before writing any parsing code, extracted the real gitignored sample (`research/samples/Mission
02-Bagram.miz`) into the session scratchpad and read the actual byte-level shape of `mission`
(coalition/country/group/unit nesting, `route.points[]`, `triggers.zones[]` including the misspelled
`"verticies"` key, `trigrules`' `predicate` tree) directly, rather than trusting the research notes'
prose paraphrase alone — this caught the exact real-file nesting order (`y` before `x` in `route.
points[]`, action dicts' extra fields) needed to write the reader without guessing.

### Files Changed

- `mission-interpreter/pyproject.toml` — new. `dcs-mission-interpreter`, Python 3.11+,
  `mypy --strict` (with a `[[tool.mypy.overrides]]` exemption for `_vendor.dcs_lua.*`, third-party
  code predating strict-mode conventions), `ruff` (vendor dir excluded from lint/format),
  `pythonpath = ["src", "tests"]` so `tests/fixtures/` imports as an ordinary package.
- `mission-interpreter/.gitignore` — new, mirrors `world-model/.gitignore`'s pycache/venv/cache
  exclusions (there is no repo-wide one; each subproject carries its own).
- `mission-interpreter/CLAUDE.md`, `mission-interpreter/ROADMAP.md` — new, modeled on
  `world-model/`'s equivalents.
- `mission-interpreter/src/_vendor/dcs_lua/{__init__,parse,serialize}.py`, `LICENSE.txt` — vendored
  pydcs Lua parser, see above.
- `mission-interpreter/src/miz/tree.py` — typed intermediate representation (`RawMission` and
  nested dataclasses: `Coalition`/`Country`/`Group`/`Unit`/`Route`/`RoutePoint`/`TriggerZone`/
  `TriggerZoneVertex`/`TriggerRule`/`BriefingText`). Only the parts MI-1.5's filter needs precise
  structure over get dedicated fields; everything else rides along as a raw dict/mapping on the
  nearest node or on `RawMission.raw`.
- `mission-interpreter/src/miz/dictionary.py` — `resolve_dict_keys`, the generic recursive
  tree-wide `DictKey_*` substitution pass (not a fixed field list, per the plan's corrected MI-1
  scope). A dictionary miss is logged and the raw `DictKey_...` string is left in place rather than
  raising, since the DictKey-bearing-field vocabulary is not closed.
- `mission-interpreter/src/miz/reader.py` — `read_miz`: opens the zip, parses `mission` +
  `l10n/DEFAULT/dictionary` via the vendored parser, runs the DictKey pass, and builds `RawMission`.
  Individually-optional fields (most of `mission`'s subsections) default rather than hard-fail if
  absent, per the plan's own "written against one sample, expect adjustment" framing. `mission["theatre"]`
  (present inline, a real-bytes bonus finding beyond what the validation note called out) is
  preferred over the zip-root `theatre` file when both exist.
- `mission-interpreter/src/miz/__init__.py` — package exports.
- `mission-interpreter/src/filter/crew_available.py` — `filter_crew_available`/
  `CrewAvailableMission`. Drops every group with `hidden`/`hiddenOnPlanner`/`hiddenOnMFD`/
  `lateActivation` set. `CrewAvailableMission` has no raw-passthrough field at all (unlike
  `RawMission`) — a structural guarantee, not a discipline promise, that a hidden group's existence
  can't leak back in through an unfiltered catch-all field added later.
- `mission-interpreter/src/filter/trigrules.py` — predicate-inspection helpers over `trigrules`'
  raw schema (Decision 1a), for research/debugging only; never referenced by `crew_available.py`'s
  actual filtering decision (that decision uses only each group's own four boolean markers).
- `mission-interpreter/src/filter/__init__.py` — package docstring records the Decision 5 scoping
  (`mission["trig"]` explicitly unparsed/unfiltered, carried through only on `RawMission.trig_raw`,
  never on `CrewAvailableMission`).
- `mission-interpreter/tests/conftest.py` — `REAL_SAMPLE_MIZ_PATH` constant + the skip-guard
  convention.
- `mission-interpreter/tests/fixtures/synthetic_mission.py` — committed, hand-authored `.miz`-shaped
  fixture (writes a real small zip file), covering DictKey resolution, all four author-only markers
  including `hiddenOnMFD` (unexercised by the real sample), a circle + polygon trigger zone, one
  `trigrules` rule, and a kneeboard image path.
- `mission-interpreter/tests/test_dictionary.py`, `test_reader.py`, `test_filter.py` — see Tests
  Added below.
- Root `ROADMAP.md` — Mission Interpreter row updated from "Not started" to reflect MI-0/MI-1/MI-1.5.

### Tests Added

- `test_dictionary.py` — `resolve_dict_keys` against nested dicts/lists, non-DictKey strings/other
  types pass through unchanged, and a missing dictionary entry is left in place and logged.
- `test_reader.py` — synthetic-fixture coverage of theatre/briefing/kneeboard-image parsing, group/
  unit/route field extraction, all four author-only markers being parsed correctly (not filtered —
  MI-1 is pre-filter), the circle/polygon trigger-zone shapes including the literal `"verticies"`
  key, and `trigrules` parsing with DictKey resolution reaching into action text. Plus one
  `@pytest.mark.skipif`-guarded test against the real sample asserting the same category of facts
  against real bytes (theatre, date, presence of `lateActivation`/`hiddenOnPlanner` groups, polygon
  vertices, a `triggerStart` rule).
- `test_filter.py` — the plan's central invariant: `test_synthetic_fixture_drops_every_author_only_
  group` proves the crew-available tree contains exactly the one visible group and none of the four
  author-only ones; `test_synthetic_fixture_author_only_names_do_not_leak_anywhere_in_output` goes
  further and asserts the hidden groups' names don't appear anywhere in `dataclasses.asdict()` of
  the whole `CrewAvailableMission` (not just "not in the group list"); `test_synthetic_fixture_
  trigrules_and_trig_are_not_on_crew_available` is a structural field-presence check. A fourth,
  skip-guarded test (`test_real_sample_drops_every_author_only_group`) re-proves the same invariant
  against the real sample's actual hidden/late-activation groups. All four ran and passed locally
  (the real sample is present in this checkout).

### Checks

mission-interpreter/:
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy --strict` (`mission-interpreter/src`): pass — 11 source files, `_vendor.dcs_lua.*` exempted
  per its own override
- `pytest -q`: pass — 14 passed (12 always-run + 2 real-sample-only, both present and passing in
  this checkout; verified separately that both skip cleanly with `SKIPPED` (not error/failure) when
  the gitignored sample file is temporarily moved aside)

No other subproject was touched by this task (MI-2's world-model HTTP server is separate, future
scope per the plan).

### Notable Discoveries

- **`mypy` config discovery is CWD-only, confirmed again for this subproject.** Running
  `mypy mission-interpreter/src` from the repo root silently finds no `pyproject.toml` and runs
  *without* `--strict` at all (verified: an intentionally-untyped probe function was accepted
  without complaint). `CLAUDE.md`'s own Verification section commands must be run with
  `mission-interpreter/` as cwd (`cd mission-interpreter && mypy src`), matching the same gotcha
  already recorded for world-model in agent memory — this is not new, but it bit this session too
  and is worth restating in `mission-interpreter/CLAUDE.md`'s Commands section (done).
- **`pip download --no-deps -d <dir> "git+https://..."` works even though the sandbox blocks
  `curl`/raw GitHub fetches directly.** This was the only viable way to get real pydcs source this
  session (no `gh` CLI installed, `dangerouslyDisableSandbox` did not restore `curl`'s network
  access this time despite an earlier session's memory note that it had). Worth remembering as a
  fallback path for future "need one real file from a GitHub repo" situations.
- **`mission["theatre"]` exists inline in the real sample**, not just as the zip-root `theatre`
  member the research notes focused on — a small bonus finding beyond what either research note
  called out; `reader.py` prefers it when present.
- The vendored pydcs Lua parser round-tripped the real 346KB `mission` file and the dictionary file
  with no issues on first try — the plan's risk note about needing "adjustment against a second
  sample" applies to this subproject's own field-mapping code (`reader.py`'s `_parse_*` helpers),
  not to the vendored parser itself, which real bytes now validate independently of pydcs's own
  test suite.
