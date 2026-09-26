---
name: aircraft-layer-hardening-fixes
description: Bounded audio queue + guarded collector accept() loop; a shutdown-vs-failure classification needs an explicit flag, not an inference from a value that another thread mutates in two steps
metadata:
  type: project
---

Two 2026-09-26 RECOMMENDED review fixes landed in `aircraft-layer/`, no plan.md (scoped
directly from the review docs): bounded `AudioPlaybackSender`'s queue (`_MAX_QUEUE_LEN =
64`, oldest-dropped, mirroring `F10CommandQueue`), and guarded
`CollectorServer.serve_forever`'s previously-unwrapped `accept()` call (log at
`logger.exception`, retry after a backoff, distinguish real failure from an intended
`close()`-triggered shutdown).

**Corrected 2026-09-26 after Reviewer found the first version's fix was false as
claimed.** The original memory entry here said `self._socket` was "captured into a local
once per loop iteration ... never re-read after the exception fires," and claimed that
was what made shutdown-classification safe. That was wrong about the `except` block
specifically: it *did* re-read `self._socket` a second time (`if self._socket is None:
return`) to decide whether an `OSError` from `accept()` was a real failure or a
`close()`-driven shutdown. Since `close()` does `self._socket.close()` then
`self._socket = None` as two separate statements, a blocked `accept()` can raise from
the `close()` call itself while `self._socket` still holds the old (now-closed) object
-- the read can land between the two statements. The Reviewer reproduced this outside
pytest 300+ times: **161/~230 clean shutdowns logged a false "accept() failed
unexpectedly" ERROR** -- the common case on this platform, not a rare theoretical race,
and it defeated the whole anti-silence point of the guard. `pytest`'s own suite run
never caught this because a single pass through the test only has to get lucky once.

**The load-bearing gotcha, corrected**: shutdown-vs-failure classification for a
`close()`-from-another-thread loop needs an *explicit flag set before the mutation that
can be observed as a failure*, not an inference from a value the same `close()` call
also mutates. Fix: `self._shutting_down = True` as the first statement of `close()`
(before `self._socket.close()` runs), checked in the `except OSError` block instead of
`self._socket is None`. Because the flag write happens-before the syscall that raises
the `OSError` the other thread can observe, this removes the race deterministically
rather than narrowing it. The separate top-of-loop `if sock is None: return` check (a
local captured once per iteration, used for the actual `.accept()` call so a `None`
socket is never dereferenced) was already correct and is unchanged -- it was only the
`except` block's *classification* read that was unsafe, not the call-site guard.
Every other `serve_forever`-shaped loop in this codebase (`F10CommandReceiver`,
`UnitVelocityReceiver`) avoids needing this because they have *no* retry path -- any
`OSError` there just returns, so there's nothing to misclassify. The race is specific to
adding retry semantics.

**Test the classification by running the shutdown path many times, not once.** A ~70%
failure rate still lets a single test run pass "by luck" a meaningful fraction of the
time; `test_close_during_a_blocked_accept_ends_the_loop_cleanly` now loops 20 fresh
server instances and asserts no ERROR record on each one, which is what actually would
have caught the original defect instead of just documenting a claim about it.

See [[verify_full_suite_not_just_new_files]] — same genre of "the failure isn't in the
assertion you wrote, it's in the warnings section." A docstring/memory claim about *why*
code is safe is not itself evidence that it is -- reproduce the actual race before
trusting the inference (this entry existed, stated a false safety property, and would
have misled the next agent had the Reviewer not measured instead of reasoning).
