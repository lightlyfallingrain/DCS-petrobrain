# BL-B46 — `logger`'s own logger propagates

- [ ] **BL-B46 — `logger`'s own logger propagates, so a host process would see every line twice.** #status/open
  Found and accepted during [[BL-11]] Stage 4 round 4, 2026-10-08. **Optional by Reviewer ruling, not
  a defect in current use.**

  `_configure_logger_for_main()` attaches a `StreamHandler(sys.stderr)` to this module's own named
  logger and leaves `propagate` at its default `True`. Standalone (`python -m logger ...`) root has
  no handlers, so nothing duplicates. But if the module were imported into a host process that calls
  `logging.basicConfig`, each record reaches both handlers:

  ```
  $ python -c "
  import logging, logger as m
  logging.basicConfig(level=logging.INFO, format='ROOT> %(message)s')
  m._configure_logger_for_main()
  m.logger.info('does this appear once or twice?')"
  does this appear once or twice?
  ROOT> does this appear once or twice?
  ```

  **Why it was not fixed on that branch**, recorded because the reasoning is the useful part: the
  Reviewer ruled it optional on the grounds that nothing in the current call graph reaches the
  host-import case, and that the failure mode is **noisy** (a doubled line) rather than **silent** (a
  dropped line) — the opposite risk profile from the required fixes in that milestone, which existed
  precisely because a line was silently lost. That distinction is worth keeping: this project's
  expensive failures have all been silent ones.

  The orchestrator initially framed this as the code-disagrees-with-its-own-comment pattern that had
  already bitten the branch twice, and that framing was an overstatement — the docstring cites the
  host-process case as a *reason for scoping to the module's own logger*, which is true, and never
  claims host integration is clean.

  Fix when convenient: either `logger.propagate = False` (one line) or narrow the docstring to say
  the host case is out of scope. Whoever next touches that function should take one of the two.
