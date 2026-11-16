### Implementation Summary

Effector-sequence rows now speak their own `petrovich-says` line when the row completes (written,
or found already at the target value); the four hard-coded readbacks in `crew_console.py`
(`"Observ on."`, `"Observ off."`, `"Weapons armed."`, `"Weapons safe."`) are removed. The engine
stays pure -- it reports what completed via a new field on its own state, `body.py` drains it into
`CrewConsole`'s normal speech path.

**Design choice not spelled out in the plan:** the plan allowed either "a `spoken: tuple[str, ...]`
on `EffectorRunState`, or a returned value." I chose the state field, specifically to avoid
widening `advance()`'s return type from `EffectorRunState` to a tuple -- that would have broken
~40 `state = advance(...)` call sites in `test_effector_engine.py` alone (an "existing tests must
be rewritten" situation). The field is reset to a fresh value (`()` when nothing completed) on
every `advance()` call, never accumulated, and mission reset (D11) clears it for free via the
existing `field(default_factory=EffectorRunState)` / re-run-`__init__` mechanism -- no reset-
specific code needed, confirmed by a dedicated test.

### Files Changed
- `body-layer/src/belief/effector_sequences.py` -- added `_strip_petrovich_says` (strips
  whitespace, then one matching pair of quote characters), applied to every data row's
  `petrovich-says` cell at parse time.
- `body-layer/src/belief/effector_engine.py` -- added `_speak_text` (sentence-case + trailing
  punctuation, matching the fixed phrasing it replaces); added `EffectorRunState.spoken: tuple[str,
  ...] = ()`; `advance()` appends a formatted line at the two row-completion points (R12 self-check
  match, and a successful write) when the row's own `petrovich_says` is non-empty, and returns it
  on the new field. Module/function/field docstrings updated to describe the new behaviour.
- `body-layer/src/belief/crew_console.py` -- `_handle_observ_on`/`_handle_observ_off`/`_handle_
  weapons_armed`/`_handle_weapons_safe` now return `[]` on their accepted path (the readiness
  refusal in `_handle_observ_on` is unchanged, out of scope). Added `drain_effector_speech(now_sim,
  spoken)`, called unconditionally every poll, same shape as `drain_config_error`. Added the four
  tokens to `NO_RETURN_VALUE_COMMAND_TOKENS` (see Notable Discoveries) and corrected the now-stale
  comment in `DISPATCHED_COMMAND_TOKENS` that claimed they "always return a one-line readback."
  Preserved the dated user-direction quote (2026-10-21, "weapons armed/safe") in `_handle_weapons_
  armed`'s docstring rather than deleting it, reworded to explain it now governs the sequence
  file's cell text rather than a literal return value.
- `body-layer/src/body.py` -- one new call, `crew_console.drain_effector_speech(runner.last_t_sim,
  runner.effector_state.spoken)`, right after `advance_effectors`.

### Tests Added
- `test_effector_sequences.py::test_petrovich_says_quotes_are_stripped` -- quoted cell -> unquoted
  `petrovich_says`.
- `test_effector_engine.py`, new section: row written -> line reported once; self-check-skip
  ("already in position") -> line still reported; empty `petrovich_says` cell -> nothing even
  though the row writes; failed explicit condition -> nothing; non-absolute unknown-readback skip
  -> nothing even with a non-empty cell; failed write -> nothing until the retry succeeds, then
  once; two triggers completing in the same poll -> lines in fire order. Plus a one-line test that
  `EffectorRunState().spoken == ()` (D11 coverage, same style as the neighbouring `assumed_writes`
  test).
- `test_body.py::test_weapons_armed_sequence_row_speaks_through_the_real_poll_loop` -- a custom
  `weapons-arm` sequence (the shipped fixture's own rows carry no `petrovich-says` text, see Notable
  Discoveries) driven through the real poll thread; "Weapons armed." appears exactly once in
  `crew_console.output` even after several more polls past completion.
- Updated (not added) `test_crew_console.py::test_dispatched_command_tokens_all_return_something`
  to set `console.sight_ready = True` before its sweep, so `observ_on`'s one call in that loop
  lands on the new `[]` path rather than the (unaffected, still real) readiness refusal.

### Checks
(body-layer/ only -- the only subproject touched)
- ruff format --check: pass (on every file this feature touched; one pre-existing failure in
  `test_bl_b104_association_scenarios.py`, confirmed untouched by this diff)
- ruff check: pass (same scope note)
- mypy src (strict, run from inside body-layer/): pass, 83 source files
- `.claude/scripts/fast-tests.sh body-layer`: 2237 passed, 4 xfailed
- Also run directly (not required, extra confidence): `tests/test_effector_sequences.py`,
  `tests/test_effector_engine.py`, `tests/test_crew_console.py`, `tests/test_body.py -m "not slow"`,
  `tests/test_effector_registry.py`, `tests/test_generate_effector_registry.py`, `tests/
  test_sight_effector.py`, and the one `slow`-marked file this change's docstrings reference,
  `tests/test_bl_b104_scenario_mock_flights.py` (it mentions effector-engine wiring in its own
  docstrings but never builds that wiring, so it was unaffected -- all pass).
- Full suite not run (DoD's job, per root `CLAUDE.md` "Verification").

### Notable Discoveries
- **Test-impact mismatch the plan did not name**: `test_crew_console.py::test_dispatched_command_
  tokens_all_return_something` is a project-wide regression guard that asserts every dispatched
  token either returns something truthy or is in `NO_RETURN_VALUE_COMMAND_TOKENS` (checked via
  `== []`). Removing the four handlers' hard-coded returns broke it immediately (it failed on
  `observ_off` first; `weapons_armed`/`weapons_safe` were masked behind that one assert but would
  have failed too). Not listed in the plan's own Tests section. Fixed by adding the four tokens to
  `NO_RETURN_VALUE_COMMAND_TOKENS` and setting `sight_ready = True` in that one test so `observ_on`'s
  single dispatched call lands on the `[]` path rather than its own unaffected readiness refusal.
- **The shipped fixture directory predates the pilot's speech strings.** `tests/fixtures/
  effector_config/mi-24p/*.md` is a frozen 2026-10-30 copy of `config/sequences/mi-24p/` (by design,
  so editing the shipped files cannot break pinned tests) -- it carries no `petrovich-says` text at
  all, since the pilot's commit `80a134c1` (adding those strings) landed after the freeze. This
  means `test_observ_and_weapons_safety_write_through_the_real_poll_loop` (which uses that fixture)
  needed only `== []` assertions, not a real spoken-line check; the real end-to-end spoken-line
  check needed a custom sequence built the same way `_effector_config_with_mission_start_sequences`
  already does for the mission-start triggers. Worth knowing for any future change that touches the
  real `config/sequences/mi-24p/*.md` files and expects existing tests to reflect their content --
  they generally do not, by design.
- **No open questions left by the plan** beyond the above -- Q1/Q2/Q3 from the "Decisions, verbatim"
  section were all concrete enough to implement directly, and the "Out of scope" list's four items
  were verified unchanged by inspection and by the passing test suite (none of their own tests
  needed touching).
