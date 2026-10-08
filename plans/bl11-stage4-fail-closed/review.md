### Review Summary

Reviewed `BL-11` Stage 4 steps 3-4 on `feature/bl11-stage4-fail-closed`, commits `88f3df6`
(production), `7c5b0d9` (tests + fixture), `ec1b142` (agent memory). Worktree landed on `main`
as expected (AGENTS.md rule 4's known mechanism); the scaffolding branch carried no commits of
its own (`git log main..worktree-agent-<id>` empty), so it was moved to the named tip
`ec1b1429af6dbaeb0a42a2f5b3dd30840175a8fb` via `git checkout -B`, discarding nothing. Confirmed
`plans/bl11-stage4-fail-closed/plan.md` and `implementation.md` present.

Step 3 (fail-closed gate 4) and step 4 (`LiveLosCoverage` counter) both match the plan's
described shape. Reproduced the implementer's reported checks exactly: ruff format/check clean,
`mypy --strict` clean (54 source files), pytest 1542 passed / 4 xfailed / 0 failed.

Mutation-verified two things myself, not by reading:

1. **The negative-space LOS tests are load-bearing.** Restored the old `elif` fallback to
   `line_of_sight_clear` temporarily in `visibility.py` and reran `test_visibility.py`,
   `test_detection_trace.py`, `test_mock_flight_chain.py`: exactly one test failed —
   `test_live_los_clear_none_is_not_admitted_and_the_offline_primitive_is_never_called` — for the
   right reason (`_fail_if_called` raised inside `check_visibility`, not a result-value mismatch).
   Reverted cleanly; `git diff --stat` empty afterward.
2. **The coverage-log defect is real.** Drove `_log_live_los_coverage_if_growing` directly over
   10 simulated polls (6 dead-feed polls where `no_verdict` grows every poll, then 4 healthy polls
   where it holds static). Result: polls 1-6 logged every time, polls 7-10 logged never — the
   opposite of the docstring's stated intent ("not every poll... crowding out every other log
   line"). See Required Fixes.

### Required Fixes

- **(a) `_log_live_los_coverage_if_growing` floods during exactly the failure case it exists to
  guard against, and is silent exactly when nothing is wrong.** The implementation's trigger is
  `coverage.no_verdict > last_logged_no_verdict`. `no_verdict` is cumulative for the process
  lifetime, so a dead live-LOS feed increments it every poll and the guard's condition is true
  every poll — it never reaches a "no new information" steady state the way `_push_gaze_line`'s
  label-based guard does, because a *label* can repeat while a *monotonically increasing counter*
  under continuous failure never does. Empirically: 6/6 dead-feed polls logged, 0/4 healthy polls
  logged — exactly backwards from the docstring's claim and from what a ~1 s poll interval over a
  multi-minute outage needs (this would be ~2,400 lines over a 40-minute dead-feed sortie, per the
  dispatching brief's own estimate, which I confirm is the right order of magnitude given the
  mechanism). Either the code or the comment must change — they currently disagree, and the code is
  the one that doesn't do what the module needs. The minimal fix consistent with the stated intent
  ("print one line... not one line per poll") is to log once, edge-triggered on the zero-to-nonzero
  transition (`last_logged_no_verdict == 0 and coverage.no_verdict > 0`), not on every subsequent
  growth — that satisfies "the first one carries all the information, repeats don't" literally.
  A periodic re-announcement (e.g. only log again after `no_verdict` has roughly doubled, or once
  per N polls while growing) is a reasonable alternative if the user wants visibility into a
  worsening gap over a long sortie, but that is a design choice to make explicitly, not the
  accidental behaviour currently shipped. I recommend the simple edge-trigger: it is a one-line
  change, matches the comment as written, and this is a regression guard whose job is "tell me
  once that something is wrong," not a live dashboard.
  I'll also flag the deeper question asked in the brief: whether a process-lifetime cumulative
  counter is even the right unit for this guard. I think it is adequate for "did this sortie have
  a coverage gap at all" (the stated purpose), but it cannot distinguish "one brief feed hiccup
  early in the sortie, now fully healthy" from "the feed has been dead since encountering it" —
  both show the same nonzero, non-decreasing `no_verdict`. That is a real limitation worth naming
  to the user, not a blocker for this fix: the plan's own Risks section already deferred the
  finer-grained breakdown (`skew_s`, feed-absent vs. stale vs. non-unique) to `detection_trace.py`
  under `--detection-trace`, and I think that division still holds — this counter's job is a single
  always-on "something is wrong" signal, and the fix above should restore it to actually behaving
  that way, not grow new dimensions.

### Optional Refinements

- **(b) The canonical mock-flight chain fixture (`tests/fixtures/mock_flight_canonical.json`)
  exercises only the clear path (40/40 verdicts `building_clear=True, terrain_clear=True`) and so
  cannot by itself catch a regression to the removed fallback.** I confirmed this is not a real gap
  in coverage, only in this one fixture's shape: restoring the old fallback left
  `test_mock_flight_chain.py` fully green (0 failures) while `test_visibility.py`'s dedicated
  negative-space test caught the regression immediately. Division of labor is intact — the
  dedicated unit tests pin the invariant and are mutation-verified (see above) — so this is not
  required. If the user wants the chain test to also pin this invariant end-to-end, adding one
  frame with a `False` or omitted verdict to the fixture (and asserting non-admission at the chain
  level) would close it, but that is additional test-infrastructure work riding on a branch that is
  otherwise narrowly scoped, not a defect in what shipped.
- `test_aircraft_client.py` has no dedicated test for `get_line_of_sight_latest` against the real
  loopback server (every other `AircraftLayerClient` method does: `get_telemetry_latest`,
  `get_world_objects_latest`, `get_petrovich_indication_latest`, etc.). This predates this branch
  (`get_line_of_sight_latest` was added in `fc26e8e`, X-B29) and is out of this plan's scope — noted
  only because `tests/support/mock_aircraft_layer.py`'s new `/line_of_sight/latest` route (added by
  this branch) now makes that test easy to write, if the user wants it done opportunistically.

