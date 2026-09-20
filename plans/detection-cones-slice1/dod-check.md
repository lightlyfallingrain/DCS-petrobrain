### DoD Check: detection-cones-slice1

Branch: `feature/detection-cones-slice1` (fork point `309a9595870341191b27061bb60dc9c38b36090d` on `main`)
Reviewer verdict: APPROVED WITH MINOR FIXES (`plans/detection-cones-slice1/review.md`) — its one
required fix (ROADMAP.md's inverted "binocular default" framing) is applied in commit `9878fed`,
confirmed read directly below.

### Code Quality

- **Subproject scope**: `git diff --name-only` against fork point touches only `body-layer/` +
  `plans/detection-cones-slice1/`. No `world-model/` or `aircraft-layer/` files in the diff — only
  body-layer's own commands are in scope.
- `cd body-layer && .venv/bin/ruff format --check src tests` — **PASS**, "78 files already formatted"
- `cd body-layer && .venv/bin/ruff check src tests` — **PASS**, "All checks passed!"
- `cd body-layer && .venv/bin/mypy src` — **PASS**, "Success: no issues found in 36 source files"
- `cd body-layer && .venv/bin/pytest tests -q` — **PASS**, `732 passed in 9.23s` — matches
  implementation.md's final-pass figure exactly (732 passed, 0 xfailed; `test_vision_calibration.py`'s
  `_STALE_AT_8X_MULTIPLIER` xfail set is gone, not just passing — reconfirmed directly:
  `pytest tests/test_vision_calibration.py -q` → `46 passed in 0.07s`, 0 xfailed).
  Sub-suite spot checks also run directly: `tests/test_optics.py -v` → 9/9 passed;
  `tests/test_mock_flight_chain.py -q` → 4 passed.
- No `TODO`/`FIXME`/stray `print(`/`pdb`/`breakpoint` introduced by the diff (grepped `body-layer/src`
  against the fork-point diff — zero hits).
- No unhandled errors/panics introduced: `visibility.py`'s new FOV gate is a pure boolean predicate,
  no new exception paths; `optics.py` has no I/O.

### Scope & Correctness

- Implementation matches `plans/detection-cones-slice1/plan.md`'s "Final shape" section exactly, per
  Reviewer's independent re-derivation (not re-litigated here — see review.md lines 6-40).
- Scope drift: the plan's own text records four in-session redirects (9K113 cut, derating
  added-then-reversed, multiplier 4→8→4, default flipped naked-eye) — all **user-directed**, not
  silent additions, and each is documented in `implementation.md`'s pass-by-pass log.
- Invariants: `perception/` still does not import `belief/` (Reviewer confirmed); no DCS write path
  touched; no coalition/omniscience leak — the FOV/magnification model only restricts what naked-eye
  perception admits, it does not add information.
- `git status`: clean except three **pre-existing, unrelated** untracked files under `world-model/`
  (`run.sh`, `syria-full-build.log`, `syria-theatre-unfiltered.osm.pbf`) — confirmed not staged and
  explicitly excluded per task instruction. All feature files are committed; nothing new is unstaged.
- Stale sequencer state the Reviewer flagged as an optional refinement (`.git/sequencer/`) is gone —
  `.git/sequencer` no longer exists and there is no `CHERRY_PICK_HEAD`. Resolved since the review.

**One documentation inaccuracy found, not flagged by Reviewer**: `body-layer/ROADMAP.md`'s slice-1
entry (added in the required-fix commit `9878fed`) states *"The 9K113 was cut from this slice and is
filed in todo/todo.md; its figures and its already-existing calibration column are recorded there."*
Checked directly: `todo/todo.md` is untouched by this branch (`git log --oneline -- todo/todo.md`
shows no commit from this branch), and grepping it for `9k113-sight-optics-from-manual`, `optic`, or
any 2026-09-20 entry finds nothing — the existing 9K113-related `todo.md` items predate this slice and
don't reference it. The figures do genuinely exist and are correctly sourced, just not where ROADMAP.md
says: `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`, referenced from `plan.md`
and `body-layer/CLAUDE.md`. This is a one-line factual claim to fix (either add the todo.md pointer or
correct the ROADMAP.md sentence to name the research file directly) — small, but it is exactly the
kind of claim a future reader would follow and not find. Not a merge blocker; flagging for a quick fix
before or shortly after merge.

