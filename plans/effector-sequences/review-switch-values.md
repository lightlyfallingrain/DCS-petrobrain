### Review Summary

Reviewed `feature/switch-reference-values` at `cc1520009a03a20d5f424ce956f7f254b2ced54a`
(diff `27c19054..cc152000`) against `aircraft-layer/research/
2026-10-23-mi24p-clickable-value-ranges.md`, `plans/effector-sequences/implementation.md`'s
"Switch reference values" section, and `plans/effector-sequences/stage0c-run.md`.

Checked all 22 `_HELPER_SIGNATURES` entries' `_value_range_for_helper` rules against the research
note's positional-parameter table, by hand and by mutation. Checked the raw-table-literal path
(`class`/`arg_lim`/`gain` parsing, the `BRAKE-LEVEL-OP-PTR` NULL-class and
`ILS-ADJUST-HANDLE-PTR` cases), the post-assignment `arg_lim` patch and the deliberate
non-application of `arg_value` patches, the `EffectorTrigger` merge into
`effector_sequences.py` with re-export from `effector_engine.py`, and `triggers.md`'s
descriptions against the actual firing code in `logger.py`/`crew_console.py`.

All checks (`ruff format --check`, `ruff check`, `mypy --strict` on `src` and `tools`, `pytest`)
pass clean: 2584 passed, 4 xfailed; 183 files formatted; mypy clean on 74 + 10 files.

**One genuine (currently dormant) correctness bug** and **one real mutation-coverage gap** in
the new value-range logic, both in the same class of defect this project has already paid to
fix once in this file (`_HELPER_SIGNATURES`'s own "only 3 of 22 entries tested" finding, same
docstring). Two cosmetic/optional issues besides.

### Required Fixes

- **`default_1_position_tumb`'s default `arg_lim_` is wrong when `arg_val_` is given but
  `arg_lim_` is not.** The research note (row 36) documents this helper's default as
  `arg_lim_ or {0, arg_val_}` — distinct from `default_spring_button`/`default_position_tumb`,
  whose documented default is the fixed `{0,1}`. `generate_effector_registry.py`'s
  `_value_range_for_helper` groups all three under one `lim_offset` dict and one shared fallback,
  `lo, hi = lim if lim is not None else (0.0, 1.0)` (lines ~339-348) — so a call that sets a
  custom `arg_val_` (e.g. `2`) but omits `arg_lim_` silently gets `(0.0, 1.0)` instead of the
  documented `(0.0, 2.0)`. Verified live:
  ```
  default_1_position_tumb(hint, dev, cmd, 500, anim_speed_default, 2, nil, nil)
  -> value_ranges = (discrete (0.0, 1.0),)   # should be (0.0, 2.0) per the research note
  ```
  **Currently dormant** — the research note confirms this helper is never called in the real
  module, so no element in the committed 514-element dump is affected, and `--write` cannot
  silently ship a wrong value today. But the whole point of this generator's "fails closed, at
  two levels" design is to never let a documented rule and the code's own behaviour drift apart
  unnoticed, and this is exactly that drift, in the one helper whose default does not match the
  shared fallback it was grouped with. Fix: special-case `default_1_position_tumb`'s fallback to
  `(0.0, arg_val_ if arg_val_ is not None else 1.0)` rather than the flat `(0.0, 1.0)`, and add a
  test exercising a custom `arg_val_` with no `arg_lim_` (none exists today).

