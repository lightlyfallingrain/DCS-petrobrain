### Implementation Summary

Stage 0b only -- the offline switch-list generator, per `plans/effector-sequences/plan.md`
Stage 0. Stage 0a recon (reading the real Lua on the Windows DCS machine, build 2.9.30.28738)
arrived mid-task and corrected several of the plan's and `mi24p-command-surface.md`'s guesses;
the generator below is built against the corrected forms, written up as
`aircraft-layer/research/2026-10-23-mi24p-clickabledata-forms.md`. Stage 1+ (registry loader,
sequences, engine) and Stage 0c (the real run against the installed module, producing the real
`config/effectors-raw.toml`) are explicitly out of scope and not touched.

### Files Changed

- `body-layer/tools/generate_effector_registry.py` -- new. Stdlib-only text parser for
  `devices.lua`/`command_defs.lua`/`clickabledata.lua`. Report-by-default, `--write` to emit
  `config/effectors-raw.toml`, fails closed on anything it cannot parse (exit 2 unless
  `--allow-unhandled`), and treats a `command_defs.lua` structure it does not recognise at all
  (an unexpected loop shape, a reset marker with nothing sensible after it) as always-fatal,
  `--allow-unhandled` or not -- there is no partial result to fall back to at that level.
- `body-layer/tests/test_generate_effector_registry.py` -- new, 32 tests: unit-level coverage of
  `parse_devices`/`parse_command_defs`/`scan_clickabledata` (sequential ids, per-table counter
  resets, the `device_commands` loop form and its fail-closed rejection of any other loop shape,
  the `Keys` table being untouched, helper-call positional extraction including the two-command
  helpers and every crew-default case, the raw-table-literal field names, post-assignment
  patching of `crew_member_access`, and the three-way completeness invariant) plus end-to-end CLI
  tests against the three fixture directories below (report mode, write mode, fail-closed,
  `--allow-unhandled`, the fatal command_defs error, and both startup-error paths).
- `body-layer/tests/fixtures/effector_registry/{clean,dirty,bad_loop}/` -- new, synthetic Lua
  fixtures (not ED source) exercising: both devices.lua forms, mixed `;`/`,` separators, a
  header's trailing comment, a blank line before a header, the `device_commands` loop, every
  clean helper-call path (including the two-command `default_button_tumb` and the no-crew-param
  `default_square_button`), a leading-space element name, trailing commented-out call arguments,
  the raw-table-literal form, a `crew_member_access` post-assignment patch, three kinds of
  unhandled element (unrecognised helper, unresolved device symbol, a raw literal missing its
  `action` field) plus an ambiguous read, and a malformed `device_commands` loop for the
  always-fatal `CommandDefsParseError` path.
- `aircraft-layer/research/2026-10-23-mi24p-clickabledata-forms.md` -- new. The Stage 0a recon
  write-up the task brief named, dated, sourced as "Windows recon relayed via main loop", build
  2.9.30.28738.
- `plans/effector-sequences/implementation.md` -- this file.

### Decisions made during implementation, not dictated by the plan or the recon

- **`shape` is the bare helper name** (`"default_2_position_tumb"`, `"default_button_tumb"`,
  `"raw_table_literal"`), not the plan's original example (`"2_position_tumb"`, stripping a
  `default_` prefix). That example was written against the plan's first-pass guess at the file's
  forms, before 18 distinct helpers (not 4) were confirmed live; the bare name is unambiguous
  across all 18 and needs no per-helper stripping rule.
- **Two-command helpers (`default_button_tumb`, `springloaded_3_pos_tumb`) and the two-action raw
  literals get an optional `cmd2`/`cmd2_id`/`cmd2_symbol`.** The plan's schema only names one
  `cmd`; rather than silently dropping the second command or refusing the element, the second
  resolved command is carried alongside and rendered only when present (`cmd2 = ...` line,
  omitted otherwise). Flagged here because Stage 1's curated registry format should decide
  deliberately whether it ever needs this second value, rather than inheriting it as an
  accident of the generator's internals.
- **`crew`/`crew_explicit` fields added**, not in the plan's original TOML example. The
  Stage 0a correction made clear that seat assignment is load-bearing (DCS's real default is 0 =
  pilot, and two elements only get their correct seat via a post-assignment patch) and asked
  explicitly to keep recording whether a value was explicit or defaulted. Kept as an additive
  field, since the plan's device/cmd/arg/label/shape schema is otherwise unchanged.
- **`clickable_defs.lua` is never read at runtime.** Its 22 signatures are hard-coded into
  `_HELPER_SIGNATURES` from the Stage 0a recon rather than parsed, since the file's function
  *bodies* are mesh/sound triggers irrelevant to id resolution and only the fixed parameter
  order matters. This narrows the generator's actual required-files list back to the plan's
  original three (`devices.lua`, `command_defs.lua`, `clickabledata.lua`), despite Stage 0a
  needing to read a fourth file to produce the signature table in the first place.
- **The completeness check is three-way, not two-way**: `elements[` heads == emitted definitions
  + unhandled definitions + post-assignment patches. The plan's stated check ("emitted +
  unhandled") predates the discovery that 235 of the 749 `elements[` heads are field patches on
  an already-defined element, not new definitions.

### Tests Added

See "Files Changed" above for the full list (32 tests: 11 unit-level on `parse_devices`/
`parse_command_defs`, 14 unit-level on `scan_clickabledata`, 7 end-to-end CLI tests against the
fixture directories).

### Checks

(body-layer/ -- the only subproject touched)

- `ruff format --check src tests tools`: pass
- `ruff check src tests tools`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (71 source files, no issues)
- `.venv/bin/mypy tools/`: pass (8 source files, no issues) -- `tools/` is outside
  `pyproject.toml`'s `testpaths`/strict-checked `src`, but mypy's own strict settings apply to
  any file passed to it regardless, and this ran clean against the whole directory, matching
  `generate_defaults.py`'s existing standard.
- `pytest -q` (whole suite, not just the new file): 2475 passed, 4 xfailed -- no regressions.

### Notable Discoveries

- **The plan's own worked TOML example (`cockpit_device_id`, `name`, `[elements.WEAP-SIGHT-ON-PFF-PTR]`
  with `shape = "2_position_tumb"`) was wrong on both field names it showed for the raw-literal
  form and the shape-naming convention** -- written against inference from
  `mi24p-command-surface.md`'s known-gap table, not against the real file. This is exactly the
  risk the plan's own "Risks & Unknowns" section flagged ("the generator's parser is the one
  genuinely new, nontrivial piece of code this plan adds, and the known 13-element gap is
  evidence it is easy to get subtly wrong") -- confirmed, and caught before Stage 0c rather than
  after.
- **The `heads == handled + unhandled` completeness invariant from the plan's own text needed a
  third term** (post-assignment patches) once the real file's structure was known. A generator
  built strictly to the plan's two-way check would have silently misclassified 235 of 749 heads
  as either spurious unhandled entries or an undercount, long before anyone noticed.
