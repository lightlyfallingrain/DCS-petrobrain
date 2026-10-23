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
