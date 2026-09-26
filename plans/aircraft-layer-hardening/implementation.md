### Implementation Summary

Two small, local hardening fixes in `aircraft-layer/`, both RECOMMENDED items from the
2026-09-26 whole-subproject security and performance reviews. No plan.md exists for this
task -- it was scoped directly by the user from the two review documents, not through
Architect, per the task brief.

### Files Changed

- `aircraft-layer/src/collector/audio_sender.py` -- bounded `AudioPlaybackSender`'s
  playback queue (`_MAX_QUEUE_LEN = 64`, same value and reasoning as
  `collector.cache.F10CommandQueue`'s `_MAX_QUEUE_LEN`). `play_audio`'s direct
  `self._queue.put(path)` replaced with a new `_enqueue` helper: `put_nowait`, and on
  `queue.Full`, drop the **oldest** queued (not-yet-playing) file via `get_nowait` +
  cleanup, then retry. Chose oldest-dropped over newest-rejected because a stale queued
  callout is worth less than a fresh one (task brief's own framing), and because a
  blocking `put` would stall whatever called `play_audio` (the HTTP request thread),
  which would violate this method's existing never-raises/never-blocks posture (plan
  Decision 5, referenced in the module's own docstring). `urgent=True` already clears the
  whole queue via `interrupt()` before reaching `_enqueue`, so the bound is only ever
  exercised by a flood of routine lines outpacing playback.
- `aircraft-layer/src/collector/server.py` -- guarded `CollectorServer.serve_forever`'s
  previously-unwrapped `self._socket.accept()` call. On an unexpected `OSError`, logs at
  `logger.exception` (ERROR level, visible without `--debug`) and retries after a new
  `_ACCEPT_ERROR_BACKOFF_S = 1.0` sleep, rather than either dying silently or hot-spinning
  CPU with no operator signal. Distinguished from the *intended* shutdown path (`close()`
  called from another thread, which also unblocks a pending `accept()` with `OSError`) by
  checking whether `self._socket` has been set back to `None`. That check has to be
  careful about a real race: `close()` runs on another thread and can flip `self._socket`
  to `None` between the exception firing and the retry's next loop iteration, so each
  iteration captures `self._socket` into a local (`sock`) once at the top of the loop and
  calls `.accept()` on that local, rather than re-reading `self._socket` a second time
  inside the `except` block (which surfaced as a real `AttributeError: 'NoneType' object
  has no attribute 'accept'` the first time the close-during-blocked-accept test was run
  -- see Notable Discoveries).
- `aircraft-layer/tests/test_audio_sender.py` -- added the queue-bound test (below);
  imports `_MAX_QUEUE_LEN` from the module under test.
- `aircraft-layer/tests/test_collector_server_accept_errors.py` (new) -- the `accept()`
  guard's tests (below).

### Tests Added

- `test_queue_is_bounded_and_drops_the_oldest_queued_line` (`test_audio_sender.py`) --
  blocks the worker on an in-flight `FIRST` line (same gate technique the existing
  urgent-preemption test uses), pushes `_MAX_QUEUE_LEN + 5` routine lines, releases the
  gate, and asserts the survivors are exactly the *last* `_MAX_QUEUE_LEN` lines pushed, in
  FIFO order -- i.e. the oldest 5 were dropped, not the newest.
- `test_unexpected_accept_error_is_logged_loudly_and_the_loop_recovers`
  (`test_collector_server_accept_errors.py`) -- swaps in a fake listening socket
  (`_FlakyAcceptSocket`) whose `accept()` raises `OSError` once, then returns a real
  connected socket (`socket.socketpair()`). Confirms: (a) an ERROR-level log record
  mentioning `accept()` is emitted (`caplog`, not just "no exception raised"), and (b) a
  valid line sent through the *second* accepted connection actually reaches the cache --
  proving the loop kept accepting after the injected failure, not just that it didn't
  crash. Shutdown is driven deterministically (see below), not raced against the fake's
  exhausted script.
- `test_close_during_a_blocked_accept_ends_the_loop_cleanly` -- the pre-existing shutdown
  shape (real socket, real `close()` from another thread while `accept()` is blocked)
  still ends the loop with no unhandled exception and no leftover thread.

### Checks

(aircraft-layer/ -- built an ad hoc `.venv` per the no-dep-tooling convention; no Windows
box or live DCS session reachable from here, per this subproject's own testing posture)

- ruff format --check: pass (`46 files already formatted`)
- ruff check: pass (`All checks passed!`, after fixing one `G201` finding --
  `logger.error(..., exc_info=True)` -> `logger.exception(...)`)
- mypy --strict (`src` only, per this subproject's own command list): pass (`Success: no
  issues found in 18 source files`)
- pytest -q: pass (`178 passed`, 27.7s, zero warnings on the final run)
- Lua syntax check (`luac5.1 -p`): not run -- no `.lua` file was touched by this task.

### Notable Discoveries

- **The first version of the `accept()` guard had a real race, caught by its own test, not
  by inspection.** The initial implementation re-read `self._socket` inside the `except
  OSError` block to decide "is this a real failure or an intended shutdown". `close()`
  closes the socket *then* sets `self._socket = None` as two separate statements on
  another thread -- so a blocked `accept()` can raise `OSError` from the `close()` call
  while `self._socket` still holds the (now-closed) old socket object, get misclassified
  as an unexpected failure, retry, and on the very next loop iteration call `.accept()` on
  `self._socket`, which has since become `None` -- an unhandled `AttributeError`, not the
  `OSError` the code was written to expect. `pytest`'s
  `PytestUnhandledThreadExceptionWarning` surfaced this on the very first full test run
  even though every individual assertion in that test passed (the exception was thrown on
  a *different* test's thread that happened to still be finishing). Fixed by capturing
  `self._socket` into a local once per loop iteration and never reading the attribute a
  second time after the exception fires. This is exactly the class of thing the task
  brief's "the important half of fix 2 is not the try/except" was warning about --
  the try/except alone was not sufficient, and the loud-failure design added its own new
  failure mode that had to be closed off deliberately.
- **`F10CommandReceiver`'s own close()-during-blocked-`recvfrom` shutdown shape does not
  have this race**, because it has no retry path at all -- *any* `OSError` there just
  returns, so there's nothing to misclassify. The race only appears once retry-on-failure
  is added, which is new behavior this fix introduces relative to every existing
  serve_forever-shaped loop in this codebase.
- No live DCS/Windows trigger exists for either finding (both reviews said so explicitly);
  both fixes are latent hardening, not bug fixes for an observed failure.
