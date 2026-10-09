# X-B3 — A shutdown test that never calls `close()`

- [ ] **X-B3 — `test_unexpected_accept_error_is_logged_loudly_and_the_loop_recovers` simulates
  shutdown by poking `server._socket = None` rather than calling `close()`** #status/open, so it never
  sets `_shutting_down` and its simulated-shutdown branch now exercises a dead code path.
  Harmless today (the assertion is `any(...)`, not an exact count) and purely cosmetic drift —
  worth fixing only if that test is edited for another reason.
