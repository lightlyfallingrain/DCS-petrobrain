---
name: host-specific-always-failing-is-a-real-defect
description: a test that fails every single time on a host, pre-fix and post-fix, with or without randomization, is not "host-specific and out of scope" -- it is a real latent defect in the test's premise, and the fix is to stop depending on that premise (inject the condition), not to leave it failing.
metadata:
  type: feedback
---

On `BL-B92` follow-up (`fix/connection-reporter-flaky`, `plans/connection-reporter-flaky/debug.md`),
the debugger's report measured correctly but concluded wrongly: `test_unreachable_brain_logs_one_
line_without_traceback` reproduced the identical failure (`assert []`) 3/3, pre-fix and post-fix,
with or without `-p no:randomly`, on this host -- a `bind()`-but-never-`listen()`-ed socket does
not refuse `connect()` instantly here, it blocks ~5s, past the test's 2.0s deadline. The report
framed this as "pre-existing, host-specific, out of `BL-B92`'s scope to chase further" and moved
on, verifying the *unrelated* thread-identity fix by injection instead.

**That framing was wrong.** "Cannot be driven to a pass on this machine" is not a verification gap
to work around -- it is the test failing, always, here, which is exactly what "this test is
broken" means. The report's own evidence (3/3, deterministic, both pre- and post-fix) already
proved it was not a flake and not host-timing-coincidental in the BL-B92 sense; it just didn't act
on that distinction.

**Why: a test's *premise* can be false on a given host without the test itself being
unfixable.** The premise here was "a bound-unlistened socket refuses connect() at once" -- true on
whatever host the test was authored against, false on this one. The fix is not "accept this
machine can't verify it" but "stop depending on the host's socket timing at all": monkeypatch the
one call site (`urllib.request.urlopen`) to raise the exact exception shape a real refusal
produces. This makes the test assert what its own docstring always claimed to test (the
`exc_info=` branch for a connection-refused-shaped error), deterministically, on every host --
strictly better than the thing it replaced, not a workaround.

**How to apply:** when a debug/review report says a test "cannot be made to pass on this host" or
"host-specific, out of scope" because of OS/socket/filesystem *timing*, check whether the failure
is a flake (intermittent, order-dependent) or a deterministic 3/3-and-the-same-every-time
always-failure. The latter is a defect to fix, and the fix is almost always "inject the condition
instead of relying on the real OS mechanism" -- the same move `[[caplog-cross-logger-pollution]]`
made for logging-order flakes applies here to OS-timing flakes.
