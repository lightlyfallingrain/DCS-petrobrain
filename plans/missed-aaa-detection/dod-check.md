# DoD Check: fix/los-elevation-tolerance

Branch tip verified: `git rev-parse HEAD` = `5416b0bf125625282a1739e8c3084e2edab88b0e`, matching
the expected tip named in the DoD dispatch (five commits on top of `main` @ `669ffe9`). Checked
out directly in this worktree (the branch was not checked out elsewhere).

## Code Quality

- [x] **world-model** (touched directly): `ruff format --check src tests` — 104 files already
  formatted. `ruff check src tests` — all checks passed. `mypy src` — success, 62 source files.
  `pytest tests -q` — **475 passed, 3 skipped** (matches Reviewer's re-run and the task's expected
  baseline exactly).
- [x] **body-layer** (consumes the fix via `perception.geometry.line_of_sight_clear`'s unchanged
  thin wrapper, run from inside `body-layer/` so `pythonpath = ["src", "../world-model/src"]`
  resolves against this worktree's own fixed `world-model/src`, not any other checkout):
  `ruff format --check src tests` — 111 files already formatted. `ruff check src tests` — all
  checks passed. `mypy src` — success, 52 source files. `pytest tests -q` — **1313 passed, 4
  xfailed** (matches expected baseline exactly).
- [x] No unhandled errors/panics in data paths — the entire diff is one comparison
  (`terrain_m > sightline_alt_m + _TERRAIN_TOLERANCE_M`) plus a module constant; no new control
  flow.
- [x] No debug output left in committed code — confirmed by reading the full diff.
- [x] No leftover debug code or TODO comments introduced by this feature — confirmed by reading
  the full diff (`git diff main..HEAD -- world-model/src world-model/tests`).

## Scope & Correctness

- [x] Implementation matches the plan (`plans/missed-aaa-detection/debug.md`, option 1, the
  user's own choice among five laid out by the Debugger — global tolerance sized to M7's own
  recorded SRTM stddev).
- [x] No unplanned scope added — diff is one constant, one comparison, four new tests, agent
  memory and plan docs. Reviewer independently confirmed no drift (diff stat: 2 source/test files
  + doc/memory files).
- [x] No invariants violated — the no-omniscience invariant is the one this fix trades against,
  and it is traded explicitly and narrowly: Security's deep analysis confirmed the constant has no
  override surface and applies to exactly one comparison, in one function, with one caller.
- [x] All new files staged with `git add` — `git status --porcelain` is empty on this branch tip.

## Testing

- [x] Core logic covered: four tests — the original reproduction (diluted, close-attack-pass
  geometry), an omniscience-hole guard (ridge well beyond tolerance still blocks), and a pinned
  boundary pair (11.9 m clear / 12.1 m blocked, undiluted equal-altitude geometry) added in a
  follow-up commit addressing the Reviewer's optional refinement.
- [x] Tests are meaningful, not decorative — each test's docstring states exactly what it does and
  does not prove (Reviewer and Security both independently verified this by hand-checking the
  boundary math).
- [x] No existing tests broken — both subprojects' full suites pass at their pre-existing counts
  plus the new ones.

## Documentation

- [x] Reviewer findings addressed — `review.md` verdict APPROVED, no required fixes; the one
  optional refinement (tighter boundary test) was acted on in `e58daec`.
- [x] Non-obvious behavior explained — the `_TERRAIN_TOLERANCE_M` constant carries an extensive
  comment: where the number comes from, what it costs, and an explicit airframe-specific lapse
  condition (revisit if this primitive is ever asked to model a pop-up-and-shoot airframe).

## Security

- [x] `plans/missed-aaa-detection/security-review.md` — this fix has no separate plan-review step
  (bug-fix path: Debugger → Reviewer → Security deep analysis → DoD, per `AGENTS.md`'s recommended
  sequences — a plan.md/security-plan-review.md pair is not expected here).
- [x] Security deep analysis: APPROVED. Confirmed the fix implements exactly the accepted
  no-omniscience trade, with no wider reach.

## Verdict: PASS

No required fixes outstanding. Both touched-subproject check suites pass clean. Scope matches the
plan and the user's own chosen fix option exactly.

## Acceptance boundary — what fixtures structurally cannot reach

Every test above is a monkeypatched `sample_grid` in a unit test. That proves the arithmetic (the
comparison, the boundary, the dilution-under-sightline-interpolation mechanism) is exactly what
the debug note diagnosed — it cannot prove that a real sortie, flying a real attack pass over the
real `syria-full.sqlite` grid at the real AAA position, now calls it out. Nor can any fixture
prove the accepted cost is actually mild in practice: whether 12 m starts unmasking a unit behind
a ridge the pilot can plainly see is masking it is a judgment only a real flight in mountainous
terrain can render. Both are named explicitly in the acceptance card below and tracked as live
acceptance debt in `world-model/ROADMAP.md` until a real sortie clears them — this fix is not
blocked on that sortie happening now.