### Verification of (c): blast-radius completeness

Grepped for every `get_line_of_sight_latest`-providing double and every `_world_object`-shaped
factory in `tests/`. Found 8 files with a `FakeAircraftClient`/`_world_object` pair:
`test_naked_eye_source.py`, `test_detection_trace.py`, `test_emission_pipeline.py`,
`test_player_bubble.py`, `test_logger.py` (all fixed by this branch, all provide a live-LOS join
now), plus `test_hybrid_source.py`, `test_motion_benchmark.py`, and `tests/support/
mock_aircraft_layer.py` (also fixed).

- `test_hybrid_source.py`'s `FakeAircraftClient` deliberately has no `get_line_of_sight_latest` —
  confirmed this is correct, not a miss: `HybridPerceptionSource` is the scope/hybrid channel,
  which `body-layer/CLAUDE.md`'s own module map states has "no geometric gate chain to instrument"
  — it never calls `check_visibility`, so gate 4 is not reachable from this test file at all.
- `test_motion_benchmark.py`'s `_world_object` has a `unit_name` already and needs no
  `get_line_of_sight_latest` — its own test exercises `_resolve_velocity_by_object_id` and
  `evaluate_motion_gate` directly, not `check_visibility` or `NakedEyePerceptionSource.poll` (its
  docstring's claim of being "synthesised end to end through the exact functions
  `NakedEyePerceptionSource.poll` calls" is about the parse→join→motion-gate path specifically, not
  the full poll including gate 4 — confirmed by reading the test body, no `check_visibility` or
  `.poll(` call anywhere in it).
- `src/replay.py` has no fixtures and no standalone CLI entrypoint of its own (no `__main__`,
  confirmed by grep) — it is a generic `replay(source, frames)` driver over any `PerceptionSource`.
  The live-LOS join lives upstream in whichever concrete source is passed to it
  (`NakedEyePerceptionSource`, already fixed), so there is no separate "replay.py's own path" that
  could bypass the fix. The plan's Risk note asking the implementer to check this was satisfied.

No missed fake-client double found. The implementer's 11-file blast-radius correction (vs. the
plan's 4-file estimate) is complete as far as this grep-based sweep can establish.

### Verdict

NEEDS REVISION — one required fix: (a), the coverage-log flood/silence inversion. It is a small,
local, one-line-shaped fix (edge-trigger on the zero-to-nonzero transition rather than on every
growth) and does not touch the fail-closed gate logic itself, which I am confident is correct and
well-tested. Everything else — step 3's production change, the blast-radius fix set, the fixture
backfill, the new coverage tests — is solid and I would approve them outright.

