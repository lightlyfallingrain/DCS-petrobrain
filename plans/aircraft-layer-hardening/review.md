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

---

### Re-review Summary (`ac0bff9`, second pass)

Reviewed `ac0bff9` ("Fix collector accept() shutdown race: explicit flag, not a re-read") against
this review's own required fixes. **Worktree was five commits behind the feature branch at the
start of this pass (third time this session) — fast-forwarded to `ac0bff9` via `git merge --ff-only`
before reading anything**, per the standing warning; the first read of `server.py` in this pass was
against the stale `4c73639` tree and showed no guard at all, which is what caught it.

**Required fix 1 (explicit `self._shutting_down` flag) — done correctly, verified by
reproduction, not just reading.** `self._shutting_down = True` is the first statement of `close()`,
before `self._socket.close()` runs; the `except OSError` block checks `self._shutting_down`
instead of `self._socket is None`. Traced every path that can make `accept()` raise: (a) `close()`
called before the loop's `sock = self._socket` read — top-of-loop `None` check returns cleanly,
flag irrelevant; (b) `close()` called while blocked in `sock.accept()` — flag is set (program order,
same-thread write) before the syscall that unblocks `accept()` on the other thread, so the flag is
always visible by the time the `except` block reads it (CPython's GIL makes a bool attribute write
atomic and immediately visible, so there is no reduced-memory-model escape here); (c) a genuine
unrelated `OSError` — flag is still `False`, correctly logged and retried. I independently
reproduced the fixed behavior outside pytest, 300 runs, `close()` called with **zero delay** after
`thread.start()` (a tighter race window than the test's `0.02s` sleep, and tighter than whatever
timing produced the original 161/230 failures): **0 false ERRORs, 0 stuck threads.** The
happens-before argument is sound as implemented, not just as argued.
- **One real gap, not covered by required fix 1 or by any test: `open()` never resets
  `self._shutting_down` to `False`.** If a `CollectorServer` instance is ever `close()`d and then
  `open()`ed again on the same instance (a restart, or a second `with server:` block — the
  `__enter__`/`__exit__` pair implies exactly this reuse shape), `_shutting_down` stays `True`
  forever, and every subsequent real `accept()` failure on that instance would be silently
  swallowed as "intended shutdown" instead of logged and retried — the exact silent-failure mode
  this whole fix exists to prevent, reintroduced for any reused instance. **Not currently exercised**:
  `__main__.py` constructs one `CollectorServer`, calls `open()` once, `close()` once, at process
  exit (grepped — no restart/retry-the-whole-server call site exists today), and no test reuses an
  instance across a close/open cycle. Because nothing currently triggers it, I'm not blocking on
  this, but it should not be silently carried forward: either reset the flag as the first statement
  of `open()`, or note in `close()`'s docstring that instances are single-use. Optional refinement,
  not a required fix, precisely because it is latent rather than live — but flagging it now costs one
  line, and finding it later would cost another round of "why is the collector silent."

**Required fix 2 (caplog assertion on the clean-shutdown test) — done, and correctly targets ERROR
records specifically.** `test_close_during_a_blocked_accept_ends_the_loop_cleanly` now wraps each
of 20 iterations in `caplog.at_level(logging.ERROR, logger="collector.server")` and asserts
`not error_records`, with `caplog.clear()` between iterations (so a false ERROR from iteration 3
can't be masked by iteration 4's clean pass, and can't leak into iteration 4's own assertion
either). **Would this have caught the original defect?** At a measured ~70% failure rate per run,
20 independent iterations all avoiding an ERROR by chance is `0.3^20 ≈ 3.5e-11` — indistinguishable
from zero, not merely unlikely. Confirmed the assertion is on `logging.ERROR` records specifically
(not "any record," not "no exception raised") — matches the task's ask exactly.
- Minor, not blocking: `test_unexpected_accept_error_is_logged_loudly_and_the_loop_recovers` (the
  *other*, pre-existing test in this file) simulates its own "close() already ran" moment by poking
  `server._socket = None` directly rather than calling `server.close()`, so it never sets
  `_shutting_down`. Post-fix, that means the simulated tail end of that test exercises the *old*,
  now-dead classification path (a `None` `self._socket` with `_shutting_down` still `False`), not
  the new one — harmless today because that test's assertion is `any(...)` over ERROR records
  rather than an exact count, so an extra false ERROR from the mis-simulated shutdown wouldn't fail
  it, but the test's own shutdown simulation is now out of sync with how real shutdown actually
  works. Cosmetic; worth a follow-up only if this test is touched again, not on its own.

**Required fix 3/4 (correct the false claim in all three places, preserve the old entry rather than
rewriting it) — only two of three fully corrected; `implementation.md` is half-done.**
- `server.py`'s docstring and `close()`/`serve_forever()` comments: **fully corrected** — read the
  whole thing; every mention now describes the flag mechanism, and the docstring explicitly narrates
  why the old `self._socket is None` check was unsafe (the two-separate-statements race), not just
  what replaced it.
