# BL-B93 — `test_tuning.py` leaves the tuning registry empty for later tests

- [ ] **BL-B93 — Stop `test_tuning.py`'s autouse fixture from wiping the tuning registry for the
  rest of the session.** #status/open Filed 2026-10-23 at user direction (*"yes"*). Found by the
  `[[BL-B92]]` debugger; diagnosis in `plans/connection-reporter-flaky/debug.md`.

  `test_logger.py::test_main_print_tuning_works_without_aircraft_layer_url` fails whenever it runs
  after `test_tuning.py`. That file's `autouse` fixture resets `tuning.py`'s module-level `_state`
  singleton to `None` before and after every test. Every tunable registers itself against that
  singleton once, at import time. Once it is cleared, it stays empty for the rest of the session,
  so a later `render_print_tuning` gets a fresh resolution with nothing in `.defaulted`. This is a
  global-registry leak across test files, unrelated to logging.

  Fix in the fixture (restore the prior `_state` rather than `None`), not in the failing test.
  Done when the test passes after `test_tuning.py` in file order and under random order.
  `pytest-randomly` is not installed (user decision 2026-10-23), so check by explicit ordering:
  `pytest tests/test_tuning.py tests/test_logger.py`.

  Related, seen once in the same sweep and not reproduced since:
  `test_mission_start_reset.py::test_check_for_new_mission_keeps_the_traceback_for_a_non_connection_failure`.
  It belongs to BL-B92's family (an unfiltered `caplog.records[0]`), so check it while here.
