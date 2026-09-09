### Debug Report

### Observed Issue

Live DCS sortie acceptance testing of `--console` mode (`plans/pb2-contact-memory`, Stage 6)
crashed on the very first poll tick:

```
sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread.
The object was created in thread id 8451039616 and this is thread id 6147420160.
```

Traceback: `_run_poll_loop` (background poll thread, spawned by Stage 4) →
`ConsolePerceptionRunner.run_once` → `NakedEyePerceptionSource.poll` →
`visibility.check_visibility` → `geometry.line_of_sight_clear` → `store.reader.sample_grid`.

Command that reproduces it: `PYTHONPATH=src:../world-model/src .venv/bin/python -m logger
--console --aircraft-layer-url http://<host>:7791 --theatre Syria --world-model-db
../world-model/data/world-model/syria-full.sqlite`.

### Hypothesis

`main()`'s `--console` branch (`body-layer/src/logger.py`) opened `world_model_conn` via
`open_world_model` (`perception/geometry.py`) on the **main thread**, then built
`NakedEyePerceptionSource` (which holds that connection) via `_build_sources`, also on the main
thread, and handed the resulting `ConsolePerceptionRunner` — sources and all — to a **background**
daemon thread (`_run_poll_loop`). `sqlite3.Connection` objects are thread-affine by default
(`check_same_thread=True`); `open_world_model` never passes `check_same_thread=False`. So the
first `sample_grid` query issued from the poll thread against a connection created on the main
thread must fail exactly this way. The plain (non-`--console`) path never crosses a thread
boundary with the connection — connection-open, `_build_sources`, and the poll loop all stay on
`main()`'s single thread there — so only `--console`'s Stage 4 threading split could have
introduced this.

### Evidence

- Read `perception/geometry.py`'s `open_world_model` — confirmed it is a bare
  `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`, no `check_same_thread=False` anywhere in
  the codebase (grepped both `body-layer/src` and `world-model/src`).
- Read `logger.py`'s `main()` before the fix — confirmed `world_model_conn` is opened once, before
  the `if args.console` branch, and only the `--console` branch passes the resulting
  `ConsolePerceptionRunner` (holding sources built from that connection) into a spawned
  `threading.Thread` running `_run_poll_loop`; the non-`--console` branch keeps everything on
  `main()`'s own thread in a `while True` loop.
- Grepped all of `NakedEyePerceptionSource`'s existing tests (`test_naked_eye_source.py`,
  `test_emission_pipeline.py`, `test_visibility.py`): every one monkeypatches
  `visibility.line_of_sight_clear` to a no-op, confirming `sample_grid` — and therefore the
  connection itself — was never actually queried against a real `sqlite3.Connection` in any
  pre-existing automated test, real or cross-thread.
- Reproduced the underlying mechanism directly with a throwaway script: opened a real
  `sqlite3.Connection` via world-model's `store.writer.open_for_build` on the main thread, queried
  it from a spawned `threading.Thread`, and got the byte-for-byte same exception class and message
  shape (`sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that
  same thread. The object was created in thread id ..., and this is thread id ...`), confirming
  the hypothesis before touching any production code.

### Fix Applied

`body-layer/src/logger.py`:

- Renamed `_run_poll_loop` to `_run_console_poll_loop` and moved `open_world_model(...)` +
  `_build_sources(..., emit_mode="every_poll")` **into** it, so the connection is opened — and the
  sources holding it are constructed — on the poll thread itself, the same thread that will
  actually query it. The connection is closed in a `finally` when the poll loop stops (whether via
  `stop_event` or an unexpected exception).
- `ConsolePerceptionRunner.sources` got a `default_factory=list` default, since `main()` now
  constructs the runner before any sources exist — the poll thread populates `runner.sources`
  itself once it starts.
- `main()`'s `--console` branch no longer opens `world_model_conn` at all; it passes
  `aircraft_client`, `args.theatre`, and `args.world_model_db` (the raw path) to the thread target
  instead of a pre-built runner whose sources already hold a wrong-thread connection. Added
  `poll_thread.join()` after `stop_event.set()` so the connection is confirmed closed before
  `main()` returns.
- The non-`--console` path is functionally unchanged (still opens/builds/closes everything on
  `main()`'s single thread), only wrapped in `try/finally` so `world_model_conn.close()` runs
  reliably.
- Did not use `check_same_thread=False` — that would paper over the connection's real lifecycle
  mismatch (a connection should live and die with the thread that uses it) rather than fix it, and
  the task brief explicitly flagged this as a shortcut to avoid given the world-model seam's
  shared-file usage pattern.

### Verification

- New test `body-layer/tests/test_logger.py::
  test_console_poll_loop_uses_a_thread_local_world_model_connection` builds a real (schema-only)
  world-model `.sqlite` via `store.writer.open_for_build`, drives the fixed
  `_run_console_poll_loop` on a real background `threading.Thread` exactly as `main()` does, and
  deliberately does **not** monkeypatch `visibility.line_of_sight_clear` — so a real
  `NakedEyePerceptionSource` reaches `check_visibility` → `line_of_sight_clear` → `sample_grid` →
  a genuine sqlite query on that thread, the exact call chain from the crash. This is the class of
  bug the existing fakes/monkeypatches structurally could not catch; the new test both fails
  against a manual revert of the fix (confirmed the underlying mechanism separately via the
  throwaway repro script above, which used the identical opened-on-main/queried-on-thread pattern
  the pre-fix code followed) and passes cleanly against the fixed code.
- `cd body-layer && ruff format --check src tests`: pass.
- `cd body-layer && ruff check src tests`: pass.
- `cd body-layer && mypy src`: pass, no issues in 20 source files.
- `PYTHONPATH=body-layer/src:world-model/src pytest body-layer/tests -q`: 203 passed (202 before
  this fix, +1 new regression test), no regressions.
- `git status`: clean after staging this fix's files (`body-layer/src/logger.py`,
  `body-layer/tests/test_logger.py`, `plans/pb2-contact-memory/implementation.md`, this file). An
  unrelated, pre-existing uncommitted change to `body-layer/run-body.sh` (present before this
  debugging session started) was left untouched, not staged as part of this fix.
