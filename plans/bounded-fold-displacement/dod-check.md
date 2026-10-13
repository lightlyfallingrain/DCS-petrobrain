# Definition of Done — bounded-fold-displacement (BL-B58 option 2 / BL-B59)

**Verdict scoped to `fix/bl-b59-retention-hysteresis` tip `50428dd`.** If the branch has moved
since, this verdict is stale — re-run against the new tip before merging.

**Worktree mechanics**: this agent's own disposable branch sat at `main` (`c28a6b9`) with zero
unique commits (`git log main..HEAD` empty), while `fix/bl-b59-retention-hysteresis` was checked
out in the user's own feature worktree (`/Users/sg/Code/DCS-petrobrain-b59`), refusing a second
checkout. Repointed via `git checkout -B worktree-agent-adc5368a9e49fcfc2 50428dd`, landing
exactly on the named tip with a clean tree. Same resolution pattern every prior round on this
feature used (`feedback_target_branch_checked_out_elsewhere.md`, already in agent memory).

## Mechanical checks

(`body-layer/`, the only subproject this diff touches — confirmed: `git diff --stat main..HEAD --
audio-adapter` is empty, and every other subproject's files are untouched by this branch's diff.)

| check | result |
|---|---|
| `ruff format --check src tests` | clean, 120 files |
| `ruff check src tests` | clean |
| `mypy src --strict` (run from inside `body-layer/`) | clean, 55 source files |
| `pytest tests -q` | **1704 passed, 4 xfailed** |
| `audio-adapter` (unaffected subproject, checked not assumed) | not re-run this pass — confirmed by diff that no file in that tree changed; the plan/implementation/review logs each independently measured 255 passed / 1 skipped at earlier tips on this same branch |
| `git diff main..HEAD -- '*/pyproject.toml'` | empty — no dependency change, any subproject |
| debug output / TODO / FIXME introduced by this diff | none (`git diff main..HEAD -- body-layer/src \| grep -E '^\+.*(print\(\|TODO\|FIXME\|breakpoint\()'` — no hits) |
| working tree | clean (`git status --porcelain` empty) |
| new files staged | yes — everything in `git diff --stat main..HEAD` is committed, nothing untracked |

The `research/2026-10-05-security-audit.md` ruff-format flag some rounds mention is pre-existing
and outside `src tests` scope — not reproduced here because the check above was scoped to
`src tests`, matching this subproject's own `CLAUDE.md` Commands section.

## Scope & correctness

**Matches the plan.** Four implementation commits (mechanism off → calibration on → accumulator
→ observability) plus a NaN-safety round (one finding, two review iterations to close both
operand gaps) — exactly the staging `plans/bounded-fold-displacement/plan.md` §8 specifies, with
mechanism and calibration kept in separate commits per `body-layer/CLAUDE.md`'s invariant.

**No unplanned scope.** `git diff --stat` touches exactly the files the plan's §7 "Affected
Modules" and the implementation log name: `position_belief.py`, `contacts.py`, `groups.py`
(the trace field only), `STRUCTURE.md`, three test files, plus the plan's own documents and two
ROADMAP entries. Nothing in `belief/callouts.py`, `belief/threat.py`, or any speech/command
surface moved.

**No invariant violated** — checked against `body-layer/CLAUDE.md`'s own list, not assumed:
- No-omniscience: the bound reads only believed state (`growth_rate_mps`, percept timestamps);
  the probes that scored residual error against ground truth are outside the shipped mechanism.
- Mechanism/calibration separation: honoured (Stage 1 wired-off, Stage 2 switched on, separate
  commits).
- `Contact.position`'s single-writer invariant: honoured — `ingest`'s fold branch calls
  `contact.record(percept, ambiguous_fold=True)`, never assigns `.position` directly (Reviewer
  confirmed by reading the docstring and the call site both rounds).
