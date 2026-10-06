# Definition of Done — `feature/bl11-tick-cost` (`BL-11` Stages 1, 2, 3b, 5)

**Verdict: DoD PASSED.** Acceptance testing is **outstanding, deliberately, and does not gate the
merge** — see "Acceptance boundary" below.

**Branch:** `feature/bl11-tick-cost`
**Tip verified:** `8e49506` — `git rev-parse HEAD` matched the dispatched sha before any check ran.
**Gated:** 2026-10-06.

## Branch-identity check

`AGENTS.md` rule 4. The main checkout was on `main`, so the branch was free and checked out
directly rather than snapshotted. **Import resolution was proved, not assumed**, because a DoD run
on this project once reported `1177/4` — exactly `main`'s baseline — against a branch's own
`1192/4`:

```
perception.group_salience -> <worktree>/body-layer/src/perception/group_salience.py
logger                    -> <worktree>/body-layer/src/logger.py
run_log_paths             -> <worktree>/body-layer/src/run_log_paths.py
belief.enrichment         -> <worktree>/body-layer/src/belief/enrichment.py
coordinates               -> <worktree>/body-layer/../world-model/src/coordinates/__init__.py
```

`run_log_paths` exists only on this branch, which is itself positive evidence the worktree's own
`src` is in play. The suite's **1518** also differs from `main`'s 1466, so the number cannot be
`main`'s by accident.

## Subprojects touched — derived from the diff, not from memory

`git diff --name-only main HEAD` over 62 files. The only subproject with source changes is
**`body-layer`** (`src/` 9 files, `tests/` 8 files). Everything else is `plans/`, `docs/`,
`run-scripts/*.sh` (shell, no Python toolchain), `.claude/`, `todo/`, and `body-layer`'s own
`BACKLOG.md`/`CLAUDE.md`/`RUN.md`/`docs/STRUCTURE.md`. **No second subproject's commands are owed.**

## Code quality

| check | command | result |
|---|---|---|
| format | `ruff format --check src tests` | **PASS** — 118 files already formatted |
| lint | `ruff check src tests` | **PASS** — All checks passed! |
| types | `mypy src` (from inside `body-layer`) | **PASS** — no issues in 54 source files |
| tests | `pytest tests -q` | **PASS** — **1518 passed, 4 xfailed** (`main` baseline 1466/4; +52, xfail count unchanged) |

Toolchain borrowed from the main checkout's `body-layer/.venv` by absolute path with `cwd` inside
the worktree's own `body-layer/` (this worktree has no `.venv`).

- **No unhandled errors in data paths.** The three JSONL writers now report a write failure once and
  disable rather than raising or failing silently per write; `_per_run_log_paths.resolve` puts every
  statement under one guard over a named `_RESOLVE_FAILURES` tuple and degrades one log rather than
  killing the crew.
- **No debug output left.** The `src` diff (1,061 lines) contains no added `TODO`/`FIXME`/`XXX`/
  `breakpoint`/`pdb`. The added `print(..., file=sys.stderr)` calls at `logger.py:2215` are the
  intended startup path lines and the degrade reports, not debug residue.
- **No leftover debug code or new TODOs.**

## Scope & correctness

- **Matches the plan.** `BL-11` Stages 1, 2, 3b and 5 as filed. Stage 3a was **deliberately
  omitted** and the performance pass vindicated that with a number: 189 `describe_position` calls
  against 187 distinct 50 m cells — 2 redundant, 1.1 %. Stage 6 is subsumed by Stage 1 and held
  mechanically by `test_no_stale_five_hertz_claims_remain_in_src`. Stage 4 is untouched and remains
  gated on a sortie.
- **No unplanned scope.** `belief/callouts.py`, `belief/speech.py` and `perception/motion.py`
  (`BL-B34`) were explicitly not touched, and the performance pass confirmed the `callouts.py`
  multiplier intact at `:823`/`:833`/`:891`.
- **No invariants violated.** No DCS-installation access of any kind; no `world-model/data/` content
  staged; provenance/uncertainty handling untouched; code still owns factual state. The one
  forum/community-claim rule is not engaged — every number acted on came from this repo's own
  measurement.
