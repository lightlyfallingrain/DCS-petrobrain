### Review Summary

Reviewed `BL-B58` option 2 / `BL-B59` (bounded fold displacement) on `fix/bl-b59-retention-hysteresis`
at `d2cfa4b`, against `plans/bounded-fold-displacement/plan.md` and the related plans/ROADMAP
entries it supersedes or closes. Seven commits (`8042c77`..`d2cfa4b`), plus the plan commit
`da15972` that carries Stage 0's roadmap bookkeeping.

The mechanism is exactly what the plan specifies: a third caller-invoked post-fusion clamp
(`position_belief.clamp_fold_displacement`), applied from `Contact.record`'s new `ambiguous_fold`
keyword, bounding the fuse's own mean-displacement at `plausible_speed_mps(class) × elapsed` after
`clamp_to_detection_envelope`. `ingest`'s fold branch is the one call site that sets
`ambiguous_fold=True`; every other call site is unchanged. The accumulator moved from `+=` to
`max()` in its own commit (Stage 3), and `fold_budgets` rides on the group trace (Stage 4).

I independently reproduced every number in the plan's acceptance tables by running the scratchpad
probes against a snapshot of the pre-implementation commit (`da15972`, where they were written to
run — they monkeypatch `Contact.record`, which only works before the real keyword existed), and by
running `clamp_plugin.py` against the real suite. I also mutated the merged code directly: disabled
`clamp_fold_displacement` (identity) and reverted `max()` to `+=`, confirming each change is caught
by a specific test, then reverted both mutations (`git status --porcelain` clean throughout).

No required fixes. Two optional notes below.

### Required Fixes

None.

### Optional Refinements

- **`tests/test_contacts.py`'s mutation coverage is good but narrow to one geometry.** The
  dedicated clamp test (`test_fold_displacement_m_is_bounded_by_the_contacts_own_plausible_speed`)
  and the three-fold accumulator test both bite cleanly under mutation (verified below), but both
  use the same D/E/F three-contact fixture shape. A second fixture at a different class
  (`OP_ARMORED` or `OP_TRUCK`, which have different `plausible_speed_mps` rows) would guard against
  a future change to `contact_growth_rate_mps`'s resolution order silently changing which rate gets
  read. Low priority — the function being bounded is already covered by the shared-table
  invariant (`BL-B51`) elsewhere. (Optional.)
- **The plan's own Decision 1 (per-unit records for `BL-14`) and Decision 2 (zero-elapsed fold
  moves nothing) are both recommended-not-yet-ratified in the plan text.** Worth a one-line
  confirmation from the user before `BL-14` planning starts, since the plan explicitly flags
  Decision 1 as "the one decision that should not wait." Not a defect in this branch — out of this
  review's scope per the orchestrator's instructions (a separate `/explore` is open on `BL-14`) —
  flagging only so it isn't lost. (Optional, not a blocker.)

### Verification

