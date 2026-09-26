---
name: aircraft-layer-hardening-fixes
description: Bounded audio queue + guarded collector accept() loop; a retry-on-failure loop needs its shutdown-detection read done once per iteration, not twice
metadata:
  type: project
---

Two 2026-09-26 RECOMMENDED review fixes landed in `aircraft-layer/`, no plan.md (scoped
directly from the review docs): bounded `AudioPlaybackSender`'s queue (`_MAX_QUEUE_LEN =
64`, oldest-dropped, mirroring `F10CommandQueue`), and guarded
`CollectorServer.serve_forever`'s previously-unwrapped `accept()` call (log at
`logger.exception`, retry after a backoff, distinguish real failure from an intended
`close()`-triggered shutdown).

**The load-bearing gotcha**: adding retry-on-failure to a `serve_forever`-shaped loop
that also supports `close()`-from-another-thread shutdown introduces a race that a
plain try/except does not have. `close()` does `socket.close()` then `self._socket =
None` as two separate statements; a blocked `accept()` can raise from the `close()` call
while `self._socket` still holds the old (now-closed) object. If the `except` block
re-reads `self._socket` a second time to classify the error, it can misclassify a real
shutdown as a failure, retry, and then call `.accept()` on `None` on the next loop
iteration -- an unhandled `AttributeError`, not the `OSError` everything else expects.
Fix: capture `self._socket` into a local once per loop iteration (`sock = self._socket`,
checked for `None` before the call), never re-read the attribute after the exception
fires. Every other `serve_forever`-shaped loop in this codebase (`F10CommandReceiver`,
`UnitVelocityReceiver`) avoids this because they have *no* retry path -- any `OSError`
there just returns, so there's nothing to misclassify. The race is specific to adding
retry semantics, and pytest's `PytestUnhandledThreadExceptionWarning` is what caught it
(the individual test's assertions all passed; the exception surfaced as a warning
attributed to the thread, easy to miss if not read carefully).

See [[verify_full_suite_not_just_new_files]] — same genre of "the failure isn't in the
assertion you wrote, it's in the warnings section."
