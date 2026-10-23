# Definition of Done Check: fix/connection-reporter-flaky (BL-B92)

**Scope note on tip.** Run at tip `10d56d063b065c1f134cb0497c551309c913fd76`, reached by
fast-forwarding this worktree from `f4e552c1` (HEAD was a strict ancestor, tree clean). This
verdict is scoped to that exact commit; if the branch moves, re-verify.

Merge target: `main` (currently at `f4e552c1`). **Merge needs the user's approval — not performed
by this check.**

## Diff scope

`git diff --name-only f4e552c1 10d56d06`:

```
.claude/agent-memory/debugger/project_caplog_cross_logger_pollution.md
.claude/agent-memory/implementer/feedback_host_specific_always_failing_is_a_real_defect.md
.claude/agent-memory/reviewer/feedback_caplog_leaked_thread_fix_verify_by_independent_injection.md
.claude/agent-memory/reviewer/feedback_host_specific_measurement_is_not_a_scope_verdict.md
body-layer/ROADMAP/BL-B92.md
body-layer/ROADMAP/BL-B93.md
body-layer/ROADMAP/body-layer-backlog.md
body-layer/tests/test_brain_client.py
body-layer/tests/test_logger.py
plans/connection-reporter-flaky/debug.md
plans/connection-reporter-flaky/performance.md
plans/connection-reporter-flaky/review.md
plans/connection-reporter-flaky/security.md
```

Only `body-layer/` carries code changes, and only in `tests/` — no `src/` file touched (confirmed
by diff scope; also independently confirmed by the debugger, reviewer, and security reports). Per
the enumeration rule, only body-layer's own commands apply here.

## Code Quality

- [x] **body-layer format** — `ruff format --check src tests`: 163 files already formatted. PASS.
- [x] **body-layer lint** — `ruff check src tests`: all checks passed. PASS.
- [x] **body-layer type check** — `cd body-layer && .venv/bin/mypy src` (strict): no issues found
      in 71 source files. PASS. (`mypy src` does not type-check `tests/`; the two changed files
      are test files — this matches the subproject's own documented command and the four
      pre-existing, unrelated `attr-defined` errors in `test_brain_client.py` noted by the
      reviewer and debugger are unchanged by this diff.)
- [x] **body-layer tests, file order** (no `pytest-randomly` reinstalled, per user direction):
      `pytest body-layer/tests -q` → **2445 passed, 4 xfailed**, zero failures. Matches the
      baseline both the debugger's and reviewer's reports report post-fix.
- [x] **Brain-client target test alone, 3×**:
      `pytest tests/test_brain_client.py::test_unreachable_brain_logs_one_line_without_traceback -q`
      → PASS, PASS, PASS (0.14s/0.13s/0.13s). This is the test the follow-up fixed by
      monkeypatching `urllib.request.urlopen`; confirmed independently green on this host, not
      taken on the debug/review reports' word.
- [x] **No unhandled errors/panics in data paths** — no production code touched at all.
- [x] **No debug output / leftover TODOs** — `git diff f4e552c1 10d56d06 -- body-layer/tests/*.py`
      grepped for `TODO|FIXME|print(|pdb|XXX`: no hits.

**`pytest-randomly` uninstall, independently verified** (the task asked this be checked, not
taken on account): `python -m pip show pytest-randomly` → "Package(s) not found"; no
`*-dist-info` directory anywhere under `body-layer/.venv`; the plugin's own package directory
(`body-layer/.venv/lib/python3.14/site-packages/pytest_randomly/`) is an empty leftover holding
only a stale `__pycache__`, no entry points, and pytest does not register it as a plugin (no
`--randomly-seed` test-collection error, confirmed below). Also confirmed `--randomly-seed=` now
**fails loudly** (`error: unrecognized arguments: --randomly-seed=42`) rather than silently doing
nothing — recorded in `BL-B92.md` so a future reader checking this fix after a regression does not
reach for a seed sweep that can no longer run.

## Scope & Correctness

- [x] Implementation matches `plans/connection-reporter-flaky/debug.md` — this feature went
      straight through Debugger → Reviewer → Performance Reviewer → Security (bug-fix sequence per
      `AGENTS.md`'s role sequences; no separate `plan.md`, which is correct for a bug fix — there is
      no Architect plan to check against).