- **Mutation-coverage gap in `_value_range_for_helper`'s grouped `if helper in (...)` branches** —
  the same failure class this file's own `_HELPER_SIGNATURES` test comment already documents
  ("mutating an untested entry... left the whole suite green"), now reappearing one function
  down. Removing `"default_blue_cover"` from its group (the momentary-vs-latching 0/1 block) and
  re-running the full `test_generate_effector_registry.py` suite leaves it **84/84 green** — the
  mutation silently changes that element's value range from `discrete(0.0, 1.0)` to
  `unknown("no value-range rule for helper 'default_blue_cover'")` with no test failing. The same
  almost certainly holds for `default_CB_button`, `default_tumb_button`,
  `default_square_button`, `stick_button`, `default_2_position_small_tumb`,
  `default_2_position_flares_tumb`, `default_spring_button`, `default_position_tumb`,
  `radio_wheel_1` — none of the 22 helpers has a dedicated value-range test beyond the ones
  explicitly named in the "Tests Added" list (`default_button`, `default_2_position_tumb`,
  `default_3_position_tumb`, `multiposition_switch`, `triple_switch`, `default_axis(_limited)`,
  `default_animated_lever`, `springloaded_3_pos_tumb`). The fail-closed posture limits the blast
  radius of a mutation here to "silently downgraded to unknown" rather than "silently wrong," which
  is a real mitigation, but it's still an untested claim for roughly a third of the helper table.
  Given this project's own precedent for this exact gap, add one assertion per remaining helper
  (a loop over `_HELPER_SIGNATURES` building a minimal call per helper and asserting the expected
  `ValueRange`, mirroring `test_helper_signatures_positional_crew_and_command_count`'s pattern,
  would cover all of them in one test rather than nine near-duplicates).

### Optional Refinements

- **`render_switch_reference.py`'s Values column renders a negative-lower-bound continuous range
  ambiguously**: `-1-1 continuous (gain 0.1)` (verified by rendering a synthetic fixture
  reproducing `COLLECTIVE-CORR-PTR`'s real -1..1 range). Read quickly it looks like a typo or a
  single number, not a range from -1 to 1 — exactly the readability bar the task called out
  ("is the Values notation readable to a pilot writing a sequence file?"). A separator that
  survives a negative lower bound (e.g. `-1 to 1 continuous`, or `[-1, 1] continuous`) would read
  unambiguously in every case, not just the non-negative ones the existing tests happen to cover
  (`test_continuous_without_gain`'s own `-1-1 continuous` is already the ambiguous form, just
  never flagged as such). Low cost, not blocking — this is a UX polish on a column that is blank
  on every real row until the Windows rerun anyway.
- **`render_switch_reference.py`'s rendered "Source:" line is stale** (`"config/effectors-raw.toml"`,
  line 198) — the real path has been `config/effectors-raw/mi-24p.toml` since Stage 2's R13
  per-aircraft split, and the generated `switch-reference.md` currently ships the wrong path in
  its own header. Pre-existing, not introduced by this diff, and purely cosmetic (the staleness
  test checks content equality, not this string) — worth a one-line fix next time this file is
  touched.
