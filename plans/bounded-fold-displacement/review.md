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
