---
name: logger-main-untested-by-design
description: body-layer/src/logger.py's main() has no CLI/argparse test coverage by design -- factor testable decision logic into pure module-level functions instead of testing main() directly.
metadata:
  type: project
---

`body-layer/src/logger.py`'s `main()` docstring states it is "Not exercised by automated tests"
(a live/replay-loop driver, same posture as `aircraft-layer/src/collector/__main__.py`'s `main()`).
This is accurate for the *whole* function, including its argparse construction and validation --
before 2026-09-24 there was zero test coverage of any `parser.error(...)` branch or CLI flag
default in this file.

**How to apply:** when a plan needs new CLI-flag behaviour in `logger.py` (a new default, a new
validation) that should be tested, don't try to drive `main()` end-to-end. Factor the decision
logic into a small pure module-level function (e.g. `_resolve_speech_log_path`) that takes plain
values, not an `argparse.Namespace`, and call it from `main()` after `parser.parse_args()`. That
function gets full unit coverage; `main()`'s own untested-by-design posture is preserved. Only
reach for a real `sys.argv` + `pytest.raises(SystemExit)` test (see
`test_speech_log_cli_validation_rejects_speech_log_with_no_speech_log` in `test_logger.py`) for a
check that has to live in argparse's own error path itself (e.g. a `store_true`/value mutual
exclusion), and keep that to the minimum needed -- one such test, not one per flag.
