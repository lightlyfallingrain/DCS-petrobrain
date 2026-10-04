## Definition of Done: redundant-group-disclosure

**Branch:** `fix/redundant-group-disclosure` · **Verified tip:** `acae73f` (confirmed via
`git rev-parse fix/redundant-group-disclosure` from an isolated DoD worktree whose own `HEAD` was
`main`/`3fe93fd` — the branch is checked out in the main checkout, so verification ran against a
`git archive fix/redundant-group-disclosure` snapshot extracted to
`/private/tmp/claude-501/-Users-sg-Code-DCS-petrobrain/912e8304-06e6-47eb-b21d-2480a8d16101/scratchpad/rgd-snapshot`,
with every command's cwd inside that snapshot's `body-layer/` directory, using the main checkout's
`body-layer/.venv/bin/{ruff,mypy,pytest}` binaries.)

### Code Quality

- [x] `ruff format --check src tests` — 114 files already formatted.
- [x] `ruff check src tests` — all checks passed.
- [x] `mypy src` (strict, run as `cd body-layer && mypy src` per this project's CWD-only config
  discovery rule) — Success: no issues found in 53 source files.
- [x] `pytest tests -q` — **1414 passed, 4 xfailed**, exactly as predicted (main's own baseline is
  1409 passed/4 xfailed; +5 new tests, 0 regressions).
- [x] No debug output / no TODOs introduced — diff reviewed (`git show --stat acae73f` and the
  full `main...fix/redundant-group-disclosure` diff for `body-layer/ROADMAP.md`); only touched
  files are `callouts.py`, `speech.py`, their tests, `BACKLOG.md`/`ROADMAP.md` bookkeeping,
  `plans/contact-duplication-ambiguity-runaway/plan.md`, three `plans/redundant-group-disclosure/`
  docs, and agent-memory files.
- [x] Only one subproject touched (`body-layer`) — confirmed from the file list above; no other
  subproject's commands are owed.

### Scope & Correctness

- [x] Matches `plans/redundant-group-disclosure/implementation.md` (no separate `plan.md` — this
  is a bug-fix branch, Debugger→Reviewer→Security(deep)→DoD per `AGENTS.md`'s role-sequence table;
  no plan-review-stage security doc is expected under the current once-per-feature cadence).
  `render_group_disclosure` gained the exact keyword-only `already_reported_contact_ids` parameter
  described, with the three-way silent/partial/full split; `CalloutScheduler.
  _already_reported_member_ids` supplies it from `_last_spoken_signature` plus the shared
  `_is_merge_echo_of_earlier_contact` predicate. Verified directly in
  `body-layer/src/belief/callouts.py` (lines ~551, ~639–880) and `speech.py`.
- [x] No unplanned scope added — the one test-expectation change
  (`test_2c_transcript_fixture_renders_four_lines_not_seven`) is the fix's own designed behaviour
  hitting a second, pre-existing fixture case (confirmed below), not an unrelated change riding
  along.
- [x] No invariants violated — Security's deep analysis (acae73f) confirmed no-omniscience
  (reads only speech history + believed contact state, no ground-truth read), no new dependency,
  no per-tick cost blowup (per-candidate, same shape already priced for the flood fix).
- [x] All new files staged — confirmed via `git show --stat acae73f`; nothing untracked.

### Testing

- [x] Core logic covered: 4 new `test_speech.py` unit tests on `render_group_disclosure`'s new
  branch, 1 new `test_callouts.py` integration test exercising `_already_reported_member_ids`
  end-to-end through the scheduler.
- [x] Tests are meaningful, not decorative — they pin literal rendered sentences (not shape
  predicates — this project's own recurring failure class, see `NOTES.md`), and the integration
  test is built on a real fixture chain (merge-echo + group persistence), not a synthetic shortcut.
- [x] **One existing test's expectation changed —
  `test_2c_transcript_fixture_renders_four_lines_not_seven` now expects `"BTR-70 and truck, in 1
  o'clock group."`** Read the full docstring and the diff: this is the fix's own branch-1 logic
  hitting a second case the task didn't originally name — the fixture's five-member group's first
  disclosure used to speak the full roster even though one member (`CONTACT_2`) had already been
  individually announced as line 1; under the fix, the other two never-individually-spoken infantry
  fold in silently (an already-known class, branch-4 rule) and the opening line names only the
  BTR-70 and truck. Line count is unchanged (still 4 lines); only the third line's wording
  shortened. This is the same bug class as the task's named 730.9 example, not a weakened
  assertion — confirmed by reading the full reasoning in the docstring and cross-checking against
  `implementation.md`'s "Notable Discoveries" section, which independently derives the identical
  explanation.
- [x] No existing tests broken — 1414/4 passed/xfailed, zero failures.

### Documentation

- [x] Reviewer findings addressed — both rounds returned **zero required fixes**. Round 1's three
  optional refinements were all actioned anyway (shared predicate factored into
  `_is_merge_echo_of_earlier_contact`, residual filed as `BL-B25`, bookkeeping landed in
  `ROADMAP.md`/`BACKLOG.md`/`plans/contact-duplication-ambiguity-runaway/plan.md`). Round 2
  re-verified all three and found no further required fixes (one cosmetic label mismatch between
  `implementation.md` and `review.md`, noted but not actioned, harmless).
- [x] Non-obvious behaviour explained — `implementation.md`'s "Where 'already reported' is known"
  section, the module docstring extension in `callouts.py`, and the `BL-B25` backlog entry for the
  known current-tick-reevaluation residual.

### Security

- [x] No security-plan-review.md expected (bug-fix path, once-per-feature cadence — not a gap).
- [x] `plans/redundant-group-disclosure/security-review.md` exists and is **APPROVED**. No
  dependency change, no omniscience violation, suppression-chain composition verified safe
  per-member (not per-group — see NOTES.md harvest below), cost shape already priced.

### Verdict: PASS

No FAILs. Nothing to route back to Implementer, Reviewer, or Security.

---

### Acceptance boundary — what these fixtures structurally cannot reach

This DoD passed on **fixtures and a retrospective reconstruction of one recorded sortie
(`sortie-1004`)**, not a live flight. Two things that reconstruction cannot establish:

1. **Whether the suppression *feels* right in the cockpit, not just whether it is logically
   correct.** The measurement found 1 of 5 group-level lines in the sortie confirmed suppressed
   (the named `t_sim=730.9` case), 1 more strongly suspected, 3 unaffected — a real but modest
   effect size. A fixture cannot tell us whether the pilot actually noticed the earlier
   over-talkative behaviour on *these* specific lines, or whether removing them changes anything
   he'd consciously register. Only a flight settles that.
2. **The over-suppression risk this fix's own design accepts.** `BL-B25` (filed, not fixed) means
   the predicate is re-evaluated at the *current* tick rather than the tick the original
   suppression happened — bounded, and it pushes toward *more* speaking, not less, so it is not
   the dangerous direction for this particular residual. But the fix's *general* risk direction —
   over-suppression, a group going silent about a member that was never actually reported — is
   exactly what no fixture chain can rule out exhaustively. The security review verified the
   per-member composition logic is correct by construction and by a dedicated test, but "correct
   by construction against the cases we thought to test" is not the same guarantee as "the pilot
   never hears silence where he needed a report," which only many real sorties across many
   scenarios can approach.

**Live verification is deliberately deferred, not waived**, and rides the already-pending
`fix/contact-report-flood` sortie rather than needing a dedicated flight — see
`body-layer/ROADMAP.md`'s Live acceptance debt entry added this run.