- [x] No unplanned scope added silently. Two genuinely separate-root-cause flakes
      (`test_main_print_tuning_works_without_aircraft_layer_url`,
      `test_mission_start_reset.py::test_check_for_new_mission_keeps_the_traceback_for_a_non_
      connection_failure`) were found mid-investigation and correctly **not** fixed on this branch
      — flagged, with the first minted as `BL-B93` and the second left as a note inside `BL-B93`'s
      entry (both checked below). The one scope question worth stating plainly: the follow-up fix
      (socket → monkeypatch) is a second commit beyond the original diagnosis's stated fix, but it
      corrects the original diagnosis's own mistake (see "Recurring-fix pattern" below) rather than
      adding new scope — the ticket's own title ("connection-reporter tests order-dependent") still
      covers it, since `test_unreachable_brain_logs_one_line_without_traceback` was one of the two
      "two more flaky tests reported mid-fix" this ticket explicitly took on.
- [x] No invariants from `CLAUDE.md`/`body-layer/CLAUDE.md` violated. Security's report confirms no
      dependency change, no new network listener, nothing reachable outside the test suite.
      Reviewer confirms the `client._poll_worker` private-attribute access and the `urlopen`
      monkeypatch are both consistent with existing practice in this test file, and the departure
      from `body-layer/CLAUDE.md`'s "don't mock urllib" convention is scoped correctly (that
      convention guards wire-format tests; this test asserts exception-shape classification, which
      an injected exception tests more precisely, not less — reviewer's follow-up review traces
      this independently from source, not from the debugger's account).
- [x] All new files staged — `git status --porcelain` showed only `BL-B92.md` modified by this DoD
      pass (see below); everything from the fix itself was already committed on the branch.

## Testing

- [x] Core logic covered: the fix is entirely test-code, and its own correctness is verified by
      the reviewer's independent mutation tests (removing `_ConnectionReporter`'s early-return,
      flipping `_poll_loop`'s `exc_info=` branch) on **both** the original fix and the follow-up —
      each caught by the test the mutation should break, confirming the assertions are not
      decorative.
- [x] Tests are meaningful — see above; also the debugger's own adversarial stress test (a thread
      hammering the unrelated logger at ~1000x the real leak's rate) and the reviewer's two
      independent injection harnesses (100/100 and 50/50 runs) both demonstrate the pre-fix form
      fails under the exact mechanism and the post-fix form does not.
- [x] No existing tests broken — full suite 2445/2445 passed, 4 xfailed unchanged, matching the
      pre-fix baseline's non-flaky count.

## Documentation

- [x] Reviewer findings addressed — **Required Fixes: None** on both the original and follow-up
      review. Both Optional Refinements (a `close()`/`stop()` teardown mechanism on
      `BrainLayerClient`) are explicitly deferred as broader-than-scope, not silently dropped.
- [x] Non-obvious behavior explained — `debug.md` carries the full mechanism (cross-logger
      pollution via root-logger capture, thread-identity disambiguation, the host-specific socket
      premise and its correction), and the fixed tests themselves now carry docstring notes per
      the debugger's report so a future reader does not reintroduce the unfiltered form.

**`BL-B92.md` entry accuracy — checked against the actual diff and history, not taken on the
entry's own word:**

- The entry correctly separates the three things this ticket touched: the two original
  `test_connection_reporter_*` flakes (fixed), `test_main_print_tuning_...` (correctly flagged,
  not fixed, filed as `BL-B93`), and `test_unreachable_brain_logs_one_line_without_traceback`
  (fixed, in a follow-up commit, after an initial mistaken "host-specific, out of scope" framing
  that the entry itself documents being corrected).
- **Added this pass**: a paragraph stating precisely that, on `main`, this test's pre-fix
  `caplog.records[0]` (no thread filter) meant it was **passing by accident** whenever it did
  pass — correctness depended on no other leaked thread's record landing in the same 2.0 s
  capture window, not on the code actually distinguishing instances — and that this is
  independent of the separate, host-specific socket-timing defect that made it fail
  deterministically on *this* host specifically. Verified against `git show f4e552c1:body-layer/
  tests/test_brain_client.py`: pre-fix, the test did take `caplog.records[0]` unconditionally with
  no thread filter, confirming the "passing by accident" characterization is accurate and not
  just restated from the task prompt.
