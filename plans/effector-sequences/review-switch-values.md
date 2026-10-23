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
