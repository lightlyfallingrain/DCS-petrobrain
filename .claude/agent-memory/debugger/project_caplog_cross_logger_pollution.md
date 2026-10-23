---
name: caplog-cross-logger-pollution
description: caplog.at_level(logger=name) only scopes level, not which records are captured -- any propagating logger anywhere in the process can land in an unrelated test's caplog.records, and body-layer has several never-stopped daemon threads that do exactly this.
metadata:
  type: project
---

`caplog.at_level(level, logger=name)` only sets the **level** of the named logger for the
`with` block. It does **not** limit which records appear in `caplog.records` — pytest's
`LoggingPlugin` attaches its capture handler to the **root** logger unconditionally for every
test's call phase (`_pytest/logging.py`, `catching_logs.__enter__`), regardless of the `logger=`
argument. Any logger in the process that propagates to root (the default; nothing in body-layer
sets `propagate = False`) can contribute a stray record to an unrelated test's `caplog.records`
if its timing happens to coincide.

**body-layer has at least one source of this already, and it is a known, accepted leak, not
something to "fix" by stopping the thread**: `belief/brain_client.py`'s `BrainLayerClient.
_poll_loop` is a `daemon=True` thread, started lazily on the first `poll_replies()` call, with
no `close()`/`stop()` anywhere in the class — tests in `test_brain_client.py`/
`test_crew_console.py` that point a `BrainLayerClient` at an unreachable URL leave this thread
running for the *rest of the pytest session*, retrying every `_POLL_RETRY_BACKOFF_S` (1.0 s) and
logging `"background brain reply poll failed (retrying)"` via its own
`logging.getLogger("belief.brain_client")` on every attempt. `_run_plain_logger_main_for_n_polls`'s
own docstring in `test_logger.py` already documents this as a known fact about the suite.

**Why this makes an `assert caplog.records == [...]`-style test order-dependent *and*
non-deterministic given the same `--randomly-seed`**: the pollution's timing is wall-clock
coincidence (whichever test happens to be executing its call-phase capture window at the moment
the leaked thread's periodic retry fires), not something the collection-order seed alone pins.
Reruns of the identical seed can produce a different failing test, or none at all. This cost real
investigation time on `BL-B92` before the mechanism was found (`plans/connection-reporter-flaky/
debug.md`) — if a `body-layer` test asserts an exact `caplog.records` list and fails
intermittently under `pytest-randomly` but passes in isolation and with `-p no:randomly`, check
this mechanism *before* suspecting handler/level state on the module's own logger. Diagnostic
tell: the extra record's `logger.name` in the failure output is a logger the test under
investigation never touches (e.g. `belief.brain_client` showing up in a `logger.py`-focused
test).

**Fix pattern applied on `BL-B92`**: filter `caplog.records` to `record.name ==
<module_under_test>.__name__` before asserting, rather than trusting the capture to already be
scoped to that logger. This is the narrow, correct fix for the *asserting* test — it does not
require stopping the leaking daemon thread, which is a separate, broader, already-accepted
tradeoff elsewhere in the suite.

**When two different leaked-thread instances share the same logger name, filtering by logger
name is not enough** — `tests/test_brain_client.py::test_unreachable_brain_logs_one_line_
without_traceback` is exactly this case: its own `BrainLayerClient` and some *other* test's
already-leaked `BrainLayerClient` both log via `belief.brain_client`. The discriminator that
works there is **thread identity**: keep a reference to the client's own worker thread
(`client._poll_worker`, a pre-existing field) and filter `record.thread == worker.ident`. Safe
because two *live* daemon threads never share an `ident` — Python only recycles one after the
owning thread has fully exited, and a leaked `_poll_loop` never exits. (A synthetic repro that
modeled the "leaked" thread as short-lived instead of alive-the-whole-time gave a false negative
here — `ident` got recycled once the short-lived thread exited — so get this detail right when
writing a similar injection test.)

**A second, unrelated bug class also masquerades as an "order-dependent" `pytest-randomly`
flake in this codebase**: `tests/test_tuning.py`'s `autouse` fixture calls `tuning.
reset_for_testing()` (clearing the module-level `_state` singleton) both before *and after*
every test in that file. Since every tunable constant registers itself against that singleton
**once, at import time** (Python caches imports), clearing it after `test_tuning.py`'s own tests
run leaves it permanently empty for the rest of the session — any later call to `render_print_
tuning` through `main()` gets a fresh, empty `Resolution`. This produced `test_main_print_tuning_
works_without_aircraft_layer_url`'s flake (`"at default" not in out`) and has nothing to do with
caplog/logging — it's a module-level registry reset leaking across test *files*. Worth checking
for this shape (an autouse fixture resetting a process-wide singleton with no corresponding
re-registration path) whenever an "order-dependent" test's assertion is about something other
than logging output.