- The implementer's agent-memory file (`.claude/agent-memory/implementer/project_aircraft_layer_hardening_fixes.md`):
  **fully corrected, and done the right way** — a `**Corrected 2026-09-26 ...**` paragraph replaces
  the false claim in place, states what was wrong and why, cites the 161/230 measurement, and closes
  with a generalizable lesson (a docstring/memory claim about safety is not evidence of safety).
  This is the one the task flagged as mattering most, and it's the most thoroughly done of the three.
- **`implementation.md` is only partially corrected.** A new "Follow-up pass (this entry)" paragraph
  was correctly *appended* right after the summary — this is the right shape, dated and additive, not
  a rewrite of the earlier text — and it accurately narrates the fix. **But two other passages further
  down in the same file, describing the same change, were left untouched and still state the
  disproven claim as current fact, with no correction or pointer to one:**
  - Under "Files Changed" → `server.py`: *"Distinguished from the intended shutdown path ... by
    checking whether `self._socket` has been set back to `None`. ... each iteration captures
    `self._socket` into a local (`sock`) once at the top of the loop ... rather than re-reading
    `self._socket` a second time inside the `except` block"* — this is exactly the false mechanism
    the Follow-up paragraph two sections above just said was wrong.
  - Under "Notable Discoveries": *"Fixed by capturing `self._socket` into a local once per loop
    iteration and never reading the attribute a second time after the exception fires."* — same
    false claim, stated as the resolution.
  
  A reader who reads "Files Changed" or "Notable Discoveries" without also reading the "Follow-up
  pass" paragraph above them (both entirely plausible — they're different sections, and "Files
  Changed" reads as the current, factual state of each file) comes away with the wrong mechanism.
  This is a real, if narrow, instance of exactly the failure this whole review cycle exists to
  prevent: a document stating a safety property the code does not have. **Required fix**: correct or
  annotate those two passages (a one-line "superseded, see Follow-up pass above" note at minimum,
  or an inline correction matching what was done in `server.py`'s docstring) — do not leave the
  document internally contradictory about which mechanism is real.

**Scope**: nothing else changed beyond the required fixes. Diff is exactly
`server.py`/`server.py`'s test file/`implementation.md`/agent-memory — no audio_sender.py change,
no unrelated refactor. I still agree with all three optional items from the first review being left
optional:
- `AudioPlaybackSender.close()`'s blocking `put()` on a bounded queue — still an unlikely,
  shutdown-only-path edge case, not touched, agreed optional.
- Leaked-temp-file assertion on the queue-bound test — still a nice-to-have, not a gap in what's
  actually verified (hand-verified by the previous review), agreed optional.
- Suite-wide `filterwarnings` for `PytestUnhandledThreadExceptionWarning` — still out of scope for
  this small PR, still worth doing; this is the one I'd actually promote to a `todo/todo.md` backlog
  entry rather than leaving it to be re-suggested by the next reviewer who hits the same class of
  bug, since it's cheap, project-wide, and exactly the mechanism that caught the *original* crash in
  the first place (per `implementation.md`'s own Notable Discoveries).

Checks re-run independently from a fresh venv (not trusted from the commit message): `ruff format
--check` — 46 files, clean. `ruff check` — clean. `mypy aircraft-layer/src` (project's
`pyproject.toml` sets `strict = true`) — `Success: no issues found in 18 source files`. `pytest
aircraft-layer/tests -q` — `178 passed` in 27.24s, matching the claimed count exactly (strengthened
in place, not added to). Additionally reproduced the shutdown race directly (see above): 300 runs,
zero-delay `close()`, 0 false ERRORs.

### Re-review Verdict

**APPROVED WITH MINOR FIXES.** Both of this review's required fixes are correctly implemented and
independently verified (one by direct code tracing plus a 300-run stress reproduction, one by
checking the assertion's target and doing the math on 20 reps). The one new required item is small
and mechanical — two passages in `implementation.md` still describe the disproven mechanism as
current fact and need a correction or a pointer to one, the same treatage already given to
`server.py`'s docstring. It is a documentation-only fix (no code or test changes), so this does not
need another Implementer→Reviewer loop for the code itself; whoever picks this up next can patch
`implementation.md` directly and this then goes to DoD. The `open()`-doesn't-reset-the-flag gap and
the mis-simulated shutdown in the *other* test are both noted above as non-blocking (one latent,
currently unexercised; one cosmetic and self-neutralizing) — flagged for awareness, not required.

### Re-review Confidence

Full read of `server.py`, both test files, `implementation.md`, and the implementer's agent-memory
file. Independently re-ran all four checks from a fresh venv rather than trusting the commit
message's numbers. Independently reproduced the shutdown-classification fix under a tighter race
window (zero-delay `close()`, 300 runs) than the implementer's own test uses, rather than trusting
the 20-repetition count alone.
