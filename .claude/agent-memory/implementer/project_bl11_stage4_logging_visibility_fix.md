---
name: bl11-stage4-logging-visibility-fix
description: logging.lastResort defaults to WARNING; a caplog-only test suite can't see it; fix stays scoped to one named logger
metadata:
  type: project
---

`body-layer/src/logger.py` configured no logging handler/level anywhere. With none set in the
hierarchy, Python falls back to `logging.lastResort`, threshold `WARNING` (30) — every
`logger.info(...)` call (including `_log_live_los_coverage_summary`'s unconditional end-of-run
line, `BL-11` Stage 4) was silently dropped on every real run, while `logger.warning(...)` calls
printed by accident of that same fallback's threshold matching. Found by DoD, not by three review
rounds or a security pass — every existing test used `caplog.at_level(logging.INFO, ...)`, which
forcibly overrides the level for its block and proves the call fires, never that it is visible
under the ambient (unconfigured) default a real sortie actually runs with.

Fix: `_configure_logger_for_main()`, called as `main()`'s first statement, scoped to *this
module's own* `logging.getLogger(__name__)` — never `logging.basicConfig`/root. Named loggers
only compose hierarchically when one name is a dotted prefix of another; `"logger"` is not a
parent of `"perception.hybrid_source"` or `"belief.crew_console"`, so raising this one logger's
level cannot also turn on another module's unrelated `INFO` call site (which, surveyed first,
included a genuine per-poll flood risk — `hybrid_source._record_drop`). Before picking the fix,
grep every `logger.info` call site in the subproject and check its call frequency — a global
`basicConfig` would have silently re-created the same defect class in reverse (silence -> flood).

Handler management: clear-and-re-add on every call, not `if not logger.handlers:` guarded. A
guard binds `StreamHandler(sys.stderr)` to whichever stream was current on the *first* call and
never rebinds — harmless in production (`main()` runs once per process) but wrong for a test that
calls `main()` directly under `capsys`: a guard would bind to test 1's captured stream and go
silent for every later in-process `main()` call in the same session.

Test requirement that mattered most: at least one test with **no `caplog.at_level` anywhere**,
capturing real `sys.stderr` via `capsys` and asserting the line is present in it. Proved it could
go red by removing the `_configure_logger_for_main()` call: the test failed on the real-stderr
assertion while pytest's own "Captured log call" section still showed the record — i.e. the call
fired but was not visible, which is the exact distinction a `caplog`-only suite cannot draw.

See [[feedback_counterfactual_must_not_perturb_a_constant_the_test_imports]] for the general
"prove red for the stated reason" discipline this round followed via `shasum` before/after on the
removed call, restored with `Edit`.