- **A stray orphaned line at the very end of `plans/effector-sequences/implementation.md`**
  (`    existing test extended, no test added or removed)`, introduced by this diff) — an
  apparent copy-paste leftover from the "Checks" section earlier in the same file. Harmless
  (plan files aren't code), but worth trimming.

### Verdict

APPROVED WITH MINOR FIXES

The two Required Fixes are both narrow, low-blast-radius (one dormant on a never-called helper,
one a test-coverage gap whose failure mode is already fail-closed to "unknown" rather than
"wrong"), and match a defect class this same file has already named and partially fixed once.
Neither blocks merge on its own if the user wants this on the Windows-rerun path now and the
fixes queued as a fast follow — but given the project's own "never guessed" design intent for
this exact generator, I'd want them closed before the next real DCS regeneration is trusted
blind. Everything else — the 20 other helper rules, the raw-literal path, the post-assignment
patch logic (including the `arg_value`-does-not-change-`values` claim, confirmed correct and
well-tested), the `EffectorTrigger` merge/re-export, and every `triggers.md` description checked
against the firing code — is correct and well covered.

### Review Confidence

Full read of both generator tools (`generate_effector_registry.py`, `render_switch_reference.py`,
`render_triggers.py`), the research note, and the relevant plan sections. Mutation-tested the
`_HELPER_SIGNATURES`-grouped branches (one confirmed gap, `default_blue_cover`) and the
`default_1_position_tumb` default coupling directly against a synthetic call (confirmed bug).
Did not mutation-test every one of the other ~20 helper rules individually — the one Required
Fix above asks for exactly that coverage, so closing it will also answer whether a second latent
mismatch exists elsewhere in the group. The real `config/effectors-raw/mi-24p.toml` dump has no
`values` field yet (expected — awaits the Windows rerun per `stage0c-run.md`), so the Values
column's real-world content could not be read from the committed file; readability was checked
against the unit tests' synthetic cases and one hand-built fixture instead.

---

## Fix re-review, 2026-10-23

Re-reviewed `c13ec5c1` (fix pass) against this review and the real-run findings it addresses, at
tip `e4f2915d` (`c13ec5c1` + a parallel explore-notes commit on mission-start triggers, out of
scope for this pass — not reviewed, and not touched by this diff). `git diff 97ad4e3a c13ec5c1`:
9 files, `generate_effector_registry.py`, `render_switch_reference.py`,
`effector_sequences.py`/`triggers.md`, both test files, the two generated config files, the
research note, and `implementation.md`.

**Both Required Fixes verified closed, by mutation, not just by reading the diff:**

- **`default_1_position_tumb`'s default `arg_lim_`** now special-cases to
  `(0.0, arg_val_ if arg_val_ is not None else 1.0)` (lines ~466-477), reading `arg_val_` one
  offset before `arg_lim_` per the research note's row 36. Three new tests cover: no-`arg_val_`
  stays `(0,1)`; a custom `arg_val_` (`2`) with no `arg_lim_` changes the upper bound to `2.0`;
  an unresolvable `arg_val_` is `"unknown"`, never a silent fallback. The implementer's own
  mutation log (disabling the branch, both new tests failing as expected, restored by checksum)
  is consistent with what I read in the code.
- **Mutation-coverage gap closed**: `test_value_range_for_every_helper_signature_minimal_call`
  now iterates all 22 `_HELPER_SIGNATURES` entries via one minimal call each, asserted against
  an independently-transcribed `_EXPECTED_DEFAULT_VALUE_RANGES` table (verified the two sets are
  equal, `set(_EXPECTED_DEFAULT_VALUE_RANGES) == set(gen._HELPER_SIGNATURES)`, so no helper can
  silently drop out of coverage the way `default_blue_cover` did). **Re-ran the
  `default_blue_cover` mutation myself** — removed it from its `_discrete([0.0, 1.0],
  momentary=False)` group (line ~444), ran `test_generate_effector_registry.py`: the new test
  fails with exactly the predicted `discrete` → `unknown` downgrade (`1 failed, 93 passed`).
  Restored the file (confirmed byte-identical via `diff` against a pre-mutation copy), re-ran:
  `94 passed`. The fix holds.

**New real-run findings (arithmetic, NULL class, `radio_wheel_1`, rounding, unknowns reporting),
checked against the amended research note and the code:**

- **Safe arithmetic evaluator** (`_eval_constant_arithmetic`/`_lua_arithmetic`/`_ARITHMETIC_BINOPS`):
  an AST whitelist over `ast.Constant` (numeric only, explicitly excluding `bool`), `ast.UnaryOp`
  with `ast.USub`, and `ast.BinOp` restricted to `(Add, Sub, Mult, Div)` — no `eval` anywhere, and
  `ast.Pow` is not in the whitelist, so `**` falls through to the final `return None` rather than
  being evaluated (confirmed by reading `_ARITHMETIC_BINOPS`'s definition and the fallthrough at
  the end of the function) — no exponent of any size can be computed, so there is no hang/crash
  surface from large exponents, and none from the evaluator being asked to do anything but
  `+ - * /` on literals. `ast.Name`/`ast.Call`/everything else hits the same fallthrough, so a
  real identifier or a function call is rejected, never silently substituted. Division by zero:
  `_lua_arithmetic` wraps the *entire* top-level evaluation in one `try/except ZeroDivisionError`
  outside the recursive walk, so a `0` denominator anywhere in a nested expression (e.g.
  `1 / (2 - 2)`) propagates up through the recursion untouched and is caught once at the top —
  verified this structurally holds by reading the call shape, not just trusting the single-level
  test case. **Animation-only identifiers do not make a value unknown**: the anim-speed argument
  sits at a different helper offset than the value-affecting ones (`delta_`/`gain_`/`arg_val_`),
  so an identifier like `anim_speed_default` passed as the *animation* parameter is never routed
  through `_lua_scalar` for a value-range computation at all — confirmed directly by
  `test_default_1_position_tumb_default_arg_lim_uses_custom_arg_val`, whose call text carries
  `anim_speed_default` in the anim slot and still resolves to a clean `discrete (0.0, 2.0)`, and
  by `test_multiposition_switch_steps_from_count_delta_min`/`..._fractional_delta_is_evaluated`,
  both of which also carry `anim_speed_default` in the anim slot alongside a literal/arithmetic
  `delta_` and resolve cleanly. The *value*-position identifier case (`anim_speed_default / 5` as
  `delta_` itself) is correctly the opposite: `test_multiposition_switch_unresolvable_delta_
  expression_is_unknown` confirms that one is `"unknown"`, as it must be — these are two
  different parameters, not a contradiction. Agree with this split.
- **NULL-class `"none"` kind**: `ValueKind.NONE`, `_none_value()`, and
  `_value_ranges_for_raw_literal`'s `elif kind == "NULL": result.append(_none_value())` branch,
  ahead of the generic `unhandled raw-literal class` fallback. Rendered as `"—"` in
  `render_switch_reference.py`. `test_raw_table_literal_null_class_action_is_none_not_unknown`
  exercises `BRAKE-LEVEL-OP-PTR`'s own shape directly; `test_none_kind_renders_as_an_em_dash`
  covers the render side. Correct and matches the amended research note's point 3.
- **`radio_wheel_1`: relative, stepped.** Now emitted via the `relative=True` branch in `_discrete`
  rather than `_continuous`, with step count derived from `(hi - lo) / step_size`, and two guard
  clauses (`step_size <= 0`, `n_steps < 0`) that fail to `"unknown"` rather than raising or
  producing a garbage range. Both the explicit-args and default-args cases are tested
  (`test_radio_wheel_1_is_relative_discrete_not_continuous`/`..._default_step_and_limit`), and the
  render side is covered by `test_relative_discrete_list_is_marked`. Matches the amended research
  note's point 2.
- **Rounding**: `_VALUE_ROUND_NDIGITS = 6`, `_round_value`, applied once at construction in
  `_discrete` (every value, via a set comprehension before `sorted`) and `_continuous`
  (`min`/`max`/`gain`) — computed once at the point of computation, not re-applied by every
  downstream reader, matching the module's own stated design posture elsewhere in this file.
  `test_default_axis_arithmetic_gain_is_evaluated_and_rounded` checks the rounding directly
  (`vr.gain == round(vr.gain, 6)`), not just that the value is approximately right.
- **Unknowns in the run report and header, exit 0**: `_unknown_value_ranges` walks every handled
  element's `value_ranges` for `kind == ValueKind.UNKNOWN`, printed as a count in both `main`'s
  stdout summary and the TOML header's `# Elements:` comment line, and listed in full (element,
  action index, reason) in the stdout report. **Agree with exit 0.** Confirmed by reading `main`:
  nothing gates the return value on `unknown_value_ranges` — only `unhandled` (without
  `--allow-unhandled`) does, same posture as `ignored`/`n_post_assigns`. This is consistent with
  the module's own documented design ("fails closed, at two levels" — the `ValueRange` level
  already fails closed to `"unknown"`; making the whole run fail over it would be a second,
  redundant refusal at a coarser grain, for a condition that already can't silently ship wrong
  data). Confirmed live against the `clean` fixture (which has one `default_button_tumb`-caused
  unknown): `--scripts-dir tests/fixtures/effector_registry/clean` (report mode) prints `1 value
  range(s) unknown` in the summary line, the element/action/reason beneath it, and (in `--write`
  mode) the TOML header carries `Value ranges unknown: 1 (see the run report).` — the mechanism
  works exactly as described.
  - **Gap, not required**: no test asserts any of this wiring. `test_clean_fixture_report_mode_
    exits_zero_and_writes_nothing` only checks `"9 emitted, 0 unhandled"` in stdout, and
    `test_clean_fixture_write_mode_produces_loadable_toml` checks the header's `Statements
    ignored: 1` line but not the adjacent `Value ranges unknown: 1` one, even though the `clean`
    fixture exercises both (confirmed live above). The code is correct and the behaviour is
    simple string-count plumbing off data this file already computes elsewhere, which is why this
    is not a required fix — but it is new, user-visible output with zero assertion coverage,
    worth closing opportunistically (one `assert "1 value range(s) unknown" in result.stdout`
    and one `assert "Value ranges unknown: 1" in rendered`, both in the existing end-to-end tests
    at lines ~798/818, no new test needed).
- **`"to"` notation**: reads unambiguously for both the discrete-step-count and continuous forms,
  including the negative-lower-bound case the first review flagged (`-1 to 1 continuous`,
  confirmed in the regenerated `switch-reference.md`'s `COLLECTIVE-CORR-PTR`/`OP-COLL-THROTTLE-
  PTR` rows). Both optional refinements from the first review (the separator, and the stale
  `config/effectors-raw.toml` → `config/effectors-raw/mi-24p.toml` source-line path) are applied
  and verified in the rendered file; the third (`implementation.md`'s orphaned line) is gone.
- **`TRIGGER_INFO[TAKEOFF]` wording**: now correctly attributes the self-check to the engine ("the
  engine's own implicit self-check -- a row does not write if its switch is already observed at
  the target value") rather than to the sequence file's own row conditions, matching
  `effector_engine.advance`'s documented behaviour in `body-layer/CLAUDE.md`. `triggers.md`'s
  generated copy matches (staleness test green).

**Checks** (body-layer only): `ruff format --check src tests tools` clean (183 files);
`ruff check src tests tools` clean; `cd body-layer && .venv/bin/mypy src` clean (74 files);
`.venv/bin/mypy tools` clean (10 files); `pytest -q` — 2596 passed, 4 xfailed, matching the
implementer's own report exactly. `test_render_switch_reference.py`/`test_render_triggers.py`
(the staleness checks against both generated files) pass, confirming the committed
`switch-reference.md`/`triggers.md` match the current generator/code.

**Not reviewed, per scope**: mission-start trigger wiring (the parallel explore-notes commit at
the tip, being built by another agent) and the raw dump's real values (awaits the pending Windows
rerun — the committed `config/effectors-raw/mi-24p.toml` is confirmed unchanged by this diff, and
its ~25 arithmetic-`helper_args` elements, 5 `radio_wheel_1` elements, and NULL-class actions are
exactly where the implementer said they'd be).

### Verdict (fix pass)

APPROVED

Both Required Fixes from the first review are closed and independently mutation-verified by this
pass, not just re-read. All three optional refinements were also applied. The real-run findings
(arithmetic evaluator, NULL class, `radio_wheel_1`, rounding, unknowns reporting) are each correct,
tested, and consistent with the amended research note. The one new gap found — no test asserts
the unknowns-count wiring in the run report/header — is cosmetic test-coverage on otherwise-correct
plumbing, not a required fix; worth closing opportunistically next time this file is touched.

### Review Confidence (fix pass)

Full read of the diff and both generated config files. Mutation-verified both Required Fixes
myself (the `default_blue_cover` removal/restore, confirmed by re-running the full
`test_generate_effector_registry.py` suite before and after) rather than relying on the
implementer's reported mutation log alone. Ran every check command myself rather than trusting
the implementation summary's reported numbers. Did not independently re-verify the
`default_1_position_tumb` branch-disable mutation (`elif helper == "..." ` → `elif False`) the
implementer reported — the three dedicated tests for that fix are correct and sufficient reading
of the code, and the `default_blue_cover` mutation already demonstrates the review's mutation
methodology holds on this file.
