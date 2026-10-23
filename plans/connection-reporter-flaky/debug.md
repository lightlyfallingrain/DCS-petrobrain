### Debug Report

### Observed Issue

Two `body-layer` tests fail intermittently under `pytest-randomly`'s random test ordering, pass
in isolation, and pass reliably with `-p no:randomly`:

- `test_connection_reporter_announces_the_first_connection` (noted 2026-10-22 in `BL-B80`'s DoD
  pass, attributed to `a5def59e`)
- `test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop` (noted 2026-10-23,
  `plans/guidance-ready-edge/dod-check.md`)

Both assert an exact list of `_ConnectionReporter`-emitted messages via
`[r.getMessage() for r in caplog.records]`, inside a `caplog.at_level(logging.INFO,
logger=logger_module.__name__)` block.

### Hypothesis (confirmed)

**Root cause is not test-order-dependent state on the `logger` module's own logger or handlers —
it is cross-logger pollution of `caplog.records` from an unrelated, permanently-leaked background
thread**, and the pollution's timing is wall-clock-coincidental, not pinned by `--randomly-seed`.

`caplog.at_level(level, logger=name)` only scopes the **level** of the named logger for the
duration of the `with` block. It does **not** limit which records land in `caplog.records`:
pytest's `LoggingPlugin` attaches its capture handler to the **root** logger unconditionally for
every test's call phase (`_pytest/logging.py`, `catching_logs.__enter__`), regardless of the
`logger=` argument any individual test passed to `at_level`. Any logger anywhere in the process
that propagates to root (the default, and nothing in this codebase sets `propagate = False`)
contributes to `caplog.records` for whichever test happens to be running when it fires.