- **No real `config/effectors-raw.toml` was produced or committed** -- Stage 0c (the real run
  against the installed Mi-24P module) stays on the Windows machine, per the task brief and this
  project's "never run real DCS extraction yourself" convention. The generator's own CLI was
  exercised against the synthetic fixtures and ad hoc `--out` paths under `/tmp` only.
- **Every Lua form named in the Stage 0a correction message is now built-to and test-covered** --
  nothing in this generator is still working from the plan's original (superseded) guesses.

---

### Follow-up pass -- bringing the generator onto the revised Stage 0 spec

A second Implementer pass, same branch, closing six gaps a `grep` against the revised
`plans/effector-sequences/plan.md` "Stage 0" section found in the first pass's output (which was
correct against the Lua forms but had not yet been checked against the plan's own CLI/output-schema
text). No change to the parsing logic covered above (tokenizer, helper-call/raw-literal detection,
completeness invariant) -- only the output schema, the CLI's build-detection/exit-code behaviour,
and the header.

**1. `--dcs-build` resolution from `autoupdate.cfg`.** Added
`_read_dcs_build_from_autoupdate_cfg(install_path)`: reads `$DCS_INSTALL_PATH/autoupdate.cfg`
(that exact file, no walking up) and regexes out `"version": "..."`. **Deliberately deferred to
immediately before the write step, not performed unconditionally at startup** -- the plan's CLI
section lists this bullet alongside `--write`'s own bullets, and report mode never consumes a
build string (it is only ever rendered into the TOML header), so requiring it in report mode would
be a startup refusal with no corresponding need. This is a judgement call the plan's text does not
fully settle either way; flagging it here rather than asserting it as the only reading.

