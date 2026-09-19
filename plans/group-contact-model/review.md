### Review Summary

Re-review of `feature/group-contact-speech`, scoped to the three commits added since the prior
approval at `6b7cdec` (`2e80dcd`, `66a856d`, `023c591` — `git diff 6b7cdec..HEAD`). These are
user-driven phrasing changes plus one defect fix, made after the user heard Stage 4b's output
rendered. The prior approval (commit `6b7cdec`) is not re-reviewed.

- `2e80dcd` fixes the `"a handful trucks"` grammar defect by having `_cardinality_phrase` carry
  its own connector (`"a handful of"`), and adds `body-layer/tools/speak_samples.py`, a new
  assertion-free acceptance aid.
- `66a856d` adds `"a couple of"` for two-or-three and lets a `watch`/`priority`-attended contact
  with an exact interval (`lo == hi`) speak the real number instead of a hedge, capped at twelve.
- `023c591` is docstring-only, recording that imperfect English ("a couple of armor", "three
  T-72") is in character and out of scope to polish.

**Verified directly, not just trusted:**
- `_cardinality_phrase`'s branch order: the `attended and lo == hi` check sits after the
  `lo == 1 and hi == 1` singular guard, so a singular contact is unaffected regardless of
  `attended` — confirmed by reading and by the new test.
- The honesty condition: `_cardinality_phrase(4, 5, attended=True)` hedges (`"a handful of"`),
  `_cardinality_phrase(8, 10, attended=True)` hedges (`"several"`) — an inexact interval never
  gets a number no matter how it's attended.
- The twelve-count cap: `attended and lo==hi==13` (outside `_SPOKEN_NUMBERS`) falls through to
  `"several"`; `attended and lo==hi==16` hits the pre-existing `lo >= 16: return "many"` branch.
  Both correct — the hedge resumes above the cap, not a numeral.
- `facts.get("attention") in ("watch", "priority")` — checked against `belief/attention.py`'s
  actual `Attention` literal (`"ignore" | "normal" | "watch" | "priority"`) and against
  `tools.py`'s two `"attention"` key writers (`describe_contact`'s facts builder, line 255; the
  event-derived entry, line 598) — the key name and both values are real, and `facts.get(...)`
  on a dict never raises when the key is absent, satisfying the "missing/None cannot raise"
  check.
- No `_cardinality_phrase` branch double-composes a connector: `"several"`/`"many"` stay
  bare-noun phrases (unchanged), `"a handful of"` and the new `"a couple of"` each carry their
  own trailing `"of"`, and `_contact_report_text`'s composition is still a plain
  `f"{phrase} {plural_noun}"` join — no second connector logic was added alongside it.
  `attended`'s exact-number branch returns a bare numeral (`"three"`), which composes the same
  way.
- `attended: bool = False` default — every pre-existing call site of `_cardinality_phrase`
  besides `_contact_report_text` (there are none) is unaffected; `_contact_report_text` itself
  only sets `attended=True` when the new `attention` read says so, otherwise behaves exactly as
  before.
- Ran `body-layer/tools/speak_samples.py` directly (see Required Fixes — needed a different
  `PYTHONPATH`/interpreter than the file's own docstring states) and confirmed its printed table
  matches the reasoning above, including the regression guard's self-check line.
- `023c591` is confirmed docstring-only (`git show --stat` — one file, only insertions, all
  inside the module docstring).
- Scope discipline: grepped the diff for metres/kilometres spelling, acronym spacing, "very
  close", and range-uncertainty changes — none appear; the one `"kilometres"` hit in the diff is
  pre-existing text that moved position, not new content.
- Five new tests in `test_speech.py` do pin the rule's limits, not just its happy path: exact
  count when attended, hedge held when inexact-but-attended, hedge resumed above the spoken
  cap, and the singular guard re-checked under `attended=True`.
- New files staged; `git status` on the branch shows nothing from these three commits
  uncommitted (the untracked files present — `run.sh`, `syria-full-build.log`,
  `syria-theatre-unfiltered.osm.pbf` — are unrelated stray files, not part of this branch's
  diff).

**Verification run (body-layer's own commands, from `body-layer/`):**
- `ruff format --check src tests tools` — pass
- `ruff check src tests tools` — pass
- `mypy src` — pass, no issues
- `pytest tests -q` — 664 passed (up from 659, as expected: 5 new tests)

### Required Fixes

- **`body-layer/tools/speak_samples.py`'s own documented usage command does not work as
  written.** The docstring says `PYTHONPATH=src python3 tools/speak_samples.py`. Running exactly
  that fails immediately: `ModuleNotFoundError: No module named 'query'` (missing
  `../world-model/src` on `PYTHONPATH`), and even with that added, `ModuleNotFoundError: No
  module named 'pyproj'` (needs `body-layer/.venv`'s interpreter, not plain `python3` — the
  world-model seam pulls in `pyproj`, per `body-layer/CLAUDE.md`'s own "Running the live logger"
  note about this exact failure mode). The correct invocation is
  `PYTHONPATH=src:../world-model/src .venv/bin/python tools/speak_samples.py`, confirmed working
  when I ran it. Fix the two usage lines in the module docstring (plain and `--speak` forms) to
  match. Since this is a dev-facing acceptance tool whose entire point is being runnable, a
  command in its own header that doesn't run is a real defect, not a nit — this is the same
  documented-command class of gap `body-layer/CLAUDE.md` calls out for the live logger.

### Optional Refinements

- `speak_samples.py`'s `build_facts` return type is bare `dict` — `mypy --strict` on that file
  in isolation flags two `[type-arg]` errors (`dict[str, object]` would clear them). The file is
  outside `body-layer/CLAUDE.md`'s configured `mypy src` scope, so this isn't a required-fix
  violation of the project's stated check, but it's a one-line inconsistency with the "fully
  type-hinted" stack standard the rest of the subproject holds to (optional).
- `speak_samples.py` imports `belief.speech._contact_report_text`, a private name, across the
  `tools/` → `src/` boundary. Judged acceptable for what this file is — a dev tool driving the
  exact function whose output is under judgment, taking the same `facts` dict shape the function
  itself takes, with no public wrapper that returns bare rendered text for a hand-built facts
  dict today. An alternative (a thin public re-export) would remove the private-name coupling
  but adds surface for a one-off acceptance aid; not worth requiring (optional).
- `body-layer/tools/` did not exist before this commit — this is the subproject's first
  `tools/`. Judged as the right home in spirit (mirrors `world-model/tools/`'s "one-off
  inspection/probe scripts" role for this subproject) even though `body-layer/CLAUDE.md` doesn't
  yet document a `tools/` convention the way the root `CLAUDE.md` does for `world-model/tools/`.
  Worth a one-line mention in `body-layer/CLAUDE.md`'s Structure section at some point, but not
  blocking this branch (optional).

### Verdict

APPROVED WITH MINOR FIXES

The phrasing and honesty-condition logic is correct and well-tested; the one required fix is
confined to two lines of a docstring in a brand-new, non-shipping dev tool and does not touch
`speech.py`'s actual behavior. Once fixed, this is mergeable.

### Review Confidence

Full read — all three commits' diffs read in full, the honesty/cap/singular-guard properties
hand-verified against the code (not just the tests' claims), the acceptance tool actually run
end-to-end, and the full body-layer verification suite (format/lint/mypy/pytest) run directly
rather than trusted from a prior report.