- **`BL-B92`'s original "done when" wording** (`git show a3d6d352:body-layer/ROADMAP/BL-B92.md`):
  *"the full body-layer suite passes under several random seeds (`--randomly-seed=<n>`), not only
  with ordering disabled."* That bar was met — the debugger's 61-seed sweep and the follow-up's
  5-seed sweep both ran against the real, then-still-installed plugin, not a simulation — but
  `pytest-randomly` has since been uninstalled, so the entry's own evidence is historical and
  cannot be re-run as stated. Added a clarifying paragraph to the entry recording this and the
  loud-failure behavior of `--randomly-seed=` now, verified directly (see Code Quality above)
  rather than asserted.

**`BL-B93.md` entry checked:**

- The `--print-tuning` root cause is stated correctly and specifically: `test_tuning.py`'s
  `autouse` fixture resets `tuning.py`'s module-level `_state` singleton to `None` both before and
  after every test in that file, which leaves it `None` for the rest of the pytest session once
  that file's tests finish (not reset back to its pre-test value) — matching
  `tests/test_tuning.py`'s own module docstring and `tuning.py`'s `_get_state()` lazy-rebuild
  behavior, confirmed by reading both files directly, not taken on the entry's word. The proposed
  fix direction (restore the prior `_state` in the fixture's teardown rather than leaving it
  `None`) is sound and correctly scoped as "fix in the fixture, not the failing test."
  "Done when" is stated as a concrete, re-runnable check
  (`pytest tests/test_tuning.py tests/test_logger.py`) rather than a random-seed claim, correctly
  anticipating the plugin's absence.