### Review Confidence

Full read. Production diff (`visibility.py`, `naked_eye_source.py`, `logger.py`) read in full and
mutation-tested (both the fail-closed gate and the coverage-log guard). Test diff read in full
across all touched files; the four-file blast-radius grep sweep was run directly rather than
trusted from the implementation log. Full suite + ruff + mypy reproduced independently, not
inherited from the implementer's report.

---

## Round 2: review of the fix (`77faae3`, answering round 1's required fix (a))

Worktree landed on `main` as expected; its scaffolding branch carried no unique commits, so it
was moved to the named tip `77faae3bd3e0d9e3b8f19685adbc134131e5bac6` via `git checkout -B`,
discarding nothing. Scope narrowed to the coverage-log fix and its five new tests only, per the
dispatching brief — everything else in this file's round 1 stands.

`_log_live_los_coverage_if_growing` was renamed to `_warn_live_los_coverage_gap_once` (edge-
triggered on the zero-to-nonzero `no_verdict` transition, fires once, never again) and a new
`_log_live_los_coverage_summary` was added — an unconditional, try/except-wrapped `logger.info`
called as the first statement in both poll loops' `finally:` blocks, logging the real totals even
at `no_verdict == 0`. This second piece was the user's own design call, not something round 1
asked for, and the dispatching brief invited pushback on it; I don't have one — treating a `0/N`
line as "the guard visibly passing" is consistent with `detection_trace.py`'s
`static_enum_failures` precedent already in this codebase, and a post-flight regression guard
whose whole job is reporting a magnitude needs the magnitude logged even when it's zero.

Reproduced the implementer's own repro independently before trusting the fix: dead feed over 6
polls warns exactly once (poll 1); end-of-run line reads `30/30`; a healthy run never warns but
still logs `0/28`. Matches the report exactly.

**Mutation-verified each of the five new tests and the teardown claim myself, not by reading:**

1. **The `== 1` call-count test is load-bearing, not vacuous.** Removed the `if already_warned:
   return True` early-return guard (reproducing the old flood shape against the new trigger
   condition) and reran. `test_..._fires_exactly_once_under_continuous_growth` failed with
   `10 == 1` — ten warnings logged, one per poll, exactly the pre-fix flood. The weaker `>= 1`
   shape the brief warned about would have passed this mutation; the test as written does not.
   Reverted with `Edit`; `git diff --stat` empty afterward.
2. **Both `finally:`-block tests are wired independently, not sharing a path.** Replaced the
   `_log_live_los_coverage_summary(runner.sources)` call in `_run_console_poll_loop`'s `finally:`
   with `pass` and reran both integration tests: `test_console_poll_loop_logs_the_coverage_
   summary_in_its_finally_block` failed (`summaries == []`), and
   `test_crew_text_poll_loop_logs_the_coverage_summary_in_its_finally_block` still passed. The two
   loops genuinely do not share a code path for this call — breaking one does not break the other,
   confirming the implementer's claim and item 3 of the dispatching brief. Reverted with `Edit`;
   `git diff --stat` empty afterward.

**Teardown safety (item 2 of the brief).** Read `_log_live_los_coverage_summary`'s body: every
statement that can raise (the `isinstance` check, the `coverage` attribute access, and the
`logger.info` call itself) is inside the `try:`; nothing executes before entering it. Python's
`logging` module does not propagate formatting/handler exceptions by default (`Handler.
handleError` swallows them unless `logging.raiseExceptions` is forced off and a handler is
unusually configured, neither true here), so in practice the surrounding `except Exception:` is
already a second line of defense behind stdlib's own. The claim "must never raise" holds for both
reasons, not just the one stated.

**Reachable disagreement between the `bool` flag and the source's counter (item 4).** Grepped
`runner.sources = _build_sources(...)` in `logger.py`: it is assigned exactly once per loop, before
the `while` loop starts, and never reassigned inside it (confirmed by reading both loop bodies in
full — no second `runner.sources =` anywhere between the `try:` and the matching `finally:`). A
`NakedEyePerceptionSource` is therefore never rebuilt mid-run on either poll-loop path, so the
`live_los_warned` local and the source's own `LiveLosCoverage` counter cannot diverge in the
current code. This is worth stating explicitly, as the brief asked, because `_build_sources` is a
plain function call sitting right there in the source — a future change that moved it inside the
loop (e.g. to support hot-reconnecting a source) would silently reintroduce this as a real bug with
no test currently positioned to catch it.

