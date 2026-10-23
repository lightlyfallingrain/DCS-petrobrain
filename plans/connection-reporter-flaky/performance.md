### Performance Review

Scope: `fix/connection-reporter-flaky`, `git diff f4e552c1 08630ae7` (tip `08630ae7`). Test-only
change in `body-layer/tests/test_logger.py` and `body-layer/tests/test_brain_client.py` — no
`src/` file touched. No subproject phase budget applies here (not a runtime hot path, not the
offline build pipeline); this is a short pass per the task's own scoping.

### Findings

#### `caplog.records` filtering by logger name / thread id
- **Location:** three `test_connection_reporter_*` tests (filter by `record.name ==
  logger_module.__name__`) and `test_unreachable_brain_logs_one_line_without_traceback` (filter by
  `record.thread == worker.ident`) in `body-layer/tests/`.
- **Risk:** none credible. Each filter is a single list comprehension over `caplog.records`, which
  in these tests holds at most a handful of entries (one test's own log lines plus, rarely, one
  stray record from a leaked background thread). This runs once per test, in test code, not on any
  runtime hot path Petrobrain ships.
- **Action:** MONITOR (nominal — no follow-up expected).
- **Mitigation:** none needed.

#### Monkeypatched `urllib.request.urlopen` replacing a real bound-but-unlistened socket connect
- **Location:** `test_unreachable_brain_logs_one_line_without_traceback`,
  `body-layer/tests/test_brain_client.py`.
- **Risk:** none — this is a pure win, not a risk. The prior version opened a real socket and, on
  this host, blocked for the client's full 5.0 s `poll_timeout_s` before the connection attempt
  failed (per `debug.md`'s measurement); the deadline loop then still waited up to its own 2.0 s.
  The monkeypatch raises `URLError` synchronously, so the test now proceeds as soon as the worker
  thread's first retry fires rather than after a multi-second real-socket timeout.
- **Action:** MONITOR (positive effect, not a defect).
- **Mitigation:** n/a.

### Test-suite wall-time effect

Net effect is faster, not slower:
- The previous `test_unreachable_brain_logs_one_line_without_traceback` depended on a real socket
  connect that, per `debug.md`, took ~5.0 s to fail on the host it was investigated on (exceeding
  its own 2.0 s poll deadline and failing outright there) — the fix removes that real-socket wait
  entirely in favor of a synchronous, monkeypatched raise.
- The added `caplog.records` filters are O(n) over a tiny per-test record list — no measurable
  per-test cost.
- `debug.md`'s own verification runs report the same full-suite baseline (2445 passed / 4
  xfailed) before and after, with no reported wall-time regression, consistent with this being a
  net speed-up, not merely neutral.

No production code (`src/`) was touched, so there is no runtime-path cost to assess at all — the
whole-theatre pipeline and per-request runtime constraints in this role's brief do not apply to a
test-only diff.

### Verdict
APPROVED
