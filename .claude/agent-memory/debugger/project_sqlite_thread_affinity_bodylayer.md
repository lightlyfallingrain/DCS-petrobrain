---
name: sqlite-thread-affinity-bodylayer
description: sqlite3.Connection is thread-affine by default; body-layer's --console poll thread crashed until conn was opened on that thread
metadata:
  type: project
---

`perception/geometry.py`'s `open_world_model` opens with plain `sqlite3.connect(...)` — no
`check_same_thread=False`. Any code path that opens this connection (or builds a
`NakedEyePerceptionSource`/anything holding it) on one thread and then queries it from another
thread raises `sqlite3.ProgrammingError` on first use. `body-layer/src/logger.py`'s `--console`
poll thread (`_run_console_poll_loop`, formerly `_run_poll_loop`) hit exactly this in live
acceptance testing (Stage 6) because `main()` built the connection+sources on the main thread and
handed them to a spawned background thread.

**Why it wasn't caught by tests**: `test_naked_eye_source.py` / `test_emission_pipeline.py` /
`test_visibility.py` all monkeypatch `visibility.line_of_sight_clear` to a no-op, so
`store.reader.sample_grid` (the thing that actually queries the connection) is never exercised
against a real `sqlite3.Connection` in any pre-existing test, let alone across a thread boundary.

**Fix pattern**: open the connection and build anything holding it on the thread that will
actually use it, close it in that thread's own `finally`. Do not reach for
`check_same_thread=False` as a shortcut — it papers over the lifecycle mismatch.

**How to apply**: any future body-layer code that spawns a thread/process and touches the
world-model sqlite seam (`perception.geometry.open_world_model`, `store.reader.*`) must open its
own connection on that thread, never receive one built elsewhere. When testing such code, don't
monkeypatch past the sqlite layer — build a real (schema-only is enough) `.sqlite` via
world-model's `store.writer.open_for_build` and let the real query execute, or the test can't
catch this class of bug.