**Docstring/code agreement (item 5).** Both new docstrings match what the code does: the
edge-trigger-once claim, the "no `--flag` to gate it" claim, and the "must never raise" claim are
all true of the code as written (verified above, not just read). `implementation.md`'s round 2
section accurately describes the same mutation-testing approach used here, independently reached.

Full checks reproduced independently: ruff format/check clean, `mypy --strict` clean (54 source
files, run from inside `body-layer/`), pytest 1547 passed / 4 xfailed / 0 failed — matching the
implementer's report exactly.

### Verdict (round 2)

APPROVED. The required fix from round 1 is correctly implemented and its tests are genuinely
load-bearing (verified by mutation, not just by reading). The unconditional summary is a sound
addition consistent with existing project precedent. Ready for DoD.

### Review Confidence (round 2)

Full read, scoped to the fix as instructed. Every new test mutation-verified against the actual
mechanism it claims to pin, not inherited from the implementer's report. Teardown-safety and
mid-run-rebuild reachability both checked by reading the full relevant code paths, not assumed.

---

## Round 3: review of the fix (`c6f196e`, answering Security's advisory finding)

Worktree landed on `main` as expected; its scaffolding branch carried no unique commits
(`git log main..worktree-agent-<id>` empty), so it was moved to the named tip
`c6f196e5782dbe270b9d35a51d2d96364e11a04a` via `git checkout -B`, discarding nothing. Scope
narrowed to this one commit, per the dispatching brief — rounds 1 and 2 above stand and were not
re-reviewed.

This wires `_warn_live_los_coverage_gap_once`/`_log_live_los_coverage_summary` (already approved
in round 2) into `main()`'s third, previously-uninstrumented branch — the bare `else:` reached
with neither `--console` nor `--crew-text` — mirroring the other two poll loops' shape exactly.

**1. The `sources` hoist.** Correct, and the right call. `sources: list[PerceptionSource] = []`
is declared before the `try:` and reassigned from `_build_sources(...)` inside it, so `finally:`'s
`_log_live_los_coverage_summary(sources)` always has a valid list even if `_build_sources`/
`PerceptionLogger(...)` raised first. On the empty-list path, `_log_live_los_coverage_summary` is
a documented no-op (no `NakedEyePerceptionSource` in the list to match the `isinstance` check),
so a startup failure here produces no summary line — same as it would produce none today without
this fix, since the function didn't exist on this path before. I don't read this as masking
anything: the exception itself still propagates out of the `except KeyboardInterrupt: pass` (which
does not catch it) and out of `finally:` after `world_model_conn.close()`, so a construction
failure is still loud via its own traceback; the summary's silence on that path is "nothing to
report" layered on top of a failure that is reported through a different, pre-existing channel.
Confirmed the hoist changes nothing on the success path (full suite reproduced identically before
and after reading it) and confirmed by direct mutation (below) that `finally:` really does run
with a non-empty list on the normal path. `mypy --strict`'s clean pass is not hiding a widened
type — the annotation `list[PerceptionSource]` matches `_build_sources`'s own return type exactly,
and `[]` is a valid literal for that annotation with no `Any` or union introduced.

**2. The test approach (`main()` driven through its loop body).** Sound, and appropriately
scoped. This does make `main()`'s bare-branch loop body a tested surface for the first time —
previously only its argparse path was (`test_main_rejects_neither_theatre_pair_nor_mission_
understanding` et al.) — but it is the correct tool for proving a wiring defect is actually fixed:
Security's finding was specifically that this branch's production code failed to call two
functions, and the only way to prove the calls are now reachable from a real `sys.argv` invocation
is to invoke it that way. `main()` itself is unmodified (confirmed: `git show` of this commit's
`logger.py` diff touches only the `else:` branch body, nothing in argument parsing or dispatch).
The implementer's own notes correctly flag this as a precedent to keep narrow rather than adopt
generally, and I agree with that framing — read it as "this branch's wiring is now pinned," not
"`main()` is now an integration-tested entrypoint."

