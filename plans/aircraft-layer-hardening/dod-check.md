# Definition of Done: aircraft-layer-hardening

Branch `feature/aircraft-layer-hardening`, tip `f9e570c`. Worktree was stale at task start (tip
`4c73639`, missing all five feature commits) -- fast-forwarded via `git checkout -B` before
reading anything, per the standing warning that this has hit three agents this session.

## Verdict: PASS

## Code Quality

- **Subprojects touched** (from `git diff --name-only 4c73639..HEAD`): `aircraft-layer/` only
  (source: `src/collector/audio_sender.py`, `src/collector/server.py`; tests:
  `test_audio_sender.py`, `test_collector_server_accept_errors.py` [new]). Also touched:
  `.claude/agent-memory/{implementer,reviewer}/`, `plans/aircraft-layer-hardening/`,
  `todo/todo.md` -- none of these are subproject source, no other subproject's checks apply.
- Ran all four commands myself, fresh `.venv` built in the worktree (none existed, gitignored as
  expected):
  - `ruff format --check src tests` -- **46 files already formatted**
  - `ruff check src tests` -- **All checks passed!**
  - `mypy src` (strict, per `pyproject.toml`) -- **Success: no issues found in 18 source files**
  - `pytest tests -q` -- **178 passed** in 26.85s, zero warnings
  - Lua syntax check: not applicable, no `.lua` file in the diff (confirmed via
    `git diff --name-only ... -- '*.lua'`, empty).
  - All four numbers match exactly what `implementation.md` and both review passes claimed --
    reproduced, not trusted.
- No debug output, no `print`, no leftover TODOs introduced by this diff (checked both changed
  source files in full above).
- No unhandled errors/panics in the data path: `_enqueue`'s overflow loop and `serve_forever`'s
  `except OSError` are the two paths this feature added, both read and traced against the test
  files that exercise them.

## Scope & Correctness

- No `plans/aircraft-layer-hardening/plan.md` exists, and correctly so -- the task was scoped
  directly from two already-existing whole-subproject review documents
  (`aircraft-layer/research/2026-09-26-security-review.md`, `-performance-review.md`), not a new
  Architect pass. `implementation.md` states this explicitly and the Reviewer confirmed the scope
  match on both passes.
- Diff is exactly the two RECOMMENDED findings: bounded audio queue (drop-oldest) and a guarded
  `accept()` loop. No export-throttle change, no HTTP request-size cap, no unrelated refactor --
  confirmed by reading the full diff and cross-checking against both Reviewer passes, which say
  the same.
- No CLAUDE.md invariants touched (no DCS-write, no provenance/timestamp field, no OSM/DCS
  authority question -- this is pure collector-internal hardening).
- All new files (`test_collector_server_accept_errors.py`, both agent-memory files) are staged
  and committed as of `f9e570c`; `git status --porcelain` clean at every commit checked.

## Testing

- `test_queue_is_bounded_and_drops_the_oldest_queued_line` -- traced the assertion: blocks the
  worker on an in-flight line, floods `_MAX_QUEUE_LEN + 5`, asserts survivors are exactly the last
  64 pushed in FIFO order. Genuinely proves which end drops, not decorative.
- `test_unexpected_accept_error_is_logged_loudly_and_the_loop_recovers` -- injects a real `OSError`
  from a fake socket, asserts an ERROR record mentioning `accept()` was logged AND that a
  subsequent real connection still reaches the cache (proves recovery, not just non-crash).
- `test_close_during_a_blocked_accept_ends_the_loop_cleanly` -- **this is the one that matters
  most for this PR's history.** Runs 20 fresh server instances, asserts zero ERROR records each
  time, `caplog.clear()` between iterations so one iteration's failure can't be masked by the
  next's pass. At the reviewer's measured ~70%-per-run failure rate for the original (broken)
  mechanism, 20 independent passes all avoiding the ERROR by chance is `0.3^20 ~= 3.5e-11` --
  this would have caught the original defect essentially with certainty, not just "probably."
  Confirmed the assertion targets `logging.ERROR` records specifically, not "any log line" or
  "no exception raised."
- No existing test broken (178 passed, same count claimed at both review passes).

## Documentation

