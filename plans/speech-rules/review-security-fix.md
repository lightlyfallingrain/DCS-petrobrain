### Review Summary

Reviewed the Security Required Fix 1 commit (`f6304355`, on top of `262d5c9d`) for BL-17 — the
`nan`/`inf`/non-numeric guard on the two Lua→Python `int()` conversions in
`body-layer/src/rules/engine.py`. Branch `feature/speech-rules` fast-forwarded cleanly into this
worktree (HEAD was a strict ancestor of `f6304355`, tree clean).

**Confirmed by mutation, not just by reading the diff**: with the `_make_action_wrapper`
`math.isfinite` guard removed, `test_action_wrapper_rejects_nan_instead_of_raising` and
`test_action_wrapper_rejects_infinity_instead_of_raising` both go red with exactly the
`ValueError`/`OverflowError` Security's report describes. With `_digits_readback`'s guard
removed, `test_digits_rejects_a_string_slot_instead_of_raising` and
`test_digits_rejects_nan_instead_of_raising` both go red the same way. All four tests are real,
not decorative. `implementation.md`'s claim that `engine.py`/`loader.py` have no other
Lua-supplied `int(...)`/`float(...)` conversion, and `actions.py`/`sandbox.py` have none either,
was independently re-grepped against the merged tree (not just re-read) — confirmed: the only two
`int(` sites in `src/rules/*.py` are the two this fix guards, `actions.py`'s one `invoke` receives
an already-validated int, and the crash path Security traced (a bare Python exception escaping
`run_rule`'s `except (RuleRuntimeError, RuleBudgetExceeded)` and reaching the main-thread crew-text
REPL loop uncaught) is closed for every Lua→Python conversion in `body-layer/src/rules/`, not only
the two named sites — there are no others to close.

**The judgement call the dispatch asked for: the two sites are not architecturally equivalent, and
only one of the two fixes is right.**