**3. Cross-test pollution, verified by reproducing it, not reading about it.** Temporarily
reverted the fix's own fix — changed `monkeypatch.setattr(logger_module, "time",
_RaiseAfterNSleeps())` back to the rejected `monkeypatch.setattr(logger_module.time, "sleep",
_RaiseAfterNSleeps().sleep)` — and ran the full suite: **6 `PytestUnhandledThreadExceptionWarning`s**
reappeared, each a `KeyboardInterrupt` raised inside a leftover `belief.brain_client.
BrainLayerClient._poll_loop` daemon thread's `time.sleep(_POLL_RETRY_BACKOFF_S)` call, exactly as
described. Reverted; full suite back to 1549 passed / 4 xfailed / **0 warnings** (ran with
`-W error::pytest.PytestUnhandledThreadExceptionWarning` to make a reappearing warning fail the
run outright, not just print). The stand-in cannot swallow an attribute the module needs: grepped
every `time.<attr>` use in `logger.py`/`run_log_paths.py` reachable from this branch —
`time.sleep` (faked) and `time.time()` (via `_per_run_log_paths`'s stamping, called before the
loop) — and `_RaiseAfterNSleeps.__getattr__` delegates anything but `sleep` to the real module, so
`time.time()` still resolves correctly. `time.monotonic()` (used by `_wait_for_next_tick`) is
never reached on this branch at all — the plain-logger path calls `time.sleep` directly, not
`_wait_for_next_tick` — so there's no attribute this stand-in is asked for and doesn't have.

On whether this belongs somewhere more discoverable than `.claude/agent-memory/implementer/
feedback_monkeypatch_module_attr_not_shared_stdlib.md`: **yes, as an optional refinement, not a
blocker.** The trap is general-purpose (any test monkeypatching a shared stdlib module in a suite
that leaves daemon threads running past their test) and `body-layer/CLAUDE.md`'s own `## Testing`
section is where a future test author would look for this class of guidance, not an implementer's
personal memory file. I'd suggest a one- or two-line addition there pointing at this commit's
docstring rather than duplicating the explanation. Not required for this round.

**4. Non-vacuousness of the two new tests, reproduced by mutation myself.**
- Removed the `live_los_warned = _warn_live_los_coverage_gap_once(sources, live_los_warned)` call
  from the loop body: `test_plain_logger_path_warns_on_the_live_los_coverage_gap_once` failed with
  `assert 0 == 1` (`warnings == []`). Reverted with `Edit`; `git diff --stat` empty afterward.
- Separately removed `_log_live_los_coverage_summary(sources)` from `finally:`:
  `test_plain_logger_path_logs_the_coverage_summary_in_its_finally_block` failed
  (`summaries == []` vs. the expected `2/2` line) — and the captured log for that run still showed
  the transition warning firing, confirming the two failures are independent, matching the
  implementer's own report exactly. Reverted with `Edit`; `git diff --stat` empty afterward.

Both mutations were run in isolation (`-k plain_logger_path`), each reverted before the next, and
a final full-suite run after all reverts confirmed a clean tree and 1549 passed / 4 xfailed /
0 failed / 0 warnings.

Checks reproduced independently: ruff format --check clean, ruff check clean, `mypy --strict`
clean (54 source files, run from inside `body-layer/`), `pytest -q` 1549 passed / 4 xfailed /
0 failed / 0 warnings — matching the implementer's report exactly.

### Verdict (round 3)

APPROVED. The hoist is correct and does not mask anything beyond what was already unreported on
this path; the `main()`-driving test approach is sound and appropriately scoped as a one-off, not
a new default; the cross-test-pollution fix reproducibly holds; both new tests are genuinely
load-bearing. One optional refinement only (give the monkeypatch-stdlib trap a home in
`body-layer/CLAUDE.md`, not required). Ready for DoD.

### Review Confidence (round 3)

Full read, scoped to `c6f196e` as instructed. Both new tests mutation-verified against the actual
calls they claim to pin. The cross-test-pollution claim was reproduced directly (reverted the fix,
watched the warnings reappear, re-applied the fix, watched them disappear) rather than taken from
the implementation log. Full suite, ruff, and mypy run independently in this worktree, not
inherited.
