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

---

### Follow-up review, 2026-10-23

Reviewing the follow-up commit on `fix/connection-reporter-flaky`, tip
`0a08a5ed7e687cac48fff76eea4ad2886132dbbb` (fast-forwarded cleanly from this worktree's prior
`f4e552c1`; HEAD was a strict ancestor, tree clean). Diff scope:
`body-layer/tests/test_brain_client.py` (the one test's socket→monkeypatch rewrite),
`body-layer/ROADMAP/BL-B92.md`'s follow-up note, `plans/connection-reporter-flaky/debug.md`'s new
"Follow-up" section, and two new agent-memory files. No production code touched.

**Correction to my earlier review, filed in this same document above:** that review's own
"host-specific" framing was wrong, not just the debugger's. I wrote *"confirms this is a
pre-existing, host-specific socket-timing issue … and not something this fix could have
addressed"* after reproducing the identical failure on pre-fix and post-fix code — which correctly
established *not caused by this diff* but does not establish *out of scope* or *unfixable*. The
test's premise (a bound-but-unlistened socket refuses `connect()` at once) was simply false on
this host, and the fix was to stop depending on that premise, which is exactly what this follow-up
does. Confirmed independently this pass: `/Users/sg/Code/DCS-petrobrain/.claude/worktrees/agent-aa0c930618469cbd6/body-layer/tests/test_brain_client.py::test_unreachable_brain_logs_one_line_without_traceback`
now passes 3/3 alone and the full suite passes 2445/2445 in one run (file order — see note on
`pytest-randomly` below), where it previously failed deterministically.

**Exception shape matches a real refused connection.** Read `src/belief/brain_client.py`:
`_poll_once` catches `(urllib.error.URLError, OSError)` around the one `urllib.request.urlopen`
call and re-raises `BrainLayerError(...) from exc`; `_poll_loop` then computes
`exc_info=not isinstance(exc.__cause__, (urllib.error.URLError, OSError))`. The injected
`urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))` is exactly the shape
`urlopen` raises on a real refused connection (`http.client`/`socket` raise the `OSError`, `urlopen`
wraps it as `URLError(err)` — this is a stdlib-documented wrapping, not an invented shape), so
`exc.__cause__` is that `URLError`, the `isinstance` check is `True`, and `exc_info` resolves to
`False` — the same branch a real refusal takes. The classification logic is exercised truthfully,
not just made to pass.

**The departure from "don't mock urllib" is justified and the documentation is accurate.**
`body-layer/CLAUDE.md`'s "Testing" section states the convention is about the aircraft-layer HTTP
client being tested against a real loopback server "mirroring `aircraft-layer/tests/test_api.py`'s
pattern … catches real wire-format mismatches" — i.e. it guards against a client that parses its
own mocked expectations instead of a real server's real bytes. This test asserts something
orthogonal: which branch of `_poll_loop`'s own `exc_info=` decision fires for a given *exception
shape* coming back from `_poll_once`. No bytes are parsed on this path (the failure happens before
any response body exists), so there is no wire format to fake past. debug.md's own framing of this
distinction is accurate and I'd reach the same conclusion independently reading the code — this
is a deliberate, narrow, documented departure, not a silent one.

**Monkeypatch cannot leak past teardown in a way that changes other tests.** `monkeypatch.setattr`
is function-scoped and pytest reverts it automatically at teardown, confirmed by reading
`pytest`'s own fixture semantics (no custom teardown code here to get wrong). The one real
question is the leaked `_poll_worker` daemon thread this test starts (same accepted leak every
other test in this file produces) retrying against the live patch *while it is still active*
within the 2.0s `with` block, or against the real `urlopen` afterward. Traced both: while the
patch is active, any other already-leaked thread from an earlier test that happens to fire during
that 2.0s window gets the same fake `URLError` a real refusal would produce — harmless, since this
test's own assertion filters `caplog.records` to `record.thread == worker.ident`, not to what any
other thread logs, and the fake exception shape is indistinguishable from what that thread would
have logged against its own real unreachable target anyway. After teardown, this test's own
worker's *next* retry (≥1.0s later) hits the real `urlopen` against `127.0.0.1:1`, the same
already-leaked-forever target every other test in this file already produces. No new leak
behaviour, confirmed by reading `debug.md`'s account and re-deriving it from the code rather than
accepting the account alone.

**Mutation check, independently re-run.** Changed `_poll_loop`'s
`exc_info=not isinstance(exc.__cause__, (urllib.error.URLError, OSError))` to `exc_info=True` and
reran the target test alone — failed, with the real traceback printed, exactly as the test's own
`assert not record.exc_info` predicts. Reverted; `git status --porcelain` on
`src/belief/brain_client.py` came back clean after. The test is not a pass-by-construction — it
fails when the classification logic it claims to pin is broken.

**debug.md's corrected framing is accurate.** Its "Follow-up" section states the earlier
conclusion "was wrong in its conclusion, not its measurements" — the ~5.0s block measurement was
real, the inference that this made the test untestable-here was not. That is the right diagnosis
of the earlier mistake (mine included, see correction above), stated without overclaiming or
re-litigating the original measurement.

**`test_mission_start_reset.py` flake — agree it is out of scope.** debug.md reports a single,
non-reproducing failure at `--randomly-seed=2` on pre-fix code in an unrelated file
(`test_check_for_new_mission_keeps_the_traceback_for_a_non_connection_failure`), sharing the same
general root-cause *family* (an exact-list/`records[0]` caplog assertion with no logger-name or
thread filter) but a different file, not reproduced on 3 more runs at the same seed, and passing
3/3 alone. Agreed this is correctly left unfixed here: it is a different test in a different file,
BL-B92's own scope is the three/four tests it already names, and "found once while sweeping seeds
for an unrelated fix, not reproducible" is exactly the bar this project uses elsewhere for
"flag, don't fix" (the `test_main_print_tuning_works_without_aircraft_layer_url` precedent in the
first review above). Worth a backlog note if it recurs, as debug.md already says.

**`pytest-randomly` note.** The coordinator advised mid-task that the user is uninstalling
`pytest-randomly` from the shared venv; at verification time here it was still present (`import
pytest_randomly` succeeded), so seed-targeted runs were skipped per that instruction and plain
`pytest -q`/`-k` runs were used instead (file order). Ran: `ruff format --check`/`ruff check`
(both PASS, 163 files), `cd body-layer && .venv/bin/mypy src` (strict, PASS, 71 files), the target
test alone ×3 (PASS each), and the full suite once in file order (2445 passed, 4 xfailed, 0
failed). No seed sweep performed this pass — the debugger's own 61-seed sweep and this follow-up's
5-seed sweep (seeds 11/22/33/44/55, reported in debug.md) stand as the random-order evidence, per
the coordinator's instruction.

### Required Fixes (follow-up)

None.

### Optional Refinements (follow-up)

- Same `close()`/`stop()`-on-teardown refinement noted in the original review above, now
  slightly more motivated: this is the second test in this file to need a filter worked around a
  permanently-leaked daemon thread rather than closing it. Still not required — still a broader
  change than this ticket's scope.

### Verdict (follow-up)
APPROVED

### Review Confidence (follow-up)
Full read. Mutation-tested independently (not reused from debug.md's own account), exception
shape verified against the actual `_poll_once`/`_poll_loop` source rather than taken on debug.md's
word, monkeypatch-teardown interaction traced by reading `pytest` fixture semantics rather than
assumed, and format/lint/type/test commands run directly in this worktree. Seed-sweep evidence for
this specific follow-up is not independently reproduced here (see `pytest-randomly` note above) —
that is a tooling-availability gap in this pass, not a diagnosis gap: the mechanism was confirmed
by mutation and by direct exception-shape inspection, and the debugger's own 5-seed sweep already
covers the random-order case.
