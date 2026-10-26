# Definition of Done: fix/optic-views-actual-look

Verdict scoped to tip `9d8908e2782c18d27e221a9af94b8cb426a56848`. If the branch moves past this
commit, re-run.

## Address

`git rev-parse HEAD` at dispatch was `fee96cdc6b2a5ade2d16bcc40317a95461a7a375`, a strict ancestor
of the expected tip with a clean tree. Fast-forwarded (`git merge --ff-only
9d8908e2782c18d27e221a9af94b8cb426a56848`); HEAD is now the expected tip.

Role sequence followed: this is a **bug fix** (Debugger -> Reviewer -> Security deep analysis ->
Performance Reviewer -> DoD), not a new feature, so there is no Architect `plan.md` and no
`security-plan-review.md` -- neither is required for this class of change. Confirmed against
`AGENTS.md`'s recommended sequences table.

## Code Quality

Diff touches exactly one subproject with code: `body-layer/` (`src/body.py`,
`tests/test_body.py`). Everything else in the diff is docs/plans/notes/agent-memory
(`docs/acceptance/`, `plans/optic-views-actual-look/`, `.claude/agent-memory/reviewer/`).

Ran from `body-layer/` using `/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/` (worktree has no
own venv):

```
$ ruff format --check src tests
178 files already formatted
$ ruff check src tests
All checks passed!
$ (cd body-layer && .venv/bin/mypy src)   # run as: cd body-layer && mypy src
Success: no issues found in 77 source files
$ pytest -q
2694 passed, 4 xfailed in 29.09s
```

- No unhandled errors/panics introduced in data paths -- the sight-tier `assert`s in
  `_resolve_active_gaze` are a verbatim carry-over from the pre-existing `_render_pov_frame` code
  (Security's finding, confirmed independently by grep), not new.
- No `print`/debug output or TODO/FIXME left in the new `body.py` code (checked by grep against the
  diff).
- No new behaviour-affecting constant introduced (no new `tuning.py` entry needed).

## Scope & Correctness

No `plans/optic-views-actual-look/plan.md` exists because this is a bug fix, not an Architect-led
feature -- `debug.md` is the plan-equivalent artifact for this class of work and is present.
Implementation matches `debug.md`'s stated design (shared `_resolve_active_gaze` resolver, three
cases: sight-tier world direction, fixed-look `actual_aim_*`, free-scan `scan_plan` fallback) and
the follow-on commit (`_speech_log_sink` swapped onto the same resolver) closes the one remaining
reporting site the first commit's own notes flagged as left for later -- no silent scope
expansion, both commits reviewed and both explicitly scoped in their own messages.

No CLAUDE.md invariants violated:
- No-omniscience boundary untouched (`Percept`/`detection_trace_writer.py` exemption unaffected;
  this fix touches debug-view/log rendering only, which already carries its own documented
  ground-truth exemption per `pov_view.py`/`eyesight_view.py` module docstrings).
- `_speech_log_sink` continues to read `runner` live per spoken line (unchanged design property,
  confirmed by Reviewer).
- No new in-process cross-subproject import, no new dependency.

All new/modified files staged -- confirmed via `git status --porcelain` (clean, see below) after
the fast-forward.

## Testing

13 new/modified tests target the fix directly (`_resolve_active_gaze` three branches,
`_render_eyesight_frame` sight-tier and binocular cases, `_speech_log_sink` sight-tier and
binocular cases) -- re-ran them in isolation, all pass:

```
$ pytest tests/test_body.py -k "resolve_active_gaze or render_eyesight_frame_sight_tier or render_eyesight_frame_binocular or speech_log_sink" -v
13 passed, 185 deselected in 0.18s
```

Reviewer independently verified these tests fail against the pre-fix code (mutation testing via
`git archive`/in-place revert), not just that they pass against the fix -- recorded in
`plans/optic-views-actual-look/review.md`. Tests are meaningful, not decorative. No existing test
broken: full suite 2694 passed, 4 xfailed, same xfail count as before this change (unrelated to
this fix).

## Documentation