### Testing

- Core logic covered: `test_optics.py` (FOV gate mechanism, boundary/off-boresight/elevation cases,
  both named optics), `test_visibility.py` (FOV wiring, magnification threading, default-optic
  regression pin), `test_vision_calibration.py` (photographic ground truth, fully green).
- Tests are meaningful, not decorative: Reviewer independently re-derived the arithmetic behind the
  rewritten `test_mock_flight_chain.py`/`test_naked_eye_source.py` fixtures rather than trusting the
  numbers, and found them correct (review.md lines 25-36) — re-confirmed by directly running
  `test_mock_flight_chain.py` here (4 passed).
- No existing tests broken: full suite green at 732/732, 0 xfailed/0 failed.

### Documentation

- Reviewer's one required fix (ROADMAP.md framing) — **applied**, confirmed by reading
  `body-layer/ROADMAP.md` lines 756-798 directly: slice 1 marked "DONE (2026-09-20)", the
  "binocular default" framing corrected to describe the actual naked-eye-default outcome, and a
  milestone-completion note included (the loop: slice 1 → fly it with BL-9 → adapt → slice 2).
- Non-obvious behavior explained: `body-layer/CLAUDE.md`'s `visibility.py`/`optics.py` Structure
  entries fully rewritten for the final state (read in full, lines 183-246) — the circular-import
  resolution, the 4.0→8.0→4.0 round trip, and the default-flip rationale are all recorded.
- Minor gap noted above (ROADMAP.md's `todo/todo.md` claim doesn't check out).

### Security

Per root `CLAUDE.md`'s "Agents" section, `security` is currently exempted for this project phase
("offline single-user local pipeline with no hot path and no untrusted-input surface yet") and was
not invoked — no `security-plan-review.md`/`security-review.md` exists for this feature, consistent
with every other body-layer feature at this phase. Not a gap.

### Verdict

**PASS**, with one small documentation fix recommended (ROADMAP.md's todo.md-filing claim) —
does not block merge, flagging so it doesn't get forgotten.

### Milestone Completion Question (root CLAUDE.md)

**Does this change what slice 2 should be, or invalidate a downstream assumption?**

- **Slice 2's priority is essentially unchanged**, but its *reason for being needed* shifts. Before
  this slice, the single biggest lever on over-detection was the permanently-glassed-up default —
  that lever has now been pulled, and pulled by far more than the cone mechanism itself contributes
  (review.md's own words: "larger than anything the cone test itself contributes"). Slice 2 remains
  the only thing that makes an optic *selectable* (nothing today calls `check_visibility` with a
  non-default optic) and the only thing that gives "scan"/attention operational meaning. It is still
  gated on the ED research deep pass per the plan, unaffected by this slice's outcome.
- **The calibration confound is partially removed, not removed.** The roadmap's original claim was
  that a sortie today would confound calibration because "Petrovich sees in every direction at once."
  That is still literally true within the cockpit-mask envelope: no scanning/dwell/attention model
  exists, and neither shipped optic restricts its own field in the live path (binoculars' 4.25° FOV
  has no caller yet). What changed is the *magnitude* of the confound, not its presence: default
  range dropped ~4x from the naked-eye-default change, which is real and large, but it came from the
  default swap, not from the cone/FOV mechanism doing any gating in the live path yet. A sortie flown
  today would measure "what does an all-seeing-within-the-cockpit-mask naked-eye observer first
  report" — a meaningfully better question than before slice 1, but not the single-clean-optic
  question slice 2 was meant to produce.
- **The vision-calibration fixture's naked_eye/binocular columns do not need re-shooting.** The
  multiplier's round trip (4.0→8.0→4.0) landed back on the value the 2026-09-17 photographic ladder
  was calibrated against, and `test_vision_calibration.py` is fully green (46/46, 0 xfailed) —
  confirmed by direct run, not assumed. What the fixture's four columns (`naked_eye`, `binocular`,
  `9k113_wide`, `9k113_narrow`) do still need is a live sortie confirming the *belief pipeline's*
  default output at these settings in the field — the photographic ladder validates the constants
  against ground-truth screenshots, not the running belief-state process end to end. That is BL-9's
  job (belief-vs-truth visibility), and it hasn't flown. This is recorded as live-acceptance debt
  below, not treated as blocking.
