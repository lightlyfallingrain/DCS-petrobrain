### Review Summary

Reviewed BL-B106 (async speech) on `feature/async-speech-impl`, tip `868b5418` (fast-forwarded
into this worktree from `f480cf71`, which was a strict ancestor; tree was clean). Diff reviewed:
`72fd46e7..868b5418` (`4387203a` implementation, `868b5418` implementer agent-memory).

The implementation matches the plan and its "Refresh against the code of 2026-11-12" section
closely, including the one decision that section bound over the older text (`body.py` naming,
`--speech-audio` no longer existing, `ConnectionReporter` lock, `audio_adapter_reporter`
pass-through). Each specifically-flagged risk was checked against the actual code, not just the
plan's description of it:

- **`body.py`'s `main()`'s single `CrewConsole(...)` call** does construct `SpeechWorker(
  audio_adapter_client, reporter=audio_adapter_reporter)`, `.open()`s it before the poll thread
  starts, and passes `speech_worker=speech_worker` into `CrewConsole(...)` alongside
  `speech_client=`. Decision 1's named risk (silent revert to blocking if this is omitted) does
  not apply here — confirmed by reading the actual call site, not inferring from the file list.
- **`speech_log_sink` is called only from `drain_speech_results`, on the poll thread** —
  `SpeechWorker._process` (speech_worker.py) never imports or calls it; it only calls
  `self._reporter.report_failure`/`report_success` and appends a `_SpeechResult`. The cross-thread
  data race Decision 2 flags is closed as designed.
- **`interrupt()`** clears the queue then calls `client.stop()` synchronously on the calling
  thread, swallowing and logging any exception. `_handle_stop_talking` and `reset_for_new_mission`
  both route through `speech_worker.interrupt()` when a worker is configured, with the
  pre-existing direct `speech_client.stop()` call kept as the fallback when it is not. Matches
  Decisions 3/4.
- **The pre-existing synchronous fallback branch in `_print`** is unchanged in content (now an
  `elif` instead of the original `if`, since the worker branch is checked first, but every line of
  the fallback body — the `push_speech` try/except, the reporter calls, the duration bracket — is
  identical to what was there before). The "third branch" for `silenced` + worker exists exactly as
  implementation.md describes: `deferred_to_worker` stays `False` when silenced, so the line falls
  through to the synchronous `speech_log_sink` call with all three timing fields `None` — matching
  the pre-existing silenced-line row shape and confirming `speech_log_sink`'s own "not gated by
  `silenced`" invariant holds for both the worker and fallback paths. Verified by reading the code,
  and by `test_print_silenced_with_worker_configured_enqueues_nothing_but_still_logs`.
- **`reset_for_new_mission`** now passes `speech_worker=self.speech_worker` (closing BL-B106's own
  Decision 4) and `audio_adapter_reporter=self.audio_adapter_reporter` (closing the pre-existing
  BL-B96 omission the refresh section named) — both added to `test_mission_start_reset.py`'s
  `_CREW_CONSOLE_PRESERVE` set, and both have dedicated identity-preservation tests.
- **`ConnectionReporter`** gained a `threading.Lock` around the read-modify-write in
  `report_failure`/`report_success`, matching the refresh section's instruction exactly.
- **Checks**: `ruff format --check`, `ruff check`, `mypy --strict` (`cd body-layer &&
  .venv/bin/mypy src`), and `pytest -q` (full `body-layer/tests` suite) were run by the Reviewer
  directly (fresh `.venv` built in this worktree, since none existed) rather than taken on the
  implementer's word: `ruff format` 200 files already formatted, `ruff check` all passed, `mypy`
  success on 82 source files, `pytest` **3192 passed, 4 xfailed** — matching
  `implementation.md`'s own reported numbers exactly.
- **Tunable rule**: the `_MAX_QUEUE_LEN = 64` bound is reused verbatim from
  `AudioPlaybackSender`/`F10CommandQueue`/`_pending_positional_replies`'s identical cap, carries a
  `#:` comment explaining why it is not a behaviour-affecting tunable (a defensive insurance bound,
  not something that changes what Petrovich does), and is not in `config/defaults.toml`. Correct
  side of the line — it does not change what he says, sees, or how long he waits; it is a ceiling
  that is never expected to bind.
- **Comment pruning**: nothing was pruned from a changed block that lost a durable line, a `#:`
  tunable comment, or an untested edge case — the changes are additive (new fields/methods/
  branches with new docstrings), not edits to an existing comment that removed something. No
  finding here.

### Test count note (not a defect)

The dispatch prompt's expectation of "`test_speech_worker.py` (15)" and "9 new in
`test_crew_console.py`" does not match the actual file contents: `test_speech_worker.py` has
**11** test functions, and `test_crew_console.py` gained **8** new test functions (one of them,
`test_drain_speech_results_calls_speech_log_sink_with_result_timings`, covers two of
`implementation.md`'s nine listed behaviours — "real timings" and "no-op on a second drain" — in
one function, which is where the "9" in that file's own prose comes from). Every behaviour listed
in the plan's Stage 4 and in `implementation.md`'s own "Tests Added" section is covered; the
mismatch is in the expected head-count carried in the dispatch prompt, not a gap in the
implementation. Flagging for the record rather than treating as a finding.

### Required Fixes

None.

### Optional Refinements

- **Plan's inventory table (`plan.md`'s "Inventory" section) calls `overlay_client.
  push_text_line` a "follow-on" not fixed now** — by the time this plan was implemented,
  `overlay_client`/the in-cockpit text overlay had already been removed entirely by `BL-B96`
  (confirmed: `grep -rn overlay_client body-layer/src/` returns nothing). The decision not to
  touch it is still correct, but for a different reason than the plan states (nothing to touch,
  not "deferred"). Worth a one-line note in the plan or `implementation.md` for a future reader
  who greps the inventory table and wonders why `overlay_client` isn't in the diff — optional,
  purely for future-reader clarity, no behavioural consequence.
- **Dispatch-prompt test counts (15 / 9) don't match the actual 11 / 8** — see "Test count note"
  above. Worth correcting wherever that count was first recorded (if anywhere outside this
  conversation), so a future reader doesn't go looking for 4 missing tests that were never
  promised by the plan or `implementation.md` themselves.

### Verdict
APPROVED

### Review Confidence
Full read — plan (incl. the 2026-11-12 refresh section), implementation.md, the full diff
(`speech_worker.py`, `crew_console.py`, `body.py`, `connection_reporter.py`, both test files,
`body-layer/CLAUDE.md`, the roadmap entry, the implementer's agent-memory file), and the
dispatch prompt's specific checkpoints verified individually against the code rather than against
the plan's description of the code. Format/lint/type/test commands run directly by the Reviewer
(not taken on trust) against a freshly built `.venv` in this worktree, with results matching
`implementation.md`'s own reported numbers exactly.
