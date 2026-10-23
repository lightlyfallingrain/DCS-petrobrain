# Review — BL-B90 Stage 0b (offline effector-registry generator)

Branch `feature/effector-sequences`, reviewed at `7b63010fdd7a3d273f65830798b2094127dcb25e`
(fast-forwarded cleanly from `6dfece18`, worktree tree was clean).

Scope reviewed: `body-layer/tools/generate_effector_registry.py`,
`body-layer/tests/test_generate_effector_registry.py`,
`body-layer/tests/fixtures/effector_registry/{clean,dirty,bad_loop}/`,
`aircraft-layer/research/2026-10-23-mi24p-clickabledata-forms.md`,
`plans/effector-sequences/{plan.md,implementation.md,explore-notes.md}`.

### Review Summary

Both Implementer passes are built against the corrected, live-confirmed Lua forms (the 2026-10-23
recon), not the plan's original guesses — verified by cross-checking every one of the 22
`_HELPER_SIGNATURES` entries against the research note's Q3 table by hand; all 22 are correct.
`ruff format --check`/`ruff check`/`mypy --strict` (src and tools)/`pytest -q` all pass clean
(2481 passed, 4 xfailed, no regressions). The three-way completeness invariant (`heads == handled +
unhandled + post-assignment patches`) is sound and matches the recon's own 749 = 501 + 13 + 235
decomposition. CRLF handling, mixed `;`/`,` separators, the header trailing-comment case, the
`device_commands` loop form (and its fail-closed rejection of any other loop shape), the leading-
space element name, trailing commented-out call args, and the raw-literal field names are all
either tested or hand-verified live during this review and are correct.

Four gaps below are real, none of them a currently-live bug against the actual installed file (I
could not make the shipped code produce a wrong number against anything the recon confirmed
exists) — but two of them are demonstrated, not theoretical: I mutated the code twice during this
review and got the full suite to stay green both times, which is exactly the "silently wrong
rather than unhandled" failure mode this plan is most worried about.

### Required Fixes

- **No guard against a `*_commands` table or a `devices["X"]` name being defined a second time.**
  Demonstrated: `parse_command_defs` on a fixture with two `count = start_command` / `foo_commands`
  blocks (same name) returns `{"foo_commands": {"A": 3001, "B": 3002, "C": 3001}}` — the second
  block's counter restarts at 3001 and silently reassigns the duplicate id `3001` with no error, no
  "unhandled" entry, and no effect on the `heads == handled + unhandled + patches` completeness
  count (that invariant only watches `clickabledata.lua`, never `command_defs.lua`/`devices.lua`
  internal consistency). Same thing for `devices.lua`: a repeated `devices["A"] = counter()`
  silently returns `{"A": 2}` instead of erroring. The recon confirms the real file currently has 49
  distinct table names and 73 distinct devices with no duplicates, so this is not live today — but
  it is exactly the "produce a silently wrong number rather than an unhandled entry" risk the task
  brief names, the module's own docstring claims to fail closed "at two levels" and this would be
  an undocumented third gap in that claim, and Stage 0c's real run happens unsupervised on the
  Windows machine with no Mac-side check of this property. Add a cheap guard (raise
  `CommandDefsParseError`/an equivalent on a repeated table or device name) before Stage 0c runs
  against the live install.

- **"Statements ignored" counting/reporting (plan.md "Forms the parser must handle" point 6, and
  the Output/Tests sections — header line `Statements ignored: <n>`) is not implemented at all.**
  `scan_clickabledata` only ever looks for the literal `elements[...]` regex; a hypothetical
  top-level loop or other statement that creates or mutates an element without matching that exact
  pattern (e.g. a dynamic `elements[key..i] = ...`) is completely invisible to the scanner — not
  counted as a head, not unhandled, not "ignored." The 2026-10-23 recon's Q4 confirms the real file
  currently has zero such statements, so this isn't live either, but the plan built this counting
  mechanism specifically as the safety net for exactly that unknown, and it's silently absent from
  both the run report and the TOML header with no decision-log entry explaining the drop. Either
  implement it, or add an explicit note to `implementation.md` recording Q4's zero finding and why
  the current completeness check is judged an adequate substitute — so a future reader doesn't
  rediscover this as a surprise after a DCS patch.

- **`_HELPER_SIGNATURES`' positional-crew mapping — the brief's own "look hardest here" item — is
  untested for 19 of its 22 entries.** Only `default_2_position_tumb`, `default_button_tumb`, and
  `default_square_button` are exercised by any test. I mutated `multiposition_switch`'s `crew_idx`
  from `10` to `9` and reran the full suite: **2481 passed, 0 failures** — the mutation was
  completely invisible. A wrong entry for any of the other 18 helpers (covering most of the 501
  real helper calls — 205 `default_2_position_tumb`, 82 `default_button`, 40
  `multiposition_switch`, 34 `default_blue_cover`, 33 `default_axis`, etc.) would silently
  misattribute device/cmd/arg/seat fields with no test failure, and frequently without even
  tripping "unhandled" (a misread crew position often still parses as a valid integer or `nil`). I
  cross-checked every one of the 22 entries by hand against the research note's Q3 parameter lists
  and all 22 are correct as shipped, so this is not a live bug — but it is wholly undefended. Add a
  parametrized/table-driven test asserting `n_commands`/`crew_idx` for each of the 22 (or at least
  the 18 actually called) signatures against the recon's documented positions, before this table is
  next touched by anyone who hasn't re-read the recon.

