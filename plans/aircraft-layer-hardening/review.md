### Review Summary

Reviewed `6e821c9` ("Aircraft-layer: bound audio queue, guard collector accept() loop") against
its parent `4c73639`, on branch `feature/aircraft-layer-hardening`. Scope matches the two
RECOMMENDED findings from the 2026-09-26 whole-subproject security/performance reviews, no
plan.md (correctly, per the task brief — user-scoped directly from the review docs). Diff is
exactly the two touched modules + their new/extended tests + `implementation.md` +
`.claude/agent-memory/implementer/`; no export-throttle change, no HTTP request-size cap, no
unrelated refactor crept in.

**Fix 1 (bounded audio queue, drop-oldest)** is solid: `play_audio`'s never-raises/never-blocks
contract holds on every path I traced, the FIFO-survivors test genuinely proves *which* end was
dropped, and I independently reproduced the overflow scenario outside pytest to confirm dropped
files are actually removed from disk (0 leaked temp files after a forced 69-file overflow +
drain). `interrupt()`'s pre-existing full-queue-clear path (used by `urgent=True`) is unaffected
and its own test still passes.

**Fix 2 (guarded `accept()`) has a real defect, not just an imprecision.** The code's own
docstring, `implementation.md`, and the implementer's agent-memory file all state the same claim:
that `self._socket` is captured into a local once per iteration and **never re-read** after the
exception fires, specifically to avoid misclassifying a `close()`-driven shutdown as a failure.
That claim is false as written — the `except OSError` block does re-read `self._socket` (`if
self._socket is None: return`), and I ran the real `close()`-during-blocked-`accept()` shutdown
path (the same shape `test_close_during_a_blocked_accept_ends_the_loop_cleanly` exercises)
300+ times outside pytest: **it logged the false `"collector accept() failed unexpectedly"` ERROR,
plus a spurious 1.0s backoff, on 161/~230 clean shutdowns before I stopped the run** — this is not
a rare theoretical race, it fires on roughly two-thirds of ordinary shutdowns on this platform.
The original `AttributeError`-on-`None` crash the fix targeted is genuinely gone (a second,
unconditional `sock is None` check at the top of the loop protects every `.accept()` call site),
but the *classification* the docstring describes as safe is not, and it directly undermines fix
2's whole stated purpose: an ERROR line that fires on most ordinary shutdowns teaches an operator
to ignore it, which is worse than the silence it was meant to replace.

I also confirmed, per the task's ask, that the suite would not catch a regression of the original
crash: `pyproject.toml` sets no `filterwarnings`, so a reintroduced `PytestUnhandledThreadExceptionWarning`
would show up only as a warning in the summary, not a failure — "178 passed" either way. Flagged
as a suggestion, not blocking this PR, since it's a suite-wide gap rather than something this
change introduced.

All claimed checks reproduced independently from a fresh venv: `ruff format --check` clean (46
files), `ruff check` clean, `mypy --strict` clean over 18 source files, `pytest -q` 178 passed
(27.3s), no warnings. The `G201` fix (`logger.error(..., exc_info=True)` → `logger.exception(...)`)
is genuinely equivalent — `Logger.exception` is implemented as `self.error(msg, exc_info=True,
...)` in the stdlib, and the call site is inside an `except OSError:` block so `exc_info` resolves
correctly either way.

### Required Fixes

- **Replace the `self._socket`-is-`None` inference in `serve_forever`'s `except OSError` block
  with an explicit shutdown flag, set in `close()` *before* `self._socket.close()` runs** (e.g.
  `self._shutting_down = True` as the first statement of `close()`, checked instead of
  `self._socket is None` in the except block). Because the flag-write happens-before the
  `close()` syscall in program order on the same thread, and the `accept()` exception can only be
  *observed* by the other thread after that syscall executes, this removes the race
  deterministically rather than narrowing it — it isn't the "consider a flag" suggestion the task
  brief floated, it's the actual fix, since the current approach reads a value whose write is not
  atomically paired with the event that triggers the read. This was empirically demonstrated, not
  theoretical: see Review Summary above (161/~230 false ERRORs). Update the docstring,
  `implementation.md`, and the agent-memory file's claim about "never re-reading the attribute"
  to match whatever the corrected mechanism actually does — right now, all three describe
  behavior the code does not have.
- **Add an assertion to `test_close_during_a_blocked_accept_ends_the_loop_cleanly`** that no
  ERROR-level record was logged (`caplog.at_level(logging.ERROR, ...)`, assert no matching
  records) — its own docstring already claims "ends the loop without logging it as a failure,"
  but nothing in the test body checks that, which is exactly why this shipped despite failing
  that claim on most runs. This test, with that assertion added, should be the regression test
  for the fix above.

### Optional Refinements

- `AudioPlaybackSender.close()`'s `self._queue.put(_SENTINEL)` is a plain blocking `put()` on a
  now-bounded queue — previously guaranteed to return immediately (unbounded queue), it can now
  block if the queue happens to be at `_MAX_QUEUE_LEN` and nothing is draining it (e.g. the
  worker thread died from an exception outside `_run`'s own `try/except Exception` around
  `player.play()`, such as one from `_cleanup`'s `os.remove` swallowing only `OSError`). Extremely
  unlikely given realistic callout rates and that `close()` runs once at shutdown, not on a hot
  path, but it's a new failure mode this fix's bounding introduced that wasn't there before and
  isn't covered by any test. A `put(path, timeout=...)` with a fallback (drop-oldest via
  `get_nowait` then `put_nowait`) would make `close()`'s own bounded-time expectation (the
  `join(timeout=5)` right after it) hold on every path, not just the common one. (Optional — no
  plausible trigger under current callout volumes.)
- Consider adding an explicit `assert not any(...)` for leaked temp files to
  `test_queue_is_bounded_and_drops_the_oldest_queued_line` (I verified this by hand outside pytest
  — 0 leaked files after a 69-file overflow — but the test itself only checks which files
  survived to play, not that the dropped ones were removed from disk).
- `pyproject.toml` has no `filterwarnings` configuration, so a reintroduced
  `PytestUnhandledThreadExceptionWarning` (exactly the class of bug this PR's own
  `implementation.md` says caught the original crash) would only show up as a summary warning,
  not a failing run. Worth a project-wide `filterwarnings = ["error::pytest.PytestUnhandledThreadExceptionWarning"]`
  (or similar) at some point — out of scope for this small PR, noted for the backlog.

### Verdict

NEEDS REVISION

The audio-queue fix (Fix 1) is clean and ready as-is. The `accept()` guard (Fix 2) fixes the crash
it targeted but the shutdown-classification mechanism it introduced does not do what its own
docstring says, and empirically produces a false "unexpected failure" ERROR log on most ordinary
shutdowns — the opposite of the anti-silence goal the whole fix exists for. This is a small,
mechanical fix (a boolean flag, reordered by one line, plus one test assertion), not a design
reopen; recommend sending straight back through Implementer → Reviewer per the standard loop
rather than escalating to the user.

### Review Confidence

Full read of both changed modules and both test files. The `accept()` race was verified by
running the actual shutdown path (real socket, real `close()`, real `serve_forever`) 300+ times
outside pytest rather than trusting the implementer's account of it, per this role's standing
practice for exactly this class of claim. The audio-queue drop-oldest/cleanup behavior was also
independently reproduced (not just read). Not independently re-run on Windows/live DCS — this
subproject's own testing posture (per `aircraft-layer/CLAUDE.md`) treats the collector/`Export.lua`
live path as validated separately, unaffected by this change's scope.
