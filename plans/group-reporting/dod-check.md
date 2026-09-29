## Definition of Done: group-reporting

Reviewed `feature/group-reporting` @ `8959e2c` (confirmed via `git rev-parse HEAD` against a nested
detached-HEAD worktree checked out at that exact sha — this worktree's own branch had landed
elsewhere, per dispatch instructions) against `main` @ `acc94db`.

### Code Quality

- [x] Format/lint/type/test pass for the only touched subproject (body-layer). Run from inside the
  verified snapshot's `body-layer/`, using the main checkout's `.venv` interpreter by absolute path:
  - `ruff format --check src tests` — 113 files already formatted
  - `ruff check src tests` — All checks passed
  - `mypy src` (strict) — Success: no issues found in 53 source files
  - `pytest tests -q` — **1349 passed, 4 xfailed**, matching the expected/claimed number exactly
    (main's own baseline is 1313/4)
- [x] No unhandled errors/panics introduced — checked the diff directly, no bare `except`/`pass`
  swallows added.
- [x] No debug output left in committed code — grepped the diff for `print(`/`console.log`/
  `pdb.set_trace`/debugger calls, none found.
- [x] No leftover TODO/FIXME/XXX introduced by this feature — none in the diff.

### Scope & Correctness

- [x] Implementation matches `plans/group-reporting/plan.md`, including its own Stage 4 design
  addendum and the two later coordinator decisions (2-member floor, pair/couple wording) —
  confirmed by Reviewer's independent code reading, not just by trusting the plan's own account.
- [x] No unplanned scope added silently — Reviewer's review.md found none; the two backstop
  mechanisms (flat-metre, then unit-width) were both explicit, dated, user-directed additions with
  their own commits, not silent scope creep.
- [x] No CLAUDE.md invariants violated — Security's deep analysis (`security-review.md`) traced the
  no-omniscience boundary through every touched module (`groups.py`, `speech.py`, `callouts.py`,
  `contacts.py`) and found clustering/disclosure read only `Contact.position`/`last_class_raw`,
  never ground truth, an `object_id`, or the trace-writer path.
- [x] All new/modified files staged and committed — `git status --porcelain` on the branch is
  clean; nothing untracked or modified outside commits.

### Testing

- [x] Core logic covered: `test_groups.py`, `test_callouts.py`, `test_speech.py`,
  `test_crew_console.py`, `test_contacts.py`, `test_console.py`, `test_tools.py` all touched with
  real assertions against instrumented per-tick output, not guessed expected strings (confirmed by
  reading `implementation.md`'s own account of how fixtures were re-verified after the unit-width
  rework).
- [x] Tests are meaningful — the two `store._groups._groups = {}` workarounds flagged by review as
  needing a fresh look were removed once the unit-width backstop made them genuinely unnecessary,
  rather than kept as dead scaffolding.
- [x] No existing tests broken — 1349/4 matches the pre-existing baseline's shape (net zero: two
  backstop tests removed transiently by the mechanism commit, reinstated recalibrated by the
  calibration commit).

### Documentation

- [x] Reviewer's required fixes addressed — both were `body-layer/ROADMAP.md` staleness/framing
  issues (line ~1260 describing n=2 as still-open when the backstop fixed it, and not telling the
  user the n>=3 risk was distinct); `f19d719` corrected them on the branch, and this gate's own pass
  goes further, updating the entry again now that the unit-width rework closes n>=3 too (see
  "Roadmap" below).
- [x] Non-obvious behaviour explained — `implementation.md`'s "Notable Discoveries" sections carry
  the reasoning (angular vs. world-space unit-width currencies, the `_representative_size_m`
  fallback chain, the `OP_TRUCK` keyword-match coincidence) in enough detail that a future reader
  does not have to re-derive it from the diff.

### Security

- [x] `plans/group-reporting/security-review.md` exists and is **APPROVED** (deep analysis, run
  against an isolated snapshot at `b92c7a7`, re-verified here at `8959e2c` since performance's own
  pass landed after it with no code change).
- **[FLAG, not a fail] `plans/group-reporting/security-plan-review.md` does not exist.** This
  feature took the "New feature" role sequence (Explore → Architect → ... → DoD), which calls for a
  Security plan review immediately after Architect and before Implementer — it was never run;
  neither `plan.md` nor `implementation.md` mentions one, and no commit in `git log main..
  feature/group-reporting` corresponds to it. No new dependency was introduced by this plan (the
  deep analysis's own "Dependency Status: No dependency change" confirms this after the fact), so
  the plan-review step's main distinct value — catching a bad dependency or design-level risk
  *before* code exists — was not exercised, and the deep analysis that did run is a thorough,
  code-level substitute that covers the same ground the plan review would have (the no-omniscience
  boundary across every touched module, per-member attribution, persistence-across-ticks) rather
  than a lighter design-only pass. Given the sortie deadline and that re-running a plan review now
  would only re-confirm what the deep analysis already traced through actual code, I am not
  treating this as a blocking DoD failure — but it is a real process gap in this feature's history,
  not a waived step, and is recorded here so it is visible rather than silently absent.

### Roadmap

- `body-layer/ROADMAP.md`'s group-reporting entry updated (this gate): flips `[~]` to `[x]`,
  corrects the n>=3 framing now that `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS = 20.0` closes both
  the n=2 and n>=3 cohesion risks (superseding the flat-metre backstop the previous roadmap pass
  described), and states the two attribution consequences are now bounded to ~140 m rather than
  unbounded. **Milestone completion question, answered in the roadmap entry itself**: yes — Stage
  5's design should now be built from this sortie's evidence on the unit-width figure, not from
  further code reading in advance of it.
- Root `ROADMAP.md`'s Body Layer row given a short addition naming group-reporting's DoD-pass,
  linking the acceptance card, and noting it rides into `main` together with the LOS-elevation-
  tolerance and confirm-band fixes.

### NOTES.md

- One entry added: the explore-phase lesson about lived-cockpit intuition refuting a just-proposed
  design within minutes (gaze-wedge, the 3-member floor, the pair/couple vocabulary), framed as
  "ask early, expect the first answer to move it" rather than as a grouping-specific note.

### Verdict

**PASS.** All mechanical checks pass at the exact expected numbers. Reviewer, Security (deep
analysis) and Performance have all signed off. The one gap found (`security-plan-review.md` never
produced) is flagged above rather than fixed retroactively, given the deep analysis already covers
equivalent ground and no dependency was introduced — see that section for the reasoning; it should
not be silently repeated on the next "New feature"-sequence branch.

Acceptance testing is the user's own — see `docs/acceptance/2026-09-29-group-reporting-sortie.md`.
