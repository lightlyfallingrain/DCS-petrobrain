# X-B1 — Unhandled thread exception should fail the test suite

- [ ] **X-B1 — Make an unhandled thread exception fail the test suite, not just warn it.** #status/open
  `pyproject.toml` declares no `filterwarnings`, so `PytestUnhandledThreadExceptionWarning`
  warns and the run still reports "178 passed". Raised by the reviewer on
  `feature/aircraft-layer-hardening`, twice, and it is worth doing because **that warning is
  the mechanism that caught the original bug** on that branch: a background thread died with
  an `AttributeError`, every assertion in the test still passed, and only the warning said
  otherwise. A dead daemon thread that leaves a green suite is exactly the failure this
  project keeps meeting in the air. Affects every subproject's test config, not one file —
  which is why it is here rather than on a branch.
