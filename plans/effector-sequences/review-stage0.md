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

---

### Re-review — 2026-10-23 (fix commit `05ed91d7..197f6577`)

Reviewed `197f65773a78f2669ced8a8a44aabd84ec366875` (worktree fast-forwarded cleanly from
`6dfece18`, a strict ancestor; tree clean before and after).

**All four Required Fixes close the gap, demonstrated by re-running the exact mutations from the
first pass against the fixed code, not just by reading the diff:**

- **Duplicate-name guard.** Mutated the new `table_name in tables` check back out
  (`parse_command_defs`) and reran `test_parse_command_defs_duplicate_table_name_raises_not_silently_restarts`:
  fails (`DID NOT RAISE DuplicateNameError`). Restored, confirmed clean. `parse_devices` has the
  mirrored guard and its own direct test (not separately mutated — same mechanism, already proven
  by the command-defs case).
- **Helper-signature table coverage.** Re-ran the reviewer's own mutation
  (`multiposition_switch`'s `crew_idx` 10→9 in the shipped `_HELPER_SIGNATURES`) against
  `test_helper_signatures_positional_crew_and_command_count`: fails with
  `AssertionError: multiposition_switch: crew_idx positioned wrong`. Restored, confirmed clean via
  `git status --porcelain`.
- **"Statements ignored."** Implemented as `_find_ignored_statements` (blank every matched head's
  consumed span, report remaining non-blank lines) plus a `scan_clickabledata` return value and a
  `render_toml`/CLI report line. Verified directly (not only via the test suite) against a
  hand-built fixture combining the real file's **leading-space element name**, a **nested-table
  raw literal** (`arg_lim = {{0.0, 1.0}, {0.0, 0.5}}`, i.e. Q5's actual `STICK-PTT-PTR` shape) and
  a **post-assignment patch** in one text: `scan_clickabledata` on that text returns `heads=2,
  handled=['STICK-PTT-PTR', 'X'], unhandled=[], patches=0, ignored=[]` — none of the three
  real-file forms is misclassified as ignored or dropped. Ran the actual `clean`/`dirty` fixture
  directories through the CLI directly (not just `pytest`): clean reports
  `10 elements[ heads: 9 emitted, 0 unhandled, 1 field patches, 1 statements ignored` (the
  `elements = {}` line, correctly the only ignored line); dirty reports
  `14 elements[ heads: 9 emitted, 4 unhandled, 1 field patches, 2 statements ignored` — the emitted/
  unhandled counts match the pre-fix numbers exactly (9/4, 9 elements written), confirming no
  regression from broadening `_ELEMENTS_HEAD_RE`.
- **CLI flag rename.** `--output` is now the defined flag; incidentally, `--out` *still* works
  (argparse's default long-option prefix matching resolves the unambiguous abbreviation) — not a
  bug, just worth knowing it wasn't a hard rename in the sense of breaking the old spelling.

**Dynamic-key handling** (new, beyond the four fixes, since fix 2 and fix "2b" are coupled):
`elements[key..i] = ...` is now surfaced as `unhandled` with a reason naming the actual key
expression, verified directly against the `for`-loop synthetic text from `implementation.md`'s
own description — correctly 1 head, 0 handled, 1 unhandled, and the loop's `for`/`end` lines
correctly land in `ignored` rather than being swallowed into the dynamic-key head's span.

**Completeness invariant**: unaffected by this pass's changes — `heads == handled + unhandled +
patches` is still asserted in `main()` and is orthogonal to the newly-added `ignored` count, which
the code and docstrings are explicit never feeds that arithmetic. Not independently re-derived
against the real file's 749/501/13/235 decomposition this pass (no live DCS access from this
worktree), but nothing in this diff touches how heads/handled/unhandled/patches are computed or
counted — only *which* heads are found (`_ELEMENTS_HEAD_RE` broadened to match any key form, not
just quoted-string keys) and what happens to the ones that fall outside the completeness
arithmetic. The clean/dirty fixture runs above are the closest available proxy and show no
regression.

**`_EXPECTED_HELPER_SIGNATURES` independence claim.** Diffed it character-for-character against the
shipped `_HELPER_SIGNATURES` in the module: identical, including key order. On its own this would
read as "copied from the module and labelled independent" — but the recon note's own Q3 code block
lists all 22 signatures in that exact order, so two honest transcriptions of the same ordered
source naturally produce an identical literal. Verified the claim the right way instead: hand-
derived `(n_commands, crew_idx)` for all 22 entries directly from the recon's own positional-
parameter lists (counting argument positions in each `helper(hint_, device_, command_[, command2_],
arg_, ..., crew)` signature myself) and checked both tables against that independent arithmetic —
all 22 match. Combined with the mutation result above (a wrong entry in the shipped table is
caught by the test literal, which is a separate object and does not move with it), this is real
independence, not a diff artifact. Saved as a general lesson:
`.claude/agent-memory/reviewer/feedback_independent_transcription_claim_needs_source_math_not_diff.md`.

**Other checks, this pass:**

- `ruff format --check src tests tools`, `ruff check src tests tools`, `cd body-layer && mypy src`,
  `mypy tools`: all pass clean (71 + 8 source files).
- `pytest -q`: 2491 passed, 4 xfailed — matches `implementation.md`'s reported count exactly
  (2481 + 10 new tests), no regressions.
- No leftover debug code/TODOs in the diff.
- `git status --porcelain` clean before and after every mutation check; no stray files.

### Re-review Verdict

**APPROVED.** All four Required Fixes are genuinely closed, each verified by re-running the exact
mutation that originally demonstrated the gap and confirming it now fails a test (not merely that
new tests exist). All three Optional Refinements were also done. No regressions in the mechanical
checks or the fixture-level behavior. Stage 0 is ready for Stage 0c (the real run against the
Windows DCS install).

### Re-review Confidence

Full read of the fix diff (`generate_effector_registry.py`, the test file, `implementation.md`'s
"Review fixes" section) and the recon note's Q3/Q4/Q5 sections. Verified by mutation, not just by
reading: reran both of the first pass's demonstrated mutations against the fixed code and watched
each fail a test; ran the CLI directly against the `clean`/`dirty` fixtures to cross-check reported
counts outside of `pytest`; hand-built and ran a synthetic fixture combining three real-file forms
(leading-space name, nested-table raw literal, post-assignment patch) through `scan_clickabledata`
directly to check the broadened head-matching/ignored-statement logic does not misclassify any of
them. Not independently re-verified against the live DCS install (no Mac-side access to it) — that
remains Stage 0c's own job, same limitation the first pass noted.

---

## 2026-10-23 — BL-B91 fix review (security change request)

Reviewed commit `9032bec5fd27ba9002499bed2dd0030f7edfef50` on `feature/effector-sequences`
("BL-B91: escape TOML control characters in effector-registry label/name fields"). Verified in a
detached checkout at that exact sha (this worktree's HEAD, `f4e552c1`, was not an ancestor of the
tip — main gained a merge today — so used `git checkout --detach 9032bec5` against a clean tree
rather than fast-forwarding; tree was clean before and after).

This is the fix for `BL-B91` (`body-layer/ROADMAP/BL-B91.md`), filed by the security deep analysis
on this branch (`plans/effector-sequences/security-stage0.md`): `_toml_string`/`_toml_key` escaped
only `\` and `"`, so a raw control character (newline, other C0, DEL) in the two ED-sourced
free-text fields (`label`, element `name`) produced a TOML value `tomllib` could not parse. User
direction picked option (C), fix now.

### Scope fit

The fix departs from the security report's own recommended action — "escape or ... mark the
element unhandled" — by choosing full TOML-spec escaping over the unhandled-element fallback.
`implementation.md`'s "BL-B91 fix pass" section states why: escaping loses no information and
needs no new fail-closed branch, and the unhandled-element path was named in the finding as a
fallback for exactly the case where escaping is not possible, which does not apply here (every
codepoint has either a short escape or a `\uXXXX` form in TOML basic strings). That is the more
complete fix, not a narrower one, and it is the one the security report's own wording leaves room
for ("escape **or**..."). No scope drift: new code is one helper (`_toml_escape`) plus its lookup
table, called from the two existing render sites, nothing else touched.

### Spec correctness — verified directly, not just read

- **Short escapes**: `_TOML_SHORT_ESCAPES` covers exactly the TOML 1.0 basic-string set
  (`\b \t \n \f \r \" \\`), matching spec.
- **`\uXXXX` for the rest**: every other codepoint `< U+0020` plus `U+007F` (DEL) goes through
  `\\u{ord(ch):04x}`. TOML's grammar accepts either case for the hex digits; lowercase (what
  `:04x` produces) is valid.
- **Non-ASCII passes through unescaped and round-trips** — not covered by the new test suite
  (which only exercises ASCII control classes, the quote, the backslash, and plain text), so I ran
  it myself: café, Привет мир, and plain ASCII all round-tripped byte-identical through
  `_toml_string` → `tomllib.loads`, and the raw UTF-8 bytes were present unescaped in the rendered
  string (not re-encoded as `\u` escapes). This is the one check in the brief the tests don't
  cover, and it holds.
- **Both keys and values go through it**: `_toml_key` and `_toml_string` both call `_toml_escape`
  (lines 926, 930); confirmed by reading, and by the dedicated
  `test_toml_key_escapes_control_characters_in_a_quoted_key` test.

### Tests fail on the old code — re-ran the counterfactual myself, not trusted from the report

Copied the pre-fix `_toml_string`/`_toml_key` (`git show 0c9ff074:...`) into the tree and ran the
14 new/relevant tests against it: **10 fail** (`test_toml_string_round_trips_every_control_class`'s
7 non-plain/quote/backslash cases, the injection-payload test, the quoted-key test, and the
end-to-end `render_toml` test), **4 pass** (plain text, quote, backslash, tab — already handled
pre-fix). This matches `implementation.md`'s own counterfactual claim exactly. Also independently
reran the security report's own demonstration payload
(`'evil\nlabel = "INJECTED"\n[elements.pwn]\nx=1'`) against the unmodified pre-fix module in an
isolated interpreter (`-I`, separate scratch dir) and confirmed `tomllib.TOMLDecodeError: Illegal
character '\n'` — the exact failure the finding describes. Restored the fixed file afterward;
`git status --porcelain` on `generate_effector_registry.py` was empty, confirming a byte-identical
restore.

### Nothing else bypasses the helper

`grep`'d the renderer for every string emission site: `_toml_key`, `_toml_string`,
`_toml_str_array` (which itself calls `_toml_string` per element) are the only three, and
`render_toml` routes every free-text field (`name` via `_toml_key`; `device_symbol`,
`cmd_symbols`, `label`, `shape`, `seat` via `_toml_string`/`_toml_str_array`) through one of them.
No inline `f"\"{...}\""` or `.replace()` string construction remains anywhere in the file.

### Reuse check, confirmed

`generate_defaults.py`'s `_toml_value()` has the identical two-character-only gap (read directly:
`body-layer/tools/generate_defaults.py:214-221`, unchanged by this commit). Correctly left out of
scope and flagged rather than silently ignored — it renders this repo's own `tuning.*` source-tree
literals, not ED-sourced free text, so BL-B91's threat does not apply to it. A graph query
(`gq.sh`) surfaced the same node cluster and did not contradict this.

### Checks run (this pass, independently)

- `ruff format --check src tests tools`: 172 files already formatted.
- `ruff check src tests tools`: all checks passed.
- `cd body-layer && mypy src`: success, 71 source files. `mypy tools`: success, 8 source files.
- `pytest tests -q`: 2505 passed, 4 xfailed — matches `implementation.md`'s reported count
  exactly.
- No leftover debug code or TODOs in the diff.
- `git status --porcelain`: clean throughout, including after the counterfactual swap-and-restore.

### Memory / graph queries run

`python3 .claude/scripts/memory-search.py toml escaping effector registry` — not indexed yet, no
hit (expected: a one-occurrence finding, not yet promoted to a memory per the security report's
own note). `.claude/scripts/gq.sh` on the `generate_defaults.py` reuse question — surfaced the
expected node cluster, nothing contradicting direct code reading.

### Verdict

**APPROVED.** The escape helper is TOML-1.0-spec-correct (short escapes plus `\uXXXX`, verified
against non-ASCII pass-through which the tests themselves don't cover), both keys and values route
through it, nothing else in the renderer bypasses it, the new tests demonstrably fail on the
pre-fix code (verified by mutation, not by reading), and the `generate_defaults.py` sibling gap is
correctly identified as out of scope with a reason, not silently left unmentioned. Format/lint/
type/test all pass clean. No regressions, no scope drift, no missing coverage.

### Review Confidence

Full read of the fix diff and its three input documents. Every checklist item in the dispatch
prompt verified directly (spec correctness including the one gap the tests don't cover, the
counterfactual re-run on genuinely swapped-out pre-fix code, the bypass grep, the full
format/lint/type/test suite) rather than taken from `implementation.md`'s report.
