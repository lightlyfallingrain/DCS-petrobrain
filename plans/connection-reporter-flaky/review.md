### Review Summary

Reviewed `fix/connection-reporter-flaky` at `bc3d9920ee43b4831ed4671c18e529245705c5c2`
(fast-forwarded cleanly from `f4e552c1`, HEAD was a strict ancestor, tree clean).

Scope: `body-layer/tests/test_brain_client.py`, `body-layer/tests/test_logger.py`,
`body-layer/ROADMAP/BL-B92.md`, `plans/connection-reporter-flaky/debug.md`, and a debugger
agent-memory file. No production code touched — the whole fix is test-side, matching the
diagnosis (`caplog.records` picking up a leaked daemon thread's log records, not a defect in
`_ConnectionReporter` or `BrainLayerClient`).

**Diagnosis verified independently, not just read.** `caplog.at_level(level, logger=name)`
scoping only the *level*, not which records land in `caplog.records`, was confirmed by writing a
standalone harness (not reusing the debugger's own repro) that calls the real
`logger._ConnectionReporter` against a concurrent thread hammering `belief.brain_client` at a
different logger name: the unfiltered form failed 100/100 runs, the filtered (shipped) form 0/100.
A second independent harness modeled two live `belief.brain_client`-named threads (one carrying
`exc_info`, one not) to check the `test_unreachable_brain_logs_one_line_without_traceback` fix:
unfiltered `caplog.records[0]` picked the wrong (traceback-bearing) instance 50/50 times; the
shipped `record.thread == worker.ident` filter never did. Both confirm the mechanism and the fix
independently of the debugger's own stress-test account.

**Mutation check on the connection-reporter fix.** Removed the `if self._connected is False:
return` early-return in `_ConnectionReporter.report_failure` (a real regression: duplicate
"disconnected" lines) and reran — `test_connection_reporter_says_disconnected_once_then_connected_
once` and `..._reannounces_after_a_recovery_and_a_second_drop` both failed as expected. The
filtered assertion still catches the behaviour it claims to pin; the fix did not weaken it.
Reverted the mutation before continuing.

**Live-seed reproduction attempt.** Reproducing the real failure via `--randomly-seed` on this
host did not land on the connection-reporter flake itself across ~20 seeds tried (1-5, 36, 56,
100-105) — consistent with debug.md's own account that the pollution is wall-clock-coincidental,
not seed-deterministic, and that repeated runs of the same seed did not reproduce it reliably
during the debugger's own investigation either. The sweep did reproduce the *other*, explicitly
out-of-scope `test_main_print_tuning_works_without_aircraft_layer_url` flake at seeds 2, 3, and 36
on pre-fix code, matching debug.md's account of that separate bug class. Given the mechanism was
confirmed deterministically by injection (above) and the mutation check holds, the absence of a
live seed-reproduction on this run is not treated as a gap in the diagnosis.

**`test_unreachable_brain_logs_one_line_without_traceback` host issue — confirmed, not refuted.**
Reproduced directly: reverted both test files to their pre-fix (`f4e552c1`) content and ran just
this test — fails with `assert []` (zero `caplog.records` after the 2.0s wait). Restored the
shipped (post-fix) files and reran — fails identically, same `assert []`, now at the `own_records`
line. Same failure, same shape, on both pre-fix and post-fix code on this host — confirms this is
a pre-existing, host-specific socket-timing issue (a bound-but-unlistened socket not refusing
`connect()` instantly here), not a regression introduced by this fix, and not something this fix
could have addressed. Tree was restored clean (`git status --porcelain` empty) after each
diversion.

**Private-attribute access (`client._poll_worker`) is consistent with existing practice.** Grepped
`tests/*.py` for `._<name>` access patterns: widespread (67 hits in `test_crew_console.py` alone,
34 already in `test_brain_client.py` before this diff). Not a new pattern this fix introduces.

**Thread-leak-vs-filter tradeoff: filtering is the right call here, not a required fix to add
`close()`/`stop()`.** `BrainLayerClient` has no `close()`/`stop()` anywhere in the class (confirmed
by reading the source — only `daemon=True` threads, never joined), and the leak is already a
documented, accepted tradeoff elsewhere in this suite (`_run_plain_logger_main_for_n_polls`'s own
docstring in `test_logger.py`, and the debugger's own agent-memory file). Adding a stop mechanism
would be a broader design change touching every test in `test_brain_client.py`/
`test_crew_console.py` that constructs a `BrainLayerClient` against an unreachable URL — not a
narrow, cheap fix to these three/four tests. Noted below as an optional refinement, not required.

**`test_main_print_tuning_works_without_aircraft_layer_url` correctly identified as a different
bug class and correctly left unfixed** — it asserts over `capsys`, not `caplog`; the real cause
(`tuning.py`'s module-level `_state` singleton left `None` by `test_tuning.py`'s autouse teardown
for the rest of the session) is unrelated to this ticket's root cause. Flagging rather than fixing
is the right scope boundary for a bug-fix branch named after a different symptom.

### Verification run (independently, this review)

- `ruff format --check src tests` — PASS (163 files already formatted)
- `ruff check src tests` — PASS (all checks passed)
- `cd body-layer && .venv/bin/mypy src` (strict) — PASS (71 source files, no issues)
- `pytest body-layer/tests -q -p no:randomly` — 2444 passed, 4 xfailed, 1 failed
  (`test_unreachable_brain_logs_one_line_without_traceback`, the pre-existing host issue above,
  confirmed identical pre-fix and post-fix)
- `pytest body-layer/tests -q --randomly-seed=<n>` for n in {1,2,3,4,5,36,56,100-105} — connection-
  reporter group green throughout; `test_unreachable_brain_logs_one_line_without_traceback` fails
  consistently (same host issue); unrelated tuning flake observed at seeds 2, 3, 36 as predicted
- `pytest-randomly` was already installed in the shared `body-layer/.venv` as reported — not
  touched, used via `--randomly-seed=` as instructed
- Spot-checked `mypy` on the two changed test files directly (not part of this subproject's own
  `mypy src` command, done as an extra check): 28 pre-existing errors, identical in count and
  content against pre-fix (`f4e552c1`) versions of the same files — unrelated to this diff, not
  flagged further

### Required Fixes

None.

### Optional Refinements

- Consider a `close()`/`stop()` method on `BrainLayerClient` (and the equivalent for `_worker`'s
  escalation-POST thread) at some point, used by a test fixture teardown, so future tests against
  unreachable URLs don't leak daemon threads for the rest of the session at all — this would
  close the root cause rather than filtering around its symptom on a per-test basis. Not required
  here: it's a broader change than this ticket's scope, the leak is an already-accepted tradeoff
  documented elsewhere, and filtering is the narrowest correct fix for the three/four tests
  actually affected today. Worth it only once enough *other* tests are found to need the same
  filter-around-a-leak treatment that these did.
- `test_main_print_tuning_works_without_aircraft_layer_url`'s real cause (the `tuning.py`
  module-level `_state` singleton left permanently `None` after `test_tuning.py`'s autouse
  teardown) is correctly flagged as out of scope and not fixed here. Worth minting its own backlog
  ID so it isn't lost — not a required fix on this branch, since fixing it would broaden the
  diff beyond BL-B92's stated scope.

### Verdict
APPROVED

### Review Confidence
Full read. Diagnosis re-derived independently (two standalone injection harnesses, not reuse of
the debugger's own repro scripts), the connection-reporter fix mutation-tested, the host-specific
test-brain-client failure reproduced and confirmed identical pre-fix/post-fix, and the full
format/lint/type/test suite run directly rather than trusted from the debug report.
