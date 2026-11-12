# Definition of Done: BL-B106 (async speech: the mouth never blocks the eyes and arms)

Branch `feature/async-speech-impl`, tip `ef6bcb0cd3f7bb0ae9c383ebbebf2170edb88b88`. This verdict
is scoped to that commit; a later commit on the branch would need a fresh pass.

HEAD at dispatch (`f480cf71...`) was a strict ancestor of the named tip and the tree was clean —
fast-forwarded with `git merge --ff-only ef6bcb0c...`.

## Code Quality

Only `body-layer/` touches code in this diff (`git diff main..ef6bcb0c` — confirmed; `plans/` and
`.claude/agent-memory/` are docs/memory). All commands run directly in this worktree, against
`/Users/sg/Code/DCS-petrobrain/body-layer/.venv` (no `.venv` exists inside the worktree copy, per
`.claude/agent-memory/reviewer/feedback_worktree_use_main_checkout_venv.md`):

| check | result |
|---|---|
| `ruff format --check src tests` | 200 files already formatted |
| `ruff check src tests` | All checks passed! |
| `cd body-layer && .venv/bin/mypy src` | Success: no issues found in 82 source files |
| `pytest tests -q` (full suite) | **3193 passed, 4 xfailed** in 280.32s |

Matches `implementation.md`'s and `review.md`'s own reported numbers exactly (3193 = the
pre-existing 3192 + the one perf-fix test; 4 xfailed pre-existing/unrelated).

- No unhandled errors/panics in data paths: `SpeechWorker._run` wraps each queued item in its own
  `except Exception` (reviewed by both Reviewer and Security; catches `Exception` not
  `BaseException`, correctly scoped for a non-main daemon thread) so a bug in one item cannot
  silently kill the worker for the rest of the sortie.
- No debug output or leftover TODOs introduced — confirmed by the diff review already performed by
  Reviewer/Security (full reads, not spot checks) and spot-confirmed here by rereading
  `speech_worker.py` and the `crew_console.py`/`body.py` hunks.

## Scope & Correctness

- Implementation matches `plans/async-speech/plan.md`, including its "Refresh against the code of
  2026-11-12" section, which the plan itself states binds over the older text. Reviewer traced
  every plan decision (1-4) to the actual code, not the plan's description of it, and so did
  Security/Performance independently.
