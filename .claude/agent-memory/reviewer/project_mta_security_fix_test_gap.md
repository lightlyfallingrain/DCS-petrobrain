---
name: mta-security-fix-test-gap
description: multi-theatre-afghanistan security fix (f7f2827) -- required-fix test passed even with the required fix removed
metadata:
  type: project
---

Reviewed the security fix for `plans/multi-theatre-afghanistan/security.md`'s required fix
(validate `theatre` against `THEATRE_PROJECTIONS` before building a path/URI in
`body-layer/src/logger.py`). The fix code itself was correct and placed before path construction.
But empirically disabling *only* the required fix (keeping the optional
`try/except (sqlite3.Error, OSError)` around the mismatch guard) still passed all 5 new tests,
because that optional fix's broad except converts *any* downstream failure -- including the
ones an unvalidated theatre would now cause -- into the same generic `SystemExit` the tests check
for. Disabling both fixes together did fail all 5, so the suite caught total regression but not
the required fix specifically regressing later.

**Why:** a security-required-fix test that only asserts `pytest.raises(SystemExit)` (plus a loose
side-effect check like "no file matching this glob exists") can pass for the wrong reason when an
adjacent, unrelated robustness fix also converts failures to the same exception type. The two
fixes' tests become entangled without anyone intending it.

**How to apply:** whenever a plan bundles a required security fix with an optional
robustness/error-handling fix touching the same code path, empirically disable the required fix
*alone* (leaving the optional one in place) and rerun its tests -- not just both-disabled. If the
tests still pass, they're asserting on the wrong signal (exception type/control flow) rather than
the actual rejection reason (error message content, or that a specific downstream call was never
reached). This is a sharper version of [[feedback_regression_test_empirical_check]] -- disabling
"the fix" isn't enough when there are two fixes in one diff; each needs its own isolated disable.

Also found in the same review: a parametrized test payload (`"Syria?mode=rwc"`) named after a
specific vulnerability (SQLite URI query-string injection) didn't actually reproduce it --
security.md's own demonstration needed a second `&`-separated query parameter
(`?mode=rwc&dummy=-full.sqlite`) for SQLite's URI parser to split the string the injection depends
on; the single-parameter form just raises a malformed-access-mode error instead. Check that an
"attack payload" test input actually reproduces the cited demonstration, not just that it looks
similar.
