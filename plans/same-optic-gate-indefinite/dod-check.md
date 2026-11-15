# Definition of Done: fix/same-optic-gate-indefinite

**Scope note on this verdict.** This check ran against tip `bf1837a54485d298ee0c06eb186342b2a32c02ce`
(after a `git merge --ff-only` from this worktree's stale starting point `15c8b914`, which was a
strict ancestor with a clean tree). The verdict below is scoped to that commit only.

## Mechanical checks (body-layer — the only subproject this branch touches)

All run in this worktree, foreground, using `/Users/sg/Code/DCS-petrobrain/body-layer/.venv`
(no venv exists in this worktree itself) with `cwd` inside this worktree's `body-layer/`:

| check | command | result |
|---|---|---|
| format | `.venv/bin/ruff format --check src tests tools` | **PASS** — 205 files already formatted |
| lint | `.venv/bin/ruff check src tests tools` | **PASS** — "All checks passed!" |
| types | `cd body-layer && .venv/bin/mypy src` | **PASS** — "Success: no issues found in 79 source files" |
| tests | `PYTHONPATH=src:../world-model/src .venv/bin/pytest tests -q` | **PASS** — 3045 passed, 4 xfailed, 0 failed (236.07s) |

Matches `implementation.md`'s and `review.md`'s own reported counts exactly, independently
reproduced here rather than trusted. (The one pre-existing unformatted file the first review round
flagged, `research/2026-10-05-security-audit.md`, is no longer reported — either since fixed on a
sibling branch now merged into `main`, or not reached by this check's narrower `src tests tools`
path scope; either way it is not this branch's file and not a blocker.)

- No debug output or TODOs introduced by this feature (confirmed via the full diffs read below).
- No unhandled errors/panics in data paths: the fix is pure closed-form float arithmetic over
  already-internal `Covariance2D` values; no new I/O, no new exception path.
- `git status --porcelain` at this tip: clean. All files are committed (verified before and after
  this report's own additions, see "Staged/committed" below).

## Scope & correctness

- **Matches the plan.** There is no `plans/<featurename>/plan.md` for this entry — it is a bug fix
  (Debugger → Reviewer → Security → Performance → DoD path per `AGENTS.md`'s role sequences), and
  `debug.md` carries the investigation, hypothesis, evidence, fix and two rounds of user-directed
  continuation in its place. Read in full.
- **No unplanned scope added silently.** Two passes, both user-directed at an explicit decision
  point (`debug.md`'s "User direction 2026-11-09 (after the first pass)": *"continue as
  recommended"*; and the final "User decision 2026-11-09: stop here": *"stop here. If this becomes
  a problem in missions, we'll investigate more, but not now."*). The fence-reset pass
  (`implementation.md`) is exactly what that stop decision called for, nothing more.
- **No invariants violated.** No-omniscience preserved — confirmed independently by Reviewer (both
  rounds) and Security: no belief code reads `Observation.derived_world_position` or a ground-truth
  field; the one ground-truth probe (`measure_gate_calibration.py`'s `correlated_innovation_true_axis`)
  is confined to `tools/`, outside `mypy src`'s scope, documented "test-only, can never ship." No
  tuning-mechanism question — every changed production value (`_MIN_S_DETERMINANT_RATIO`) is a
  numerical-stability margin, not a behaviour-affecting constant, and every changed test value is a
  fence/ceiling, not a `tuning.py` entry — reasoning stated explicitly in both `debug.md` and
  `implementation.md`, and endorsed independently by Reviewer.
- **All new files staged.** Confirmed by `git status --porcelain` at this tip (clean) and by this
  report's own additions below (staged separately before commit).

## Testing

- **Core logic covered.** New regression test
  (`test_correlated_innovation_s_stays_psd_over_a_same_optic_ensemble`, 240 calls across both
  optics/four ranges) directly exercises the defect this fix closes and would fail against the
  pre-fix code (confirmed in `debug.md`: re-run repro went from 3/300 negative-determinant trials to
  0/300 post-fix). Not decorative — it asserts the actual numerical property (`det(S)`/`trace(S)`
  non-negative) the bug violated, at a tolerance two to three orders of magnitude tighter than the
  bug's own signature.
- **No existing tests broken** in the sense that matters here: the one test the first attempted fix
  *did* break (`test_stage0a_armour_growth_bounded_...`) was caught, root-caused and fixed before
  shipping (debug.md's own account of the exact-cap-alone regression) — re-verified bit-for-bit
  identical to the original `main` behaviour.
- **Six pre-existing fences did move**, and this is the correct, disclosed outcome, not a broken-test
  problem: the production fix removes a genuine over-rejection, so test fences built around the
  bug's own behaviour necessarily move. Per the user's explicit instruction, none were edited during
  the debug pass itself — they were reset in a clearly separated second pass (commit `5a896538`)
  with every new value independently re-measured (3-8 salts) rather than fitted to pass. The two
  tests whose old fence's *premise* (not just its number) was itself an artifact of the bug
  (`test_residual_fold_rate_for_far_binocular_near_unaided_is_small`,
  `test_false_trigger_rate_for_long_gap_stationary_same_group_exceeds_the_gate`) were converted from
  "the trigger works" assertions to "record the honest truth" assertions, with both the old dated
  finding and the new superseding note kept in the module docstring (prune for tense, not deletion).

## Documentation

- **Reviewer findings addressed.** One Required Fix (`debug.md`/`implementation.md` falsely claimed
  the harness-resampling fix had been applied to `_fuse_two_looks`, when only `_e3_fold_rate` had
  been touched) — closed in commit `259ea573`, re-reviewed and confirmed closed (`review.md`'s
  Re-review section, APPROVED, no further required fixes). Two Optional Refinements were partially
  addressed (a docstring note on the one-sided clamp) and partially left as explicitly-justified,
  documented choices (the tautological `<= 1.0` fence cell) — neither blocks.
- **Non-obvious behaviour explained.** `_max_c_down_for_psd`'s own docstring carries the PSD
  derivation; `debug.md` and `implementation.md` carry the measurement trail and the three ruled-out
  hypotheses for the residual mismatch, so the next person who touches this gate does not re-run
  dead ends. `notes/perception-calibration-and-measurement.md` now carries the generalizable lessons
  (see "Knowledge harvest" below).

## Security

- `plans/same-optic-gate-indefinite/security-review.md`: **APPROVED**. No dependency change, no
  untrusted-input surface in the diff (pure internal float math plus two offline dev-only CLI
  scripts). No finding met the bar for a backlog item.
- No separate `security-plan-review.md` exists for this entry — correct and expected: this is a bug
  fix (Debugger-path), and Security's plan-review step applies to the Architect→Implementer path,
  not the bug-fix path (`AGENTS.md`, "Recommended Role Sequences": `Bug fix: Debugger → Reviewer →
  Security (deep analysis) → Definition of Done`, no plan-review stage listed).

## Performance

- `plans/same-optic-gate-indefinite/performance-review.md`: **APPROVED**. Measured cost: +0.10 ms to
  +6.6 ms per poll at this project's actual observed scale (16-554 contacts), against a 1.0 s poll
  budget whose dominant cost (`group_salient_ids`, ~300 ms) this change does not touch. Verdict is
  MONITOR, not a blocker — re-measure only if the unpruned-contact-store axis (`BL-B23`) grows
  materially past 554, which is tracked separately and not this entry's scope.

## Milestone-completion question

**Yes — this changes what BL-B110 Stage 2 should be, and it is already recorded on BL-B110's own
entry file** (`body-layer/ROADMAP/BL-B110.md`, "Note, 2026-11-09", present before this DoD pass,
verified by reading the file directly rather than trusting the dispatch prompt's characterization):
Stage 2's trigger design was never built against honest numbers — the Stage 0 STOP finding
(long-gap false-trigger 25-27%) and the residual-catch figures (1-5%) that motivated deferring Stage
2 were both artifacts of the indefinite-`S` bug this branch fixes. Stage 2 must be re-designed and
re-measured on the honest post-fix numbers, not the stale ones. `[[BL-B113]]` (new, deferred) records
the separate, still-open finding that even with `S` valid, the same-optic gate over-rejects relative
to chi-square(2) for a reason not yet identified — this is the input Stage 2's eventual re-design
will have to account for, not something this entry resolves.

## `#needs-flight` — does not apply

The production change is a closed-form numerical correction to how an existing covariance gate
combines already-internal values; it has no new CLI surface, no new cockpit-observable behaviour,
and nothing in it requires live DCS to exercise or verify — every claim in `debug.md` was checked
with standalone repro scripts and two measurement tools (`measure_same_group_fold.py`,
`measure_gate_calibration.py`) run against the real production code, at up to 72,000 trials per
sweep. The measured behavioural effect size is small (debug.md: "the determinant bug was
contributing roughly 1% of trials per cell... not the dominant driver of the ~85-94% ceiling") and
is already covered, where it is flight-observable at all, by BL-B108's and BL-B110's own existing
`#needs-flight` cards (same-optic/cross-optic fold behaviour, per-sector scan) rather than by a new
one for this entry. `BL-B113.md` is tagged `#status/deferred` only, consistent with this: it is
explicitly conditioned on a future mission report ("if this becomes a problem in missions, we'll
investigate more"), not on a scheduled sortie — there is no clearing command to execute now; the
unblock condition is "Petrovich is heard reporting the same group twice" in an actual flight, which
only a future sortie can supply, and the entry says so.

## Execute the unblock condition of accepted debt

Checked for a runnable clearing condition per this role's own standing rule. `BL-B113`'s deferral
is conditioned on a future mission observation, not a script, probe, or query — there is nothing
to execute now. `BL-B110`'s "Stage 2 must be re-designed" note is a scoping instruction for the next
Architect pass on that entry, not an unblock command either. No executable clearing condition was
left unexecuted by this check.

## Knowledge harvest

`notes/perception-calibration-and-measurement.md` — four new bullets appended (none were
duplicates per `/notes-harvest`'s own scan):
1. A sum of two valid covariances is always PSD; subtracting a correlated cross-term is not, and a
   cap built for one call site does not protect another by default.
2. Driving a cap to the *exact* validity boundary (rather than a conservative one) can make a
   different caller's result come out larger even though the covariance it fed stays nominally
   valid — `min(conservative, exact)`, not replacement, is the general fix shape.
3. A stand-in/"as-if" test gate's own measured discriminating power can be an artifact of an
   unrelated numerical degeneracy in the pipeline it was measured against; fixing the degeneracy can
   invalidate the old number rather than confirm it.
4. A fix that removes a numerical-hygiene defect does not necessarily move the behaviour the defect
   was suspected of causing — measure the suspected downstream effect explicitly, don't credit the
   fix with it.

Two of these generalize agent-memory already written by Debugger/Performance Reviewer during this
task (`.claude/agent-memory/debugger/feedback_exact_psd_cap_can_regress_a_different_caller.md`,
`feedback_numerical_fix_can_leave_rejection_rate_unchanged.md`) — kept distinct here because
`notes/` is the project-wide reusable-insight store and agent-memory is role-scoped; no duplication
within `notes/` itself.

## Recurring-fix pattern check

Reviewer's one Required Fix on this branch — a dated claim in `debug.md`/`implementation.md`
("this fix was also applied to `_fuse_two_looks`") that did not match the actual diff — is a
documentation-accuracy defect, not a coordinate-frame or provenance-field category.
`.claude/agent-memory/dod/MEMORY.md` carries several "recurring_*" entries, closest of which is
`project_recurring_correct_conclusion_unearned_reason.md` (a correct conclusion with an unchecked
reason) and `project_main_doc_describes_unmerged_branch_behaviour.md` (prose describing the wrong
branch's state) — neither is an exact match: this was a correct *intended* scope statement that
simply hadn't shipped yet, caught by diffing the actual hunks against the claim. Searched
`.claude/agent-memory/` for a prior occurrence of this exact shape ("doc claims function X was
fixed in this pass; diff shows only function Y was") and found none. **One occurrence, not a
pattern yet** — no new or updated pattern memory filed. Reviewer's own memory file
(`feedback_debug_log_fix_scope_claim_vs_diff_hunks.md`) is the right place for this to live until a
second occurrence, if one comes, promotes it.

## Verdict

**PASSED**, scoped to tip `bf1837a54485d298ee0c06eb186342b2a32c02ce`.

## Acceptance testing

**PENDING (live) does not apply in the usual sense — there is nothing new for the user to fly.**
This is a numerical-conditioning fix verified entirely by offline measurement against the real
production code (standalone repros, two measurement tools, the full test suite); see
"`#needs-flight` — does not apply" above. No acceptance testing plan or card is published for this
entry. The user's open live-acceptance items remain exactly where they were before this
branch: `BL-B108`'s and `BL-B110`'s own existing cards (named `main` as the branch to fly in each
case), unaffected by this fix beyond the fence numbers this entry documents.