- `BL-B51`'s one-table rule: honoured — `clamp_fold_displacement`'s bound is read through
  `contact_growth_rate_mps`, the one shared resolution; grepped for a second copy, none found
  (Reviewer, round 1).
- No new import cycle / no cross-module omniscience leak in `position_belief.py` — confirmed by
  reading its import list.

**Both pinned invariant tests pass unmodified**: `test_the_eager_cap_still_chains_a_long_infantry_line`
and `test_2c_transcript_fixture_renders_three_lines_not_seven`, both diffed against pre-feature
tips and confirmed byte-identical, both passing by name.

**Does BL-B58 and BL-B59 get closed by one mechanism, honestly?**

- **BL-B58 (absorption)**: already closed by BL-12 Stage 3.5's admission gate (merged earlier).
  This feature's own measurement shows the gate becomes a **no-op** at the k=1 bound in the
  incident that motivated it (63.8 → 155.0 m against the 78.0 m backstop) — the bound fixes the
  absorption at its source, and the gate is retained as a safety net for an uncalibrated table
  rather than because it is still doing the work. `BL-B58`'s own entry already records this
  (Three measurements... banner, added by the Architect pass, confirmed again here by the
  Reviewer's independent probe reruns).
- **BL-B59 (eviction)**: this is the half this feature actually fixes. Measured: 0 membership
  transitions over 60 ticks of repeat folds, versus the unbounded baseline's 12. `GROUP_1` stays
  `[CONTACT_1, CONTACT_2, CONTACT_3]` throughout rather than evicting `CONTACT_2`. **BL-B59's own
  entry file is still marked `#status/open` on disk at this tip** — this is a bookkeeping gap I
  am closing as part of this DoD pass (see Roadmap bookkeeping below), not a defect in the code.

So: yes, one mechanism (the displacement bound) closes both halves, and it is honest to mark
`BL-B59` done now. `BL-B58`'s entry was already closed by the earlier Stage 3.5 round and needed
only a confirming note, not a reopen.

## Testing

- Core logic covered: the clamp's identity branches, the binding case, the NaN-safety guard (both
  operands), the accumulator's `max()` semantics, the real-pipeline incident-2 regression, and the
  admission-gate no-op — each with a dedicated test, and each mutation-tested by the Reviewer
  (disabling the clamp, reverting `max()` to `+=`, removing each NaN guard clause, reverting the
  `as_of_sim` bump) with the expected test failing cleanly every time, then restored and
  re-confirmed green (`shasum` before/after matched on every round).
- Tests are meaningful, not decorative — demonstrated by the mutation testing above, independent
  of the implementer's own claims.
- No existing test broken: +7 net over the pre-feature baseline (1697 → 1704), all additions,
  zero deletions, both pinned invariants unmodified.
- One optional Reviewer refinement not acted on (a second test fixture at a different
  `plausible_speed_mps` class) — correctly judged low-priority by the Reviewer since the bounded
  function is already covered by `BL-B51`'s shared-table invariant elsewhere. Not a gap worth
  blocking on.

## Documentation

- Reviewer findings addressed: **two required fixes** from the "NaN-safety fix close-out" round
  (guard `max_displacement_m` itself; bump `as_of_sim` on hold) were both closed in the
  close-out round and re-reviewed APPROVED. Final verdict: **APPROVED**, no required fixes
  outstanding, full read.
- Non-obvious behaviour explained in code: `position_belief.py`'s module docstring now cross-
  references the "Hold-recovery timing" invariant from the new guard; `fold_displacement_m`'s
  field docstring states it now measures the clamped displacement and tracks a running maximum,
  not a sum.

## Security

