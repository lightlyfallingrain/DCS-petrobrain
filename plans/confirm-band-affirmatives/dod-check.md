# Definition of Done Check: confirm-band-affirmatives

Branch `fix/confirm-band-affirmatives`, tip `e4af660`, off `main` @ `8e9282b`. HEAD verified
matching before any check ran — worked directly in the main checkout, no worktree/archive needed.

Origin: a bug fix (Debugger-class defect, diagnosed from a 2026-09-26 sortie — see
`todo/todo.md`), not an Architect-planned feature. No `plans/confirm-band-affirmatives/plan.md`
and no `security-plan-review.md` are expected for this branch, and none exist — that is correct
for a fix of this kind, not a gap.

## Code Quality

- [x] Two touched subprojects (`body-layer`, `audio-adapter`), both run in full:
  - `body-layer`: `ruff format --check` clean (111 files) · `ruff check` clean · `mypy --strict`
    clean (52 source files) · `pytest` **1313 passed, 4 xfailed** (matches expected).
  - `audio-adapter`: `ruff format --check` clean (29 files) · `ruff check` clean · `mypy --strict`
    clean (15 source files) · `pytest` **213 passed, 1 skipped** (matches expected).
- [x] No unhandled errors/panics introduced — the one pre-existing `except Exception` in
  `crew_console.py:1799` is outside this diff's changed hunks (confirmed by Security's own diff
  check).
- [x] No debug output or leftover TODOs in the diff.

## Scope & Correctness

- [x] No `plan.md` exists (bug fix, not planned feature) — implementation matches the diagnosis
  recorded in `todo/todo.md`'s corrected entry (2026-09-28) and `body-layer/ROADMAP.md`'s
  live-acceptance-debt entry.
- [x] No unplanned scope added — Decision 2a (sector coverage) and the `_confirmation_expired_sim`
  hygiene reset were explicitly named as out-of-scope/optional, not silently pulled in.
- [x] No invariants violated. The one deliberate tradeoff (widened vocabulary + longer window also
  gates the destructive `cancel_task`/`cancel_scan`/`cancel_watch` tokens) was surfaced by Security
  as an accepted-risk item for the user, not decided by any agent — see below.
- [x] `git status --porcelain` is clean for everything belonging to this feature. The three
  modified `run-scripts/*.sh` files are the user's own uncommitted local edits (brain HTTP client
  flags), unrelated to this branch — left untouched per instruction.

## Testing

- [x] Core logic covered: `test_voice_commands.py` and `test_crew_console.py` extended across five
  review rounds; a cross-subproject coupling test in `audio-adapter/tests/test_command_matcher.py`
  pins the anchor-word/classifier boundary from both sides.
- [x] Tests are meaningful — the Reviewer's log shows each of the five rounds' fixes verified by
  direct reproduction against the real matcher, not by a test that supplied its own default for
  the parameter under scrutiny (see Harvest below).
- [x] No existing tests broken — one test was legitimately changed
  (`test_handle_transcript_confirm_expires_after_window`) because its own scenario's correct
  answer changed under the new window; the reviewer confirmed nothing it used to guard was lost,
  since a new test now covers that case.

## Documentation

- [x] All required Reviewer fixes addressed — `plans/confirm-band-affirmatives/review.md` shows
  four "NEEDS REVISION" rounds each resolved, with round 5 "APPROVED".
- [x] Non-obvious behavior explained: `todo/todo.md`'s corrected diagnosis, the docstring in
  `voice_commands.py`, and `body-layer/ROADMAP.md`'s live-acceptance-debt entry.

## Security

- [x] No `security-plan-review.md` expected (bug fix, no plan.md) — consistent with prior
  agent-memory note on this pattern.
- [x] `security-review.md` exists, verdict **APPROVED**, with one accepted-risk item surfaced for
  the user rather than decided by Security or DoD: the widened vocabulary/window also gates the
  three destructive cancel tokens. Security's own recommendation is (A) accept as the designed
  tradeoff. **This decision is the user's — see report below, not resolved by this gate.**

## Performance

- [x] `plans/confirm-band-affirmatives/performance.md` — verdict **APPROVED**, MONITOR only.
  Confirmed: this lives on the per-transcript dispatch path, not the 5 Hz poll loop; every new
  piece of state is a fixed-size scalar or frozenset, none of which grows or accumulates over a
  sortie.

## Verdict: PASSED

All mechanical checks pass. No outstanding required fixes. One accepted-risk security tradeoff is
carried forward to the user's decision (not blocking). Live-DCS acceptance is outstanding and
tracked as debt in `body-layer/ROADMAP.md` (see the Acceptance Testing Plan below) — this does not
gate the merge, per project policy on live-acceptance debt vs. deferred-vs-waived scoping.