- **`_make_action_wrapper`'s nan/inf check — correct, and consistent with an existing, already-
  reviewed contract.** The wrapper's own module docstring (predating this fix) already documents
  that a bad call — wrong arity, wrong type, out of bounds — answers `{ok=false, reason=nil}`
  rather than raising, and D5 (`plan.md` line 94) already states "validation in Python of every
  value Lua passes in" as the action registry's job. Every rule that calls an action is written to
  check this explicitly (`config/rules/flight.lua`'s `turn_heading_relative`: `if not r.ok then
  return say(unable(r.reason)) end`) — the rule author sees and handles the rejection by design.
  `nan`/`inf` joining that same reject branch, with the same `{ok=false, reason=nil}` answer, is
  the same failure class (an out-of-contract numeric argument) using the same established
  mechanism, not a new one. This is also exactly what Security's Required Fix 1 text prescribes.
  No change needed here.

- **`_digits_readback`'s degrade to `"Unable."` — does not satisfy the user's decision, required
  fix.** Before this patch, `digits` had no validation contract at all (a bare lambda); there is no
  pre-existing "the rule author checks and handles this" pattern the way there is for actions —
  a rule just does `say(digits(n))` with nothing to check. Returning `render_unable("").text`
  directly means: **no stderr log is produced** (confirmed — `_digits_readback` never raises and
  never calls `logger.error`; only `run_rule`'s `except` clause logs, and this path never reaches
  it), and the pilot hears **"Unable."**, which this project's own convention
  (`project_say_again_vs_unable` memory) reserves for "action unavailable" — a legitimate
  precondition failure, the same closed vocabulary `_UNABLE_TEMPLATES` enumerates
  (`NO_LINE_OF_SIGHT`, `NO_SUCH_COMMAND`, …). `digits(s.direction)` on a string slot is not a
  precondition failure; it is a bug in the rule file (a porting mistake, calling `digits` on the
  wrong kind of slot), exactly the class BL-17's own user decision names: *"Rule clash or lua error
  etc -> std error log and say aloud 'action file error'"* (`BL-17.md`) and D6's "A Lua error at
  dispatch time → that command's reply is 'Action file error.' ... The error and its traceback are
  logged." The current fix silently hides that bug behind a normal-sounding "Unable." with no
  trace anywhere — worse than before only in that it no longer crashes, but it still doesn't give
  the author (or the user, debugging the next ported command) what D6 promises.

  **Verified the fix by probe, not just by argument**: patching `_digits_readback` to raise
  `RuleRuntimeError(...)` instead of returning `render_unable("").text` (restored afterward,
  working tree is clean) and calling `run_rule` directly with the string-slot case produces
  exactly: `logger.error("rule 'spell_word' (r.lua) dispatch error: digits() called with
  non-numeric value: 'left'")` on stderr, and `RuleOutcome(lines=[], error=True)` — which
  `_handle_rule` turns into `[ACTION_FILE_ERROR_LINE]` with
  `_reset_one_shot_command_state()`. This is the minimal correct fix: `RuleRuntimeError` is
  already imported into `engine.py` (used elsewhere in the same module), `run_with_budget`'s own
  `except` clauses don't intercept it (they only catch `_InstructionBudgetExceeded`/
  `lua54.LuaError`), so it propagates untouched to `run_rule`'s `except (RuleRuntimeError,
  RuleBudgetExceeded)` exactly as the empirical propagation mechanics Security measured for a
  Lua-called Python callback predict — a directly-raised `RuleRuntimeError` is not a `LuaError`
  either, but it IS one of the two types that `except` clause already names, so it is caught
  correctly, unlike the bare `ValueError`/`OverflowError` that motivated this fix in the first
  place.

Security's own Required Fix 1 text (`security-stage0-2.md`) explicitly prescribed the
"degrade to Unable" shape for both sites, calling it "the same graceful-degradation posture
`_make_action_wrapper` already uses" — so the implementer built exactly what was asked, and the
asymmetry between the two sites wasn't something Security's charter (crash prevention) was
positioned to catch. Per this project's current division of labour, player-facing correctness
(including which failure the pilot is told about) is Reviewer's, not Security's, to hold — this is
that check doing its job.

### Required Fixes

1. **`body-layer/src/rules/engine.py:_digits_readback`** — replace the two `return
   render_unable("").text` branches with `raise RuleRuntimeError(...)` (a short message naming
   what was received is enough; `run_rule`'s log line already carries the rule id and file). This
   routes through D6's existing failure path (stderr log, "Action file error." readback, one-shot
   state rollback via `_handle_rule`) instead of a silent, unlogged "Unable." that reads as a
   legitimate precondition failure rather than a rule-file bug. Verified working by probe above.
   Update `test_digits_rejects_a_string_slot_instead_of_raising` and
   `test_digits_rejects_nan_instead_of_raising` to assert `outcome.error is True` and
   `outcome.lines == []` (the shape `test_a_lua_error_during_dispatch_is_reported_as_error` already
   asserts for a genuine Lua error) instead of the current `"Unable."` assertion, and update
   `implementation.md`'s "Security fix" section to describe the two sites' differing treatment
   (action-wrapper reject-branch vs. digits raising) and why, so the decision record doesn't read
   as more uniform than the fix actually is.

### Optional Refinements

- `_digits_readback`'s docstring sentence *"`""` is not one of D11's closed reason tokens -- it is
  deliberately not one, so `render_unable` falls through to its own unrecognised-reason default
  rather than reading as a real `ACTION_FILE_ERROR_LINE`-style reason"* becomes dead once Required
  Fix 1 lands (no more `render_unable` call in this function) — delete it along with the branches
  it was explaining, rather than leaving a comment describing code that no longer exists (optional,
  since it will be touched anyway by Required Fix 1, but flagging so it isn't missed in the
  rewrite).

### Verdict

NEEDS REVISION — Required Fix 1 above (the action-wrapper half of Security's own Required Fix 1 is
fine as shipped; the `digits` half needs to raise instead of degrade).

### Review Confidence

Full read of the diff, the two touched functions' full surrounding context, `plan.md`'s D5/D6 and
`BL-17.md`'s user decision, and `render_unable`/`_UNABLE_TEMPLATES`. Verified by mutation (both new
nan/inf-guard removals, confirmed red) and by an independent probe of the proposed fix (confirmed
the `RuleRuntimeError` route produces the stderr log and `error=True` D6 requires) rather than by
inspection alone. All stated checks (`ruff format --check`, `ruff check`, `mypy --strict src`,
`fast-tests.sh body-layer`) run fresh in this worktree and pass, matching the numbers
`implementation.md` claims (2737 passed, 4 xfailed; `test_rules_engine.py` 15/15 individually).
Not spot-checked: the rest of the merged batch (audio-adapter `rule_patterns.py`, the sandbox/
loader modules, the crew-console rule-dispatch wiring) was read for this fix's blast radius only,
not re-reviewed end to end — that was `review-stage1b-2.md`'s job, not this one's.

---

### Re-review, 2026-11-17

Scope: did the Required Fix 1 commit above actually land correctly. Diff checked:
`git diff 6ec02ae4..1b68c101` — `body-layer/src/rules/engine.py`, `body-layer/tests/
test_rules_engine.py`, `plans/speech-rules/implementation.md`, and one new implementer memory
file (`feedback_restore_mutation_probe_not_via_git_checkout.md`). Nothing else is in this diff —
confirmed with `git diff ... --name-only`, four files, matching the dispatch's stated scope
exactly.

**`_digits_readback` now raises as required.** Both branches changed from `return
render_unable("").text` to `raise RuleRuntimeError(f"digits() called with non-numeric value:
{n!r}")` / `raise RuleRuntimeError(f"digits() called with non-finite value: {n!r}")` — the exact
shape asked for, and the docstring was rewritten (not just trimmed) to explain why `digits` has no
pre-existing reject-branch contract the way `_make_action_wrapper` does, naming this review's
Required Fix 1 by file. The dead sentence about `""` not being one of D11's closed reason tokens
(flagged as an Optional Refinement above) is gone, correctly, since there is no more
`render_unable` call left in the function for it to describe — nothing load-bearing was lost with
it; it described code that no longer exists.

**Tests assert the D6 outcome and are real, not decorative.** Both renamed tests
(`test_digits_rejects_a_string_slot_as_a_dispatch_error`,
`test_digits_rejects_nan_as_a_dispatch_error`) now assert `outcome.lines == []` and `outcome.error
is True` — the shape `test_a_lua_error_during_dispatch_is_reported_as_error` already asserts for a
genuine Lua error — in place of the old `outcome.lines == ["Unable."]` / `outcome.error is False`.
**Verified by mutation myself, not just by reading the diff**: reverted `_digits_readback` to the
pre-fix `return render_unable("").text` shape (via a backed-up copy of the file, restored from
that copy afterward — not `git checkout --`, per the new implementer memory's own lesson, since
this worktree had no uncommitted state to lose anyway), re-ran `tests/test_rules_engine.py -k
digits`: both renamed tests go red with exactly `AssertionError: assert ['Unable.'] == []` /
the string-slot twin, the old-behaviour failure the fix is supposed to prevent. Restored and
re-ran: 15/15 green again, matching `implementation.md`'s claimed count.

**`implementation.md` is accurate.** The "Review-fix round, 2026-11-17" section correctly
describes the asymmetry (action-wrapper reject-branch unchanged and correct vs. `digits` now
raising), cites the review file and the user's BL-17 decision by name, records which two tests
changed and how, and explicitly notes the two action-wrapper tests are untouched. It does not read
as more uniform than the fix actually is — the problem this Required Fix existed to close.

**Checks, fresh in this worktree** (`cd body-layer`, venv built from
`/opt/homebrew/bin/python3.14` since none existed): `ruff format --check` — 218 files already
formatted; `ruff check` — all checks passed; `.venv/bin/mypy --strict src` — success, 89 source
files; `.claude/scripts/fast-tests.sh body-layer` — 2737 passed, 4 xfailed, matching
`implementation.md`'s numbers exactly. `git status --porcelain` clean in `body-layer/` after the
mutation probe and restore.

**Nothing else changed.** No scope creep beyond the four files the dispatch named; the one new
memory file is a legitimate implementer self-correction (restoring a mutated file from a backup
copy rather than `git checkout --`, which would have discarded the uncommitted fix along with the
mutation at the time it was written) and not itself part of the fix.

#### Verdict

APPROVED

#### Review Confidence

Full read of the diff and both touched functions' current state; verified by mutation (fresh
revert-and-restore, not relying on the first review's probe); all four stated checks re-run fresh
in this worktree and pass with matching numbers. Not spot-checked: the rest of the merged
`feature/speech-rules` tip beyond this diff (audio-adapter, sandbox/loader, crew-console wiring)
— out of scope for this re-review, per the dispatch.