- **CLI flag name silently departs from the plan's own spec.** `plan.md`'s "Tool"/"CLI" section
  names the output-path override `--output` three times (`[--output <path>]`, "tests always pass
  `--output` into `tmp_path`"). The shipped tool and every test use `--out`. Harmless functionally,
  but an undocumented departure from an explicit written CLI spec, and neither Implementer pass's
  decision log in `implementation.md` mentions renaming it. Either rename to `--output` to match,
  or add a one-line decision-log entry — per this project's "departing is allowed, doing it silently
  is not."

### Optional Refinements

- The plan's own Tests paragraph names two string/comment-stripping edge cases that have no
  dedicated fixture: a hint containing a literal `--` inside the Lua string (the `dirty` fixture's
  `"broken -- no action field"` happens to touch this but for an unrelated reason — that element is
  unhandled anyway because it's missing `action`, so a comment-stripping regression there would not
  be caught), and a `--[[ ... ]]` block comment containing a fake `elements[...]` line that must not
  be counted. I did not find a bug in `_strip_lua_comments` for either case, but add the fixtures
  the plan asks for (optional).
- No fixture is actually CRLF-encoded, even though the research note calls CRLF out by name as a
  parsing trap. I hand-verified live during this review that `Path.read_text()`'s universal-newline
  translation makes this a non-issue (wrote a throwaway CRLF fixture, ran the CLI against it,
  correct output) — worth committing that as a real fixture rather than leaving it to
  reviewer-time verification (optional).
- Once the duplicate-name guard above is added, give it its own direct unit test (optional, falls
  out of the Required fix almost for free).

### Judgment calls from `implementation.md` — reviewed

- **`autoupdate.cfg` read at write-time only, not unconditionally at startup** — agree. Report mode
  never consumes a build string, so requiring it unconditionally would be a refusal with no
  corresponding need.
- **Exit codes 1 (not-on-DCS-machine / unreadable input) vs. 2 (N unhandled)** — agree, and this now
  matches the plan's own text exactly (verified by re-reading plan.md's CLI section directly, not
  from implementation.md's account of it).
- **`seat`/`seat_explicit`, always one of `pilot`/`operator`/`both`** — agree; this is the right side
  of "never guessed at," correctly implemented and tested both inline and as a post-assignment
  patch.
- **Out-of-set `crew_member_access` → unhandled rather than an unmapped number** — agree, consistent
  with the fail-closed posture and tested for both the inline and post-assignment path.

### Other checks

- Never executes Lua; stdlib-only imports confirmed by reading the import block
  (`argparse`/`hashlib`/`os`/`re`/`sys`/`dataclasses`/`pathlib`). No DCS-BIOS reference anywhere
  except the module docstring's explanatory note. No ED source committed — all nine fixture `.lua`
  files are small, clearly synthetic, and labelled as such in their own header comments.
  `DCS_INSTALL_PATH`/`--scripts-dir` resolution matches the plan exactly, including the "never
  searches for the install" posture.
- Parallel-treatment grep check (per this role's standing instruction): the plan claims a
  three-way completeness check "always holds" and the code asserts it in `main()` — confirmed the
  assert is present and that `scan_clickabledata`'s bucket construction is exhaustive by
  inspection; no sibling location where this invariant should also apply but doesn't (Stage 0b has
  one scanner, not several parallel channels).
- Commands run from this worktree's `body-layer/` using `/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/`
  tools (no venv exists in this worktree):
  - `ruff format --check src tests tools` — pass (172 files already formatted)
  - `ruff check src tests tools` — pass
  - `cd body-layer && mypy src` — pass (71 source files)
  - `mypy tools` — pass (8 source files)
  - `pytest -q` — 2481 passed, 4 xfailed, no regressions
- No leftover debug code or TODO comments found in the new files.
- Stage 0c (the real run on the Windows DCS machine) and Stage 1+ are correctly untouched, per
  `implementation.md`'s own scope statement — no `config/effectors-raw.toml` exists in this repo.

### Verdict

APPROVED WITH MINOR FIXES

The core parser is sound, built against verified live forms rather than guesses, and passes every
mechanical check. The four Required Fixes are defense-in-depth/spec-compliance gaps rather than
live bugs — I could not make the shipped code misbehave against anything the recon confirms exists
in the real file — but two of them (the duplicate-table-name guard and the untested helper
signatures) are exactly the "silently wrong number, not an unhandled entry" failure mode this task
was built to avoid, and I demonstrated both gaps by mutation during this review. Close them before
Stage 0c's real run against the live Windows install, where an undetected duplicate or signature
typo would do real damage with nothing to catch it.

### Review Confidence

Full read of the generator, the test file, all nine fixture files, both research/plan documents,
and `implementation.md`'s two decision logs. Verified claims rather than trusting them: ran the
full `ruff`/`mypy`/`pytest` suite myself, manually cross-checked all 22 `_HELPER_SIGNATURES`
entries against the research note's Q3 parameter lists by hand, and mutated the running code twice
(an untested helper's `crew_idx`, and the completeness assert) to confirm what the test suite would
and would not catch, restoring the file cleanly after each. Not spot-checked.
