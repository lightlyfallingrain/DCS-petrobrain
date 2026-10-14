# Definition of Done — `collapse(group, depth)`, Stages 1–4

**Scoped to tip `3cbfa8214a7eed83b533a7da6cb9e1dfe2ac62cb` on `feature/group-collapse`.** If the
branch has moved since this was written, this verdict is stale for anything past that sha.

## Address

Worktree HEAD at dispatch (`f25c57c5a00cc6a75266e0f85c680792abf7aa10`) was a strict ancestor of the
named tip on a clean tree. Fast-forwarded with `git merge --ff-only 3cbfa82...`; `git rev-parse
HEAD` confirmed `3cbfa8214a7eed83b533a7da6cb9e1dfe2ac62cb` afterward. All named input documents
present and read: `plans/group-collapse/plan.md`, `implementation.md`, `review.md`,
`performance-review.md`, `security-review.md`,
`docs/acceptance/2026-10-13-group-model-and-attention-tiers.md`, `body-layer/ROADMAP/BL-B61.md`.

## Checks run myself

From inside `body-layer/`, cwd kept in this worktree, binaries borrowed from the main checkout's
`.venv` by absolute path (this worktree's own `.venv` has no `ruff`/`mypy`/`pytest` installed —
confirmed before running anything). Confirmed resolution to **this worktree's own `src`**, not the
main checkout's, by an import-path check from this tree's own file (`belief.__file__` resolved
under `.claude/worktrees/agent-af9344bead5dcde48/body-layer/src/belief/__init__.py`).

```
ruff format --check src tests   -> 124 files already formatted
ruff check src tests            -> All checks passed!
mypy src                        -> Success: no issues found in 57 source files
pytest                          -> 1748 passed, 4 xfailed
```

Matches the expected count exactly. **Diff scope checked against `f25c57c` (the branch point):**
`git diff --name-only f25c57c..HEAD` touches only `body-layer/` (src, tests, docs/STRUCTURE.md,
ROADMAP entries), `plans/group-collapse/`, and `.claude/agent-memory/`. No other subproject's files
appear in the diff, so no second subproject gate is owed.

## Clean tree

`git status --porcelain` was empty before this report's own edits began; staged after.

## Required fixes closed in code, not just in documents

- **Reviewer's two required fixes** (STRUCTURE.md staleness describing Stage 3 as "attempted and
  reverted" when it had in fact landed; the untested `OP_GROUPSOMETHING`-folds-to-aggregate wording
  change) — both closed at `ed50840`, confirmed by the Reviewer's own **independent mutation**
  (flipped `_subclass_label`'s fallback, reran the new pinning test, watched it fail for the stated
  reason, restored, confirmed checksum match), not merely re-read. I did not re-run that mutation a
  third time myself — the Reviewer's confirmation pass already did it from source, and redoing it
  here would be re-verifying the Reviewer's own verification rather than the code.
- **Security's one finding** (`units_hi` can propagate `math.inf`) was explicitly **not** required
  — Security's own verdict was APPROVED with the finding presented per the risk-communication
  format, recommending option (C) as non-blocking. Option (C) (a docstring note, no code change)
  was taken: confirmed present at `body-layer/src/belief/group_view.py:158-163`
  ("**This can legitimately be `math.inf`, and is deliberately not guarded here.**").
- **The plan's own arithmetic correction** (push-path cost understated 5–47x) is struck and
  corrected in place in `plan.md` §1, not silently replaced — confirmed by reading the correction
  block; the conclusion ("depth is affordable on the push path") is unchanged at the corrected
  figure.

## Scope & correctness