- **Reviewer findings addressed**, both rounds:
  - Round 1 (NEEDS REVISION, `1124f9d`): required an explicit `self._shutting_down` flag instead
    of inferring shutdown from `self._socket is None`, plus a caplog assertion on the regression
    test. Both done in `ac0bff9`, verified: I read `server.py` and confirm `self._shutting_down`
    is set as the literal first statement of `close()`, before `self._socket.close()` runs, and
    checked in the `except OSError` block instead of the old inference. The 20-iteration
    ERROR-record assertion is in the test file as described above.
  - Round 2 (APPROVED WITH MINOR FIXES, `e5e8490`): required correcting the false "never re-reads
    the attribute" claim everywhere it appeared -- three places named, one (`implementation.md`)
    only half-fixed at that point. `f9e570c` is exactly that fix. I read all three and confirm:
    - `server.py`'s docstring/comments: describe the real mechanism (flag-write
      happens-before the racy syscall), no trace of the old claim.
    - `.claude/agent-memory/implementer/project_aircraft_layer_hardening_fixes.md`: carries a
      `**Corrected 2026-09-26...**` paragraph in place, states what was wrong, cites the 161/230
      measurement, and closes with the generalizable lesson. This is the file that matters most
      (the next agent trusts it without re-deriving), and it's right.
    - `implementation.md`: both previously-untouched passages ("Files Changed" and "Notable
      Discoveries") now carry a **SUPERSEDED by the follow-up pass** annotation in place, with
      the original text kept, not deleted -- matches this project's stated convention of
      preserving superseded reasoning rather than rewriting history. Confirmed by reading the
      full file, not just the diff.
- `todo/todo.md` carries all three backlog items from the two review rounds, already present,
  no duplicates needed: the suite-wide `filterwarnings` gap, `CollectorServer.open()` not
  resetting `_shutting_down`, and the cosmetic test-simulation drift in the other accept-error
  test. Grepped and read each; wording matches what the reviews raised.

## Security

- No `plans/aircraft-layer-hardening/security-plan-review.md` or `security-review.md` exists,
  and I'm treating that as satisfied rather than missing: this feature has no plan.md for the
  same reason (scoped directly from an already-completed whole-subproject security pass,
  `4c73639`, "Security: full aircraft-layer subproject audit, no required fixes" -- read in
  full, APPROVED with two RECOMMENDED items, one of which *is* this feature's `accept()` fix).
  Per root `CLAUDE.md`'s current cadence ("security runs once per whole feature, immediately
  before DoD"), that whole-subproject pass is the gate this diff is implementing findings from,
  not a gate this diff still owes. No new dependency, no new attack surface, no scope beyond the
  two named RECOMMENDED items -- nothing here would warrant re-running Security.

## Acceptance testing

**Skipped, per the task's own instruction and my agreement with it.** Neither fix changes
anything perceivable in the cockpit -- both are latent-failure hardening for conditions with no
observed live trigger (both source reviews say so explicitly, and `implementation.md`'s own
Notable Discoveries repeats it). No test-card, no live-acceptance debt item added to
`aircraft-layer/ROADMAP.md`'s live-acceptance-debt scheme -- there is nothing outstanding to
track, this is not a deferred live test, it's work that was never in scope for one.

## Milestone Completion question

Does this change what the next aircraft-layer work should be, or invalidate a downstream
assumption? **No.** These were pre-existing RECOMMENDED findings from a review that already
happened; nothing about applying them is new information. The export-throttle split and the
`LoGetWorldObjects` FPS measurement remain correctly deferred in the backlog pending an actual
measurement -- this work took none, and the performance review that raised them explicitly
declined to split `EXPORT_INTERVAL_S` without one. The unit-velocity feed already logs
`unit_count`/`bridge_call_ms` every poll and remains unread; that data, not this PR, is what
would unblock that item.

## What remains unverified

- Everything requiring a live DCS session or the Windows box: I have neither reachable from this
  worktree. Both fixes are stated by both source reviews and by this task as latent hardening
  with **no observed live trigger** -- so there is no live symptom this gate is leaving
  unconfirmed, only the general fact that the collector process itself has not been restarted
  against a real Export.lua since this change (routine for a change of this shape, per this
  subproject's own testing posture in `aircraft-layer/CLAUDE.md`).
- The reviewer's 300-run stress reproduction of the shutdown race (zero-delay `close()`) was not
  re-run by me -- I verified the mechanism by reading the code and tracing the happens-before
  argument, and by running the actual test suite (which includes the 20-iteration version of the
  same shape), not by an independent long-run stress test of my own.