- Reviewer findings: **both review passes (`1b0d5de5` and the `_speech_log_sink` follow-on
  `8091730e`) returned Required Fixes: None.** One Optional Refinement is on record (the
  `optic_policy.py` five-construction-site convention that `_resolve_active_gaze`'s binocular
  branch depends on by convention, not by type/assert) -- explicitly optional, explicitly "not a
  defect, nothing in this diff weakens it," and the Reviewer's own agent-memory file
  (`feedback_shared_gaze_resolver_cross_site_convention.md`) records it as a pattern to re-check
  next time `optic_policy.py` is touched, not a blocking item here.
- Non-obvious behaviour: `_resolve_active_gaze`'s own docstring carries the three-case design
  rationale that used to live in `_render_pov_frame`'s deleted comment (Reviewer confirmed this is
  legitimate "the code says it itself now" pruning, not a loss).

## Security

No `security-plan-review.md` (no Architect plan for a bug fix, see above). `security.md` is the
deep-analysis pass, run after Reviewer, before DoD, per the bug-fix sequence -- **Verdict:
APPROVED**, no findings filed ("nothing here... rises to even a low-risk item").

## Performance

Not required by DoD's own checklist, but this batch ran it anyway per root `CLAUDE.md`'s "once per
batch" cadence (one batch: both commits together) -- `performance.md`: **Verdict: APPROVED**.

---

## Acceptance boundary -- what these fixtures structurally cannot reach

All 13 new tests, and the mutation-tested review, exercise `_resolve_active_gaze`,
`_render_eyesight_frame`, `_render_pov_frame`, and `_speech_log_sink` against a **fabricated
`runner`** (a test double with `SightHead`/`OpticState`/`scan_plan` fields set by hand) -- never
against a real DCS session, a real `AircraftLayerClient` poll, or a real terminal. That proves the
*logic* ("given these three input shapes, resolve this gaze") is correct. It cannot prove:

- that a **real** sortie's poll loop ever actually produces the three input shapes the tests
  assume (e.g. that `_apply_active_gaze` really does leave `OpticState.actual_aim_*` set exactly
  when the test doubles assume it is);
- that the **rendered ASCII output** in a real terminal, at real terminal width, with the real
  `--eyesight-view`/`--pov-view` flag combination, actually shows what a human reading it would
  call "the optic Petrovich is really looking through" -- a test asserting `frame.gaze.label ==
  "sight_wide"` is not the same claim as a pilot reading the top-view header and agreeing it names
  the right optic;
- that the **original symptom** (the 2026-10-26 sortie screenshot: `--eyesight-view` showing
  `3_oclock` while `--pov-view` showed the correct `+6/+1` boresight, same poll, same optic) is
  actually gone when both views are watched side by side in a live cockpit, including the one case
  the sortie did not happen to exercise (a binocular glass phase, per debug.md's "second, narrower
  finding").

This is exactly the F10-vocabulary class of gap named in this role's own standing instructions:
code that does what it says, verified against a fixture, where the fixture cannot see whether it
is the right subsystem or the right human-facing presentation. Live acceptance is **owed**, not
waived -- see below.

## Verdict: DoD PASSED (mechanical + review + security + performance)

Live flight acceptance is outstanding and tagged `#needs-flight` on `BL-B99`'s roadmap entry
(this fix corrects behaviour inside an already-`[x]`-done milestone, so it is an addendum there,
not a new entry -- see "Roadmap" below). Per root `CLAUDE.md`/this role's instructions, this does
not block merge: the user's Windows/DCS access is a separate resource from this review.

## Roadmap

No new BL-B/BL-<n> entry minted. This fix corrects a defect inside `[[BL-B99]]` (the `--pov-view`
milestone, already `[x]` #status/done), reported via `docs/acceptance/2026-10-26-sortie-feedback.md`.
Addendum appended to `body-layer/ROADMAP/BL-B99.md` itself (not the pointer `ROADMAP.md`) recording
this fix and re-adding `#needs-flight` since BL-B99's own `#needs-flight` tag from its original
merge was never cleared by a sortie, and this fix changes exactly the behaviour that tag covers.

**Does this change what the next milestone should be, or invalidate a downstream assumption?**
No. This is a correctness fix to an existing debug/calibration tool; it changes no brain-facing
API, no belief-state field, no `TOOL_SET` entry, and no tunable. The next actionable milestone is
unchanged.
