# DoD Check — Cones Slice 2C (the o'clock scan loop)

Branch: `feature/cones-2c-scan-loop`. Implementation `665821f`, tests `bfb57c4`, implementer memory
`9b819ba`. Review `0fb7445` (**APPROVED WITH MINOR FIXES**, full-read confidence). Fixes applied in
`ddc2d43` (stale `_previously_visible_ids`/`_acquired_ids` docstring names; missing 2C section in
`plans/detection-cones-slice2/implementation.md`) — both confirmed present in `ddc2d43`'s diff by
direct read, not by trusting the commit message.

Run from a worktree detached at `ddc2d43` (`feature/cones-2c-scan-loop`'s tip); the branch itself
stays checked out in the shared main checkout per the current worktree convention, so this DoD pass
worked from a detached copy of the same commit rather than touching that checkout.

## Code Quality

- **Subprojects touched**: `git diff --name-only 19180a0..ddc2d43` (merge-base of `main` and the
  branch tip) touches `body-layer/`, `plans/`, and `.claude/` only. `world-model/` and
  `aircraft-layer/` are untouched — confirmed by `awk -F/ '{print $1}' | sort -u` on the diff.
- Set up `body-layer/.venv` fresh in this worktree (none existed) and ran the full sequence from
  `body-layer/CLAUDE.md` "Commands":
  - `ruff format --check src tests` → **83 files already formatted** (PASS)
  - `ruff check src tests` → **All checks passed!** (PASS)
  - `cd body-layer && mypy src` → **Success: no issues found in 39 source files** (PASS)
  - `pytest tests -q` → **830 passed, 4 xfailed** (PASS — exact match to the expected count)
  - `pytest tests -q -rx` confirms all 4 xfails are the pre-existing 2A binocular-presence-multiplier
    residual (`test_armored_vehicle_is_visible_at_the_farthest_photographed_range`,
    `test_computed_tier_matches_ground_truth[C-1000m]`,
    `test_gate_admits_every_photographed_range[C-8890m]`,
    `test_gate_admits_every_photographed_range[C-6580m]`) — 2C added none.
- No debug output or TODO/FIXME/pdb/breakpoint introduced: `git diff 19180a0..ddc2d43 -- body-layer`
  grepped for `print(`/`TODO`/`FIXME`/`pdb.set_trace`/`breakpoint(` on added lines — no hits.
- No unhandled errors/panics in a new data path: `gaze_at(t_sim, plan)` is a pure table
  lookup/modulo function (Reviewer confirmed no wall-clock read, no mutation); the two new
  acquisition dicts are pruned every poll with no unbounded growth (Reviewer traced both
  `_acquire_on_change`/`_acquire_every_poll` by hand).

## Scope & Correctness

- `git diff --name-status 19180a0..ddc2d43 -- body-layer` touches exactly `belief/decay.py`,
  `logger.py`, `perception/gaze.py`, `perception/naked_eye_source.py`, and their tests — matches the
  plan's 2C file list. `optics.py`, `object_model.py`, `visibility.py`, `clustering.py`,
  `association.py`, `belief/contacts.py` are untouched (2A/2A.5/2B undisturbed). No 2D code exists
  on this branch (no dwell state, no `BINOCULAR_OPTIC` caller) — reviewer confirmed, spot-checked by
  grep here.
- Implementation matches `plans/detection-cones-slice2/plan.md`'s 2C sections: the free-scan table
  `12, 11, 10, 9, 12, 1, 2, 3` at 2 s/leg (16 s cycle, forward arc twice per cycle),
  `OBSERVED_WINDOW_S` 5.0 → 16.0, time-based acquisition state. One genuine plan defect was found and
  resolved during implementation (a commanded sector generalised to its own sub-cycling smaller cone
  rather than a static wedge) — Reviewer judged this the correct reading of the plan's own hard
  parts 1 and 2a, not scope creep, and it is now recorded in `implementation.md`'s 2C section.
- All files touched are already committed on the branch (`git status --porcelain` clean at
  `ddc2d43`); no new files were left unstaged.

## Testing

- Core logic covered: free-scan table walk, `ahead`'s degenerate static case, `left`/`right`'s
  3-leg cycling, `full` matching the table verbatim, command-relative-not-absolute-time property
  (`test_gaze.py`); both `OBSERVED_WINDOW_S` bound derivations pinned as module-level `assert`s in
  `decay.py` plus pytest wrappers (Reviewer noted the asserts are the real protection, the tests are
  documentation — flagged optional, not required); time-based acquisition/eviction traced and tested
  for both `on_change` and `every_poll` modes; determinism reconfirmed by
  `test_replaying_the_same_stream_twice_yields_identical_observations`.
- Moved test expectations (rescale factors, trace-outcome relocation, widened debounce gaps) were
  independently re-derived by the Reviewer rather than trusted from the commit message — all
  confirmed correct.
- No existing tests broken: 810 → 830 passed is a net addition, same 4 xfails carried forward
  unchanged.

## Documentation

- Both Reviewer required fixes addressed in `ddc2d43` (confirmed by reading the diff, not just the
  commit message).
- `implementation.md`'s 2C section records the plan-defect finding and its resolution.
- Non-obvious behaviour (why a commanded sector sub-cycles, the `OBSERVED_WINDOW_S` derivation
  inequality) is documented in both the module docstrings that use it and `implementation.md`.

## Security

Project's `CLAUDE.md` "Agents" section exempts `security` for this phase (offline single-user local
pipeline, no hot path, no untrusted-input surface) — no plan-review or deep-analysis sign-off file
is expected or present for this slice, consistent with every prior cones sub-slice.

