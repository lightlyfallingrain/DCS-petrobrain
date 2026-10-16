### Implementation Summary

`BL-B77` — the prerequisite the user ordered ahead of the contacts-callout plan itself: unify the
one hedge register that was spoken two different ways. `render_group_disclosure`'s
undifferentiated-pair branch carried a hardcoded `"A couple of contacts."` literal while
`_cardinality_phrase` — the shared hedge register every other caller uses — returns bare stems
(`"couple"`/`"handful"`/`"several"`/`"many"`). The pair branch now calls `_cardinality_phrase(2, 2)`
and composes its own text from the returned stem, exactly as every other caller does.

### Files Changed
- `body-layer/src/belief/speech.py` —
  - `_render_full_group_composition`'s `elif is_pair:` branch (undifferentiated case) now calls
    `_cardinality_phrase(2, 2)` instead of carrying the literal `"A couple of"`, and composes
    `f"{hedge.capitalize()} {_plural_unit_type_display(value, level)}"`. An `assert hedge is not
    None` documents why this call can never return `None` (that only happens for `lo == hi == 1`).
  - `_cardinality_phrase`'s own docstring corrected to describe the bare stems it actually returns
    (`"couple"`/`"handful"`/`"several"`/`"many"`, no leading article, no per-phrase connector) —
    it previously still described the pre-brevity wording (`"a couple of"`/`"a handful of"`), which
    is exactly what let the inconsistency survive undetected: a reader checking the register
    against the group line found the *docstring* agreeing with the literal, not the code.
    **The function itself is unchanged** — no behaviour change there, per the user's separate
    direction for `[[X-T4]]` to use the existing hedge vocabulary as-is.
  - `render_group_disclosure`'s own docstring (the "A two-member group is the only size this stage
    words specially" bullet) updated to describe `"Couple {contacts}"` and the shared-register call
    instead of the old hardcoded phrasing.
- `body-layer/tests/test_speech.py` — renamed
  `test_render_group_disclosure_undifferentiated_pair_says_a_couple_of` to `..._says_couple` and
  changed its assertion from `"A couple of contacts."` to `"Couple contacts."` This is a
  **specification change, not a test fixed to match output**: the whole point of `BL-B77` is that
  the spoken line changes to read the shared register, and this is the one test that pins exactly
  that line. No other test asserted the old literal.
- `body-layer/ROADMAP/BL-B77.md` — marked done with a short account of what changed and the
  "Group." branch decision below.
- `.claude/agent-memory/implementer/feedback_worktree_no_venv.md` — new memory: an isolated
  worktree has no subproject `.venv` of its own; run the main checkout's venv binaries with `cwd`
  inside the worktree's subproject directory instead.

### Decision: the `"Group."` three-or-more branch is unchanged

Per the roadmap entry's explicit instruction, this branch was inspected, not changed by default.
Decision: **leave it as the bare word `"Group"`**, with no hedge at all. A group of three or more
undifferentiated members has no count to hedge about — Petrovich is reporting one thing he
believes in (a group), not a vague quantity of individually-counted members, which is exactly the
distinction the roadmap entry itself raises as the reason this might be correct. The two-member
case is different: there, "couple" genuinely hedges a count (two distinct, nameable members), the
same quantity `_cardinality_phrase` already hedges within one contact's own cardinality. No code
change to this branch.

### Third-site check

`grep -rn 'couple of' body-layer/src/` found no third caller composing this hedge by hand beyond
the one fixed. The other hits are unrelated: `_phrase_for_duration` (`speech.py` ~1125) is a
separate duration-phrase vocabulary (`"a moment"`/`"a minute"`/`"a couple of minutes"`), not the
contact-count hedge register; `_undifferentiated_phrase` (`speech.py` ~2088) uses exact spoken
numbers (`"two contacts"`) for a differentiated group's own undifferentiated members rather than
the hedge register at all, so it was never part of the two-registers inconsistency; the remaining
hits in `callouts.py` and `speech.py`'s own docstrings/comments are quotes of historical sortie
transcripts, not code paths that render speech.

### Tests Added
- None added; one existing test renamed and its assertion changed (see above) to match the
  corrected behaviour.

### Checks
(body-layer/ — the only subproject touched)
- `ruff format --check src tests`: pass (133 files already formatted)
- `ruff check src tests`: pass (all checks passed)
- `cd body-layer && mypy src` (CWD-only, run from inside the subproject): pass (60 source files,
  no issues)
- `pytest tests -q`: pass — 2061 passed, 4 xfailed (pre-existing xfails, unrelated to this change).
  The renamed test confirmed passing by name in unfiltered `-v` output
  (`test_render_group_disclosure_undifferentiated_pair_says_couple PASSED`).

### Notable Discoveries
- This worktree was created with no `body-layer/.venv` of its own (gitignored, not copied).
  Resolved by invoking the main checkout's `body-layer/.venv/bin/<tool>` with `cwd` set inside this
  worktree's own `body-layer/` directory — `mypy`'s CWD-only config discovery still resolves
  against the worktree's `pyproject.toml`, since that depends on the working directory, not which
  `site-packages` the interpreter happens to live in. Recorded as
  `.claude/agent-memory/implementer/feedback_worktree_no_venv.md`.
- No new tunable constant was needed for this change — `_cardinality_phrase`'s thresholds are
  untouched, and the fix is purely which word a pre-existing call returns to a caller that
  previously bypassed it.