- **One out-of-scope dangling reference, flagged not edited:**
  `plans/player-bubble/performance.md:64` reasons about "avoiding the `O(n)` `_resolvable()` pass",
  and `_resolvable` is now deleted (the pass survives as `_resolvable_terms`). It is a
  forward-looking note for an unbuilt feature, so unlike the dated research notes it could mislead.
  Belongs to another plan.
- **All files staged**, clean tree.

## Testing

- **Core logic covered, and the coverage was checked by mutation rather than by reading.** The
  performance pass reverted each load-bearing mechanism in `src` and re-ran: the grid key → 1 failed
  (`test_cache_hits_after_a_one_metre_nudge`, the finding's own reproduction); `_wait_for_next_tick`
  → 3 failed. Production restored and verified byte-identical by sha each time.
- **Tests are meaningful, and three were explicitly repaired for being decorative** — this is the
  branch's most creditable feature. Round 2 replaced the equivalence file's *imports* of the code it
  pins with local copies of the pre-change bodies (an equivalence test that imports its subject
  proves nothing). Round 3 gave both `test_close_does_not_raise_on_a_healthy_writer` cases teeth by
  buffering the row until `close()`, after finding the row was already on disk so the assertion held
  whatever `close()` did. Round 5 found `OverflowError` in the guard tuple had **no test at all**.
  The equivalence file also carries a non-vacuity guard, because equality between two
  implementations that both return `frozenset()` proves nothing.
- **No existing tests broken.** Two were modified and both were flagged: `test_all_three_logs_share_
  one_stamp` and `test_a_single_configured_log_rolls_without_inventing_the_others`, rerooted onto
  `tmp_path` because the new `mkdir` would otherwise have made the suite deposit an untracked
  `logs/` wherever pytest started. Both were added by this same branch two commits earlier, so no
  pre-existing contract was rewritten; assertions unchanged in meaning.

## Documentation

- **Reviewer findings addressed across five rounds** (`review.md`, `review-round2.md` …
  `review-round5.md`), each round's required fixes landed and re-reviewed; round 5's single required
  fix is commit `f70ff3e`. The performance pass's one change request — a docstring, not code — is
  commit `8e49506`.
- **Reviewer confidence:** full reads, not spot-checks. Rounds 2–5 each verified their predecessor's
  fix by constructing a failing counterfactual and restoring production byte-identical by sha.
- Non-obvious behaviour explained in `RUN.md` (the path passed is not the path written — glob, do not
  hardcode; the stderr line is authoritative), `body-layer/CLAUDE.md`, `docs/STRUCTURE.md`, and four
  NOTES.md entries added by this gate.

## Security

- `plans/bl11-tick-cost/security-review.md` — **APPROVED**, three low findings on the new `mkdir`.
  Findings 1 and 2 were fixed (`071410f`, re-entering the Implementer→Reviewer loop per `AGENTS.md`
  and then taking two further rounds to close the closure's exception seam completely). Finding 3
  (typo blast radius) and finding 5 (`suppress(OSError)` around `close()`) were accepted as
  correct-as-written. Finding 4 — a disabled log reads as a short one — was **filed as backlog
  (`BL-B39`), not fixed**, and is named on the acceptance card so the user is not surprised by it.
- `plans/bl11-tick-cost/security-plan-review.md` — **absent, and expected to be.** Under the
  2026-09-24 cadence, Security runs **once per whole feature immediately before DoD**, not as a plan
  review. The whole-subproject audit this milestone derives from is
  `body-layer/research/2026-10-05-security-audit.md`.

## Acceptance boundary — what these fixtures structurally cannot reach

**Stated plainly, because a bench pass is not a flight pass.** Every number in this gate comes from
a harness with a **fake in-process aircraft client**, **no TTS engine**, and **static objects**, on
a Mac that is not the one flying. So:

1. **Every CPU figure is a floor.** No LAN is in the path. The sortie's **4.98 s p90 is unexplained
   by any measurement here** and the candidates — `BL-B33`'s five sequential 2.0 s timeouts,
   `BL-B32`'s synchronous TTS — are precisely the two things the harness replaces with something
   free. A gate that reports "the period is 1.000 s" is reporting the CPU half only.
2. **89.7 % within-tick cache hit rate is an upper bound.** Static objects mean believed positions
   settle and cross 50 m cells rarely. The direction is certain (the old exact-float key could never
   hit for a re-observed contact); the magnitude needs a flight.
3. **The pilot-facing risk is not measurable here at all.** Stage 3b shares one enrichment result
   across a 50 m cell (worst case ~70.7 m horizontal). Whether a spoken line ever sounds *wrong
   about a nearby feature* is a judgement made with ears in a cockpit. No fixture has ears. This is
   the `F10`-vocabulary lesson restated: *"Scan" drove the wrong subsystem and no fixture could
   detect it; "Cancel Task" spoke a raw task id, which is only a defect when a human hears it.*
   A 70 m qualifier error is exactly that class.
4. **The startup stderr lines were never seen in a real launch.** The path resolution behind them is
   verified by execution; `main()` starting is not.

**Live verification is deferred, not waived, and must not gate the merge** (user direction,
2026-09-19). Recorded on `body-layer/ROADMAP.md`'s **Live acceptance debt** list rather than as a
one-off caveat. It **batches with almost any sortie** that exercises ground contacts at mixed
ranges — no deployment, no particular geometry, nothing new to start.

Card: `docs/acceptance/2026-10-06-bl11-tick-cost-sortie.md`. Every command in it was executed and
its real output pasted, except the flight; the four things that cannot be run from here are labelled
UNVERIFIED in the card itself.

## Process signals for the user

1. **The dispatching claim that "Stage 0 is already `[x]`" was not true of this branch or of
   `main`.** The `[x]` lives on the unmerged `fix/callout-observability-gate`, whose DoD did pass
   (`24fa35d`) but whose roadmap edit never reached `main`. **Consequence handled:** roadmap edits
   here are scoped to the stages this branch owns, Stage 0's paragraph is untouched, and the new
   live-acceptance-debt entry is inserted mid-list rather than at the top where the other branch
   also inserted — so the two merge cleanly. **`BL-B39`/`BL-B40` are likewise on `main` only**, not
   on this branch, so `BACKLOG.md` will merge the `BL-B30` resolution here against those two
   additions there.
2. **Recurring pattern, 5 instances on this one branch: a correct conclusion carrying a reason the
   code or data does not support.** The branch's own log named it (*"Fifth round, fifth
   correct-conclusion-wrong-reason"*). This is **process debt, not code debt** — code is held by
   tests, prose is held by nothing, and two earlier instances had already done real damage (the
   stale "5 Hz" docstrings produced `BL-B30`'s entire wrong premise plus a wrong figure in an agent's
   memory). Three of the five were one grep from being caught. Worth an explicit "what would falsify
   this reason" step at Reviewer round 1 rather than discovering it over five rounds.
3. **5th occurrence of multi-round widening of an enumerated set** — `_RESOLVE_FAILURES` grew
   `OSError` → `+ValueError` → `+RuntimeError` → `+OverflowError` across rounds 2–5. First time on a
   *defensive* set rather than a tuning one. What ended it was structural (one `try:` over every
   statement) plus a per-entry counterfactual, and the per-entry counterfactual would likely have
   compressed four rounds into one.

## NOTES.md harvest

Four entries added, all earned on this branch and all checked against the existing file:

1. A guard entry no test defends is a comment, not a contract — dropping `OverflowError` left the
   suite green. Generalises past exception tuples to any enumerated defensive set.
2. Two fixes each passing its own counterfactual while the pair leaves the seam open — a per-fix
   counterfactual only tests the statement the fix touched.
3. A benchmark that cannot fail proves nothing, so every harness needs its own can-this-fail probe.
   **Explicitly distinguished in the text from the existing `BL-B23` entry** ("the fix works" ≠ "the
   cost is bounded"), which is about measuring a real thing along one axis; this is about measuring
   nothing while printing plausible numbers.
4. A diagnostic signature can survive the fix it diagnosed and come to mean the opposite —
   `distinct_positions == describe_calls == cache_misses`, still true in 37/37 ticks.

Nothing was added that is obvious from the code or already in `CLAUDE.md`.

## Not done here, by instruction

**Nothing is marked merged.** The merge is the user's, with their approval.
