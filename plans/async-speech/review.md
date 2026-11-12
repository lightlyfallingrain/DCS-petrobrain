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

## Fix review (e77f8b26)

Review-of-the-fix for the performance-reviewer change request (`plans/async-speech/
performance-review.md`'s NOW finding), re-entering the loop per `AGENTS.md`. Worktree HEAD was
`f480cf71` (ancestor of the named tip); fast-forwarded to `e77f8b26059cc96896f24c41e20fef89b2e65cfc`
cleanly (tree was clean before and after). Diff reviewed: `57a5a7ca..e77f8b26`, one commit
("BL-B106: give AudioAdapterClient.stop() its own short timeout"), three files:
`audio_client.py`, `test_speech_worker.py`, `implementation.md`.

- **Scope matches the finding exactly.** `AudioAdapterClient` gains `stop_timeout_s: float = 1.0`
  (module constant `_DEFAULT_STOP_TIMEOUT_S`), used only inside `stop()`'s `urlopen(...,
  timeout=self.stop_timeout_s)` call. `push_speech`'s and `get_transcripts`'s own timeout handling
  is untouched — confirmed by reading the diff hunk boundaries, not just the stat summary: the
  only changed method body is `stop()`.
- **The new test genuinely exercises `stop()`'s path, not `push_speech`'s.**
  `test_interrupt_wall_time_is_bounded_well_under_push_speechs_timeout_against_a_wedged_client`
  calls `worker.interrupt()`, which (per `speech_worker.py`'s `interrupt()`, read directly) clears
  the queue and calls `self._client.stop()` — never `push_speech`. It reuses the same genuinely-
  wedged raw-socket `_WedgedSpeechServer` as the existing enqueue test (own local copy, no shared
  fixture yet — consistent with this file's existing style) and asserts wall time `< 2.0s` against
  a client built with defaults (`stop_timeout_s=1.0`, `timeout_s=5.0` unchanged), which is a real
  assertion about `/stop`'s own bound, not `push_speech`'s. The implementer's reported
  counterfactual (reverting to `self.timeout_s` reproduces a ~5.1s stall and fails the test) is the
  right way to have confirmed this is not a decorative assertion; I did not independently re-run
  the revert, since the commit message states it was checked and the test's own numbers (asserting
  `< 2.0` against a 1.0s timeout, comfortably below `push_speech`'s 5.0s) are consistent with a
  real, not accidentally-always-passing, check.
- **Tuning-mechanism inclusion test applied correctly.** `_DEFAULT_STOP_TIMEOUT_S` bounds a
  transport-level wait on a failed/wedged HTTP call — the implementer.md inclusion test's own listed
  exemption ("a protocol constant... is not" behaviour-affecting) names exactly this case. It does
  not change what Petrovich says, sees, remembers, or how long *he* makes the pilot wait; it bounds
  how long a broken network call is tolerated before the poll thread gives up. Treating it as an
  ordinary module literal rather than a `tuning.py` entry is correct, and the `#:` comment above it
  states the reasoning and cites the precedent (`speech_worker._MAX_QUEUE_LEN`) accurately.
  `body-layer/config/defaults.toml` is correctly untouched (confirmed: the fix commit's full file
  list is `audio_client.py`, `test_speech_worker.py`, `implementation.md` — no `defaults.toml`).
- **Cross-key coupling, noted but not a defect.** `stop_timeout_s` (1.0) is shorter than
  `timeout_s` (5.0) by design and by the commit's own stated reasoning (`/stop` has no synthesis to
  wait out), but nothing asserts `stop_timeout_s <= timeout_s` at the dataclass level — a caller
  constructing `AudioAdapterClient(base_url=..., stop_timeout_s=10.0)` would silently defeat the
  fix's purpose. Low risk: the client is constructed exactly once in `body.py` with neither field
  overridden, so there is no live path that could hit this today. Optional, not required.
- **Nothing else changed** — `implementation.md`'s new "Perf fix" section matches the diff; no
  unrelated edits rode along.

**Checks** (main checkout's `.venv` by absolute path, cwd in this worktree's `body-layer/`, per
`.claude/agent-memory/reviewer/feedback_worktree_use_main_checkout_venv.md`):
`ruff format --check` — 200 files already formatted; `ruff check` — all passed; `mypy src` —
success, 82 source files; `pytest -q tests/test_speech_worker.py tests/test_crew_console.py` —
**288 passed**.

### Fix Required Fixes
None.

### Fix Optional Refinements
- **No assertion that `stop_timeout_s <= timeout_s`** on `AudioAdapterClient` — see above. Worth a
  one-line guard or comment if a second construction site is ever added; not worth one for a
  single, fixed-argument call site.

### Fix Verdict
APPROVED

### Fix Review Confidence
Full read — the one-commit diff in full, `speech_worker.py`'s `interrupt()`, the new test and its
helper server, `implementation.md`'s new section, and `performance-review.md`'s NOW finding it
answers. Checks run directly, not taken on trust.
