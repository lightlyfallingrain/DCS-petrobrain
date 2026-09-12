### Implementation Summary

Implemented MI-6 exactly per the locked plan (`plans/mi6-runtime-compilation/plan.md`, commit
`48a2f5c`): a new `mission-interpreter/src/runtime/` package compiling a full
`MissionUnderstanding` into the compact `RuntimeMissionUnderstanding` (`current_mission`) shape,
a pure deterministic mapping with no model/world-model involvement, including the player-intent
reconciliation logic (ownship/purpose/task/threat_N) the plan identifies as this stage's
substantive work. Wired an additive `--emit-compact PATH` flag into `player_intent/main.py`.

### Files Changed
- `mission-interpreter/src/runtime/__init__.py` — new package.
- `mission-interpreter/src/runtime/compact.py` — `RuntimeMissionUnderstanding`, `CompactRoutePoint`,
  `CompactLocation`. Every field is `Tagged[T]`, matching the plan's "no epistemic metadata
  stripped" requirement. `purpose`/`task` are `Tagged[str] | None`; `priorities`/`intended_plan`
  are not fields at all (documented gap, per plan Decision #1). No `current_phase` field —
  `phases` carries ordered `MissionPhase` boundaries instead (plan's Context section).
- `mission-interpreter/src/runtime/compile.py` — `compile_current_mission`, mirroring
  `schema/build.py`'s one-entry-point-plus-small-helpers style. Reconciliation helpers:
  `_reconcile_ownship`, `_reconcile_purpose_or_task`, `_reconcile_threats`, plus `_build_route`/
  `_build_key_locations` (both drop `WorldRef`'s raw JSON down to `x`/`y`/`place_name`) and
  `_first_place_name` (reads the first `find_place_by_name` match's `"name"` key — `PlaceMatch.name`
  in `world-model/src/query/search.py` confirms this key exists).
- `mission-interpreter/src/player_intent/main.py` — added `--emit-compact PATH` argparse option
  and `write_compact(understanding, path)`, called from `main()` after the console runs. Factored
  as a standalone function specifically so it's unit-testable without a live world-model/Ollama
  pair (neither is injectable in `main()` today).
- `mission-interpreter/pyproject.toml` — added `"runtime"` to `known-first-party` (ruff isort),
  matching every other `src/` package's entry.
- `mission-interpreter/CLAUDE.md` — new Structure bullets for `src/player_intent/` (MI-5, was
  missing) and `src/runtime/` (MI-6), the latter documenting both corrections to
  `MISSION_INTERPRETER.md`'s `current_mission` example.
- `mission-interpreter/ROADMAP.md`, root `ROADMAP.md` — MI-6 marked done.

### Tests Added
- `test_runtime_compile.py` (16 tests) — passthrough fields unchanged; ownship display-string
  formatting from a resolved `Ownship`, empty-string placeholder when `UNKNOWN` with no player
  answer, and reconciliation from a `free_text` player answer; purpose/task: fill-from-free-text
  when never populated, stays `None` when never populated and never asked, confirm-raises-
  confidence-without-upgrading-`epistemic_status` (the test explicitly checking `INFERENCE` stays
  `INFERENCE` — the "would catch an accidental upgrade" test the plan calls for), reject-clears-to-
  `None`, untouched when no matching `player_intent` entry; threats: confirm-keeps-and-raises-
  confidence while asserting the *raw* `known_threats` tuple is untouched, reject-drops-from-
  compact-only (same raw-untouched assertion), untouched when no matching entry; route: x/y/
  place-name extraction with both a populated and an empty `name_matches`; key_locations: id/kind/
  place-name extraction; and an explicit test asserting `priorities`/`intended_plan` are not fields
  on the dataclass and `CompactLocation` carries no role/relevance field.
- `test_runtime_compact.py` (2 tests) — `dataclasses.asdict()` → `json.dumps` → `json.loads`
  round-trip over a fully-populated compact instance, and a second test confirming `purpose`/`task`
  serialize as JSON `null` when absent (not omitted or `{}`).
- `test_player_intent_main.py` (1 test) — `write_compact` writes a file that parses as JSON and
  round-trips into the expected compact shape; this is the plan's stage-4 "light integration
  check," built by hand-constructing an `understanding` and calling `write_compact` directly
  rather than running `main()` end to end (which needs a live world-model server + Ollama daemon
  with no injection point — see the test's module docstring).

### Checks
mission-interpreter/:
- ruff format --check: pass
- ruff check: pass
- mypy --strict src: pass (31 source files)
- pytest -q: pass (111 passed)

### Notable Discoveries
- `player_intent/questions.py`'s `_ownship_candidates` is always empty today (confirmed by
  reading, not just the plan's summary), so `question_id == "ownship"`'s `Question.kind` is always
  `"free_text"` in practice — the reconciliation code still checks `isinstance(answer.parsed, str)`
  defensively rather than assuming this, in case `_ownship_candidates` is ever populated later
  (a `"choice"` answer's `parsed` is also a `str`, the matched option, so no code change would be
  needed if that happens — only the `question_kind` on the stored `PlayerAnswer` would differ,
  which this code doesn't branch on).
- The plan's literal phrasing for purpose/task rejection — "clears the compact field to `None`
  with `epistemic_status` `UNKNOWN`" — doesn't quite fit the declared field type
  (`Tagged[str] | None`, where `None` already means "never populated," not a `Tagged` wrapper
  carrying `epistemic_status="UNKNOWN"`). Implemented literally as "the whole optional field
  becomes `None`" since that's what the plan's own `compact.py` field-type listing specifies and
  is what "clears... to None" most directly means; this collapses "never asked" and "asked, model
  guessed wrong, player rejected" into the same observable state (both `None`). Flagging this as a
  minor loss of distinction versus a hypothetical `Tagged[str | None]` design, not fixing it
  unprompted since the plan explicitly resolved the field's type and this is a one-line change if
  revisited.
- `world-model/src/query/search.py`'s `PlaceMatch.name: str` confirms `name_matches[0]["name"]` is
  the right key for extracting a place name from `WorldRef.name_matches` — not independently
  verified in the MI-6 plan itself, checked directly against world-model's schema before relying
  on it in `_first_place_name`.
