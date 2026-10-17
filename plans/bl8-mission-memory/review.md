# Review: BL-8 Mission Memory, Stages 1, 2, 3, 5

Branch `feature/bl8-mission-memory`, tip `dc3735da86206774f03350e33d535b73996a807f`
(HEAD was `24f217fc`, 44 commits behind; fast-forwarded cleanly, tree was clean).

### Review Summary

The implementation matches the plan closely and the reasoning in `implementation.md` is sound —
the closure-injection resolution of the Decision 1 / Decision 6 tension is the correct call, the
schema honestly separates believed facts from last-observed ones (`y`, `as_of_sim`), and the
append-only/strike bookkeeping is exactly as specified. Mutation-testing the two structural guards
(import-direction grep, single-construction-site grep) confirmed both are real contracts, not
decorative: injecting a `mission_memory` import into `belief/contacts.py` and a second `Entry(`
construction site each failed the corresponding test immediately, then were cleanly reverted.

The gaps found are all in test coverage for claims the implementer stated but did not exercise,
plus documentation the plan designated "Changed" that was never touched. None of them is a logic
defect in the shipped code as far as I can tell from reading it; they are coverage/documentation
debt the batch should close before DoD.

### Required Fixes

- **No test exercises `admission._seen_how`'s output on a written entry.** No test in
  `test_mission_memory_admission.py` asserts on `entry.seen` at all — not `.optic`, not
  `.range_m`, not `.confidence`. The implementer's own claim ("`range_m` is honestly `None` where
  the sighting source cannot supply it, never fabricated") is correct by reading
  `admission.py:166-179`, but it is currently unverified by the test suite: deleting the
  `range_m=None` line or hardcoding a wrong value would not fail a single test. Add an assertion
  on `entry.seen` (optic matches `sighting_spans[-1].source`, `range_m is None`, confidence/
  certainty populated) to at least one of the existing `group`/`air_defence` admission tests.

- **No test exercises `dcs_to_wgs84` on a registered theatre, or the `ValueError` catch for an
  unregistered one, anywhere in the mission-memory suite.** Every admission and marks test passes
  `theatre=None`, which skips the `if theatre is not None:` branch entirely in both
  `admission._build_entry_position` and `marks._mark_position`. Decision 8's two concrete claims —
  "`lat`/`lon` are `dcs_to_wgs84` applied to believed x/z" and "an unregistered theatre yields null,
  never raises, and a memory write must never kill the poll loop" — are therefore both untested.
  This is the one place in the batch where a regression could silently reintroduce a crash on the
  poll thread (a memory write raising past `step()`/`mark_here`/`mark_target`) with nothing to
  catch it. `test_tools.py` already uses `theatre="Syria"` against a registered projection
  elsewhere in this test suite, so the fixture pattern exists; add one test per site
  (`admission.py`, `marks.py`) with a registered theatre asserting `lat`/`lon` populate, and one
  with an unregistered theatre string asserting `lat`/`lon` are `None` and no exception propagates.

- **The plan's own "Changed" file list for `body-layer/CLAUDE.md`, `body-layer/docs/STRUCTURE.md`,
  and `body-layer/ROADMAP/BL-8.md` was not touched by either implementation pass.** Confirmed by
  grep: zero hits for `mission_memory` in `CLAUDE.md` or `STRUCTURE.md`, and `BL-8.md` still reads
  "Not started" / `#status/open` with no record that Stages 1, 2, 3 and 5 have landed. The
  implementer flagged this explicitly both times ("Flagging for whoever closes out the milestone")
  rather than silently skipping it, which is the right instinct, but the plan lists these as
  "Changed" files for *this* work, not for a later closing pass, and root `CLAUDE.md`'s own
  "Milestone Completion" expectation is that a roadmap entry reflects what has actually landed.
  Add the `mission_memory/` module-map entry (the eight-file package, the import-direction
  invariant) to `CLAUDE.md`'s Module map and `STRUCTURE.md`, and update `BL-8.md` to record that
  Stages 1/2/3/5 are done with Stage 4 (trigger) and Stage 6 deferred per the user's own 2026-10-17
  decisions already quoted in the plan.

### Optional Refinements