`belief/brain_client.py`'s `BrainLayerClient._poll_loop` is a `daemon=True` background thread,
started lazily on the first `poll_replies()` call and **never stopped** — this is an
already-documented, accepted characteristic of the suite
(`_run_plain_logger_main_for_n_polls`'s own docstring in `tests/test_logger.py` describes exactly
this: "a leftover `belief.brain_client.BrainLayerClient` daemon poll thread from an earlier test
... still retry-backoff-sleeping because nothing stops a `daemon=True` thread"). Several tests in
`tests/test_brain_client.py` and `tests/test_crew_console.py` construct a `BrainLayerClient`
against an unreachable URL (`http://127.0.0.1:1`, "nothing listening") specifically to exercise
the retry path. Once started, that thread retries forever, once every `_POLL_RETRY_BACKOFF_S`
(1.0 s), logging `"background brain reply poll failed (retrying)"` via its own
`logging.getLogger("belief.brain_client")` — a different logger than `logger.py`'s own — on every
failed attempt, for the rest of the pytest session (the thread is never joined or stopped; it
dies only when the process exits).

Because the full suite runs in ~18-19 s and the leaked thread keeps firing roughly once a second
for whatever remains of that run, and because nearly the entire wall-clock duration of a pytest
run is covered by *some* test's call-phase capture window, one of those periodic retries will,
on a large fraction of runs, land inside whichever test happens to be executing at that exact
moment — and under `pytest-randomly`'s shuffle, which test that is varies from run to run (it is
not determined by the seed value alone; it depends on real scheduling/timing jitter, which is why
repeated runs of the *same* `--randomly-seed` did not reproduce the same failure during
investigation — one run failed `test_connection_reporter_announces_the_first_connection`, an
immediate rerun of the identical seed instead failed an unrelated test,
`test_main_print_tuning_works_without_aircraft_layer_url`, a **separate, pre-existing, also
order-dependent flake outside this bug's scope** — not touched here).

### Evidence

- **Direct reproduction, pre-fix, seed 56**: a full-suite sweep across `--randomly-seed` values
  (1-100) against the *unmodified* test file reproduced the real failure, with the exact predicted
  log lines:

  ```
  Captured log call
  WARNING  belief.brain_client:brain_client.py:307 background brain reply poll failed (retrying)
  INFO     logger:logger.py:2063 aircraft layer connected

  FAILED tests/test_logger.py::test_connection_reporter_announces_the_first_connection
  ```

  This is not the injected repro below — it is the real leaked daemon thread's own retry warning,
  landing in `caplog.records` for this test, exactly as the mechanism predicts. Re-running
  `--randomly-seed=56` after the fix (same section below): full suite passes, 2445 passed /
  4 xfailed, same baseline as before.
- Confirmed the leak path by reading `src/belief/brain_client.py`: `_poll_worker`/`_worker` are
  `daemon=True` threads with no `close()`/`stop()` method anywhere in the class, and
  `_poll_loop`'s `except BrainLayerError` branch calls
  `logger.warning("background brain reply poll failed (retrying)", ...)` on its own
  `logging.getLogger(__name__)` (`"belief.brain_client"`), then `time.sleep(_POLL_RETRY_BACKOFF_S)`
  (1.0 s) and loops forever.
- Found a real failing seed by sweeping `--randomly-seed` values against the full suite
  (`pytest-randomly` was not installed in `body-layer/.venv`; installed it for this
  investigation — it is a dev-only test tool, not a production dependency, so `pyproject.toml`
  was not touched): **seed 36** reproduced
  `FAILED tests/test_logger.py::test_connection_reporter_announces_the_first_connection`.
  Re-running the identical seed three more times did *not* reproduce the same failure (it
  reproduced the unrelated tuning flake instead each time) — confirming the failure is
  timing-coincidental, not seed-deterministic, which rules out ordinary state-leak-via-object
  hypotheses (each test constructs a fresh `_ConnectionReporter()`; no shared mutable state there)
  and points at a race against something that fires on its own clock.
- Deterministic proof of the exact mechanism: a standalone repro test ran the *actual*
  `_ConnectionReporter` call sequence inside `caplog.at_level(logging.INFO,
  logger=logger_module.__name__)`, and, inside that same `with` block, emitted one record from
  `logging.getLogger("belief.brain_client")` (a stand-in for the leaked thread's real retry log).
  Pre-fix, `caplog.records` contained both messages and the exact-list assertion failed with
  exactly the kind of extra/out-of-order message the real flake reports. Filtering
  `caplog.records` to `record.name == logger_module.__name__` removed the injected record and the
  assertion passed. Stress-tested the fix against the real, patched
  `test_connection_reporter_announces_the_first_connection` function directly (not a
  reimplementation) with a background thread hammering the unrelated logger at ~1000x the real
  leak's rate for 500 iterations — passed throughout; the unfiltered pre-fix version, run against
  the identical adversarial noise, failed on its very first iteration.

### Fix Applied

`body-layer/tests/test_logger.py`, all three `test_connection_reporter_*` tests (the exact-match
group BL-B92 names): filter `caplog.records` to this module's own logger before asserting,
instead of trusting `caplog.at_level(logger=name)` to have already scoped the captured records to
that logger:

```python
messages = [
    r.getMessage() for r in caplog.records if r.name == logger_module.__name__
]
assert messages == [...], messages
```

This is the narrowest fix that makes the whole group order-independent: it does not touch
`_ConnectionReporter`, `_configure_logger_for_main`, or anything about how `logger.py` configures
logging, and it does not touch the leaked-daemon-thread design in `belief/brain_client.py` (which
is a separate, already-accepted tradeoff documented elsewhere in this test file and out of this
bug's scope — stopping it would be a broader change touching every test that exercises
`BrainLayerClient` against an unreachable URL, not a fix to these three tests). It also does not
weaken any assertion's content: the exact-message-list pin that each test's docstring explains
("these are lines a person reads on a terminal while flying") is unchanged — it now simply checks
what `_ConnectionReporter`'s own logger said, which is what each test's docstring already claimed
to be testing, rather than what every logger in the whole pytest process happened to say during an
arbitrary wall-clock window. Added a docstring note on all three tests (one full explanation on
the first, cross-referenced by the other two) so a future reader does not reintroduce the
unfiltered form.

### Verification

- `ruff format --check src tests` — PASS (163 files already formatted)
- `ruff check src tests` — PASS (all checks passed)
- `cd body-layer && .venv/bin/mypy src` (strict) — PASS (71 source files, no issues)
- `pytest body-layer/tests -q -p no:randomly` — PASS (2445 passed, 4 xfailed — same baseline as
  the last DoD pass)
- `pytest body-layer/tests -q --randomly-seed=36` (the seed that reproduced the real failure) —
  PASS, `test_connection_reporter_*` group green (one unrelated pre-existing flake,
  `test_main_print_tuning_works_without_aircraft_layer_url`, still occurs under this seed — not in
  scope, see "Hypothesis" above)
- `pytest body-layer/tests -q --randomly-seed=<n>` for seeds 1-10, 36, 56, and 100-150 (61 seeds
  total) — `test_connection_reporter_*` group passed in every single run, including the two seeds
  (36, 56) that reproduced the real failure pre-fix
- Direct adversarial stress test against the real patched test function (500 iterations under a
  background thread spamming the unrelated logger at ~1000x the real leak's retry rate) — passed;
  the pre-fix unfiltered form failed immediately under identical noise, confirming the fix
  specifically closes the mechanism identified above and is not a coincidental pass.
- `pytest body-layer/tests/test_brain_client.py -q -p no:randomly` — **1 failed** (
  `test_unreachable_brain_logs_one_line_without_traceback`), **10 passed**; confirmed this one
  failure is the pre-existing host-specific socket-timing issue described below, not a
  regression (reproduces identically against the unmodified pre-fix code on this host, with or
  without `pytest-randomly`). The thread-identity fix itself verified by deterministic injection
  instead — see below.

### Two more flaky tests reported mid-investigation — checked against the same root cause

The coordinator reported two more tests seen failing under `pytest-randomly`'s default order on
an unmodified base, both logging-output assertions:

- `tests/test_logger.py::test_main_print_tuning_works_without_aircraft_layer_url`
- `tests/test_brain_client.py::test_unreachable_brain_logs_one_line_without_traceback`

**`test_main_print_tuning_works_without_aircraft_layer_url` — does not share this root cause. Not
fixed here.** It asserts over `capsys`-captured stdout, not `caplog` — no logger involved at all.
Reading `src/tuning.py` and `tests/test_tuning.py`: `tuning.py` keeps one module-level `_state`
singleton (`_get_state()`), lazily built once and never rebuilt in production — every tunable
constant's own module (`attack_run.py`, `visibility.py`, etc.) registers itself against that one
`Resolution` object via its own `tuning.real(...)`/`tuning.whole(...)`/etc. call **at import
time**, which (because Python caches imports) happens exactly once per process, during test
collection. `tests/test_tuning.py` has an `autouse` fixture that calls `tuning.reset_for_testing()`
(`_state = None`) both before *and after* every test in that file, "so the module-level cache
from a previous test ... does not leak in" (that file's own module docstring) — intentional for
*that* file's own tests, but it leaves the **shared global `_state` reset to `None` for the rest
of the pytest session** once the file's own tests are done. The next time anything calls
`render_print_tuning`/`validate_against_defaults` through `main()`, `_get_state()` lazily rebuilds
a **fresh, empty** `Resolution` — and since every tunable module was already imported once and
will never call its `tuning.real(...)` accessor again, that fresh `Resolution`'s `.defaulted`
dict stays permanently empty, which is exactly the observed symptom (`"at default" not in out`,
only the header line printed). Confirmed by reading the mechanism; this is a genuine *global
registry reset leaking across test files*, not a caplog/root-propagation/leaked-thread issue —
a different bug class entirely. Flagging as its own issue rather than filing a `BL-B` id myself
(ID minting is the main loop's/architect's call); worth isolating `test_tuning.py`'s autouse
reset (e.g. only resetting, not leaving `_state = None` for every *other* file for the rest of
the session — perhaps restoring the pre-test state in the fixture's teardown rather than clearing
it) in a dedicated fix.

**`test_unreachable_brain_logs_one_line_without_traceback` — shares the root-cause *family*
(leaked `BrainLayerClient` daemon thread + shared logger name landing in an unrelated capture
window), one layer deeper. Fixed here.** This test's own `BrainLayerClient` and *any other* test's
leaked, never-stopped `BrainLayerClient` daemon thread (e.g. `test_invalid_reply_still_logs_a_
traceback`'s, which keeps a traceback) log via the **same** `belief.brain_client` logger name —
so, unlike the connection-reporter tests (where filtering by logger name was enough, because only
one call site in the whole process uses that logger), filtering by logger name here is not enough
to tell "my client's record" from "a different, already-leaked client instance's record" that
happens to land in the same capture window. The original code took `caplog.records[0]`
unconditionally, which can be the wrong instance's record — with the wrong `exc_info`, which is
exactly what this test asserts about.

**Fix**: keep a reference to this test's own `client._poll_worker` thread (the real worker
`poll_replies()` starts, a pre-existing dataclass field) and filter `caplog.records` to
`record.thread == worker.ident` before taking the first match — the one discriminator that
correctly distinguishes *this* client's own background thread from any other leaked one sharing
the same logger name, since two live daemon threads never share a thread identity while both are
alive (Python only recycles a thread's `ident` after it has fully exited, and a leaked
`BrainLayerClient`'s `_poll_loop` never exits).

**Verification note — a separate, unrelated host-specific finding limited live verification of
this one test on this machine.** Investigating why this test's own live-socket race couldn't be
reproduced via the usual seed-sweep method surfaced that *on this specific host*, connecting to a
TCP socket that is `bind()`-but-never-`listen()`-ed does **not** refuse instantly (contrary to
this test's own comment, "connect is refused at once") — it blocks until `urllib`'s 5.0 s
`poll_timeout_s` elapses (confirmed directly: a bare `socket.create_connection` to such a socket
measured ~5.0 s before raising `TimeoutError`, both inside and outside the tool sandbox).
Confirmed this is **pre-existing and unrelated to this fix**: running the *original, unmodified*
test logic standalone on this host reproduces the identical failure (zero `caplog.records` after
the test's 2.0 s wait, regardless of ordering, regardless of `-p no:randomly` vs. any seed) — so
this one test cannot presently be driven to a real pass on this particular machine, with or
without the fix above, and was already failing on `main` here before this investigation began.
This is almost certainly a difference in this host's TCP stack/sandbox behavior for a bound-but-
unlistened socket versus whatever environment the test was authored and last verified against,
not a defect in `BrainLayerClient` or in the fix — worth its own research note if it recurs
elsewhere, but out of `BL-B92`'s scope to chase further here.

Because the live-socket path can't be exercised to a pass on this host, the thread-identity fix
was verified by **direct deterministic injection** instead (same method used above for the
connection-reporter fix): a synthetic test started a long-lived "leaked" thread that logs via
`belief.brain_client` *with* `exc_info` (standing in for a real leaked instance), then started a
second thread logging the same message *without* `exc_info` (standing in for this test's own
client) while the leaked thread was still alive. Unfiltered `caplog.records[0]` picked up the
leaked thread's record (`exc_info` present) — reproducing the reported failure's shape exactly.
Filtering by `record.thread == <own thread>.ident` picked the right one every time.