- Matches the plan: signature, `CONTACT` naming (not `UNIT`, per the user's settled decision),
  cardinality as an interval (never `len(members)`), canonical sort at every level, the flat
  `composition` tuple surviving unchanged as the match key, `air_defence_composition` surviving
  unchanged, the FOV/mask gate reading remembered observability bookkeeping rather than a second
  mask computation, Stage 4 sharing the level-1 table rather than inventing a second one.
- **No unplanned scope.** The one behaviour change beyond a pure re-expression — the
  `OP_GROUPSOMETHING`-in-a-mixed-clause wording fold — was identified, reasoned about, and
  deliberately kept by the Reviewer (not silently introduced), and is now pinned by a test.
- **No invariant violated.** No-omniscience: `group_view.py` imports nothing from `perception/`
  (confirmed by the Reviewer's grep, independently re-checked by Security's deep analysis); the
  FOV/mask gate is a read of bookkeeping, not a second mask computation, matching Decision 6's
  "cost pruning, not content filtering" reading. `Contact.last_class_raw`/`.classification` dual
  field untouched. Classification `level` monotonicity untouched.
- `git status --porcelain` clean — all files from the diff are committed, none staged-but-uncommitted.

## Testing

1748 passed / 4 xfailed, up from the pre-feature baseline with new tests added
(`test_group_view.py`, new cases in `test_speech.py`/`test_groups.py`/`test_tools.py`). The
Reviewer independently mutated two of the highest-risk claims from source rather than trusting
`implementation.md`'s own mutation table; the confirmation pass independently mutated the pinning
test's own target. No existing assertion's expected value was altered by the fix commits
(`ed50840` is a pure addition, confirmed by diff).

## Documentation

- Reviewer findings addressed: both required fixes closed and independently confirmed (above).
- `STRUCTURE.md`'s `group_view.py` entry now describes the landed Stage 3 state accurately.
- Plan's own arithmetic correction recorded in place, not silently fixed.

## Security

- `security-plan-review.md` does not exist for this feature as a separate file — this feature's
  plan review and deep analysis both appear inside `security-review.md` as the project's current
  single-security-pass-per-feature cadence (root `CLAUDE.md`, "Agents": Security runs once per
  whole feature, immediately before DoD, not as separate plan-review/deep-analysis documents for
  every feature). `security-review.md`: **APPROVED**.

---

## This feature is NOT user-flyable — stated plainly, not a gap

Nothing the pilot hears changes, with exactly one exception: an `OP_GROUPSOMETHING`-class member
inside a group's *mixed* composition clause now folds into the undifferentiated aggregate
(`"something"`/`"N contacts"`) rather than saying `"group"` — reviewed, judged acceptable, and
pinned by a test so a sortie is not the only thing that could catch a regression on it.
`render_contact_report`'s single-contact path still says `"group"`, deliberately, untouched.

Stages 1–2 are a derivation plus an inspectable `tree` key (no speech consumer). Stage 3 is a
behaviour-preserving re-expression of an existing speech clause. Stage 4 is a behaviour-identical
matcher share, confirmed by mutation. **The motivating consumers — "describe group", "what armor
is there", "where's that Shilka" — are Part 3's high tier and are unbuilt.** There is no acceptance
card and no sortie request for this reason: a flight cannot exercise a seam that produces no
different audible output, and manufacturing a flight test for it would test nothing real.

**What is worth five minutes of inspection, if any:** `--console show <id>` on a group contact now
returns a `tree` key. Command, run from `body-layer/` with a loaded console session:

```
show <group-contact-id>
```

UNVERIFIED by me against a live session — this needs a running `--console` poll loop (DCS or
replay), which this worktree cannot start. If inspecting it, look for a `tree` field nested under
the group's facts, shaped as `{GROUP: {...}, CLASS: {...}, ...}` keyed by `CollapseDepth`. Not
blocking — this is an optional five-minute look, not a required acceptance step.

## Milestone completion question

**Yes, this changes what the next milestone should be, in two ways** — recorded on the owning
entry files, not just here:

1. **`BL-14` cannot be planned as a pure consumer of today's group model or of `collapse` itself.**
   The 2026-10-13 attention-tier direction says `BL-14` needs *per-unit* records for selected
   targets, produced by an attention-driven resolution mechanism that does not exist yet.
   `collapse` serves the reporting/pull-path half of that (a cheap, derived, depth-bounded view) —
   exactly the shape `BL-14`'s own per-target reporting needs — but supplies no resolution: the
   two of six real units `BL-12`'s own measurement found with no record at all are still absent
   after this branch, because `collapse` only ever projects a group's *existing* members. Recorded
   on `body-layer/ROADMAP/BL-14.md`.
2. **`BL-B61`'s class-level resolution gap now has a concrete, named downstream consequence**:
   `step left|right`'s "stay inside the unit group" semantics rests on group identity that
   `group_matches` test 4 cannot enforce at class level for 5 of 10 real `op_class` values. Not
   fixed by this branch (`collapse` reads `Contact.classification` through the lattice directly and
   never touches `Group.composition` — confirmed in the plan's Decision 3/finding B). `BL-B61`
   itself was already filed by the Architect during this plan's own work, correctly, and is not
   re-filed here.

The attention-tiers direction's claim that "the tier's job becomes choosing a depth" is **narrower
than true as stated**: choosing a depth is what `collapse` makes cheap for the *reporting* side,
but the tiers also need the resolution mechanism named in point 1, which `collapse` does not
provide. Worth surfacing to the user as a correction to that framing, not a silent gap.

## Roadmap/backlog updates made

- `body-layer/ROADMAP/BL-W39.md` — new done-entry for this feature (minted `BL-W39`, next unused
  number after `BL-W38`, checked against the directory rather than a written list).
- `body-layer/ROADMAP/body-layer-roadmap.md` — index entry added for `BL-W39`, placed immediately
  after `BL-12` and before `BL-14` in the "Group model..." sequence.
- `body-layer/ROADMAP/BL-14.md` — "2026-10-13 update" section added recording the milestone
  question's answer above, so the next session planning `BL-14` sees it without re-deriving it.
- `body-layer/ROADMAP/BL-B61.md` — **not** re-filed; already exists, filed correctly by the
  Architect during this plan's own work.
- Root `ROADMAP.md`'s status table — **not edited.** Body-layer's overall phase status (BL-12
  merged/unflown, BL-13 built-not-flown) is unchanged by this branch; this is an internal
  derivation milestone with no in-cockpit observable and no phase transition, so adding it to that
  row's narrative would be noise against the one-line test that row is meant to pass. The BL-14
  sequencing consequence is recorded on BL-14's own entry instead, which is where a reader planning
  BL-14 will actually look.

## NOTES.md harvest

Two candidates added (both judged non-duplicate, non-obvious from code or CLAUDE.md):

1. **Fixture-realism failure mode** — "Fixture Management & Test Infrastructure": a blocked stage
   that looks like a genuine product fork can be a fixture pinning a state no real producer can
   emit; check reachability against the real producer before trusting the fork.
2. **Plan-arithmetic column error** — "Planning & Process Lessons": a plan's own cost table citing
   the wrong column of its own measured data (group-depth instead of the actually-requested
   sub-class depth) still reads as internally consistent; check which depth/rate the call site
   actually uses, not just the plan's internal arithmetic.

## Recurring-fix pattern check

Checked Reviewer's two required fixes and Security's one finding against
`.claude/agent-memory/dod/` for a prior "recurring fix" category. None of the three match an
existing pattern memory in this directory (searched: documentation staleness, untested wording
divergence, non-finite-float propagation). The `OP_GROUPSOMETHING`/air-defence-vocabulary-resolution
gap *does* match an existing pattern already tracked elsewhere — `BL-B61`'s own filing cites
`project_recurring_air_defence_vocabulary_resolution_gap.md` directly (this is its 5th occurrence
in the `BL-B47` family) — but that memory already exists and was correctly consulted by the
Architect at plan time rather than rediscovered here, so no update to it is needed from this DoD
pass. No new pattern memory written.

## Verdict

**PASS.**