- The `test_mission_start_reset.py` flake note is present, accurately scoped ("seen once... not
  reproduced since... belongs to BL-B92's family... check it while here" — not a demand to fix it
  immediately, matching debug.md's own account of a single non-reproducing occurrence).

**Backlog index (`body-layer-backlog.md`) checked:** both `[[BL-B92]]` and `[[BL-B93]]` lines are
present (lines 132-133), titles match each entry file's own `#` heading, and the numbering follows
the next-unused-ID rule (`BL-B91` was already taken on a different branch, correctly skipped per
the entry's own note).

## Security

- [x] `plans/connection-reporter-flaky/security.md` exists, verdict **APPROVED**, no required
      fixes.
- [x] No separate `security-plan-review.md` — correct for a bug fix (Security's plan-review step
      runs after Architect, which this ticket has none of; the bug-fix role sequence is
      Debugger → Reviewer → Security (deep analysis) → DoD, per `AGENTS.md`).

## Performance

- [x] `plans/connection-reporter-flaky/performance.md` exists, verdict **APPROVED** — test-only
      diff, net effect faster (a real multi-second socket timeout replaced by a synchronous
      monkeypatched raise), no runtime-path cost since no `src/` file changed.

## Recurring-fix pattern (process signal for the user)

Checked `plans/connection-reporter-flaky/review.md`'s required fixes against
`.claude/agent-memory/dod/MEMORY.md` for a prior "recurring fix" entry — none exists yet in this
role's own memory on this category, but the material here is itself exactly that category,
appearing **twice within this one ticket**:

1. The debugger's first pass on `test_unreachable_brain_logs_one_line_without_traceback`
   concluded "pre-existing, host-specific, out of scope" after measuring the real cause
   correctly (a ~5.0 s block, not an instant refusal) but drawing the wrong inference from the
   measurement (that this made the test *untestable here*, rather than *testing the wrong thing*).
2. The reviewer's first-pass review repeated the identical inference independently — "confirms
   this is a pre-existing, host-specific socket-timing issue... and not something this fix could
   have addressed" — then caught and corrected itself in the follow-up review, in its own words:
   *"that review's own 'host-specific' framing was wrong, not just the debugger's."*

Both agent-memory files already capture this
(`feedback_host_specific_always_failing_is_a_real_defect.md`,
`feedback_host_specific_measurement_is_not_a_scope_verdict.md`) — two roles, same ticket, same
exact mistake, independently. This is now a 2-occurrence pattern (debugger, then reviewer,
same session) worth a standing check earlier in the chain: **"a measurement that a premise is
false on this host is not, by itself, evidence the behavior under test is untestable or out of
scope here" — that inference needs an explicit second step (does the test's premise, not just its
environment, need to change) before being accepted.** Flagging as process debt per this role's own
instructions; not blocking this merge, since both instances were caught and corrected within the
same ticket before reaching DoD.

## Knowledge harvest

Ran `/notes-harvest connection-reporter-flaky` — its shallow awk-based extraction only pulled the
first line of each `debug.md` section (not meaningful standalone), so the real candidates were
picked by reading `debug.md`/`review.md` in full rather than from the script's table. Checked
each against `notes/*.md` for duplicates before writing (not assumed non-duplicate):

- Added to `notes/fixture-management-and-test-infrastructure.md`: the `caplog.at_level(logger=)`
  level-vs-capture-scope distinction (root-logger capture regardless of the `logger=` argument,
  plus the practical filter-by-name/thread-id fix), and "a test passing alone is not proof its
  assertion discriminates — it may be passing on absence of collision, not presence of correct
  logic." Checked `notes/model-selection-and-local-llm-serving-brain-layer-br-1.md`'s existing
  `caplog.at_level(...)` entry first — that one is about `caplog` vs. the real log stream
  (`capsys`/subprocess), a different point; not a duplicate.
- Added to `notes/debugging-and-root-cause-diagnosis.md`: "a correct measurement that a test's
  premise is false on this host is not, by itself, evidence the test is out of scope or
  untestable — it may mean the premise itself needs to change," naming that both the debugger and
  the reviewer independently made this exact inferential error on this ticket before either
  self-corrected.
- Skipped as obvious-from-code or already covered: the specific `record.thread == worker.ident`
  mechanics (code-derivable), the `urllib.request.urlopen` monkeypatch technique (code-derivable),
  and the `tuning.py` `_state` singleton leak (fully captured in `BL-B93.md` itself, not a general
  lesson beyond this one fixture's design).

## Verdict: DoD PASSED

All mechanical checks pass, fresh, on the tip named above. Reviewer, Security, and Performance
Reviewer have all signed off with no required fixes outstanding.

---

## Acceptance boundary — what this feature's fixtures structurally cannot reach

This is a test-infrastructure-only fix with **no runtime behavior change, no cockpit-facing
change, and no DCS interaction of any kind.** There is nothing for a live sortie to accept or
reject here — the entire "feature" is "the test suite's own correctness when verifying itself."
**No acceptance testing plan is meaningful for this change**, and no test card is warranted: there
is no Windows-side, DCS-side, or pilot-perceptible behavior this touches. The honest line is: this
change could be wrong in a way DoD's own commands would also miss — if the real leaked-daemon-
thread mechanism recurs in a *different* test file this ticket didn't touch (the
`test_mission_start_reset.py` single-occurrence flake is exactly that risk, named and left alone
on purpose) — but that is a test-suite reliability risk, not a flight-behavior risk, and no fixture
or sortie can distinguish "fixed" from "not yet observed to flake again" for a wall-clock-
coincidental race. The only thing that would ever surface a recurrence is seeing the suite flake
again.

**Execute the unblock condition of accepted debt, per this role's own standing instruction:**
`BL-B93` (open, not deferred) names its own clearing condition —
`pytest tests/test_tuning.py tests/test_logger.py` should currently still fail (that is *why*
it is filed as `#status/open`, not evidence this ticket should fix it). Ran it:

```
$ cd body-layer && python -m pytest tests/test_tuning.py tests/test_logger.py -q
...
AssertionError: assert 'at default' in 'tuning: no override file (PETROBRAIN_TUNING unset)\n'
FAILED tests/test_logger.py::test_main_print_tuning_works_without_aircraft_layer_url
1 failed, 200 passed in 4.81s
```

Confirms `BL-B93` is accurately filed as still-open (the clearing condition it names does
currently fail, as the entry says it should) — not a stale backlog item masquerading as closed.
Out of this ticket's scope to fix (that is precisely `BL-B93`'s own job); recorded here per the
"execute the unblock condition" instruction rather than left unexecuted.

No `#needs-flight` tag applies to anything in this diff — there is no flight-dependent behavior
here to tag.

Given there is nothing to acceptance-test, proceeding directly to the user decision: **merge
approval.**
