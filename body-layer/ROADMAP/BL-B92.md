# BL-B92 — Connection-reporter tests are order-dependent under pytest-randomly

- [x] **BL-B92 — Isolate the `test_connection_reporter_*` tests so they pass in any order.**
  #status/done **Merged to `main` 2026-10-23 (`27f9821f`, `fix/connection-reporter-flaky`).**
  Filed 2026-10-23 at user direction (*"yes"*, to filing one item for the group).
  (`BL-B91` was already taken on `feature/effector-sequences` when this was minted on
  `fix/guidance-ready-edge`, hence the skip.)

  Two tests in the same group fail intermittently under `pytest-randomly`'s default random order,
  pass in isolation, and pass reliably with `-p no:randomly`:
  - `test_connection_reporter_announces_the_first_connection` — noted 2026-10-22 in
    `[[BL-B80]]`'s DoD pass, attributed to `a5def59e`.
  - `test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop` — noted 2026-10-23
    by `fix/guidance-ready-edge`'s implementer, reviewer and DoD (`plans/guidance-ready-edge/dod-check.md`).

  **Resolved 2026-10-23 on `fix/connection-reporter-flaky`** (`plans/connection-reporter-flaky/debug.md`).
  Root cause was **not** logging-handler state on `logger.py`'s own module logger — it was
  cross-logger pollution of `caplog.records` from a leaked, never-stopped
  `belief.brain_client.BrainLayerClient` daemon `_poll_loop` thread (started by unrelated tests in
  `test_brain_client.py`/`test_crew_console.py` against an unreachable URL), which retries forever
  and logs via its own `belief.brain_client` logger every ~1.0 s. `caplog.at_level(level,
  logger=name)` only scopes the *level* of the named logger, not which records land in
  `caplog.records` — pytest's capture handler is attached to the root logger for every test
  regardless, so any propagating logger's output can land in an unrelated test's capture window.
  Reproduced directly against the real (seed 56) failure's captured log output, confirmed the
  mechanism with a deterministic injection repro, and fixed by filtering `caplog.records` to
  `record.name == logger_module.__name__` in all three `test_connection_reporter_*` tests. Full
  suite green under `-p no:randomly` and under the seed that reproduced the real failure (56) plus
  ten other seeds.

  **Two more flaky tests reported mid-fix, checked against this root cause (`debug.md`'s own
  section on this)**:
  - `test_main_print_tuning_works_without_aircraft_layer_url` — **does not share this root
    cause, not fixed here.** No logger involved at all (`capsys`, not `caplog`); the real cause
    is `tests/test_tuning.py`'s `autouse` fixture resetting `tuning.py`'s module-level `_state`
    singleton to `None` after its own tests, which leaves every *other* test's later
    `render_print_tuning` call building a fresh, permanently-empty `Resolution` (every tunable's
    own accessor call that would populate it already ran once, at import time, and never runs
    again). A global-registry-reset leak across test files, not a logging issue. Worth its own
    backlog item — not minted here (ID minting is the main loop's call).
  - `test_unreachable_brain_logs_one_line_without_traceback` — **shares the root-cause family one
    layer deeper (same leaked-daemon-thread mechanism, same `belief.brain_client` logger name
    this time, from a *different* leaked `BrainLayerClient` instance) and is fixed here**: filters
    `caplog.records` by `record.thread == client._poll_worker.ident` instead of blindly taking
    `caplog.records[0]`, since logger-name filtering alone can't distinguish two different client
    instances sharing one logger name. **Follow-up, 2026-10-23 (`debug.md`'s own "Follow-up"
    section):** the real-socket half of the test (a `bind()`-but-never-`listen()`-ed socket,
    meant to stand in for an instantly-refused connection) was a genuine, always-failing defect on
    this host, not a verification gap — the first pass mistook "cannot be driven to a pass here"
    for "pre-existing and out of scope." Fixed by monkeypatching
    `urllib.request.urlopen` to raise the same `URLError`-wrapping-`OSError` shape a real refusal
    produces, removing the test's dependence on this (or any) host's socket timing entirely. Green
    5/5 alone, in the full suite under `-p no:randomly`, and across 5 random seeds.

    **Stated precisely, since "fixed" covers two independent defects, not one:** on `main`, this
    test's pre-fix `caplog.records[0]` (no thread filter) meant that whenever it *did* pass, it was
    passing by accident — correctness depended on no other leaked `BrainLayerClient` thread firing
    into the same capture window during this test's 2.0 s wait, not on the code actually
    distinguishing its own record from a different leaked instance's. That is the general
    `BL-B92` root cause, one layer deeper. Separately and additionally, on *this* host specifically,
    the test's second premise — a `bind()`-but-never-`listen()`-ed socket refuses `connect()` at
    once — was simply false (measured ~5.0 s block, confirmed on a bare `socket.create_connection`
    with no test framework involved), so here it did not even get the chance to pass by accident:
    it failed deterministically, pre-fix and post-fix of the first (thread-identity) fix, 3/3,
    before the follow-up replaced the real socket with a monkeypatched `urlopen`.

  **On this entry's original "done when" wording** (quoted verbatim in this file's own history):
  *"the full body-layer suite passes under several random seeds (`--randomly-seed=<n>`), not only
  with ordering disabled."* That bar was met before `pytest-randomly` was uninstalled from the
  shared venv (user decision, 2026-10-23): the debugger's 61-seed sweep (1-10, 36, 56, 100-150) and
  the follow-up's 5-seed sweep (11/22/33/44/55) both exercised the real plugin, not a simulation of
  it, and both are reported above. The plugin's own package directory under `body-layer/.venv` is
  now an empty, entry-point-less leftover (DoD check, 2026-10-23: `pip show pytest-randomly` finds
  nothing, no `dist-info`, pytest does not register it as a plugin) — the uninstall is real, not
  partial. **This entry's own random-seed evidence is historical and cannot be re-run as stated**:
  a future reader checking this fix after a regression should use `pytest tests -q` in file order
  (BL-B93's method) rather than attempting `--randomly-seed=`, which now fails loudly
  (`error: unrecognized arguments: --randomly-seed=<n>`, confirmed by this DoD check) rather than
  silently running unordered.