- One unplanned-but-in-scope addition: the performance-reviewer's NOW finding (`SpeechWorker.
  interrupt()`'s `client.stop()` sharing `push_speech`'s 5.0s timeout) went through the standing
  "change request re-enters Implementer → Reviewer → DoD" loop — Implementer fixed it
  (`AudioAdapterClient.stop_timeout_s = 1.0`), Reviewer re-reviewed just that change and
  re-APPROVED (`review.md`'s "Fix review (e77f8b26)"). Not silent scope drift — tracked end to end.
- No CLAUDE.md invariants violated: no new omniscience path (`SpeechWorker`/`drain_speech_results`
  never touch ground truth), module independence preserved (stdlib-only new imports, confirmed by
  Security's dependency-status check), `_MAX_QUEUE_LEN = 64` correctly kept as an ordinary literal
  rather than a `tuning.py` entry (it bounds a defensive queue depth, not something Petrovich
  decides — Reviewer and the Fix review both checked this against the inclusion test explicitly).
- All files staged and committed — confirmed by `git status --porcelain` below.

## Testing

- Core logic covered: `SpeechWorker` itself (order preservation, no-overlap, bounded
  drop-oldest-plus-one-warning, urgent interrupt, close/lifecycle, the genuinely-wedged-socket
  non-blocking-enqueue test, and the perf-fix's bounded-interrupt-under-a-wedged-client test) in
  `test_speech_worker.py`; `CrewConsole`'s wiring (worker-vs-fallback split, the `silenced`
  third-branch, `drain_speech_results`, `stop_talking`/`reset_for_new_mission` routing,
  `audio_adapter_reporter` pass-through) in `test_crew_console.py` against a `FakeSpeechWorker`
  double — deliberately not a real thread, since the threading behaviour is already exercised in
  `test_speech_worker.py`.
- Tests are meaningful, not decorative: the implementer's own counterfactual check (reverting
  `stop_timeout_s` to `self.timeout_s` reproduces the ~5.1s stall and fails the new test) is
  recorded in `implementation.md`, and the Reviewer's fix-review treated the test's own numbers
  (asserting `<2.0s` against a 1.0s timeout, well below `push_speech`'s 5.0s default) as
  independently consistent with a real check rather than re-running the revert from scratch.
- No existing tests broken: the ~53 pre-existing `FakeSpeechClient`-based assertions in
  `test_crew_console.py` are confirmed unmodified (Decision 1's own claim, verified by running the
  full suite, not assumed) — the fallback synchronous path they exercise is still exactly the code
  that ran before this feature.
- `test_mission_start_reset.py`'s generic per-field preserve-set test caught a real gap the plan's
  own Stage-4 list did not name (`speech_worker`/`audio_adapter_reporter` missing from
  `_CREW_CONSOLE_PRESERVE`) by actually running the full suite — recorded in `implementation.md`'s
  "Notable Discoveries," confirming this test earns its keep again.

## Documentation

- Reviewer findings addressed: `review.md`'s "Required Fixes" is empty on both the main pass and
  the fix-review pass — both APPROVED with no blocking items. The two Optional Refinements (an
  `overlay_client` inventory-table note, and a dispatch-prompt test-count mismatch) are purely
  for a future reader's clarity, not code changes, and are not required for DoD.
- Non-obvious behaviour explained: `body-layer/CLAUDE.md`'s "Voice-latency instrumentation"
  paragraph and module map were updated in the implementation itself (confirmed present in this
  worktree) to describe the async dispatch, which thread calls `speech_log_sink` and why, and the
  new `speech_worker.py` module-map entry.
- Added at DoD time (per the plan's own Stage 6 instruction, "add a short pointer... since this
  plan is what resolves it"): a "Resolved 2026-11-12 by `[[BL-B106]]`" line in
  `plans/voice-latency-instrumentation/performance-review.md`'s `push_speech`-blocking MONITOR
  note, pointing forward to this plan, and a matching back-pointer in `plans/async-speech/plan.md`
  Stage 6 noting it is done. This is a documentation pointer on a closed plan's own artifact, not
  a reopened decision.

## Security

- `plans/async-speech/security-plan-review.md` does not exist — **this is correct, not a gap**:
  root `CLAUDE.md`/`AGENTS.md` ("Security's plan review left the sequences," 2026-10-30 user
  direction) dropped Security's plan-review step between Architect and Implementer from the
  standard sequence; it remains available on demand only, and nothing in this plan asked for it.
- `plans/async-speech/security-review.md` exists and is **APPROVED**, no required fixes.
  Dependency status: no new dependency (stdlib only, confirmed by reading the diff's import
  lines). Thread-safety of every piece of newly-shared state (`ConnectionReporter`'s lock,
  `_overflow_warned`'s acceptable cosmetic race, `_results`'s symmetric locking) individually
  checked against the code. The plan's own flagged risk (a dropped overflow line gets no
  `speech_log_sink` row) assessed as an observability nuance, not a security finding, and not
  filed as new — it is the plan's own already-accepted risk.

## Milestone-boundary question (per "Milestone Completion")

Does this change what the next milestone should be, or invalidate a downstream assumption? **No
invalidation; one second-order effect recorded on the roadmap entry.** `plans/voice-latency-
instrumentation/performance-review.md`'s Stage-6 finding ("`drain_pending_positional_replies`
bounded to at most one poll interval") assumed the poll itself reliably took ~1s — a slow
`push_speech` call could stretch that bound arbitrarily, so this milestone is what makes that
already-stated bound actually *true*, not merely modeled, rather than opening a new question.
`[[BL-B116]]` (body resource arbitration, minted on a separate docs branch, not yet merged here)
builds on the now-asynchronous speech path; nothing in this feature's own scope needs revisiting
for it to proceed.

## Acceptance Testing Plan

**Goal:** confirm the poll loop (eyes/arms) no longer stalls on speech, and that interrupt/reset/
failure behaviour around it is correct in a live cockpit.

**Live acceptance: cannot be performed now.** Per root `CLAUDE.md` "Workflow," DoD PASSED merges
automatically; a live test the user has not yet flown does not hold the merge. Marked
**PENDING (live)**, tagged `#needs-flight` on `body-layer/ROADMAP/BL-B106.md`.

**Prerequisites**
- [x] Type-checked (`cd body-layer && .venv/bin/mypy src`) — confirmed above.
- [ ] Fly on `main`, after merge — see the test card the main loop publishes.

**Test Cases** (what the sortie needs to verify, per the dispatch prompt)
1. A long callout no longer freezes scan updates / 9K113 slew while being spoken.
2. `stop talking` cuts speech within ~1s (now bounded by `stop_timeout_s = 1.0`, not
   `push_speech`'s 5.0s default).
3. Speech order unchanged, no overlapping lines (FIFO queue, single worker thread).
4. After a mission restart, no stale pre-restart line is spoken (`reset_for_new_mission` now calls
   `speech_worker.interrupt()`).
5. With the audio-adapter down, body-layer keeps ticking and logs one "audio adapter disconnected"
   line, then "connected" when it returns (`ConnectionReporter`, now lock-guarded against the
   worker thread's concurrent calls).

**Pass Criteria:** the feature passes if all five hold and no regression appears in ordinary
speech/command behaviour.

## Verdict

**DoD: PASSED** (tip `ef6bcb0cd3f7bb0ae9c383ebbebf2170edb88b88`).
**Acceptance testing: PENDING (live)** — `#needs-flight` tag applied on
`body-layer/ROADMAP/BL-B106.md`; branch to fly is `main` after merge.
