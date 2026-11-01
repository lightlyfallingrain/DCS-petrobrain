# DoD Check: relative-distance-grouping (BL-B108)

Scoped to tip `71f911d855d2bf5c7b19ad8d2262ab19def4aa04` (feature/relative-distance-grouping).
This worktree started as a strict ancestor of that tip and was fast-forwarded to it; if the branch
has moved since, this verdict is stale and must be re-run.

## Pre-check: inputs present

- `plans/relative-distance-grouping/`: plan.md, explore-notes.md, alignment.md,
  implementation.md, review.md, performance-review.md, security-review.md — all present.
- `body-layer/ROADMAP/BL-B108.md`, `BL-B109.md` — present.
- `review.md` round 3 verdict: **APPROVED WITH MINOR FIXES**. The one required fix (stale "5-67%"
  memory-only fold-rate figure vs. the shipped code's measured 0-86%) was applied in commit
  `f8629e46`, confirmed by direct read: `plan.md`'s amendment now carries a "Superseded figure
  (review round 3)" line with the correct 0-86% range and the user's follow-on decision, and
  `BL-B108.md`'s roadmap entry quotes the corrected range with the same attribution. Not a silent
  rewrite — the superseded figure stays visible next to the correction.
- `performance-review.md` verdict: **APPROVED — MONITOR** (cost is deliberate, already measured
  and justified; `_FIELD_FOURIER_K=256` and ensemble-sweep cost are the named items to watch).
- `security-review.md` verdict: **APPROVED**. One observation noted (mission-memory volume growth
  from dropping the `nameable` gate) — judged a player-experience/volume concern, not a security
  one, no action needed; matches the user's own "keep all" decision in `plan.md`.

## Scope of the diff vs. origin/main

```
git diff origin/main...HEAD --stat: 48 files changed, 6623 insertions(+), 495 deletions(-)
```

Subprojects touched: **body-layer** only (plus `.claude/agent-memory/*`, `plans/`, which are not
code subprojects). No other subproject's checks are owed.

## Quality Gates (body-layer)

| Check | Status | Detail |
|---|---|---|
| Format (`ruff format --check src tests`) | PASS | 192 files already formatted |
| Lint (`ruff check src tests`) | PASS | All checks passed! |
| Types (`cd body-layer && .venv/bin/mypy src`) | PASS | Success: no issues found in 79 source files |
| Tests (`pytest tests -q`, full suite incl. slow mock-flight module) | PASS | 2967 passed, 4 xfailed in 221.10s — matches `review.md`'s own independently re-run numbers (2962 passed excl. mock-flight module + 5 in it = 2967) exactly |

All four commands run directly against this worktree, using the main checkout's `body-layer/.venv`
binaries (this worktree has no `.venv` of its own — gitignored, not copied by the worktree
mechanism) with `PYTHONPATH=src:../world-model/src` for pytest and a `cd body-layer` for mypy per
`body-layer/CLAUDE.md`'s CWD-only config-discovery note.

## Code Violation Scans

| Check | Status | Detail |
|---|---|---|
| No debug output (`print(`, `pdb.set_trace`, `breakpoint()`) in touched src | PASS | 0 occurrences across the 9 touched `src/` files |
| No TODO/FIXME/HACK/XXX in touched src | PASS | 0 occurrences |
| No bare-except / silent-pass in touched src | PASS | 0 occurrences |
| Untracked source/config files | PASS | `git status --porcelain` clean (fast-forward merge, nothing left uncommitted) |
| Stray agent-memory paths (subproject-relative instead of repo-root) | PASS | None — all five agent-memory files added by this feature live under repo-root `.claude/agent-memory/<role>/` |

## File size (>400 lines)

Several touched files exceed 400 lines (`contacts.py` 1935, `naked_eye_source.py` 1781,
`position_belief.py` 1161, `estimation.py` 1052, `association_over_time.py` 572). This is
**pre-existing, widespread condition across the whole subproject** (`crew_console.py` 5393,
`body.py` 5224, etc.), not a threshold this feature newly crossed or a problem Review flagged as
new scope — not treated as a blocking finding here, consistent with how prior DoD passes on this
subproject have read the same signal.

## Scope & Correctness

- Implementation matches `plan.md` and its 2026-11-01 amendment, with the one deliberate,
  documented deviation (mechanism-and-calibration-in-one-commit, flagged by Reviewer as a
  reasoned, verified exception, not a silent violation of the "mechanism and calibration never
  share a commit" invariant).
- No unplanned scope added silently — `implementation.md`'s "Notable Discoveries" section records
  every deviation from the plan's literal text (test vehicle choice, deferred E1a group-identity
  check left to `[[BL-B105]]`, the test card left to merge/DoD) with its own reasoning, not
  discovered by this role.
- `alignment.md`'s goal check (CONCERNS, resolved) and the plan's own E1-E4 expectations are
  delivered same-optic and whenever both groups are in view; the memory-only cross-optic gap is
  fenced, documented, and user-accepted — not silently narrowed.
- No invariants from `body-layer/CLAUDE.md` violated — no-omniscience boundary respected
  (cross-optic correlation returns `(0.0, 0.0)` by design rather than inferring the field value
  from two correlated optics); mechanism/calibration-in-one-commit is the one flagged, reasoned
  exception above.
- All new files staged — confirmed via `git status --porcelain` (clean) after the fast-forward.

## Testing

- Core logic covered: `test_relative_distance_scenarios.py` (E1-E4 scenario tests, 674 lines) and
  `test_relative_distance_sweep.py` (ensemble sweep + fence table, 640 lines), both new.
- Tests are meaningful, not decorative — Reviewer independently re-ran an N=300 ensemble sweep
  across 24 geometry/optic-order/temporal-order cells and an instrumented trace, not just
  re-running the suite as shipped; found a real covariance-fusion defect (`_is_valid_covariance`)
  that a weaker mean-residual-only guard would have missed, confirming the tests exercise real
  failure surfaces.
- No existing tests broken — full suite green, matches pre-fix counts exactly (`implementation.md`
  and `review.md` both report the same 2962/5/4 split).

## Documentation

- Reviewer findings addressed: round 3's one required fix (stale figure) applied in `f8629e46`,
  verified above. Round 3's optional refinements (docstring note on the hypothesis-scaling
  crossover, naming the mechanism-and-calibration-in-one-commit exception as a pattern) are left
  open — both explicitly optional, not required fixes, and do not block merge.
