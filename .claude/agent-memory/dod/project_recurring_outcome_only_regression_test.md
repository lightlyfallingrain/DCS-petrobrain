---
name: recurring-outcome-only-regression-test
description: 2nd occurrence of a regression test asserting only final outward status/exception, not the specific mechanism, for a security/correctness control that sits next to a broader catch-all.
metadata:
  type: project
---

**Pattern, now seen twice:** a regression test for a rejection/guard path asserts only the final
observable outcome (an HTTP status code, a `SystemExit`) rather than *which* code path produced
it — and that outcome turns out to be reachable by more than one mechanism, so disabling the
specific control under test still leaves the assertion passing.

1. **`audio-adapter-review-findings`** (NOTES.md, "Testing & Provenance"/general lessons):
   negative-`Content-Length` tests asserted only `status == 400`, which the pre-fix code already
   produced via an unrelated incidental guard taking a different rejection path to the same
   status code.
2. **`multi-theatre-afghanistan`** (this feature, `plans/multi-theatre-afghanistan/review.md`'s
   "Fix review (f7f2827)"): the security-regression tests for an unregistered-theatre rejection
   asserted only `pytest.raises(SystemExit)`. A broad `except (sqlite3.Error, OSError)` added in
   the same fix (for an unrelated, legitimate robustness reason) converted *any* downstream
   failure — including the one that results from removing the required registry check — into the
   same generic `SystemExit`, so the test could not tell "rejected by the registry check" apart
   from "rejected later, for an unrelated reason." Found empirically (disable the required check
   alone, rerun) by the Reviewer, not by reading.

**Why: this project now has two independent instances of the same root cause** — a broad
catch-all or fallback path sitting near a specific control, where the specific control's own
regression test only checks the shared outward signal both paths produce.

**How to apply:** when a regression test exists specifically to guard a security or correctness
control, and that control sits near any broader exception handler, fallback branch, or shared
error path, assert the *specific* rejection reason (an error message substring, a
`pytest.fail`-on-reach sentinel on the thing the control is supposed to prevent from being
called) — not just the final exception type or status code. This is cheap to add once the
author is thinking about it, and both prior instances were only caught by a Reviewer manually
disabling the control and re-running, not by reading the test. Worth raising as a standing check
at **Reviewer** (not just DoD) whenever a fix adds both a specific guard and a broader catch-all
in the same diff — that combination is exactly the shape both occurrences share. Two is enough to
treat this as a pattern rather than a one-off; flag to the user as process debt that may warrant
a written reviewer checklist item rather than relying on each reviewer rediscovering it.