**Mechanical checks** (`body-layer`, this worktree's checkout of `d2cfa4b`):
- `ruff format --check src tests` — clean (120 files).
- `ruff check src tests` — clean.
- `mypy src --strict` — clean, 55 source files.
- `pytest tests -q` — **1702 passed, 4 xfailed** (confirmed; baseline at `da15972` measured
  separately at **1697 passed, 4 xfailed**, so +5 net, matching the two dedicated new tests in
  `test_contacts.py` plus `test_groups.py`'s two additions plus `test_callouts.py`'s one addition).
- `audio-adapter`: `pytest tests -q` — **255 passed, 1 skipped**, confirmed myself (not just taken
  on the implementer's word).

**Stage 1 behaviour-neutrality** (the staging argument's load-bearing claim): checked out `8042c77`
in isolation (`git archive` snapshot, not a live checkout — the branch is held in a user worktree)
and ran the real suite from inside that snapshot's `body-layer/`: **1697 passed, 4 xfailed**,
identical to the `da15972` baseline. The mechanism is wired but genuinely unreachable at Stage 1, as
claimed — no silent identity-that-happens-to-be-reachable defect.

**Scratchpad probes, run against the pre-implementation snapshot** (`da15972`, where they are
designed to run — they install their own monkeypatch of `Contact.record`/
`_fold_target_for_ambiguous_candidates`, which only works before the real `ambiguous_fold` keyword
exists; running them against `d2cfa4b` directly raises `TypeError` on the keyword collision, as
expected, not a defect):

- `probe_o2_bound.py` (§2a): reproduced the full table exactly — baseline 132.7/143.3 m, 12
  transitions; **B1′ 40.0/40.0 m at t=20, 0 transitions, 160.0 m at t=80**; B1 (hold covariance)
  40.0 m but 10 transitions and 208.2 m by t=80; B2 (test-5 slack) **552.1 m bound, no-op**; B3a/B3b
  (`radius_m()` family) **300.0/150.0 m bound, no-op, prior radius 300.0 m confirmed**; B4a/B4b
  (absolute 50/25 m) retained but residual grows post-bound (255.9 / 200.0 m); B5 (bound 0) 0.0 m
  residual at the fold tick, confirming it is a scene artifact, not a mechanism merit.
- `probe_o2_motion.py` (§2b, the discriminator): reproduced the moving-pair property exactly — at
  2.0 m/s (= class bound) B1′ is **byte-identical to baseline at every sample** (5.0/8.9/11.7/12.5
  m), while B5 (bound 0) grows unbounded (10.0/20.0/40.0/80.0 m, "freezes"). At 8.0 m/s (4× the
  class bound, the stated regression) B1′ reaches **104.2 m vs baseline's 49.8 m at t=40** — the
  plan's one measured regression, confirmed as stated, not worse than claimed.
- `probe_o2_accuracy.py` (§3, §4): reproduced the six-unit table — baseline 72.1/94.9 m (U1/U3),
  k=1 **40.0 m / 2.29° and 2.22°** at the fold tick, 46.8 m by t=80 for U1. Confirmed **2 real
  units (U5/U6) have no record at all, before or after, at every bound tested**, and B6 ("found
  instead of fold") reaches 0.0 m per-unit error at the cost of **18 contacts for 6 real units at
  t=80** (82 in the separate moving-pair scene) — the overcount runaway the plan warns against.
- `probe_o2_stage35.py` (§2d, §5): reproduced the gate-goes-quiet table exactly — k=1 roster
  `[1,2,3]` with the gate neutralised (same roster gate-on/off), absorbing edge 63.8→155.0 m against
  the 78.0 m backstop; k=3 edge returns to 75.5 m, gate load-bearing again.
- `probe_o2_motion_keyed.py` (§6): reproduced — gate candidates stay **3** across motion-None,
  motion-keyed-but-still-None, and declared-stopped (0.0 m/s) variants; `BL-B24`'s 17 m pair still
  passes both gates at 0.0 m/s growth. Confirms the motion-keyed direction does not invalidate this
  bound and does not (yet) reduce fold frequency or shrink `BL-B24`, as the plan states.
- `clamp_plugin.py` suite run (§5): `PB_CLAMP_K=off` → **1697 passed, 4 xfailed**;
  `PB_CLAMP_K=1.0` → **1 failed, 1696 passed, 4 xfailed**, the one failure being exactly
  `test_fold_displacement_m_is_written_on_a_fold_and_reset_on_an_unambiguous_record`, as claimed.

**Mutation checks, run against the merged code at `d2cfa4b` directly** (reverted after, working
tree clean throughout — confirmed by `git status --porcelain` before and after):

- Disabled `clamp_fold_displacement` (forced early return of `fused` unconditionally). Result:
  `test_fold_displacement_m_is_bounded_by_the_contacts_own_plausible_speed` **fails**
  (`5.000124996874888 == 1.5 ± 1e-6` → assertion fails), the other two
  `fold_displacement` tests in that file still pass (they deliberately stay clear of the bound, per
  their own docstrings). The dedicated bound test is the one that bites, as it should — the
  rewritten provenance test does **not** bite this particular mutation, which is consistent with
  its own stated design (its geometry sits comfortably under a 150 m bound at non-zero elapsed
  time) rather than a coverage gap, since the dedicated test above covers the same mechanism at a
  tighter margin.
- Reverted `max()` to `+=` in `ContactStore.ingest`'s fold branch. Result: **both**
  `test_fold_displacement_m_is_written_on_a_fold_and_reset_on_an_unambiguous_record` (the rewritten
  provenance test — its second-fold assertion compares against `max(...)`, which diverges from
  `+=`) and `test_fold_displacement_m_tracks_the_worst_single_fold_not_an_accumulated_sum` fail
  cleanly (`15.95... != 9.95...`). Both tests are real evidence for `max()`, not decorative.

**Pinned invariants, read not just run:**
`test_the_eager_cap_still_chains_a_long_infantry_line` (`test_groups.py`) and
`test_2c_transcript_fixture_renders_three_lines_not_seven` (`test_callouts.py`) — diffed both files
and confirmed neither function's body changed; only new tests were added around them.

**Invariant reads:**
- `Contact.position`'s field docstring (`contacts.py:374-378`) still states `record`/`from_percept`
  are the only writers, both via `fold_position` — `ingest`'s fold branch calls
  `contact.record(percept, ambiguous_fold=True)`, never assigns `.position` directly.
- `fold_position`'s and `PositionEstimate`'s docstrings in `position_belief.py` still draw the
  boundary the plan cites twice (the detection envelope and now the fold bound are both "a caller
  concern", never something the fuse itself resolves). `clamp_fold_displacement` takes a bare
  `max_displacement_m: float | None` and never imports or references `belief.contacts` or
  `association_over_time` — no-omniscience and no new import cycle, confirmed by reading the
  module's import list.
- `growth_rate_mps` is resolved exactly once per `record` call via `contact_growth_rate_mps`
  (`association_over_time.py:333`) and reused for both the envelope-clamp's inflation and the new
  fold bound — grepped for `_PLAUSIBLE_SPEED_MPS` and `plausible_speed_mps` across `src/`: the only
  definition is in `position_belief.py`; no second copy exists anywhere the bound reads from.
- `plans/group-retention-hysteresis/plan.md` §5 carries `> **Decision 1 REVISED — 2026-10-13. §5
  is SUPERSEDED and was not implemented.**` — superseded in place, not deleted, §2's measurements
  intact and cited as justification.

### Verdict

APPROVED

### Review Confidence

Full read — plan, all affected source files, full diff, both pinned-invariant tests read in full,
all five scratchpad probes run and their output compared line-by-line against the plan's tables,
the suite run at Stage 1 in isolation, and two independent mutations applied directly to the merged
code and reverted cleanly.

## Round: NaN-safety fix close-out (2026-10-13)

Reviewed `3dfe922` ("Make clamp_fold_displacement NaN-safe on its own terms"), the single commit
closing the one finding from `security-review.md`. Scope: `body-layer/src/belief/
position_belief.py` (the new `math.isfinite` guard in `clamp_fold_displacement` plus the two
docstring additions), `body-layer/tests/test_position_belief.py` (one new test), and
`plans/bounded-fold-displacement/implementation.md`'s round entry.

**Mutation, run myself** (`Edit`, not a heredoc, per worktree rules): removed the two-line guard
(`if not math.isfinite(fused.x) or not math.isfinite(fused.z): return prior`).
`test_clamp_fold_displacement_holds_prior_on_nan_mean` fails exactly as the commit claims —
`result.x == nan` where `prior.x == 100.0` was expected. Restored via `Edit`; `shasum -a 256`
before and after the mutate/restore cycle match
(`2e0153acab774084d6397facf1c00a3db3d151ab382815ac1f4d7807a77404cd`), and `git diff --stat` on the
restored tree is empty.

**The guard closes two of three doors, not all three — the third is the one the orchestrator's
brief specifically asked me to look for.** Checked by direct probe against the merged code
(`PYTHONPATH=src:../world-model/src <venv>/python3 -c '...'`), not by reading alone:

- `fused.x`/`fused.z` non-finite: guarded, confirmed held (`result is prior`).
- **`max_displacement_m` itself non-finite: *not* guarded.** `clamp_fold_displacement(fused=
  PositionEstimate(x=150.0, z=300.0, …), prior=PositionEstimate(x=100.0, z=200.0, …),
  max_displacement_m=math.nan)` returns `x=nan, z=nan` — probed directly, reproduces the *exact*
  mechanism the security review described for `fused`'s mean (`displacement_m <= max_displacement_m`
  is `False` for a NaN bound too, `displacement_m > 0.0` is also `False`, `scale = 0.0`, `dx * 0.0 ==
  NaN` when `max_displacement_m` itself was NaN — the multiplication is against `scale`, and `scale`
  inherits the NaN here, not `dx`). The guard's own new docstring paragraph ("Non-finite `fused`
  mean, by design, not by accident") is accurate about what it covers but reads as more complete
  than it is — it does not mention the bound is a second, unguarded path to the identical
  corruption. **Reachability today is low, by the same reasoning the security review already
  applied to the original finding**: `max_displacement_m` is `growth_rate_mps * max(0.0, elapsed)`
  in the one real caller (`Contact.record`), and `growth_rate_mps` resolves through
  `contact_growth_rate_mps` → `object_model.profile_for` → `plausible_speed_mps`, a table lookup
  that does not currently produce NaN/inf under any believed classification. Not reachable, same as
  the original finding — but this round's whole point was to make the function's safety claim true
  "on its own terms rather than borrowed from caller ordering," and the claim as shipped is still
  partly borrowed from `max_displacement_m`'s callers never producing a bad bound.
- `prior.x`/`prior.z` non-finite: not a new corruption path — if `prior` itself already carries a
  non-finite mean, every branch (guarded or not) just continues propagating what was already there,
  which is a pre-existing-garbage-in case, not something this commit's guard could or should fix.

**The hold branch does not bump `as_of_sim`, and the module's own docstring says it must.** The
guard `return`s `prior` by bare identity, so `as_of_sim` stays at whatever it was before this poll
— probed directly: with `prior.as_of_sim=0.0` and `fused.as_of_sim=1.0`, the guard's result carries
`as_of_sim=0.0`, not `1.0`. This is not a style nit: the module's own header docstring states the
"Hold-recovery timing" invariant in so many words — *"`as_of_sim` ('this estimate is current as of
this sim-time,' bumped on every poll including a hold, since the belief is still the best current
answer even when unchanged)"* — and names the exact prior incident this guards against (the
2026-09-25 security addendum, where a *different* `as_of_sim`-handling bug in these same two
functions' siblings caused hold-recovery time to scale as `1 / poll_interval_s`, measured ~47s
becoming ~934s). `clamp_to_detection_envelope`'s own hold branch, three lines above this one in the
same file, gets this right — it constructs a new `PositionEstimate` with `as_of_sim=fused.as_of_sim`
even though it (like this guard) cannot re-fuse. This guard's docstring addition explains why it
cannot re-inflate `prior.covariance` (no `observer`/`growth_rate_mps` available) but that reasoning
only covers the covariance field — `fused.as_of_sim` is already a parameter in scope, needs no
growth rate, and bumping it costs nothing. **Read as two claims**: "this function has no
`observer`/`growth_rate_mps` of its own" (true) "so holding the prior exactly as given is the whole
of this guard" (does not follow for `as_of_sim`, only for `covariance`). Not reachable today either
— `grep -rn "as_of_sim" src/` outside `position_belief.py` turns up nothing, so no current consumer
reads a stale value — but it is latent in exactly the shape the project has already been burned by
once in this file.

Both gaps are one or two lines each and sit inside the function this commit already modified — not
scope creep, and not something I am asking to re-open the original low-severity/not-reachable
judgement call. They are about whether *this* commit actually delivers what its own message claims
("NaN-safe on its own terms," not borrowed). The `as_of_sim` test fix would need
`test_clamp_fold_displacement_holds_prior_on_nan_mean` reworked from `assert result is prior` to a
field-equality assertion (mirroring `test_clamp_to_detection_envelope_*`'s own pattern a few hundred
lines up in the same file), since an `as_of_sim`-bumped hold is no longer identity-equal to `prior`.

Everything else holds: both docstring paragraphs are otherwise accurate (the
`clamp_to_detection_envelope` addition's "incidental, not a contract" framing is correct and well
placed); scope is exactly the three files claimed, nothing else moved
(`tests/test_groups.py::test_the_eager_cap_still_chains_a_long_infantry_line` unmodified, diffed
against `de6aacf` — empty; `tests/test_callouts.py::test_2c_transcript_fixture_renders_three_lines_
not_seven` passes by name; `audio-adapter` diff against `de6aacf` empty). Checks: `ruff format
--check`/`ruff check` clean (120 files), `mypy --strict` clean (55 files), `pytest -q` **1703
passed / 4 xfailed** (was 1702/4 at `de6aacf`, exactly +1). `audio-adapter`: 255 passed, 1 skipped.

### Required Fixes

- **`clamp_fold_displacement`'s new guard must also treat a non-finite `max_displacement_m` as the
  hold case** (`body-layer/src/belief/position_belief.py`, the guard currently at `if not
  math.isfinite(fused.x) or not math.isfinite(fused.z): return prior`) — add `or not
  math.isfinite(max_displacement_m)` to the condition (safe to call unconditionally at that point:
  the `max_displacement_m is None` branch above already returns first). Without it, a non-finite
  bound reaches the exact same `dx * scale == NaN` corruption the commit's own message describes,
  through `scale` inheriting the NaN rather than `dx`. Update the docstring paragraph to say so.
- **The hold branch must bump `as_of_sim` to `fused.as_of_sim`**, matching
  `clamp_to_detection_envelope`'s sibling hold branch and the module's own "Hold-recovery timing"
  invariant — return a new `PositionEstimate(x=prior.x, z=prior.z, covariance=prior.covariance,
  as_of_sim=fused.as_of_sim, fused_at_sim=prior.fused_at_sim, fused_covariance=prior.
  fused_covariance)` rather than bare `prior`. Rework
  `test_clamp_fold_displacement_holds_prior_on_nan_mean`'s `assert result is prior` into a
  field-by-field assertion (`result.x == prior.x`, `result.z == prior.z`, `result.as_of_sim ==
  fused.as_of_sim`, `result.fused_at_sim == prior.fused_at_sim`), since the corrected hold is no
  longer identity-equal to `prior`.

### Optional Refinements

- None — both findings above are cheap, in-scope, and directly bear on correctness, so neither
  reads as a nice-to-have.

### Verdict

**NEEDS REVISION.** Both required fixes are small (each a one-line condition or constructor change
plus a docstring/test touch-up) and stay inside `clamp_fold_displacement` — this does not reopen
the broader feature or the original security finding's own low-severity judgement, only whether
this specific commit's claim to have closed it fully is accurate. Re-enters Implementer → Reviewer
(this round) → DoD per `AGENTS.md`'s change-request loop.

### Review Confidence

Full read of the commit's diff and both touched docstrings in full module context, plus three
direct probes against the merged code (the documented mutation test, a non-finite-bound probe, and
an `as_of_sim`-staleness probe) rather than reasoning from the docstring text alone.

## Round: close-out of both required fixes (2026-10-13)

Reviewed `2a9a676` ("Close both NaN-safety gaps the review found in clamp_fold_displacement"), the
single commit addressing both required fixes from the round above. Scope: `body-layer/src/belief/
position_belief.py`, `body-layer/tests/test_position_belief.py`, `plans/bounded-fold-displacement/
implementation.md`.

**Worktree mechanics**: this agent's own disposable branch (`worktree-agent-a0291a60857cf9c32`) sat
at `main` (`c28a6b9`) with zero unique commits vs. `main`, while `fix/bl-b59-retention-hysteresis`
was checked out in the user's own worktree (`/Users/sg/Code/DCS-petrobrain-b59`), refusing a second
checkout. Repointed via `git checkout -B worktree-agent-a0291a60857cf9c32 2a9a676`, landing exactly
on the named tip with a clean tree.

**Is the operand set now closed?** Re-ran the same enumeration the prior round used. The guard now
reads `not math.isfinite(fused.x) or not math.isfinite(fused.z) or not math.isfinite(
max_displacement_m)`, one combined condition, one hold branch, no separate path left returning bare
`prior`. Checked every operand feeding the `dx`/`dz`/`displacement_m`/`scale` arithmetic below the
guard:
- `fused.x`/`fused.z`: guarded (unchanged from the previous fix).
- `max_displacement_m`: now guarded — the gap this round closes. `max_displacement_m is None`
  returns first, so `math.isfinite(max_displacement_m)` is never reached with `None` — confirmed by
  reading the guard order, not assumed.
- `prior.x`/`prior.z`: **not guarded, and this is unchanged from the prior round's own finding, not
  a new gap.** If `prior` itself already carries a non-finite mean, every branch (guarded or not)
  propagates what was already there — a pre-existing-garbage-in case this function's guard was
  never meant to fix, since `prior` is this module's own prior output and finite by induction from
  the founding look onward. Nothing in this round's diff touches that boundary.
- Covariance fields (`xx`/`zz`/`xz`): not computed through this clamp's `dx * scale` arithmetic at
  all — the ordinary-fuse branch passes `fused.covariance`/`fused.fused_covariance` straight
  through unchanged, and the hold branch passes `prior.covariance`/`prior.fused_covariance`
  straight through unchanged. Neither is derived arithmetic this guard needs to sanitise.

**No third gap. The set is closed for the two operands this function's own arithmetic can corrupt
(`fused`'s mean, `max_displacement_m`); the `prior`-already-garbage case was already out of scope
last round and stays out of scope this round.**

**The hold branch's field set, checked against this function specifically, not copied blind from
its sibling.** `clamp_to_detection_envelope`'s hold branch inflates covariance via `_inflated_
since_last_fuse(prior, fused.as_of_sim, growth_rate_mps)`, because that function has an `observer`/
`growth_rate_mps` to do so with. `clamp_fold_displacement` has neither — its signature is `(fused,
prior, max_displacement_m)`, confirmed by reading it — so `covariance=prior.covariance` unchanged
is correct *for this function*, not a shortcut. `fused_at_sim=prior.fused_at_sim` (held, not
bumped) and `as_of_sim=fused.as_of_sim` (bumped) is the right split: traced the one real caller
(`Contact.record`, `contacts.py:586-588`) — `max_displacement_m = growth_rate_mps * max(0.0,
percept.t_sim - prior_position.fused_at_sim)`, where `prior_position` is `self.position` *before*
this fold. Holding `fused_at_sim` at the prior's value means a run of consecutive holds keeps
`fused_at_sim` anchored at the last genuine fuse, so the bound (`max_displacement_m`) keeps growing
poll over poll exactly as the module's "Hold-recovery timing" invariant intends — a repeated hold
does not reset the clock on itself. Bumping `fused_at_sim` on a hold (the wrong field to bump)
would have frozen the bound at whatever it was on the first hold, defeating the mechanism. This is
the one place this round's fix could have silently reintroduced the sibling defect
`clamp_to_detection_envelope`'s hold branch was itself hardened against in `plans/
position-belief-runaway/debug.md` — it did not.

**"Both hold branches construct a fresh `PositionEstimate`"** reads correctly as "both finiteness
operands (`fused`'s mean, `max_displacement_m`) share the one hold branch, which now constructs,"
not as two separate branches — there is exactly one `if`/`return` for the finiteness guard, and it
is the only place in this function that used to return bare `prior`. No duplicate or missed path.

**Both mutations reproduced myself** (`Edit`, not a heredoc, per worktree rules):
- Removed the `or not math.isfinite(max_displacement_m)` clause.
  `test_clamp_fold_displacement_holds_prior_on_nan_max_displacement` failed exactly as claimed —
  `result.x == nan` where `100.0` was expected (`assert nan == 100.0`). Restored via `Edit`;
  `git diff --stat`/`git status --porcelain` on the restored tree both empty.
- Reverted both finiteness-guard branches' `return PositionEstimate(...)` to bare `return prior`
  (there is only one such branch, so this is one edit, not two). Both
  `test_clamp_fold_displacement_holds_prior_on_nan_mean` and
  `test_clamp_fold_displacement_holds_prior_on_nan_max_displacement` failed on
  `result.as_of_sim == fused.as_of_sim` (`0.0 == 1.0`), exactly the invariant this fix is about.
  Restored via `Edit`; diff/status both empty again.

**The reworked test.** `test_clamp_fold_displacement_holds_prior_on_nan_mean`'s old `assert result
is prior` became six field assertions (`x`, `z`, `covariance`, `as_of_sim`, `fused_at_sim`,
`fused_covariance`) — a strict superset of what identity implicitly guaranteed, not a narrower
check. `as_of_sim` is asserted against `fused.as_of_sim` (`1.0`), which differs from `prior.
as_of_sim` (`0.0`) in the fixture, so the assertion exercises the value actually *advancing*, not
merely existing. The new `test_clamp_fold_displacement_holds_prior_on_nan_max_displacement` test
mirrors the same six-field pattern for the operand this round adds.

**Scope.** `git diff 7f078f2 -- body-layer/tests/test_groups.py body-layer/tests/test_callouts.py`
is empty — `test_the_eager_cap_still_chains_a_long_infantry_line` and
`test_2c_transcript_fixture_renders_three_lines_not_seven` are both unmodified, and both pass by
name. `git diff 7f078f2 -- audio-adapter` is empty — that subproject untouched. Nothing outside the
three files the commit claims moved.

**Checks, run myself**: `ruff format --check` clean except the pre-existing `research/
2026-10-05-security-audit.md` flag (unrelated to this round, confirmed present before and after);
`ruff check` clean (all checks passed); `mypy src --strict` clean, 55 source files; `pytest -q`
**1704 passed / 4 xfailed** (both before mutation and after restore — identical both times).
`audio-adapter`: **255 passed / 1 skipped**.

### Required Fixes

None.

### Optional Refinements

None.

### Verdict

**APPROVED.**

### Review Confidence

Full read — both fixed docstring paragraphs in full module context, the sibling hold branch
(`clamp_to_detection_envelope`) compared field-by-field rather than assumed parallel, the one real
caller (`Contact.record`) traced to confirm the `fused_at_sim`-held/`as_of_sim`-bumped split
actually serves the "Hold-recovery timing" invariant rather than merely matching its sibling's
shape, both mutations reproduced directly against the merged code and cleanly restored, and the
full test/lint/type suite for both touched subprojects run and read.