## Milestone-completion question (per `CLAUDE.md` "Milestone Completion")

- **2D's conditionality is unchanged by 2C's code.** The plan states 2D is "conditional — only built
  if 2C's sortie shows a real need" (plan `plan.md` line 61) and explicitly gates it on the *sortie*,
  not on 2C merging. Nothing in the 2C diff resolves that question one way or the other — it can
  only be resolved by flying it. 2D stays genuinely conditional.
- **The milestone is not closeable yet, and the plan itself says so.** The slicing table treats 2D as
  part of the same milestone with a conditional gate, and the plan's effort/value section (`plan.md`
  around line 864) argues *for* deferring 2D's build, not for treating the milestone as already
  closed without a verdict. Recommend the milestone stays open through 2C's sortie: either the
  sortie shows no real need and 2D is formally skipped (a decision, recorded — not silence), or it
  shows a need and 2D gets built. Closing the milestone now would convert "conditional, pending
  evidence" into "done" without the evidence ever arriving.
- **`body-layer/ROADMAP.md` flag for merge-time update** (not edited here, per instructions):
  - The "Cones slice 2B" entry's live-acceptance debt note ("clears on 2C's sortie") should be
    updated once 2C's card is flown — it currently describes 2B's gaze-as-filter behaviour as
    untested against a free-scan baseline, which 2C's sortie is what provides.
  - No "Cones slice 2C" entry exists yet in the roadmap's done-list (only 2A/2A.5 and 2B do) — needs
    one at merge, following the same format, including the live-acceptance debt entry for the sortie
    itself (this is new debt 2C creates, not debt it clears).
  - The milestone-level framing ("Next: 2C ... Then conditionally 2D") under the 2A/2A.5 entry is now
    stale once 2C merges — it should read as "2C done, 2D conditional on its sortie."

## Verdict

**DoD: PASSED** on all mechanical/code-quality/scope/testing/documentation criteria. Acceptance
testing is a separate live-DCS step (see acceptance testing plan and test-card artifact) and is
**not yet performed** — this DoD pass does not claim live verification, per the project's
never-block-merge-on-live-acceptance policy. DO NOT MERGE until the user has flown the card and
responds to the acceptance question, per this task's explicit instruction.
