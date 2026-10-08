---
name: caplog-at-level-masks-default-logging-visibility
description: caplog.at_level(logging.INFO, ...) proves a log call happens, not that it's ever visible under the module's real default configuration
metadata:
  type: project
---

On `feature/bl11-stage4-fail-closed` (`BL-11` Stage 4 step 4), three Reviewer rounds and a Security
deep analysis all mutation-verified that `_log_live_los_coverage_summary`'s `logger.info(...)` call
fires correctly from both poll loops' `finally:` blocks — using
`caplog.at_level(logging.INFO, logger=logger_module.__name__)`. All of that verification was real
and correct about what it tested.

What none of it tested: whether the line is visible on an actual `python -m logger ...` run, with
no test harness involved. It is not. `body-layer/src/` configures no logging handler and no level
anywhere, so Python's `logging.lastResort` fallback applies — threshold `WARNING` (30). An `INFO`
(20) call is silently dropped at runtime even though it fires unconditionally in code and every
`caplog`-based test passes. Caught by running
`python -c "import logger; logger.logger.info('x'); logger.logger.warning('y')"` directly, with no
pytest involved — only `y` printed.

**Why this matters generally**: `caplog.at_level(level, ...)` forcibly overrides the effective
level for the duration of the test block. It is the right tool for "does this call happen, with
this message, at this severity" — it is *not* evidence the message reaches any real sink under the
ambient configuration the shipped code actually runs with. A codebase that never calls
`logging.basicConfig`/`setLevel`/adds a handler can ship a feature whose entire "always-on,
no-flag-needed, visible on every run" design intent (the explicit framing in this plan's own
docstrings) silently fails for every level below `WARNING`, and nothing in a `caplog`-based test
suite will ever show it.

**Check at DoD, not earlier**: grep the touched subproject's `src/` for
`basicConfig|addHandler|setLevel|dictConfig|StreamHandler` before trusting any plan/review/security
claim that a new `logger.info`/`logger.debug` call is "visible by default" or "on for every run
with no flag" — if the grep is empty, run the logger call directly outside pytest and see what
actually prints. `grep` plus one direct `python -c` repro costs under a minute and this defect
survived three review rounds and a security pass without it.

1st occurrence. Watch for a 2nd — if this shape recurs, raise it as a standing DoD check rather
than a one-off catch.