- Non-obvious behaviour explained via `docs/STRUCTURE.md`-adjacent module docstrings and this
  role's own `notes/` harvest (below) — the covariance-fusion bug, the hypothesis-geometry vs.
  real-geometry distinction, the `_FIELD_FOURIER_K=256` finding, and the hypothesis-scaling
  amplification mechanism are all now recorded where the next reader will find them.

## Security

- `plans/relative-distance-grouping/security-plan-review.md` — **not present**. Per root
  `CLAUDE.md`'s "Agents" section ("Security's plan review left the sequences... 2026-10-30"), plan
  review now runs on demand only; its absence here is not a FAIL.
- `plans/relative-distance-grouping/security-review.md` — present, **APPROVED**.

## Milestone-completion question

**Does this change the next milestone, or invalidate a downstream assumption?** Yes, in one
specific way: BL-B108 ships E1 same-optic and whenever both groups are in view, but **not**
cross-optic when the far group is held only in memory (0-86% fold rate in that one geometry
class, worst case far-binocular/near-unaided/far-first at 4.5-5.0 km). The user accepted this as
the honest limit for now and named the closing mechanism themselves: an "expected-area check"
feature (look at the remembered group's expected location/area, not the whole bearing, using
composition/count and plausible-displacement-given-speed as the same/different test —
`explore-notes.md`, "Follow-on answers"). This is now the natural next BL-B10x item, distinct from
`[[BL-B109]]` (callout wording, already split out and separately scoped). `[[BL-B105]]`'s own E1a
group-identity-check gap (deferred by this milestone, "Notable Discoveries" #7) is a second,
smaller downstream dependency worth remembering when BL-B105 is picked up.

## Unblock-condition execution (accepted debt)

The accepted debt here is not a "fix it when X" with a runnable clearing command — it is a
documented honest limit plus a named follow-on feature, not a probe or script to execute. The one
thing that is runnable and was checked directly rather than trusted: the shipped fence test itself.

```
$ cd body-layer && PYTHONPATH=src:../world-model/src .venv/bin/python -m pytest tests/test_relative_distance_sweep.py -q
.......................................................................  [100%]
71 passed in 31.85s
```

Run directly (not assumed from the implementer's/reviewer's own counts): 71 passed, confirming the
fence that bounds the accepted memory-only cross-optic limit is itself green on this exact tip.

## Verdict: PASS

All mechanical checks pass, both prior review stages (Reviewer round 3, Security) are APPROVED,
Performance is APPROVED — MONITOR, the one required fix was independently confirmed applied, and
the fence test that bounds the one accepted limitation was independently re-run and is green.

