---
name: recurring-host-specific-premise-mistaken-for-scope-boundary
description: a correct measurement that a test's premise is false on this host got read as "out of scope" by two different roles on the same ticket before either self-corrected -- 2nd occurrence watch
metadata:
  type: project
---

On `fix/connection-reporter-flaky` (BL-B92, 2026-10-23), both the Debugger and, independently, the
Reviewer made the identical inferential error on the same test
(`test_unreachable_brain_logs_one_line_without_traceback`):

1. Measured correctly that a `bind()`-but-never-`listen()`-ed socket does not refuse `connect()`
   instantly on this host (it blocks ~5.0s, confirmed with a bare `socket.create_connection`, no
   test framework involved).
2. Concluded from that correct measurement that the test was therefore "pre-existing,
   host-specific, and out of scope" / "cannot presently be driven to a real pass on this
   particular machine."
3. Both self-corrected later in the same session: the measurement was right, the inference was
   not. The test's own docstring claimed to test "connection refused"; the actual fix was to stop
   depending on real socket timing (monkeypatch `urlopen` to raise the same exception shape a
   refusal produces), not to leave a correctly-diagnosed, always-failing defect unfixed.

**Why this is a recurring-fix pattern, not a one-off**: the same wrong inference ("this
measurement means the test is untestable/out-of-scope here" rather than "this measurement means
the test's premise is wrong") was made by two different roles, independently, on the same ticket,
in the same session. Both agent-memory files from that session already capture their own half:
`.claude/agent-memory/implementer/feedback_host_specific_always_failing_is_a_real_defect.md` and
`.claude/agent-memory/reviewer/feedback_host_specific_measurement_is_not_a_scope_verdict.md`. This
file is the DoD-level roll-up: **2 occurrences, same session** — short of this project's own
"2+ times, raise as a standing earlier check" bar by only the fact that both happened in one
sitting rather than across separate sessions.

**What to do if a 3rd occurrence shows up** (a different ticket, a different role): this becomes
worth a standing check earlier in the chain — e.g. Debugger's own role instructions gaining a line
like "a measurement that a test's premise is false on this host is not itself a scope verdict;
ask whether the premise should change before concluding the test can't be fixed here." Not added
proactively here since two occurrences were both caught and corrected within the same ticket
before reaching DoD — this is a watch, not yet a gap that reached merge.

Also harvested as a general testing/debugging lesson (not role-specific) in
`notes/debugging-and-root-cause-diagnosis.md`.