- **`GROUP_ENTRY_CONFIDENCE_FLOOR`'s rendered `defaults.toml` entry carries no `range:` line**,
  unlike the other three new constants. This is not a bug in the Implementer's code: `tuning.
  fraction()` fixes `lo=0.0`/`hi=1.0` internally by delegating to `real()`, so the bound is
  genuinely enforced at runtime — but `generate_defaults.py`'s AST scan only reads `lo=`/`hi=`
  keyword arguments at the call site itself, and `fraction()`'s call site has none, so the
  generator has nothing to render. This is the first use of `tuning.fraction` in this codebase, so
  the gap in the generator was never exercised before now. Not a defect in this batch's own code,
  and not something this batch should be asked to fix in `generate_defaults.py` — flagging so a
  future reader checking "do `lo`/`hi` render" for a `fraction()`-declared key does not mistake a
  pre-existing generator limitation for a new constant's own error. (Saved to agent memory below.)
- **`ad_link`/`group_link` eventual symmetry is demonstrated in-memory, not via a genuine JSONL
  replay**, unlike the strike chain's own replay test (`test_replay_rebuilds_struck_by_from_an_
  actual_jsonl_file`). The in-memory version is logically sufficient (the same store methods
  decide both), but given the strike chain got the stronger "from the file alone" treatment, the
  link test reads as slightly less rigorous by comparison. Cheap to add if ever touched again; not
  worth a fix cycle on its own.

### Checklist verification

- **Decision 1 (import direction):** `tests/test_mission_memory_import_direction.py` greps
  `src/belief/*.py` for `from|import mission_memory` at line start, allowing only `tool_api.py`.
  Mutation-tested: adding `import mission_memory` to `contacts.py` failed it immediately. The one
  comment reference in `speech.py` (`#: mission_memory.admission's own name for...`) does not match
  the regex, correctly. `crew_console.py` never imports `mission_memory`; the plan's own
  Decision 6 tension with Decision 1 is resolved by closure injection in `logger.py`, matching an
  existing pattern (`speech_log_sink`). Sound.
- **Append-only:** confirmed by reading — `store.append()` never mutates an existing `Entry`
  (frozen dataclasses throughout), the strike is a separate append naming `strikes=<seq>`, and
  `struck_by` is rebuilt by replay (`rebuild_struck_by`), tested against both the in-memory store
  and an actual JSONL round-trip.
- **Co-moving Fields / single construction site:** `append()` is the only `Entry(` construction in
  `store.py` (grep-tested), and `admission.py`/`marks.py`/`query.py`/`tools.py` are grepped to
  contain no `Entry(` at all. Mutation-tested: injecting a second `Entry(` call anywhere in
  `admission.py` failed the grep test immediately.
- **No ground truth (Decision 8):** code reads correctly — both `admission._build_entry_position`
  and `marks._mark_position` derive `lat`/`lon` from believed `x`/`z` via `dcs_to_wgs84`, catching
  `ValueError` to `None`. **Untested**, see Required Fixes above.
- **Tuning constants:** all four render in `config/defaults.toml` with the rendered comment
  (not just the source `#:` comment) checked directly. `RESIGHT_MOVE_M`'s hazard sentence (per-look
  noise, not discrete step buckets) is genuinely sentence one in the rendered file — confirmed by
  reading the TOML, not the source. `lo`/`hi` on the three `real()`-declared constants are AST
  literals. `GROUP_ENTRY_CONFIDENCE_FLOOR`'s reuse search was re-run independently
  (`grep -rn "confidence >=\|CONFIDENCE_FLOOR" src/belief/`) and confirms nothing on the describe/
  callout path gates on a confidence threshold — `voice_commands.py`'s `CONFIRM_FLOOR` is speech-
  recognition confidence, an unrelated domain. New key correctly declared.
- **`TOOL_SET` 15 → 17:** `tool_api.py`'s docstring records the BL-7 fold-vs-extend reasoning in
  the required style, argues why `get_contact_history`'s fold is right where BL-7 declined one, and
  why the two new tools have no existing tool's question to be a subset of. `test_tool_api.py`'s
  `_EXPECTED_TOOL_NAMES` updated.
- **Scope:** nothing beyond Stages 1, 2, 3, 5. Stage 4's schema (nullable `weapon`/`outcome`)
  shipped in Stage 1 as the plan specified; no trigger code exists. Stage 6 absent entirely, as
  expected.

### Verification

Run from inside `body-layer/`, main checkout's venv (worktree has none, as both implementers
reported):

```
ruff format --check src tests   -> 152 files already formatted
ruff check src tests            -> All checks passed!
mypy src                        -> Success: no issues found in 68 source files
pytest -q                       -> 2158 passed, 4 xfailed in 16.81s
```

Matches the implementer's reported state exactly.

### Verdict

**APPROVED WITH MINOR FIXES.** The three Required Fixes are all test-coverage/documentation gaps,
not logic defects found in the shipped code — the behaviour they would catch already reads correct
by inspection and by the plan's own reasoning. They should go through the standard loop
(Implementer → Reviewer on the fix) rather than being waved through, since "add tests for an
already-correct code path" is exactly the kind of small change that can quietly miss something
(e.g. a test added against the wrong theatre fixture, or one that doesn't actually exercise the
`except ValueError` branch).

### Review Confidence

Full read of all seven new `mission_memory/` modules, all eight new/changed test files, the three
`belief/` files gaining mission-memory surface (`tool_api.py`, `crew_console.py`'s dispatch, the
`speech.py` rename), `logger.py`'s wiring, and the rendered `config/defaults.toml`. Mutation-tested
both structural guards. Not independently re-derived: the pre-existing `~160` test-file mypy
findings the implementer reported as unrelated noise (did not re-run `mypy tests` as a batch,
consistent with this subproject's own stated convention of not doing so).