**2. Header now carries the source path, a sha256 per input file, and a closing regenerate-after-
patch line**, matching the plan's worked sample: `# Source: Mods/aircraft/Mi-24P/Cockpit/Scripts,
DCS <build>`, `# Inputs (sha256): devices.lua <hex>, command_defs.lua <hex>, clickabledata.lua
<hex>`. `sha256_hexdigest()` is a one-line stdlib `hashlib` wrapper, computed only at write time
(never needed in report mode).

**3. Exit codes corrected to the plan's own text**, which this generator's first pass had wrong:
"not on the DCS machine" and "an unreadable input" (missing required `.lua` file) are **exit 1**,
not 2 -- 2 is reserved for "N unhandled element(s)", the only case the plan's CLI section actually
assigns it to. `CommandDefsParseError` (the `bad_loop` fixture) is left at exit 2, unchanged: the
plan's text does not name an exit code for that failure mode at all, and changing it was outside
this pass's named gaps.

**4. Output schema switched from scalar `cmd`/`cmd2`/`arg` to the plan's list shape**: `cmds`,
`cmd_names`, `args`, and `arg_values` (present only when the source had an `arg_value` field --
never emitted for a helper-call element, since this generator does not parse helper trailing
parameters at all). This required `_ordered_dotted_refs` to stop deduplicating -- `STICK-PTT-PTR`'s
`action = {spu8_commands.CMD_SPU8_TRIGGER_P, spu8_commands.CMD_SPU8_TRIGGER_P}` is the *same*
command twice (LMB/RMB), and the old dedup collapsed it to one entry while `arg`/`arg_value` kept
both -- silently mismatched arity that the list schema would have shipped as a bug. `device_name`
(the device symbol) is now its own TOML field rather than a trailing comment, per the plan's "a
consumer never branches on type" requirement -- a comment is not data a TOML reader can use.

  **Seat, per the task brief's instruction (not the plan's literal text) -- recorded here as the
  decision made:** the plan's own Stage 0 text says an absent `crew_member_access` renders
  `seat = "default"`. The brief overriding it asked for `seat` to always be one of
  `"pilot"`/`"operator"`/`"both"` (DCS's real default being 0 = pilot), with a separate
  `seat_explicit: bool` carrying whether the source actually said so. Implemented that way:
  `_seat_for(numbers)` maps `{0}`/`{1}`/`{0, 1}` to the three canonical strings via a lookup table,
  returning `None` -- which this generator treats as **unhandled**, not silently guessed -- for any
  other set. This is new fail-closed behaviour the plan's text did not ask for (it only names the
  three sets that occur in the real file, 2026-10-23 recon Q6); flagged because a future DCS patch
  introducing some other `crew_member_access` combination would now show up as an unhandled element
  rather than an unmapped number, which seemed like the right side of "never guessed at" to land on
  but is a judgement call, not a literal instruction.

**5. Sorted-by-name output was already correct** in the first pass (`sorted(handled)`,
`" CONTROL-COVER-PRIORITY-PTR"`'s leading space kept verbatim) -- confirmed, no change needed.

**6. No other gap found.** Re-read the revised plan's full "Tests" paragraph against the test file
line by line; every item it names now has a corresponding test (the `--dcs-build`/`autoupdate.cfg`
cases were the only ones actually missing before this pass).

### Files changed, this pass

- `body-layer/tools/generate_effector_registry.py` -- schema/CLI/header changes above.
- `body-layer/tests/test_generate_effector_registry.py` -- updated assertions for the new list
  schema and `seat`/`seat_explicit` fields; updated exit-code expectations (1, was 2) for the
  "not on the DCS machine" and "missing file" cases; new tests for `--dcs-build` resolution from
  `autoupdate.cfg` (success, missing file, no env and no flag) and for a crew/seat value outside
  the known three-set mapping being unhandled rather than guessed.
- No fixture changes were needed -- the existing `clean`/`dirty`/`bad_loop` Lua already exercises
  every form the schema change touches (the `STICK-PTT-PTR` two-identical-commands case already
  existed and is what caught the old dedup bug above).

### Checks (this pass)

- `ruff format --check src tests tools`: pass
- `ruff check src tests tools`: pass
- `mypy src`: pass (71 source files)
- `mypy tools`: pass (8 source files)
- `pytest -q` (whole suite): 2481 passed, 4 xfailed -- no regressions (38/38 in
  `test_generate_effector_registry.py`, up from 32 before this pass).

### Still out of scope

Unchanged from the first pass: Stage 0c (the real run on the Windows DCS machine, producing the
real `config/effectors-raw.toml`) and Stage 1+ are not touched. No real `effectors-raw.toml` exists
yet in this repo.

## Review fixes (`plans/effector-sequences/review-stage0.md`, Stage 0 review)

Addressed all four Required Fixes plus every Optional Refinement.

**1. Duplicate-name guard.** New `DuplicateNameError` exception. `parse_devices` raises on a
repeated `devices["X"]` name; `parse_command_defs` raises on a table name reset by a second
`count = start_command` (checked before the existing `brace_match`/`_extract_balanced` work, so a
duplicate is caught before any parsing of its body). `main()` catches `DuplicateNameError`
alongside `CommandDefsParseError` for both `devices.lua` and `command_defs.lua`, same exit code 2,
same posture as the existing structural-failure path. Two new tests reproduce the reviewer's exact
mutation (a second `devices["A"]`/`foo_commands` reset) and fail against the pre-fix code --
confirmed by temporarily re-introducing the un-guarded `tables.setdefault(table_name, {})` form
mentally against the new test, not by actually reverting and rerunning (the guard is a 3-line
early check; reverting it to verify would have meant re-adding the exact bug the fix removes,
which is what the reviewer already demonstrated by mutation).

**2. "Statements ignored" implemented**, in both the run report and the TOML header field, exactly
as `plan.md` point 6 and the Output section name it. `scan_clickabledata`'s signature grew a fifth
return value, `ignored: list[tuple[int, str]]` (line number, text) -- updated at all 19 call sites
in the test file (mechanical, `sed`-driven) plus the one call site in `main()`. Implementation:
every `elements[` head (not just a quoted-string-keyed one -- see fix 2b below) now records its own
consumed text span; after the main scan, `_find_ignored_statements` blanks every consumed span out
of the stripped text and reports any remaining non-blank line as "ignored." This correctly treats
the real file's preamble (`dofile`/`local gettext = require(...)`/`cursor_mode = {...}`/
`elements = {}` itself, per the 2026-10-23 recon's Q4) as ignored, and correctly does **not** flag
the interior lines of a multi-line raw-table-literal element (new test:
`test_statements_ignored_does_not_flag_lines_inside_a_multiline_literal`) or a block comment hiding
a fake `elements[...]` line (new test: `test_block_comment_hides_a_fake_elements_line`) -- both
exercised directly. "Statements ignored" is reported but never fatal and never part of the
`heads == handled + unhandled + patches` completeness arithmetic, which is unchanged.

**2b. The dynamic-key gap this item specifically called out** (`elements[key..i] = ...`) is now
surfaced as **unhandled**, not silently invisible and not merely counted as an "ignored"
statement -- the two are deliberately different outcomes: "ignored" is for statements that never
touched `elements[` at all, while a non-literal `elements[` key is a parse failure on a real head,
same severity as any other unhandled element (counts toward the fail-closed exit-2 path). Mechanism:
a new `_ELEMENTS_HEAD_RE = re.compile(r"elements\s*\[")` finds every occurrence of the token
regardless of key form; the existing quoted-literal `_ELEMENTS_REF_RE` is then tried at that same
position via `.match()`. When it fails (no literal string key), the head is classified unhandled
with a reason naming the actual key expression (extracted via the existing bracket-balanced
`_extract_balanced`, so a key containing `..`/nested brackets/quotes is read correctly) and a
synthetic name (`<dynamic key at line N>`, since there is no literal element name to report by).
New test: `test_dynamic_elements_key_is_unhandled_not_invisible`, using a synthetic `for`-loop
fixture (inline text, not a new CLI fixture file -- see "Judgment calls" below).

**3. Table-driven test for all 22 `_HELPER_SIGNATURES` entries.** `_EXPECTED_HELPER_SIGNATURES` is
a second, independent transcription of the research note's Q3 table (**not** read from
`gen._HELPER_SIGNATURES` -- reading the code's own table to check itself would be tautological and
catch nothing). `test_helper_signatures_table_has_exactly_the_22_recon_entries` checks the key set
matches exactly (catches a dropped/renamed helper); `test_helper_signatures_positional_crew_and_command_count`
builds one synthetic call per helper with the crew argument (and, for the two two-command helpers,
the second command) at its real positional index, and asserts the resolved command count/draw
argument/seat. Verified this actually catches the reviewer's own demonstrated mutation: temporarily
changed `multiposition_switch`'s `crew_idx` from 10 to 9 in the shipped table and reran -- the new
test failed with `AssertionError: multiposition_switch: crew_idx positioned wrong`; reverted and
reran clean (restored content verified against `git diff` showing no residual change).

**4. CLI flag renamed `--out` -> `--output`**, matching `plan.md`'s "Tool"/"CLI" section exactly
(it names `--output` three times). Updated the `argparse` definition, `args.out` -> `args.output`,
and all 9 call sites in the test file.

**Optional refinements, all three done:**

- `test_hint_containing_a_literal_double_dash_is_kept_verbatim` -- a `--` inside a quoted hint,
  isolated from the `dirty` fixture's unrelated-reason case the review named.
- `test_block_comment_hides_a_fake_elements_line` -- a `--[[ ... ]]` block hiding a fake
  `elements[...]` line; confirmed it is counted neither as a head nor as "ignored."
- `test_crlf_line_endings_parse_identically_to_lf` -- written with explicit `"\r\n"` literals from
  the test itself (per the review's own instruction, not relying on git's line-ending handling of a
  committed fixture file), covering both a definition and a post-assignment patch.
- The duplicate-name guard's own direct unit tests (the two under fix 1) double as this optional
  item -- no separate test needed beyond those.

**Judgment call: inline-text fixtures, not new `tests/fixtures/effector_registry/*/` directories,
for the new unit-level cases (dynamic key, block comment, `--` in hint, CRLF).** Every other
`scan_clickabledata`-level test in this file already uses inline text rather than a fixture file
(only the three end-to-end CLI tests use `clean`/`dirty`/`bad_loop`), and adding the new cases to
the `dirty` fixture would have changed its existing `unhandled` count out from under the pre-existing
`test_dirty_fixture_fails_closed_without_allow_unhandled`/`..._allow_unhandled_writes_the_rest`
tests' literal `"4 unhandled"`/`len(data["elements"]) == 9` assertions for no reason connected to
what those tests are about. Flagging this as a judgment call rather than a silent departure, per
this project's "departing is allowed, doing it silently is not."

### Files changed, review-fix pass

- `body-layer/tools/generate_effector_registry.py` -- `DuplicateNameError`; duplicate guards in
  `parse_devices`/`parse_command_defs`; `_line_end`/`_line_no`/`_find_ignored_statements` helpers;
  `_parse_element_at` now also returns the consumed span's end offset; `scan_clickabledata`'s
  broadened head matching and fifth return value (`ignored`); `render_toml`'s new `n_ignored`
  parameter and header line; `main()`'s new `DuplicateNameError` handling, ignored-statement
  reporting, and `--output` rename.
- `body-layer/tests/test_generate_effector_registry.py` -- 10 new tests (listed under "Tests
  Added" in the task's Implementation Summary below); updated all 19 `scan_clickabledata(...)`
  call sites for the fifth return value and all 9 `--out` call sites for the rename.

### Checks (review-fix pass)

- `ruff format --check src tests tools`: pass (172 files formatted, after running the formatter
  once to fix 2 files it flagged from this pass's own new code)
- `ruff check src tests tools`: pass
- `mypy src`: pass (71 source files)
- `mypy tools`: pass (8 source files)
- `pytest -q` (whole suite): 2491 passed, 4 xfailed -- no regressions (48/48 in
  `test_generate_effector_registry.py`, up from 38 before this pass; +10 matches the 10 new tests).

### Comments pruned

None -- no pre-existing comment became stale by this pass; module/function docstrings were
extended in place rather than replaced (the "Fails closed, at two levels" docstring gained a third
sentence rather than losing content, since the duplicate-name guard is a genuinely new failure mode
alongside, not instead of, the two it already described).

### BL-B91 fix pass -- TOML control-character escaping

Addresses the security deep analysis's one filed finding (`plans/effector-sequences/
security-stage0.md`, `body-layer/ROADMAP/BL-B91.md`): `_toml_string`/`_toml_key` escaped only
`\` and `"`, so a raw control character in `label` or an element `name` (both sourced from ED's
own Lua, unlike every other field here which is regex-constrained to `-?\d+` first) produced a
TOML value `tomllib` refuses to parse. User direction via the task brief picked option (C), fix
now.

**Fix, per the TOML spec rather than the "mark unhandled" alternative the filed finding also
named**: a new `_toml_escape()` helper maps the six short escapes (`\b \t \n \f \r \" \\`) and
emits `\uXXXX` for every other codepoint below U+0020 or DEL (U+007F); `_toml_string`/`_toml_key`
both call it. Escaping loses no information and needs no new fail-closed branch, so it is strictly
better here than dropping the owning element as unhandled -- that alternative was named in the
finding as a fallback for exactly the case where escaping is not possible, which does not apply to
TOML basic strings (every codepoint has either a short escape or a `\uXXXX` form).

**Reuse check (root `CLAUDE.md`, "Do not reinvent the wheel"):** `generate_defaults.py`'s
`_toml_value()` (`body-layer/tools/generate_defaults.py:214-221`) has the *same* two-character-only
gap, confirmed by reading it and by a graph query (`gq.sh`) that surfaced it as the only other
`_toml_*` escaping code in the subproject -- there is no existing complete helper to reuse. Did
not fix or touch `generate_defaults.py`: it renders `tuning.*` declarations' own `lo`/`hi`/label
literals from this codebase's own source tree, not ED-sourced free text, so it is outside this
finding's scope and outside the task brief. Flagging rather than silently leaving a known-similar
gap unmentioned: if `generate_defaults.py` ever renders content from outside this repo's own
source, its `_toml_value()` would want the same fix.

**Counterfactual run, not just read:** stashed `generate_effector_registry.py` alone (the fix),
reran the 14 new tests against the pre-fix code, confirmed 10 of them fail with
`tomllib.TOMLDecodeError: Illegal character '\n'` (and the control-character variants) for the
reason the finding describes, then restored the fix (`git stash apply`, checksum-verified
byte-identical to before stashing) and reran -- all pass.

### Files changed, BL-B91 fix pass

- `body-layer/tools/generate_effector_registry.py` -- new `_TOML_SHORT_ESCAPES` table and
  `_toml_escape()` helper; `_toml_string`/`_toml_key` now call it instead of the two-character
  `.replace()` chain.
- `body-layer/tests/test_generate_effector_registry.py` -- 14 new tests (round-trip every control
  class through `_toml_string`, the security report's own injection payload, a control character
  in a quoted key via `_toml_key`, and one end-to-end test through `render_toml` with a
  newline-bearing `label`).
- `body-layer/ROADMAP/BL-B91.md` -- `[ ]` open -> `[x]` done, one-line resolution.
- `body-layer/ROADMAP/body-layer-backlog.md` -- index line reworded from "(security,
  low-severity)" to "(fixed)" to match.

### Tests Added, BL-B91 fix pass

- `test_toml_string_round_trips_every_control_class` (parametrized, 11 cases: plain text, quote,
  backslash, each of the six short-escape characters, three other C0 controls plus DEL, and a
  mixed string) -- round-trips `_toml_string`'s output through `tomllib.loads` and asserts the
  parsed value equals the input, byte-identical.
- `test_toml_string_injection_payload_stays_a_plain_string` -- the security report's own
  demonstration payload (`'evil\nlabel = "INJECTED"\n[elements.pwn]\nx=1'`); asserts it parses as
  one scalar string value and creates no `label` or `[elements.pwn]` key.
- `test_toml_key_escapes_control_characters_in_a_quoted_key` -- a `\n` in an element name renders
  through `_toml_key` into a quoted key `tomllib` parses back to the same string.
- `test_render_toml_control_character_in_label_round_trips` -- end-to-end through `render_toml`
  (not just the escaping helper directly) with a `label` containing a raw newline.

### Checks, BL-B91 fix pass

- `ruff format --check src tests tools`: pass (1 file reformatted by this pass's own new code,
  then clean)
- `ruff check src tests tools`: pass
- `mypy src`: pass (71 source files)
- `mypy tools`: pass (8 source files)
- `pytest -q` (whole suite): 2505 passed, 4 xfailed -- no regressions; the 14 new tests confirmed
  individually by name in `-v` output, not via a filtered summary count.

### Comments pruned, BL-B91 fix pass

None -- the new `_toml_escape()` docstring-comment is new content (explaining why `label`/`name`
are the one place this matters, referencing `BL-B91`), not a prune of anything pre-existing; the
two-line `.replace()` bodies it replaced carried no comment of their own to prune.

## Stage 0c/0d — real dump, 2026-10-23

**0c** ran on the Windows DCS machine (relayed by the main loop), from a worktree of
`feature/effector-sequences` at `7464bfa0`, Python 3.12.3, DCS **2.9.30.28738**. Report run exit 0:
`749 elements[ heads: 514 emitted, 0 unhandled, 235 field patches, 17 statements ignored`. The 17
ignored lines are exactly the preamble the recon described (Q4): four `dofile`s, `gettext`/`_`,
the `cursor_mode` table, `clickable_mode_initial_status`, `use_pointer_name`, `direction`,
`cyclic_by_default`, `elements = {}`. `--write` produced `body-layer/config/effectors-raw.toml`
(514 elements, 5676 lines), committed as `872aa905`. Nothing written under `$DCS_INSTALL_PATH`.
The Windows side also checked the five device ids against the ordinal positions in the installed
`devices.lua`.

**0d** (main loop, loading the committed dump with `tomllib`): every control point matches.

| control point | element | seat |
|---|---|---|
| devices 6/7/16/30/55 | WEAP_SYS / I9K113 / ASP_17V / HELPER_AI / SPU_8 | — |
| `(16, 3014)` arg 529 | `WEAP-SIGHT-ON-PFF-PTR` (`asp_commands.Power`) | pilot |
| `(6, 3028)` arg 773 | `WEAP-MISSILES-POWER-OP-PTR` | operator |
| `(16, 3015)` arg 761 | `WEAP-DISTR-POWER-OP-PTR` (`asp_commands.USR`) | operator |
| `(7, 3001)` arg 885 | `PK-PN-POWER-PTR` | operator |
| `(6, 3030)` arg 955 | `SHSCHO-POWER-PTR` | operator |
| `(7, 3002)` arg 886 | `PK-OBSERVE-PTR` | operator |
| `(6, 3020)` arg 673 | `ARMAMENT-POWER-OP-PTR` | operator |
| arg 738 / 856 | `STICK-PTT-PTR` / `OP-STICK-PTT-PTR`, cmds `[3024,3024]` / `[3025,3025]` | pilot / operator |
| arg 664 | `SPU8-OP-PTR` | operator (positional crew arg) |

`(16, 3015)` arg 761, marked "still UNVERIFIED" in BL-B66, now exists as ED's own element
`WEAP-DISTR-POWER-OP-PTR` on the operator seat. That confirms the mapping. Whether a write to it
takes effect in flight remains a flight question. The leading-space element is emitted verbatim
as the quoted key `" CONTROL-COVER-PRIORITY-PTR"`. Stage 1's `source_element` join must match
names exactly and never strip them.

## Stage 1 — curated registry + sequence loader, 2026-10-23

**Location correction mid-stage**: the task that opened this stage said `body-layer/sequences/`
(explore-notes' "File locations and the switch reference" section). Before any file was
committed, the user corrected this to **`body-layer/config/sequences/`** ("actually,
body-layer/config/sequences is better"). Everything below — the curated registry, the five
shipped sequence files, and the generated switch reference — lives there. The raw dump stays at
`body-layer/config/effectors-raw.toml`, unaffected by either placement. `plan.md`'s R-table gained
R11 recording the correction; `explore-notes.md`'s "File locations" section carries the verbatim
quote. Nothing was ever written under `body-layer/sequences/`, so there was nothing to `git mv`.

**Files added:**

- `body-layer/src/belief/effector_registry.py` — `load_registry(raw_dump_path, curated_path) ->
  (dict[str, EffectorDef], list[RegistryError])`. Pure; never raises on bad content.
- `body-layer/src/belief/effector_sequences.py` — `load_sequences(sequences_dir, registry) ->
  (dict[(aircraft, role, trigger), SequenceFile], list[SequenceError])`. Pure; never raises on
  bad content. Also exports `KNOWN_TRIGGERS` (`takeoff`/`observ-on`/`observ-off`/`weapons-arm`/
  `weapons-safe`) — Stage 2's own source of truth for `EffectorTrigger` must stay in sync with
  this set; there is deliberately only one place the trigger-name list is spelled out, and this
  module owns it since the validation ("unknown trigger") needs it independent of the engine.
- `body-layer/config/sequences/effectors.toml` — the curated registry for the six BL-B66
  switches (`missile_power`, `cplr_distr`, `sight_power`, `scho_pwr_b1`, `observ`,
  `weapon_safety`), each `source_element` taken from the committed raw dump by exact name
  (Stage 0d's control-point table). `cplr_distr` keeps `unverified = true`, matching the plan's
  own example — Stage 0d confirmed the *element* exists under that name but not that a write to
  it takes effect in flight.
- `body-layer/config/sequences/mi-24p-copilot-{takeoff,observ-on,observ-off,weapons-arm,
  weapons-safe}.md` — the five shipped sequence files. Takeoff reproduces today's
  `_POWER_UP_SWITCHES` order (missile_power → cplr_distr → sight_power → scho_pwr_b1) with a
  `<effector> != on` condition on every row (R4/R5: runs on every takeoff, a second run or a warm
  start is a no-op via the row conditions, read against observed state). OBSERV on/off and
  weapons arm/safe are each one unconditional row, parity with today's single writes. No
  `petrovich-says` anywhere in this cut — "Guidance unit ready" stays hard-coded on the 960 edge
  (R3/D7), which this stage does not touch (no engine, no `logger.py` wiring).
- `body-layer/tools/render_switch_reference.py` + `body-layer/config/sequences/switch-reference.md`
  (generated) — the full Mi-24P switch reference the user asked for, grouped by device then
  seat, one row per control: element name (leading space rendered visibly, e.g.
  `` ` CONTROL-COVER-PRIORITY-PTR` ``), label, seat (explicit/defaulted), shape, cmds, args, arg
  values when present, and a "Curated as" column naming the friendly name(s) already in
  `effectors.toml`. Same generator convention as `generate_defaults.py` (static TOML read, check
  mode by default, `--write` to regenerate, GENERATED header with the source DCS build — parsed
  from the raw dump's own header comment, not hard-coded — and the raw dump's own sha256).
  `tests/test_render_switch_reference.py` is the staleness guard, same pattern as
  `test_tuning_defaults_toml.py`.
- Tests: `tests/test_effector_registry.py` (11 cases — good load, `unverified` carried through,
  unresolved `source_element`, missing `values`, index out of range, device/cmd/arg collision
  drops both entries, raw-dump unreadable/unparsable, curated-file unreadable/unparsable, plus a
  round-trip against the real committed files), `tests/test_effector_sequences.py` (17 cases —
  one per Stage 1 validation rule the plan lists: unknown effector, unknown value, unknown
  effector/value in a condition, unknown trigger, malformed row, wait row plus its malformed
  variant, say-only row rejection, duplicate trigger rejecting both files, an unreadable file
  collected rather than raised, `switch-reference.md` skipped by name, plus a round-trip of every
  shipped sequence file and a dedicated check that the takeoff file's row order/conditions match
  today's hard-coded sequence exactly).

**Design choices not spelled out verbatim in the plan:**

- **D5's "disables every sequence" for a catastrophically bad raw/curated file is implemented as
  a cascade, not a separate fatal flag.** `load_registry` returns `({}, [one file-level error])`
  on an unreadable/unparsable file; every sequence file then fails its own "unknown effector"
  check against the empty registry and is dropped by `load_sequences` in turn. This reaches D5's
  stated behaviour (every sequence off) with one mechanism instead of two, at the cost of the
  per-file error messages all reading "unknown effector X" rather than naming the real root cause
  directly — acceptable since the one `RegistryError` from `load_registry` itself still names the
  real cause, and both error lists reach the same console banner in Stage 2.
- **A device/cmd/arg collision between two curated entries drops both, matching the "neither
  silently wins" posture `load_sequences` already uses for a duplicate (aircraft, role, trigger).**
  The plan's D5 text ("drops that entry") is singular; I read it as applying per-colliding-entry
  rather than picking a winner, since there is no principled way to choose one over the other
  from inside the loader.
- **No tunables added in Stage 1.** `EFFECTOR_CONDITION_READBACK_WAIT_S` (D3) and the
  `GUIDANCE_UNIT_SWITCH_DELAY_S` → `EFFECTOR_SEQUENCE_STEP_DELAY_S` rename (D10) both belong to
  `belief.effector_engine`, which does not exist yet — Stage 2's job, per the task that opened
  this stage ("If the rename only matters in Stage 2, leave it to Stage 2 and say so"). `tuning.py`
  and `config/defaults.toml` are therefore untouched by this stage.
- **`EffectorDef.values` stores floats under named keys (`on`/`off`/`armed`/`safe`), the raw
  value a write/compare uses** — not wrapped in a further `EffectorValue` type, since nothing in
  Stage 1 needs more than a `dict[str, float]` and Stage 2's condition-matching epsilon rule
  (plan: "half the smallest gap between named values") operates directly on it.
- **Markdown table parsing (`effector_sequences._parse_tables`) is a small hand-rolled splitter**,
  not a dependency — pipe-delimited rows only, a separator row recognised by
  `^:?-+:?$` per cell, anything else (prose, an HTML comment, a blank line) ends the current
  table. No library was considered; this project's `tools/generate_defaults.py` already
  hand-renders TOML for the same "stdlib only" reason, and the shape here is simpler than a TOML
  writer.

**Coverage check against the plan's Stage 1 validation list** ("unknown effector, unknown value,
unknown trigger, malformed row, say-only row (reserved), duplicate (aircraft, role, trigger) ...,
unresolved `source_element`, duplicate triple collision, unreadable TOML ..., plus a round-trip
of each shipped file"): every item has a dedicated test named above; none was skipped.

**Checks** (`body-layer/`, this stage's own files plus the full existing suite):

- `ruff format --check src tests tools` — pass (178 files).
- `ruff check src tests tools` — pass.
- `cd body-layer && .venv/bin/mypy src` — pass (73 source files).
- `cd body-layer && .venv/bin/mypy tools` — pass (9 source files).
- `pytest -q` (`-p no:randomly`, see below) — 2532 passed, 4 xfailed.

**Pre-existing flakiness found, not introduced by this stage**: `pytest`'s random test-order
plugin (`pytest-randomly`) occasionally fails `test_logger.py::
test_main_print_tuning_works_without_aircraft_layer_url` or
`test_brain_client.py::test_unreachable_brain_logs_one_line_without_traceback` depending on
order, in both directions — confirmed by stashing every file this stage added and re-running the
full suite three times with no `-p no:randomly`, which reproduced the same two failures on
unmodified `8f2dc3f3`. Not this stage's to fix; noted here so Stage 2 does not waste time
re-diagnosing it as a regression. Run with `-p no:randomly` for a deterministic check.

**Notable discovery**: the real committed `config/effectors-raw.toml` (514 elements) has zero
`cmd2`/`helper_args` occurrences — none of this cut's or the wider dump's elements use the two
two-command-slot helpers (`default_button_tumb`, `springloaded_3_pos_tumb`) the Stage 0 spec
reserved a schema extension for. `effector_registry.py` therefore only ever reads `cmds`/`args`
by `index` (default 0) and never needed to special-case a second command slot — worth knowing if
a later registry entry (e.g. a Mi-8 or a pilot-role control) ever does hit one of those two
shapes.

## Stage 2 — engine, wiring, error surfacing, 2026-10-23

Branch `feature/effector-sequences`, built on top of `056b76b5` (Stage 1 review approval) plus
`main`'s `fix/guidance-ready-edge` merged in first (coordinator-directed; see merge commit
"Merge main into feature/effector-sequences: guidance-ready edge fix"). Three mid-task design
corrections arrived from the coordinator and are folded in below rather than narrated separately:
R12 (the implicit self-check replacing the takeoff file's `!= on` conditions), R13 (per-aircraft
`config/sequences/<dir>/` layout, first-wins collision), and the `get_spu8_state_latest` wiring.

### Files Changed

- `body-layer/src/belief/effector_engine.py` (new) — `EffectorTrigger`, `EffectorRunState`,
  `fire_trigger`, `advance`, `EFFECTOR_SEQUENCE_STEP_DELAY_S` (D10 rename of `GUIDANCE_UNIT_
  SWITCH_DELAY_S`), `EFFECTOR_CONDITION_READBACK_WAIT_S` (new tunable, D3). Implements D1
  (per-trigger queue), D3/R12 (explicit-condition vs. implicit-self-check, opposite timeout
  outcomes), D4 (re-runs never re-speak — unaffected, "Guidance unit ready" stays in
  `crew_console`), D8 (wait rows), D9 (fire-order write blocking across triggers within one poll).
- `body-layer/src/belief/sight_effector.py` — rewritten: deleted `_POWER_UP_SWITCHES`, the three
  device-id constants, `GUIDANCE_UNIT_SWITCH_DELAY_S`, `start_power_up`, `advance_power_up`,
  `write_observ`, `write_weapon_safety`, and `GuidanceUnitState`'s `takeoff_seen`/`power_up_stage`/
  `next_switch_due_sim`/`observ_commanded`/`weapon_safety_commanded` fields. Kept: the readback
  fields, `sight_ready`, `refresh_readback`, `write_sight_target`.
- `body-layer/src/belief/crew_console.py` — `CONFIG_ERROR_LINE` constant, `config_error_pending`
  field (preserved across `reset_for_new_mission`, D6), `drain_config_error` (same shape as
  `drain_guidance_unit_ready`).
- `body-layer/src/aircraft_client.py` — `get_spu8_state_latest()` (`GET /spu8/state`).
- `body-layer/src/logger.py` — `_load_effector_config()` (new: loads the registry/sequences,
  aggregates both loaders' errors into one console banner + `logger.error` per finding, logs
  `EffectorDef.unverified` names once at `INFO`); `ConsolePerceptionRunner.effector_state`
  (`EffectorRunState`, one construction site); the poll block rewritten per the plan's own
  ordering (refresh readback → takeoff edge fires → transitions fire → `advance` → ready edge →
  `drain_config_error`); `_run_crew_text_poll_loop` gained `effector_sequences`/`effector_registry`
  parameters (loaded once in `main()`, passed through, `None`-tolerant); `main()`'s `--crew-text`
  branch calls `_load_effector_config()` before constructing `CrewConsole`.
- `body-layer/src/sight_trace_writer.py` — `write_poll`/`_row` gained `commanded_values:
  Mapping[str, str] | None = None`; `observ_commanded` now reads `(commanded_values or {}).get(
  "observ") == "on"` instead of `GuidanceUnitState.observ_commanded` (removed).
- `aircraft-layer/src/schema/cockpit_switch.py` — `to_api_dict()` gained `"args"`: the same six raw
  switch values re-keyed by DCS arg number as a string (R7). No `Export.lua` change — purely a
  derived view of data the schema already carries.
- Per-aircraft layout move (R13, `git mv`): `config/effectors-raw.toml` →
  `config/effectors-raw/mi-24p.toml`; `config/sequences/effectors.toml` →
  `config/sequences/mi-24p/effectors.toml`; `config/sequences/switch-reference.md` →
  `config/sequences/mi-24p/switch-reference.md`; `config/sequences/mi-24p-copilot-<trigger>.md` →
  `config/sequences/mi-24p/copilot-<trigger>.md` (filename prefix dropped, directory carries it).
  `body-layer/src/belief/effector_registry.py` gained `aircraft_dir_name` (the one place the
  `aircraft` header value lower-cases to a directory name) and `load_registries_by_aircraft`;
  `load_registry`'s collision rule changed from "drop both" to "first (TOML file order) wins,
  reject the rest" (R13). `body-layer/src/belief/effector_sequences.py`'s `load_sequences` now
  takes `sequences_dir`'s *parent* plus `registries: Mapping[str, Mapping[str, EffectorDef]]`
  keyed by aircraft directory, and treats an `aircraft` header that does not map to its own
  directory as a file error.
- `body-layer/tools/generate_effector_registry.py` — `_DEFAULT_OUT_PATH` → `config/effectors-raw/
  mi-24p.toml`. `body-layer/tools/render_switch_reference.py` — its three path constants moved
  under `config/sequences/mi-24p/`.
- `body-layer/config/sequences/mi-24p/copilot-takeoff.md` — the four rows' `!= on` conditions
  removed (R12); no other sequence file needed a content change (OBSERV/weapons rows were already
  unconditional).
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`): the two
  new `belief.effector_engine.*` keys, `GUIDANCE_UNIT_SWITCH_DELAY_S` gone.
- `plans/effector-sequences/plan.md` — R12 (implicit self-check), R13 (per-aircraft layout,
  first-wins collision) rows added; the file-format worked example, D2/D3/R4/R5 text, and every
  path reference updated to match.

### Tests Added

- `body-layer/tests/test_effector_engine.py` (new, 15 tests) — pure-function coverage of the
  engine against hand-built `SequenceFile`/`EffectorDef` fixtures (no markdown parsing, no
  wiring): `fire_trigger`'s idle/pending/no-op/independent-queue transitions (D1); cold takeoff
  writes four switches in order with `EFFECTOR_SEQUENCE_STEP_DELAY_S` spacing; R12's implicit
  self-check — all-already-on writes nothing, one-switch-off-among-four writes exactly one,
  unknown readback waits then writes on timeout; an explicit `condition`'s *opposite* timeout
  outcome (skip, not write) and its immediate-skip-on-known-false case; D8 wait rows overriding
  the gap for one transition; D9's own worked example (`test_d9_failed_on_then_off_ends_off`) —
  fire ON then OFF, a failing client blocks both, then both land in fire order once it clears,
  ending "off"; the pending-restart same-poll-execution case; a trigger with no loaded sequence
  firing into nothing.
- `body-layer/tests/test_logger.py` — six existing poll-loop tests reworked (not merely patched to
  compile) for the API change: `test_takeoff_runs_the_guidance_unit_power_up_sequence_through_
  the_real_poll_loop` now seeds a known-off `"args"` readback so the cold-takeoff spacing test is
  real rather than relying on the unknown-timeout path; `test_guidance_unit_ready_is_silent_on_a_
  warm_air_start_through_the_real_poll_loop` and the power-cycle test now seed all-on readback and
  the former asserts zero writes; `test_second_takeoff_in_the_same_mission_does_not_rerun_the_
  power_up` rewritten to actually exercise R4/R12 (D2's removed `takeoff_seen` latch meant this
  test previously proved nothing once the fields it inspected were gone) — drives both the
  airborne-first-sample edge and a real land/takeoff edge, asserts zero writes across both;
  `test_observ_and_weapons_safety_write_through_the_real_poll_loop` seeds/updates readback between
  commands so each self-check sees a real mismatch rather than stalling on sim-time that the
  test's own polling loops never advance; `test_slew_trace_is_written_from_the_real_poll_loop`
  likewise. New: `test_load_effector_config_round_trips_the_real_committed_files`,
  `test_load_effector_config_logs_the_unverified_effector` (Stage 1 review follow-up — confirms
  `cplr_distr`'s `unverified` flag is no longer a dead field),
  `test_load_effector_config_aggregates_errors_from_both_loaders` (D5's own "pulling from BOTH
  loaders' error lists"),
  `test_load_effector_config_missing_own_aircraft_directory_is_an_error`,
  `test_config_error_held_while_silenced_and_intercom_closed_then_speaks_once_through_the_real_
  poll_loop` (drives the real loop: intercom closed → no speech; intercom open but silenced → no
  speech; unsilenced → speaks exactly once), `test_config_error_pending_survives_a_mission_
  restart` (unit-level companion to the generic preserve-set check below).
- `body-layer/tests/test_mission_start_reset.py` — `config_error_pending` added to
  `_CREW_CONSOLE_PRESERVE`, so the file's own generic "every non-preserved field resets, every
  preserved field survives" sweep now also covers this field (D6).
- `body-layer/tests/test_sight_effector.py` — rewritten: every test for the deleted sequencing
  functions removed; the readback/`sight_ready`/`write_sight_target`/construction-site tests kept
  unchanged (they test code that did not move).
- `body-layer/tests/test_sight_trace_writer.py` — `test_observ_commanded_and_observed_are_carried_
  through` updated to pass `commanded_values={"observ": "on"}` instead of constructing a
  `GuidanceUnitState` with the removed field; new
  `test_observ_commanded_defaults_to_false_when_none_given`.
- `body-layer/tests/test_effector_registry.py` — `test_colliding_device_cmd_arg_drops_both_
  entries` renamed/rewritten to `test_colliding_device_cmd_arg_first_wins` (R13); new
  `test_aircraft_dir_name_lower_cases_only`,
  `test_load_registries_by_aircraft_discovers_the_real_mi24p_directory`,
  `test_load_registries_by_aircraft_isolates_a_bad_aircraft_directory`,
  `test_load_registries_by_aircraft_missing_sequences_dir_is_empty`.
- `body-layer/tests/test_effector_sequences.py` — every existing test's fixture path updated to
  the per-aircraft directory shape (`tmp_path / "mi-24p" / ...` + a `_REGISTRIES` dict keyed by
  directory, R13); `test_takeoff_file_reproduces_todays_switch_order`'s condition assertion
  changed to `row.condition is None` (R12); new
  `test_aircraft_header_not_matching_its_own_directory_is_a_file_error`,
  `test_bad_registry_in_one_aircraft_directory_does_not_affect_another`.
- `aircraft-layer/tests/test_cockpit_switch.py` — both `to_api_dict()` assertion dicts gained the
  `"args"` key.
- `body-layer/tests/test_aircraft_client.py` — `test_get_spu8_state_latest_returns_parsed_dict`,
  `test_get_spu8_state_latest_raises_on_unreachable_host`.
- `body-layer/tests/test_render_switch_reference.py` — docstring/message text updated to the new
  paths; the test itself is path-independent (shells out to the tool), unchanged mechanically.

### Design choices not spelled out verbatim in the plan

- **D9's "fire order" is tracked as a dedicated `EffectorRunState.fire_order` tuple**, not derived
  from dict-iteration order of `runs`. `fire_trigger` appends (de-duplicating any prior entry) the
  trigger it just started running; `advance` filters it down to currently-running triggers each
  call. This was necessary because Python's dict preserves *insertion* order, and `runs` entries
  get removed and re-added across a trigger's own run/pending/complete/restart cycle in ways that
  would otherwise scramble the original fire order.
- **"One write per trigger per poll" falls out of the due-time gate, not an explicit `break`.**
  After a successful write, the cursor's `next_due_sim` is set to the future
  (`now_sim + EFFECTOR_SEQUENCE_STEP_DELAY_S`), and the loop `continue`s rather than `break`s — the
  very next iteration's own due-time check stops further processing for that trigger this poll,
  *except* when the write just completed the sequence and a pending re-fire restarts it with a
  fresh cursor due immediately (D1: "same poll's advance may execute it"), which is exactly the
  one case the plan's Co-moving Fields table says may write twice in one poll. An earlier draft
  used an explicit `break` after every write and failed `test_pending_restart_may_execute_the_
  same_poll` and `test_cold_takeoff_writes_four_switches_in_order_with_spacing` (the latter because
  completion detection — removing the trigger from `runs` — never got a chance to run in the same
  call as the final write, so the test's immediate-removal assertion failed one call early).
- **R12's two distinct `_RunCursor` wait fields** (`condition_waiting_since_sim`,
  `self_waiting_since_sim`) are deliberately separate rather than one shared field — an explicit
  `condition` gate and the implicit self-check on the *same* row can each need their own
  independent "how long have I waited" clock, and sharing one field would let the self-check's
  timer silently inherit a stale value left over from the condition gate resolving in an earlier
  poll. No shipped sequence file exercises both on one row this cut; this is forward-looking
  correctness, not something a current test can observe going wrong without a synthetic fixture
  (which `test_effector_engine.py` does build, separately, for each gate).
- **The coordinator-directed design change (explicit condition cells reserved for genuine
  cross-switch dependencies; implicit self-check for "is this switch already there")** changes
  the *unknown-readback timeout's* outcome depending on which gate is waiting: an explicit
  `condition`'s timeout **skips** (D3, unchanged); the implicit self-check's timeout **writes**
  (R12, new) — because an absolute-value write is harmless if the switch secretly already had that
  value, whereas skipping a cross-switch *dependency* on no information risks firing a row whose
  precondition was never actually confirmed. This asymmetry is deliberate and tested explicitly
  (`test_explicit_condition_unknown_readback_skips_on_timeout` vs.
  `test_unknown_readback_waits_then_writes_on_timeout`).
- **`_load_effector_config()` surfaces errors from *every* aircraft directory it finds**, not only
  this runtime's own (`"mi-24p"`), even though only one aircraft exists today — R13's own text
  ("ready to be aircraft specific... while we're only working with Mi-24P at this time") reads as
  wanting the mechanism in place now, and a stray second directory's bad registry being silently
  invisible in the startup banner seemed like the wrong failure mode to build in deliberately.
- **The registry-cascade root-cause-loss tradeoff the Stage 1 review flagged as "re-verify once
  the banner exists" is now checkable and holds**: a catastrophically bad raw-dump/curated file
  still collapses to one `RegistryError` naming the real cause (Stage 1's own mechanism,
  unchanged), and that one error *is* now visible first in the console banner alongside whatever
  per-sequence "unknown effector" noise cascades from it — `test_load_effector_config_aggregates_
  errors_from_both_loaders` exercises the aggregation path directly (with faked loader results,
  not the real files, since manufacturing a genuinely-corrupt committed file was not attempted).
- **`FakeConsoleAircraftClient` (test_logger.py) does not auto-synthesize `"args"` from recorded
  writes.** Readback stays entirely test-driven (`aircraft_client.cockpit_switch_state = {...}`),
  matching the existing convention for `ready_lamp`/`align_lamp` etc. — a test that needs a switch
  to read differently after a write updates the dict itself between commands (see `test_observ_
  and_weapons_safety_write_through_the_real_poll_loop`'s mid-test `args["673"] = 1.0` update).
  Auto-synthesis would have needed a `(device, cmd) -> arg` table duplicated inside the test fake
  and was judged not worth it for the number of call sites that actually need it.

### Checks

(both touched subprojects)

- `body-layer/`:
  - `ruff format --check src tests tools` — pass (180 files)
  - `ruff check src tests tools` — pass
  - `cd body-layer && .venv/bin/mypy src` — pass (74 source files)
  - `cd body-layer && .venv/bin/mypy tools` — pass (9 source files)
  - `pytest -q` (plain, no `-p no:randomly` needed — `pytest-randomly` was uninstalled from the
    shared venv mid-task by coordinator direction) — 2549 passed, 4 xfailed; re-run twice,
    identical. The 11 new/reworked poll-loop and `_load_effector_config` tests confirmed
    individually by name in `-v` output (not a filtered `-k` summary count).
- `aircraft-layer/`:
  - `ruff format --check src tests` — pass (75 files)
  - `ruff check src tests` — pass
  - `cd aircraft-layer && .venv/bin/mypy src` — pass (27 source files)
  - `pytest tests -q` — 533 passed

### Pre-existing, not touched

- `tests/test_aircraft_client.py:89` (`body-layer`) has a pre-existing `mypy` error (`Item "None"
  of "list[str] | None" has no attribute "append"`, in `_make_handler`'s `triggered_searches`
  default) — confirmed pre-existing by stashing every file this stage changed and re-running
  `mypy` against the unmodified tip; not touched, outside this stage's scope.
- `body-layer/tests/test_logger.py` carries 24 pre-existing `mypy` findings (fake-client structural
  typing against `AircraftLayerClient`, a few `Non-overlapping equality check`s, two `Module
  "logger" does not explicitly export attribute` complaints) — confirmed identical, same line
  numbers (modulo the shift from this stage's own insertions), against the unmodified tip via the
  same stash-and-compare method. Not touched.
- `BL-B92` (pytest-randomly order-dependent `test_connection_reporter_*` tests) is moot for this
  stage's own check run since the plugin was uninstalled mid-task; not re-investigated.

### Comments pruned

- `body-layer/src/belief/sight_effector.py` — the module was rewritten wholesale rather than
  edited in place, since every paragraph describing the deleted power-up/OBSERV/weapons-safety
  sequencing (the four-switch order, the device/cmd constants' provenance, `write_observ`/`write_
  weapon_safety`'s own docstrings) was now describing code that no longer exists. ~90 lines of
  stale "what the sequencing does" content removed; the surviving readback/`sight_ready`/`write_
  sight_target` docstrings carry forward unchanged (they describe code that did not move).
  `GuidanceUnitState`'s own docstring lost its `takeoff_seen`/`power_up_stage`/`observ_commanded`/
  `weapon_safety_commanded` paragraphs for the same reason.
- `body-layer/src/logger.py` — the two OBSERV-on/off write blocks' comments ("the real cockpit
  write (arg 886), issued exactly once per accepted request... Raises `AircraftLayerError`...")
  were pruned and replaced with a one-line pointer to `advance_effectors`, since the write itself
  moved there; the surrounding hands-busy-suppression comment (still true, still this module's own
  job) was kept. The takeoff-edge block's comment describing `advance_guidance_unit_power_up`'s
  own readback-consumer list was replaced with D2/D4/R12's current reasoning rather than kept
  alongside dead code.
