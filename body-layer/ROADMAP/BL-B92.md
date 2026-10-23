# BL-B92 — Connection-reporter tests are order-dependent under pytest-randomly

- [ ] **BL-B92 — Isolate the `test_connection_reporter_*` tests so they pass in any order.**
  #status/open Filed 2026-10-23 at user direction (*"yes"*, to filing one item for the group).
  (`BL-B91` was already taken on `feature/effector-sequences` when this was minted on
  `fix/guidance-ready-edge`, hence the skip.)

  Two tests in the same group fail intermittently under `pytest-randomly`'s default random order,
  pass in isolation, and pass reliably with `-p no:randomly`:
  - `test_connection_reporter_announces_the_first_connection` — noted 2026-10-22 in
    `[[BL-B80]]`'s DoD pass, attributed to `a5def59e`.
  - `test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop` — noted 2026-10-23
    by `fix/guidance-ready-edge`'s implementer, reviewer and DoD (`plans/guidance-ready-edge/dod-check.md`).

  Suspected cause, not yet verified: logging-handler state leaking between tests, so a reporter's
  output is or is not captured depending on what ran before. Fix as one `caplog`/handler-isolation
  change for the whole group, not per test. Done when the full body-layer suite passes under
  several random seeds (`--randomly-seed=<n>`), not only with ordering disabled.
