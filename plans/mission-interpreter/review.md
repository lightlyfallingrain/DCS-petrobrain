### Review Summary

Reviewed MI-1 (`.miz` parser) + MI-1.5 (author-only-knowledge filter) on
`feature/mission-interpreter-mi0-mi1` against `plans/mission-interpreter/plan.md` (locked,
`e900b9b`) and `plans/mission-interpreter/implementation.md`. This is the first code in the new
`mission-interpreter` subproject. Every specific claim in the Implementer's report was checked
directly against the source, not taken on trust, per the task brief's eight numbered points.

Findings, verified directly:

1. **pydcs vendoring (Decision 1) — confirmed accurate.** `src/_vendor/dcs_lua/LICENSE.txt` is
   pydcs's real LGPL-3.0 text. `__init__.py` documents provenance (upstream repo, commit
   `55dc18adbd6907ea17d87de559445c4f9bc39146`, pydcs 0.15.0). Grepped both vendored files:
   `parse.py`'s only import line is `from typing import ...`; `serialize.py` has zero import
   statements at all — genuinely self-contained, nothing silently missing from the rest of pydcs.
   `pyproject.toml`'s `[[tool.mypy.overrides]]` scopes `ignore_errors=true` to `_vendor.dcs_lua.*`
   only; `ruff`'s `extend-exclude` is scoped to `src/_vendor` only — both narrow, not a blanket
   strictness weakening. Ran `mypy --strict` myself (see Checks below) — real code stays fully
   strict, vendor dir is silently skipped as intended.
2. **Structural no-leak guarantee — confirmed genuinely structural, not by discipline.** Read
   `CrewAvailableMission`'s dataclass fields directly (`crew_available.py`): `theatre`,
   `coalitions`, `trigger_zones`, `briefing`, `kneeboard_images` — no `raw`/`trig_raw`/catch-all
   field anywhere, unlike `RawMission`, which does carry those. `_is_crew_available` gates on all
   four markers (`hidden`, `hidden_on_planner`, `hidden_on_mfd`, `late_activation`) via boolean OR,
   deny-by-default. `test_filter.py` exercises all four (including `hiddenOnMFD`, via the synthetic
   fixture, since the real sample never sets it) and the assertion is a genuine absence check —
   `test_synthetic_fixture_author_only_names_do_not_leak_anywhere_in_output` asserts each hidden
   group's name string is `not in` `repr(dataclasses.asdict(crew_available))`, not merely "no
   crash." A companion test asserts `trigger_rules`/`trig_raw`/`raw` are literally absent from
   `CrewAvailableMission`'s field list.
3. **`"verticies"` misspelling — confirmed preserved.** `reader.py:252` reads
   `node.get("verticies")` literally; `tree.py`'s `TriggerZone` docstring explains why it isn't
   "fixed." The synthetic fixture also uses the literal misspelled key.
4. **`mission["trig"]` out of scope — confirmed.** `reader.py` copies `mission.get("trig", {})`
   verbatim into `RawMission.trig_raw` and no other code reads it. `filter/__init__.py`'s docstring
   documents the Decision 5 scoping explicitly (not a silent omission).
5. **DictKey substitution — confirmed genuinely recursive/tree-wide.** `dictionary.py`'s
   `resolve_dict_keys` recurses into any `dict`/`list` generically and substitutes any string
   matching `^DictKey_`; no fixed field list anywhere. `test_reader.py`'s
   `test_synthetic_fixture_trigrules_parsed_with_dictkey_resolved` proves this reaches a
   trigger-action's `text` field, not just the four briefing fields.
6. **`trigrules` parsed directly, not via pydcs wrappers — confirmed.** `filter/trigrules.py` reads
   raw `predicate` strings itself (`KNOWN_RULE_KINDS`, `_CONDITION_PREFIX`/`_ACTION_PREFIX`); no
   import of any pydcs `TriggerRule`/condition/action class anywhere in the diff.
7. **Test fixture strategy — confirmed correct on both halves.** Physically moved the real
   gitignored sample aside and reran the suite: 12 passed, 2 skipped cleanly (`SKIPPED`, not
   error/failure) — the skip-guard genuinely works, not just written correctly. The synthetic
   fixture (`tests/fixtures/synthetic_mission.py`) is committed, hand-written Lua text writing a
   real zip via `zipfile.ZipFile`, self-contained, and does not touch the gitignored path.
8. **Scaffolding — consistent with `world-model/`'s conventions and accurately scoped.**
   `pyproject.toml`/`CLAUDE.md`/`ROADMAP.md` mirror `world-model/`'s shape. Root `ROADMAP.md`'s
   status-table row is accurate (MI-0/1/1.5 done, MI-2 onward not started). Confirmed no
   `src/schema/`, `src/world_enrich/`, or `src/synth/` exist yet — scope stayed at MI-1/MI-1.5,
   no MI-2+ creep.

Checks run myself (not just trusted from the report), from `mission-interpreter/` as cwd:
- `ruff format --check src tests` — pass (13 files already formatted)
- `ruff check src tests` — pass
- `mypy src` — pass, 11 source files, strict
- `pytest tests -q` — 14 passed
- Confirmed the report's own claim about the `mypy` cwd gotcha: invoking `mypy mission-interpreter/src`
  from the repo root silently drops `--strict` (an injected untyped-function probe was accepted
  without error); invoking `mypy src` from inside `mission-interpreter/` catches it correctly. The
  report's Notable Discoveries section states this accurately.

### Required Fixes

- **Stage the implementer's own agent-memory files.** `.claude/agent-memory/implementer/MEMORY.md`
  (modified) and `.claude/agent-memory/implementer/project_mi1_mi15_scaffold.md` (new) are present
  in the working tree but not staged (`git status` shows them as unstaged/untracked alongside the
  fully-staged feature diff). Root `CLAUDE.md`'s Definition of Done requires "all new/modified
  files staged and committed" before declaring a task complete — this is a two-command fix
  (`git add` both paths), not a design issue.

### Optional Refinements

- **`mission-interpreter/CLAUDE.md`'s own Commands section documents the exact invocation that
  silently defeats `mypy --strict`** (`mypy mission-interpreter/src` from repo root, per the
  report's own Notable Discoveries finding). This mirrors `world-model/CLAUDE.md`'s pre-existing
  identical pattern verbatim, so it's not a regression this Implementer introduced, and fixing it
  would mean touching a sibling subproject's doc out of this plan's scope — flagging only so a
  future session doesn't get bitten silently by copy-pasting this exact command. Not a blocker.

### Verdict

APPROVED

### Review Confidence

Full read — read every changed source file in full (`tree.py`, `dictionary.py`, `reader.py`,
`crew_available.py`, `trigrules.py`, `filter/__init__.py`, `_vendor/dcs_lua/__init__.py`,
`LICENSE.txt`, all three test files, `synthetic_mission.py`, `conftest.py`, `pyproject.toml`,
`CLAUDE.md`, `ROADMAP.md`), plus the plan and implementation log. Ran format/lint/type/test myself
from the correct cwd, and independently verified the two claims most load-bearing for the plan's
central invariant (structural no-leak field absence, skip-guard actually skipping) by direct
inspection and by physically removing the real sample file and rerunning the suite, rather than
trusting the Implementer's narrative.
