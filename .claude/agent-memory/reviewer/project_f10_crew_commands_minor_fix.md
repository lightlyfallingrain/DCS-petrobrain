---
name: f10-crew-commands-minor-fix
description: F10 radio-menu command input reviewed APPROVED WITH MINOR FIXES; caught a flaky test by actually running pytest instead of trusting reported numbers
metadata:
  type: project
---

Reviewed `feature/f10-crew-commands` (Stages 1-3; Stage 4 is user-run live DCS acceptance,
correctly out of scope). Scope, module boundaries, and provenance handling were all clean — the
Hook script (`petrobrain-f10-commands-hook.lua`) matched the live-confirmed research doc mechanism
exactly (`"scripting"` state, `(result, success)` interpretation, fixed-literal snippets, poll
gating tied to `onSimulationStart`/`onSimulationStop`).

**Required fix found only by actually running the tests**: implementation.md reported
"109 passed" for aircraft-layer, but `aircraft-layer/tests/test_f10_command_receiver.py::
test_all_allowed_commands_are_enqueued` failed deterministically in this review's environment,
4/4 runs, with a different observed order each time. Root cause: the test's `_send` helper opens a
brand-new UDP socket per datagram and then asserts the three datagrams arrive in send order — UDP
delivery order across independently-created sockets isn't guaranteed by the OS even on loopback.
The real Hook script doesn't have this problem: `sendToken` opens one `sendSocket` and reuses it
across all sends in a poll cycle, a materially different (more order-preserving) pattern than the
test's one-socket-per-datagram loop. This reinforces [[feedback_rerun_mypy_dont_trust_log]]'s
lesson at the pytest layer too, not just mypy: rerun the actual test suite yourself rather than
trusting a reported pass count, especially for any test that touches real sockets/threads/timing.

See [[feedback_verify_mypy_cwd_claims_by_reproduction]] for the same "reproduce it yourself"
discipline applied to a different check.
