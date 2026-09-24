# Definition of Done — position-belief-runaway

Branch `fix/position-belief-runaway`, head `0465290`, branched from `main` at `a04eec8`.
Full role sequence complete: Debugger → Reviewer (required fix) → Debugger (fix) → Reviewer
(re-review, APPROVED) → Security (found one issue) → Implementer (fix) → Reviewer (re-review,
APPROVED). This is the DoD gate, run in a `main`-based worktree with the branch checked out
elsewhere in the main working directory — verification below was run against an isolated
`git archive` scratch tree of the branch tip, per the standing pytest/PYTHONPATH trap.

## Code Quality

- [x] **Touched subprojects, determined from the diff, not memory.**
  `git diff --stat main..fix/position-belief-runaway` — only `body-layer/` (`src` + `tests`),
  `plans/position-belief-runaway/`, and `.claude/agent-memory/{debugger,implementer,reviewer,
  security}/`. No other subproject touched; only body-layer's own commands needed.

- [x] **body-layer format/lint/type/test, run against an isolated `git archive` of the branch
  tip** (not the worktree's own main-based checkout — see note above):

  ```
  cd body-layer && .venv/bin/ruff format --check src tests && .venv/bin/ruff check src tests \
    && .venv/bin/mypy src && .venv/bin/pytest tests -q
  ```

  - `ruff format --check`: 103 files already formatted.
  - `ruff check`: All checks passed.
  - `mypy src`: Success, no issues found in 48 source files.
  - `pytest tests -q`: **1192 passed, 4 xfailed** — matches the task's expected figure exactly
    (main baseline 1177/4 → +15 new tests, no regressions, no new xfails).

  (A first pytest run inside the worktree's own checkout returned 1177/4 — the exact `main`
  baseline, confirming the worktree was silently testing `main`'s code. Re-ran from inside a
  `git archive fix/position-belief-runaway` scratch tree with `cwd` set inside its own
  `body-layer/`, which resolved correctly to 1192/4. New memory left at
  `.claude/agent-memory/dod/feedback_dod_worktree_pythonpath_trap_applies_here_too.md`.)

- [x] **No unhandled errors/panics in data paths.** Diffed `body-layer/src` against `main`:
  no new bare `except`/silent `pass` patterns introduced.
- [x] **No debug output / leftover TODOs.** Grepped the full diff (`src` + `tests`) for
  `TODO|FIXME|XXX|print(|pdb|breakpoint`: no hits.

## Scope & Correctness

- [x] **Matches the plan.** This is a bug-fix workflow (Debugger → Reviewer → Security → DoD, no
  Architect stage) — no `plans/position-belief-runaway/plan.md` exists, correctly; `debug.md`
  (with two dated addenda) stands in as the scope record and every commit maps to one of its
  four named fixes plus the independent speech bug.
- [x] **No unplanned scope added silently.** Every change traces to: the debug report's two
  root-cause fixes, Reviewer's one required fix (determinant-floor scale), Security's one
  required fix (hold-recovery timing), or the independently-reported speech stutter bug. Two
  "found, not fixed" items are explicitly logged as deliberate follow-ups, not silently dropped
  (`last_seen_sim`-reads-as-fresh-during-a-hold; the class-level threat-table join gap, unrelated
  to this branch).
- [x] **No CLAUDE.md invariants violated.** No new dependency, no DCS-install write, all
  perception/belief boundaries (`Percept`'s structural no-omniscience cut) untouched by this
  branch — confirmed by reading the diff, not assumed.
- [x] **All new/modified files staged.** Confirmed via `git status --porcelain` on the branch tip
  (see Verification below) — clean at `0465290`.

## Testing

- [x] Core logic covered: 15 new tests across `test_position_belief.py` (residual guard, envelope
  clamp, determinant-floor regression, hold-recovery-timing regression), `test_contacts.py`
  (end-to-end slow-drift, cardinality non-corruption), `test_speech.py` (stutter fix).
- [x] Tests are meaningful, not decorative — Reviewer independently re-executed every regression
  test against isolated pre-fix/post-fix `git archive` trees and confirmed fail-before/pass-after
  for each, rather than reading the diff alone (see `review.md`'s multiple "independently
  re-ran... not inferred from the diff" notes).
- [x] No existing tests broken — 1192/4 vs. main's 1177/4, zero regressions, zero new xfails.

## Documentation

- [x] Reviewer required fixes addressed: both (`97d5c65` for the determinant floor, re-reviewed
  APPROVED in `cd768af`; `6a8daaf` for hold-recovery timing, re-reviewed APPROVED in `0465290`).
- [x] Non-obvious behavior explained: `position_belief.py`'s module/class docstrings state the
  `fused_at_sim`-vs-`as_of_sim` invariant directly (per Reviewer's confirmation); `debug.md`'s two
  addenda record the "logged as a decision, not an oversight" `last_seen_sim` gap.

## Security

- [x] No `security-plan-review.md` — correct for a bug-fix workflow (Security's plan-review step
  only applies to the Architect-driven new-feature sequence).
- [x] `plans/position-belief-runaway/security-review.md` exists. Verdict: **NEEDS FIXES** on
  `4ba3da7` (hold-recovery timing, the one substantive finding — correctly classified as a
  robustness/correctness finding, not an exploitable vulnerability, given this project's
  no-untrusted-input threat model). Fix applied (`6a8daaf`) and re-reviewed **APPROVED** by
  Reviewer in `0465290`. Effectively resolved — no open security items.

## Verdict: DoD criteria PASSED

All mechanical and process checks pass. Live acceptance is explicitly **outstanding**, not
counted as passed — see the Acceptance Testing Plan below and the boundary statement that
precedes it.

---

## Acceptance boundary — what this DoD pass cannot see

DoD ran fixtures, isolated-tree pytest, and read the full review/security paper trail. It did
**not** fly the aircraft, and there is a real gap between what that verifies and what a sortie
verifies, same class as the F10-vocabulary lesson this role's own instructions name:

- **"No range callout beyond the detection cap" is structurally checkable by fixture** — the
  regression tests pin exact numeric cases at the cap boundary — **and is also the one thing a
  live flight can trivially falsify or confirm by ear.** High confidence either way.
- **Whether the *believed position* the fix produces is actually close to the true position, not
  just bounded within the detection envelope, is not something a fixture or this gate can show.**
  A test can assert "stays under 10 km"; it cannot assert "matches where the pilot can see the
  target actually is," because no fixture carries an independent ground-truth check against human
  perception. This is exactly the gap the acceptance card's block 2 exists to probe.
- **The ~7-10 s hold-recovery figure is a regression-test number and an independently-reproduced
  measurement against a synthetic scenario (Security's probe, 8 poll intervals plus 2 jittered
  sequences) — never against a real sortie's actual poll timing, actual disagreement geometry, or
  actual pilot perception of "stuck."** A fixture cannot show whether 7-10 seconds *feels* right
  in the cockpit.

## Live-acceptance debt

Not merged yet. This branch adds to, not clears, `body-layer/ROADMAP.md`'s live-acceptance debt
list — a new entry there names the card and marks it `[ ]`, distinct from the precise-position-
belief entry it supersedes for testing purposes (that entry now explicitly says not to judge its
position-belief items until this fix merges). Card:
`docs/acceptance/2026-09-25-position-belief-sortie.md`, batched conceptually with the three
already-open cards (`2026-09-23-eyes-and-voice-sortie.md`, `2026-09-24-watch-reporting-sortie.md`,
`2026-09-24-damage-and-firing-probes.md`) — four sorties of debt total, this one included.

## Milestone-completion question

Does this change what the next milestone should be, or invalidate a downstream assumption? No —
this is a bug fix to an already-merged milestone (`precise-position-belief`), not a new milestone.
It does **not** change BR-1's readiness (`plans/brain-layer/plan.md`, waiting on
`feature/brain-layer`) — the brain layer consumes belief-state facts through the existing tool API,
which this branch does not touch the shape of. It does mean any brain-layer acceptance testing
that exercises position-derived facts should happen against the merged, fixed belief, not the
buggy `precise-position-belief` merge — worth a one-line note if BR-1 starts before this merges.

## Verification (all commands run, output pasted, not asserted)

Diff scope:
```
$ git diff --stat main..fix/position-belief-runaway
 ... 22 files changed, 2068 insertions(+), 29 deletions(-)
```
(only body-layer/{src,tests}, plans/position-belief-runaway/, .claude/agent-memory/*)

Format/lint/type, isolated `git archive` scratch tree of the branch tip:
```
$ ruff format --check src tests
103 files already formatted
$ ruff check src tests
All checks passed!
$ mypy src
Success: no issues found in 48 source files
```

Test, same isolated tree:
```
$ pytest tests -q
1192 passed, 4 xfailed in 10.33s
```

Debug-artifact scan (diff only):
```
$ grep -nE '^\+.*(TODO|FIXME|XXX|print\(|pdb|breakpoint)' <diff> → no hits
$ grep -nE '^\+.*except|^\+\s*pass\s*$' <src diff> → no hits
```