- `plans/bounded-fold-displacement/security-review.md`: **APPROVED**. One low-severity, not-
  reachable-today finding (NaN propagation if a future caller reorders the two clamps), with a
  recommended fix — which the implementation round then closed and Review re-approved. No plan-
  review document exists for this feature under its own name because it followed the Security
  deep-analysis step of the change-request loop (`AGENTS.md`'s "A change request from Security...
  re-enters the loop") rather than a fresh Architect→Security(plan)→Implementer sequence; the
  original plan (`plans/group-retention-hysteresis/plan.md`) did receive its own earlier
  Architect pass and this feature is its superseding replacement, decided by the user directly
  rather than through a separate plan-review document. Not a gap — the user's own decision
  (2026-10-13) to choose option 2 over the retention term is the plan-level sign-off here.

## What this DoD pass cannot verify, and the acceptance boundary

**Fixture-only.** Every number above comes from one probe geometry (probe 2's three-infantry-
plus-ZSU scene) replayed through the real pipeline, plus unit tests. No sortie has exercised this
path. Specifically out of reach for any fixture:

- **Whether the bound's one calibration axis (`_PLAUSIBLE_SPEED_MPS`) is actually correct for
  real DCS units.** It is a table of stated assumptions, none measured against real telemetry.
  The plan's own stated, accepted regression — a unit moving at 4× its believed class rate is
  now tracked *worse* than before the fix (104.2 m vs 49.8 m baseline) — is exactly the shape of
  defect only a misclassified fast mover in a real flight would surface. No fixture can produce
  "the project's speed table turned out to be wrong," only a flight can.
- **Whether the fix feels right from the cockpit.** A membership flip stopping and a held
  position no longer drifting are both things the pilot could notice on a sortie trace or in a
  spoken callout, but nothing here has driven that trace through a real flight.
- **The fixtures cannot calibrate a slack-term family at all** (plan §10) — a declared-
  uncertainty-keyed bound (the B2 candidate) is a no-op in every existing fixture, which the plan
  states as a limit of the measurement, not something reasoned past.

## Per-weapon acceptance split — stated as a channel split, not an accuracy split

**Correction applied, not the framing I started with.** The feature's measured result is a
held-position error of **40.0 m at the fold tick (2.29° at 1,000 m, under the naked-eye channel's
own `BEARING_SIGMA_DEG = 3.0`)**, against a baseline of 72–95 m (4.1–5.3°). That number belongs to
the **naked-eye / binocular perception channel** — the one `perception/optics.py` implements
today (`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`).

- **Guns and rockets**: served by this channel. The pilot closes the aiming loop visually, and
  this feature's measured 40 m / 2.29° clears the channel's own noise floor. This feature's work
  is sufficient here.
- **ATGM (9K113) guidance**: **not served by this channel at all, by the weapon's own nature** —
  there is no naked-eye channel for ATGM guidance; the copilot holds the missile sight on target
  for the whole flight. So 40 m is not a shortfall against the ATGM requirement; it is the wrong
  instrument for that question entirely. Improving the naked-eye-derived position further would
  not move this number, because the 9K113 sight is a separate perception channel this project has
  not built.
- **The 9K113 optic does not exist in this codebase today**, confirmed by reading, not inferring:
  `perception/optics.py` declares exactly two optics (`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`) and its
  own docstring states the 9K113 is "deferred entirely"; `belief/groups.py:385`, `perception/
  association.py:91`, `perception/visibility.py:49` all independently say the same thing in their
  own words. This is a hard prerequisite, not a tuning gap — `BL-14` cannot deliver ATGM guidance
  without a 9K113 perception channel, independently of anything this feature does to the
  naked-eye position.

## The known regression — where it is recorded, and whether it needs its own entry

**The regression**: a unit moving at 4× its believed class rate (a misclassified fast mover) is
now tracked at 104.2 m error versus the unbounded baseline's 49.8 m at the same tick (plan §2b).
Accepted, documented in the plan's §10 Risks as a stated (not resolved) risk, with its mitigation
named (Stage 3.5's gate remains load-bearing at a 3× looser bound, and the classification fold
itself should correct a misclassification over time).

**It is recorded where someone will find it** — plan §2b and §10, and `BL-B58`'s own recheck
banner references the Stage 3.5 gate's continued load-bearing role at the wider bound. But it had
no roadmap entry of its own, and this project's convention is that a measured, named defect gets
one (see `BL-B57`, filed for a comparably narrow, comparably low-probability gap in the same
speed table). **Filed as `BL-B60`** as part of this DoD pass (see Roadmap bookkeeping) — it is a
genuine, measured, open risk with a clear reproduction and no fix yet, which is exactly this
project's bar for a backlog entry rather than a footnote.

## Milestone-completion question

**Does this change what comes next, or invalidate a downstream assumption?** The plan's own §11
already answers this and I confirm it holds at this tip:

1. **`BL-14` (attack run)** narrows rather than unblocks. After this bound, a held per-unit
   position is accurate within the naked-eye channel's own noise for guns/rockets. *Completeness*
   (two real units with no record at all, before and after) remains unfixed and is a different
   mechanism (fold-vs-split, plan §4, Decision 1). **A third thing now bears on `BL-14` that
   landed mid-pass and is not yet reflected in any plan**: the group-model/attention-tiers
   direction (`docs/group-model-attention-tiers`, unmerged) reframes the whole question as
   "resolution depends on attention tier," which changes what "does BL-14 need per-unit records"
   even means — it is not a fixed requirement but a function of whether a unit is in the high
   attention tier (watched/targeted/asked-about). That direction is not on `main` yet and this
   feature does not depend on it, but whoever plans `BL-14` next should read it before assuming
   this plan's Decision 1 framing is still the whole picture.
2. **`BL-B59` is closed by this plan** rather than by a retention term, as already recorded on its
   own entry's banner. **`BL-B50`'s recheck condition becomes dischargeable** — the 2C fixture is
   now stable under repeat folds (0 transitions vs 12), which is exactly the condition that entry
   named. **`BL-B58`'s recheck note survives**: the accumulator still never resets to zero, now at
   a bounded rate (`max()`, Stage 3) rather than an unbounded sum.
3. **`BL-14`'s ATGM half has a hard, independent prerequisite** — the 9K113 optic channel does
   not exist. This is not new information this feature discovered, but it is directly relevant to
   anyone reading this feature's 40 m number and assuming it says something about missile
   guidance. Worth stating plainly rather than letting the number travel without its channel
   attached.

## Verdict

**PASS.** Mechanical checks clean, scope matches the plan, both named halves of the defect
(BL-B58 absorption, BL-B59 eviction) are closed by the one mechanism, security and reviewer
sign-off are both clean with required fixes addressed and re-reviewed, and the acceptance
boundary (fixture-only, uncalibrated speed table, no sortie) is stated rather than implied away.

Outstanding before this can be called *flown*: a real sortie exercising a repeatedly-folded group
and a stationary target the fold would otherwise have drifted.

## Acceptance test card

Published: https://claude.ai/artifact/NxSFmKNdjxvGG2JtnVKvUC — branch `fix/bl-b59-retention-
hysteresis` (already checked out at `/Users/sg/Code/DCS-petrobrain-b59`), tip `50428dd`. Covers:
group membership stability under repeat folds, stationary-member position holding, how to read
`fold_budgets` on `--group-trace` output and its one honest limit (shows the clamped value, not
whether the clamp fired), the accepted `BL-B60` fast-mover trade-off to watch for rather than
expect fixed, and the guns/rockets-vs-ATGM channel split stated plainly so no one reads the 40 m
figure as a missile-guidance claim.

The logger invocation on the card was verified against this build's own argument parser
(`python -m logger --help`, and a run with a missing world-model store to confirm every flag is
accepted and `--group-trace` requires `--console`/`--crew-text` as documented) — not against a
live DCS session, which this pass has no access to. Marked `UNVERIFIED on real DCS` on the card
itself.
