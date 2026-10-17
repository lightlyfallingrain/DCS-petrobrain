### Review Summary

Bug fix branch `fix/lua-hook-wiki-link-brackets`, tip `8903f0ec`, reviewed in full (fast-forwarded
from a stale base, confirmed as a strict ancestor before merging). One-commit change: 4 `[[ID]]`→
backtick substitutions inside comments across three Hook `.lua` files, a new regression-guard test
module (`aircraft-layer/tests/test_dcs_export_lua_syntax.py`), and one `docs/DOC_CONVENTIONS.md`
bullet recording the rule and the incident.

Verified independently (re-run, not trusted from the report):
- `ruff format --check`, `ruff check` on `src tests`: clean.
- `mypy --strict src tests` (run from inside `aircraft-layer/`): 2 `unused-ignore` errors, both
  confirmed via `git blame` to predate this branch (2026-09-11 and 2026-10-05, untouched lines) —
  not this change's.
- `pytest tests -q`: 346 passed.
- `git show 8903f0ec -- aircraft-layer/dcs-export/`: all four hunks are comment-text substitutions
  only (`[[BL-B73]]`→`` `BL-B73` `` etc.); no executable Lua line changed.
- Mutated the fix back in (reinstated `[[BL-B73]]` in `petrobrain-line-of-sight-hook.lua`): both
  `test_no_nested_long_bracket_in_block_comment` and `test_loads_as_lua` failed for that file, with
  `luajit` reporting the exact DCS-observed parse error (`'=' expected near 'to'`). Restored, tree
  clean again.
- `luajit` is on this machine's `PATH`, so `test_loads_as_lua` genuinely ran (not skipped) for all
  26 files — confirmed via `-v` output, 53/53 passed on the clean tree.
- Repo-wide sweep for `[[ID]]`-shaped forms in any tracked `.lua` file (`git ls-files '*.lua'` — 26
  under `aircraft-layer/dcs-export/`, 7 under `world-model/tools/dcs-mission-probe/`): no remaining
  occurrence anywhere in the repo, not only the three scoped files. The one hit from a broader grep
  (`petrobrain-elevation-cost-probe-hook.lua:309`, `local NULL_CODE = [[return "x"]]`) is a genuine
  Lua long-bracket string literal with no nested `[[`, confirmed not to match the test's own regex
  and confirmed passing in the test run above — not a wikilink, not a miss.
- `loadfile` mechanism: path travels via `PB_LUA_CHECK_PATH` env var read inside the `-e` chunk,
  never spliced into Lua source or passed positionally — confirmed by inspection and by the mutation
  test above producing a *parse* error (`'=' expected near 'to'`), not a runtime API error, which is
  what the positional-argument version produced before (26 false failures, per the commit message).
  `subprocess.run` uses the list form (no `shell=True`); the path comes from a `Path.glob` over a
  repo-tracked directory, not external input. No security concern for this test-only call.

### Required Fixes

- **The regression-guard regex misses the project's own dotted ID form.**
  `_WIKI_LINK_RE = re.compile(r"\[\[[A-Za-z][\w-]*\]\]")` in
  `aircraft-layer/tests/test_dcs_export_lua_syntax.py` cannot match `[[AA-1.1]]`-style stage links —
  `\w` and `-` don't include `.`, and `docs/DOC_CONVENTIONS.md` itself documents this exact form
  (*"A parent milestone with its own stages links down to them, e.g. `Stages: [[AA-1.1]] [[AA-1.2]]
  …`"*). Verified directly: `_WIKI_LINK_RE.fullmatch("[[AA-1.1]]")` returns `None` while
  `[[BL-B73]]`/`[[BR-2]]`/`[[WM-W12]]` all match. This is not hypothetical scope-gold-plating — the
  dotted stage-link form is a real, documented variant of the exact convention that just caused a
  total detection blackout, and this test module's own stated purpose is to be "the floor" against
  reintroducing *any* member of that family. A future stage-link wikilink pasted into a Hook header
  comment would pass this guard silently and reproduce the 2026-10-17 incident. Fix is small: allow
  `.` in the character class (e.g. `[\w.-]*`), confirm it still excludes the one legitimate
  long-bracket string literal in the repo (`NULL_CODE`, verified above), and re-run the mutation
  test with a dotted ID to confirm the fix actually catches it.

### Optional Refinements

- `_lua51()` trusts `luajit`/`lua5.1` by name to be Lua-5.1-syntax-compatible without checking a
  version string. Fine as-is — matches this subproject's existing convention of naming `luac5.1` by
  name elsewhere (`aircraft-layer/CLAUDE.md`'s Lua syntax check) — but worth a one-line comment if a
  future PATH ever carries a same-named but incompatible build. Not worth blocking on.
- `test_export_dir_has_lua_files`'s guard was checked by reasoning (an empty/renamed glob produces
  `[]`, which the guard's `assert _LUA_FILES` catches) rather than by physically renaming
  `dcs-export/` in the worktree — low risk, since the logic is a one-line `assert`, but noted for
  completeness.

### Verdict
APPROVED WITH MINOR FIXES

The required fix is small, localized to one regex in the new test file, and does not touch the
hook-file substitutions, the `loadfile` mechanism, or the doc note — all of which are correct and
independently verified. Recommend sending back to Implementer for the one-line regex fix plus a
mutation re-run on a dotted ID, then straight back here rather than a full re-review.

### Review Confidence
Full read — all five changed files read in full, every check in the task's priority list run
independently (not trusted from the report), plus a repo-wide sweep beyond the three named files.
